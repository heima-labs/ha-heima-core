"""Exact composed-generation history records, L0 §4.7 and canonical time."""

import json
from dataclasses import FrozenInstanceError, fields, replace
from enum import StrEnum

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes
from custom_components.heima.v3.contracts.generations import (
    ComposedGenerationManifest,
    LayerGenerationRef,
)
from custom_components.heima.v3.contracts.instants import EvidenceInstant

LAYERS = ("layer2", "layer3", "layer4", "layer5", "layer6")
REFS = tuple(LayerGenerationRef(layer, layer + "-id", layer + "-fp") for layer in LAYERS)
WHEN = EvidenceInstant("2026-10-15T12:00:00.000000+00:00")


def manifest(**overrides):
    args = dict(
        composed_generation_id="composed-1",
        previous_composed_generation_id=None,
        layers=REFS,
        impact_fingerprint="impact-fp",
        invalidated_dependents=(),
        actor_ref="system",
        effective_at=WHEN,
    )
    args.update(overrides)
    return ComposedGenerationManifest(**args)


def test_exact_history_envelopes_and_canonical_layer_order():
    record = manifest()
    assert [f.name for f in fields(record)] == [
        "composed_generation_id",
        "previous_composed_generation_id",
        "layers",
        "impact_fingerprint",
        "invalidated_dependents",
        "actor_ref",
        "effective_at",
    ]
    assert [f.name for f in fields(REFS[0])] == ["layer", "generation_id", "definition_fingerprint"]
    encoded = json.loads(canonical_json_bytes(record))
    assert encoded == dict(
        composed_generation_id="composed-1",
        previous_composed_generation_id=None,
        layers=[
            dict(layer=layer, generation_id=layer + "-id", definition_fingerprint=layer + "-fp")
            for layer in LAYERS
        ],
        impact_fingerprint="impact-fp",
        invalidated_dependents=[],
        actor_ref="system",
        effective_at=WHEN,
    )
    assert [r.layer for r in record.layers] == list(LAYERS)


@pytest.mark.parametrize("index", range(5))
def test_each_required_layer_cannot_be_missing_or_duplicated(index):
    for refs in (REFS[:index] + REFS[index + 1 :], REFS[:index] + (REFS[index],) + REFS[index:]):
        with pytest.raises(ValueError):
            manifest(layers=refs)


@pytest.mark.parametrize("index", range(4))
def test_each_adjacent_layer_swap_rejects_instead_of_sorting(index):
    refs = list(REFS)
    refs[index], refs[index + 1] = refs[index + 1], refs[index]
    with pytest.raises(ValueError):
        manifest(layers=tuple(refs))


@pytest.mark.parametrize("refs", [(), REFS + (REFS[0],), (REFS[0],) * 5])
def test_layer_count_and_unique_layer_boundaries(refs):
    with pytest.raises(ValueError):
        manifest(layers=refs)


@pytest.mark.parametrize("refs", [list(REFS), None, tuple([None] * 5)])
def test_layer_snapshot_requires_tuple_of_concrete_references(refs):
    with pytest.raises(TypeError):
        manifest(layers=refs)


@pytest.mark.parametrize("layer", ["layer0", "layer1", "layer7", "layer8", "Layer2", ""])
def test_closed_configuration_layer_vocabulary(layer):
    with pytest.raises(ValueError):
        LayerGenerationRef(layer, "id", "fp")


class Text(StrEnum):
    VALUE = "layer2"


@pytest.mark.parametrize("field", ["layer", "generation_id", "definition_fingerprint"])
@pytest.mark.parametrize("invalid", [None, 1, True, Text.VALUE, "\ud800"])
def test_reference_metadata_rejects_bad_primitive_or_unencodable_text(field, invalid):
    args = dict(layer="layer2", generation_id="id", definition_fingerprint="fp")
    args[field] = invalid
    with pytest.raises((TypeError, ValueError)):
        LayerGenerationRef(**args)


@pytest.mark.parametrize("field", ["composed_generation_id", "impact_fingerprint", "actor_ref"])
@pytest.mark.parametrize("invalid", [None, 1, True, Text.VALUE, "\ud800"])
def test_manifest_essential_text_fields_reject(field, invalid):
    with pytest.raises((TypeError, ValueError)):
        manifest(**{field: invalid})


