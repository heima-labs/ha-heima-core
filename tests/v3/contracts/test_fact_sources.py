"""Closed source shapes, runtime data modes and stable source comparison."""

import json
from dataclasses import FrozenInstanceError, fields, replace
from enum import StrEnum
from itertools import product
from uuid import UUID

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts import fact_sources
from custom_components.heima.v3.contracts.canonical_json import canonical_json_bytes
from custom_components.heima.v3.contracts.fact_sources import (
    ApplyStepSource,
    FactSource,
    FactSourceFingerprint,
    fact_source_fingerprint,
    validate_runtime_source_shape,
)

FACT_KINDS = (
    "sensor",
    "analyzer",
    "third_party_plugin",
    "semantic_resolver",
    "reaction",
    "admin_command",
    "resident_response",
    "timeout",
    "recovery",
    "system",
    "test",
    "legacy",
)
ACTION_KINDS = (
    "reaction",
    "admin_command",
    "resident_response",
    "timeout",
    "recovery",
    "system",
    "test",
)
ACTORS = ("ha_admin", "resident", "heima", "scheduler", "service", "system", "test", "unknown")


def source(cls=FactSource, **changes):
    return cls(**{"kind": "reaction", "source_id": "r", "correlation_id": "origin", **changes})


@pytest.mark.parametrize("kind", FACT_KINDS)
def test_exact_fact_vocabulary(kind):
    assert source(kind=kind).kind == kind
    assert fact_source_fingerprint(source(kind=kind)).kind == kind


@pytest.mark.parametrize("kind", ACTION_KINDS)
def test_exact_action_vocabulary(kind):
    assert source(ApplyStepSource, kind=kind).kind == kind


@pytest.mark.parametrize(
    "kind", ["sensor", "analyzer", "third_party_plugin", "semantic_resolver", "legacy"]
)
def test_fact_only_and_archive_kinds_are_never_action_sources(kind):
    with pytest.raises(ValueError):
        source(ApplyStepSource, kind=kind)


@pytest.mark.parametrize("cls", [FactSource, ApplyStepSource])
@pytest.mark.parametrize("actor", ACTORS)
def test_exact_actor_vocabulary_without_person_identity(cls, actor):
    assert source(cls, actor_type=actor).actor_type == actor
    names = {field.name for field in fields(cls)}
    assert not names.intersection({"actor_ref", "user_id", "trusted", "token", "raw_payload"})


@pytest.mark.parametrize("cls", [FactSource, ApplyStepSource])
@pytest.mark.parametrize(
    "field,value,error",
    [
        ("kind", "administrator", ValueError),
        ("kind", "SENSOR", ValueError),
        ("kind", "", ValueError),
        ("kind", False, TypeError),
        ("actor_type", "administrator", ValueError),
        ("actor_type", "", ValueError),
        ("actor_type", None, TypeError),
        ("source_id", None, TypeError),
        ("source_id", 1, TypeError),
        ("source_type", True, TypeError),
        ("configuration_fingerprint", {}, TypeError),
        ("correlation_id", None, TypeError),
        ("correlation_id", b"id", TypeError),
    ],
)
def test_source_shape_rejects_wrong_fields_without_echoing_raw_data(cls, field, value, error):
    with pytest.raises(error):
        source(cls, **{field: value})


@pytest.mark.parametrize("field", ["source_type", "configuration_fingerprint"])
@pytest.mark.parametrize("value", [None, "", " a ", "e\u0301", "é"])
@pytest.mark.parametrize("cls", [FactSource, ApplyStepSource])
def test_optional_fields_are_opaque_and_not_normalized(cls, field, value):
    assert getattr(source(cls, **{field: value}), field) == value


@pytest.mark.parametrize("value", [None, "", "route", " e\u0301 "])
def test_fact_route_is_preserved_and_action_has_no_route_field(value):
    assert source(route_fingerprint=value).route_fingerprint == value
    with pytest.raises(TypeError):
        source(ApplyStepSource, route_fingerprint=value)


@pytest.mark.parametrize("value", [False, 1, [], object()])
def test_route_rejects_non_string_metadata(value):
    with pytest.raises(TypeError):
        source(route_fingerprint=value)


class SourceEnum(StrEnum):
    REACTION = "reaction"


@pytest.mark.parametrize(
    "field",
    [
        "kind",
        "actor_type",
        "source_id",
        "source_type",
        "configuration_fingerprint",
        "route_fingerprint",
        "correlation_id",
    ],
)
def test_enum_members_are_not_primitive_source_fields(field):
    with pytest.raises(TypeError):
        source(**{field: SourceEnum.REACTION})


@pytest.mark.parametrize("cls", [FactSource, ApplyStepSource, FactSourceFingerprint])
def test_declared_source_values_are_frozen_and_slotted(cls):
    value = fact_source_fingerprint(source()) if cls is FactSourceFingerprint else source(cls)
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        value.source_id = "changed"


