"""Composed owner/type metadata and exact state uniqueness, L0 §4/L2 §2.3."""

from dataclasses import FrozenInstanceError, fields

import pytest
from hypothesis import given
from hypothesis import strategies as st

from custom_components.heima.v3.contracts.fact_types import FactTypeClaim
from custom_components.heima.v3.contracts.location import Location
from custom_components.heima.v3.runtime.producer_staging import (
    CORE_FACT_TYPE_CLAIMS,
    ComposedFactProducers,
    FactTypeBinding,
    StaticStateClaim,
    compose_fact_producers,
)

# Independent normative fixture: additions/removals/owner or kind changes must be reviewed.
RESERVATIONS = (
    ("manual_hold.lifecycle", "layer0.divergence_hold", "event"),
    ("actuator.resident_control", "layer0.resident_control_ingress", "event"),
    ("actuator.channel_state.*", "layer0.channel_observation", "state"),
    ("actuator.correction", "layer5.correction_attribution", "event"),
    ("actuator.target_lifecycle", "layer5.target_evidence", "event"),
    ("reaction.decision.*", "layer5.reaction_decision", "state"),
    ("reaction.managed_episode.*", "layer5.managed_episode", "state"),
    ("reaction.follow_up", "layer6.reaction_follow_up", "event"),
    ("automation.availability", "layer6.availability", "event"),
    ("reaction.advisory", "layer6.reaction_advisory", "event"),
    ("recovery.confirmation_request", "layer6.recovery_confirmation", "event"),
    ("reaction.action_notice", "layer6.reaction_action_notice", "event"),
    ("proposal.review_pending", "layer6.proposal_review", "event"),
    ("reaction.consent_request", "layer6.consent_request", "event"),
    ("reaction.advisory_feedback", "layer5.advisory_feedback", "event"),
)
ROOMS = frozenset(("a", "b", "c"))
ZONES = frozenset(("night",))
CLAIM = FactTypeClaim("custom.*", "owner", "state")
STATE = StaticStateClaim("custom.reading", Location("room", room_id="a"), "owner")


def compose(**changes):
    args = dict(type_claims=(CLAIM,), state_claims=(STATE,), room_ids=ROOMS, zone_ids=ZONES)
    args.update(changes)
    return compose_fact_producers(**args)


def test_exact_core_reservations_always_included():
    result = compose(type_claims=(), state_claims=(), room_ids=frozenset(), zone_ids=frozenset())
    actual = tuple((c.fact_type_pattern, c.owner_id, c.emission_kind) for c in result.type_claims)
    assert actual == RESERVATIONS
    assert result.type_claims == CORE_FACT_TYPE_CLAIMS
    assert result.state_claims == ()


@pytest.mark.parametrize("pattern,owner,kind", RESERVATIONS)
def test_every_reserved_claim_protects_owner_and_kind(pattern, owner, kind):
    for bad_owner, bad_kind in (("other", kind), (owner, "event" if kind == "state" else "state")):
        with pytest.raises(ValueError):
            compose(type_claims=(FactTypeClaim(pattern, bad_owner, bad_kind),), state_claims=())
    result = compose(type_claims=(FactTypeClaim(pattern, owner, kind),), state_claims=())
    binding = result.resolve_type(pattern.replace("*", "channel"), owner)
    assert binding.emission_kind == kind


@pytest.mark.parametrize("pattern", ["*.*", "actuator.*", "reaction.*", "*.*.*"])
def test_broad_claims_cannot_capture_core_namespaces(pattern):
    with pytest.raises(ValueError):
        compose(type_claims=(FactTypeClaim(pattern, "plugin", "state"),), state_claims=())


@pytest.mark.parametrize(
    "where,accepted",
    [
        (Location("casa"), True),
        (Location("room", room_id="a"), True),
        (Location("room", room_id="missing"), False),
        (Location("zone", zone_id="night"), True),
        (Location("zone", zone_id="missing"), False),
        (Location("rooms", room_ids=frozenset(("a", "b"))), True),
        (Location("rooms", room_ids=frozenset(("a", "missing"))), False),
        (Location("rooms", room_ids=frozenset(("missing", "b"))), False),
        (Location("rooms", room_ids=frozenset(("missing", "other"))), False),
    ],
)
def test_location_reference_decision_table(where, accepted):
    state = StaticStateClaim("custom.reading", where, "owner")
    if accepted:
        result = compose(state_claims=(state,))
        assert result.state_claims == (state,)
        assert result.state_claims[0] is not state
        assert result.state_claims[0].where is not state.where
    else:
        with pytest.raises(ValueError):
            compose(state_claims=(state,))


@pytest.mark.parametrize(
    "states",
    [
        (STATE, STATE),
        (STATE, StaticStateClaim("custom.reading", Location("room", room_id="a"), "other")),
    ],
)
def test_duplicate_static_identity_rejects_even_same_owner(states):
    with pytest.raises(ValueError):
        compose(state_claims=states)


def test_equivalent_type_claims_do_not_create_duplicate_producers():
    result = compose(type_claims=(CLAIM, FactTypeClaim("custom.read*", "owner", "state")))
    assert result.state_claims == (STATE,)
    assert result.resolve_type("custom.reading", "owner").emission_kind == "state"


@pytest.mark.parametrize(
    "change",
    [
        StaticStateClaim("unclaimed", Location("casa"), "owner"),
        StaticStateClaim("custom.reading", Location("casa"), "other"),
        StaticStateClaim("manual_hold.lifecycle", Location("casa"), "layer0.divergence_hold"),
    ],
)
def test_static_claim_requires_matching_declared_owner_and_state_kind(change):
    with pytest.raises(ValueError):
        compose(state_claims=(change,))


