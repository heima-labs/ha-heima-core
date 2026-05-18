"""Built-in statistical anomaly analyzer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from ..event_store import EventStore
from ..plugin_contracts import AnomalySignal, BehaviorFinding

_ANOMALY_RULE_IDS = (
    "arrival_time_outlier",
    "departure_time_outlier",
    "extended_absence",
    "presence_pattern_drift",
    "heating_setpoint_outlier",
    "heating_unresponsive",
    "heating_vacation_mismatch",
    "stove_on_unattended",
    "oven_on_unattended",
    "appliance_unusual_hour",
    "lights_on_unattended",
    "lighting_scene_drift",
    "alarm_disarm_unusual_hour",
    "alarm_expected_not_armed",
    "sensor_activity_drop",
    "ghost_activity",
    "unusual_stillness",
)


@dataclass(frozen=True)
class AnomalyRule:
    """Effective anomaly rule configuration."""

    rule_id: str
    enabled: bool = True
    severity: str = "warning"
    thresholds: dict[str, Any] = field(default_factory=dict)


class AnomalyAnalyzer:
    """Analyze persisted snapshots for statistical anomalies."""

    def __init__(self, *, options_provider: Callable[[], dict[str, Any]] | None = None) -> None:
        self._options_provider = options_provider or (lambda: {})
        self._last_diagnostics: dict[str, Any] = {
            "analyzer_id": self.analyzer_id,
            "enabled": True,
            "rules": {},
            "last_findings": 0,
        }

    @property
    def analyzer_id(self) -> str:
        return "anomaly"

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: Any | None = None,
    ) -> list[BehaviorFinding]:
        del event_store
        options = self._options_provider()
        anomaly_cfg = _safe_dict(options.get("anomaly"))
        enabled = bool(anomaly_cfg.get("enabled", anomaly_cfg.get("anomaly_enabled", True)))
        rules = _effective_rules(anomaly_cfg)
        findings: list[BehaviorFinding] = []
        if enabled and snapshot_store is not None:
            findings.extend(self._evaluate_heating_unresponsive(snapshot_store, rules))
        self._last_diagnostics = {
            "analyzer_id": self.analyzer_id,
            "enabled": enabled,
            "rules": {rule_id: _rule_diag(rule) for rule_id, rule in rules.items()},
            "last_findings": len(findings),
        }
        return findings

    def diagnostics(self) -> dict[str, Any]:
        """Return analyzer diagnostics."""
        return dict(self._last_diagnostics)

    def _evaluate_heating_unresponsive(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["heating_unresponsive"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 4)
        min_gap_c = _threshold_float(rule, "min_gap_c", 1.5)
        min_delta_c = _threshold_float(rule, "min_delta_c", 0.2)
        window = max(min_observations, _threshold_int(rule, "window", min_observations))
        snapshots = [
            snapshot
            for snapshot in snapshot_store.snapshots(limit=window)
            if getattr(snapshot, "heating_setpoint", None) is not None
            and getattr(snapshot, "heating_current_temperature", None) is not None
        ]
        if len(snapshots) < min_observations:
            return []

        gaps = [
            float(snapshot.heating_setpoint) - float(snapshot.heating_current_temperature)
            for snapshot in snapshots
        ]
        if not gaps or min(gaps) < min_gap_c:
            return []

        temperature_delta = float(snapshots[-1].heating_current_temperature) - float(
            snapshots[0].heating_current_temperature
        )
        if temperature_delta >= min_delta_c:
            return []

        avg_gap = sum(gaps) / len(gaps)
        confidence = min(1.0, (avg_gap / max(min_gap_c * 2, 0.1)))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Heating appears unresponsive: current temperature stayed below setpoint "
                f"by at least {min_gap_c:.1f}C across {len(snapshots)} snapshots."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "snapshot_count": len(snapshots),
                "avg_gap_c": round(avg_gap, 3),
                "temperature_delta_c": round(temperature_delta, 3),
                "min_gap_c": min_gap_c,
                "min_delta_c": min_delta_c,
            },
        )
        return [
            BehaviorFinding(
                kind="anomaly",
                analyzer_id=self.analyzer_id,
                description=signal.description,
                confidence=signal.confidence,
                payload=signal,
            )
        ]


def _effective_rules(anomaly_cfg: dict[str, Any]) -> dict[str, AnomalyRule]:
    raw_rules = _safe_dict(anomaly_cfg.get("rules"))
    return {
        rule_id: _effective_rule(rule_id, _safe_dict(raw_rules.get(rule_id)))
        for rule_id in _ANOMALY_RULE_IDS
    }


def _effective_rule(rule_id: str, raw: dict[str, Any]) -> AnomalyRule:
    default = _default_rule(rule_id)
    thresholds = dict(default.thresholds)
    thresholds.update(_safe_dict(raw.get("thresholds")))
    return AnomalyRule(
        rule_id=rule_id,
        enabled=bool(raw.get("enabled", default.enabled)),
        severity=str(raw.get("severity") or default.severity),
        thresholds=thresholds,
    )


def _default_rule(rule_id: str) -> AnomalyRule:
    thresholds: dict[str, Any] = {}
    if rule_id == "heating_unresponsive":
        thresholds = {
            "window": 4,
            "min_observations": 4,
            "min_gap_c": 1.5,
            "min_delta_c": 0.2,
        }
    return AnomalyRule(rule_id=rule_id, enabled=True, severity="warning", thresholds=thresholds)


def _rule_diag(rule: AnomalyRule) -> dict[str, Any]:
    return {
        "enabled": rule.enabled,
        "severity": rule.severity,
        "thresholds": dict(rule.thresholds),
    }


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _threshold_int(rule: AnomalyRule, key: str, default: int) -> int:
    try:
        return max(1, int(rule.thresholds.get(key, default)))
    except (TypeError, ValueError):
        return default


def _threshold_float(rule: AnomalyRule, key: str, default: float) -> float:
    try:
        return float(rule.thresholds.get(key, default))
    except (TypeError, ValueError):
        return default


def _severity(value: str) -> Literal["info", "warning", "critical"]:
    if value == "info":
        return "info"
    if value == "critical":
        return "critical"
    return "warning"
