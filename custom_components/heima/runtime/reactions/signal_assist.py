"""Generic room-scoped signal assist reaction."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Literal

from homeassistant.core import HomeAssistant

from ...room_sources import room_signal_bucket_labels
from ..contracts import ApplyStep
from ..snapshot import DecisionSnapshot
from .base import HeimaReaction
from .composite import (
    RuntimeCompositeMatcher,
    RuntimeCompositePatternSpec,
    RuntimeCompositeSignalSpec,
    ThresholdMode,
    parse_snapshot_ts,
)

BucketMatchMode = Literal["eq", "lte", "gte"]


def _normalize_bucket_match_mode(value: str | BucketMatchMode | None) -> BucketMatchMode:
    normalized = str(value or "eq").strip().lower()
    if normalized in {"eq", "lte", "gte"}:
        return normalized  # type: ignore[return-value]
    return "eq"


def _bucket_match_mode_label(value: str | BucketMatchMode | None, *, language: str) -> str:
    normalized = _normalize_bucket_match_mode(value)
    is_it = language.startswith("it")
    if normalized == "lte":
        return "bucket o inferiori" if is_it else "bucket or lower"
    if normalized == "gte":
        return "bucket o superiori" if is_it else "bucket or higher"
    return "bucket esatto" if is_it else "exact bucket"


class RoomSignalAssistReaction(HeimaReaction):
    """Trigger configured steps when room-scoped signal burst pattern is observed."""

    def __init__(
        self,
        *,
        hass: HomeAssistant,
        bucket_getter: Any | None = None,
        burst_getter: Any | None = None,
        use_burst_accessor: bool = False,
        room_id: str,
        trigger_signal_entities: list[str] | None = None,
        steps: list[ApplyStep],
        primary_signal_entities: list[str] | None = None,
        primary_bucket: str | None = None,
        primary_bucket_match_mode: BucketMatchMode = "eq",
        primary_bucket_labels: list[str] | None = None,
        primary_threshold: float | None = None,
        primary_threshold_mode: ThresholdMode = "rise",
        primary_rise_threshold: float | None = None,
        primary_signal_name: str = "primary",
        humidity_rise_threshold: float = 8.0,
        corroboration_signal_entities: list[str] | None = None,
        corroboration_bucket: str | None = None,
        corroboration_bucket_match_mode: BucketMatchMode = "eq",
        corroboration_bucket_labels: list[str] | None = None,
        corroboration_threshold: float | None = None,
        corroboration_threshold_mode: ThresholdMode = "rise",
        corroboration_rise_threshold: float | None = None,
        corroboration_signal_name: str = "corroboration",
        temperature_signal_entities: list[str] | None = None,
        temperature_rise_threshold: float = 0.8,
        correlation_window_s: int = 600,
        followup_window_s: int = 900,
        house_state_filter: str | None = None,
        reaction_id: str | None = None,
    ) -> None:
        self._hass = hass
        self._house_state_filter = str(house_state_filter).strip() if house_state_filter else None
        self._bucket_getter = bucket_getter or (lambda _room_id, _signal_name: None)
        self._burst_getter = burst_getter or (lambda _room_id, _signal_name, *, window_s: False)
        self._use_burst_accessor = use_burst_accessor
        self._room_id = room_id
        resolved_primary_entities = [
            e for e in (primary_signal_entities or trigger_signal_entities or []) if e
        ]
        resolved_primary_threshold = (
            primary_threshold
            if primary_threshold is not None
            else (
                primary_rise_threshold
                if primary_rise_threshold is not None
                else humidity_rise_threshold
            )
        )
        resolved_corroboration_entities = [
            e for e in (corroboration_signal_entities or temperature_signal_entities or []) if e
        ]
        resolved_corroboration_threshold = (
            corroboration_threshold
            if corroboration_threshold is not None
            else (
                corroboration_rise_threshold
                if corroboration_rise_threshold is not None
                else temperature_rise_threshold
            )
        )
        self._primary_entities = resolved_primary_entities
        self._corroboration_entities = resolved_corroboration_entities
        self._steps = list(steps)
        self._primary_bucket = str(primary_bucket or "").strip() or None
        self._primary_bucket_match_mode = _normalize_bucket_match_mode(primary_bucket_match_mode)
        self._primary_bucket_labels = tuple(
            str(item).strip() for item in (primary_bucket_labels or []) if str(item).strip()
        )
        self._primary_threshold = float(resolved_primary_threshold)
        self._primary_threshold_mode = primary_threshold_mode
        self._corroboration_bucket = str(corroboration_bucket or "").strip() or None
        self._corroboration_bucket_match_mode = _normalize_bucket_match_mode(
            corroboration_bucket_match_mode
        )
        self._corroboration_bucket_labels = tuple(
            str(item).strip() for item in (corroboration_bucket_labels or []) if str(item).strip()
        )
        self._corroboration_threshold = float(resolved_corroboration_threshold)
        self._corroboration_threshold_mode = corroboration_threshold_mode
        self._primary_signal_name = primary_signal_name or "primary"
        self._corroboration_signal_name = corroboration_signal_name or "corroboration"
        self._correlation_window_s = correlation_window_s
        self._followup_window_s = followup_window_s
        self._reaction_id = reaction_id or self.__class__.__name__
        self._legacy_trigger_entities = [e for e in (trigger_signal_entities or []) if e]
        self._matcher = RuntimeCompositeMatcher(hass)
        self._pattern = RuntimeCompositePatternSpec(
            primary=RuntimeCompositeSignalSpec(
                name=self._primary_signal_name,
                entity_ids=tuple(self._primary_entities),
                threshold=self._primary_threshold,
                threshold_mode=self._primary_threshold_mode,
            ),
            corroborations=(
                RuntimeCompositeSignalSpec(
                    name=self._corroboration_signal_name,
                    entity_ids=tuple(self._corroboration_entities),
                    threshold=self._corroboration_threshold,
                    threshold_mode=self._corroboration_threshold_mode,
                    required=bool(self._corroboration_entities),
                ),
            )
            if self._corroboration_entities
            else (),
            correlation_window_s=self._correlation_window_s,
        )
        self._pending_episode_ts: datetime | None = None
        self._last_fired_ts: float | None = None
        self._last_fired_iso: str | None = None
        self._fire_count = 0
        self._suppressed_count = 0
        self._steady_condition_active = False

    @property
    def reaction_id(self) -> str:
        return self._reaction_id

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        if not history:
            return []
        snapshot = history[-1]
        if self._room_id not in snapshot.occupied_rooms:
            self._steady_condition_active = False
            self._last_fired_ts = None
            self._last_fired_iso = None
            return []
        if self._house_state_filter and snapshot.house_state != self._house_state_filter:
            return []

        if self._primary_bucket:
            should_fire = self._steady_ready()
        elif self._use_burst_accessor:
            should_fire = self._burst_ready()
        else:
            now = parse_snapshot_ts(snapshot.ts)
            if now is None:
                return []

            result = self._matcher.observe(
                now=now,
                pending_since=self._pending_episode_ts,
                spec=self._pattern,
            )
            self._pending_episode_ts = result.pending_since
            should_fire = result.ready

        if should_fire and self._is_cooled_down():
            self._pending_episode_ts = None
            self._fire_count += 1
            self._last_fired_ts = time.monotonic()
            self._last_fired_iso = datetime.now().isoformat()
            if self._primary_bucket:
                self._steady_condition_active = True
            return list(self._steps)
        if should_fire:
            self._suppressed_count += 1
        return []

    def reset_learning_state(self) -> None:
        self._matcher.reset()
        self._pending_episode_ts = None
        self._last_fired_ts = None
        self._last_fired_iso = None
        self._fire_count = 0
        self._suppressed_count = 0
        self._steady_condition_active = False

    def diagnostics(self) -> dict[str, Any]:
        diagnostics = {
            "room_id": self._room_id,
            "trigger_signal_entities": list(self._legacy_trigger_entities),
            "primary_signal_name": self._primary_signal_name,
            "primary_entities": list(self._primary_entities),
            "primary_bucket": self._primary_bucket,
            "primary_bucket_match_mode": self._primary_bucket_match_mode,
            "primary_bucket_labels": list(self._primary_bucket_labels),
            "corroboration_signal_name": self._corroboration_signal_name,
            "corroboration_entities": list(self._corroboration_entities),
            "corroboration_bucket": self._corroboration_bucket,
            "corroboration_bucket_match_mode": self._corroboration_bucket_match_mode,
            "corroboration_bucket_labels": list(self._corroboration_bucket_labels),
            "uses_burst_accessor": self._use_burst_accessor,
            "humidity_entities": list(self._primary_entities),
            "temperature_entities": list(self._corroboration_entities),
            "fire_count": self._fire_count,
            "suppressed_count": self._suppressed_count,
            "last_fired_ts": self._last_fired_ts,
            "last_fired_iso": self._last_fired_iso,
            "pending_episode": self._pending_episode_ts.isoformat()
            if self._pending_episode_ts
            else None,
            "steady_condition_active": self._steady_condition_active,
        }
        if not self._primary_bucket and not self._use_burst_accessor:
            diagnostics["primary_threshold"] = self._primary_threshold
            diagnostics["primary_threshold_mode"] = self._primary_threshold_mode
            diagnostics["primary_rise_threshold"] = self._primary_threshold
        if not self._corroboration_bucket and not self._use_burst_accessor:
            diagnostics["corroboration_threshold"] = self._corroboration_threshold
            diagnostics["corroboration_threshold_mode"] = self._corroboration_threshold_mode
            diagnostics["corroboration_rise_threshold"] = self._corroboration_threshold
        return diagnostics

    def _is_cooled_down(self) -> bool:
        if self._last_fired_ts is None:
            return True
        return (time.monotonic() - self._last_fired_ts) >= self._followup_window_s

    def _steady_ready(self) -> bool:
        current_bucket = self._bucket_getter(self._room_id, self._primary_signal_name)
        if not self._bucket_matches(
            current_bucket,
            expected_bucket=self._primary_bucket,
            match_mode=self._primary_bucket_match_mode,
            labels=self._primary_bucket_labels,
        ):
            self._steady_condition_active = False
            return False
        if self._corroboration_bucket:
            corroboration_bucket = self._bucket_getter(
                self._room_id,
                self._corroboration_signal_name,
            )
            if not self._bucket_matches(
                corroboration_bucket,
                expected_bucket=self._corroboration_bucket,
                match_mode=self._corroboration_bucket_match_mode,
                labels=self._corroboration_bucket_labels,
            ):
                self._steady_condition_active = False
                return False
        if self._steady_condition_active:
            return False
        return True

    @staticmethod
    def _bucket_matches(
        current_bucket: str | None,
        *,
        expected_bucket: str | None,
        match_mode: BucketMatchMode,
        labels: tuple[str, ...],
    ) -> bool:
        expected = str(expected_bucket or "").strip()
        current = str(current_bucket or "").strip()
        if not expected or not current:
            return False
        if match_mode == "eq":
            return current == expected
        order = list(labels)
        if not order:
            return current == expected
        try:
            current_index = order.index(current)
            expected_index = order.index(expected)
        except ValueError:
            return current == expected
        if match_mode == "lte":
            return current_index <= expected_index
        if match_mode == "gte":
            return current_index >= expected_index
        return current == expected

    def _burst_ready(self) -> bool:
        should_fire = bool(
            self._burst_getter(
                self._room_id,
                self._primary_signal_name,
                window_s=self._followup_window_s,
            )
        )
        if not should_fire:
            return False
        if self._corroboration_signal_name and self._corroboration_entities:
            return bool(
                self._burst_getter(
                    self._room_id,
                    self._corroboration_signal_name,
                    window_s=self._followup_window_s,
                )
            )
        return True


def _is_canonical_signal_assist_type(reaction_type: str | None) -> bool:
    normalized = str(reaction_type or "").strip()
    return normalized in {"room_signal_assist", "room_air_quality_assist"}


def _is_room_cooling_assist_type(reaction_type: str | None) -> bool:
    return str(reaction_type or "").strip() == "room_cooling_assist"


def normalize_room_signal_assist_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Normalize legacy aliases to the generic composite reaction contract."""
    trigger_signal_entities = [
        str(v).strip() for v in cfg.get("trigger_signal_entities", []) if str(v).strip()
    ]
    primary_signal_entities = [
        str(v).strip()
        for v in cfg.get("primary_signal_entities", trigger_signal_entities)
        if str(v).strip()
    ]
    primary_bucket = str(cfg.get("primary_bucket") or "").strip() or None
    primary_bucket_match_mode = str(cfg.get("primary_bucket_match_mode") or "eq").strip() or "eq"
    temperature_signal_entities = [
        str(v).strip() for v in cfg.get("temperature_signal_entities", []) if str(v).strip()
    ]
    corroboration_signal_entities = [
        str(v).strip()
        for v in cfg.get("corroboration_signal_entities", temperature_signal_entities)
        if str(v).strip()
    ]
    corroboration_bucket = str(cfg.get("corroboration_bucket") or "").strip() or None
    corroboration_bucket_match_mode = (
        str(cfg.get("corroboration_bucket_match_mode") or "eq").strip() or "eq"
    )
    humidity_rise_threshold = float(cfg.get("humidity_rise_threshold", 8.0))
    primary_rise_threshold = float(cfg.get("primary_rise_threshold", humidity_rise_threshold))
    primary_threshold = float(cfg.get("primary_threshold", primary_rise_threshold))
    primary_threshold_mode = str(cfg.get("primary_threshold_mode", "rise")).strip() or "rise"
    temperature_rise_threshold = float(cfg.get("temperature_rise_threshold", 0.8))
    corroboration_rise_threshold = float(
        cfg.get("corroboration_rise_threshold", temperature_rise_threshold)
    )
    corroboration_threshold = float(
        cfg.get("corroboration_threshold", corroboration_rise_threshold)
    )
    corroboration_threshold_mode = (
        str(cfg.get("corroboration_threshold_mode", "rise")).strip() or "rise"
    )
    primary_signal_name = str(cfg.get("primary_signal_name", "primary"))
    corroboration_signal_name = str(cfg.get("corroboration_signal_name", "corroboration"))
    reaction_type = str(cfg.get("reaction_type") or "").strip()
    if _is_room_cooling_assist_type(reaction_type):
        if primary_signal_name.strip().lower() == "temperature":
            primary_signal_name = "room_temperature"
        if corroboration_signal_name.strip().lower() == "humidity":
            corroboration_signal_name = "room_humidity"
    if _is_canonical_signal_assist_type(reaction_type) and primary_bucket:
        primary_threshold = primary_rise_threshold
        primary_threshold_mode = "rise"
        if corroboration_bucket:
            corroboration_threshold = corroboration_rise_threshold
            corroboration_threshold_mode = "rise"
    return {
        "reaction_type": reaction_type,
        "trigger_signal_entities": trigger_signal_entities,
        "primary_signal_entities": primary_signal_entities,
        "primary_bucket": primary_bucket,
        "primary_bucket_match_mode": primary_bucket_match_mode,
        "temperature_signal_entities": temperature_signal_entities,
        "corroboration_signal_entities": corroboration_signal_entities,
        "corroboration_bucket": corroboration_bucket,
        "corroboration_bucket_match_mode": corroboration_bucket_match_mode,
        "humidity_rise_threshold": humidity_rise_threshold,
        "primary_rise_threshold": primary_rise_threshold,
        "primary_threshold": primary_threshold,
        "primary_threshold_mode": primary_threshold_mode,
        "temperature_rise_threshold": temperature_rise_threshold,
        "corroboration_rise_threshold": corroboration_rise_threshold,
        "corroboration_threshold": corroboration_threshold,
        "corroboration_threshold_mode": corroboration_threshold_mode,
        "primary_signal_name": primary_signal_name,
        "corroboration_signal_name": corroboration_signal_name,
    }


