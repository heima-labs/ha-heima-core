#!/usr/bin/env python3
"""Live reaction debugger for Heima.

Polls HA diagnostics and entity states to help inspect one configured reaction
while it is firing, pending, suppressed, or blocked.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import os
from pathlib import Path
import sys
import time
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib.ha_client import HAApiError, HAClient


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _as_bool_str(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _truncate(value: Any, limit: int = 120) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _format_ts(value: Any, *, full: bool) -> str:
    text = str(value or "").strip()
    if not text or text == "-":
        return "-"
    if isinstance(value, (int, float)):
        return text if full else "-"
    if full:
        return text
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return text


def _since_s(value: Any) -> str:
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return "-"
    delta = time.monotonic() - raw
    if delta < 0:
        return "0s"
    return f"{int(delta)}s"


def _short_iso(value: Any) -> str:
    """Return HH:MM:SS from an ISO timestamp string, or '-' if absent."""
    if not value:
        return "-"
    s = str(value)
    # extract HH:MM:SS from "2026-04-16T14:53:49.123456"
    try:
        return s[11:19]
    except IndexError:
        return s


def _clear_screen() -> None:
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _should_clear_screen(clear_requested: bool) -> bool:
    return bool(clear_requested) and sys.stdout.isatty()


def _extract_runtime(diag: dict[str, Any]) -> dict[str, Any]:
    data = _safe_dict(diag.get("data"))
    return _safe_dict(data.get("runtime"))


def _reaction_sensor_payload(client: HAClient) -> tuple[str, dict[str, Any]]:
    state = client.get_state("sensor.heima_reactions_active")
    attrs = _safe_dict(state.get("attributes"))
    reactions = _safe_dict(attrs.get("reactions"))
    return str(state.get("state") or ""), reactions


def _labels_map(diag: dict[str, Any]) -> dict[str, str]:
    data = _safe_dict(diag.get("data"))
    entry = _safe_dict(data.get("entry"))
    options = _safe_dict(entry.get("options"))
    reactions = _safe_dict(options.get("reactions"))
    raw = _safe_dict(reactions.get("labels"))
    result: dict[str, str] = {}
    for reaction_id, label in raw.items():
        rid = str(reaction_id).strip()
        if rid:
            result[rid] = str(label)
    return result


def _entry_options(diag: dict[str, Any]) -> dict[str, Any]:
    data = _safe_dict(diag.get("data"))
    entry = _safe_dict(data.get("entry"))
    return _safe_dict(entry.get("options"))


def _room_cfg_from_options(options: dict[str, Any], room_id: str) -> dict[str, Any]:
    for room in _safe_list(options.get("rooms")):
        if not isinstance(room, dict):
            continue
        if str(room.get("room_id") or "").strip() == room_id:
            return dict(room)
    return {}


def _reaction_cfg_from_options(options: dict[str, Any], reaction_id: str) -> dict[str, Any]:
    reactions = _safe_dict(options.get("reactions"))
    configured = _safe_dict(reactions.get("configured"))
    cfg = configured.get(reaction_id)
    return dict(cfg) if isinstance(cfg, dict) else {}


def _runtime_reaction_labels(
    reactions_payload: dict[str, Any],
    reactions_diag: dict[str, Any],
    stored_labels: dict[str, str],
) -> dict[str, str]:
    labels: dict[str, str] = dict(stored_labels)
    all_ids = set(reactions_payload) | set(reactions_diag)
    for reaction_id in sorted(all_ids):
        if labels.get(reaction_id):
            continue
        state = _safe_dict(reactions_payload.get(reaction_id))
        diag = _safe_dict(reactions_diag.get(reaction_id))
        reaction_type = str(state.get("reaction_type") or "").strip()
        room_id = str(diag.get("room_id") or "").strip() or reaction_id
        primary_entities = _safe_list(diag.get("primary_entities"))
        trigger_entities = _safe_list(diag.get("trigger_signal_entities"))
        primary_count = len(primary_entities or trigger_entities)
        entity_steps = diag.get("entity_steps")

        if reaction_type == "room_darkness_lighting_assist":
            parts = [f"Luce {room_id}"]
            if primary_count > 0:
                parts.append(f"lux:{primary_count}")
            if isinstance(entity_steps, int) and entity_steps > 0:
                parts.append(f"{entity_steps} entita")
            labels[reaction_id] = " - ".join(parts)
            continue

        if reaction_type in {
            "room_signal_assist",
            "room_cooling_assist",
            "room_air_quality_assist",
        }:
            parts = [f"Assist {room_id}"]
            if primary_count > 0:
                parts.append(f"signals:{primary_count}")
            labels[reaction_id] = " - ".join(parts)
            continue

        if reaction_type:
            labels[reaction_id] = f"{reaction_type} - {room_id}"
        else:
            labels[reaction_id] = reaction_id
    return labels


def _available_reaction_candidates(labels_map: dict[str, str]) -> str:
    if not labels_map:
        return "none"
    items = [f"{reaction_id} [{label}]" if label else reaction_id for reaction_id, label in sorted(labels_map.items())]
    return ", ".join(items[:12])


def _match_reaction_id(
    *,
    reactions_payload: dict[str, Any],
    labels_map: dict[str, str],
    requested_id: str | None,
    label_contains: str | None,
) -> str:
    if requested_id:
        if requested_id in reactions_payload:
            return requested_id
        raise HAApiError(f"reaction_id not found in sensor.heima_reactions_active: {requested_id}")

    if label_contains:
        needle = label_contains.strip().lower()
        for reaction_id in sorted(reactions_payload):
            label = labels_map.get(reaction_id, "")
            haystacks = [
                reaction_id.lower(),
                label.lower(),
                str(reactions_payload.get(reaction_id)).lower(),
            ]
            if any(needle in haystack for haystack in haystacks):
                return reaction_id
        raise HAApiError(
            f"no reaction label contains: {label_contains!r}. available: {_available_reaction_candidates(labels_map)}"
        )

    if len(reactions_payload) == 1:
        return next(iter(reactions_payload))

    raise HAApiError(
        "multiple configured reactions found: pass --reaction-id or --label-contains. "
        + f"available: {_available_reaction_candidates(labels_map)}"
    )


def _find_reaction_plan_steps(
    apply_plan_steps: list[dict[str, Any]],
    reaction_id: str,
) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    reason_token = f":{reaction_id}"
    for step in apply_plan_steps:
        if not isinstance(step, dict):
            continue
        reason = str(step.get("reason") or "")
        params = _safe_dict(step.get("params"))
        target = str(step.get("target") or "")
        if reason.endswith(reason_token) or reaction_id in reason or target == reaction_id:
            matched.append(step)
            continue
        if reaction_id in str(params):
            matched.append(step)
    return matched


def _reaction_event_match(last_event: dict[str, Any], reaction_id: str) -> bool:
    if str(last_event.get("type") or "") != "reaction.fired":
        return False
    context = _safe_dict(last_event.get("context"))
    return str(context.get("reaction_id") or "") == reaction_id


def _collect_entity_states(client: HAClient, entity_ids: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for entity_id in entity_ids:
        try:
            state = client.get_state(entity_id)
            rows.append(
                {
                    "entity_id": entity_id,
                    "state": state.get("state"),
                    "attributes": _safe_dict(state.get("attributes")),
                    "last_changed": state.get("last_changed"),
                }
            )
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "entity_id": entity_id,
                    "error": str(exc),
                }
            )
    return rows


def _canonical_entity_ids_for_room(room_id: str) -> list[str]:
    rid = str(room_id or "").strip()
    if not rid:
        return []
    return [
        f"binary_sensor.heima_occupancy_{rid}",
        f"sensor.heima_occupancy_{rid}_source",
        f"sensor.heima_occupancy_{rid}_last_change",
        f"binary_sensor.heima_lighting_hold_{rid}",
        "sensor.heima_security_state",
        "sensor.heima_security_reason",
        "sensor.heima_house_state",
        "sensor.heima_house_state_reason",
    ]


def _room_input_entity_ids(room_cfg: dict[str, Any]) -> list[str]:
    entity_ids: list[str] = []
    for key in ("occupancy_sources", "learning_sources", "sources"):
        for value in _safe_list(room_cfg.get(key)):
            entity_id = str(value).strip()
            if entity_id:
                entity_ids.append(entity_id)
    seen: set[str] = set()
    result: list[str] = []
    for entity_id in entity_ids:
        if entity_id not in seen:
            seen.add(entity_id)
            result.append(entity_id)
    return result


def _auto_entity_ids(
    reaction_diag: dict[str, Any],
    reaction_state: dict[str, Any],
    plan_steps: list[dict[str, Any]],
    room_cfg: dict[str, Any],
) -> list[str]:
    entity_ids: list[str] = []
    room_id = str(reaction_diag.get("room_id") or "").strip()

    entity_ids.extend(_canonical_entity_ids_for_room(room_id))
    entity_ids.extend(_room_input_entity_ids(room_cfg))

    for key in (
        "primary_entities",
        "corroboration_entities",
        "trigger_signal_entities",
        "humidity_entities",
        "temperature_entities",
        "entity_step_ids",
    ):
        for value in _safe_list(reaction_diag.get(key)):
            entity_id = str(value).strip()
            if entity_id:
                entity_ids.append(entity_id)

    for step in plan_steps:
        params = _safe_dict(step.get("params"))
        entity_id = str(params.get("entity_id") or "").strip()
        if entity_id:
            entity_ids.append(entity_id)

    source_template_id = str(reaction_state.get("source_template_id") or "").strip()
    if source_template_id:
        entity_ids.append(f"template:{source_template_id}")

    seen: set[str] = set()
    result: list[str] = []
    for entity_id in entity_ids:
        if entity_id.startswith("template:"):
            continue
        if entity_id not in seen:
            seen.add(entity_id)
            result.append(entity_id)
    return result


def _summary_reasoning(
    *,
    reaction_id: str,
    reaction_state: dict[str, Any],
    reaction_diag: dict[str, Any],
    current_primary_bucket: str | None,
    snapshot: dict[str, Any],
    matched_plan_steps: list[dict[str, Any]],
    active_constraints: list[str],
    last_event: dict[str, Any],
    guard_diag: dict[str, Any] | None = None,
) -> list[str]:
    reasons: list[str] = []
    room_id = str(reaction_diag.get("room_id") or "").strip()
    occupied_rooms = [str(item) for item in _safe_list(snapshot.get("occupied_rooms"))]

    if not reaction_state:
        return [f"reaction {reaction_id} not present in heima_reactions_active"]
    if bool(reaction_state.get("muted")):
        reasons.append("reaction is muted")
    if room_id and room_id not in occupied_rooms:
        reasons.append(f"room {room_id!r} not in snapshot.occupied_rooms")
    expected_primary_bucket = str(reaction_diag.get("primary_bucket") or "").strip()
    if (
        expected_primary_bucket
        and current_primary_bucket
        and not _bucket_matches_reaction_config(
            current_bucket=current_primary_bucket,
            expected_bucket=expected_primary_bucket,
            match_mode=str(reaction_diag.get("primary_bucket_match_mode") or "eq"),
            bucket_labels=[str(v) for v in _safe_list(reaction_diag.get("primary_bucket_labels"))],
        )
    ):
        reasons.append(
            f"current primary bucket is {current_primary_bucket!r}, expected {expected_primary_bucket!r}"
        )
    if reaction_diag.get("pending_episode"):
        reasons.append("matcher has a pending episode")
    if reaction_diag.get("steady_condition_active") is False and reaction_diag.get("primary_bucket"):
        reasons.append("steady bucket condition not active yet")
    if not matched_plan_steps:
        reasons.append("reaction has no current step in apply_plan")
    if active_constraints:
        reasons.append("constraints active: " + ", ".join(active_constraints))
    if guard_diag:
        guard_blocked_total = int(guard_diag.get("blocked_total") or 0)
        room_id_local = str(reaction_diag.get("room_id") or "").strip()
        manual_hold_rooms = [str(r) for r in _safe_list(guard_diag.get("manual_hold_rooms"))]
        if room_id_local in manual_hold_rooms:
            reasons.append(f"manual hold enabled for room '{room_id_local}' (check binary_sensor.heima_lighting_hold_{room_id_local})")
        if guard_blocked_total > 0:
            reasons.append(f"lighting_reaction_guard blocked {guard_blocked_total} step(s) total (manual hold active at fire time)")
    if _reaction_event_match(last_event, reaction_id):
        reasons.append("last emitted event confirms reaction.fired")
    else:
        reasons.append("last emitted event is not reaction.fired for this reaction")
    return reasons


def _compute_verdict(
    *,
    reaction_id: str,
    reaction_state: dict[str, Any],
    reaction_diag: dict[str, Any],
    current_primary_bucket: str | None,
    snapshot: dict[str, Any],
    matched_plan_steps: list[dict[str, Any]],
    active_constraints: list[str],
    last_event: dict[str, Any],
    guard_diag: dict[str, Any] | None = None,
) -> str:
    room_id = str(reaction_diag.get("room_id") or "").strip()
    occupied_rooms = [str(item) for item in _safe_list(snapshot.get("occupied_rooms"))]
    expected_primary_bucket = str(reaction_diag.get("primary_bucket") or "").strip()

    if not reaction_state:
        return "reaction_missing"
    if bool(reaction_state.get("muted")):
        return "muted"
    if room_id and room_id not in occupied_rooms:
        return "idle_waiting_occupancy"
    if active_constraints and matched_plan_steps:
        return "blocked_by_constraints"
    if (
        expected_primary_bucket
        and current_primary_bucket
        and not _bucket_matches_reaction_config(
            current_bucket=current_primary_bucket,
            expected_bucket=expected_primary_bucket,
            match_mode=str(reaction_diag.get("primary_bucket_match_mode") or "eq"),
            bucket_labels=[str(v) for v in _safe_list(reaction_diag.get("primary_bucket_labels"))],
        )
    ):
        return "idle_waiting_bucket"
    if reaction_diag.get("pending_episode"):
        return "pending_episode"
    if guard_diag and int(guard_diag.get("blocked_total") or 0) > 0 and not matched_plan_steps:
        room_id_local = str(reaction_diag.get("room_id") or "").strip()
        blocked_by_room = _safe_dict(guard_diag.get("blocked_by_room"))
        if room_id_local and int(blocked_by_room.get(room_id_local) or 0) > 0:
            return "blocked_by_manual_hold"
    if int(reaction_diag.get("suppressed_count") or 0) > 0 and not matched_plan_steps:
        return "suppressed_cooldown"
    if matched_plan_steps and any(str(step.get("blocked_by") or "").strip() for step in matched_plan_steps):
        return "blocked_by_constraints"
    if matched_plan_steps:
        return "ready_apply_plan_present"
    if _reaction_event_match(last_event, reaction_id):
        return "fired_recently"
    if reaction_diag.get("steady_condition_active"):
        return "steady_condition_active"
    return "idle_waiting_trigger"


def _bucket_matches_reaction_config(
    *,
    current_bucket: str,
    expected_bucket: str,
    match_mode: str,
    bucket_labels: list[str],
) -> bool:
    current = str(current_bucket or "").strip()
    expected = str(expected_bucket or "").strip()
    normalized_mode = str(match_mode or "eq").strip().lower()
    if not current or not expected:
        return False
    if normalized_mode == "eq":
        return current == expected
    try:
        current_index = bucket_labels.index(current)
        expected_index = bucket_labels.index(expected)
    except ValueError:
        return current == expected
    if normalized_mode == "lte":
        return current_index <= expected_index
    if normalized_mode == "gte":
        return current_index >= expected_index
    return current == expected


def _print_header(
    *,
    base_url: str,
    reaction_id: str,
    label: str,
    interval_s: float,
    iteration: int,
    watch_friendly: bool,
) -> None:
    if not watch_friendly:
        print(f"Heima Reaction Live Debug  interval={interval_s:.1f}s  tick={iteration}")
        print(f"HA: {base_url}")
    else:
        print("Heima Reaction Live Debug")
    print(f"Reaction: {reaction_id}")
    if label:
        print(f"Label: {label}")
    print()


def _print_assessment(verdict: str, reasons: list[str]) -> None:
    print("[assessment]")
    print(f"  verdict={verdict}")
    if not reasons:
        print("  why=-")
        print()
        return
    print("  why:")
    for item in reasons:
        print(f"    - {item}")
    print()


def _print_reaction_status(
    reaction_state: dict[str, Any],
    reaction_diag: dict[str, Any],
    current_primary_bucket: str | None,
    *,
    full_timestamps: bool,
) -> None:
    print("[reaction]")
    print(
        "  "
        + " | ".join(
            [
                f"type={reaction_state.get('reaction_type') or '-'}",
                f"muted={_as_bool_str(reaction_state.get('muted'))}",
                f"origin={reaction_state.get('origin') or '-'}",
                f"fire_count={reaction_diag.get('fire_count', 0)}",
                f"suppressed_count={reaction_diag.get('suppressed_count', 0)}",
                (
                    f"last_fired={reaction_diag.get('last_fired_iso') or '-'}"
                    if full_timestamps
                    else f"last_fired={_short_iso(reaction_diag.get('last_fired_iso'))}"
                ),
            ]
        )
    )
    print(
        "  "
        + " | ".join(
            [
                f"room_id={reaction_diag.get('room_id') or '-'}",
                f"primary_bucket={reaction_diag.get('primary_bucket') or '-'}",
                f"primary_bucket_match_mode={reaction_diag.get('primary_bucket_match_mode') or '-'}",
                f"current_primary_bucket={current_primary_bucket or '-'}",
                f"pending_episode={_format_ts(reaction_diag.get('pending_episode') or '-', full=full_timestamps)}",
                f"steady_condition_active={_as_bool_str(reaction_diag.get('steady_condition_active'))}",
            ]
        )
    )
    entity_step_ids = [str(e) for e in _safe_list(reaction_diag.get("entity_step_ids")) if str(e).strip()]
    if entity_step_ids:
        print(f"  entity_step_ids={', '.join(entity_step_ids)}")
    print()


def _print_runtime_snapshot(
    snapshot: dict[str, Any],
    active_constraints: list[str],
    *,
    full_timestamps: bool,
    options: dict[str, Any] | None = None,
) -> None:
    print("[snapshot]")
    print(
        "  "
        + " | ".join(
            [
                f"ts={_format_ts(snapshot.get('ts') or '-', full=full_timestamps)}",
                f"house_state={snapshot.get('house_state') or '-'}",
                f"anyone_home={_as_bool_str(snapshot.get('anyone_home'))}",
                f"people_count={snapshot.get('people_count') or 0}",
                f"security_state={snapshot.get('security_state') or '-'}",
            ]
        )
    )
    occupied = ", ".join(str(item) for item in _safe_list(snapshot.get("occupied_rooms"))) or "-"
    constraints = ", ".join(active_constraints) or "-"
    print(f"  occupied_rooms={occupied}")
    print(f"  active_constraints={constraints}")
    if options is not None:
        engine_enabled = bool(options.get("engine_enabled", True))
        apply_mode = str(options.get("lighting_apply_mode") or "scene")
        print(f"  engine_enabled={_as_bool_str(engine_enabled)} | lighting_apply_mode={apply_mode}")
    print()


def _print_canonical_buckets(
    *,
    room_id: str,
    bucket_state: dict[str, Any],
    burst_baseline: dict[str, Any],
    last_burst_ts: dict[str, Any],
    full_timestamps: bool,
) -> None:
    print("[canonical_buckets]")
    if not room_id:
        print("  room_id unavailable")
        print()
        return
    room_prefix = f"{room_id}:"
    room_buckets = {
        key: value for key, value in bucket_state.items() if str(key).startswith(room_prefix)
    }
    if not room_buckets:
        print("  no canonical bucket state found for this room")
        print()
        return
    for key, value in sorted(room_buckets.items()):
        baseline = burst_baseline.get(key)
        last_burst = last_burst_ts.get(key)
        suffix_parts: list[str] = []
        if baseline not in (None, "", {}):
            suffix_parts.append(f"burst_baseline={baseline}")
        if last_burst not in (None, "", {}):
            suffix_parts.append(
                f"last_burst_ts={_format_ts(last_burst, full=full_timestamps)}"
            )
        suffix = " | " + " | ".join(suffix_parts) if suffix_parts else ""
        print(f"  {key}={value}{suffix}")
    print()


def _print_plan_steps(matched_plan_steps: list[dict[str, Any]]) -> None:
    print("[apply_plan]")
    if not matched_plan_steps:
        print("  no step currently attributable to this reaction")
        print()
        return
    for index, step in enumerate(matched_plan_steps[:8], start=1):
        params = _safe_dict(step.get("params"))
        print(
            "  "
            + f"{index}. domain={step.get('domain') or '-'} "
            + f"action={step.get('action') or '-'} "
            + f"target={step.get('target') or '-'} "
            + f"entity_id={params.get('entity_id') or '-'} "
            + f"blocked_by={step.get('blocked_by') or '-'} "
            + f"reason={_truncate(step.get('reason') or '-', 90)}"
        )
    print()


def _print_event_state(
    last_event_state: dict[str, Any],
    event_store_state: dict[str, Any],
    *,
    full_timestamps: bool,
) -> None:
    print("[events]")
    last_attrs = _safe_dict(last_event_state.get("attributes"))
    last_context = _safe_dict(last_attrs.get("context"))
    print(
        "  "
        + " | ".join(
            [
                f"last_type={last_attrs.get('type') or last_event_state.get('state') or '-'}",
                f"ts={_format_ts(last_attrs.get('ts') or '-', full=full_timestamps)}",
                f"key={last_attrs.get('key') or '-'}",
                f"reaction_id={last_context.get('reaction_id') or '-'}",
                f"step_count={last_context.get('step_count') or '-'}",
            ]
        )
    )
    store_attrs = _safe_dict(event_store_state.get("attributes"))
    by_type = _safe_dict(store_attrs.get("event_type_counts"))
    if by_type:
        compact = ", ".join(f"{key}={value}" for key, value in sorted(by_type.items())[:8])
        print(f"  event_type_counts={compact}")
    print()


def _print_entities(entity_rows: list[dict[str, Any]], *, full_timestamps: bool) -> None:
    print("[entities]")
    if not entity_rows:
        print("  none")
        print()
        return
    for row in entity_rows:
        entity_id = row.get("entity_id") or "-"
        if row.get("error"):
            print(f"  {entity_id}: ERROR {row['error']}")
            continue
        attrs = _safe_dict(row.get("attributes"))
        detail_parts: list[str] = []
        for key in ("unit_of_measurement", "device_class", "brightness", "color_mode"):
            if key in attrs:
                detail_parts.append(f"{key}={attrs.get(key)}")
        details = " | ".join(detail_parts)
        suffix = f" | {details}" if details else ""
        print(
            f"  {entity_id}: state={row.get('state')} | last_changed={_format_ts(row.get('last_changed') or '-', full=full_timestamps)}{suffix}"
        )
    print()


def _print_entities_compact(entity_rows: list[dict[str, Any]], *, full_timestamps: bool) -> None:
    print("[entities]")
    if not entity_rows:
        print("  none")
        print()
        return
    for row in entity_rows:
        entity_id = row.get("entity_id") or "-"
        if row.get("error"):
            print(f"  {entity_id}: ERROR {row['error']}")
            continue
        print(
            f"  {entity_id}: state={row.get('state')} | last_changed={_format_ts(row.get('last_changed') or '-', full=full_timestamps)}"
        )
    print()


def _print_occupancy_trace(
    room_id: str,
    occupancy_trace: dict[str, Any],
    *,
    full_timestamps: bool,
) -> None:
    if not room_id:
        return
    print("[occupancy_trace]")
    trace = _safe_dict(occupancy_trace.get(room_id))
    if not trace:
        print("  unavailable")
        print()
        return
    print(
        "  "
        + " | ".join(
            [
                f"mode={trace.get('occupancy_mode') or '-'}",
                f"candidate_state={trace.get('candidate_state') or '-'}",
                f"effective_state={trace.get('effective_state') or '-'}",
                f"forced_off_by_max_on={_as_bool_str(trace.get('forced_off_by_max_on'))}",
            ]
        )
    )
    print(
        "  "
        + " | ".join(
            [
                f"candidate_since={_format_ts(trace.get('candidate_since') or '-', full=full_timestamps)}",
                f"effective_since={_format_ts(trace.get('effective_since') or '-', full=full_timestamps)}",
                f"on_dwell_s={trace.get('on_dwell_s') if trace.get('on_dwell_s') is not None else '-'}",
                f"off_dwell_s={trace.get('off_dwell_s') if trace.get('off_dwell_s') is not None else '-'}",
                f"max_on_s={trace.get('max_on_s') if trace.get('max_on_s') not in (None, '') else '-'}",
            ]
        )
    )
    fused = _safe_dict(trace.get("fused_observation"))
    if fused:
        print(
            "  "
            + " | ".join(
                [
                    f"fused_state={fused.get('state') or '-'}",
                    f"plugin_id={trace.get('plugin_id') or '-'}",
                    f"reason={fused.get('reason') or '-'}",
                ]
            )
        )
    print()


def _print_room_inputs(room_cfg: dict[str, Any]) -> None:
    print("[room_inputs]")
    if not room_cfg:
        print("  no room config found for this reaction room")
        print()
        return
    print(
        "  "
        + " | ".join(
            [
                f"room_id={room_cfg.get('room_id') or '-'}",
                f"display_name={room_cfg.get('display_name') or '-'}",
                f"occupancy_mode={room_cfg.get('occupancy_mode') or '-'}",
                f"logic={room_cfg.get('logic') or '-'}",
            ]
        )
    )
    occupancy_sources = ", ".join(_room_input_entity_ids({"occupancy_sources": room_cfg.get("occupancy_sources")})) or "-"
    learning_sources = ", ".join(_room_input_entity_ids({"learning_sources": room_cfg.get("learning_sources")})) or "-"
    print(f"  occupancy_sources={occupancy_sources}")
    print(f"  learning_sources={learning_sources}")
    print()


def _print_persisted_config(reaction_cfg: dict[str, Any]) -> None:
    print("[persisted_config]")
    if not reaction_cfg:
        print("  no persisted config found for this reaction_id")
        print()
        return
    keys = [
        "reaction_type",
        "room_id",
        "primary_signal_name",
        "primary_bucket",
        "primary_bucket_match_mode",
        "origin",
        "author_kind",
        "source_template_id",
        "source_proposal_id",
        "source_proposal_identity_key",
        "created_at",
        "last_tuned_at",
    ]
    summary = [f"{key}={reaction_cfg.get(key)}" for key in keys if reaction_cfg.get(key) not in (None, "", [])]
    if summary:
        print("  " + " | ".join(summary))

    primary_entities = ", ".join(str(v) for v in _safe_list(reaction_cfg.get("primary_signal_entities"))) or "-"
    corroboration_entities = ", ".join(
        str(v) for v in _safe_list(reaction_cfg.get("corroboration_signal_entities"))
    ) or "-"
    print(f"  primary_signal_entities={primary_entities}")
    print(f"  corroboration_signal_entities={corroboration_entities}")

    entity_steps = _safe_list(reaction_cfg.get("entity_steps"))
    if not entity_steps:
        print("  entity_steps=-")
        print()
        return
    print(f"  entity_steps_total={len(entity_steps)}")
    for index, step in enumerate(entity_steps[:8], start=1):
        if not isinstance(step, dict):
            print(f"  {index}. {step}")
            continue
        print(
            "  "
            + f"{index}. entity_id={step.get('entity_id') or '-'} "
            + f"action={step.get('action') or '-'} "
            + f"brightness={step.get('brightness') if step.get('brightness') is not None else '-'} "
            + f"color_temp_kelvin={step.get('color_temp_kelvin') if step.get('color_temp_kelvin') is not None else '-'}"
        )
    print()


def _debug_once(
    client: HAClient,
    *,
    reaction_id: str,
    label: str,
    entity_ids: list[str],
    interval_s: float,
    iteration: int,
    clear: bool,
    verbosity: str,
    watch_friendly: bool,
) -> None:
    diag = client.get(f"/api/diagnostics/config_entry/{client.find_heima_entry_id()}")
    runtime = _extract_runtime(diag)
    options = _entry_options(diag)
    engine = _safe_dict(runtime.get("engine"))
    snapshot = _safe_dict(engine.get("snapshot"))
    reactions_diag = _safe_dict(engine.get("reactions"))
    reaction_diag = _safe_dict(reactions_diag.get(reaction_id))
    reaction_cfg = _reaction_cfg_from_options(options, reaction_id)
    room_cfg = _room_cfg_from_options(options, str(reaction_diag.get("room_id") or ""))
    behaviors = _safe_dict(engine.get("behaviors"))
    canonicalizer = _safe_dict(behaviors.get("event_canonicalizer"))
    guard_diag = _safe_dict(behaviors.get("lighting_reaction_guard"))
    bucket_state = _safe_dict(canonicalizer.get("bucket_state"))
    burst_baseline = _safe_dict(canonicalizer.get("burst_baseline"))
    last_burst_ts = _safe_dict(canonicalizer.get("last_burst_ts"))
    occupancy = _safe_dict(engine.get("occupancy"))
    occupancy_trace = _safe_dict(occupancy.get("room_trace"))
    room_id = str(reaction_diag.get("room_id") or "").strip()
    current_primary_bucket = None
    if room_id:
        current_primary_bucket = str(bucket_state.get(f"{room_id}:room_lux") or "").strip() or None
    apply_plan = _safe_dict(engine.get("apply_plan"))
    apply_plan_steps = _safe_list(apply_plan.get("steps"))
    matched_plan_steps = _find_reaction_plan_steps(apply_plan_steps, reaction_id)
    active_constraints = [str(item) for item in _safe_list(engine.get("active_constraints"))]

    _, reactions_payload = _reaction_sensor_payload(client)
    reaction_state = _safe_dict(reactions_payload.get(reaction_id))

    last_event_state = client.get_state("sensor.heima_last_event")
    event_store_state = client.get_state("sensor.heima_event_store")
    last_event_attrs = _safe_dict(last_event_state.get("attributes"))

    if not entity_ids:
        entity_ids = _auto_entity_ids(reaction_diag, reaction_state, matched_plan_steps, room_cfg)
    entity_rows = _collect_entity_states(client, entity_ids)

    reasons = _summary_reasoning(
        reaction_id=reaction_id,
        reaction_state=reaction_state,
        reaction_diag=reaction_diag,
        current_primary_bucket=current_primary_bucket,
        snapshot=snapshot,
        matched_plan_steps=matched_plan_steps,
        active_constraints=active_constraints,
        last_event=last_event_attrs,
        guard_diag=guard_diag,
    )
    verdict = _compute_verdict(
        reaction_id=reaction_id,
        reaction_state=reaction_state,
        reaction_diag=reaction_diag,
        current_primary_bucket=current_primary_bucket,
        snapshot=snapshot,
        matched_plan_steps=matched_plan_steps,
        active_constraints=active_constraints,
        last_event=last_event_attrs,
        guard_diag=guard_diag,
    )

    if _should_clear_screen(clear):
        _clear_screen()
    _print_header(
        base_url=client.base_url,
        reaction_id=reaction_id,
        label=label,
        interval_s=interval_s,
        iteration=iteration,
        watch_friendly=watch_friendly,
    )
    if verbosity == "full":
        _print_reaction_status(
            reaction_state,
            reaction_diag,
            current_primary_bucket,
            full_timestamps=True,
        )
    else:
        _print_reaction_status(
            reaction_state,
            reaction_diag,
            current_primary_bucket,
            full_timestamps=False,
        )
    _print_runtime_snapshot(snapshot, active_constraints, full_timestamps=verbosity == "full", options=options)
    _print_canonical_buckets(
        room_id=room_id,
        bucket_state=bucket_state,
        burst_baseline=burst_baseline,
        last_burst_ts=last_burst_ts,
        full_timestamps=verbosity == "full",
    )
    if verbosity == "full":
        _print_entities(entity_rows, full_timestamps=True)
    else:
        _print_entities_compact(
            entity_rows if verbosity == "medium" else entity_rows[:8],
            full_timestamps=False,
        )
    if verbosity != "minimal":
        _print_occupancy_trace(
            room_id,
            occupancy_trace,
            full_timestamps=verbosity == "full",
        )
    _print_plan_steps(matched_plan_steps)
    _print_assessment(verdict, reasons)
    if verbosity == "full":
        _print_persisted_config(reaction_cfg)
        _print_room_inputs(room_cfg)
        _print_event_state(last_event_state, event_store_state, full_timestamps=True)
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Live debug for one Heima reaction")
    parser.add_argument("--ha-url", default=os.environ.get("HA_URL", "http://127.0.0.1:8123"))
    parser.add_argument("--ha-token", default=os.environ.get("HA_TOKEN"), required=False)
    parser.add_argument("--reaction-id")
    parser.add_argument("--label-contains")
    parser.add_argument(
        "--entity",
        action="append",
        dest="entities",
        default=[],
        help="Entity to watch. Repeat multiple times.",
    )
    parser.add_argument("--interval-s", type=float, default=1.0)
    parser.add_argument("--iterations", type=int, default=0, help="0 = infinite")
    parser.add_argument("--no-clear", action="store_true")
    parser.add_argument(
        "--watch-friendly",
        action="store_true",
        help="Emit a single stable snapshot and disable terminal clear codes for use under watch.",
    )
    parser.add_argument(
        "--verbosity",
        choices=("minimal", "medium", "full"),
        default="medium",
        help="Output detail level. Default: medium.",
    )
    args = parser.parse_args()

    if not str(args.ha_token or "").strip():
        raise HAApiError("missing Home Assistant token: pass --ha-token or export HA_TOKEN")

    client = HAClient(base_url=args.ha_url, token=args.ha_token, timeout_s=20)
    diag = client.get(f"/api/diagnostics/config_entry/{client.find_heima_entry_id()}")
    runtime = _extract_runtime(diag)
    engine = _safe_dict(runtime.get("engine"))
    reactions_diag = _safe_dict(engine.get("reactions"))
    _, reactions_payload = _reaction_sensor_payload(client)
    labels_map = _runtime_reaction_labels(reactions_payload, reactions_diag, _labels_map(diag))
    reaction_id = _match_reaction_id(
        reactions_payload=reactions_payload,
        labels_map=labels_map,
        requested_id=args.reaction_id,
        label_contains=args.label_contains,
    )
    label = labels_map.get(reaction_id, "")

    iterations = int(args.iterations)
    if args.watch_friendly and iterations == 0:
        iterations = 1

    iteration = 0
    while True:
        iteration += 1
        _debug_once(
            client,
            reaction_id=reaction_id,
            label=label,
            entity_ids=list(args.entities),
            interval_s=float(args.interval_s),
            iteration=iteration,
            clear=not bool(args.no_clear or args.watch_friendly),
            verbosity=str(args.verbosity),
            watch_friendly=bool(args.watch_friendly),
        )
        if iterations > 0 and iteration >= iterations:
            return 0
        time.sleep(max(0.2, float(args.interval_s)))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
