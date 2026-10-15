"""L0 §4.0 identities are distinct from current-state change content."""

from dataclasses import FrozenInstanceError, dataclass, fields, replace
from math import nextafter
from types import MappingProxyType
from typing import cast

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes
from custom_components.heima.v3.contracts.fact_sources import FactSource, fact_source_fingerprint
from custom_components.heima.v3.contracts.fact_state import (
    FactChangeFingerprint,
    FactIdentityKey,
    fact_change_fingerprint,
    fact_identity_key,
)
from custom_components.heima.v3.contracts.house_facts import HouseFact, build_house_fact
from custom_components.heima.v3.contracts.instants import EvidenceInstant
from custom_components.heima.v3.contracts.location import Location

SOURCE = FactSource("sensor", "sensor.a", "temperature", "config-a", "route-a", "heima", "origin-a")
WHEN = EvidenceInstant("2026-10-15T12:00:00.000000+00:00")


def fact(**overrides: object) -> HouseFact:
    arguments = dict(
        fact_type="temperature",
        value=20,
        where=Location("room", room_id="a"),
        when=WHEN,
        source=SOURCE,
        confidence=1,
        available=True,
        evidence={},
    )
    arguments.update(overrides)
    return build_house_fact(**arguments).fact


@pytest.mark.parametrize(
    "overrides,identity_changed,state_changed",
    [
        ({}, False, False),
        ({"when": EvidenceInstant("2026-10-15T12:00:00.000001+00:00")}, False, False),
        ({"source": replace(SOURCE, correlation_id="new-origin")}, False, False),
        ({"evidence": {"reason": "new detail"}}, False, False),
        ({"value": 21}, False, True),
        ({"confidence": 0.5}, False, True),
        ({"available": False, "confidence": None}, False, True),
        ({"fact_type": "humidity"}, True, False),
        ({"where": Location("room", room_id="b")}, True, False),
    ],
)
def test_identity_and_state_decision_table(overrides, identity_changed, state_changed):
    before, after = fact(), fact(**overrides)
    assert (fact_identity_key(before) != fact_identity_key(after)) is identity_changed
    assert (fact_change_fingerprint(before) != fact_change_fingerprint(after)) is state_changed
    if overrides:
        assert before != after


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "analyzer"),
        ("source_id", "sensor.b"),
        ("source_type", "humidity"),
        ("actor_type", "resident"),
        ("configuration_fingerprint", None),
        ("route_fingerprint", None),
    ],
)
@pytest.mark.parametrize("available", [True, False])
def test_each_stable_source_field_changes_state_without_changing_identity(field, value, available):
    kwargs = dict(available=available, confidence=1 if available else None)
    before = fact(**kwargs)
    after = fact(source=replace(SOURCE, **{field: value}), **kwargs)
    assert fact_identity_key(before) == fact_identity_key(after)
    assert fact_change_fingerprint(before) != fact_change_fingerprint(after)


@pytest.mark.parametrize(
    "left,right,equal",
    [
        (True, 1, False),
        (False, 0, False),
        (1, 1.0, True),
        (-0.0, 0, True),
        ({"x": True}, {"x": 1}, False),
        ({"b": 2, "a": [1]}, {"a": [1.0], "b": 2}, True),
        (0, nextafter(0, 1), False),
        (1, nextafter(1, 0), False),
    ],
)
def test_canonical_value_equivalence(left, right, equal):
    a, b = map(fact_change_fingerprint, (fact(value=left), fact(value=right)))
    assert (a == b) is equal
    assert (a != b) is not equal
    assert hash(a) == hash(canonical_json_bytes(a))
    if equal:
        assert hash(a) == hash(b)
        assert len({a, b}) == 1


@pytest.mark.parametrize("confidence", [0, nextafter(0, 1), nextafter(1, 0)])
def test_confidence_changes_at_valid_boundaries(confidence):
    assert fact_change_fingerprint(fact(confidence=confidence)) != fact_change_fingerprint(fact())


def test_confidence_canonical_equivalence():
    assert fact_change_fingerprint(fact(confidence=1)) == fact_change_fingerprint(
        fact(confidence=1.0)
    )
    assert fact_change_fingerprint(fact(confidence=-0.0)) == fact_change_fingerprint(
        fact(confidence=0)
    )


