"""Contract decisions/boundaries and properties, independent of implementation."""

from dataclasses import FrozenInstanceError, dataclass, field
from decimal import Decimal
from enum import IntEnum, StrEnum
from fractions import Fraction
from types import MappingProxyType

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes
from custom_components.heima.v3.contracts.payloads import (
    MAX_COLLECTION_DEPTH,
    MAX_PAYLOAD_BYTES,
    MAX_SAFE_INTEGER,
    PayloadErrorCode,
    PayloadValidationError,
    freeze_house_fact_value,
    freeze_persisted_projection,
    prepare_evidence,
    validate_house_fact_value,
)


@dataclass(frozen=True)
class Record:
    data: object


@dataclass(frozen=True, slots=True)
class SlottedRecord:
    data: object


@dataclass
class MutableRecord:
    data: object


class Label(StrEnum):
    A = "a"


class Count(IntEnum):
    ONE = 1


# D01-D11: scalar contract, boundaries and type distinction.
@pytest.mark.parametrize(
    "value, expected",
    [
        (None, b"null"),
        (False, b"false"),
        (True, b"true"),
        (0, b"0"),
        (1, b"1"),
        (1.0, b"1"),
        (-0.0, b"0"),
        (9007199254740990, b"9007199254740990"),
        (9007199254740991, b"9007199254740991"),
        (-9007199254740990, b"-9007199254740990"),
        (-9007199254740991, b"-9007199254740991"),
        (5e-324, b"5e-324"),
        (1.7976931348623157e308, b"1.7976931348623157e+308"),
        ("1.5", b'"1.5"'),
    ],
)
def test_scalar_decisions(value, expected):
    result = freeze_house_fact_value(value)
    assert result.canonical_bytes == expected
    assert type(result.value) is type(value)
    assert canonical_json_bytes(result.value) == expected
    assert validate_house_fact_value(value) is None


@pytest.mark.parametrize(
    "value, code",
    [
        (9007199254740992, PayloadErrorCode.INTEGER),
        (-9007199254740992, PayloadErrorCode.INTEGER),
        (float("nan"), PayloadErrorCode.NONFINITE),
        (float("inf"), PayloadErrorCode.NONFINITE),
        (float("-inf"), PayloadErrorCode.NONFINITE),
        (Decimal("1.5"), PayloadErrorCode.TYPE),
        (Fraction(1, 2), PayloadErrorCode.TYPE),
        (complex(1, 2), PayloadErrorCode.TYPE),
        (b"a", PayloadErrorCode.TYPE),
        (object(), PayloadErrorCode.TYPE),
        (Label.A, PayloadErrorCode.TYPE),
        (Count.ONE, PayloadErrorCode.TYPE),
        (set(), PayloadErrorCode.TYPE),
        ((1, 2), PayloadErrorCode.TYPE),
        (MutableRecord(1), PayloadErrorCode.TYPE),
        (Record, PayloadErrorCode.TYPE),
        ("\ud800", PayloadErrorCode.UNICODE),
        ({1: "a"}, PayloadErrorCode.TYPE),
        ({Label.A: 1}, PayloadErrorCode.TYPE),
        ({"\udfff": 1}, PayloadErrorCode.UNICODE),
        ({"a": {"b": []}}, PayloadErrorCode.DEPTH),
        ([[[]]], PayloadErrorCode.DEPTH),
    ],
)
def test_invalid_value_and_evidence(value, code):
    with pytest.raises(PayloadValidationError) as caught:
        freeze_house_fact_value(value)
    assert caught.value.code == code
    assert str(caught.value) == code.value
    with pytest.raises(PayloadValidationError):
        validate_house_fact_value(value)
    # Evidence adds the root mapping; scalar violations still keep the same code.
    evidence = prepare_evidence({"detail": value})
    assert evidence.payload.canonical_bytes == b"{}"
    assert len(evidence.diagnostics) == 1
    assert evidence.diagnostics[0].code == code


@pytest.mark.parametrize("value", [[], {}, {"a": []}, [[1]], {"a": {"b": 1}}])
def test_allowed_depth(value):
    result = freeze_house_fact_value(value)
    assert canonical_json_bytes(result.value) == result.canonical_bytes


@pytest.mark.parametrize("delta", [-1, 0, 1])
def test_ascii_size_boundary(delta):
    value = "a" * (8192 - 2 + delta)  # UTF-8 JSON quotes count too.
    if delta > 0:
        with pytest.raises(PayloadValidationError) as caught:
            freeze_house_fact_value(value)
        assert caught.value.code == PayloadErrorCode.SIZE
    else:
        assert len(freeze_house_fact_value(value).canonical_bytes) == 8192 + delta


