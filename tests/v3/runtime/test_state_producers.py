"""Producer generations are staging data until the coordinator installs them."""

from dataclasses import FrozenInstanceError, dataclass, replace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.fact_sources import FactSourceFingerprint
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
from custom_components.heima.v3.runtime.state_producers import (
    FixedSourceStateProducer,
    FixedStateProducerRegistration,
    InactiveProducerGeneration,
    PreparedStateProducerGeneration,
    prepare_state_producer_generation,
)

WHEN = EvidenceInstant("2026-10-15T12:00:00.000000+00:00")
CLAIM = StaticStateClaim("temperature", Location("room", room_id="r"), "layer2.sensor")
SOURCE = FactSourceFingerprint("sensor", "sensor.a", "temperature", "heima", "semantic-a", None)


def generation(identifier="g1", source=SOURCE):
    manifest = ComposedGenerationManifest(
        identifier,
        None,
        tuple(
            LayerGenerationRef(layer, layer + "-id", layer + "-fp")
            for layer in ("layer2", "layer3", "layer4", "layer5", "layer6")
        ),
        "impact",
        (),
        "system",
        WHEN,
    )
    composition = compose_fact_producers(
        type_claims=(FactTypeClaim("temperature", "layer2.sensor", "state"),),
        state_claims=(CLAIM,),
        room_ids=frozenset(("r",)),
        zone_ids=frozenset(),
    )
    return prepare_state_producer_generation(
        manifest, composition, (FixedStateProducerRegistration(CLAIM, source),)
    )


def build(port, **overrides):
    args = dict(value=20, when=WHEN, correlation_id="cycle-origin", confidence=0.75)
    args.update(overrides)
    return port.build(**args)


def test_current_port_assigns_every_staged_source_field_and_claim():
    source = replace(
        SOURCE,
        kind="analyzer",
        source_type="family",
        actor_type="scheduler",
        route_fingerprint="fixed-route",
    )
    current = generation(source=source)
    port = current.bind(CLAIM, lambda: current)
    result = build(port)
    fact = result.fact
    assert fact.fact_type == CLAIM.fact_type and fact.where == CLAIM.where and fact.when == WHEN
    assert fact.how.source.kind == "analyzer"
    assert fact.how.source.source_id == "sensor.a"
    assert fact.how.source.source_type == "family"
    assert fact.how.source.actor_type == "scheduler"
    assert fact.how.source.configuration_fingerprint == "semantic-a"
    assert fact.how.source.route_fingerprint == "fixed-route"
    assert fact.how.source.correlation_id == "cycle-origin"
    assert fact.value == 20 and fact.how.confidence == 0.75 and fact.how.available is True
    assert result.diagnostics == ()


@pytest.mark.parametrize("state", ["none", "future", "current", "old", "same-id-copy"])
def test_active_generation_decision_table(state):
    prepared = generation()
    active = {"value": None}
    port = prepared.bind(CLAIM, lambda: active["value"])
    if state == "current":
        active["value"] = prepared
    elif state == "future":
        active["value"] = generation("older")
    elif state == "old":
        active["value"] = generation("newer")
    elif state == "same-id-copy":
        active["value"] = generation()
    if state == "current":
        assert build(port).fact.value == 20
    else:
        with pytest.raises(InactiveProducerGeneration):
            build(port)


def test_generation_swap_updates_fingerprint_and_blocks_old_port():
    old = generation()
    new = generation("g2", replace(SOURCE, configuration_fingerprint="semantic-b"))
    active = {"value": old}
    first = old.bind(CLAIM, lambda: active["value"])
    second = new.bind(CLAIM, lambda: active["value"])
    assert build(first).fact.how.source.configuration_fingerprint == "semantic-a"
    with pytest.raises(InactiveProducerGeneration):
        build(second)
    active["value"] = new
    with pytest.raises(InactiveProducerGeneration):
        build(first)
    assert build(second).fact.how.source.configuration_fingerprint == "semantic-b"


def test_generation_change_during_payload_read_rejects_result():
    old, new = generation(), generation("new")
    active = {"value": old}

    @dataclass(frozen=True)
    class Reentrant:
        reading: int

        def __getattribute__(self, name):
            if name == "reading":
                active["value"] = new
            return object.__getattribute__(self, name)

    port = old.bind(CLAIM, lambda: active["value"])
    with pytest.raises(InactiveProducerGeneration):
        build(port, value=Reentrant(1))


def test_inactive_port_rejects_before_inspecting_payload():
    @dataclass(frozen=True)
    class Poison:
        reading: int

        def __getattribute__(self, name):
            if name == "reading":
                pytest.fail("inactive producer inspected a payload")
            return object.__getattribute__(self, name)

    current = generation()
    with pytest.raises(InactiveProducerGeneration):
        build(current.bind(CLAIM, lambda: None), value=Poison(1))


def test_runtime_cannot_override_staged_source_or_claim():
    current = generation()
    port = current.bind(CLAIM, lambda: current)
    for overrides in (
        {"source": SOURCE},
        {"fact_type": "manual_hold.lifecycle"},
        {"where": Location("casa")},
        {"configuration_fingerprint": "old"},
        {"owner_id": "other"},
        {"route_fingerprint": "other"},
    ):
        with pytest.raises(TypeError):
            build(port, **overrides)


def test_causal_id_is_propagated_without_uuid_safety_net(monkeypatch):
    from custom_components.heima.v3.contracts import fact_sources

    def forbidden():
        pytest.fail("port minted a correlation id")

    monkeypatch.setattr(fact_sources, "uuid4", forbidden)
    current = generation()
    port = current.bind(CLAIM, lambda: current)
    assert (
        build(port, correlation_id="explicit-origin").fact.how.source.correlation_id
        == "explicit-origin"
    )