@pytest.mark.parametrize("cls", [FactSource, ApplyStepSource])
def test_declared_defaults_and_uuid_safety_net(cls):
    first, second = cls("reaction", "r"), cls("reaction", "r")
    assert first.actor_type == "heima"
    assert first.source_type is None and first.configuration_fingerprint is None
    if cls is FactSource:
        assert first.route_fingerprint is None
    assert UUID(first.correlation_id).version == UUID(second.correlation_id).version == 4
    assert first.correlation_id != second.correlation_id


def test_explicit_causal_chain_does_not_mint_intermediate_ids(monkeypatch):
    def forbidden():
        pytest.fail("explicit source propagation must not mint another correlation")

    monkeypatch.setattr(fact_sources, "uuid4", forbidden)
    fact = source(correlation_id="opaque-origin")
    action = source(ApplyStepSource, correlation_id=fact.correlation_id)
    downstream = source(kind="semantic_resolver", correlation_id=fact.correlation_id)
    assert (
        fact.correlation_id == action.correlation_id == downstream.correlation_id == "opaque-origin"
    )
    assert fact_source_fingerprint(fact) == fact_source_fingerprint(
        replace(fact, correlation_id="different-origin")
    )


@pytest.mark.parametrize("cls", [FactSource, ApplyStepSource])
@pytest.mark.parametrize("test_kind,test_actor,test_mode", list(product([False, True], repeat=3)))
def test_runtime_shape_mode_decision_table(cls, test_kind, test_actor, test_mode):
    value = source(
        cls, kind="test" if test_kind else "reaction", actor_type="test" if test_actor else "heima"
    )
    if test_mode or not (test_kind or test_actor):
        assert validate_runtime_source_shape(value, test_mode=test_mode) is None
    else:
        with pytest.raises(ValueError):
            validate_runtime_source_shape(value, test_mode=test_mode)


@pytest.mark.parametrize("test_mode", [False, True])
def test_legacy_is_archive_only_even_in_test_mode(test_mode):
    value = source(kind="legacy")
    assert value.kind == "legacy"
    with pytest.raises(ValueError):
        validate_runtime_source_shape(value, test_mode=test_mode)


@pytest.mark.parametrize("test_mode", [0, 1, None, "test"])
def test_runtime_mode_is_not_truthiness_based(test_mode):
    with pytest.raises(TypeError):
        validate_runtime_source_shape(source(), test_mode=test_mode)


@pytest.mark.parametrize("value", [None, {}, "reaction", fact_source_fingerprint(source())])
def test_runtime_shape_requires_typed_source(value):
    with pytest.raises(TypeError):
        validate_runtime_source_shape(value)


def test_structurally_valid_admin_fields_are_data_without_an_authority_claim():
    value = source(kind="admin_command", actor_type="ha_admin")
    # The future HA boundary must assign these from verified inputs. This API only
    # checks shape and data mode; it does not return a principal, grant or capability.
    assert validate_runtime_source_shape(value) is None
    assert set(json.loads(canonical_json_bytes(value))) == {
        "kind",
        "source_id",
        "source_type",
        "configuration_fingerprint",
        "route_fingerprint",
        "actor_type",
        "correlation_id",
    }
    assert not hasattr(value, "trusted")


@pytest.mark.parametrize(
    "field,new",
    [
        ("kind", "sensor"),
        ("source_id", "other"),
        ("source_type", "family"),
        ("actor_type", "unknown"),
        ("configuration_fingerprint", "next-generation"),
        ("route_fingerprint", "next-route"),
    ],
)
def test_each_stable_source_field_independently_changes_fingerprint(field, new):
    before = fact_source_fingerprint(source())
    after = fact_source_fingerprint(replace(source(), **{field: new}))
    assert after != before
    assert getattr(after, field) == new


def test_fingerprint_has_exact_stable_fields_and_excludes_correlation():
    value = source(
        source_type="family",
        configuration_fingerprint="config",
        route_fingerprint="route",
        actor_type="scheduler",
    )
    expected = FactSourceFingerprint("reaction", "r", "family", "scheduler", "config", "route")
    assert fact_source_fingerprint(value) == expected
    assert set(json.loads(canonical_json_bytes(expected))) == {
        "kind",
        "source_id",
        "source_type",
        "configuration_fingerprint",
        "route_fingerprint",
        "actor_type",
    }
    assert not hasattr(expected, "correlation_id")


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("kind", "fake", ValueError),
        ("source_id", None, TypeError),
        ("source_type", [], TypeError),
        ("configuration_fingerprint", False, TypeError),
        ("route_fingerprint", False, TypeError),
        ("actor_type", "fake", ValueError),
        ("correlation_id", None, TypeError),
    ],
)
def test_forged_fact_source_is_revalidated_by_runtime_shape_and_fingerprint(field, value, error):
    forged = source()
    object.__setattr__(forged, field, value)
    with pytest.raises(error):
        validate_runtime_source_shape(forged)
    with pytest.raises(error):
        fact_source_fingerprint(forged)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("kind", "sensor", ValueError),
        ("source_id", False, TypeError),
        ("correlation_id", None, TypeError),
    ],
)
def test_forged_action_source_is_revalidated(field, value, error):
    forged = source(ApplyStepSource)
    object.__setattr__(forged, field, value)
    with pytest.raises(error):
        validate_runtime_source_shape(forged)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("kind", "fake", ValueError),
        ("source_id", None, TypeError),
        ("source_type", [], TypeError),
        ("actor_type", None, TypeError),
        ("configuration_fingerprint", False, TypeError),
        ("route_fingerprint", False, TypeError),
    ],
)
def test_fingerprint_constructor_validates_its_own_fields(field, value, error):
    with pytest.raises(error):
        replace(fact_source_fingerprint(source()), **{field: value})


