"""Live comparison/order semantics, not durable queue or completed-cycle proof."""

from dataclasses import FrozenInstanceError, replace
from itertools import groupby

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.fact_sources import FactSourceFingerprint
from custom_components.heima.v3.contracts.fact_state import fact_identity_key
from custom_components.heima.v3.contracts.fact_types import FactTypeClaim
from custom_components.heima.v3.contracts.generations import (
    ComposedGenerationManifest,
    LayerGenerationRef,
)
from custom_components.heima.v3.contracts.instants import EvidenceInstant
from custom_components.heima.v3.contracts.location import Location
from custom_components.heima.v3.contracts.payloads import PayloadErrorCode, PayloadValidationError
from custom_components.heima.v3.runtime.producer_staging import (
    StaticStateClaim,
    compose_fact_producers,
)
from custom_components.heima.v3.runtime.state_acceptance import (
    AcceptedStateTransition,
    AppendOrder,
    StateAcceptanceCoordinator,
    StateCycleContext,
)
from custom_components.heima.v3.runtime.state_producers import (
    FixedStateProducerRegistration,
    InactiveProducerGeneration,
    prepare_state_producer_generation,
)

WHEN = EvidenceInstant("2026-10-16T12:00:00.000000+00:00")
NEXT = EvidenceInstant("2026-10-16T12:00:00.000001+00:00")
CLAIM = StaticStateClaim("signal", Location("casa"), "owner")
SOURCE = FactSourceFingerprint("sensor", "sensor.a", None, "heima", "semantic", None)


def generation(identifier="g", source=SOURCE):
    manifest = ComposedGenerationManifest(
        identifier,
        None,
        tuple(
            LayerGenerationRef(layer, layer, layer + "-fp")
            for layer in ("layer2", "layer3", "layer4", "layer5", "layer6")
        ),
        "impact",
        (),
        "system",
        WHEN,
    )
    composed = compose_fact_producers(
        type_claims=(FactTypeClaim("signal", "owner", "state"),),
        state_claims=(CLAIM,),
        room_ids=frozenset(),
        zone_ids=frozenset(),
    )
    return prepare_state_producer_generation(
        manifest, composed, (FixedStateProducerRegistration(CLAIM, source),)
    )


def setup(*, last_cycle_id=0, sink=None):
    prepared = generation()
    active = {"value": prepared}
    diagnostics = []

    def reader():
        return active["value"]

    coordinator = StateAcceptanceCoordinator(
        reader, diagnostics.extend if sink is None else sink, last_cycle_id=last_cycle_id
    )
    return coordinator, active, prepared.bind(CLAIM, reader), diagnostics


def accept(coordinator, cycle, port, **overrides):
    args = dict(value="on", confidence=1)
    args.update(overrides)
    return coordinator.accept(cycle, port, **args)


def test_on_off_on_keeps_every_transition_at_one_instant_and_last_current():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    transitions = [accept(c, cycle, port, value=value) for value in ("on", "off", "on")]
    assert [t.fact.value for t in transitions] == ["on", "off", "on"]
    assert [t.order for t in transitions] == [
        AppendOrder(1, 1),
        AppendOrder(1, 2),
        AppendOrder(1, 3),
    ]
    assert all(
        t.fact.when == WHEN and t.fact.how.source.correlation_id == "origin" for t in transitions
    )
    key = fact_identity_key(transitions[0].fact)
    assert c.current(key) is transitions[2]
    assert c.allocate_order(cycle) == AppendOrder(1, 4)
    assert diags == []


@pytest.mark.parametrize(
    "overrides,changed",
    [
        ({}, False),
        ({"evidence": {"detail": "different"}}, False),
        ({"value": "off"}, True),
        ({"confidence": 0.5}, True),
        ({"value": True}, True),
        ({"available": False, "confidence": None}, True),
    ],
)
def test_state_change_decision_table(overrides, changed):
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    first = accept(c, cycle, port)
    second = accept(c, cycle, port, **overrides)
    assert (second is not None) is changed
    assert c.current(fact_identity_key(first.fact)) is (second if changed else first)
    assert c.allocate_order(cycle).ordinal == (3 if changed else 2)