def _build_normalized_room_signal_assist_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
    *,
    expected_contract: str,
) -> RoomSignalAssistReaction | None:
    try:
        room_id = str(cfg["room_id"]).strip()
        normalized = normalize_room_signal_assist_config(cfg)
        reaction_type = normalized["reaction_type"]
        correlation_window_s = int(cfg.get("correlation_window_s", 600))
        followup_window_s = int(cfg.get("followup_window_s", 900))
        steps_raw: list = cfg.get("steps", [])
        steps = [ApplyStep(**s) if isinstance(s, dict) else s for s in steps_raw]
        rooms = list(dict(getattr(engine, "_entry").options).get("rooms") or [])  # noqa: SLF001
        primary_bucket_labels = room_signal_bucket_labels(
            rooms, room_id, normalized["primary_signal_name"]
        )
        corroboration_bucket_labels = room_signal_bucket_labels(
            rooms, room_id, normalized["corroboration_signal_name"]
        )
        if not room_id or not normalized["primary_signal_entities"]:
            raise ValueError("room_id or primary_signal_entities missing")
        if expected_contract == "canonical":
            if not _is_canonical_signal_assist_type(reaction_type):
                raise ValueError("canonical builder requires canonical reaction type")
            primary_trigger_mode = str(cfg.get("primary_trigger_mode") or "bucket").strip()
            if primary_trigger_mode != "burst" and not normalized["primary_bucket"]:
                raise ValueError("canonical room signal assist requires primary_bucket")
            if (
                primary_trigger_mode != "burst"
                and reaction_type == "room_signal_assist"
                and normalized["corroboration_signal_entities"]
                and not normalized["corroboration_bucket"]
            ):
                raise ValueError("canonical room signal assist requires corroboration_bucket")
        elif expected_contract == "cooling":
            if not _is_room_cooling_assist_type(reaction_type):
                raise ValueError("cooling builder requires room_cooling_assist")
            if not normalized["primary_signal_name"]:
                raise ValueError("cooling builder requires primary signal name")
        else:
            raise ValueError("unsupported signal assist contract")
    except (KeyError, TypeError, ValueError):
        return None
    return RoomSignalAssistReaction(
        hass=engine._hass,  # noqa: SLF001
        bucket_getter=engine.signal_bucket,
        burst_getter=engine.signal_burst_recent,
        use_burst_accessor=(
            expected_contract == "cooling"
            or (
                expected_contract == "canonical"
                and str(cfg.get("primary_trigger_mode") or "bucket").strip() == "burst"
            )
        ),
        room_id=room_id,
        trigger_signal_entities=normalized["trigger_signal_entities"],
        primary_signal_entities=normalized["primary_signal_entities"],
        primary_bucket=normalized["primary_bucket"],
        primary_bucket_match_mode=_normalize_bucket_match_mode(
            normalized.get("primary_bucket_match_mode")
        ),
        primary_bucket_labels=primary_bucket_labels,
        primary_threshold=normalized["primary_threshold"],
        primary_threshold_mode=normalized["primary_threshold_mode"],
        primary_rise_threshold=normalized["primary_rise_threshold"],
        primary_signal_name=normalized["primary_signal_name"],
        corroboration_signal_entities=normalized["corroboration_signal_entities"],
        corroboration_bucket=normalized["corroboration_bucket"],
        corroboration_bucket_match_mode=_normalize_bucket_match_mode(
            normalized.get("corroboration_bucket_match_mode")
        ),
        corroboration_bucket_labels=corroboration_bucket_labels,
        corroboration_threshold=normalized["corroboration_threshold"],
        corroboration_threshold_mode=normalized["corroboration_threshold_mode"],
        corroboration_rise_threshold=normalized["corroboration_rise_threshold"],
        corroboration_signal_name=normalized["corroboration_signal_name"],
        temperature_signal_entities=normalized["temperature_signal_entities"],
        humidity_rise_threshold=normalized["humidity_rise_threshold"],
        temperature_rise_threshold=normalized["temperature_rise_threshold"],
        correlation_window_s=correlation_window_s,
        followup_window_s=followup_window_s,
        steps=steps,
        house_state_filter=cfg.get("house_state_filter") or None,
        reaction_id=proposal_id,
    )


