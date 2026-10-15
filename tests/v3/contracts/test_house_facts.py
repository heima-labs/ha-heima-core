"""Complete immutable fact assembly, hard value failures and soft evidence loss."""

import json
import math
from dataclasses import FrozenInstanceError, dataclass, fields, replace

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts import fact_sources
from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes
from custom_components.heima.v3.contracts.fact_sources import ApplyStepSource, FactSource
from custom_components.heima.v3.contracts.house_facts import (
    FactBuildResult,
    HouseFact,
    Provenance,
    build_house_fact,
    house_fact_canonical_bytes,
)
from custom_components.heima.v3.contracts.location import Location
from custom_components.heima.v3.contracts.payloads import PayloadErrorCode, PayloadValidationError

WHEN = "2026-01-01T00:00:00.000000+00:00"


def build(**changes):
    inputs = dict(
        fact_type="room.signal",
        value="on",
        where=Location("room", room_id="kitchen"),
        when=WHEN,
        source=FactSource("reaction", "r", correlation_id="origin"),
        confidence=0.75,
    )
    inputs.update(changes)
    return build_house_fact(**inputs)


def test_builder_has_exact_envelopes_and_diagnostics_are_local_only():
    result = build()
    assert type(result) is FactBuildResult
    assert result.diagnostics == ()
    assert {f.name for f in fields(result.fact)} == {"fact_type", "value", "where", "when", "how"}
    assert {f.name for f in fields(result.fact.how)} == {
        "confidence",
        "source",
        "available",
        "evidence",
    }
    assert result.fact.how.available is True
    assert result.fact.how.confidence == 0.75
    assert result.fact.how.evidence == {}
    encoded = json.loads(house_fact_canonical_bytes(result.fact))
    assert set(encoded) == {"fact_type", "value", "where", "when", "how"}
    assert encoded["where"] == {
        "scope": "room",
        "room_id": "kitchen",
        "zone_id": None,
        "room_ids": None,
    }
    assert "diagnostics" not in encoded


@pytest.mark.parametrize(
    "available,confidence,valid",
    [
        (True, None, False),
        (True, 0.0, True),
        (True, 1.0, True),
        (False, None, True),
        (False, 0.0, False),
        (False, 1.0, False),
    ],
)
def test_availability_confidence_decision_table(available, confidence, valid):
    if valid:
        result = build(available=available, confidence=confidence)
        assert result.fact.how.available is available
        assert result.fact.how.confidence == confidence
    else:
        with pytest.raises(ValueError):
            build(available=available, confidence=confidence)


@pytest.mark.parametrize(
    "confidence,valid",
    [
        (-math.ulp(0.0), False),
        (-0.0, True),
        (0, True),
        (math.ulp(0.0), True),
        (math.nextafter(1.0, 0.0), True),
        (1, True),
        (1.0, True),
        (math.nextafter(1.0, math.inf), False),
        (math.nan, False),
        (math.inf, False),
        (-math.inf, False),
        (10**400, False),
    ],
)
def test_confidence_boundary_values_without_rounding_or_overflow(confidence, valid):
    if valid:
        result = build(confidence=confidence)
        assert result.fact.how.confidence == confidence
        assert type(result.fact.how.confidence) is type(confidence)
    else:
        with pytest.raises(ValueError):
            build(confidence=confidence)


@pytest.mark.parametrize("confidence", [True, False, "0.5", object()])
def test_confidence_rejects_boolean_and_non_numbers(confidence):
    with pytest.raises(TypeError):
        build(confidence=confidence)


@pytest.mark.parametrize("available", [1, 0, None, "true"])
def test_availability_is_boolean_not_truthiness(available):
    with pytest.raises(TypeError):
        build(available=available)


@pytest.mark.parametrize("value", [None, "previous", {"state": "off"}, False])
def test_unavailable_value_is_preserved_without_becoming_usable(value):
    result = build(available=False, confidence=None, value=value)
    assert result.fact.value == value
    assert result.fact.how.confidence is None
    assert result.fact.how.available is False


