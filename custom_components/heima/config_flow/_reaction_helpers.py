"""Shared helper functions for reaction options flow modules."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from ..runtime.analyzers.base import ReactionProposal
from ..runtime.proposal_engine import ActivityProposal


def house_state_proposal_review_details(
    proposal: ReactionProposal,
    cfg: dict[str, Any],
    *,
    is_it: bool,
) -> str:
    snapshot = safe_mapping(cfg.get("context_snapshot"))
    predicted_state = str(snapshot.get("predicted_state") or cfg.get("predicted_state") or "")
    weekday = snapshot.get("weekday")
    hour_bucket = snapshot.get("hour_bucket")
    rooms_raw = snapshot.get("rooms")
    rooms = ", ".join(str(room) for room in rooms_raw) if isinstance(rooms_raw, list) else ""
    anyone_home = bool(snapshot.get("anyone_home"))
    support = cfg.get("support")
    total = cfg.get("total")

    lines = [
        (
            "Tipo proposta: contesto appreso per stato casa"
            if is_it
            else "Proposal type: learned house-state context"
        )
    ]
    if predicted_state:
        lines.append(
            f"Stato previsto: {predicted_state}" if is_it else f"Predicted state: {predicted_state}"
        )
    if weekday not in (None, ""):
        weekday_label = _weekday_label(weekday, is_it=is_it)
        lines.append(f"Giorno: {weekday_label}" if is_it else f"Weekday: {weekday_label}")
    if hour_bucket not in (None, ""):
        hour_label = _hour_bucket_label(hour_bucket)
        lines.append(f"Ora: {hour_label}" if is_it else f"Hour: {hour_label}")
    if rooms:
        lines.append(f"Stanze: {rooms}" if is_it else f"Rooms: {rooms}")
    lines.append(
        ("Presenza: qualcuno in casa" if anyone_home else "Presenza: nessuno in casa")
        if is_it
        else ("Presence: someone home" if anyone_home else "Presence: nobody home")
    )
    if support not in (None, "") and total not in (None, ""):
        lines.append(
            f"Evidenza: {support}/{total} osservazioni"
            if is_it
            else f"Evidence: {support}/{total} observations"
        )
    lines.append(
        f"Affidabilità: {proposal.confidence:.0%}"
        if is_it
        else f"Confidence: {proposal.confidence:.0%}"
    )
    return "\n".join(lines)


def activity_proposal_review_details(
    proposal: ActivityProposal,
    *,
    is_it: bool,
) -> str:
    pattern = ", ".join(sorted(proposal.primitive_pattern))
    context = safe_mapping(proposal.context_conditions)
    lines = [
        (
            "Tipo proposta: attivita composita appresa"
            if is_it
            else "Proposal type: learned composite activity"
        )
    ]
    lines.append(
        f"Attivita: {proposal.activity_name}" if is_it else f"Activity: {proposal.activity_name}"
    )
    if pattern:
        lines.append(f"Pattern: {pattern}")
    room_id = str(context.get("room_id") or "").strip()
    if room_id:
        lines.append(f"Stanza: {room_id}" if is_it else f"Room: {room_id}")
    hour_range = context.get("hour_range")
    if isinstance(hour_range, list | tuple) and len(hour_range) == 2:
        lines.append(
            f"Ora: {hour_range[0]}-{hour_range[1]}"
            if is_it
            else f"Hour: {hour_range[0]}-{hour_range[1]}"
        )
    lines.append(
        f"Evidenza: {proposal.occurrence_count} osservazioni"
        if is_it
        else f"Evidence: {proposal.occurrence_count} observations"
    )
    lines.append(
        f"Affidabilità: {proposal.confidence:.0%}"
        if is_it
        else f"Confidence: {proposal.confidence:.0%}"
    )
    return "\n".join(lines)


def proposal_review_type(proposal: object) -> str:
    proposal_type = str(getattr(proposal, "proposal_type", "") or "").strip()
    if proposal_type:
        return proposal_type
    return str(getattr(proposal, "reaction_type", "") or "").strip()


def format_last_seen(value: str) -> str:
    try:
        return datetime.fromisoformat(value).date().isoformat()
    except (TypeError, ValueError):
        return ""


def safe_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    return {}


def _weekday_label(weekday: Any, *, is_it: bool) -> str:
    it_days = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
    en_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    try:
        index = int(weekday)
    except (TypeError, ValueError):
        return str(weekday)
    if 0 <= index <= 6:
        return it_days[index] if is_it else en_days[index]
    return str(weekday)


def parse_hhmm_to_min(value: str) -> int | None:
    raw = value.strip()
    if not raw or ":" not in raw:
        return None
    hour_str, minute_str = raw.split(":", 1)
    try:
        hour = int(hour_str)
        minute = int(minute_str)
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _hour_bucket_label(value: Any) -> str:
    try:
        hour = float(value)
    except (TypeError, ValueError):
        return str(value)
    whole_hour = int(hour)
    minute = round((hour - whole_hour) * 60)
    if minute == 60:
        whole_hour += 1
        minute = 0
    return f"{whole_hour % 24:02d}:{minute:02d}"


def format_min_to_hhmm(value: int) -> str:
    minute_of_day = max(0, min(int(value), 23 * 60 + 59))
    return f"{minute_of_day // 60:02d}:{minute_of_day % 60:02d}"


def coarse_numeric_bucket(value: Any, *, step: int) -> int | None:
    if not isinstance(value, (int, float)):
        return None
    return int(round(float(value) / step) * step)


def normalize_rgb(value: Any) -> str | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    try:
        return ",".join(str(int(channel)) for channel in value)
    except (TypeError, ValueError):
        return None