def build_room_signal_assist_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> RoomSignalAssistReaction | None:
    """Build a canonical bucket-based room signal assist reaction."""
    return _build_normalized_room_signal_assist_reaction(
        engine,
        proposal_id,
        cfg,
        expected_contract="canonical",
    )


def build_room_cooling_assist_reaction(
    engine: Any,
    proposal_id: str,
    cfg: dict[str, Any],
) -> RoomSignalAssistReaction | None:
    """Build the generic threshold-based room cooling assist reaction."""
    return _build_normalized_room_signal_assist_reaction(
        engine,
        proposal_id,
        cfg,
        expected_contract="cooling",
    )


def present_room_signal_assist_label(
    reaction_id: str,
    cfg: dict[str, Any],
    labels_map: dict[str, str],
) -> str | None:
    """Return a human label for persisted room signal assist reactions."""
    try:
        room_id = str(cfg.get("room_id", "")).strip() or reaction_id
        reaction_type = str(cfg.get("reaction_type") or "").strip()
        primary_signal_name = str(cfg.get("primary_signal_name") or "").strip().lower()
        corroboration_signal_name = str(cfg.get("corroboration_signal_name") or "").strip().lower()
        primary_trigger_mode = str(cfg.get("primary_trigger_mode") or "").strip().lower()
        house_state_filter = str(cfg.get("house_state_filter") or "").strip().lower()
        observed = int(cfg.get("episodes_observed", 0))
        if reaction_type == "room_cooling_assist":
            parts = [f"Raffrescamento {room_id}"]
        elif reaction_type == "room_air_quality_assist":
            parts = [f"Aria {room_id}"]
        else:
            parts = [f"Assist {room_id}"]
        if primary_signal_name:
            signal_bits = [primary_signal_name]
            if corroboration_signal_name:
                signal_bits.append(corroboration_signal_name)
            parts.append(" + ".join(signal_bits))
        if primary_trigger_mode:
            parts.append(primary_trigger_mode)
        if house_state_filter:
            parts.append(f"stato:{house_state_filter}")
        if observed > 0:
            parts.append(f"{observed} episodi")
        return " — ".join(parts)
    except (TypeError, ValueError):
        return labels_map.get(reaction_id)