@given(st.one_of(st.none(), st.booleans(), st.integers(-(2**53 - 1), 2**53 - 1), st.text()))
def test_unavailable_value_is_irrelevant(value):
    a = fact_change_fingerprint(fact(value=value, available=False, confidence=None))
    b = fact_change_fingerprint(fact(value=None, available=False, confidence=None))
    assert a.value is None
    assert a == b and hash(a) == hash(b)


def test_unavailable_value_is_not_inspected():
    unavailable = fact(available=False, confidence=None)
    # A poison sentinel proves the extraction path never projects undefined value.
    # Forged facts are otherwise outside this builder-output API's contract.
    object.__setattr__(unavailable, "value", object())
    result = fact_change_fingerprint(unavailable)
    assert result.value is None
    assert canonical_json_bytes(result)


@dataclass(frozen=True)
class Reading:
    samples: tuple[object, ...]
    unit: str


@given(st.lists(st.integers(-1000, 1000), max_size=10))
def test_typed_and_json_values_have_the_same_normalized_projection(samples):
    typed = fact_change_fingerprint(fact(value=Reading(tuple(samples), "C")))
    plain = fact_change_fingerprint(fact(value={"samples": samples, "unit": "C"}))
    assert type(typed.value) is MappingProxyType
    assert typed.value == plain.value
    assert typed == plain and hash(typed) == hash(plain)
    assert canonical_json_bytes(typed) == canonical_json_bytes(plain)


def test_nested_record_projection_is_immutable_and_detached():
    values = [1, 2]
    result = fact_change_fingerprint(fact(value=Reading(tuple(values), "C")))
    values.append(3)
    value = cast(dict, result.value)
    assert value["samples"] == (1, 2)
    with pytest.raises(TypeError):
        value["x"] = 1
    with pytest.raises(TypeError):
        value["unit"] = "F"


@given(st.text(), st.text())
def test_metadata_changes_preserve_identity_and_state(correlation, detail):
    before = fact()
    after = fact(
        source=replace(SOURCE, correlation_id=correlation),
        evidence={"detail": detail},
        when=EvidenceInstant("2026-10-16T00:00:00.000000+00:00"),
    )
    assert fact_identity_key(before) == fact_identity_key(after)
    assert hash(fact_identity_key(before)) == hash(fact_identity_key(after))
    assert fact_change_fingerprint(before) == fact_change_fingerprint(after)


def test_location_set_order_and_opaque_identity():
    a = fact_identity_key(fact(where=Location("rooms", room_ids=frozenset(("z", "a")))))
    b = fact_identity_key(fact(where=Location("rooms", room_ids=frozenset(("a", "z")))))
    assert a == b and hash(a) == hash(b)
    assert len({a, b}) == 1
    for location in (
        Location("casa"),
        Location("zone", zone_id="a"),
        Location("room", room_id="A"),
        Location("room", room_id=" a"),
    ):
        assert fact_identity_key(fact(where=location)) != fact_identity_key(fact())


def test_equal_instant_transition_fingerprints_do_not_coalesce_intermediate_state():
    records = [fact(value=value) for value in ("on", "off", "on")]
    fingerprints = list(map(fact_change_fingerprint, records))
    assert len(set(map(fact_identity_key, records))) == 1
    assert fingerprints[0] != fingerprints[1]
    assert fingerprints[1] != fingerprints[2]
    assert fingerprints[0] == fingerprints[2]


def test_exact_envelopes_and_source_projection():
    key = fact_identity_key(fact())
    change = fact_change_fingerprint(fact())
    assert [field.name for field in fields(key)] == ["fact_type", "where"]
    assert [field.name for field in fields(change)] == [
        "available",
        "confidence",
        "value",
        "source",
    ]
    assert change.available is True and change.confidence == 1 and change.value == 20
    assert change.source == fact_source_fingerprint(SOURCE)
    assert key.fact_type == "temperature" and key.where == Location("room", room_id="a")
    for record, field in ((key, "fact_type"), (change, "value")):
        assert not hasattr(record, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(record, field, None)
    assert change.__eq__(object()) is NotImplemented
    assert change != object()


@pytest.mark.parametrize("record", [FactIdentityKey, FactChangeFingerprint])
def test_direct_construction_requires_factory(record):
    with pytest.raises(TypeError):
        record()


@pytest.mark.parametrize("extract", [fact_identity_key, fact_change_fingerprint])
@pytest.mark.parametrize("invalid", [None, {}, SOURCE, object()])
def test_extraction_requires_concrete_builder_output(extract, invalid):
    with pytest.raises(TypeError):
        extract(invalid)