@pytest.mark.parametrize("previous", [1, True, Text.VALUE, "\ud800"])
def test_previous_id_is_optional_primitive_text(previous):
    with pytest.raises((TypeError, ValueError)):
        manifest(previous_composed_generation_id=previous)


def test_previous_id_none_and_present_remain_distinct():
    a = manifest()
    b = manifest(previous_composed_generation_id="previous")
    assert a.previous_composed_generation_id is None
    assert b.previous_composed_generation_id == "previous"
    assert a != b


@pytest.mark.parametrize("dependents", [[], None, (1,), (None,), ("\ud800",)])
def test_dependent_snapshot_is_an_immutable_text_tuple(dependents):
    with pytest.raises((TypeError, ValueError)):
        manifest(invalidated_dependents=dependents)


@pytest.mark.parametrize(
    "when",
    [
        "2026-10-15T12:00:00Z",
        "2026-10-15T12:00:00.000000+01:00",
        "2026-02-30T12:00:00.000000+00:00",
        None,
    ],
)
def test_effective_at_must_be_one_canonical_instant(when):
    with pytest.raises((TypeError, ValueError)):
        manifest(effective_at=when)


@pytest.mark.parametrize(
    "when", ["0001-01-01T00:00:00.000000+00:00", "9999-12-31T23:59:59.999999+00:00"]
)
def test_effective_at_calendar_boundaries(when):
    assert manifest(effective_at=when).effective_at == when


def test_records_are_frozen_slotted_hashable_and_replace_revalidates():
    record = manifest(invalidated_dependents=("layer5:r",))
    for item, field in ((record, "actor_ref"), (REFS[0], "generation_id")):
        assert not hasattr(item, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(item, field, "changed")
    assert hash(record) == hash(manifest(invalidated_dependents=("layer5:r",)))
    assert hash(REFS[0]) == hash(LayerGenerationRef("layer2", "layer2-id", "layer2-fp"))
    with pytest.raises(ValueError):
        replace(record, layers=REFS[:-1])
    with pytest.raises(ValueError):
        replace(REFS[0], layer="layer7")


def test_reference_subclasses_cannot_extend_persisted_manifest_schema():
    class Extra(LayerGenerationRef):
        pass

    refs = (Extra("layer2", "id", "fp"),) + REFS[1:]
    with pytest.raises(TypeError):
        manifest(layers=refs)


@pytest.mark.parametrize(
    "field,value", [("layer", "layer7"), ("generation_id", 1), ("definition_fingerprint", "\ud800")]
)
def test_tampered_reference_is_revalidated_at_manifest_boundary(field, value):
    ref = LayerGenerationRef("layer2", "id", "fp")
    object.__setattr__(ref, field, value)
    with pytest.raises((TypeError, ValueError)):
        manifest(layers=(ref,) + REFS[1:])


@given(st.permutations(REFS))
def test_only_canonical_reference_permutation_is_admitted(refs):
    refs = tuple(refs)
    if refs == REFS:
        assert manifest(layers=refs).layers == REFS
    else:
        with pytest.raises(ValueError):
            manifest(layers=refs)


@given(st.text(), st.text(), st.text(), st.lists(st.text(), max_size=5))
def test_opaque_metadata_survives_serialization_without_normalization(
    identifier, fingerprint, actor, ids
):
    refs = tuple(LayerGenerationRef(layer, identifier, fingerprint) for layer in LAYERS)
    record = manifest(
        composed_generation_id=identifier,
        previous_composed_generation_id="base:" + identifier,
        layers=refs,
        impact_fingerprint=fingerprint,
        actor_ref=actor,
        invalidated_dependents=tuple(ids),
    )
    before = canonical_json_bytes(record)
    ids.append("new")
    decoded = json.loads(before)
    assert decoded["composed_generation_id"] == identifier
    assert decoded["previous_composed_generation_id"] == "base:" + identifier
    assert decoded["impact_fingerprint"] == fingerprint
    assert decoded["actor_ref"] == actor
    assert decoded["invalidated_dependents"] == ids[:-1]
    assert canonical_json_bytes(record) == before
