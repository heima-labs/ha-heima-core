"""Location shape/identity, exact Unicode semantics and canonical recovery."""

import json
from dataclasses import FrozenInstanceError, fields
from enum import StrEnum
from itertools import permutations, product

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes
from custom_components.heima.v3.contracts.location import (
    Location,
    location_from_key,
    location_from_key_json,
    location_key_json,
)
from custom_components.heima.v3.contracts.payloads import freeze_persisted_projection


@pytest.mark.parametrize("scope", ["casa", "room", "zone", "rooms"])
@pytest.mark.parametrize("populated", list(product([False, True], repeat=3)))
def test_scope_and_optional_fields_exhaustive_decision_table(scope, populated):
    kwargs = dict(
        zip(
            ("room_id", "zone_id", "room_ids"),
            (
                "r" if populated[0] else None,
                "z" if populated[1] else None,
                frozenset({"a", "b"}) if populated[2] else None,
            ),
            strict=True,
        )
    )
    expected = {
        "casa": (False, False, False),
        "room": (True, False, False),
        "zone": (False, True, False),
        "rooms": (False, False, True),
    }[scope]
    if populated == expected:
        result = Location(scope, **kwargs)
        assert result.scope == scope
    else:
        with pytest.raises(ValueError):
            Location(scope, **kwargs)


@pytest.mark.parametrize(
    "ids,valid",
    [
        (frozenset(), False),
        (frozenset({"a"}), False),
        (frozenset({"a", "b"}), True),
        (frozenset({"a", "b", "c"}), True),
    ],
)
def test_multiple_room_cardinality_boundary(ids, valid):
    if valid:
        assert Location("rooms", room_ids=ids).key == ("rooms", *sorted(ids))
    else:
        with pytest.raises(ValueError):
            Location("rooms", room_ids=ids)


@pytest.mark.parametrize("ids", [["a", "b"], {"a", "b"}, ("a", "b"), "ab", 2, True])
def test_room_set_shape_is_not_silently_converted(ids):
    with pytest.raises(TypeError):
        Location("rooms", room_ids=ids)


@pytest.mark.parametrize("scope", ["room", "zone", "rooms"])
@pytest.mark.parametrize(
    "value,error", [("", ValueError), (False, TypeError), (1, TypeError), (b"a", TypeError)]
)
def test_nonempty_string_identifiers_in_each_form(scope, value, error):
    kwargs = (
        {"room_id": value}
        if scope == "room"
        else {"zone_id": value}
        if scope == "zone"
        else {"room_ids": frozenset({value, "a"})}
    )
    with pytest.raises(error):
        Location(scope, **kwargs)


@pytest.mark.parametrize(
    "scope,error",
    [
        ("", ValueError),
        ("house", ValueError),
        ("ROOM", ValueError),
        (None, TypeError),
        (False, TypeError),
        (1, TypeError),
    ],
)
def test_scope_is_closed_and_not_coerced(scope, error):
    with pytest.raises(error):
        Location(scope)


class ScopeEnum(StrEnum):
    ROOM = "room"


def test_enum_objects_are_not_primitive_scope_or_identifier_strings():
    with pytest.raises(TypeError):
        Location(ScopeEnum.ROOM, room_id="r")
    with pytest.raises(TypeError):
        Location("room", room_id=ScopeEnum.ROOM)


@pytest.mark.parametrize(
    "location,key,text",
    [
        (Location("casa"), ("casa",), '["casa"]'),
        (Location("room", room_id="r"), ("room", "r"), '["room","r"]'),
        (Location("zone", zone_id="z"), ("zone", "z"), '["zone","z"]'),
        (
            Location("rooms", room_ids=frozenset({"b", "a"})),
            ("rooms", "a", "b"),
            '["rooms","a","b"]',
        ),
    ],
)
def test_four_canonical_keys_equality_hash_and_json(location, key, text):
    assert location.key == key
    assert hash(location) == hash(key)
    assert location_from_key(key) == location
    assert location_key_json(location) == text
    assert location_from_key_json(text) == location
    assert location_key_json(location_from_key_json(text)) == text


def test_rooms_array_uses_codepoint_order_and_object_keys_still_use_utf16():
    location = Location("rooms", room_ids=frozenset({"😀", "\ue000"}))
    assert location.key == ("rooms", "\ue000", "😀")
    assert location_key_json(location) == '["rooms","\ue000","😀"]'
    assert canonical_json_bytes({"\ue000": 1, "😀": 2}) == '{"😀":2,"\ue000":1}'.encode()


def test_opaque_ids_preserve_whitespace_case_normalization_and_nulls():
    ids = ["a", "A", " a ", "é", "e\u0301", "\0"]
    locations = {Location("room", room_id=identifier) for identifier in ids}
    assert len(locations) == len(ids)
    for identifier in ids:
        location = Location("room", room_id=identifier)
        assert location_from_key_json(location_key_json(location)).room_id == identifier
    assert Location("room", room_id="not-in-registry").room_id == "not-in-registry"
    assert Location("zone", zone_id="not-in-registry").zone_id == "not-in-registry"


def test_scope_is_part_of_identity_and_non_locations_are_not_equal():
    places = [
        Location("casa"),
        Location("room", room_id="a"),
        Location("zone", zone_id="a"),
        Location("rooms", room_ids=frozenset({"a", "b"})),
    ]
    assert len(set(places)) == 4
    assert all(left != right for left, right in permutations(places, 2))
    assert places[0] != ("casa",)
    assert places[0].__eq__(("casa",)) is NotImplemented
    assert places[0] != None  # noqa: E711