def test_time_and_correlation_only_preserve_original_current_without_new_order():
    c, active, port, diags = setup()
    firstcycle = c.begin_cycle(WHEN, "first-origin")
    first = accept(c, firstcycle, port)
    c.end_cycle(firstcycle)
    secondcycle = c.begin_cycle(NEXT, "second-origin")
    assert accept(c, secondcycle, port) is None
    assert c.current(fact_identity_key(first.fact)) is first
    assert c.allocate_order(secondcycle) == AppendOrder(2, 1)


def test_live_comparison_does_not_depend_on_a_durable_acknowledgement():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    pending = [accept(c, cycle, port)]
    # No durable acknowledgement is supplied: these are still the live values.
    assert accept(c, cycle, port) is None
    pending.append(accept(c, cycle, port, value="off"))
    assert [t.fact.value for t in pending] == ["on", "off"]
    assert c.current(fact_identity_key(pending[0].fact)) is pending[-1]


def test_unavailable_stale_payload_changes_do_not_make_transitions():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    first = accept(c, cycle, port, available=False, confidence=None, value="old")
    assert accept(c, cycle, port, available=False, confidence=None, value=None) is None
    assert c.current(fact_identity_key(first.fact)) is first
    assert accept(c, cycle, port, available=True, confidence=0, value=None).order.ordinal == 2


def test_changed_staged_source_is_a_transition_even_with_same_value():
    c, active, oldport, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    first = accept(c, cycle, oldport)
    c.end_cycle(cycle)
    new = generation("next", replace(SOURCE, configuration_fingerprint="new-semantic"))
    active["value"] = new
    port = new.bind(CLAIM, lambda: active["value"])
    nextcycle = c.begin_cycle(NEXT, "origin2")
    second = accept(c, nextcycle, port)
    assert second.order == AppendOrder(2, 1)
    assert second.fact.value == first.fact.value
    assert second.fact.how.source.configuration_fingerprint == "new-semantic"


def test_shared_allocator_can_interleave_future_event_owner_orders():
    c, active, port, diags = setup(last_cycle_id=40)
    cycle = c.begin_cycle(WHEN, "origin")
    first = accept(c, cycle, port)
    future_event_order = c.allocate_order(cycle)
    third = accept(c, cycle, port, value="off")
    assert (first.order, future_event_order, third.order) == (
        AppendOrder(41, 1),
        AppendOrder(41, 2),
        AppendOrder(41, 3),
    )


def test_diagnostics_are_consumed_for_changed_and_unchanged_candidates():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    assert accept(c, cycle, port, evidence={"invalid": object()}) is not None
    assert accept(c, cycle, port, evidence=None) is None
    assert [d.code for d in diags] == [PayloadErrorCode.TYPE, PayloadErrorCode.MAPPING]
    assert accept(c, cycle, port) is None
    assert len(diags) == 2
    assert c.allocate_order(cycle).ordinal == 2


def test_builder_failure_leaves_index_and_order_unchanged_and_unlocks_coordinator():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    with pytest.raises(PayloadValidationError):
        accept(c, cycle, port, value=object())
    first = accept(c, cycle, port)
    assert first.order == AppendOrder(1, 1)
    assert c.current(fact_identity_key(first.fact)) is first


def test_diagnostic_failure_does_not_accept_or_consume_an_ordinal():
    calls = []

    def sink(diagnostics):
        calls.append(diagnostics)
        raise LookupError("diagnostic infrastructure failed")

    c, active, port, diags = setup(sink=sink)
    cycle = c.begin_cycle(WHEN, "origin")
    with pytest.raises(LookupError):
        accept(c, cycle, port, evidence=None)
    assert len(calls) == 1
    assert accept(c, cycle, port).order == AppendOrder(1, 1)


