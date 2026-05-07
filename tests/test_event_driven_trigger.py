from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.coordinator import HeimaCoordinator


class _FakeState:
    def __init__(self, state: str) -> None:
        self.state = state


class _FakeEvent:
    def __init__(
        self,
        entity_id: str,
        *,
        old_state: str | None = "off",
        new_state: str | None = "on",
    ) -> None:
        self.data = {
            "entity_id": entity_id,
            "old_state": _FakeState(old_state) if old_state is not None else None,
            "new_state": _FakeState(new_state) if new_state is not None else None,
        }


class _FakeHass:
    def __init__(self) -> None:
        self.created_tasks: list[object] = []

    def async_create_task(self, coro):  # noqa: ANN001
        self.created_tasks.append(coro)
        return coro


def _coordinator(options: dict | None = None) -> HeimaCoordinator:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(options=options or {})
    coordinator.hass = _FakeHass()
    coordinator._unsub_periodic_fallback = None
    coordinator._debounce_handles = {}
    coordinator._pending_eval_reasons = {}
    coordinator._eval_pending = False
    coordinator._eval_running = False
    coordinator._power_threshold_last_values = {}
    return coordinator


def test_classify_entity_prefers_explicit_config_and_patterns() -> None:
    coordinator = _coordinator(
        {
            "people_named": [
                {
                    "person_entity": "person.stefano",
                    "sources": ["device_tracker.phone"],
                }
            ],
            "learning": {"weather_entity": "weather.home"},
            "activity_bindings": {
                "stove_on": {"stove_power_entity": "sensor.stove_power"},
            },
            "rooms": [
                {
                    "room_id": "studio",
                    "occupancy_sources": ["binary_sensor.room_presence"],
                    "learning_sources": ["sensor.studio_lux"],
                }
            ],
        }
    )

    assert coordinator._classify_entity("person.stefano") == "presence"  # noqa: SLF001
    assert coordinator._classify_entity("device_tracker.phone") == "presence"  # noqa: SLF001
    assert coordinator._classify_entity("binary_sensor.hall_motion") == "motion"  # noqa: SLF001
    assert coordinator._classify_entity("binary_sensor.front_door") == "door_window"  # noqa: SLF001
    assert coordinator._classify_entity("calendar.family") == "calendar"  # noqa: SLF001
    assert coordinator._classify_entity("weather.home") == "weather"  # noqa: SLF001
    assert coordinator._classify_entity("sensor.stove_power") == "power_threshold"  # noqa: SLF001
    assert coordinator._classify_entity("binary_sensor.room_presence") == "presence"  # noqa: SLF001
    assert coordinator._classify_entity("sensor.studio_lux") is None  # noqa: SLF001


def test_environmental_sensors_do_not_trigger() -> None:
    coordinator = _coordinator(
        {
            "activity_bindings": {
                "shower_running": {"bathroom_humidity_entity": "sensor.bathroom_humidity"},
            }
        }
    )

    assert coordinator._classify_entity("sensor.bathroom_humidity") is None  # noqa: SLF001
    assert coordinator._classify_entity("sensor.studio_lux") is None  # noqa: SLF001
    assert coordinator._classify_entity("sensor.outdoor_temperature") is None  # noqa: SLF001
    assert coordinator._classify_entity("sensor.living_room_co2") is None  # noqa: SLF001


def test_power_threshold_crossing_triggers_both_directions() -> None:
    coordinator = _coordinator(
        {
            "activity_bindings": {
                "stove_on": {
                    "stove_power_entity": "sensor.stove_power",
                    "threshold_w": 200,
                }
            }
        }
    )

    assert not coordinator._power_threshold_crossed(  # noqa: SLF001
        _FakeEvent("sensor.stove_power", old_state="0", new_state="150")
    )
    assert coordinator._power_threshold_crossed(  # noqa: SLF001
        _FakeEvent("sensor.stove_power", old_state="150", new_state="250")
    )
    assert not coordinator._power_threshold_crossed(  # noqa: SLF001
        _FakeEvent("sensor.stove_power", old_state="250", new_state="260")
    )
    assert coordinator._power_threshold_crossed(  # noqa: SLF001
        _FakeEvent("sensor.stove_power", old_state="260", new_state="100")
    )


