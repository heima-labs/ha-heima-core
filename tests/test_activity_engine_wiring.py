"""Tests for ActivityDomain engine wiring."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from custom_components.heima.const import OPT_ACTIVITY_BINDINGS
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.inference import (
    ActivitySignal,
    HeimaLearningModule,
    Importance,
    InferenceContext,
)
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class _FakeStateObj:
    def __init__(self, state: str, attributes: dict[str, Any] | None = None) -> None:
        self.state = state
        self.attributes = dict(attributes or {})


class _FakeStates:
    def __init__(self, values: dict[str, str] | None = None) -> None:
        self._values = dict(values or {})

    def get(self, entity_id: str) -> _FakeStateObj | None:
        value = self._values.get(entity_id)
        if value is None:
            return None
        return _FakeStateObj(str(value))


class _FakeBus:
    def async_fire(self, event_type: str, data: dict[str, Any]) -> None:
        del event_type, data


class _FakeServices:
    async def async_call(self, *args: Any, **kwargs: Any) -> None:
        del args, kwargs

    def async_services(self) -> dict[str, dict[str, Any]]:
        return {"notify": {}}


class _RecordingModule(HeimaLearningModule):
    module_id = "recording"
    received: list[InferenceContext] = []
    emitted: list[ActivitySignal] = []

    def infer(self, context: InferenceContext) -> list[ActivitySignal]:
        type(self).received.append(context)
        return list(type(self).emitted)


class _RecordingSnapshotStore:
    def __init__(self) -> None:
        self.snapshots: list[Any] = []

    async def async_append_if_changed(self, snapshot: Any) -> bool:
        self.snapshots.append(snapshot)
        return True


def _engine(
    *,
    options: dict[str, Any] | None = None,
    states: dict[str, str] | None = None,
) -> HeimaEngine:
    hass = SimpleNamespace(
        states=_FakeStates(states),
        bus=_FakeBus(),
        services=_FakeServices(),
    )
    return HeimaEngine(hass=hass, entry=SimpleNamespace(options=options or {}))


def test_engine_configures_activity_detectors_from_bindings() -> None:
    engine = _engine(
        options={
            OPT_ACTIVITY_BINDINGS: {
                "stove_on": {"stove_power_entity": "sensor.stove_power"},
                "shower_running": {"bathroom_humidity_entity": "sensor.bathroom_humidity"},
            }
        }
    )

    assert engine._activity_domain.detector_entity_ids() == (  # noqa: SLF001
        "sensor.bathroom_humidity",
        "sensor.stove_power",
    )


def test_compute_snapshot_runs_activity_before_house_state_and_domain_plugins() -> None:
    engine = _engine(
        options={
            OPT_ACTIVITY_BINDINGS: {
                "stove_on": {
                    "stove_power_entity": "sensor.stove_power",
                    "candidate_period_s": 0,
                }
            }
        },
        states={"sensor.stove_power": "250"},
    )

    engine._compute_snapshot(reason="first")  # noqa: SLF001
    engine._compute_snapshot(reason="second")  # noqa: SLF001

    activity_result = engine._last_domain_results.require("activity")  # noqa: SLF001
    assert [activity.name for activity in activity_result.active] == ["stove_on"]
    assert engine.state.get_sensor("activity.active_names") == ("stove_on",)


def test_collect_signals_uses_previous_activity_names_from_canonical_state() -> None:
    _RecordingModule.received = []
    module = _RecordingModule()
    engine = _engine()
    engine.register_learning_module(module)
    engine.state.set_sensor("activity.active_names", ("stove_on", "tv_active"))

    engine._collect_signals(  # noqa: SLF001
        anyone_home=True,
        named_present=("alice",),
        occupied_rooms=["kitchen"],
        now_utc=datetime(2026, 5, 3, 12, 0, tzinfo=UTC),
    )

    assert _RecordingModule.received[-1].previous_activity_names == ("stove_on", "tv_active")


def test_activity_signal_is_merged_by_activity_domain_during_snapshot_compute() -> None:
    signal = ActivitySignal(
        source_id="test",
        confidence=0.8,
        importance=Importance.SUGGEST,
        ttl_s=600,
        label="movie",
        activity_name="movie_night",
        room_id="living",
    )
    _RecordingModule.received = []
    _RecordingModule.emitted = [signal]
    engine = _engine()
    engine.register_learning_module(_RecordingModule())

    engine._compute_snapshot(reason="activity_signal")  # noqa: SLF001

    assert engine.state.get_sensor("activity.active_names") == ("movie_night",)


def test_record_snapshot_persists_detected_activities() -> None:
    engine = _engine()
    store = _RecordingSnapshotStore()
    engine.set_snapshot_store(store)  # type: ignore[arg-type]
    engine.state.set_sensor("activity.active_names", ("movie_night", "stove_on"))
    engine.state.set_sensor("heima_people_home_list", "alice")
    snapshot = DecisionSnapshot(
        snapshot_id="snapshot",
        ts="2026-05-03T12:00:00+00:00",
        house_state="home",
        anyone_home=True,
        people_count=1,
        occupied_rooms=["kitchen"],
        lighting_intents={},
        security_state="disarmed",
    )

    import asyncio

    asyncio.run(engine._record_snapshot_if_changed(snapshot))  # noqa: SLF001

    assert store.snapshots[-1].detected_activities == ("movie_night", "stove_on")
