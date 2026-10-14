"""JCS standard vectors and boundary behavior of the third-party codec adapter."""

from dataclasses import dataclass
from types import MappingProxyType

import pytest

from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes


@pytest.mark.parametrize(
    "value, expected",
    [
        # RFC 8785 §3.2.2 sample, reduced to its numeric array.
        (
            [333333333.33333329, 1e30, 4.50, 2e-3, 1e-27],
            b"[333333333.3333333,1e+30,4.5,0.002,1e-27]",
        ),
        ({"\ue000": 1, "😀": 2}, '{"😀":2,"\ue000":1}'.encode()),
        ({"b": {"z": 0, "a": 1}, "a": [2, 1]}, b'{"a":[2,1],"b":{"a":1,"z":0}}'),
        (MappingProxyType({"a": (1, True)}), b'{"a":[1,true]}'),
        ("é", '"é"'.encode()),
        ("e\u0301", '"e\u0301"'.encode()),
        ('"\\\n\x00', b'"\\"\\\\\\n\\u0000"'),
        (1e-6, b"0.000001"),
        (1e-7, b"1e-7"),
        (1e20, b"100000000000000000000"),
        (1e21, b"1e+21"),
        (0.0, b"0"),
        (-0.0, b"0"),
        (5e-324, b"5e-324"),
        (1424953923781206.25, b"1424953923781206.2"),
        ([], b"[]"),
        ({}, b"{}"),
        (None, b"null"),
        (False, b"false"),
    ],
)
def test_jcs_vectors(value, expected):
    assert canonical_json_bytes(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        2**53,
        -(2**53),
        {1: "a"},
        {"\ud800": 1},
        "\udfff",
        b"a",
        object(),
        int,
    ],
)
def test_rejected_codec_inputs(value):
    with pytest.raises(ValueError):
        canonical_json_bytes(value)


def test_cyclic_input_rejected_but_shared_children_valid():
    cycle = []
    cycle.append(cycle)
    with pytest.raises(ValueError, match="Cyclic"):
        canonical_json_bytes(cycle)
    shared = {"a": 1}
    assert canonical_json_bytes([shared, shared]) == b'[{"a":1},{"a":1}]'


def test_frozen_record_projection_and_mutable_record_rejection():
    @dataclass(frozen=True)
    class Frozen:
        value: object

    @dataclass
    class Mutable:
        value: object

    assert canonical_json_bytes(Frozen((1, 2))) == b'{"value":[1,2]}'
    with pytest.raises(ValueError, match="frozen"):
        canonical_json_bytes(Mutable(1))
    with pytest.raises(ValueError):
        canonical_json_bytes(Frozen)


def test_enum_objects_rejected_at_codec_boundary():
    from enum import IntEnum, StrEnum

    class Number(IntEnum):
        ONE = 1

    class Text(StrEnum):
        A = "a"

    for value in (Number.ONE, Text.A):
        with pytest.raises(ValueError, match="Enum"):
            canonical_json_bytes(value)
