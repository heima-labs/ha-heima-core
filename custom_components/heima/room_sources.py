"""Helpers for room occupancy and learning source configuration."""

from __future__ import annotations

import json
from typing import Any

_DEFAULT_SIGNAL_BUCKETS: dict[str, list[dict[str, float | str | None]]] = {
    "illuminance": [
        {"label": "dark", "upper_bound": 30.0},
        {"label": "dim", "upper_bound": 100.0},
        {"label": "ok", "upper_bound": 300.0},
        {"label": "bright", "upper_bound": None},
    ],
    "carbon_dioxide": [
        {"label": "ok", "upper_bound": 800.0},
        {"label": "elevated", "upper_bound": 1200.0},
        {"label": "high", "upper_bound": None},
    ],
    "humidity": [
        {"label": "low", "upper_bound": 40.0},
        {"label": "ok", "upper_bound": 70.0},
        {"label": "high", "upper_bound": None},
    ],
    "temperature": [
        {"label": "cool", "upper_bound": 20.0},
        {"label": "ok", "upper_bound": 24.0},
        {"label": "warm", "upper_bound": 27.0},
        {"label": "hot", "upper_bound": None},
    ],
}
_DEVICE_CLASS_TO_SIGNAL_NAME = {
    "illuminance": "room_lux",
    "carbon_dioxide": "room_co2",
    "humidity": "room_humidity",
    "temperature": "room_temperature",
}
_BURST_DIRECTIONS = {"up", "down", "both"}


def normalize_entity_id_list(raw_entities: Any) -> list[str]:
    """Normalize selector outputs or raw lists to a stable list[str]."""
    if raw_entities is None:
        return []
    if isinstance(raw_entities, dict):
        return [
            str(key).strip()
            for key, enabled in raw_entities.items()
            if enabled and str(key).strip()
        ]
    if isinstance(raw_entities, (list, tuple, set)):
        return [str(entity_id).strip() for entity_id in raw_entities if str(entity_id).strip()]
    if isinstance(raw_entities, str):
        clean = raw_entities.strip()
        return [clean] if clean else []
    clean = str(raw_entities).strip()
    return [clean] if clean else []


