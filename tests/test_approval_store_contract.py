from __future__ import annotations

from custom_components.heima.runtime.inference.approval_store import (
    ACTIVITY_PROPOSAL_TYPE,
    HOUSE_STATE_PROPOSAL_TYPE,
    ApprovalRecord,
    ApprovalStore,
    activity_context_key,
    activity_context_snapshot,
    canonicalize_activity_context_conditions,
    canonicalize_learning_context,
    house_state_context_key,
    house_state_context_snapshot,
)


class _FakeStore:
    def __init__(self, hass, version, key):  # noqa: ANN001, ARG002
        self._data = None
        self.saved: list[dict] = []

    async def async_load(self):
        return self._data

    async def async_save(self, data):
        self._data = data
        self.saved.append(data)

    def async_delay_save(self, serialize, delay):  # noqa: ANN001, ARG002
        self._data = serialize()
        self.saved.append(self._data)


def _record(
    *,
    proposal_id: str = "proposal-1",
    decision: str = "approved",
    approved_by: str = "installer",
    context_key: str = "ctx-1",
) -> ApprovalRecord:
    return ApprovalRecord(
        proposal_id=proposal_id,
        proposal_type=HOUSE_STATE_PROPOSAL_TYPE,
        decision=decision,  # type: ignore[arg-type]
        approved_by=approved_by,  # type: ignore[arg-type]
        context_key=context_key,
        context_snapshot={"weekday": 1, "predicted_state": "working"},
    )


def _activity_record(
    *,
    proposal_id: str = "activity-proposal-1",
    decision: str = "approved",
    approved_by: str = "resident",
    context_key: str = "activity-ctx-1",
) -> ApprovalRecord:
    return ApprovalRecord(
        proposal_id=proposal_id,
        proposal_type=ACTIVITY_PROPOSAL_TYPE,
        decision=decision,  # type: ignore[arg-type]
        approved_by=approved_by,  # type: ignore[arg-type]
        context_key=context_key,
        context_snapshot={
            "activity_name": "movie_night",
            "primitive_pattern": ["relax", "tv"],
            "context_conditions": {"room_id": "living_room"},
        },
    )


def test_approval_record_requires_approved_by_role() -> None:
    record = _record(approved_by="installer")

    assert record.approved_by == "installer"
    assert record.as_dict()["approved_by"] == "installer"


def test_approval_record_requires_context_snapshot() -> None:
    assert (
        ApprovalRecord.from_dict(
            {
                "proposal_id": "proposal-1",
                "proposal_type": HOUSE_STATE_PROPOSAL_TYPE,
                "decision": "approved",
                "approved_by": "installer",
                "context_key": "ctx-1",
            }
        )
        is None
    )


def test_approval_record_from_dict_rejects_missing_approved_by() -> None:
    assert (
        ApprovalRecord.from_dict(
            {
                "proposal_id": "proposal-1",
                "proposal_type": HOUSE_STATE_PROPOSAL_TYPE,
                "decision": "approved",
                "context_key": "ctx-1",
                "context_snapshot": {"weekday": 1},
            }
        )
        is None
    )


def test_approval_record_from_dict_accepts_resident_and_installer_roles() -> None:
    resident = ApprovalRecord.from_dict(
        {
            "proposal_id": "proposal-1",
            "proposal_type": HOUSE_STATE_PROPOSAL_TYPE,
            "decision": "approved",
            "approved_by": "resident",
            "context_key": "ctx-1",
            "context_snapshot": {"weekday": 1},
        }
    )
    installer = ApprovalRecord.from_dict(
        {
            "proposal_id": "proposal-2",
            "proposal_type": ACTIVITY_PROPOSAL_TYPE,
            "decision": "rejected",
            "approved_by": "installer",
            "context_key": "ctx-2",
            "context_snapshot": {"activity": "movie_night"},
            "metadata": {"source": "service"},
        }
    )

    assert resident is not None
    assert resident.approved_by == "resident"
    assert installer is not None
    assert installer.approved_by == "installer"
    assert installer.metadata == {"source": "service"}


def test_approval_store_contract_reserves_storage_key() -> None:
    assert ApprovalStore.STORAGE_KEY == "heima_inference_approvals"