def test_utf8_and_escaping_count_in_size():
    assert len(freeze_house_fact_value("é" * 4095).canonical_bytes) == 8192
    for value in ["é" * 4096, "\n" * 4096, "\x00" * 1366]:
        with pytest.raises(PayloadValidationError, match="payload_too_large"):
            freeze_house_fact_value(value)
    assert len(freeze_house_fact_value("\n" * 4095).canonical_bytes) == 8192


def test_collection_size_and_evidence_failure():
    assert len(freeze_persisted_projection({"a": "x" * 8184}).canonical_bytes) == 8192
    result = prepare_evidence({"a": "x" * 8185})
    assert result.payload.value == {}
    assert result.diagnostics[0].code == PayloadErrorCode.SIZE
    assert len(result.diagnostics) == 1


def test_nested_immutability_and_detachment():
    source = {"a": [True, False], "b": {"number": 4}}
    result = freeze_house_fact_value(source)
    source["a"].append(None)
    source["b"]["number"] = 9
    assert result.canonical_bytes == b'{"a":[true,false],"b":{"number":4}}'
    assert canonical_json_bytes(result.value) == result.canonical_bytes
    assert isinstance(result.value, MappingProxyType)
    assert result.value["a"] == (True, False)
    with pytest.raises(TypeError):
        result.value["new"] = 1
    with pytest.raises(TypeError):
        result.value["b"]["number"] = 10
    with pytest.raises(FrozenInstanceError):
        result.value = None


@pytest.mark.parametrize("record_type", [Record, SlottedRecord])
def test_record_type_fields_frozen_and_original_untouched(record_type):
    original = {"a": 1}
    value = record_type(original)
    result = freeze_house_fact_value(value)
    assert type(result.value) is record_type
    assert result.value is not value
    assert value.data is original
    original["a"] = 2
    assert canonical_json_bytes(result.value) == b'{"data":{"a":1}}'
    with pytest.raises(TypeError):
        result.value.data["a"] = 3
    with pytest.raises(FrozenInstanceError):
        result.value.data = None


def test_record_tuple_and_depth():
    assert freeze_house_fact_value(Record((1, "a"))).canonical_bytes == b'{"data":[1,"a"]}'
    assert freeze_house_fact_value(Record(Record(1))).canonical_bytes == b'{"data":{"data":1}}'
    for value in [
        Record({"a": []}),
        Record(([1],)),
        Record(Record([])),
        Record({"a": (1,)}),
        Record({"a": Record(1)}),
        Record(((1,),)),
        Record((Record(1),)),
    ]:
        with pytest.raises(PayloadValidationError, match="collection_too_deep"):
            freeze_house_fact_value(value)
    # A record object is not EvidenceValue inside an ordinary mapping/list.
    with pytest.raises(PayloadValidationError, match="invalid_type"):
        freeze_house_fact_value({"a": Record(1)})
    with pytest.raises(PayloadValidationError, match="invalid_type"):
        freeze_house_fact_value([Record(1)])


def test_record_copy_does_not_reexecute_callbacks_or_keep_hidden_attributes():
    calls = []

    @dataclass(frozen=True)
    class WithCallback:
        data: object
        derived: int = field(init=False)

        def __post_init__(self):
            calls.append("called")
            object.__setattr__(self, "derived", 7)
            object.__setattr__(self, "hidden", [])

    original = WithCallback([1])
    result = freeze_house_fact_value(original)
    assert calls == ["called"]
    assert result.value.derived == 7
    assert not hasattr(result.value, "hidden")
    assert result.canonical_bytes == b'{"data":[1],"derived":7}'


@pytest.mark.parametrize("value", [None, 1, [], Record(1), MappingProxyType({})])
def test_projection_is_a_mapping_without_record_exception(value):
    with pytest.raises(PayloadValidationError, match="mapping_required"):
        freeze_persisted_projection(value)
    result = prepare_evidence(value)
    assert result.payload.canonical_bytes == b"{}"
    assert result.diagnostics[0].code == PayloadErrorCode.MAPPING


def test_valid_evidence_has_no_diagnostic():
    source = {"sensor": "configured-reading", "votes": [1, 2]}
    result = prepare_evidence(source)
    assert result.diagnostics == ()
    source.clear()
    assert result.payload.canonical_bytes == b'{"sensor":"configured-reading","votes":[1,2]}'