@pytest.mark.parametrize("available", [False, True])
@pytest.mark.parametrize("value", [object(), b"raw", 2**53, math.inf, {"a": {"b": []}}])
def test_invalid_value_is_hard_failure_even_while_unavailable(available, value):
    with pytest.raises(PayloadValidationError):
        build(available=available, confidence=0.5 if available else None, value=value)


@pytest.mark.parametrize(
    "evidence,code",
    [
        (None, PayloadErrorCode.MAPPING),
        ([], PayloadErrorCode.MAPPING),
        ({"raw": object()}, PayloadErrorCode.TYPE),
        ({"large": 2**53}, PayloadErrorCode.INTEGER),
        ({"n": math.nan}, PayloadErrorCode.NONFINITE),
        ({"s": "\ud800"}, PayloadErrorCode.UNICODE),
        ({"a": {"b": []}}, PayloadErrorCode.DEPTH),
        ({"s": "x" * 8192}, PayloadErrorCode.SIZE),
    ],
)
def test_evidence_violation_keeps_fact_and_returns_bounded_diagnostic(evidence, code):
    result = build(evidence=evidence)
    assert result.fact.value == "on"
    assert result.fact.how.evidence == {}
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].code is code
    assert {f.name for f in fields(result.diagnostics[0])} == {"code"}
    assert result.fact.how.source.correlation_id == "origin"


def test_missing_evidence_is_clean_while_explicit_none_is_diagnosed():
    assert build().diagnostics == ()
    assert build(evidence={}).diagnostics == ()
    assert build(evidence=None).diagnostics[0].code is PayloadErrorCode.MAPPING


@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_value_8kib_inclusive_limit(extra):
    if extra <= 0:
        fact = build(value="x" * (8192 - 2 + extra)).fact
        assert len(json.loads(house_fact_canonical_bytes(fact))["value"]) == 8192 - 2 + extra
    else:
        with pytest.raises(PayloadValidationError):
            build(value="x" * (8192 - 2 + extra))


@pytest.mark.parametrize("extra", [-1, 0, 1])
def test_evidence_8kib_inclusive_limit(extra):
    evidence = {"x": "a" * (8192 - 8 + extra)}
    result = build(evidence=evidence)
    if extra <= 0:
        assert result.fact.how.evidence == evidence
        assert result.diagnostics == ()
    else:
        assert result.fact.how.evidence == {}
        assert result.diagnostics[0].code is PayloadErrorCode.SIZE


def test_input_graph_is_detached_and_both_payloads_are_deeply_immutable():
    value, evidence = {"levels": [1, 2]}, {"route": ["a", "b"]}
    source = FactSource("sensor", "s", correlation_id="cycle")
    where = Location("rooms", room_ids=frozenset({"😀", "\ue000"}))
    fact = build(value=value, evidence=evidence, source=source, where=where).fact
    assert fact.how.source is not source
    assert fact.where is not where
    value["levels"].append(3)
    evidence["route"].clear()
    assert fact.value["levels"] == (1, 2)
    assert fact.how.evidence["route"] == ("a", "b")
    with pytest.raises(TypeError):
        fact.value["other"] = 1
    with pytest.raises(TypeError):
        fact.how.evidence["other"] = 1
    with pytest.raises(FrozenInstanceError):
        fact.value = "changed"
    with pytest.raises(FrozenInstanceError):
        fact.how.available = False
    assert json.loads(house_fact_canonical_bytes(fact))["where"]["room_ids"] == ["\ue000", "😀"]


@dataclass(frozen=True)
class NamedValue:
    states: list[str]


def test_frozen_dataclass_value_retains_type_with_detached_frozen_fields():
    value = NamedValue(["a", "b"])
    fact = build(value=value).fact
    value.states.append("c")
    assert type(fact.value) is NamedValue
    assert fact.value.states == ("a", "b")
    assert json.loads(house_fact_canonical_bytes(fact))["value"] == {"states": ["a", "b"]}