def normalize_room_signal_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize room occupancy/learning sources with backward-compatible migration."""
    data = dict(payload)

    explicit_occupancy = "occupancy_sources" in data
    explicit_learning = "learning_sources" in data

    if explicit_occupancy:
        occupancy_sources = normalize_entity_id_list(data.get("occupancy_sources"))
    else:
        occupancy_sources = _migrate_legacy_occupancy_sources(data.get("sources"))

    if explicit_learning:
        learning_sources = normalize_entity_id_list(data.get("learning_sources"))
    else:
        learning_sources = _migrate_legacy_learning_sources(data.get("sources"))

    data["occupancy_sources"] = _dedupe(occupancy_sources)
    data["learning_sources"] = _dedupe(learning_sources)
    data.pop("sources", None)
    return data


def format_room_signals_for_form(raw_signals: Any) -> str:
    """Return room signal config as a readable JSON block for the options form."""
    if isinstance(raw_signals, str):
        return raw_signals
    if not isinstance(raw_signals, list) or not raw_signals:
        return ""
    return json.dumps(raw_signals, indent=2, ensure_ascii=False)


def normalize_room_signals(
    raw_signals: Any,
    *,
    state_getter: Any | None = None,
) -> list[dict[str, Any]]:
    """Normalize room signal definitions from form input or stored payload."""
    if raw_signals in (None, ""):
        return []

    parsed = raw_signals
    if isinstance(raw_signals, str):
        try:
            parsed = json.loads(raw_signals)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid_json") from exc

    if not isinstance(parsed, list):
        raise ValueError("invalid_signal_config")

    normalized: list[dict[str, Any]] = []
    seen_signal_names: set[str] = set()
    for raw_item in parsed:
        if not isinstance(raw_item, dict):
            raise ValueError("invalid_signal_config")

        entity_id = str(raw_item.get("entity_id") or "").strip()
        signal_name = str(raw_item.get("signal_name") or "").strip()
        device_class = str(raw_item.get("device_class") or "").strip()
        if not entity_id or not signal_name:
            raise ValueError("invalid_signal_config")
        if signal_name in seen_signal_names:
            raise ValueError("duplicate_signal_name")
        seen_signal_names.add(signal_name)

        if not device_class and callable(state_getter):
            state = state_getter(entity_id)
            attributes = getattr(state, "attributes", {}) if state is not None else {}
            device_class = str(attributes.get("device_class") or "").strip()

        buckets = _normalize_signal_buckets(raw_item.get("buckets"))
        if not buckets and device_class:
            buckets = _normalize_signal_buckets(_DEFAULT_SIGNAL_BUCKETS.get(device_class))
        if not buckets:
            raise ValueError("invalid_signal_config")

        normalized.append(
            _with_normalized_burst_config(
                {
                    "entity_id": entity_id,
                    "signal_name": signal_name,
                    "device_class": device_class,
                    "buckets": [
                        {"label": label, "upper_bound": upper_bound}
                        for upper_bound, label in buckets
                    ],
                },
                raw_item,
            )
        )
    return normalized


def room_occupancy_source_entity_ids(room_or_sources: Any) -> list[str]:
    """Return occupancy sources for a room, with legacy migration fallback."""
    if isinstance(room_or_sources, dict):
        if "occupancy_sources" in room_or_sources:
            return _dedupe(normalize_entity_id_list(room_or_sources.get("occupancy_sources")))
        return _dedupe(_migrate_legacy_occupancy_sources(room_or_sources.get("sources")))
    return _dedupe(normalize_entity_id_list(room_or_sources))


def room_learning_source_entity_ids(room_or_sources: Any) -> list[str]:
    """Return learning sources for a room, with legacy migration fallback."""
    if isinstance(room_or_sources, dict):
        if "learning_sources" in room_or_sources:
            return _dedupe(normalize_entity_id_list(room_or_sources.get("learning_sources")))
        return _dedupe(_migrate_legacy_learning_sources(room_or_sources.get("sources")))
    return _dedupe(normalize_entity_id_list(room_or_sources))


def room_all_source_entity_ids(room_cfg: dict[str, Any]) -> list[str]:
    """Return all room-level sources used for occupancy or learning."""
    return _dedupe(
        [
            *room_occupancy_source_entity_ids(room_cfg),
            *room_learning_source_entity_ids(room_cfg),
        ]
    )


def autopopulate_room_signals(
    options: dict[str, Any],
    *,
    state_getter: Any,
) -> tuple[dict[str, Any], bool]:
    """Auto-populate room signal configs from learning sources when missing."""
    normalized = dict(options or {})
    rooms = list(normalized.get("rooms") or [])
    changed = False
    next_rooms: list[dict[str, Any]] = []
    for raw_room in rooms:
        room = dict(raw_room) if isinstance(raw_room, dict) else raw_room
        if not isinstance(room, dict):
            next_rooms.append(room)
            continue
        existing_signals = room.get("signals")
        if isinstance(existing_signals, list) and existing_signals:
            next_rooms.append(room)
            continue
        synthesized: list[dict[str, Any]] = []
        for entity_id in room_learning_source_entity_ids(room):
            state = state_getter(entity_id)
            attributes = getattr(state, "attributes", {}) if state is not None else {}
            device_class = str(attributes.get("device_class") or "").strip()
            signal_name = _DEVICE_CLASS_TO_SIGNAL_NAME.get(device_class)
            buckets = _DEFAULT_SIGNAL_BUCKETS.get(device_class)
            if not signal_name or not buckets:
                continue
            synthesized.append(
                _with_normalized_burst_config(
                    {
                        "entity_id": entity_id,
                        "signal_name": signal_name,
                        "device_class": device_class,
                        "buckets": [dict(item) for item in buckets],
                    },
                    {},
                )
            )
        if synthesized:
            room["signals"] = synthesized
            changed = True
        next_rooms.append(room)
    if changed:
        normalized["rooms"] = next_rooms
    return normalized, changed


def migrate_room_darkness_reactions_to_primary_bucket(
    options: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Replace numeric darkness thresholds with canonical primary_bucket when possible."""
    normalized = dict(options or {})
    room_bucket_index = _room_signal_bucket_index(normalized)
    reactions = dict(normalized.get("reactions") or {})
    configured = dict(reactions.get("configured") or {})
    changed = False
    next_configured: dict[str, Any] = {}
    for reaction_id, raw_cfg in configured.items():
        if not isinstance(raw_cfg, dict):
            next_configured[reaction_id] = raw_cfg
            continue
        cfg = dict(raw_cfg)
        reaction_type = str(cfg.get("reaction_type") or "").strip()
        if (
            reaction_type != "room_darkness_lighting_assist"
            or str(cfg.get("primary_bucket") or "").strip()
        ):
            next_configured[reaction_id] = cfg
            continue
        room_id = str(cfg.get("room_id") or "").strip()
        signal_name = str(cfg.get("primary_signal_name") or "").strip()
        threshold = cfg.get("primary_threshold")
        if not room_id or not signal_name:
            next_configured[reaction_id] = cfg
            continue
        bucket = _bucket_for_threshold(
            room_bucket_index.get((room_id, signal_name), ()),
            threshold,
        )
        if bucket is None:
            next_configured[reaction_id] = cfg
            continue
        cfg["primary_bucket"] = bucket
        cfg.pop("primary_threshold", None)
        cfg.pop("primary_threshold_mode", None)
        changed = True
        next_configured[reaction_id] = cfg
    if changed:
        reactions["configured"] = next_configured
        normalized["reactions"] = reactions
    return normalized, changed