async def test_approval_store_loads_and_saves_records(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.inference.approval_store.Store", _FakeStore
    )
    store = ApprovalStore(object())  # type: ignore[arg-type]
    await store.async_load()

    await store.async_record(_record(context_key="ctx-1"))
    await store.async_flush()

    assert store.decision_for("ctx-1", HOUSE_STATE_PROPOSAL_TYPE) is not None
    assert store.diagnostics()["total_records"] == 1


async def test_approval_store_ignores_malformed_records(monkeypatch) -> None:
    fake_store = _FakeStore(None, 1, "key")
    fake_store._data = {
        "data": {
            "records": [
                _record(context_key="ctx-valid").as_dict(),
                {"proposal_id": "bad", "decision": "approved"},
                "not-a-record",
            ]
        }
    }
    monkeypatch.setattr(
        "custom_components.heima.runtime.inference.approval_store.Store",
        lambda *args, **kwargs: fake_store,
    )
    store = ApprovalStore(object())  # type: ignore[arg-type]

    await store.async_load()

    assert len(store.records()) == 1
    assert store.records()[0].context_key == "ctx-valid"


async def test_approval_store_replaces_decision_for_context_and_type(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.inference.approval_store.Store", _FakeStore
    )
    store = ApprovalStore(object())  # type: ignore[arg-type]
    await store.async_load()

    await store.async_record(_record(context_key="ctx-1", decision="approved"))
    await store.async_record(
        _record(proposal_id="proposal-2", context_key="ctx-1", decision="rejected")
    )

    decision = store.decision_for("ctx-1", HOUSE_STATE_PROPOSAL_TYPE)
    assert decision is not None
    assert decision.decision == "rejected"
    assert store.approved_records() == ()


async def test_approval_store_saves_activity_discovered_records(monkeypatch) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.inference.approval_store.Store", _FakeStore
    )
    store = ApprovalStore(object())  # type: ignore[arg-type]
    await store.async_load()

    await store.async_record(_activity_record(context_key="activity-ctx-1"))
    await store.async_flush()

    decision = store.decision_for("activity-ctx-1", ACTIVITY_PROPOSAL_TYPE)
    assert decision is not None
    assert decision.proposal_type == ACTIVITY_PROPOSAL_TYPE
    assert decision.approved_by == "resident"


async def test_approval_store_persists_activity_rejection(monkeypatch) -> None:
    fake_store = _FakeStore(None, 1, "key")
    fake_store._data = {
        "data": {
            "records": [
                _activity_record(
                    context_key="activity-ctx-reject",
                    decision="rejected",
                    approved_by="installer",
                ).as_dict()
            ]
        }
    }
    monkeypatch.setattr(
        "custom_components.heima.runtime.inference.approval_store.Store",
        lambda *args, **kwargs: fake_store,
    )
    store = ApprovalStore(object())  # type: ignore[arg-type]

    await store.async_load()

    decision = store.decision_for("activity-ctx-reject", ACTIVITY_PROPOSAL_TYPE)
    assert decision is not None
    assert decision.decision == "rejected"
    assert decision.approved_by == "installer"


def test_house_state_context_key_sorts_rooms_and_includes_state() -> None:
    first = house_state_context_key(
        weekday=1,
        hour_bucket=8,
        rooms=["kitchen", "bedroom"],
        anyone_home=True,
        predicted_state="Working",
    )
    second = house_state_context_key(
        weekday=1,
        hour_bucket=8,
        rooms=["bedroom", "kitchen"],
        anyone_home=True,
        predicted_state="Working",
    )

    assert first == second
    assert "rooms:bedroom,kitchen" in first
    assert first.endswith(":state:working")


def test_house_state_context_key_uses_none_for_empty_context_and_rooms() -> None:
    key = house_state_context_key(
        weekday=2,
        hour_bucket=22,
        rooms=[],
        anyone_home=False,
        predicted_state="sleeping",
    )

    assert key == "weekday:2:hour_bucket:22:rooms:none:anyone_home:0:ctx:none:state:sleeping"


