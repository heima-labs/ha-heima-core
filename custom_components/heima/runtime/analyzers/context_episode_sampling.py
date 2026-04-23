"""Context-conditioned lighting episode sampling helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..event_store import HeimaEvent


@dataclass(frozen=True)
class LightingEpisodeSample:
    """One comparable lighting episode around a learned scene window."""

    ts: str
    room_id: str
    weekday: int
    minute_of_day: int
    scene_signature: tuple[tuple[Any, ...], ...]
    context_signals: dict[str, str]
    matches_target_scene: bool


@dataclass(frozen=True)
class LightingContextDataset:
    """Positive/negative comparable episodes for one learned lighting scene."""

    positive_episodes: tuple[LightingEpisodeSample, ...]
    negative_episodes: tuple[LightingEpisodeSample, ...]


def build_lighting_context_dataset(
    *,
    events: list[HeimaEvent],
    room_id: str,
    weekday: int,
    scheduled_min: int,
    window_half_min: int,
    entity_steps: list[dict[str, Any]],
) -> LightingContextDataset:
    """Build comparable positive/negative episodes around one learned scene window.

    Phase 2 intentionally uses bounded observed evidence only:
    - same room
    - same weekday
    - minute_of_day within the comparable schedule window
    - grouped by exact timestamp
    """

    target_signature = lighting_steps_signature(entity_steps)
    grouped: dict[str, list[HeimaEvent]] = {}

    for event in events:
        if event.event_type != "lighting" or event.source != "user":
            continue
        if event.room_id != room_id or event.context.weekday != weekday:
            continue
        if abs(int(event.context.minute_of_day) - int(scheduled_min)) > int(window_half_min):
            continue
        grouped.setdefault(event.ts, []).append(event)

    positive: list[LightingEpisodeSample] = []
    negative: list[LightingEpisodeSample] = []

    for ts in sorted(grouped):
        group = grouped[ts]
        if not group:
            continue
        signature = lighting_events_signature(group)
        if not signature:
            continue
        sample = LightingEpisodeSample(
            ts=ts,
            room_id=room_id,
            weekday=weekday,
            minute_of_day=int(group[0].context.minute_of_day),
            scene_signature=signature,
            context_signals=canonicalize_context_snapshot(group[0].context.signals),
            matches_target_scene=signature == target_signature,
        )
        if sample.matches_target_scene:
            positive.append(sample)
        else:
            negative.append(sample)

    return LightingContextDataset(
        positive_episodes=tuple(positive),
        negative_episodes=tuple(negative),
    )


def canonicalize_context_snapshot(signals: Mapping[str, str]) -> dict[str, str]:
    """Map raw configured context entities to abstract signal names and bounded states."""

    canonical: dict[str, str] = {}
    for entity_id, raw_state in signals.items():
        signal_name = canonical_context_signal_name(entity_id)
        state = canonical_context_state(raw_state)
        if not signal_name or not state:
            continue
        canonical[signal_name] = state
    return canonical


def canonical_context_signal_name(entity_id: str) -> str | None:
    clean = str(entity_id or "").strip().lower()
    if "." not in clean:
        return None
    _, object_id = clean.split(".", 1)
    object_id = object_id.strip("_")
    if not object_id:
        return None
    return f"{object_id}_context"


def canonical_context_state(raw_state: Any) -> str | None:
    clean = str(raw_state or "").strip().lower()
    if not clean:
        return None
    if clean in {"on", "playing", "active", "open", "home", "detected", "occupied"}:
        return "active"
    if clean in {"idle", "paused"}:
        return "idle"
    if clean in {"background"}:
        return "background"
    if clean in {"off", "inactive", "closed", "not_home", "clear", "standby", "unknown"}:
        return "inactive"
    return None


def lighting_events_signature(events: list[HeimaEvent]) -> tuple[tuple[Any, ...], ...]:
    steps: list[dict[str, Any]] = []
    for event in events:
        entity_id = str(event.data.get("entity_id") or event.subject_id or "").strip()
        action = str(event.data.get("action") or "").strip()
        if not entity_id or action not in {"on", "off"}:
            continue
        steps.append(
            {
                "entity_id": entity_id,
                "action": action,
                "brightness": event.data.get("brightness") if action == "on" else None,
                "color_temp_kelvin": (
                    event.data.get("color_temp_kelvin") if action == "on" else None
                ),
                "rgb_color": event.data.get("rgb_color") if action == "on" else None,
            }
        )
    return lighting_steps_signature(steps)


def lighting_steps_signature(entity_steps: list[dict[str, Any]]) -> tuple[tuple[Any, ...], ...]:
    signature: list[tuple[Any, ...]] = []
    for step in entity_steps:
        signature.append(
            (
                str(step.get("entity_id") or ""),
                str(step.get("action") or ""),
                step.get("brightness"),
                step.get("color_temp_kelvin"),
                tuple(step.get("rgb_color") or []) or None,
            )
        )
    return tuple(sorted(signature))