def test_hard_value_failure_and_soft_evidence_diagnostic_are_preserved():
    current = generation()
    port = current.bind(CLAIM, lambda: current)
    with pytest.raises(PayloadValidationError):
        build(port, value=object())
    result = build(port, evidence={"raw": object()})
    assert result.fact.value == 20 and result.fact.how.evidence == {}
    assert result.diagnostics[0].code is PayloadErrorCode.TYPE
    assert build(port).diagnostics == ()
    assert build(port, evidence=None).diagnostics[0].code is PayloadErrorCode.MAPPING
    unavailable = build(port, value="old", available=False, confidence=None).fact
    assert unavailable.value == "old" and unavailable.how.available is False
    assert unavailable.how.confidence is None


@pytest.mark.parametrize(
    "source",
    [
        replace(SOURCE, kind="test"),
        replace(SOURCE, actor_type="test"),
        replace(SOURCE, kind="legacy"),
    ],
)
def test_production_registration_rejects_test_and_legacy_sources(source):
    with pytest.raises(ValueError):
        FixedStateProducerRegistration(CLAIM, source)


def test_registration_and_preparation_validate_concrete_shapes():
    with pytest.raises(TypeError):
        FixedStateProducerRegistration(None, SOURCE)
    with pytest.raises(TypeError):
        FixedStateProducerRegistration(CLAIM, None)
    with pytest.raises(ValueError):
        FixedStateProducerRegistration(CLAIM, replace(SOURCE, source_id="\ud800"))
    prepared = generation()
    with pytest.raises(TypeError):
        prepare_state_producer_generation(None, prepared.composition, ())
    with pytest.raises(TypeError):
        prepare_state_producer_generation(prepared.manifest, None, ())
    with pytest.raises(TypeError):
        prepare_state_producer_generation(prepared.manifest, prepared.composition, [])
    with pytest.raises(TypeError):
        prepare_state_producer_generation(prepared.manifest, prepared.composition, (None,))


def test_unclaimed_wrong_owner_and_duplicate_registrations_reject():
    prepared = generation()
    good = FixedStateProducerRegistration(CLAIM, SOURCE)
    for registrations in (
        (good, good),
        (
            FixedStateProducerRegistration(
                StaticStateClaim("temperature", CLAIM.where, "other"), SOURCE
            ),
        ),
        (
            FixedStateProducerRegistration(
                StaticStateClaim("other", CLAIM.where, "layer2.sensor"), SOURCE
            ),
        ),
    ):
        with pytest.raises(ValueError):
            prepare_state_producer_generation(
                prepared.manifest, prepared.composition, registrations
            )


def test_binding_requires_prepared_identity_owner_and_reader():
    prepared = generation()
    for invalid in (
        None,
        StaticStateClaim("other", CLAIM.where, CLAIM.owner_id),
        StaticStateClaim(CLAIM.fact_type, Location("casa"), CLAIM.owner_id),
        StaticStateClaim(CLAIM.fact_type, CLAIM.where, "other"),
    ):
        with pytest.raises((TypeError, ValueError)):
            prepared.bind(invalid, lambda: prepared)
    with pytest.raises(TypeError):
        prepared.bind(CLAIM, None)
    empty = prepare_state_producer_generation(prepared.manifest, prepared.composition, ())
    with pytest.raises(ValueError):
        empty.bind(CLAIM, lambda: empty)


def test_records_and_map_are_immutable_and_snapshot_inputs_owned():
    prepared = generation()
    port = prepared.bind(CLAIM, lambda: prepared)
    registration = prepared._producers[(CLAIM.fact_type, CLAIM.where)]
    assert registration.claim is not CLAIM and registration.source is not SOURCE
    for record, field in ((registration, "source"), (prepared, "manifest"), (port, "_generation")):
        assert not hasattr(record, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(record, field, None)
    with pytest.raises(TypeError):
        prepared._producers[(CLAIM.fact_type, CLAIM.where)] = registration
    with pytest.raises(TypeError):
        PreparedStateProducerGeneration()
    with pytest.raises(TypeError):
        FixedSourceStateProducer()


@settings(deadline=None)
@given(st.integers(-(2**53 - 1), 2**53 - 1), st.text())
def test_fixed_source_and_semantic_fingerprint_survive_value_and_origin_changes(value, origin):
    prepared = generation()
    port = prepared.bind(CLAIM, lambda: prepared)
    result = build(port, value=value, correlation_id=origin).fact
    assert result.value == value
    assert result.how.source.source_id == SOURCE.source_id
    assert result.how.source.configuration_fingerprint == SOURCE.configuration_fingerprint
    assert result.how.source.correlation_id == origin


@settings(deadline=None)
@given(st.lists(st.text(alphabet="abc", max_size=5), min_size=1, max_size=10))
def test_equal_ids_never_resurrect_captured_generation(ids):
    prepared = generation()
    active = {"value": prepared}
    port = prepared.bind(CLAIM, lambda: active["value"])
    for identifier in ids:
        active["value"] = generation(identifier)
        with pytest.raises(InactiveProducerGeneration):
            build(port)


def test_runtime_build_uses_no_claim_pattern_lookup(monkeypatch):
    from custom_components.heima.v3.contracts import fact_types
    from custom_components.heima.v3.runtime import producer_staging

    prepared = generation()
    port = prepared.bind(CLAIM, lambda: prepared)

    def forbidden(*args, **kwargs):
        pytest.fail("claim pattern resolution reached the per-fact path")

    monkeypatch.setattr(fact_types, "fact_type_matches", forbidden)
    monkeypatch.setattr(producer_staging, "fact_type_matches", forbidden)
    monkeypatch.setattr(producer_staging.ComposedFactProducers, "resolve_type", forbidden)
    assert build(port).fact.value == 20
