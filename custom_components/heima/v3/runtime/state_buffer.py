"""State-only short-term retention; no policy query, queue, or source admission."""

from collections import deque
from collections.abc import Mapping
from types import MappingProxyType

from ..contracts.deadlines import Unrepresentable, derive_instant
from ..contracts.fact_state import FactIdentityKey, fact_identity_key
from ..contracts.instants import EvidenceInstant, parse_instant
from ..contracts.timing import Window
from .state_acceptance import AcceptedStateTransition

_DEFAULT_HORIZON_SECONDS = 15 * 60


class StateTransitionBuffer:
    """Retain trusted coordinator outputs and a predecessor per registered key.

    The owner supplies a complete staged key/horizon map and serializes calls.
    No producer ownership or installed-generation authority is inferred here.
    Append is in-memory only. Maintenance runs outside evaluation and receives a
    cycle-clock instant that future appends cannot predate. Raw immutable record
    snapshots do not certify observation coverage or implement FrozenHistoryView.
    """

    def __init__(self, horizons: Mapping[FactIdentityKey, Window]) -> None:
        owned: dict[FactIdentityKey, Window] = {}
        for key, horizon in horizons.items():
            if type(key) is not FactIdentityKey:
                raise TypeError("State buffer requires registered state identity keys")
            if not isinstance(horizon, Window):
                raise TypeError("State buffer horizon requires Window")
            validated = Window(horizon.seconds)
            owned[key] = Window(max(_DEFAULT_HORIZON_SECONDS, validated.seconds))
        self._horizons = MappingProxyType(owned)
        self._streams: dict[FactIdentityKey, deque[AcceptedStateTransition]] = {
            key: deque() for key in owned
        }
        self._last: AcceptedStateTransition | None = None
        self._maintenance_when: EvidenceInstant | None = None

    def _stream(self, key: FactIdentityKey) -> deque[AcceptedStateTransition]:
        if type(key) is not FactIdentityKey:
            raise TypeError("State buffer lookup requires a state identity key")
        return self._streams[key]

    def effective_horizon(self, key: FactIdentityKey) -> Window:
        self._stream(key)
        return self._horizons[key]

    def records(self, key: FactIdentityKey) -> tuple[AcceptedStateTransition, ...]:
        """Raw retained records; not a history-completeness or policy read API."""
        return tuple(self._stream(key))

    def append(self, transition: AcceptedStateTransition) -> None:
        """Append one already accepted state transition, never deduplicate values."""
        if type(transition) is not AcceptedStateTransition:
            raise TypeError("State buffer requires an accepted state transition")
        AcceptedStateTransition.__post_init__(transition)
        stream = self._stream(fact_identity_key(transition.fact))
        when, order = transition.fact.when, transition.order
        if self._maintenance_when is not None:
            if when < self._maintenance_when:
                raise ValueError("Append predates the maintenance clock")
        previous = self._last
        if previous is not None:
            before = previous.order
            if (order.cycle_id, order.ordinal) <= (before.cycle_id, before.ordinal):
                raise ValueError("State append order must increase strictly")
            if order.cycle_id == before.cycle_id:
                if when != previous.fact.when:
                    raise ValueError("One cycle must have one instant")
            elif when <= previous.fact.when:
                raise ValueError("A later cycle must have a later instant")
        stream.append(transition)
        self._last = transition

    def maintain(self, now: EvidenceInstant) -> int:
        """Evict superseded history outside horizons; keep each needed predecessor.

        O(registered streams + removed records), with no scan of retained history.
        Tuple snapshots already held by a reader retain their immutable records.
        This is explicit background maintenance, never implicit work in append.
        """
        parse_instant(now)
        if self._maintenance_when is not None:
            if now < self._maintenance_when:
                raise ValueError("Maintenance clock cannot regress")
        if self._last is not None:
            if now < self._last.fact.when:
                raise ValueError("Maintenance cannot predate accepted records")
        removed = 0
        for key, stream in self._streams.items():
            while len(stream) > 1:
                # The successor proves the first record is no longer needed at
                # the retained window's start. A lone current record never expires.
                expiry = derive_instant(stream[1].fact.when, self._horizons[key])
                if isinstance(expiry, Unrepresentable):
                    break
                if expiry > now:
                    break
                stream.popleft()
                removed += 1
        self._maintenance_when = now
        return removed