def migrate_burst_signal_configs_and_reactions(
    options: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Move burst thresholds from legacy cooling reactions into room signals."""
    normalized = dict(options or {})
    rooms = [
        dict(item) if isinstance(item, dict) else item
        for item in list(normalized.get("rooms") or [])
    ]
    reactions = dict(normalized.get("reactions") or {})
    configured = dict(reactions.get("configured") or {})
    changed = False

    room_map: dict[str, dict[str, Any]] = {}
    signal_maps: dict[str, dict[str, dict[str, Any]]] = {}
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("room_id") or "").strip()
        if not room_id:
            continue
        room_map[room_id] = room
        signal_map: dict[str, dict[str, Any]] = {}
        signals = []
        for raw_signal in list(room.get("signals") or []):
            if not isinstance(raw_signal, dict):
                continue
            signal = dict(raw_signal)
            signal_name = _canonical_signal_name(signal.get("signal_name"))
            if not signal_name:
                continue
            signal["signal_name"] = signal_name
            signals.append(signal)
            signal_map[signal_name] = signal
        if signals:
            room["signals"] = signals
        signal_maps[room_id] = signal_map

    next_configured: dict[str, Any] = {}
    for reaction_id, raw_cfg in configured.items():
        if not isinstance(raw_cfg, dict):
            next_configured[reaction_id] = raw_cfg
            continue
        cfg = dict(raw_cfg)
        if str(cfg.get("reaction_type") or "").strip() != "room_cooling_assist":
            next_configured[reaction_id] = cfg
            continue
        room_id = str(cfg.get("room_id") or "").strip()
        room = room_map.get(room_id)
        signal_map = signal_maps.get(room_id, {})
        if room is None:
            next_configured[reaction_id] = cfg
            continue

        primary_signal_name = _canonical_signal_name(cfg.get("primary_signal_name"))
        corroboration_signal_name = _canonical_signal_name(cfg.get("corroboration_signal_name"))
        if primary_signal_name:
            cfg["primary_signal_name"] = primary_signal_name
        if corroboration_signal_name:
            cfg["corroboration_signal_name"] = corroboration_signal_name

        correlation_window_s = _coerce_positive_int(cfg.get("correlation_window_s"), 600)
        if primary_signal_name:
            primary_signal = signal_map.get(primary_signal_name)
            if primary_signal is not None:
                primary_changed = _merge_burst_config(
                    primary_signal,
                    threshold=cfg.get("primary_rise_threshold", cfg.get("primary_threshold")),
                    window_s=correlation_window_s,
                    direction=_direction_from_threshold_mode(cfg.get("primary_threshold_mode")),
                )
                changed = changed or primary_changed
        if corroboration_signal_name:
            corroboration_signal = signal_map.get(corroboration_signal_name)
            if corroboration_signal is not None:
                corroboration_changed = _merge_burst_config(
                    corroboration_signal,
                    threshold=cfg.get(
                        "corroboration_rise_threshold",
                        cfg.get("corroboration_threshold"),
                    ),
                    window_s=correlation_window_s,
                    direction=_direction_from_threshold_mode(
                        cfg.get("corroboration_threshold_mode")
                    ),
                )
                changed = changed or corroboration_changed

        for legacy_key in (
            "trigger_signal_entities",
            "temperature_signal_entities",
            "humidity_rise_threshold",
            "temperature_rise_threshold",
            "primary_rise_threshold",
            "primary_threshold",
            "primary_threshold_mode",
            "corroboration_rise_threshold",
            "corroboration_threshold",
            "corroboration_threshold_mode",
            "correlation_window_s",
        ):
            if legacy_key in cfg:
                cfg.pop(legacy_key, None)
                changed = True

        next_configured[reaction_id] = cfg

    if changed:
        normalized["rooms"] = rooms
        reactions["configured"] = next_configured
        normalized["reactions"] = reactions
    return normalized, changed


def room_signal_names(rooms: list[dict[str, Any]], room_id: str) -> list[str]:
    """Return signal names configured for a room."""
    room = next((r for r in rooms if isinstance(r, dict) and r.get("room_id") == room_id), None)
    if not room:
        return []
    return [
        str(s.get("signal_name") or "").strip()
        for s in list(room.get("signals") or [])
        if isinstance(s, dict) and str(s.get("signal_name") or "").strip()
    ]


def room_signal_bucket_labels(
    rooms: list[dict[str, Any]], room_id: str, signal_name: str
) -> list[str]:
    """Return bucket labels for a room+signal combo."""
    room = next((r for r in rooms if isinstance(r, dict) and r.get("room_id") == room_id), None)
    if not room:
        return []
    signal = next(
        (
            s
            for s in list(room.get("signals") or [])
            if isinstance(s, dict) and s.get("signal_name") == signal_name
        ),
        None,
    )
    if not signal:
        return []
    return [
        str(b.get("label") or "").strip()
        for b in list(signal.get("buckets") or [])
        if isinstance(b, dict) and str(b.get("label") or "").strip()
    ]


def room_signal_entity_id(
    rooms: list[dict[str, Any]], room_id: str, signal_name: str
) -> str | None:
    """Return the entity_id for a room+signal combo, or None if not found."""
    room = next((r for r in rooms if isinstance(r, dict) and r.get("room_id") == room_id), None)
    if not room:
        return None
    signal = next(
        (
            s
            for s in list(room.get("signals") or [])
            if isinstance(s, dict) and s.get("signal_name") == signal_name
        ),
        None,
    )
    if not signal:
        return None
    entity_id = str(signal.get("entity_id") or "").strip()
    return entity_id or None


def _room_signal_bucket_index(
    options: dict[str, Any],
) -> dict[tuple[str, str], tuple[tuple[float | None, str], ...]]:
    index: dict[tuple[str, str], tuple[tuple[float | None, str], ...]] = {}
    for raw_room in list(options.get("rooms") or []):
        room = raw_room if isinstance(raw_room, dict) else {}
        room_id = str(room.get("room_id") or "").strip()
        if not room_id:
            continue
        for raw_signal in list(room.get("signals") or []):
            signal = raw_signal if isinstance(raw_signal, dict) else {}
            signal_name = str(signal.get("signal_name") or "").strip()
            buckets = _normalize_signal_buckets(signal.get("buckets"))
            if signal_name and buckets:
                index[(room_id, signal_name)] = buckets
    return index


def _bucket_for_threshold(
    buckets: tuple[tuple[float | None, str], ...],
    threshold: Any,
) -> str | None:
    try:
        numeric = float(threshold)
    except (TypeError, ValueError):
        return None
    for upper_bound, label in buckets:
        if upper_bound is None or numeric < upper_bound:
            return label
    return None


def _normalize_signal_buckets(raw_buckets: Any) -> tuple[tuple[float | None, str], ...]:
    normalized: list[tuple[float | None, str]] = []
    if not isinstance(raw_buckets, list):
        return ()
    for raw in raw_buckets:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "").strip()
        upper_bound_raw = raw.get("upper_bound")
        if not label:
            continue
        if upper_bound_raw in (None, ""):
            upper_bound = None
        elif isinstance(upper_bound_raw, (int, float)):
            upper_bound = float(upper_bound_raw)
        elif isinstance(upper_bound_raw, str):
            try:
                upper_bound = float(upper_bound_raw)
            except ValueError:
                continue
        else:
            continue
        normalized.append((upper_bound, label))
    return tuple(normalized)


def _with_normalized_burst_config(
    target: dict[str, Any],
    source: dict[str, Any],
) -> dict[str, Any]:
    burst_threshold = _coerce_optional_float(source.get("burst_threshold"))
    burst_window_s = _coerce_positive_int(source.get("burst_window_s"), 600)
    burst_direction = str(source.get("burst_direction") or "up").strip().lower()
    if burst_threshold is not None:
        target["burst_threshold"] = burst_threshold
        target["burst_window_s"] = burst_window_s
        target["burst_direction"] = (
            burst_direction if burst_direction in _BURST_DIRECTIONS else "up"
        )
    return target


def _merge_burst_config(
    signal_cfg: dict[str, Any],
    *,
    threshold: Any,
    window_s: int,
    direction: str,
) -> bool:
    numeric_threshold = _coerce_optional_float(threshold)
    if numeric_threshold is None:
        return False
    changed = False
    if signal_cfg.get("burst_threshold") != numeric_threshold:
        signal_cfg["burst_threshold"] = numeric_threshold
        changed = True
    if int(signal_cfg.get("burst_window_s") or 0) != int(window_s):
        signal_cfg["burst_window_s"] = int(window_s)
        changed = True
    normalized_direction = direction if direction in _BURST_DIRECTIONS else "up"
    if str(signal_cfg.get("burst_direction") or "").strip().lower() != normalized_direction:
        signal_cfg["burst_direction"] = normalized_direction
        changed = True
    return changed


def _coerce_optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return numeric if numeric > 0 else default


def _canonical_signal_name(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if raw == "temperature":
        return "room_temperature"
    if raw == "humidity":
        return "room_humidity"
    if raw == "co2":
        return "room_co2"
    if raw == "lux":
        return "room_lux"
    return raw


def _direction_from_threshold_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    if mode == "drop":
        return "down"
    if mode == "both":
        return "both"
    return "up"


def _migrate_legacy_occupancy_sources(raw_sources: Any) -> list[str]:
    migrated: list[str] = []
    for item in normalize_entity_id_list_or_structured(raw_sources):
        if isinstance(item, dict):
            entity_id = str(item.get("entity_id", "")).strip()
            if entity_id:
                migrated.append(entity_id)
        else:
            clean = str(item).strip()
            if clean:
                migrated.append(clean)
    return migrated


def _migrate_legacy_learning_sources(raw_sources: Any) -> list[str]:
    migrated: list[str] = []
    for item in normalize_entity_id_list_or_structured(raw_sources):
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get("entity_id", "")).strip()
        if entity_id and bool(item.get("learning_enabled")):
            migrated.append(entity_id)
    return migrated


def normalize_entity_id_list_or_structured(raw_entities: Any) -> list[Any]:
    """Normalize mixed legacy room source payloads without losing dict entries."""
    if raw_entities is None:
        return []
    if isinstance(raw_entities, list):
        return list(raw_entities)
    if isinstance(raw_entities, (tuple, set)):
        return list(raw_entities)
    if isinstance(raw_entities, dict):
        return [raw_entities]
    if isinstance(raw_entities, str):
        clean = raw_entities.strip()
        return [clean] if clean else []
    clean = str(raw_entities).strip()
    return [clean] if clean else []


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        clean = str(value).strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped
