"""Live state comparison and ordered transition handoff on one coordinator thread."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from ..contracts.canonical_json import canonical_json_bytes
from ..contracts.fact_state import (
    FactChangeFingerprint,
    FactIdentityKey,
    fact_change_fingerprint,
    fact_identity_key,
)
from ..contracts.house_facts import HouseFact
from ..contracts.instants import EvidenceInstant, parse_instant
from ..contracts.payloads import PayloadDiagnostic
from .state_producers import (
    ActiveStateGeneration,
    FixedSourceStateProducer,
    InactiveProducerGeneration,
    PreparedStateProducerGeneration,
)

_OMITTED = object()


@dataclass(frozen=True, slots=True)
class AppendOrder:
    cycle_id: int
    ordinal: int

    def __post_init__(self) -> None:
        if type(self.cycle_id) is not int:
            raise TypeError("Cycle id must be a primitive integer")
        if type(self.ordinal) is not int:
            raise TypeError("Append ordinal must be a primitive integer")
        if self.ordinal < 1:
            raise ValueError("Accepted append ordinals start at one")


@dataclass(frozen=True, slots=True)
class AcceptedStateTransition:
    fact: HouseFact
    order: AppendOrder

    def __post_init__(self) -> None:
        if type(self.fact) is not HouseFact:
            raise TypeError("A transition requires a concrete fact")
        if type(self.order) is not AppendOrder:
            raise TypeError("A transition requires a concrete append order")
        AppendOrder.__post_init__(self.order)


@dataclass(frozen=True, slots=True, init=False)
class StateCycleContext:
    cycle_id: int
    when: EvidenceInstant
    correlation_id: str
    generation: PreparedStateProducerGeneration

    def __init__(self) -> None:
        raise TypeError("Begin a cycle through StateAcceptanceCoordinator")


@dataclass(frozen=True, slots=True)
class _CurrentState:
    transition: AcceptedStateTransition
    fingerprint: FactChangeFingerprint


class StateAcceptanceCoordinator:
    """Live-index/order step; the owner forwards each return to buffer and queue.

    No retry journal or short-term history is retained here. Forwarding must happen
    synchronously before the next admission. The durable coordinator supplies its
    restored cycle-id seed and installed-generation reader; no database proof is
    inferred from an object/id. No await or concurrent thread access is permitted.
    """

    def __init__(
        self,
        read_active: ActiveStateGeneration,
        report_diagnostics: Callable[[tuple[PayloadDiagnostic, ...]], None],
        *,
        last_cycle_id: int = 0,
    ) -> None:
        if not callable(read_active):
            raise TypeError("Coordinator requires an active-generation reader")
        if not callable(report_diagnostics):
            raise TypeError("Coordinator requires a diagnostic sink")
        if type(last_cycle_id) is not int:
            raise TypeError("Cycle id seed must be a primitive integer")
        self._read_active = read_active
        self._report_diagnostics = report_diagnostics
        self._last_cycle_id = last_cycle_id
        self._last_when: EvidenceInstant | None = None
        self._cycle: StateCycleContext | None = None
        self._ordinal = 0
        self._busy = False
        self._current: dict[FactIdentityKey, _CurrentState] = {}

    @contextmanager
    def _mutation(self) -> Iterator[None]:
        if self._busy:
            raise RuntimeError("Coordinator mutation cannot reenter")
        self._busy = True
        try:
            yield
        finally:
            self._busy = False

    def begin_cycle(self, when: EvidenceInstant, correlation_id: str) -> StateCycleContext:
        with self._mutation():
            if self._cycle is not None:
                raise RuntimeError("An evaluation cycle is already open")
            parse_instant(when)
            if self._last_when is not None:
                if when <= self._last_when:
                    raise ValueError("Cycle instant must increase strictly")
            if type(correlation_id) is not str:
                raise TypeError("Cycle origin must be a primitive string")
            canonical_json_bytes(correlation_id)
            generation = self._read_active()
            if type(generation) is not PreparedStateProducerGeneration:
                raise InactiveProducerGeneration("No producer generation is installed")
            cycle = object.__new__(StateCycleContext)
            object.__setattr__(cycle, "cycle_id", self._last_cycle_id + 1)
            object.__setattr__(cycle, "when", when)
            object.__setattr__(cycle, "correlation_id", correlation_id)
            object.__setattr__(cycle, "generation", generation)
            self._last_cycle_id = cycle.cycle_id
            self._last_when = when
            self._ordinal = 0
            self._cycle = cycle
            return cycle

    def _require_open(self, cycle: StateCycleContext) -> None:
        if self._cycle is None:
            raise RuntimeError("No evaluation cycle is open")
        if self._cycle is not cycle:
            raise RuntimeError("Cycle context is no longer current")

    def _require_current(self, cycle: StateCycleContext) -> None:
        self._require_open(cycle)
        if self._read_active() is not cycle.generation:
            raise InactiveProducerGeneration("Cycle generation is no longer installed")

    def _allocate_order(self, cycle: StateCycleContext) -> AppendOrder:
        order = AppendOrder(cycle.cycle_id, self._ordinal + 1)
        self._ordinal = order.ordinal
        return order

    def allocate_order(self, cycle: StateCycleContext) -> AppendOrder:
        """Shared coordinator allocator for future event owners; not event admission."""
        with self._mutation():
            self._require_current(cycle)
            return self._allocate_order(cycle)

    def end_cycle(self, cycle: StateCycleContext) -> None:
        """Close even after a generation failure; this creates no durable marker."""
        with self._mutation():
            self._require_open(cycle)
            self._cycle = None

    def current(self, key: FactIdentityKey) -> AcceptedStateTransition | None:
        if type(key) is not FactIdentityKey:
            raise TypeError("Live state lookup requires a fact identity key")
        state = self._current.get(key)
        return None if state is None else state.transition

    def accept(
        self,
        cycle: StateCycleContext,
        producer: FixedSourceStateProducer,
        *,
        value: object,
        confidence: float | None,
        available: bool = True,
        evidence: object = _OMITTED,
    ) -> AcceptedStateTransition | None:
        """Build, consume diagnostics, compare live state and hand off one change.

        An unchanged observation leaves the index/order untouched. No synchronous
        durable write occurs; the caller must forward returned transitions inline.
        Forced durable baselines and event facts require separate paths.
        """
        with self._mutation():
            self._require_current(cycle)
            if type(producer) is not FixedSourceStateProducer:
                raise TypeError("State admission requires a bound fixed-source producer")
            producer.require_generation(cycle.generation)
            built = producer.build(
                value=value,
                when=cycle.when,
                correlation_id=cycle.correlation_id,
                confidence=confidence,
                available=available,
                evidence={} if evidence is _OMITTED else evidence,
            )
            key = fact_identity_key(built.fact)
            fingerprint = fact_change_fingerprint(built.fact)
            if built.diagnostics:
                self._report_diagnostics(built.diagnostics)
            self._require_current(cycle)
            previous = self._current.get(key)
            if previous is not None:
                if previous.fingerprint == fingerprint:
                    return None
            transition = AcceptedStateTransition(built.fact, self._allocate_order(cycle))
            self._current[key] = _CurrentState(transition, fingerprint)
            return transition