def test_house_state_context_key_hash_is_stable_for_canonical_context() -> None:
    first = house_state_context_key(
        weekday=1,
        hour_bucket=8,
        rooms=["studio"],
        anyone_home=True,
        predicted_state="working",
        learning_context={"presence.anyone_home": True, "activity.pc_active": "on"},
    )
    second = house_state_context_key(
        weekday=1,
        hour_bucket=8,
        rooms=["studio"],
        anyone_home=True,
        predicted_state="working",
        learning_context={"activity.pc_active": "on", "presence.anyone_home": True},
    )

    assert first == second
    assert ":ctx:none:" not in first


def test_canonicalize_learning_context_filters_h1_vocabulary() -> None:
    assert canonicalize_learning_context(
        {
            "activity.pc_active": "ON",
            "occupancy.studio": True,
            "presence.anyone_home": True,
            "custom.future_key": "ignored",
        }
    ) == {
        "activity.pc_active": "on",
        "occupancy.studio": "true",
        "presence.anyone_home": "true",
    }


def test_house_state_context_snapshot_is_human_readable() -> None:
    snapshot = house_state_context_snapshot(
        weekday=1,
        hour_bucket=8,
        rooms=["studio", "kitchen"],
        anyone_home=True,
        predicted_state="Working",
        learning_context={"activity.pc_active": "on"},
    )

    assert snapshot == {
        "weekday": 1,
        "hour_bucket": 8,
        "rooms": ["kitchen", "studio"],
        "anyone_home": True,
        "predicted_state": "working",
        "learning_context": {"activity.pc_active": "on"},
    }


def test_activity_context_key_normalizes_activity_name() -> None:
    first = activity_context_key(
        activity_name="Movie Night",
        primitive_pattern={"tv", "relax"},
        context_conditions={"room_id": "Living Room"},
    )
    second = activity_context_key(
        activity_name="movie_night",
        primitive_pattern={"relax", "tv"},
        context_conditions={"room_id": "living_room"},
    )

    assert first == second
    assert first.startswith("activity:movie_night:pattern:relax,tv:ctx:")


def test_activity_context_key_changes_with_activity_name() -> None:
    first = activity_context_key(
        activity_name="Movie Night",
        primitive_pattern={"tv", "relax"},
        context_conditions={"room_id": "living_room"},
    )
    second = activity_context_key(
        activity_name="Gaming Session",
        primitive_pattern={"tv", "relax"},
        context_conditions={"room_id": "living_room"},
    )

    assert first != second


def test_activity_context_key_changes_with_context_conditions() -> None:
    first = activity_context_key(
        activity_name="Movie Night",
        primitive_pattern={"tv", "relax"},
        context_conditions={"room_id": "living_room", "hour_range": [20, 24]},
    )
    second = activity_context_key(
        activity_name="Movie Night",
        primitive_pattern={"tv", "relax"},
        context_conditions={"room_id": "living_room", "hour_range": [18, 20]},
    )

    assert first != second


def test_activity_context_key_uses_none_for_empty_pattern_and_context() -> None:
    key = activity_context_key(
        activity_name="Movie Night",
        primitive_pattern=[],
        context_conditions={},
    )

    assert key == "activity:movie_night:pattern:none:ctx:none"


def test_canonicalize_activity_context_conditions_is_stable_and_readable() -> None:
    assert canonicalize_activity_context_conditions(
        {
            "room_id": "Living Room",
            "hour_range": [20, 24],
            "weekday_filter": {"days": {"Friday", "Monday"}},
            "ignored": None,
        }
    ) == {
        "hour_range": [20, 24],
        "room_id": "living_room",
        "weekday_filter": {"days": ["friday", "monday"]},
    }


def test_activity_context_snapshot_is_human_readable() -> None:
    snapshot = activity_context_snapshot(
        activity_name="Movie Night",
        primitive_pattern=["tv", "relax", "tv"],
        context_conditions={"room_id": "Living Room", "hour_range": [20, 24]},
    )

    assert snapshot == {
        "activity_name": "movie_night",
        "primitive_pattern": ["relax", "tv"],
        "context_conditions": {"hour_range": [20, 24], "room_id": "living_room"},
    }
