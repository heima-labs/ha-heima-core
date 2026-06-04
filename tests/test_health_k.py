from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.entities.registry import build_registry
from custom_components.heima.runtime.state_store import CanonicalState


class _FakeServices:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict, bool]] = []

    async def async_call(self, domain, service, data, blocking=False):  # noqa: ANN001
        self.calls.append((domain, service, dict(data), blocking))


class _FakeDiagnosticsSource:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {}

    def diagnostics(self) -> dict:
        return dict(self.payload)


def _coordinator() -> HeimaCoordinator:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(entry_id="entry-1")
    coordinator.hass = SimpleNamespace(services=_FakeServices())
    coordinator.engine = SimpleNamespace(
        health=SimpleNamespace(ok=True, reason="initialized"),
        state=CanonicalState(sensors={"heima_health": None}),
        diagnostics=lambda: {"engine": "ok"},
    )
    coordinator._event_store = _FakeDiagnosticsSource({"events": 1})
    coordinator._proposal_engine = _FakeDiagnosticsSource({"proposals": 2})
    coordinator._approval_store = _FakeDiagnosticsSource({"approvals": 3})
    coordinator._house_snapshot_store = _FakeDiagnosticsSource({"snapshots": 4})
    coordinator._outcome_tracker = _FakeDiagnosticsSource({"outcomes": 5})
    coordinator._ha_backed_reconciliation_summary = {}
    coordinator._last_anomaly = None
    coordinator._last_invariant_violation = None
    coordinator._last_diagnostics = {}
    coordinator._notified_installer_alert_keys = set()
    coordinator.async_refresh = _async_noop
    return coordinator


async def _async_noop() -> None:
    return None


def test_heima_health_sensor_is_registered_by_default() -> None:
    registry = build_registry(SimpleNamespace(options={}))

    assert any(sensor.key == "heima_health" for sensor in registry.sensors)


def test_health_sensor_is_ok_without_alerts() -> None:
    coordinator = _coordinator()

    coordinator._sync_health_sensor()  # noqa: SLF001

    assert coordinator.engine.state.get_sensor("heima_health") == "ok"
    attrs = coordinator.engine.state.get_sensor_attributes("heima_health")
    assert attrs["health_reason"] == "initialized"
    assert attrs["last_anomaly"] == {}


def test_health_sensor_exposes_house_state_model_summary() -> None:
    coordinator = _coordinator()
    coordinator._house_state_module = _FakeDiagnosticsSource(
        {
            "model_first_snapshot_ts": "2026-05-01T10:00:00+00:00",
            "model_last_snapshot_ts": "2026-05-02T10:00:00+00:00",
            "model_total_snapshots": 42,
            "approved_model_entries": [{"context_key": "ctx-1"}, {"context_key": "ctx-2"}],
        }
    )

    coordinator._sync_health_sensor()  # noqa: SLF001

    attrs = coordinator.engine.state.get_sensor_attributes("heima_health")
    assert attrs["house_state_model"] == {
        "model_first_snapshot_ts": "2026-05-01T10:00:00+00:00",
        "model_last_snapshot_ts": "2026-05-02T10:00:00+00:00",
        "model_total_snapshots": 42,
        "approved_model_entries": 2,
    }


def test_resolved_invariant_clears_degraded_health() -> None:
    coordinator = _coordinator()
    event = {
        "type": "anomaly.heating_home_empty",
        "key": "anomaly.heating_home_empty",
        "severity": "warning",
        "title": "Invariant violation",
        "message": "Heating is active while home is empty.",
        "context": {"check_id": "heating_home_empty", "anomaly_type": "heating_home_empty"},
        "event_id": "evt-1",
        "ts": "2026-05-07T10:00:00+00:00",
    }
    coordinator._record_installer_alert(event)  # noqa: SLF001

    coordinator._clear_resolved_invariant_alert(  # noqa: SLF001
        {"context": {"check_id": "heating_home_empty"}}
    )
    coordinator._sync_health_sensor()  # noqa: SLF001

    assert coordinator.engine.state.get_sensor("heima_health") == "ok"


@pytest.mark.asyncio
async def test_installer_alert_notification_degrades_health() -> None:
    coordinator = _coordinator()
    event = {
        "type": "anomaly.heating_home_empty",
        "key": "anomaly.heating_home_empty",
        "severity": "warning",
        "title": "Invariant violation",
        "message": "Heating is active while home is empty.",
        "context": {"check_id": "heating_home_empty", "anomaly_type": "heating_home_empty"},
        "event_id": "evt-1",
        "ts": "2026-05-07T10:00:00+00:00",
    }

    coordinator._record_installer_alert(event)  # noqa: SLF001
    await coordinator._async_notify_installer_alert(event)  # noqa: SLF001
    coordinator._sync_health_sensor()  # noqa: SLF001

    assert coordinator.engine.state.get_sensor("heima_health") == "degraded"
    attrs = coordinator.engine.state.get_sensor_attributes("heima_health")
    assert attrs["last_anomaly"]["type"] == "anomaly.heating_home_empty"
    assert attrs["last_invariant_violation"]["context"]["check_id"] == "heating_home_empty"
    assert coordinator.hass.services.calls[0][0:2] == ("persistent_notification", "create")
    assert coordinator.hass.services.calls[0][2]["notification_id"].startswith("heima_installer_")


@pytest.mark.asyncio
async def test_run_diagnostics_updates_health_attributes() -> None:
    coordinator = _coordinator()

    payload = await coordinator.async_run_diagnostics()

    assert payload["status"] == "ok"
    assert payload["engine"] == {"engine": "ok"}
    attrs = coordinator.engine.state.get_sensor_attributes("heima_health")
    assert attrs["last_diagnostics"]["event_store"] == {"events": 1}
