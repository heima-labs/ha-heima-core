"""Tests for Phase Q anomaly analyzer."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.runtime.analyzers import AnomalyAnalyzer
from custom_components.heima.runtime.finding_router import FindingRouter
from custom_components.heima.runtime.inference import HouseSnapshot


class _FakeEventStore:
    pass


class _FakeSnapshotStore:
    def __init__(self, snapshots: list[HouseSnapshot]) -> None:
        self._snapshots = snapshots

    def snapshots(self, *, limit: int | None = None) -> list[HouseSnapshot]:
        if limit is None:
            return list(self._snapshots)
        return list(self._snapshots[-limit:])


class _FakeServices:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any], bool]] = []

    async def async_call(
        self,
        domain: str,
        service: str,
        data: dict[str, Any],
        *,
        blocking: bool,
    ) -> None:
        self.calls.append((domain, service, data, blocking))


class _FakeState:
    def __init__(self) -> None:
        self._attrs: dict[str, Any] = {}

    def get_sensor_attributes(self, key: str) -> dict[str, Any]:
        del key
        return dict(self._attrs)

    def set_last_event(self, event: dict[str, Any]) -> None:
        self._attrs = dict(event)


class _FakeEngine:
    def __init__(self) -> None:
        self.state = _FakeState()

    async def async_emit_external_event(
        self,
        *,
        event_type: str,
        key: str,
        severity: str,
        title: str,
        message: str,
        context: dict[str, Any],
    ) -> None:
        self.state.set_last_event(
            {
                "event_id": f"{event_type}:test",
                "type": event_type,
                "key": key,
                "severity": severity,
                "title": title,
                "message": message,
                "context": context,
            }
        )


def _snapshot(
    *,
    heating_setpoint: float = 21.0,
    heating_current_temperature: float | None = 18.0,
) -> HouseSnapshot:
    return HouseSnapshot(
        ts="2026-05-17T20:00:00+00:00",
        weekday=6,
        minute_of_day=20 * 60,
        anyone_home=True,
        named_present=("alice",),
        room_occupancy={"living": True},
        detected_activities=(),
        house_state="home",
        heating_setpoint=heating_setpoint,
        heating_current_temperature=heating_current_temperature,
        lighting_scenes={},
        security_state="disarmed",
    )


async def test_anomaly_analyzer_heating_unresponsive_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _snapshot(heating_current_temperature=18.0),
        _snapshot(heating_current_temperature=18.05),
        _snapshot(heating_current_temperature=18.1),
        _snapshot(heating_current_temperature=18.1),
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert len(findings) == 1
    finding = findings[0]
    assert finding.kind == "anomaly"
    assert finding.payload.anomaly_type == "heating_unresponsive"
    assert finding.payload.severity == "warning"
    assert finding.payload.context["snapshot_count"] == 4


async def test_anomaly_analyzer_respects_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "heating_unresponsive": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots = [_snapshot(heating_current_temperature=18.0) for _ in range(4)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert findings == []
    assert analyzer.diagnostics()["rules"]["heating_unresponsive"]["enabled"] is False


async def test_anomaly_analyzer_applies_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "heating_unresponsive": {
                        "thresholds": {
                            "min_gap_c": 4.0,
                        }
                    }
                }
            }
        }
    )
    snapshots = [_snapshot(heating_current_temperature=18.0) for _ in range(4)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert findings == []
    assert (
        analyzer.diagnostics()["rules"]["heating_unresponsive"]["thresholds"]["min_gap_c"]
        == 4.0
    )


async def test_anomaly_finding_routes_to_installer_alert() -> None:
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.engine = _FakeEngine()
    coordinator.hass = SimpleNamespace(services=_FakeServices())
    coordinator._notified_installer_alert_keys = set()
    coordinator._last_anomaly = None
    coordinator._last_invariant_violation = None
    coordinator._sync_health_sensor = MagicMock()
    coordinator._event_store = _FakeEventStore()
    coordinator._house_snapshot_store = _FakeSnapshotStore(
        [_snapshot(heating_current_temperature=18.0) for _ in range(4)]
    )
    coordinator._anomaly_analyzer = AnomalyAnalyzer()
    coordinator._finding_router = FindingRouter(
        proposal_engine=SimpleNamespace(),
        anomaly_handler=coordinator._async_handle_anomaly_finding,
    )

    await coordinator._async_run_anomaly_analyzer()

    assert coordinator._last_anomaly is not None
    assert coordinator._last_anomaly["type"] == "anomaly.heating_unresponsive"
    services = coordinator.hass.services
    assert services.calls
    assert services.calls[0][0:2] == ("persistent_notification", "create")