@pytest.mark.parametrize("fact_type", ["", ".x", "x.", "x..y", "x.*", "*"])
def test_invalid_concrete_fact_names_reject(fact_type):
    with pytest.raises(ValueError):
        build(fact_type=fact_type)


@pytest.mark.parametrize("fact_type", ["presence", "activity.reading", " A .e\u0301", "é", "a\0b"])
def test_fact_names_keep_exact_unicode_identity(fact_type):
    assert build(fact_type=fact_type).fact.fact_type == fact_type


@pytest.mark.parametrize("fact_type", [None, 1, True])
def test_fact_names_are_primitive_strings(fact_type):
    with pytest.raises(TypeError):
        build(fact_type=fact_type)


@pytest.mark.parametrize(
    "when",
    [
        "2026-01-01T00:00:00Z",
        "2026-01-01T00:00:00.000000+01:00",
        "2026-02-30T00:00:00.000000+00:00",
    ],
)
def test_fact_instant_uses_shared_validator_without_normalization(when):
    with pytest.raises(ValueError):
        build(when=when)


@pytest.mark.parametrize("where", [None, "kitchen", {"scope": "room"}])
def test_location_is_mandatory_and_typed(where):
    with pytest.raises(TypeError):
        build(where=where)


@pytest.mark.parametrize(
    "source", [None, {}, ApplyStepSource("reaction", "r", correlation_id="origin")]
)
def test_fact_source_must_be_concrete_fact_side_source(source):
    with pytest.raises(TypeError):
        build(source=source)


@pytest.mark.parametrize("field", ["kind", "actor_type"])
def test_test_sources_require_explicit_isolated_mode(field):
    source = FactSource("reaction", "r", correlation_id="origin")
    source = replace(source, **{field: "test"})
    with pytest.raises(ValueError):
        build(source=source)
    assert build(source=source, test_mode=True).fact.how.source == source


@pytest.mark.parametrize("test_mode", [False, True])
def test_builder_never_produces_legacy_facts(test_mode):
    with pytest.raises(ValueError):
        build(source=FactSource("legacy", "archive", correlation_id="origin"), test_mode=test_mode)


def test_builder_propagates_causal_id_without_using_uuid_safety_net(monkeypatch):
    source = FactSource("reaction", "r", correlation_id="causal-origin")

    def forbidden():
        pytest.fail("builder must not mint a causal ID")

    monkeypatch.setattr(fact_sources, "uuid4", forbidden)
    assert build(source=source).fact.how.source.correlation_id == "causal-origin"


@pytest.mark.parametrize(
    "where,expected",
    [
        (Location("casa"), {"scope": "casa", "room_id": None, "zone_id": None, "room_ids": None}),
        (
            Location("room", room_id="r"),
            {"scope": "room", "room_id": "r", "zone_id": None, "room_ids": None},
        ),
        (
            Location("zone", zone_id="z"),
            {"scope": "zone", "room_id": None, "zone_id": "z", "room_ids": None},
        ),
        (
            Location("rooms", room_ids=frozenset({"a", "b"})),
            {"scope": "rooms", "room_id": None, "zone_id": None, "room_ids": ["a", "b"]},
        ),
    ],
)
def test_every_location_form_encodes_as_the_declared_where_shape(where, expected):
    fact = build(where=where).fact
    assert fact.where == where
    assert json.loads(house_fact_canonical_bytes(fact))["where"] == expected


@pytest.mark.parametrize(
    "field,value",
    [
        ("fact_type", "\ud800"),
        ("where", Location("room", room_id="\ud800")),
        ("source", FactSource("sensor", "\ud800", correlation_id="origin")),
    ],
)
def test_unencodable_essential_metadata_is_not_a_constructed_fact(field, value):
    with pytest.raises(ValueError):
        build(**{field: value})