@pytest.mark.parametrize(
    "key",
    [
        (),
        ("other",),
        ("casa", "x"),
        ("room",),
        ("room", "a", "b"),
        ("zone",),
        ("zone", "a", "b"),
        ("rooms",),
        ("rooms", "a"),
        ("rooms", "b", "a"),
        ("rooms", "a", "a"),
        ("rooms", "a", "a", "b"),
        ("room", ""),
    ],
)
def test_key_recovery_rejects_noncanonical_shape_arity_order_and_duplicates(key):
    with pytest.raises(ValueError):
        location_from_key(key)


@pytest.mark.parametrize(
    "key", [["casa"], "casa", None, (False,), ("room", 1), ("rooms", "a", None)]
)
def test_key_recovery_rejects_non_string_or_non_tuple_shapes(key):
    with pytest.raises(TypeError):
        location_from_key(key)


@pytest.mark.parametrize(
    "text",
    [
        ' ["casa"]',
        '["casa"]\n',
        '["room", "r"]',
        '["room","\\u0072"]',
        '["room","a\\/b"]',
        '["rooms","b","a"]',
        '["rooms","a","a","b"]',
        '["other"]',
        '["casa",]',
    ],
)
def test_key_text_decoder_rejects_noncanonical_or_invalid_text(text):
    with pytest.raises(ValueError):
        location_from_key_json(text)


@pytest.mark.parametrize(
    "text",
    [
        None,
        b'["casa"]',
        "null",
        '"casa"',
        "{}",
        '{"scope":"casa","scope":"room"}',
        "[null]",
        "[true]",
        "[1]",
        '[["casa"]]',
    ],
)
def test_key_text_decoder_does_not_accept_other_json_shapes(text):
    with pytest.raises(TypeError):
        location_from_key_json(text)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("scope", "unknown", ValueError),
        ("room_id", "unexpected", ValueError),
        ("zone_id", "unexpected", ValueError),
        ("room_ids", frozenset({"a", "b"}), ValueError),
    ],
)
def test_forged_locations_are_revalidated_at_identity_and_encoding(field, value, error):
    forged = Location("casa")
    object.__setattr__(forged, field, value)
    with pytest.raises(error):
        _ = forged.key
    with pytest.raises(error):
        location_key_json(forged)
    with pytest.raises(error):
        hash(forged)


def test_key_encoder_requires_location_and_value_remains_immutable():
    with pytest.raises(TypeError):
        location_key_json(("casa",))
    value = Location("room", room_id="a")
    assert {field.name for field in fields(value)} == {"scope", "room_id", "zone_id", "room_ids"}
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.room_id = "b"


def test_mult_room_subject_text_fits_shallow_projection_without_nesting_rooms():
    location = Location("rooms", room_ids=frozenset({"a", "b"}))
    subject = location_key_json(location)
    prepared = freeze_persisted_projection({"subject": subject, "facets": {"state": "on"}})
    decoded = json.loads(prepared.canonical_bytes)
    assert location_from_key_json(decoded["subject"]) == location


identifiers = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=12)


@given(st.sets(identifiers, min_size=2, max_size=8), st.data())
def test_property_input_permutations_preserve_identity_hash_and_recovery(ids, data):
    sequence = sorted(ids)
    reordered = data.draw(st.permutations(sequence))
    first = Location("rooms", room_ids=frozenset(sequence))
    second = Location("rooms", room_ids=frozenset(reordered))
    assert first == second
    assert hash(first) == hash(second)
    assert first.key == ("rooms", *sequence)
    assert location_key_json(first) == location_key_json(second)
    assert location_from_key_json(location_key_json(first)) == first


@given(st.sampled_from(["room", "zone"]), identifiers, identifiers)
def test_property_opaque_identity_changes_exactly_when_id_changes(scope, left, right):
    first = Location(scope, **{f"{scope}_id": left})
    second = Location(scope, **{f"{scope}_id": right})
    assert (first == second) is (left == right)
    assert location_from_key(first.key) == first
    assert location_from_key_json(location_key_json(second)) == second


@pytest.mark.parametrize("operation", [lambda value: value.key, hash, location_key_json])
def test_invalid_location_subclass_cannot_skip_base_shape_validation(operation):
    class UncheckedLocation(Location):
        def __post_init__(self):
            pass

    invalid = UncheckedLocation("invalid")
    with pytest.raises(ValueError):
        operation(invalid)


def test_location_equality_rejects_invalid_subclass_shape():
    class UncheckedLocation(Location):
        def __post_init__(self):
            pass

    with pytest.raises(ValueError):
        _ = Location("casa") == UncheckedLocation("invalid")


def test_overridden_key_cannot_change_canonical_encoding_equality_or_hash():
    class FalseKey(Location):
        @property
        def key(self):
            return ("casa",)

    value = FalseKey("room", room_id="kitchen")
    assert location_key_json(value) == '["room","kitchen"]'
    assert value == Location("room", room_id="kitchen")
    assert value != Location("casa")
    assert hash(value) == hash(("room", "kitchen"))


@given(
    st.sampled_from(["casa", "room", "zone", "rooms"]),
    identifiers,
    st.lists(identifiers, max_size=4),
)
def test_property_subclass_key_override_cannot_change_owned_identity(scope, identifier, false_key):
    class FalseKey(Location):
        @property
        def key(self):
            return tuple(false_key)

    kwargs = {}
    if scope == "room":
        kwargs["room_id"] = identifier
    elif scope == "zone":
        kwargs["zone_id"] = identifier
    elif scope == "rooms":
        kwargs["room_ids"] = frozenset({identifier, identifier + "other"})
    original = Location(scope, **kwargs)
    derived = FalseKey(scope, **kwargs)
    assert original == derived
    assert hash(original) == hash(derived)
    assert location_key_json(original) == location_key_json(derived)
    assert location_from_key_json(location_key_json(derived)) == original
