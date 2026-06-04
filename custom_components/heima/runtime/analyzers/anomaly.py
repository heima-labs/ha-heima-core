"""Built-in statistical anomaly analyzer."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
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
    "learned_model_stale",
)

_APPLIANCE_UNUSUAL_HOUR_ACTIVITIES = frozenset(
    {
        "washing_machine_running",
        "dishwasher_running",
        "tv_active",
        "pc_active",
    }
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

    def __init__(
        self,
        *,
        options_provider: Callable[[], dict[str, Any]] | None = None,
        inference_diagnostics_provider: Callable[[], dict[str, Any]] | None = None,
    ) -> None:
        self._options_provider = options_provider or (lambda: {})
        self._inference_diagnostics_provider = inference_diagnostics_provider or (lambda: {})
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
            findings.extend(self._evaluate_arrival_time_outlier(snapshot_store, rules))
            findings.extend(self._evaluate_departure_time_outlier(snapshot_store, rules))
            findings.extend(self._evaluate_extended_absence(snapshot_store, rules))
            findings.extend(self._evaluate_presence_pattern_drift(snapshot_store, rules))
            findings.extend(self._evaluate_heating_setpoint_outlier(snapshot_store, rules))
            findings.extend(self._evaluate_heating_unresponsive(snapshot_store, rules))
            findings.extend(self._evaluate_heating_vacation_mismatch(snapshot_store, rules))
            findings.extend(self._evaluate_stove_on_unattended(snapshot_store, rules))
            findings.extend(self._evaluate_oven_on_unattended(snapshot_store, rules))
            findings.extend(self._evaluate_appliance_unusual_hour(snapshot_store, rules))
            findings.extend(self._evaluate_lights_on_unattended(snapshot_store, rules))
            findings.extend(self._evaluate_lighting_scene_drift(snapshot_store, rules))
            findings.extend(self._evaluate_alarm_disarm_unusual_hour(snapshot_store, rules))
            findings.extend(self._evaluate_alarm_expected_not_armed(snapshot_store, rules))
            findings.extend(self._evaluate_sensor_activity_drop(snapshot_store, rules))
            findings.extend(self._evaluate_ghost_activity(snapshot_store, rules))
            findings.extend(self._evaluate_unusual_stillness(snapshot_store, rules))
            findings.extend(self._evaluate_learned_model_stale(snapshot_store, rules))
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

    def _evaluate_arrival_time_outlier(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["arrival_time_outlier"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 5)
        delta_hours = _threshold_float(rule, "delta_hours", 3.0)
        window = max(min_observations + 1, _threshold_int(rule, "window", 1000))
        snapshots = snapshot_store.snapshots(limit=window)
        transitions = _presence_transitions(snapshots, previous_home=False, current_home=True)
        if not transitions:
            return []
        current = transitions[-1]
        same_weekday = [
            transition for transition in transitions if transition.weekday == current.weekday
        ]
        if len(same_weekday) < min_observations + 1:
            return []

        baseline = [transition.hour_bucket for transition in same_weekday[:-1]]
        baseline_hour = _clock_median_hour([float(hour) for hour in baseline])
        distance = _clock_distance_hours(float(current.hour_bucket), baseline_hour)
        if distance < delta_hours:
            return []

        confidence = min(1.0, distance / max(delta_hours * 2, 0.1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Arrival happened at an unusual hour: "
                f"{_hour_bucket_label(current.hour_bucket)} differs from historical median "
                f"{_hour_bucket_label(baseline_hour)}."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "weekday": current.weekday,
                "transition_count": len(same_weekday),
                "baseline_transition_count": len(baseline),
                "current_hour_bucket": current.hour_bucket,
                "baseline_hour_bucket": round(baseline_hour, 3),
                "distance_hours": round(distance, 3),
                "delta_hours": delta_hours,
                "window": window,
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_departure_time_outlier(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["departure_time_outlier"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 5)
        delta_hours = _threshold_float(rule, "delta_hours", 3.0)
        window = max(min_observations + 1, _threshold_int(rule, "window", 1000))
        snapshots = snapshot_store.snapshots(limit=window)
        transitions = _presence_transitions(snapshots, previous_home=True, current_home=False)
        if not transitions:
            return []
        current = transitions[-1]
        same_weekday = [
            transition for transition in transitions if transition.weekday == current.weekday
        ]
        if len(same_weekday) < min_observations + 1:
            return []

        baseline = [transition.hour_bucket for transition in same_weekday[:-1]]
        baseline_hour = _clock_median_hour([float(hour) for hour in baseline])
        distance = _clock_distance_hours(float(current.hour_bucket), baseline_hour)
        if distance < delta_hours:
            return []

        confidence = min(1.0, distance / max(delta_hours * 2, 0.1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Departure happened at an unusual hour: "
                f"{_hour_bucket_label(current.hour_bucket)} differs from historical median "
                f"{_hour_bucket_label(baseline_hour)}."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "weekday": current.weekday,
                "transition_count": len(same_weekday),
                "baseline_transition_count": len(baseline),
                "current_hour_bucket": current.hour_bucket,
                "baseline_hour_bucket": round(baseline_hour, 3),
                "distance_hours": round(distance, 3),
                "delta_hours": delta_hours,
                "window": window,
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_extended_absence(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["extended_absence"]
        if not rule.enabled:
            return []
        history_window = _threshold_int(rule, "history_window", 1000)
        min_observations = _threshold_int(rule, "min_observations", 5)
        multiplier = _threshold_float(rule, "multiplier", 2.0)
        snapshots = snapshot_store.snapshots(limit=max(history_window, min_observations + 1))
        current_run = _current_absence_run_length(snapshots)
        if current_run <= 0:
            return []

        baseline_snapshots = snapshots[: len(snapshots) - current_run]
        run_lengths = _absence_run_lengths(baseline_snapshots)
        if len(run_lengths) < min_observations:
            return []

        percentile_90 = _percentile_nearest_rank(run_lengths, 0.9)
        threshold = percentile_90 * multiplier
        if current_run <= threshold:
            return []

        confidence = min(1.0, current_run / max(threshold * 2, 1.0))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Current absence is unusually long: "
                f"{current_run} snapshots away vs historical 90th percentile {percentile_90}."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "history_window": history_window,
                "min_observations": min_observations,
                "multiplier": multiplier,
                "current_run": current_run,
                "baseline_run_count": len(run_lengths),
                "percentile_90_run": percentile_90,
                "threshold_run": round(threshold, 3),
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_presence_pattern_drift(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["presence_pattern_drift"]
        if not rule.enabled:
            return []
        history_window = _threshold_int(rule, "history_window", 1000)
        min_observations = _threshold_int(rule, "min_observations", 10)
        recent_observations = _threshold_int(rule, "recent_observations", 4)
        drift_delta = _threshold_float(rule, "drift_delta", 0.5)
        snapshots = snapshot_store.snapshots(
            limit=max(history_window, min_observations + recent_observations)
        )
        if not snapshots:
            return []

        current_slot = _snapshot_slot(snapshots[-1])
        slot_snapshots = [
            snapshot for snapshot in snapshots if _snapshot_slot(snapshot) == current_slot
        ]
        if len(slot_snapshots) < min_observations + recent_observations:
            return []

        recent = slot_snapshots[-recent_observations:]
        baseline = slot_snapshots[:-recent_observations]
        if len(baseline) < min_observations:
            return []

        baseline_ratio = _home_ratio(baseline)
        recent_ratio = _home_ratio(recent)
        drift = abs(recent_ratio - baseline_ratio)
        if drift < drift_delta:
            return []

        confidence = min(1.0, drift)
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Presence pattern drifted for the current time slot: "
                f"recent home ratio {recent_ratio:.2f} vs baseline {baseline_ratio:.2f}."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "weekday": current_slot[0],
                "hour_bucket": current_slot[1],
                "history_window": history_window,
                "min_observations": min_observations,
                "recent_observations": recent_observations,
                "drift_delta": drift_delta,
                "baseline_snapshot_count": len(baseline),
                "recent_snapshot_count": len(recent),
                "baseline_home_ratio": round(baseline_ratio, 3),
                "recent_home_ratio": round(recent_ratio, 3),
                "observed_drift": round(drift, 3),
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_heating_setpoint_outlier(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["heating_setpoint_outlier"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 8)
        delta_c = _threshold_float(rule, "delta_c", 3.0)
        window = max(min_observations + 1, _threshold_int(rule, "window", 24))
        snapshots = [
            snapshot
            for snapshot in snapshot_store.snapshots(limit=window)
            if getattr(snapshot, "heating_setpoint", None) is not None
        ]
        if len(snapshots) < min_observations + 1:
            return []

        previous = [float(snapshot.heating_setpoint) for snapshot in snapshots[:-1]]
        current = float(snapshots[-1].heating_setpoint)
        baseline = _median(previous)
        deviation = abs(current - baseline)
        if deviation < delta_c:
            return []

        confidence = min(1.0, deviation / max(delta_c * 2, 0.1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Heating setpoint is unusual: current setpoint "
                f"{current:.1f}C differs from recent median {baseline:.1f}C."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "snapshot_count": len(snapshots),
                "baseline_setpoint_c": round(baseline, 3),
                "current_setpoint_c": round(current, 3),
                "deviation_c": round(deviation, 3),
                "delta_c": delta_c,
                "window": window,
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_stove_on_unattended(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        return self._evaluate_activity_unattended(
            snapshot_store,
            rules,
            rule_id="stove_on_unattended",
            activity_name="stove_on",
            label="Stove",
        )

    def _evaluate_oven_on_unattended(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        return self._evaluate_activity_unattended(
            snapshot_store,
            rules,
            rule_id="oven_on_unattended",
            activity_name="oven_on",
            label="Oven",
        )

    def _evaluate_activity_unattended(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
        *,
        rule_id: str,
        activity_name: str,
        label: str,
    ) -> list[BehaviorFinding]:
        rule = rules[rule_id]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 2)
        window = max(min_observations, _threshold_int(rule, "window", 6))
        snapshots = snapshot_store.snapshots(limit=window)
        unattended = [
            snapshot
            for snapshot in snapshots
            if activity_name in _activity_set(snapshot)
            and not bool(getattr(snapshot, "anyone_home", False))
        ]
        if len(unattended) < min_observations:
            return []

        confidence = min(1.0, len(unattended) / max(min_observations * 2, 1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                f"{label} activity was detected while nobody was home "
                f"in {len(unattended)} recent snapshots."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "activity_name": activity_name,
                "window": window,
                "min_observations": min_observations,
                "unattended_observation_count": len(unattended),
                "snapshot_count": len(snapshots),
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_appliance_unusual_hour(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["appliance_unusual_hour"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 8)
        delta_hours = _threshold_float(rule, "delta_hours", 4.0)
        window = max(min_observations, _threshold_int(rule, "window", 1000))
        snapshots = snapshot_store.snapshots(limit=window)
        if not snapshots:
            return []

        current_hour = _snapshot_encoded_hour(snapshots[-1])
        if current_hour is None:
            return []
        active_appliances = sorted(
            _activity_set(snapshots[-1]).intersection(_APPLIANCE_UNUSUAL_HOUR_ACTIVITIES)
        )
        findings: list[BehaviorFinding] = []
        for activity_name in active_appliances:
            observed_hours = [
                hour
                for snapshot in snapshots
                if activity_name in _activity_set(snapshot)
                and (hour := _snapshot_encoded_hour(snapshot)) is not None
            ]
            if len(observed_hours) < min_observations:
                continue

            baseline_hour = _clock_median_hour([float(hour) for hour in observed_hours])
            distance = _clock_distance_hours(float(current_hour), baseline_hour)
            if distance < delta_hours:
                continue

            confidence = min(1.0, distance / max(delta_hours * 2, 0.1))
            signal = AnomalySignal(
                anomaly_type=rule.rule_id,
                severity=_severity(rule.severity),
                description=(
                    f"Appliance activity '{activity_name}' is active at an unusual hour: "
                    f"{_hour_bucket_label(current_hour)} differs from historical median "
                    f"{_hour_bucket_label(baseline_hour)}."
                ),
                confidence=round(confidence, 3),
                context={
                    "rule_id": rule.rule_id,
                    "activity_name": activity_name,
                    "window": window,
                    "min_observations": min_observations,
                    "delta_hours": delta_hours,
                    "observation_count": len(observed_hours),
                    "current_hour": current_hour,
                    "baseline_hour": round(baseline_hour, 3),
                    "distance_hours": round(distance, 3),
                },
            )
            findings.append(_finding(self.analyzer_id, signal))
        return findings

    def _evaluate_lights_on_unattended(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["lights_on_unattended"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 3)
        window = max(min_observations, _threshold_int(rule, "window", 6))
        snapshots = snapshot_store.snapshots(limit=window)
        unattended = [
            snapshot
            for snapshot in snapshots
            if not bool(getattr(snapshot, "anyone_home", False)) and _lit_entities(snapshot)
        ]
        if len(unattended) < min_observations:
            return []

        entity_ids = sorted(
            {entity_id for snapshot in unattended for entity_id in _lit_entities(snapshot)}
        )
        confidence = min(1.0, len(unattended) / max(min_observations * 2, 1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Lights were physically on while nobody was home "
                f"in {len(unattended)} recent snapshots."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "window": window,
                "min_observations": min_observations,
                "unattended_observation_count": len(unattended),
                "snapshot_count": len(snapshots),
                "entity_ids": entity_ids,
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_lighting_scene_drift(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["lighting_scene_drift"]
        if not rule.enabled:
            return []
        history_window = _threshold_int(rule, "history_window", 1000)
        min_observations = _threshold_int(rule, "min_observations", 10)
        recent_observations = _threshold_int(rule, "recent_observations", 3)
        baseline_ratio_threshold = _threshold_float(rule, "baseline_ratio", 0.65)
        snapshots = snapshot_store.snapshots(
            limit=max(history_window, min_observations + recent_observations)
        )
        if not snapshots:
            return []

        current = snapshots[-1]
        current_scenes = _safe_dict(getattr(current, "lighting_scenes", {}))
        current_house_state = str(getattr(current, "house_state", "") or "")
        current_hour = int(getattr(current, "minute_of_day", 0) or 0) // 60
        findings: list[BehaviorFinding] = []
        for scene_key, current_scene_raw in sorted(current_scenes.items()):
            scene_name = str(current_scene_raw or "").strip()
            if not scene_name:
                continue

            matching = [
                snapshot
                for snapshot in snapshots
                if str(getattr(snapshot, "house_state", "") or "") == current_house_state
                and int(getattr(snapshot, "minute_of_day", 0) or 0) // 60 == current_hour
                and scene_key in _safe_dict(getattr(snapshot, "lighting_scenes", {}))
            ]
            if len(matching) < min_observations + recent_observations:
                continue

            recent = matching[-recent_observations:]
            baseline = matching[:-recent_observations]
            if len(baseline) < min_observations:
                continue
            recent_scene_names = [
                str(_safe_dict(getattr(snapshot, "lighting_scenes", {})).get(scene_key) or "")
                for snapshot in recent
            ]
            if not recent_scene_names or any(name != scene_name for name in recent_scene_names):
                continue

            baseline_scene_names = [
                str(_safe_dict(getattr(snapshot, "lighting_scenes", {})).get(scene_key) or "")
                for snapshot in baseline
            ]
            baseline_scene, baseline_ratio = _dominant_ratio(baseline_scene_names)
            if not baseline_scene:
                continue
            if baseline_scene == scene_name:
                continue
            if baseline_ratio < baseline_ratio_threshold:
                continue

            signal = AnomalySignal(
                anomaly_type=rule.rule_id,
                severity=_severity(rule.severity),
                description=(
                    "Lighting scene drifted for a usual house-state/time slot: "
                    f"{scene_key} is now '{scene_name}' instead of baseline '{baseline_scene}'."
                ),
                confidence=round(min(1.0, baseline_ratio), 3),
                context={
                    "rule_id": rule.rule_id,
                    "scene_key": str(scene_key),
                    "house_state": current_house_state,
                    "hour_bucket": current_hour,
                    "current_scene": scene_name,
                    "baseline_scene": baseline_scene,
                    "baseline_ratio": round(baseline_ratio, 3),
                    "baseline_ratio_threshold": baseline_ratio_threshold,
                    "baseline_snapshot_count": len(baseline),
                    "recent_snapshot_count": len(recent),
                    "history_window": history_window,
                },
            )
            findings.append(_finding(self.analyzer_id, signal))
        return findings

    def _evaluate_sensor_activity_drop(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["sensor_activity_drop"]
        if not rule.enabled:
            return []
        window_hours = _threshold_float(rule, "window_hours", 4.0)
        history_window = _threshold_int(rule, "history_window", 1000)
        min_observations = _threshold_int(rule, "min_observations", 10)
        drop_ratio = _threshold_float(rule, "drop_ratio", 0.3)
        snapshots = snapshot_store.snapshots(limit=history_window)
        timed = [
            (parsed, snapshot)
            for snapshot in snapshots
            if (parsed := _snapshot_time(snapshot)) is not None
        ]
        if not timed:
            return []

        latest_time = timed[-1][0]
        recent_cutoff = latest_time - timedelta(hours=max(window_hours, 0.1))
        recent = [(ts, snapshot) for ts, snapshot in timed if ts >= recent_cutoff]
        recent_rate = len(recent) / max(window_hours, 0.1)
        current_slot = (
            int(getattr(timed[-1][1], "weekday", 0) or 0),
            int(getattr(timed[-1][1], "minute_of_day", 0) or 0) // 60,
        )
        baseline = [
            (ts, snapshot)
            for ts, snapshot in timed
            if ts < recent_cutoff
            and (
                int(getattr(snapshot, "weekday", 0) or 0),
                int(getattr(snapshot, "minute_of_day", 0) or 0) // 60,
            )
            == current_slot
        ]
        if len(baseline) < min_observations:
            return []

        baseline_span_h = max(
            (baseline[-1][0] - baseline[0][0]).total_seconds() / 3600,
            1.0,
        )
        baseline_rate = len(baseline) / baseline_span_h
        threshold_rate = baseline_rate * drop_ratio
        if recent_rate >= threshold_rate:
            return []

        confidence = min(1.0, 1.0 - (recent_rate / max(threshold_rate, 0.001)))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Tracked domain activity dropped below historical baseline: "
                f"{recent_rate:.2f} snapshots/hour vs {baseline_rate:.2f} baseline."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "window_hours": window_hours,
                "history_window": history_window,
                "min_observations": min_observations,
                "drop_ratio": drop_ratio,
                "recent_snapshot_count": len(recent),
                "recent_rate_per_hour": round(recent_rate, 3),
                "baseline_snapshot_count": len(baseline),
                "baseline_rate_per_hour": round(baseline_rate, 3),
                "threshold_rate_per_hour": round(threshold_rate, 3),
                "weekday": current_slot[0],
                "hour_bucket": current_slot[1],
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_ghost_activity(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["ghost_activity"]
        if not rule.enabled:
            return []
        window = _threshold_int(rule, "window", 20)
        min_ghost_observations = _threshold_int(rule, "min_ghost_observations", 3)
        snapshots = snapshot_store.snapshots(limit=max(window, min_ghost_observations))
        ghost_snapshots = [
            snapshot
            for snapshot in snapshots
            if not bool(getattr(snapshot, "anyone_home", False))
            and any(
                bool(value)
                for value in _safe_dict(getattr(snapshot, "room_occupancy", {})).values()
            )
        ]
        if len(ghost_snapshots) < min_ghost_observations:
            return []

        confidence = min(1.0, len(ghost_snapshots) / max(min_ghost_observations * 2, 1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Room occupancy was detected while no resident was home "
                f"in {len(ghost_snapshots)} recent snapshots."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "window": window,
                "min_ghost_observations": min_ghost_observations,
                "ghost_observation_count": len(ghost_snapshots),
                "snapshot_count": len(snapshots),
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_unusual_stillness(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["unusual_stillness"]
        if not rule.enabled:
            return []
        history_window = _threshold_int(rule, "history_window", 1000)
        min_observations = _threshold_int(rule, "min_observations", 10)
        multiplier = _threshold_float(rule, "multiplier", 2.0)
        snapshots = snapshot_store.snapshots(limit=max(history_window, min_observations + 1))
        current_run = _current_stillness_run_length(snapshots)
        baseline_snapshots = snapshots[: len(snapshots) - current_run]
        run_lengths = _stillness_run_lengths(baseline_snapshots)
        if len(run_lengths) < min_observations:
            return []

        percentile_90 = _percentile_nearest_rank(run_lengths, 0.9)
        threshold = percentile_90 * multiplier
        if current_run <= threshold:
            return []

        confidence = min(1.0, current_run / max(threshold * 2, 1.0))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "House occupancy appears unusually still: current unchanged occupancy run "
                f"is {current_run} snapshot pairs."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "history_window": history_window,
                "min_observations": min_observations,
                "multiplier": multiplier,
                "current_run": current_run,
                "baseline_run_count": len(run_lengths),
                "percentile_90_run": percentile_90,
                "threshold_run": round(threshold, 3),
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_alarm_disarm_unusual_hour(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["alarm_disarm_unusual_hour"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 5)
        delta_hours = _threshold_float(rule, "delta_hours", 3.0)
        window = max(min_observations + 1, _threshold_int(rule, "window", 1000))
        snapshots = snapshot_store.snapshots(limit=window)
        transitions = _disarm_transitions(snapshots)
        if not transitions:
            return []
        current = transitions[-1]
        same_weekday = [
            transition for transition in transitions if transition.weekday == current.weekday
        ]
        if len(same_weekday) < min_observations + 1:
            return []

        baseline = [transition.hour_bucket for transition in same_weekday[:-1]]
        baseline_hour = _clock_median_hour([float(hour) for hour in baseline])
        distance = _clock_distance_hours(float(current.hour_bucket), baseline_hour)
        if distance < delta_hours:
            return []

        confidence = min(1.0, distance / max(delta_hours * 2, 0.1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Alarm was disarmed at an unusual hour: "
                f"{_hour_bucket_label(current.hour_bucket)} differs from historical median "
                f"{_hour_bucket_label(baseline_hour)}."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "weekday": current.weekday,
                "transition_count": len(same_weekday),
                "baseline_transition_count": len(baseline),
                "current_hour_bucket": current.hour_bucket,
                "baseline_hour_bucket": round(baseline_hour, 3),
                "distance_hours": round(distance, 3),
                "delta_hours": delta_hours,
                "window": window,
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_alarm_expected_not_armed(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["alarm_expected_not_armed"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 8)
        expected_ratio = _threshold_float(rule, "expected_ratio", 0.8)
        recent_disarmed_observations = _threshold_int(rule, "recent_disarmed_observations", 2)
        history_window = max(
            min_observations + recent_disarmed_observations,
            _threshold_int(rule, "history_window", 1000),
        )
        snapshots = snapshot_store.snapshots(limit=history_window)
        if not snapshots:
            return []
        current_slot = (
            int(getattr(snapshots[-1], "weekday", 0) or 0),
            int(getattr(snapshots[-1], "minute_of_day", 0) or 0) // 60,
        )
        slot_snapshots = [
            snapshot
            for snapshot in snapshots
            if (
                int(getattr(snapshot, "weekday", 0) or 0),
                int(getattr(snapshot, "minute_of_day", 0) or 0) // 60,
            )
            == current_slot
        ]
        if len(slot_snapshots) < min_observations + recent_disarmed_observations:
            return []

        recent = slot_snapshots[-recent_disarmed_observations:]
        baseline = slot_snapshots[:-recent_disarmed_observations]
        if len(baseline) < min_observations:
            return []
        if any(_security_state(snapshot) != "disarmed" for snapshot in recent):
            return []

        armed_count = sum(1 for snapshot in baseline if _is_armed_state(_security_state(snapshot)))
        armed_ratio = armed_count / len(baseline)
        if armed_ratio < expected_ratio:
            return []

        confidence = min(1.0, armed_ratio)
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Alarm is disarmed in a time slot where it is usually armed: "
                f"weekday {current_slot[0]}, hour {current_slot[1]}."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "weekday": current_slot[0],
                "hour_bucket": current_slot[1],
                "baseline_snapshot_count": len(baseline),
                "recent_disarmed_observations": len(recent),
                "armed_ratio": round(armed_ratio, 3),
                "expected_ratio": expected_ratio,
                "history_window": history_window,
            },
        )
        return [_finding(self.analyzer_id, signal)]

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
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_heating_vacation_mismatch(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["heating_vacation_mismatch"]
        if not rule.enabled:
            return []
        min_observations = _threshold_int(rule, "min_observations", 3)
        max_away_setpoint_c = _threshold_float(rule, "max_away_setpoint_c", 18.0)
        window = max(min_observations, _threshold_int(rule, "window", 6))
        snapshots = [
            snapshot
            for snapshot in snapshot_store.snapshots(limit=window)
            if getattr(snapshot, "heating_setpoint", None) is not None
        ]
        armed_away = [
            snapshot
            for snapshot in snapshots
            if str(getattr(snapshot, "security_state", "") or "").strip() == "armed_away"
        ]
        if len(armed_away) < min_observations:
            return []

        setpoints = [float(snapshot.heating_setpoint) for snapshot in armed_away]
        if not setpoints or any(setpoint <= max_away_setpoint_c for setpoint in setpoints):
            return []

        min_setpoint = min(setpoints)
        avg_setpoint = sum(setpoints) / len(setpoints)
        excess = min_setpoint - max_away_setpoint_c
        confidence = min(1.0, excess / 2.0)
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Heating setpoint remains high while security is armed away: "
                f"minimum observed away setpoint is {min_setpoint:.1f}C."
            ),
            confidence=round(confidence, 3),
            context={
                "rule_id": rule.rule_id,
                "snapshot_count": len(snapshots),
                "armed_away_snapshot_count": len(armed_away),
                "avg_away_setpoint_c": round(avg_setpoint, 3),
                "min_away_setpoint_c": round(min_setpoint, 3),
                "max_away_setpoint_c": max_away_setpoint_c,
                "window": window,
            },
        )
        return [_finding(self.analyzer_id, signal)]

    def _evaluate_learned_model_stale(
        self,
        snapshot_store: Any,
        rules: dict[str, AnomalyRule],
    ) -> list[BehaviorFinding]:
        rule = rules["learned_model_stale"]
        if not rule.enabled:
            return []
        recent_window = _threshold_int(rule, "recent_window", 500)
        drift_threshold = _threshold_float(rule, "drift_threshold", 0.5)
        dominant_ratio = _threshold_float(rule, "dominant_ratio", 0.15)
        min_stale_contexts = _threshold_int(rule, "min_stale_contexts", 2)

        diagnostics = _safe_dict(self._inference_diagnostics_provider())
        model_total_snapshots = _positive_int(diagnostics.get("model_total_snapshots"))
        if model_total_snapshots <= 0:
            return []
        approved_entries = diagnostics.get("approved_model_entries")
        if not isinstance(approved_entries, list):
            return []
        recent_snapshots = snapshot_store.snapshots(limit=recent_window)
        if not recent_snapshots:
            return []

        stale_contexts: list[dict[str, Any]] = []
        for raw_entry in approved_entries:
            entry = _safe_dict(raw_entry)
            count = _positive_int(entry.get("count"))
            expected_ratio = count / model_total_snapshots
            if expected_ratio < dominant_ratio:
                continue
            recent_count = sum(
                1 for snapshot in recent_snapshots if _snapshot_matches_model_entry(snapshot, entry)
            )
            recent_ratio = recent_count / len(recent_snapshots)
            stale_threshold = expected_ratio * drift_threshold
            if recent_ratio >= stale_threshold:
                continue
            stale_contexts.append(
                {
                    "context_key": str(entry.get("context_key") or ""),
                    "tier": str(entry.get("tier") or ""),
                    "predicted_state": str(entry.get("predicted_state") or ""),
                    "expected_ratio": round(expected_ratio, 3),
                    "recent_ratio": round(recent_ratio, 3),
                    "stale_threshold": round(stale_threshold, 3),
                    "model_count": count,
                    "recent_count": recent_count,
                }
            )

        if len(stale_contexts) < min_stale_contexts:
            return []

        confidence = min(1.0, len(stale_contexts) / max(min_stale_contexts * 2, 1))
        signal = AnomalySignal(
            anomaly_type=rule.rule_id,
            severity=_severity(rule.severity),
            description=(
                "Approved learned house-state contexts appear stale: "
                f"{len(stale_contexts)} dominant contexts dropped below expected frequency."
            ),
            confidence=confidence,
            context={
                "rule_id": rule.rule_id,
                "stale_context_count": len(stale_contexts),
                "min_stale_contexts": min_stale_contexts,
                "recent_window": recent_window,
                "recent_snapshot_count": len(recent_snapshots),
                "model_total_snapshots": model_total_snapshots,
                "drift_threshold": drift_threshold,
                "dominant_ratio": dominant_ratio,
                "stale_contexts": stale_contexts[:10],
            },
        )
        return [_finding(self.analyzer_id, signal)]


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
    severity = "warning"
    if rule_id in {"arrival_time_outlier", "departure_time_outlier"}:
        thresholds = {
            "window": 1000,
            "min_observations": 5,
            "delta_hours": 3.0,
        }
    elif rule_id == "extended_absence":
        thresholds = {
            "history_window": 1000,
            "min_observations": 5,
            "multiplier": 2.0,
        }
    elif rule_id == "presence_pattern_drift":
        thresholds = {
            "history_window": 1000,
            "min_observations": 10,
            "recent_observations": 4,
            "drift_delta": 0.5,
        }
    elif rule_id == "heating_unresponsive":
        thresholds = {
            "window": 4,
            "min_observations": 4,
            "min_gap_c": 1.5,
            "min_delta_c": 0.2,
        }
    elif rule_id == "heating_setpoint_outlier":
        thresholds = {
            "window": 24,
            "min_observations": 8,
            "delta_c": 3.0,
        }
    elif rule_id == "heating_vacation_mismatch":
        thresholds = {
            "window": 6,
            "min_observations": 3,
            "max_away_setpoint_c": 18.0,
        }
    elif rule_id in {"stove_on_unattended", "oven_on_unattended"}:
        thresholds = {
            "window": 6,
            "min_observations": 2,
        }
        severity = "critical"
    elif rule_id == "appliance_unusual_hour":
        thresholds = {
            "window": 1000,
            "min_observations": 8,
            "delta_hours": 4.0,
        }
    elif rule_id == "lights_on_unattended":
        thresholds = {
            "window": 6,
            "min_observations": 3,
        }
    elif rule_id == "lighting_scene_drift":
        thresholds = {
            "history_window": 1000,
            "min_observations": 10,
            "recent_observations": 3,
            "baseline_ratio": 0.65,
        }
    elif rule_id == "alarm_disarm_unusual_hour":
        thresholds = {
            "window": 1000,
            "min_observations": 5,
            "delta_hours": 3.0,
        }
    elif rule_id == "alarm_expected_not_armed":
        thresholds = {
            "history_window": 1000,
            "min_observations": 8,
            "expected_ratio": 0.8,
            "recent_disarmed_observations": 2,
        }
    elif rule_id == "sensor_activity_drop":
        thresholds = {
            "window_hours": 4,
            "history_window": 1000,
            "min_observations": 10,
            "drop_ratio": 0.3,
        }
    elif rule_id == "ghost_activity":
        thresholds = {
            "window": 20,
            "min_ghost_observations": 3,
        }
    elif rule_id == "unusual_stillness":
        thresholds = {
            "history_window": 1000,
            "min_observations": 10,
            "multiplier": 2.0,
        }
    elif rule_id == "learned_model_stale":
        thresholds = {
            "recent_window": 500,
            "drift_threshold": 0.5,
            "dominant_ratio": 0.15,
            "min_stale_contexts": 2,
        }
        return AnomalyRule(
            rule_id=rule_id,
            enabled=False,
            severity="warning",
            thresholds=thresholds,
        )
    return AnomalyRule(rule_id=rule_id, enabled=True, severity=severity, thresholds=thresholds)


ANOMALY_RULE_CATALOG: dict[str, AnomalyRule] = {
    rule_id: _default_rule(rule_id) for rule_id in _ANOMALY_RULE_IDS
}


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


def _positive_int(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _severity(value: str) -> Literal["info", "warning", "critical"]:
    if value == "info":
        return "info"
    if value == "critical":
        return "critical"
    return "warning"


def _finding(analyzer_id: str, signal: AnomalySignal) -> BehaviorFinding:
    return BehaviorFinding(
        kind="anomaly",
        analyzer_id=analyzer_id,
        description=signal.description,
        confidence=signal.confidence,
        payload=signal,
    )


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2


def _clock_distance_hours(left: float, right: float) -> float:
    distance = abs(left - right) % 24
    return min(distance, 24 - distance)


def _clock_median_hour(values: list[float]) -> float:
    return min(
        values,
        key=lambda candidate: (
            sum(_clock_distance_hours(candidate, value) for value in values),
            candidate,
        ),
    )


@dataclass(frozen=True)
class _DisarmTransition:
    weekday: int
    hour_bucket: int


@dataclass(frozen=True)
class _PresenceTransition:
    weekday: int
    hour_bucket: int


def _presence_transitions(
    snapshots: list[Any],
    *,
    previous_home: bool,
    current_home: bool,
) -> list[_PresenceTransition]:
    transitions: list[_PresenceTransition] = []
    for previous, current in zip(snapshots, snapshots[1:], strict=False):
        if bool(getattr(previous, "anyone_home", False)) is not previous_home:
            continue
        if bool(getattr(current, "anyone_home", False)) is not current_home:
            continue
        transitions.append(
            _PresenceTransition(
                weekday=int(getattr(current, "weekday", 0) or 0),
                hour_bucket=int(getattr(current, "minute_of_day", 0) or 0) // 60,
            )
        )
    return transitions


def _disarm_transitions(snapshots: list[Any]) -> list[_DisarmTransition]:
    transitions: list[_DisarmTransition] = []
    for previous, current in zip(snapshots, snapshots[1:], strict=False):
        if not _is_armed_state(_security_state(previous)):
            continue
        if _security_state(current) != "disarmed":
            continue
        transitions.append(
            _DisarmTransition(
                weekday=int(getattr(current, "weekday", 0) or 0),
                hour_bucket=int(getattr(current, "minute_of_day", 0) or 0) // 60,
            )
        )
    return transitions


def _security_state(snapshot: Any) -> str:
    return str(getattr(snapshot, "security_state", "") or "").strip()


def _is_armed_state(security_state: str) -> bool:
    return security_state in {"armed_away", "armed_home", "armed_night"}


def _snapshot_slot(snapshot: Any) -> tuple[int, int]:
    return (
        int(getattr(snapshot, "weekday", 0) or 0),
        int(getattr(snapshot, "minute_of_day", 0) or 0) // 60,
    )


def _snapshot_time(snapshot: Any) -> datetime | None:
    raw = str(getattr(snapshot, "ts", "") or "")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _snapshot_encoded_hour(snapshot: Any) -> int | None:
    try:
        minute_of_day = int(getattr(snapshot, "minute_of_day"))
    except (TypeError, ValueError):
        minute_of_day = -1
    if 0 <= minute_of_day < 24 * 60:
        return minute_of_day // 60
    raw = str(getattr(snapshot, "ts", "") or "")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return int(parsed.hour)


def _hour_bucket_label(value: float | int) -> str:
    hour = float(value)
    whole_hour = int(hour)
    minute = round((hour - whole_hour) * 60)
    if minute == 60:
        whole_hour += 1
        minute = 0
    return f"{whole_hour % 24:02d}:{minute:02d}"


def _activity_set(snapshot: Any) -> set[str]:
    return {
        str(activity or "").strip()
        for activity in getattr(snapshot, "detected_activities", ()) or ()
        if str(activity or "").strip()
    }


def _snapshot_matches_model_entry(snapshot: Any, entry: dict[str, Any]) -> bool:
    context = _safe_dict(entry.get("context_snapshot"))
    if not context:
        return False
    if (
        str(getattr(snapshot, "house_state", "") or "").strip()
        != str(entry.get("predicted_state") or context.get("predicted_state") or "").strip()
    ):
        return False
    try:
        if int(getattr(snapshot, "weekday", -1)) != int(context.get("weekday", -2)):
            return False
        if int(getattr(snapshot, "minute_of_day", 0)) // 60 != int(context.get("hour_bucket", -1)):
            return False
    except (TypeError, ValueError):
        return False
    if bool(getattr(snapshot, "anyone_home", False)) is not bool(context.get("anyone_home")):
        return False

    learning_context = _safe_dict(context.get("learning_context"))
    module = str(learning_context.get("module") or "").strip()
    if module == "house_state_inference_minimal":
        return True
    if module == "house_state_inference_rich":
        return _snapshot_room_context_pattern(snapshot) == _context_room_context_pattern(
            learning_context.get("room_context_pattern")
        )
    return _occupied_rooms(snapshot) == _context_rooms(context.get("rooms"))


def _occupied_rooms(snapshot: Any) -> tuple[str, ...]:
    return tuple(
        sorted(
            str(room_id)
            for room_id, occupied in _safe_dict(getattr(snapshot, "room_occupancy", {})).items()
            if bool(occupied) and str(room_id).strip()
        )
    )


def _context_rooms(raw: Any) -> tuple[str, ...]:
    if not isinstance(raw, list | tuple | set | frozenset):
        return ()
    return tuple(sorted(str(room) for room in raw if str(room).strip()))


def _snapshot_room_context_pattern(snapshot: Any) -> tuple[tuple[str, bool, bool], ...]:
    room_context = _safe_dict(getattr(snapshot, "room_device_context", {}))
    items: list[tuple[str, bool, bool]] = []
    for room_id in _occupied_rooms(snapshot):
        raw_ctx = _safe_dict(room_context.get(room_id))
        if not raw_ctx:
            continue
        items.append(
            (
                room_id,
                bool(raw_ctx.get("media_on", False)),
                bool(raw_ctx.get("work_activity", False)),
            )
        )
    return tuple(sorted(items))


def _context_room_context_pattern(raw: Any) -> tuple[tuple[str, bool, bool], ...]:
    if not isinstance(raw, list | tuple):
        return ()
    items: list[tuple[str, bool, bool]] = []
    for item in raw:
        payload = _safe_dict(item)
        room_id = str(payload.get("room_id") or "").strip()
        if not room_id:
            continue
        items.append(
            (
                room_id,
                bool(payload.get("media_on", False)),
                bool(payload.get("work_activity", False)),
            )
        )
    return tuple(sorted(items))


def _lit_entities(snapshot: Any) -> list[str]:
    return sorted(
        str(entity_id)
        for entity_id, is_on in _safe_dict(getattr(snapshot, "lights_physically_on", {})).items()
        if bool(is_on) and str(entity_id).startswith("light.")
    )


def _dominant_ratio(values: list[str]) -> tuple[str, float]:
    counts: dict[str, int] = {}
    for value in values:
        normalized = str(value or "").strip()
        if not normalized:
            continue
        counts[normalized] = counts.get(normalized, 0) + 1
    if not counts:
        return "", 0.0
    dominant, count = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[0]
    return dominant, count / sum(counts.values())


def _same_room_occupancy(left: Any, right: Any) -> bool:
    return _safe_dict(getattr(left, "room_occupancy", {})) == _safe_dict(
        getattr(right, "room_occupancy", {})
    )


def _occupied_home_pair(left: Any, right: Any) -> bool:
    return bool(getattr(left, "anyone_home", False)) and bool(getattr(right, "anyone_home", False))


def _home_ratio(snapshots: list[Any]) -> float:
    if not snapshots:
        return 0.0
    home_count = sum(1 for snapshot in snapshots if bool(getattr(snapshot, "anyone_home", False)))
    return home_count / len(snapshots)


def _absence_run_lengths(snapshots: list[Any]) -> list[int]:
    lengths: list[int] = []
    current = 0
    for snapshot in snapshots:
        if not bool(getattr(snapshot, "anyone_home", False)):
            current += 1
            continue
        if current > 0:
            lengths.append(current)
            current = 0
    if current > 0:
        lengths.append(current)
    return lengths


def _current_absence_run_length(snapshots: list[Any]) -> int:
    current = 0
    for snapshot in reversed(snapshots):
        if not bool(getattr(snapshot, "anyone_home", False)):
            current += 1
            continue
        break
    return current


def _stillness_run_lengths(snapshots: list[Any]) -> list[int]:
    lengths: list[int] = []
    current = 0
    for left, right in zip(snapshots, snapshots[1:], strict=False):
        if _occupied_home_pair(left, right) and _same_room_occupancy(left, right):
            current += 1
            continue
        if current > 0:
            lengths.append(current)
            current = 0
    if current > 0:
        lengths.append(current)
    return lengths


def _current_stillness_run_length(snapshots: list[Any]) -> int:
    current = 0
    for index in range(len(snapshots) - 1, 0, -1):
        left = snapshots[index - 1]
        right = snapshots[index]
        if _occupied_home_pair(left, right) and _same_room_occupancy(left, right):
            current += 1
            continue
        break
    return current


def _percentile_nearest_rank(values: list[int], percentile: float) -> int:
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int(len(ordered) * percentile + 0.999999) - 1))
    return ordered[index]