def test_state_changed_schedules_debounced_evaluation(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator = _coordinator()
    scheduled: list[tuple[float, object]] = []

    def fake_call_later(hass, delay, callback):  # noqa: ANN001
        scheduled.append((delay, callback))
        return lambda: None

    monkeypatch.setattr("custom_components.heima.coordinator.async_call_later", fake_call_later)

    coordinator._on_state_changed(_FakeEvent("person.stefano"))  # noqa: SLF001

    assert scheduled == [(5.0, scheduled[0][1])]
    assert coordinator._eval_pending is True  # noqa: SLF001
    assert coordinator._pending_eval_reasons == {"presence": "state_changed:person.stefano"}  # noqa: SLF001


def test_same_class_debounce_collapses_pending_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator()
    cancelled = 0
    scheduled: list[float] = []

    def fake_call_later(hass, delay, callback):  # noqa: ANN001
        scheduled.append(delay)

        def cancel() -> None:
            nonlocal cancelled
            cancelled += 1

        return cancel

    monkeypatch.setattr("custom_components.heima.coordinator.async_call_later", fake_call_later)

    coordinator._on_state_changed(_FakeEvent("binary_sensor.hall_motion"))  # noqa: SLF001
    coordinator._on_state_changed(_FakeEvent("binary_sensor.kitchen_motion"))  # noqa: SLF001

    assert scheduled == [3.0, 3.0]
    assert cancelled == 1
    assert coordinator._pending_eval_reasons == {  # noqa: SLF001
        "motion": "state_changed:binary_sensor.kitchen_motion"
    }


@pytest.mark.asyncio
async def test_reentrant_trigger_reschedules_with_normal_debounce(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator = _coordinator()
    coordinator._eval_running = True  # noqa: SLF001
    scheduled: list[float] = []

    def fake_call_later(hass, delay, callback):  # noqa: ANN001
        scheduled.append(delay)
        return lambda: None

    async def fail_evaluation(reason: str) -> None:
        raise AssertionError(f"unexpected evaluation: {reason}")

    monkeypatch.setattr("custom_components.heima.coordinator.async_call_later", fake_call_later)
    coordinator.async_request_evaluation = fail_evaluation

    await coordinator._trigger_eval(  # noqa: SLF001
        "presence",
        reason="state_changed:person.stefano",
    )

    assert scheduled == [5.0]
    assert coordinator._pending_eval_reasons == {"presence": "state_changed:person.stefano"}  # noqa: SLF001


@pytest.mark.asyncio
async def test_trigger_eval_runs_reconciled_evaluation() -> None:
    coordinator = _coordinator()
    evaluated: list[str] = []

    async def no_reconciliation_change():
        return {}, False

    async def emit_reconciliation_events(summary):  # noqa: ANN001
        raise AssertionError(f"unexpected reconciliation event: {summary}")

    async def request_evaluation(reason: str) -> None:
        evaluated.append(reason)

    coordinator._async_reconcile_ha_backed_objects = no_reconciliation_change  # noqa: SLF001
    coordinator._async_emit_reconciliation_events = emit_reconciliation_events  # noqa: SLF001
    coordinator.async_request_evaluation = request_evaluation
    coordinator._pending_eval_reasons = {"motion": "state_changed:binary_sensor.hall_motion"}  # noqa: SLF001
    coordinator._eval_pending = True  # noqa: SLF001

    await coordinator._trigger_eval("motion")  # noqa: SLF001

    assert evaluated == ["state_changed:binary_sensor.hall_motion"]
    assert coordinator._eval_running is False  # noqa: SLF001
    assert coordinator._eval_pending is False  # noqa: SLF001


def test_periodic_fallback_uses_300s_timer(monkeypatch: pytest.MonkeyPatch) -> None:
    coordinator = _coordinator()
    scheduled: list[float] = []

    def fake_call_later(hass, delay, callback):  # noqa: ANN001
        scheduled.append(delay)
        return lambda: None

    monkeypatch.setattr("custom_components.heima.coordinator.async_call_later", fake_call_later)

    coordinator._schedule_periodic_fallback()  # noqa: SLF001

    assert scheduled == [300]