def present_admin_authored_room_signal_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return room-signal-specific admin-authored review details."""
    is_it = language.startswith("it")
    details: list[str] = []
    reaction_type = str(
        cfg.get("reaction_type") or getattr(proposal, "reaction_type", "") or ""
    ).strip()
    primary_signal_name = _human_signal_name(str(cfg.get("primary_signal_name") or "").strip())
    if primary_signal_name:
        details.append(
            f"Segnale primario: {primary_signal_name}"
            if is_it
            else f"Primary signal: {primary_signal_name}"
        )
    primary_bucket = str(cfg.get("primary_bucket") or "").strip()
    if primary_bucket:
        details.append(
            f"Bucket primario: {primary_bucket}" if is_it else f"Primary bucket: {primary_bucket}"
        )
    primary_bucket_match_mode = str(cfg.get("primary_bucket_match_mode") or "").strip()
    if primary_bucket_match_mode:
        match_label = _bucket_match_mode_label(primary_bucket_match_mode, language=language)
        details.append(
            f"Match primario: {match_label}" if is_it else f"Primary bucket match: {match_label}"
        )
    primary_threshold = cfg.get("primary_threshold", cfg.get("primary_rise_threshold"))
    primary_threshold_mode = str(cfg.get("primary_threshold_mode") or "rise").strip()
    if (
        _is_room_cooling_assist_type(reaction_type)
        and not primary_bucket
        and primary_threshold not in (None, "")
    ):
        mode_label = flow._signal_threshold_mode_options().get(  # noqa: SLF001
            primary_threshold_mode, primary_threshold_mode
        )
        details.append(
            f"Condizione primaria: {mode_label} ({primary_threshold})"
            if is_it
            else f"Primary condition: {mode_label} ({primary_threshold})"
        )
    primary_entities = cfg.get("primary_signal_entities")
    if isinstance(primary_entities, list) and primary_entities:
        details.append(
            f"Entità primarie: {len(primary_entities)}"
            if is_it
            else f"Primary entities: {len(primary_entities)}"
        )
    corroboration_entities = cfg.get("corroboration_signal_entities")
    if isinstance(corroboration_entities, list) and corroboration_entities:
        corroboration_name = _human_signal_name(
            str(cfg.get("corroboration_signal_name") or "corroboration")
        )
        details.append(
            f"Corroborazione: {corroboration_name} ({len(corroboration_entities)})"
            if is_it
            else f"Corroboration: {corroboration_name} ({len(corroboration_entities)})"
        )
        corroboration_bucket = str(cfg.get("corroboration_bucket") or "").strip()
        if corroboration_bucket:
            details.append(
                f"Bucket corroborante: {corroboration_bucket}"
                if is_it
                else f"Corroborating bucket: {corroboration_bucket}"
            )
        corroboration_bucket_match_mode = str(
            cfg.get("corroboration_bucket_match_mode") or ""
        ).strip()
        if corroboration_bucket_match_mode:
            match_label = _bucket_match_mode_label(
                corroboration_bucket_match_mode, language=language
            )
            details.append(
                f"Match corroborante: {match_label}"
                if is_it
                else f"Corroborating bucket match: {match_label}"
            )
        corroboration_threshold = cfg.get(
            "corroboration_threshold", cfg.get("corroboration_rise_threshold")
        )
        corroboration_threshold_mode = str(
            cfg.get("corroboration_threshold_mode") or "rise"
        ).strip()
        if (
            _is_room_cooling_assist_type(reaction_type)
            and not corroboration_bucket
            and corroboration_threshold not in (None, "")
        ):
            mode_label = flow._signal_threshold_mode_options().get(  # noqa: SLF001
                corroboration_threshold_mode, corroboration_threshold_mode
            )
            details.append(
                f"Condizione corroborante: {mode_label} ({corroboration_threshold})"
                if is_it
                else f"Corroborating condition: {mode_label} ({corroboration_threshold})"
            )
    steps = cfg.get("steps")
    if isinstance(steps, list) and steps:
        details.append(
            f"Azioni configurate: {len(steps)}" if is_it else f"Configured actions: {len(steps)}"
        )
    return details


def present_learned_room_signal_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return learned/tuning review details for room signal assist proposals."""
    is_it = language.startswith("it")
    details: list[str] = []
    reaction_type = str(
        cfg.get("reaction_type") or getattr(proposal, "reaction_type", "") or ""
    ).strip()
    primary_signal_name = _human_signal_name(str(cfg.get("primary_signal_name") or "").strip())
    if primary_signal_name:
        details.append(
            f"Segnale primario: {primary_signal_name}"
            if is_it
            else f"Primary signal: {primary_signal_name}"
        )
    primary_bucket = str(cfg.get("primary_bucket") or "").strip()
    if primary_bucket:
        details.append(
            f"Bucket proposto: {primary_bucket}" if is_it else f"Proposed bucket: {primary_bucket}"
        )
    primary_bucket_match_mode = str(cfg.get("primary_bucket_match_mode") or "").strip()
    if primary_bucket_match_mode:
        match_label = _bucket_match_mode_label(primary_bucket_match_mode, language=language)
        details.append(
            f"Match proposto: {match_label}" if is_it else f"Proposed bucket match: {match_label}"
        )
    primary_threshold = cfg.get("primary_threshold", cfg.get("primary_rise_threshold"))
    primary_threshold_mode = str(cfg.get("primary_threshold_mode") or "rise").strip()
    if (
        _is_room_cooling_assist_type(reaction_type)
        and not primary_bucket
        and primary_threshold not in (None, "")
    ):
        mode_label = flow._signal_threshold_mode_options().get(  # noqa: SLF001
            primary_threshold_mode, primary_threshold_mode
        )
        details.append(
            f"Condizione proposta: {mode_label} ({primary_threshold})"
            if is_it
            else f"Proposed condition: {mode_label} ({primary_threshold})"
        )
    steps = cfg.get("steps")
    if isinstance(steps, list) and steps:
        details.append(
            f"Azioni proposte: {len(steps)}" if is_it else f"Proposed actions: {len(steps)}"
        )
    return details