@pytest.mark.parametrize("action", ["accept", "allocate", "end", "begin"])
def test_reentrant_mutation_from_diagnostic_sink_is_rejected(action):
    state = {}

    def sink(diagnostics):
        c, cycle, port = state["args"]
        if action == "accept":
            accept(c, cycle, port, value="off")
        elif action == "allocate":
            c.allocate_order(cycle)
        elif action == "end":
            c.end_cycle(cycle)
        else:
            c.begin_cycle(NEXT, "other")

    c, active, port, diags = setup(sink=sink)
    cycle = c.begin_cycle(WHEN, "origin")
    state["args"] = (c, cycle, port)
    with pytest.raises(RuntimeError):
        accept(c, cycle, port, evidence=None)
    assert accept(c, cycle, port).order == AppendOrder(1, 1)


def test_generation_change_inside_diagnostic_sink_prevents_live_mutation():
    replacement = generation("replacement")
    active = {}

    def sink(diagnostics):
        active["value"] = replacement

    c, active, port, diags = setup(sink=sink)
    cycle = c.begin_cycle(WHEN, "origin")
    with pytest.raises(InactiveProducerGeneration):
        accept(c, cycle, port, evidence=None)
    c.end_cycle(cycle)
    newcycle = c.begin_cycle(NEXT, "new-origin")
    newport = replacement.bind(CLAIM, lambda: active["value"])
    assert accept(c, newcycle, newport).order == AppendOrder(2, 1)


def test_port_from_another_snapshot_is_rejected_even_if_its_own_reader_reports_active():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    other = generation()
    otherport = other.bind(CLAIM, lambda: other)
    with pytest.raises(InactiveProducerGeneration):
        accept(c, cycle, otherport)
    assert accept(c, cycle, port).order.ordinal == 1


@pytest.mark.parametrize("operation", ["accept", "allocate", "end"])
def test_closed_or_previous_cycle_handle_cannot_mutate_new_cycle(operation):
    c, active, port, diags = setup()
    old = c.begin_cycle(WHEN, "old")
    c.end_cycle(old)
    current = c.begin_cycle(NEXT, "current")
    with pytest.raises(RuntimeError):
        if operation == "accept":
            accept(c, old, port)
        elif operation == "allocate":
            c.allocate_order(old)
        else:
            c.end_cycle(old)
    assert accept(c, current, port).order == AppendOrder(2, 1)


@pytest.mark.parametrize("when", [WHEN, "2026-10-16T11:59:59.999999+00:00"])
def test_equal_or_backward_cycle_instant_is_not_accepted(when):
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    c.end_cycle(cycle)
    with pytest.raises(ValueError):
        c.begin_cycle(when, "other")
    assert c.begin_cycle(NEXT, "other").cycle_id == 2


def test_open_cycle_and_no_installed_generation_reject_before_allocating_cycle_id():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    with pytest.raises(RuntimeError):
        c.begin_cycle(NEXT, "other")
    c.end_cycle(cycle)
    active["value"] = None
    with pytest.raises(InactiveProducerGeneration):
        c.begin_cycle(NEXT, "other")
    active["value"] = port._generation
    assert c.begin_cycle(NEXT, "other").cycle_id == 2


def test_no_open_cycle_operations_and_invalid_types_reject():
    c, active, port, diags = setup()
    with pytest.raises(RuntimeError):
        c.allocate_order(None)
    with pytest.raises(RuntimeError):
        c.end_cycle(None)
    with pytest.raises(TypeError):
        c.current(None)
    cycle = c.begin_cycle(WHEN, "origin")
    with pytest.raises(TypeError):
        accept(c, cycle, None)
    assert accept(c, cycle, port).order.ordinal == 1


@pytest.mark.parametrize("when,origin", [("bad", "origin"), (WHEN, None), (WHEN, "\ud800")])
def test_invalid_cycle_inputs_do_not_consume_cycle_identity(when, origin):
    c, active, port, diags = setup()
    with pytest.raises((TypeError, ValueError)):
        c.begin_cycle(when, origin)
    assert c.begin_cycle(WHEN, "origin").cycle_id == 1


