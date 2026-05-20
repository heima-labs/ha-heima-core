"""Tests for Phase Q anomaly analyzer."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
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
    ts: str = "2026-05-17T20:00:00+00:00",
    weekday: int = 6,
    minute_of_day: int = 20 * 60,
    anyone_home: bool = True,
    room_occupancy: dict[str, bool] | None = None,
    detected_activities: tuple[str, ...] = (),
    heating_setpoint: float = 21.0,
    heating_current_temperature: float | None = 18.0,
    security_state: str = "disarmed",
) -> HouseSnapshot:
    return HouseSnapshot(
        ts=ts,
        weekday=weekday,
        minute_of_day=minute_of_day,
        anyone_home=anyone_home,
        named_present=("alice",),
        room_occupancy=room_occupancy if room_occupancy is not None else {"living": True},
        detected_activities=detected_activities,
        house_state="home",
        heating_setpoint=heating_setpoint,
        heating_current_temperature=heating_current_temperature,
        lighting_scenes={},
        security_state=security_state,
    )


def _timed_snapshot(
    when: datetime,
    *,
    weekday: int | None = None,
    hour: int | None = None,
    room_occupancy: dict[str, bool] | None = None,
    anyone_home: bool = True,
) -> HouseSnapshot:
    local_hour = when.hour if hour is None else hour
    return _snapshot(
        ts=when.isoformat(),
        weekday=when.weekday() if weekday is None else weekday,
        minute_of_day=local_hour * 60,
        anyone_home=anyone_home,
        room_occupancy=room_occupancy,
    )


def _presence_snapshot(*, hour: int, anyone_home: bool, weekday: int = 1) -> HouseSnapshot:
    return _snapshot(
        weekday=weekday,
        minute_of_day=hour * 60,
        anyone_home=anyone_home,
        room_occupancy={"living": True} if anyone_home else {},
        heating_current_temperature=21.0,
    )


def _presence_transition_pair(*, hour: int, arrival: bool, weekday: int = 1) -> list[HouseSnapshot]:
    if arrival:
        return [
            _presence_snapshot(hour=hour, anyone_home=False, weekday=weekday),
            _presence_snapshot(hour=hour, anyone_home=True, weekday=weekday),
        ]
    return [
        _presence_snapshot(hour=hour, anyone_home=True, weekday=weekday),
        _presence_snapshot(hour=hour, anyone_home=False, weekday=weekday),
    ]


def _activity_snapshot(
    *,
    hour: int,
    activities: tuple[str, ...] = (),
    anyone_home: bool = True,
) -> HouseSnapshot:
    return _snapshot(
        ts=f"2026-05-18T{hour:02d}:00:00+02:00",
        weekday=0,
        minute_of_day=hour * 60,
        anyone_home=anyone_home,
        room_occupancy={"living": True} if anyone_home else {},
        detected_activities=activities,
        heating_current_temperature=21.0,
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


async def test_anomaly_analyzer_arrival_time_outlier_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_transition_pair(hour=18, arrival=True))
    snapshots.extend(_presence_transition_pair(hour=23, arrival=True))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    arrival_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "arrival_time_outlier"
    ]
    assert len(arrival_findings) == 1
    assert arrival_findings[0].payload.context["baseline_transition_count"] == 5
    assert arrival_findings[0].payload.context["current_hour_bucket"] == 23


async def test_anomaly_analyzer_arrival_time_outlier_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(4):
        snapshots.extend(_presence_transition_pair(hour=18, arrival=True))
    snapshots.extend(_presence_transition_pair(hour=23, arrival=True))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "arrival_time_outlier"
    ]


async def test_anomaly_analyzer_arrival_time_outlier_ignores_normal_time() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(6):
        snapshots.extend(_presence_transition_pair(hour=18, arrival=True))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "arrival_time_outlier"
    ]


async def test_anomaly_analyzer_arrival_time_outlier_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "arrival_time_outlier": {
                        "thresholds": {
                            "delta_hours": 8.0,
                        }
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_transition_pair(hour=18, arrival=True))
    snapshots.extend(_presence_transition_pair(hour=23, arrival=True))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "arrival_time_outlier"
    ]


async def test_anomaly_analyzer_arrival_time_outlier_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "arrival_time_outlier": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_transition_pair(hour=18, arrival=True))
    snapshots.extend(_presence_transition_pair(hour=23, arrival=True))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "arrival_time_outlier"
    ]


async def test_anomaly_analyzer_departure_time_outlier_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_transition_pair(hour=8, arrival=False))
    snapshots.extend(_presence_transition_pair(hour=14, arrival=False))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    departure_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "departure_time_outlier"
    ]
    assert len(departure_findings) == 1
    assert departure_findings[0].payload.context["baseline_transition_count"] == 5
    assert departure_findings[0].payload.context["current_hour_bucket"] == 14


async def test_anomaly_analyzer_departure_time_outlier_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(4):
        snapshots.extend(_presence_transition_pair(hour=8, arrival=False))
    snapshots.extend(_presence_transition_pair(hour=14, arrival=False))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "departure_time_outlier"
    ]


async def test_anomaly_analyzer_departure_time_outlier_ignores_normal_time() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(6):
        snapshots.extend(_presence_transition_pair(hour=8, arrival=False))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "departure_time_outlier"
    ]


async def test_anomaly_analyzer_departure_time_outlier_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "departure_time_outlier": {
                        "thresholds": {
                            "delta_hours": 8.0,
                        }
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_transition_pair(hour=8, arrival=False))
    snapshots.extend(_presence_transition_pair(hour=14, arrival=False))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "departure_time_outlier"
    ]


async def test_anomaly_analyzer_departure_time_outlier_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "departure_time_outlier": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_transition_pair(hour=8, arrival=False))
    snapshots.extend(_presence_transition_pair(hour=14, arrival=False))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "departure_time_outlier"
    ]


async def test_anomaly_analyzer_extended_absence_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(2))
        snapshots.append(_presence_snapshot(hour=10, anyone_home=True))
    snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(6))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    absence_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "extended_absence"
    ]
    assert len(absence_findings) == 1
    assert absence_findings[0].payload.context["current_run"] == 6
    assert absence_findings[0].payload.context["percentile_90_run"] == 2


async def test_anomaly_analyzer_extended_absence_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(4):
        snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(2))
        snapshots.append(_presence_snapshot(hour=10, anyone_home=True))
    snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(6))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "extended_absence"
    ]


async def test_anomaly_analyzer_extended_absence_ignores_short_current_run() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(3))
        snapshots.append(_presence_snapshot(hour=10, anyone_home=True))
    snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(3))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "extended_absence"
    ]


async def test_anomaly_analyzer_extended_absence_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "extended_absence": {
                        "thresholds": {
                            "multiplier": 4.0,
                        }
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(2))
        snapshots.append(_presence_snapshot(hour=10, anyone_home=True))
    snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(6))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "extended_absence"
    ]


async def test_anomaly_analyzer_extended_absence_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "extended_absence": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(2))
        snapshots.append(_presence_snapshot(hour=10, anyone_home=True))
    snapshots.extend(_presence_snapshot(hour=10, anyone_home=False) for _ in range(6))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "extended_absence"
    ]


async def test_anomaly_analyzer_presence_pattern_drift_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_presence_snapshot(hour=20, anyone_home=True) for _ in range(10)]
    snapshots.extend(_presence_snapshot(hour=20, anyone_home=False) for _ in range(4))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    drift_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "presence_pattern_drift"
    ]
    assert len(drift_findings) == 1
    assert drift_findings[0].payload.context["baseline_snapshot_count"] == 10
    assert drift_findings[0].payload.context["recent_snapshot_count"] == 4
    assert drift_findings[0].payload.context["observed_drift"] == 1.0


async def test_anomaly_analyzer_presence_pattern_drift_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_presence_snapshot(hour=20, anyone_home=True) for _ in range(9)]
    snapshots.extend(_presence_snapshot(hour=20, anyone_home=False) for _ in range(4))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "presence_pattern_drift"
    ]


async def test_anomaly_analyzer_presence_pattern_drift_ignores_stable_pattern() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_presence_snapshot(hour=20, anyone_home=True) for _ in range(14)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "presence_pattern_drift"
    ]


async def test_anomaly_analyzer_presence_pattern_drift_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "presence_pattern_drift": {
                        "thresholds": {
                            "drift_delta": 1.1,
                        }
                    }
                }
            }
        }
    )
    snapshots = [_presence_snapshot(hour=20, anyone_home=True) for _ in range(10)]
    snapshots.extend(_presence_snapshot(hour=20, anyone_home=False) for _ in range(4))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "presence_pattern_drift"
    ]


async def test_anomaly_analyzer_presence_pattern_drift_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "presence_pattern_drift": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots = [_presence_snapshot(hour=20, anyone_home=True) for _ in range(10)]
    snapshots.extend(_presence_snapshot(hour=20, anyone_home=False) for _ in range(4))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "presence_pattern_drift"
    ]


async def test_anomaly_analyzer_stove_on_unattended_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_activity_snapshot(hour=12, anyone_home=True) for _ in range(4)]
    snapshots.extend(
        _activity_snapshot(hour=12, activities=("stove_on",), anyone_home=False)
        for _ in range(2)
    )

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    stove_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "stove_on_unattended"
    ]
    assert len(stove_findings) == 1
    assert stove_findings[0].payload.severity == "critical"
    assert stove_findings[0].payload.context["unattended_observation_count"] == 2


async def test_anomaly_analyzer_stove_on_unattended_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _activity_snapshot(hour=12, activities=("stove_on",), anyone_home=False),
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "stove_on_unattended"
    ]


async def test_anomaly_analyzer_stove_on_unattended_ignores_attended_activity() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _activity_snapshot(hour=12, activities=("stove_on",), anyone_home=True)
        for _ in range(2)
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "stove_on_unattended"
    ]


async def test_anomaly_analyzer_stove_on_unattended_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "stove_on_unattended": {
                        "thresholds": {
                            "min_observations": 3,
                        }
                    }
                }
            }
        }
    )
    snapshots = [
        _activity_snapshot(hour=12, activities=("stove_on",), anyone_home=False)
        for _ in range(2)
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "stove_on_unattended"
    ]


async def test_anomaly_analyzer_stove_on_unattended_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "stove_on_unattended": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots = [
        _activity_snapshot(hour=12, activities=("stove_on",), anyone_home=False)
        for _ in range(2)
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "stove_on_unattended"
    ]


async def test_anomaly_analyzer_oven_on_unattended_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_activity_snapshot(hour=18, anyone_home=True) for _ in range(4)]
    snapshots.extend(
        _activity_snapshot(hour=18, activities=("oven_on",), anyone_home=False)
        for _ in range(2)
    )

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    oven_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "oven_on_unattended"
    ]
    assert len(oven_findings) == 1
    assert oven_findings[0].payload.severity == "critical"
    assert oven_findings[0].payload.context["unattended_observation_count"] == 2


async def test_anomaly_analyzer_oven_on_unattended_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _activity_snapshot(hour=18, activities=("oven_on",), anyone_home=False),
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "oven_on_unattended"
    ]


async def test_anomaly_analyzer_oven_on_unattended_ignores_attended_activity() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _activity_snapshot(hour=18, activities=("oven_on",), anyone_home=True)
        for _ in range(2)
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "oven_on_unattended"
    ]


async def test_anomaly_analyzer_oven_on_unattended_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "oven_on_unattended": {
                        "thresholds": {
                            "min_observations": 3,
                        }
                    }
                }
            }
        }
    )
    snapshots = [
        _activity_snapshot(hour=18, activities=("oven_on",), anyone_home=False)
        for _ in range(2)
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "oven_on_unattended"
    ]


async def test_anomaly_analyzer_oven_on_unattended_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "oven_on_unattended": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots = [
        _activity_snapshot(hour=18, activities=("oven_on",), anyone_home=False)
        for _ in range(2)
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "oven_on_unattended"
    ]


async def test_anomaly_analyzer_appliance_unusual_hour_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _activity_snapshot(hour=8, activities=("dishwasher_running",))
        for _ in range(7)
    ]
    snapshots.append(_activity_snapshot(hour=20, activities=("dishwasher_running",)))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    appliance_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "appliance_unusual_hour"
    ]
    assert len(appliance_findings) == 1
    assert appliance_findings[0].payload.context["activity_name"] == "dishwasher_running"
    assert appliance_findings[0].payload.context["current_hour"] == 20
    assert appliance_findings[0].payload.context["observation_count"] == 8


async def test_anomaly_analyzer_appliance_unusual_hour_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _activity_snapshot(hour=8, activities=("washing_machine_running",))
        for _ in range(6)
    ]
    snapshots.append(_activity_snapshot(hour=20, activities=("washing_machine_running",)))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "appliance_unusual_hour"
    ]


async def test_anomaly_analyzer_appliance_unusual_hour_ignores_normal_hour() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _activity_snapshot(hour=8, activities=("washing_machine_running",))
        for _ in range(7)
    ]
    snapshots.append(_activity_snapshot(hour=10, activities=("washing_machine_running",)))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "appliance_unusual_hour"
    ]


async def test_anomaly_analyzer_appliance_unusual_hour_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "appliance_unusual_hour": {
                        "thresholds": {
                            "delta_hours": 20.0,
                        }
                    }
                }
            }
        }
    )
    snapshots = [
        _activity_snapshot(hour=8, activities=("tv_active",))
        for _ in range(7)
    ]
    snapshots.append(_activity_snapshot(hour=20, activities=("tv_active",)))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "appliance_unusual_hour"
    ]


async def test_anomaly_analyzer_appliance_unusual_hour_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "appliance_unusual_hour": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots = [_activity_snapshot(hour=8, activities=("pc_active",)) for _ in range(7)]
    snapshots.append(_activity_snapshot(hour=20, activities=("pc_active",)))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "appliance_unusual_hour"
    ]


async def test_anomaly_analyzer_heating_setpoint_outlier_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_snapshot(heating_setpoint=19.0) for _ in range(8)]
    snapshots.append(_snapshot(heating_setpoint=23.0))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert [finding.payload.anomaly_type for finding in findings] == [
        "heating_setpoint_outlier"
    ]
    assert findings[0].payload.context["baseline_setpoint_c"] == 19.0
    assert findings[0].payload.context["current_setpoint_c"] == 23.0
    assert findings[0].payload.context["window"] == 24


async def test_anomaly_analyzer_heating_setpoint_outlier_respects_support() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_snapshot(heating_setpoint=19.0) for _ in range(7)]
    snapshots.append(_snapshot(heating_setpoint=23.0))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "heating_setpoint_outlier"
    ]


async def test_anomaly_analyzer_heating_setpoint_outlier_applies_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "heating_setpoint_outlier": {
                        "thresholds": {
                            "delta_c": 5.0,
                        }
                    }
                }
            }
        }
    )
    snapshots = [_snapshot(heating_setpoint=19.0) for _ in range(8)]
    snapshots.append(_snapshot(heating_setpoint=23.0))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "heating_setpoint_outlier"
    ]


async def test_anomaly_analyzer_heating_vacation_mismatch_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _snapshot(heating_setpoint=21.0, security_state="disarmed"),
        _snapshot(heating_setpoint=19.0, security_state="armed_away"),
        _snapshot(heating_setpoint=19.5, security_state="armed_away"),
        _snapshot(heating_setpoint=20.0, security_state="armed_away"),
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    vacation_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "heating_vacation_mismatch"
    ]
    assert len(vacation_findings) == 1
    assert vacation_findings[0].payload.context["armed_away_snapshot_count"] == 3
    assert vacation_findings[0].payload.context["max_away_setpoint_c"] == 18.0


async def test_anomaly_analyzer_heating_vacation_mismatch_filters_fixed_window() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _snapshot(heating_setpoint=19.0, security_state="armed_away"),
        _snapshot(heating_setpoint=19.0, security_state="armed_away"),
        _snapshot(heating_setpoint=19.0, security_state="armed_away"),
    ]
    snapshots.extend(_snapshot(heating_setpoint=21.0, security_state="disarmed") for _ in range(6))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "heating_vacation_mismatch"
    ]


async def test_anomaly_analyzer_heating_vacation_mismatch_uses_strict_threshold() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _snapshot(heating_setpoint=18.0, security_state="armed_away"),
        _snapshot(heating_setpoint=18.5, security_state="armed_away"),
        _snapshot(heating_setpoint=19.0, security_state="armed_away"),
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "heating_vacation_mismatch"
    ]


async def test_anomaly_analyzer_alarm_disarm_unusual_hour_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(5):
        snapshots.append(_snapshot(security_state="armed_away", minute_of_day=6 * 60))
        snapshots.append(_snapshot(security_state="disarmed", minute_of_day=7 * 60))
    snapshots.append(_snapshot(security_state="armed_away", minute_of_day=1 * 60))
    snapshots.append(_snapshot(security_state="disarmed", minute_of_day=2 * 60))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    alarm_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "alarm_disarm_unusual_hour"
    ]
    assert len(alarm_findings) == 1
    assert alarm_findings[0].payload.context["baseline_transition_count"] == 5
    assert alarm_findings[0].payload.context["current_hour_bucket"] == 2


async def test_anomaly_analyzer_alarm_disarm_unusual_hour_scans_transitions() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _snapshot(security_state="disarmed", minute_of_day=2 * 60),
        _snapshot(security_state="disarmed", minute_of_day=2 * 60),
        _snapshot(security_state="disarmed", minute_of_day=2 * 60),
        _snapshot(security_state="disarmed", minute_of_day=2 * 60),
        _snapshot(security_state="disarmed", minute_of_day=2 * 60),
        _snapshot(security_state="disarmed", minute_of_day=2 * 60),
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "alarm_disarm_unusual_hour"
    ]


async def test_anomaly_analyzer_alarm_expected_not_armed_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _snapshot(weekday=1, minute_of_day=23 * 60, security_state="armed_night")
        for _ in range(8)
    ]
    snapshots.extend(
        _snapshot(weekday=1, minute_of_day=23 * 60, security_state="disarmed")
        for _ in range(2)
    )

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    expected_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "alarm_expected_not_armed"
    ]
    assert len(expected_findings) == 1
    assert expected_findings[0].payload.context["baseline_snapshot_count"] == 8
    assert expected_findings[0].payload.context["recent_disarmed_observations"] == 2
    assert expected_findings[0].payload.context["hour_bucket"] == 23


async def test_anomaly_analyzer_alarm_expected_not_armed_filters_current_slot() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [
        _snapshot(weekday=1, minute_of_day=22 * 60, security_state="armed_night")
        for _ in range(8)
    ]
    snapshots.extend(
        _snapshot(weekday=1, minute_of_day=23 * 60, security_state="disarmed")
        for _ in range(2)
    )

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "alarm_expected_not_armed"
    ]


async def test_anomaly_analyzer_sensor_activity_drop_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    recent_time = datetime(2026, 5, 5, 20, 0, tzinfo=UTC)
    baseline_start = recent_time - timedelta(hours=12)
    baseline = [
        _timed_snapshot(baseline_start + timedelta(minutes=minute), weekday=1, hour=20)
        for minute in range(0, 200, 10)
    ]
    snapshots = [
        *baseline,
        _timed_snapshot(recent_time, weekday=1, hour=20),
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    drop_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "sensor_activity_drop"
    ]
    assert len(drop_findings) == 1
    assert drop_findings[0].payload.context["baseline_snapshot_count"] == 20
    assert drop_findings[0].payload.context["recent_snapshot_count"] == 1
    assert drop_findings[0].payload.context["window_hours"] == 4.0


async def test_anomaly_analyzer_sensor_activity_drop_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    recent_time = datetime(2026, 5, 5, 20, 0, tzinfo=UTC)
    baseline_start = recent_time - timedelta(hours=12)
    baseline = [
        _timed_snapshot(baseline_start + timedelta(minutes=minute), weekday=1, hour=20)
        for minute in range(0, 90, 10)
    ]
    snapshots = [*baseline, _timed_snapshot(recent_time, weekday=1, hour=20)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "sensor_activity_drop"
    ]


async def test_anomaly_analyzer_sensor_activity_drop_ignores_normal_activity() -> None:
    analyzer = AnomalyAnalyzer()
    recent_time = datetime(2026, 5, 5, 20, 0, tzinfo=UTC)
    baseline_start = recent_time - timedelta(hours=12)
    baseline = [
        _timed_snapshot(baseline_start + timedelta(minutes=minute), weekday=1, hour=20)
        for minute in range(0, 200, 10)
    ]
    recent = [
        _timed_snapshot(recent_time + timedelta(minutes=minute), weekday=1, hour=20)
        for minute in range(0, 240, 10)
    ]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore([*baseline, *recent]))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "sensor_activity_drop"
    ]


async def test_anomaly_analyzer_sensor_activity_drop_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "sensor_activity_drop": {
                        "thresholds": {
                            "drop_ratio": 0.03,
                        }
                    }
                }
            }
        }
    )
    recent_time = datetime(2026, 5, 5, 20, 0, tzinfo=UTC)
    baseline_start = recent_time - timedelta(hours=12)
    baseline = [
        _timed_snapshot(baseline_start + timedelta(minutes=minute), weekday=1, hour=20)
        for minute in range(0, 200, 10)
    ]
    snapshots = [*baseline, _timed_snapshot(recent_time, weekday=1, hour=20)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "sensor_activity_drop"
    ]


async def test_anomaly_analyzer_sensor_activity_drop_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "sensor_activity_drop": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    recent_time = datetime(2026, 5, 5, 20, 0, tzinfo=UTC)
    baseline_start = recent_time - timedelta(hours=12)
    snapshots = [
        _timed_snapshot(baseline_start + timedelta(minutes=minute), weekday=1, hour=20)
        for minute in range(0, 200, 10)
    ]
    snapshots.append(_timed_snapshot(recent_time, weekday=1, hour=20))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "sensor_activity_drop"
    ]


async def test_anomaly_analyzer_ghost_activity_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_snapshot(anyone_home=True) for _ in range(17)]
    snapshots.extend(
        _snapshot(anyone_home=False, room_occupancy={"living": True})
        for _ in range(3)
    )

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    ghost_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "ghost_activity"
    ]
    assert len(ghost_findings) == 1
    assert ghost_findings[0].payload.context["ghost_observation_count"] == 3


async def test_anomaly_analyzer_ghost_activity_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_snapshot(anyone_home=False, room_occupancy={"living": True}) for _ in range(2)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "ghost_activity"
    ]


async def test_anomaly_analyzer_ghost_activity_ignores_normal_occupancy() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_snapshot(anyone_home=True, room_occupancy={"living": True}) for _ in range(20)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "ghost_activity"
    ]


async def test_anomaly_analyzer_ghost_activity_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "ghost_activity": {
                        "thresholds": {
                            "min_ghost_observations": 4,
                        }
                    }
                }
            }
        }
    )
    snapshots = [_snapshot(anyone_home=False, room_occupancy={"living": True}) for _ in range(3)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "ghost_activity"
    ]


async def test_anomaly_analyzer_ghost_activity_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "ghost_activity": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots = [_snapshot(anyone_home=False, room_occupancy={"living": True}) for _ in range(3)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "ghost_activity"
    ]


async def test_anomaly_analyzer_unusual_stillness_emits_finding() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(10):
        snapshots.extend(_snapshot(room_occupancy={"living": True}) for _ in range(2))
        snapshots.append(_snapshot(room_occupancy={"studio": True}))
    snapshots.extend(_snapshot(room_occupancy={"living": True}) for _ in range(8))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    stillness_findings = [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "unusual_stillness"
    ]
    assert len(stillness_findings) == 1
    assert stillness_findings[0].payload.context["current_run"] == 7
    assert stillness_findings[0].payload.context["percentile_90_run"] == 1


async def test_anomaly_analyzer_unusual_stillness_respects_min_observations() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots = [_snapshot(room_occupancy={"living": True}) for _ in range(8)]

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "unusual_stillness"
    ]


async def test_anomaly_analyzer_unusual_stillness_ignores_short_current_run() -> None:
    analyzer = AnomalyAnalyzer()
    snapshots: list[HouseSnapshot] = []
    for _ in range(10):
        snapshots.extend(_snapshot(room_occupancy={"living": True}) for _ in range(3))
        snapshots.append(_snapshot(room_occupancy={"studio": True}))
    snapshots.extend(_snapshot(room_occupancy={"living": True}) for _ in range(3))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "unusual_stillness"
    ]


async def test_anomaly_analyzer_unusual_stillness_threshold_override() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "unusual_stillness": {
                        "thresholds": {
                            "multiplier": 10.0,
                        }
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(10):
        snapshots.append(_snapshot(room_occupancy={"living": True}))
        snapshots.append(_snapshot(room_occupancy={"studio": True}))
    snapshots.extend(_snapshot(room_occupancy={"living": True}) for _ in range(8))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "unusual_stillness"
    ]


async def test_anomaly_analyzer_unusual_stillness_disabled_rule() -> None:
    analyzer = AnomalyAnalyzer(
        options_provider=lambda: {
            "anomaly": {
                "rules": {
                    "unusual_stillness": {
                        "enabled": False,
                    }
                }
            }
        }
    )
    snapshots: list[HouseSnapshot] = []
    for _ in range(10):
        snapshots.append(_snapshot(room_occupancy={"living": True}))
        snapshots.append(_snapshot(room_occupancy={"studio": True}))
    snapshots.extend(_snapshot(room_occupancy={"living": True}) for _ in range(8))

    findings = await analyzer.analyze(_FakeEventStore(), _FakeSnapshotStore(snapshots))  # type: ignore[arg-type]

    assert not [
        finding
        for finding in findings
        if finding.payload.anomaly_type == "unusual_stillness"
    ]


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