def present_tuning_room_signal_assist_details(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    target_cfg: dict[str, Any],
    language: str,
) -> list[str]:
    """Return room-signal-specific tuning diff lines."""
    is_it = language.startswith("it")
    details: list[str] = []
    reaction_type = str(
        cfg.get("reaction_type")
        or target_cfg.get("reaction_type")
        or getattr(proposal, "reaction_type", "")
        or ""
    ).strip()
    current_bucket = str(target_cfg.get("primary_bucket") or "").strip()
    proposed_bucket = str(cfg.get("primary_bucket") or "").strip()
    if current_bucket or proposed_bucket:
        if current_bucket != proposed_bucket:
            details.append(
                f"Bucket primario: {current_bucket} -> {proposed_bucket}"
                if is_it
                else f"Primary bucket: {current_bucket} -> {proposed_bucket}"
            )
    current_primary_match_mode = str(target_cfg.get("primary_bucket_match_mode") or "").strip()
    proposed_primary_match_mode = str(cfg.get("primary_bucket_match_mode") or "").strip()
    if current_primary_match_mode or proposed_primary_match_mode:
        current_primary_match_label = _bucket_match_mode_label(
            current_primary_match_mode, language=language
        )
        proposed_primary_match_label = _bucket_match_mode_label(
            proposed_primary_match_mode, language=language
        )
        if current_primary_match_mode != proposed_primary_match_mode:
            details.append(
                f"Match primario: {current_primary_match_label} -> {proposed_primary_match_label}"
                if is_it
                else (
                    "Primary bucket match: "
                    f"{current_primary_match_label} -> {proposed_primary_match_label}"
                )
            )
    current_threshold = target_cfg.get(
        "primary_threshold", target_cfg.get("primary_rise_threshold")
    )
    proposed_threshold = cfg.get("primary_threshold", cfg.get("primary_rise_threshold"))
    if (
        _is_room_cooling_assist_type(reaction_type)
        and not (current_bucket or proposed_bucket)
        and current_threshold not in (None, "")
        and proposed_threshold not in (None, "")
    ):
        if str(current_threshold) != str(proposed_threshold):
            details.append(
                f"Soglia primaria: {current_threshold} -> {proposed_threshold}"
                if is_it
                else f"Primary threshold: {current_threshold} -> {proposed_threshold}"
            )

    current_mode = str(target_cfg.get("primary_threshold_mode") or "rise").strip()
    proposed_mode = str(cfg.get("primary_threshold_mode") or "rise").strip()
    if (
        _is_room_cooling_assist_type(reaction_type)
        and not (current_bucket or proposed_bucket)
        and current_mode != proposed_mode
    ):
        current_label = flow._signal_threshold_mode_options().get(current_mode, current_mode)  # noqa: SLF001
        proposed_label = flow._signal_threshold_mode_options().get(proposed_mode, proposed_mode)  # noqa: SLF001
        details.append(
            f"Modo primario: {current_label} -> {proposed_label}"
            if is_it
            else f"Primary mode: {current_label} -> {proposed_label}"
        )

    current_primary_entities = target_cfg.get("primary_signal_entities")
    proposed_primary_entities = cfg.get("primary_signal_entities")
    if isinstance(current_primary_entities, list) and isinstance(proposed_primary_entities, list):
        if len(current_primary_entities) != len(proposed_primary_entities):
            details.append(
                f"Entità primarie: {len(current_primary_entities)} -> {len(proposed_primary_entities)}"
                if is_it
                else (
                    f"Primary entities: {len(current_primary_entities)} ->"
                    f" {len(proposed_primary_entities)}"
                )
            )

    current_corroboration_bucket = str(target_cfg.get("corroboration_bucket") or "").strip()
    proposed_corroboration_bucket = str(cfg.get("corroboration_bucket") or "").strip()
    if current_corroboration_bucket or proposed_corroboration_bucket:
        if current_corroboration_bucket != proposed_corroboration_bucket:
            details.append(
                f"Bucket corroborante: {current_corroboration_bucket} -> {proposed_corroboration_bucket}"
                if is_it
                else (
                    "Corroboration bucket: "
                    f"{current_corroboration_bucket} -> {proposed_corroboration_bucket}"
                )
            )
    current_corroboration_match_mode = str(
        target_cfg.get("corroboration_bucket_match_mode") or ""
    ).strip()
    proposed_corroboration_match_mode = str(
        cfg.get("corroboration_bucket_match_mode") or ""
    ).strip()
    if current_corroboration_match_mode or proposed_corroboration_match_mode:
        current_corroboration_match_label = _bucket_match_mode_label(
            current_corroboration_match_mode, language=language
        )
        proposed_corroboration_match_label = _bucket_match_mode_label(
            proposed_corroboration_match_mode, language=language
        )
        if current_corroboration_match_mode != proposed_corroboration_match_mode:
            details.append(
                "Match corroborante: "
                f"{current_corroboration_match_label} -> {proposed_corroboration_match_label}"
                if is_it
                else (
                    "Corroborating bucket match: "
                    f"{current_corroboration_match_label} -> {proposed_corroboration_match_label}"
                )
            )

    current_corroboration_threshold = target_cfg.get(
        "corroboration_threshold", target_cfg.get("corroboration_rise_threshold")
    )
    proposed_corroboration_threshold = cfg.get(
        "corroboration_threshold", cfg.get("corroboration_rise_threshold")
    )
    if (
        _is_room_cooling_assist_type(reaction_type)
        and not (current_corroboration_bucket or proposed_corroboration_bucket)
        and current_corroboration_threshold
        not in (
            None,
            "",
        )
        and proposed_corroboration_threshold
        not in (
            None,
            "",
        )
    ):
        if str(current_corroboration_threshold) != str(proposed_corroboration_threshold):
            details.append(
                f"Soglia corroborante: {current_corroboration_threshold} -> {proposed_corroboration_threshold}"
                if is_it
                else (
                    "Corroboration threshold: "
                    f"{current_corroboration_threshold} -> {proposed_corroboration_threshold}"
                )
            )

    current_corroboration_mode = str(
        target_cfg.get("corroboration_threshold_mode") or "rise"
    ).strip()
    proposed_corroboration_mode = str(cfg.get("corroboration_threshold_mode") or "rise").strip()
    if (
        _is_room_cooling_assist_type(reaction_type)
        and not (current_corroboration_bucket or proposed_corroboration_bucket)
        and current_corroboration_mode != proposed_corroboration_mode
    ):
        current_label = flow._signal_threshold_mode_options().get(  # noqa: SLF001
            current_corroboration_mode, current_corroboration_mode
        )
        proposed_label = flow._signal_threshold_mode_options().get(  # noqa: SLF001
            proposed_corroboration_mode, proposed_corroboration_mode
        )
        details.append(
            f"Modo corroborante: {current_label} -> {proposed_label}"
            if is_it
            else f"Corroboration mode: {current_label} -> {proposed_label}"
        )

    current_corroboration_entities = target_cfg.get("corroboration_signal_entities")
    proposed_corroboration_entities = cfg.get("corroboration_signal_entities")
    if isinstance(current_corroboration_entities, list) and isinstance(
        proposed_corroboration_entities, list
    ):
        if len(current_corroboration_entities) != len(proposed_corroboration_entities):
            details.append(
                (
                    "Entità corroboranti: "
                    f"{len(current_corroboration_entities)} -> {len(proposed_corroboration_entities)}"
                )
                if is_it
                else (
                    "Corroboration entities: "
                    f"{len(current_corroboration_entities)} -> {len(proposed_corroboration_entities)}"
                )
            )

    current_steps = target_cfg.get("steps")
    proposed_steps = cfg.get("steps")
    if isinstance(current_steps, list) and isinstance(proposed_steps, list):
        if len(current_steps) != len(proposed_steps):
            details.append(
                f"Azioni: {len(current_steps)} -> {len(proposed_steps)}"
                if is_it
                else f"Actions: {len(current_steps)} -> {len(proposed_steps)}"
            )

    return details


def present_room_signal_assist_proposal_label(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
) -> str | None:
    room_id = str(cfg.get("room_id") or "").strip()
    if not room_id:
        return None
    primary_signal_name = _human_signal_name(str(cfg.get("primary_signal_name") or "").strip())
    if primary_signal_name:
        return f"Assist {room_id} · {primary_signal_name}"
    return f"Assist {room_id}"


def _human_signal_name(signal_name: str) -> str:
    clean = str(signal_name or "").strip()
    if clean == "room_humidity":
        return "humidity"
    if clean == "room_temperature":
        return "temperature"
    if clean == "room_co2":
        return "co2"
    return clean


def present_room_signal_assist_review_title(
    flow: Any,
    proposal: Any,
    cfg: dict[str, Any],
    language: str,
    is_followup: bool,
) -> str | None:
    if str(getattr(proposal, "origin", "") or "") == "admin_authored":
        return None
    title = present_room_signal_assist_proposal_label(flow, proposal, cfg, language)
    if not title:
        return None
    if language.startswith("it"):
        return f"Affinamento assist: {title}" if is_followup else f"Nuovo assist: {title}"
    return f"Assist tuning: {title}" if is_followup else f"New assist: {title}"