@pytest.mark.parametrize(
    "left,right,equal",
    [
        (1, 1.0, True),
        (-0.0, 0, True),
        (True, 1, False),
        (False, 0, False),
        ({"a": 1, "b": 2}, {"b": 2, "a": 1}, True),
    ],
)
def test_fact_and_provenance_equality_use_canonical_semantics(left, right, equal):
    first, second = build(value=left).fact, build(value=right).fact
    assert (first == second) is equal
    assert hash(first) == hash(house_fact_canonical_bytes(first))
    if equal:
        assert hash(first) == hash(second)
    first_how = build(evidence={"n": left}).fact.how
    second_how = build(evidence={"n": right}).fact.how
    assert (first_how == second_how) is equal
    assert hash(first_how) == hash(canonical_json_bytes(first_how))
    if equal:
        assert hash(first_how) == hash(second_how)


def test_whole_record_equality_keeps_time_and_evidence():
    first = build().fact
    assert first != build(when="2026-01-01T00:00:00.000001+00:00").fact
    assert first != build(evidence={"changed": True}).fact
    assert first.__eq__(object()) is NotImplemented
    assert first.how.__eq__(object()) is NotImplemented


@pytest.mark.parametrize("cls", [HouseFact, Provenance])
def test_records_cannot_bypass_the_single_builder(cls):
    with pytest.raises(TypeError):
        cls()
    with pytest.raises(TypeError):
        replace(build().fact if cls is HouseFact else build().fact.how)


def test_records_and_result_are_slotted_and_result_is_frozen():
    result = build()
    for record in [result, result.fact, result.fact.how]:
        assert not hasattr(record, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.diagnostics = ()


@pytest.mark.parametrize("value", [None, {}, build().fact.how])
def test_fact_encoder_requires_concrete_fact(value):
    with pytest.raises(TypeError):
        house_fact_canonical_bytes(value)


@given(
    st.lists(st.integers(-(2**53 - 1), 2**53 - 1), max_size=12),
    st.dictionaries(st.text(alphabet="abc", max_size=8), st.booleans(), max_size=8),
)
def test_property_mutating_inputs_does_not_change_fact_bytes_or_hash(values, evidence):
    original_values, original_evidence = list(values), dict(evidence)
    fact = build(value=values, evidence=evidence).fact
    encoded, hashed = house_fact_canonical_bytes(fact), hash(fact)
    values.append(42)
    evidence["new"] = True
    assert json.loads(encoded)["value"] == original_values
    assert dict(fact.how.evidence) == original_evidence
    assert house_fact_canonical_bytes(fact) == encoded
    assert hash(fact) == hashed


@given(
    st.floats(min_value=0, max_value=1, allow_nan=False, allow_infinity=False),
    st.integers(-(2**53 - 1), 2**53 - 1),
)
def test_property_bad_evidence_preserves_all_essential_content(confidence, value):
    clean = build(confidence=confidence, value=value)
    degraded = build(confidence=confidence, value=value, evidence={"invalid": object()})
    assert degraded.fact == clean.fact
    assert degraded.diagnostics[0].code is PayloadErrorCode.TYPE
    assert degraded.fact.how.confidence == confidence


def test_all_source_fields_are_copied_without_swapping_or_dropping_metadata():
    source = FactSource(
        "analyzer", "fusion", "family", "configuration", "route", "scheduler", "origin"
    )
    owned = build(source=source).fact.how.source
    assert owned == source
    assert owned is not source


def test_builder_owns_location_fields_without_dispatching_subclass_hooks():
    class FalseKey(Location):
        @property
        def key(self):
            return ("casa",)

    result = build(where=FalseKey("zone", zone_id="night"))
    assert type(result.fact.where) is Location
    assert result.fact.where.key == ("zone", "night")


def test_source_mode_flag_is_validated_as_boolean():
    with pytest.raises(TypeError):
        build(test_mode=1)