def test_record_validation_immutability_and_envelope_separation():
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    transition = accept(c, cycle, port)
    for record, field in ((cycle, "cycle_id"), (transition, "fact"), (transition.order, "ordinal")):
        assert not hasattr(record, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(record, field, None)
    with pytest.raises(TypeError):
        StateCycleContext()
    for bad in (True, 1.0, None):
        with pytest.raises(TypeError):
            AppendOrder(bad, 1)
        with pytest.raises(TypeError):
            AppendOrder(1, bad)
    for ordinal in (-1, 0):
        with pytest.raises(ValueError):
            AppendOrder(1, ordinal)
    with pytest.raises(TypeError):
        AcceptedStateTransition(None, AppendOrder(1, 1))
    with pytest.raises(TypeError):
        AcceptedStateTransition(transition.fact, None)
    assert not hasattr(transition.fact, "order")


def test_constructor_dependencies_are_explicit_and_seed_is_not_a_boolean():
    prepared = generation()
    c = StateAcceptanceCoordinator(lambda: prepared, lambda _: None)
    cycle = c.begin_cycle(WHEN, "origin")
    port = prepared.bind(CLAIM, lambda: prepared)
    transition = accept(c, cycle, port)
    assert transition.order == AppendOrder(1, 1)
    with pytest.raises(TypeError):
        StateAcceptanceCoordinator(None, lambda _: None)
    with pytest.raises(TypeError):
        StateAcceptanceCoordinator(lambda: None, None)
    with pytest.raises(TypeError):
        StateAcceptanceCoordinator(lambda: None, lambda _: None, last_cycle_id=True)


@settings(deadline=None)
@given(st.lists(st.booleans(), max_size=40))
def test_generated_same_instant_transitions_equal_run_length_changes(values):
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    transitions = []
    for value in values:
        transition = accept(c, cycle, port, value=value)
        if transition is not None:
            transitions.append(transition)
    assert [t.fact.value for t in transitions] == [value for value, group in groupby(values)]
    assert [t.order.ordinal for t in transitions] == list(range(1, len(transitions) + 1))
    assert c.allocate_order(cycle).ordinal == len(transitions) + 1
    if transitions:
        assert c.current(fact_identity_key(transitions[-1].fact)) is transitions[-1]


@settings(deadline=None)
@given(st.lists(st.integers(-5, 5), min_size=1, max_size=15))
def test_live_current_survives_cycle_close_and_order_resets(values):
    c, active, port, diags = setup()
    transitions = []
    for index, value in enumerate(values):
        when = EvidenceInstant(f"2026-10-16T12:00:00.{index:06d}+00:00")
        cycle = c.begin_cycle(when, str(index))
        transition = accept(c, cycle, port, value=value)
        if transition is not None:
            assert transition.order.ordinal == 1
            transitions.append(transition)
        c.end_cycle(cycle)
    assert [t.fact.value for t in transitions] == [value for value, group in groupby(values)]
    assert c.current(fact_identity_key(transitions[-1].fact)) is transitions[-1]


def test_live_lookup_is_unknown_before_the_first_accepted_state():
    c, active, port, diags = setup()
    candidate = port.build(value="on", confidence=1, when=WHEN, correlation_id="origin")
    assert c.current(fact_identity_key(candidate.fact)) is None


@pytest.mark.parametrize("operation", ["accept", "allocate"])
def test_installed_snapshot_replacement_invalidates_open_cycle(operation):
    c, active, port, diags = setup()
    cycle = c.begin_cycle(WHEN, "origin")
    active["value"] = generation()  # same manifest id, another installed image
    with pytest.raises(InactiveProducerGeneration):
        if operation == "accept":
            accept(c, cycle, port)
        else:
            c.allocate_order(cycle)
    c.end_cycle(cycle)