@pytest.mark.parametrize("value", [None, "reaction", source(ApplyStepSource)])
def test_fingerprint_requires_fact_source(value):
    with pytest.raises(TypeError):
        fact_source_fingerprint(value)


opaque = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=12)


@given(st.sampled_from(FACT_KINDS), opaque, opaque, opaque)
def test_property_correlation_never_changes_stable_fingerprint(kind, identity, first_id, second_id):
    first = source(kind=kind, source_id=identity, correlation_id=first_id)
    second = replace(first, correlation_id=second_id)
    assert fact_source_fingerprint(first) == fact_source_fingerprint(second)
    assert hash(fact_source_fingerprint(first)) == hash(fact_source_fingerprint(second))
    assert first.correlation_id == first_id and second.correlation_id == second_id


@given(opaque, opaque, opaque)
def test_property_configuration_and_route_are_separate_stable_axes(config, route, next_value):
    value = source(configuration_fingerprint=config, route_fingerprint=route)
    before = fact_source_fingerprint(value)
    assert (
        fact_source_fingerprint(replace(value, configuration_fingerprint=next_value)) == before
    ) is (config == next_value)
    assert (fact_source_fingerprint(replace(value, route_fingerprint=next_value)) == before) is (
        route == next_value
    )


@pytest.mark.parametrize("base", [FactSource, ApplyStepSource])
def test_runtime_shape_validation_does_not_dispatch_to_overridden_subclass_hook(base):
    class UncheckedSource(base):
        def __post_init__(self):
            pass

    unchecked = source(UncheckedSource, correlation_id=None)
    with pytest.raises(TypeError):
        validate_runtime_source_shape(unchecked)
    if base is FactSource:
        with pytest.raises(TypeError):
            fact_source_fingerprint(unchecked)


def test_fingerprint_validates_excluded_correlation_without_subclass_dispatch():
    class UncheckedFact(FactSource):
        def __post_init__(self):
            pass

    with pytest.raises(TypeError):
        fact_source_fingerprint(source(UncheckedFact, correlation_id=None))


@pytest.mark.parametrize("cls", [FactSource, ApplyStepSource])
@pytest.mark.parametrize("field", ["kind", "actor_type"])
def test_default_runtime_mode_rejects_test_data_without_explicit_mode(cls, field):
    with pytest.raises(ValueError):
        validate_runtime_source_shape(source(cls, **{field: "test"}))


@pytest.mark.parametrize("base", [FactSource, ApplyStepSource])
def test_extended_operational_source_is_rejected_before_serializing_person_fields(base):
    from dataclasses import dataclass

    @dataclass(frozen=True, slots=True)
    class ExtendedSource(base):
        actor_ref: str = "fixture-person"

    extended = source(ExtendedSource)
    # Concrete witness: the generic frozen-dataclass codec includes extra fields.
    assert json.loads(canonical_json_bytes(extended))["actor_ref"] == "fixture-person"
    with pytest.raises(TypeError):
        validate_runtime_source_shape(extended)
    if base is FactSource:
        with pytest.raises(TypeError):
            fact_source_fingerprint(extended)


@given(
    st.sampled_from([FactSource, ApplyStepSource]),
    st.sampled_from(["actor_ref", "raw_payload", "extra"]),
    opaque,
    st.booleans(),
)
def test_property_operational_source_admission_rejects_any_extended_schema(
    base, name, payload, test_mode
):
    from dataclasses import field, make_dataclass

    extended_type = make_dataclass(
        "ExtendedSource",
        [(name, str, field(default=payload))],
        bases=(base,),
        frozen=True,
        slots=True,
    )
    extended = source(extended_type)
    with pytest.raises(TypeError):
        validate_runtime_source_shape(extended, test_mode=test_mode)
    if base is FactSource:
        with pytest.raises(TypeError):
            fact_source_fingerprint(extended)