def test_core_static_state_producers_can_use_the_reserved_state_namespace():
    state = StaticStateClaim(
        "actuator.channel_state.channel",
        Location("room", room_id="a"),
        "layer0.channel_observation",
    )
    result = compose(type_claims=(), state_claims=(state,))
    assert result.resolve_type(state.fact_type, state.owner_id).emission_kind == "state"


def test_distinct_static_keys_and_event_bindings():
    states = (
        STATE,
        StaticStateClaim("custom.other", STATE.where, "owner"),
        StaticStateClaim(STATE.fact_type, Location("room", room_id="b"), "owner"),
    )
    result = compose(
        type_claims=(
            CLAIM,
            FactTypeClaim("custom.event", "owner", "state"),
            FactTypeClaim("events.*", "event-owner", "event"),
        ),
        state_claims=states,
    )
    assert result.state_claims == states
    binding = result.resolve_type("events.occurred", "event-owner")
    assert binding.fact_type == "events.occurred"
    assert binding.owner_id == "event-owner"
    assert binding.emission_kind == "event"


@pytest.mark.parametrize(
    "name,owner", [("unknown", "owner"), ("custom.reading", "other"), ("custom.*", "owner")]
)
def test_resolution_rejects_undeclared_wrong_owner_or_nonconcrete_type(name, owner):
    with pytest.raises(ValueError):
        compose().resolve_type(name, owner)


def test_failed_candidate_does_not_mutate_previous_composition():
    previous = compose()
    snapshot = (
        previous.type_claims,
        previous.state_claims,
        previous.resolve_type("custom.reading", "owner"),
    )
    with pytest.raises(ValueError):
        compose(state_claims=(STATE, STATE))
    assert snapshot == (
        previous.type_claims,
        previous.state_claims,
        previous.resolve_type("custom.reading", "owner"),
    )


def test_staging_records_are_immutable_exact_and_slotted():
    result = compose()
    binding = result.resolve_type("custom.reading", "owner")
    for record, field in ((STATE, "owner_id"), (result, "state_claims"), (binding, "owner_id")):
        assert not hasattr(record, "__dict__")
        with pytest.raises(FrozenInstanceError):
            setattr(record, field, None)
    assert [f.name for f in fields(STATE)] == ["fact_type", "where", "owner_id"]
    assert [f.name for f in fields(binding)] == ["fact_type", "owner_id", "emission_kind"]
    assert [f.name for f in fields(result)] == ["type_claims", "state_claims"]


@pytest.mark.parametrize("record", [ComposedFactProducers, FactTypeBinding])
def test_composition_and_binding_require_staging_factory(record):
    with pytest.raises(TypeError):
        record()


@pytest.mark.parametrize(
    "changes",
    [
        {"type_claims": []},
        {"state_claims": []},
        {"state_claims": (None,)},
        {"room_ids": set(ROOMS)},
        {"zone_ids": set(ZONES)},
        {"room_ids": frozenset((1,))},
        {"zone_ids": frozenset(("",))},
        {"room_ids": frozenset(("\ud800",))},
        {"zone_ids": frozenset(("\ud800",))},
    ],
)
def test_malformed_candidate_inputs_reject(changes):
    with pytest.raises((TypeError, ValueError)):
        compose(**{"state_claims": (), **changes})


@pytest.mark.parametrize(
    "field,value",
    [
        ("fact_type", "*"),
        ("fact_type", None),
        ("where", None),
        ("where", Location("room", room_id="\ud800")),
        ("owner_id", 1),
        ("owner_id", "\ud800"),
    ],
)
def test_static_claim_validates_essential_shape(field, value):
    args = dict(fact_type=STATE.fact_type, where=STATE.where, owner_id=STATE.owner_id)
    args[field] = value
    with pytest.raises((TypeError, ValueError)):
        StaticStateClaim(**args)


def test_location_subclass_hooks_cannot_hide_static_duplicates():
    class FalseKey(Location):
        @property
        def key(self):
            return ("casa",)

    other = StaticStateClaim(STATE.fact_type, FalseKey("room", room_id="a"), "owner")
    assert type(other.where) is Location
    with pytest.raises(ValueError):
        compose(state_claims=(STATE, other))


@given(st.permutations(("a", "b", "c")), st.booleans())
def test_permuting_claims_preserves_resolved_semantics(rooms, reverse):
    states = tuple(
        StaticStateClaim("custom.reading", Location("room", room_id=room), "owner")
        for room in rooms
    )
    claims = (CLAIM, FactTypeClaim("other.*", "other", "event"))
    if reverse:
        claims = tuple(reversed(claims))
    result = compose(type_claims=claims, state_claims=states)
    assert set(result.state_claims) == set(
        StaticStateClaim("custom.reading", Location("room", room_id=room), "owner")
        for room in ROOMS
    )
    assert result.resolve_type("custom.reading", "owner").emission_kind == "state"
    assert result.resolve_type("other.event", "other").emission_kind == "event"


@given(st.text(alphabet="abcé😀 ", min_size=1, max_size=12))
def test_generated_duplicate_identity_is_always_rejected(room):
    location = Location("room", room_id=room)
    state = StaticStateClaim("custom.reading", location, "owner")
    with pytest.raises(ValueError):
        compose(state_claims=(state, state), room_ids=frozenset((room,)))


@given(st.permutations(("a", "b", "c")))
def test_room_set_input_order_cannot_evade_duplicate_detection(rooms):
    a = StaticStateClaim("custom.reading", Location("rooms", room_ids=frozenset(rooms)), "owner")
    b = StaticStateClaim(
        "custom.reading", Location("rooms", room_ids=frozenset(reversed(rooms))), "owner"
    )
    with pytest.raises(ValueError):
        compose(state_claims=(a, b))