def test_equality_and_local_hash_use_canonical_content():
    for left, right in [(1, 1.0), (0.0, -0.0), ({"a": 1, "b": 2}, {"b": 2, "a": 1})]:
        a, b = freeze_house_fact_value(left), freeze_house_fact_value(right)
        assert a == b
        assert hash(a) == hash(b)
        assert hash(a) == hash(a.canonical_bytes)
    assert freeze_house_fact_value(True) != freeze_house_fact_value(1)
    assert freeze_house_fact_value([1, 2]) != freeze_house_fact_value([2, 1])
    assert freeze_house_fact_value(1) != 1
    assert (
        len(
            {
                freeze_house_fact_value(1),
                freeze_house_fact_value(1.0),
                freeze_house_fact_value(True),
            }
        )
        == 2
    )


# Properties use relations and reference bytes, never the production algorithm as oracle.
safe_scalar = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(-(2**53 - 1), 2**53 - 1),
    st.floats(allow_nan=False, allow_infinity=False, width=64),
    st.text(max_size=20),
)


@settings(max_examples=50)
@given(st.dictionaries(st.text(max_size=8), safe_scalar, max_size=8))
def test_property_mapping_permutation_and_detachment(value):
    expected = freeze_house_fact_value(value)
    reversed_result = freeze_house_fact_value(dict(reversed(list(value.items()))))
    assert expected == reversed_result
    assert hash(expected) == hash(reversed_result)
    value.clear()
    assert canonical_json_bytes(expected.value) == expected.canonical_bytes


@settings(max_examples=50)
@given(st.lists(safe_scalar, max_size=8))
def test_property_array_order_is_preserved(value):
    frozen = freeze_house_fact_value(value)
    assert isinstance(frozen.value, tuple)
    assert len(frozen.value) == len(value)
    assert frozen.canonical_bytes == canonical_json_bytes(value)
    value.clear()
    assert canonical_json_bytes(frozen.value) == frozen.canonical_bytes


@settings(max_examples=30)
@given(st.integers(min_value=1, max_value=10**20), st.booleans())
def test_property_outside_safe_domain_never_coerced(offset, negative):
    value = (2**53 - 1 + offset) * (-1 if negative else 1)
    with pytest.raises(PayloadValidationError, match="integer_out_of_range"):
        freeze_house_fact_value(value)
    assert prepare_evidence({"a": value}).payload.canonical_bytes == b"{}"


def test_contract_constants():
    assert MAX_SAFE_INTEGER == 9007199254740991
    assert MAX_COLLECTION_DEPTH == 2
    assert MAX_PAYLOAD_BYTES == 8192


# MC/DC: hold the other atomic conditions fixed at the pure traversal boundary.
# Public entry-point cases above verify the same context policies end to end.
@pytest.mark.parametrize(
    "value, record_context, allow_record, accepted",
    [
        (None, False, False, True),
        (True, False, False, True),
        (object(), False, False, False),
        ([1], False, False, True),
        ((1,), False, False, False),
        ((1,), True, False, True),
        (object(), True, False, False),
        (Record(1), False, True, True),
        (Record(1), False, False, False),
        (object(), False, True, False),
        (Record, False, True, False),
    ],
)
def test_mcdc_traversal_context(value, record_context, allow_record, accepted):
    from custom_components.heima.v3.contracts.payloads import _freeze

    if accepted:
        assert canonical_json_bytes(
            _freeze(value, 0, record_context=record_context, allow_record=allow_record)
        ) == canonical_json_bytes(value)
    else:
        with pytest.raises(PayloadValidationError):
            _freeze(value, 0, record_context=record_context, allow_record=allow_record)


def test_record_and_mapping_have_equal_canonical_payload():
    record = freeze_house_fact_value(Record(1))
    mapping = freeze_house_fact_value({"data": 1})
    assert record == mapping
    assert hash(record) == hash(mapping)


def test_diagnostic_and_evidence_result_immutable():
    result = prepare_evidence({"value": float("nan")})
    with pytest.raises(FrozenInstanceError):
        result.diagnostics = ()
    with pytest.raises(FrozenInstanceError):
        result.payload = None
    with pytest.raises(FrozenInstanceError):
        result.diagnostics[0].code = PayloadErrorCode.TYPE


def test_mutation_imports_resolve_to_active_source_tree():
    from pathlib import Path

    import custom_components.heima.v3.contracts.payloads as payloads

    root = Path.cwd().resolve()
    assert Path(payloads.__file__).resolve().is_relative_to(root / "custom_components")
