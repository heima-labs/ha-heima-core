"""Shared helpers for Phase AB smart lighting live tests."""

from __future__ import annotations

import time
from typing import Any

from lib.ha_client import HAApiError, HAClient

ENTRY_ROOM_ID = "studio"
MOTION_RAW = "input_boolean.test_heima_room_studio_motion_raw"
MOTION_SENSOR = "binary_sensor.test_heima_room_studio_motion"
LUX_INPUT = "input_number.test_heima_studio_lux"
LUX_SENSOR = "sensor.test_heima_studio_lux"
OUTDOOR_LUX_INPUT = "input_number.test_heima_outdoor_lux"
LIGHT_ENTITY = "light.test_heima_studio_main"
LIGHT_RAW = "input_boolean.test_heima_light_studio_main_raw"
LIGHT_BRIGHTNESS = "input_number.test_heima_light_studio_main_brightness"
LIGHT_COLOR_TEMP = "input_number.test_heima_light_studio_main_color_temp"
RESET_SCRIPT = "script.test_heima_reset"
CONFLICTING_LIGHTING_REACTION_TYPES = {
    "context_conditioned_lighting_scene",
    "contextual_room_lighting_assist",
    "room_contextual_lighting_assist",
    "room_lighting_assist",
    "room_vacancy_lighting_off",
}


def assert_true(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def require_entities(client: HAClient, entities: list[str]) -> None:
    missing = [entity_id for entity_id in entities if not client.entity_exists(entity_id)]
    if missing:
        raise HAApiError("missing required entities:\n- " + "\n- ".join(missing))


def wait_numeric_state(
    client: HAClient,
    entity_id: str,
    expected: float,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last = "<missing>"
    while time.time() < deadline:
        if client.entity_exists(entity_id):
            last = str(client.state_value(entity_id))
            try:
                if abs(float(last) - expected) < 0.01:
                    return
            except ValueError:
                pass
        time.sleep(poll_s)
    raise HAApiError(f"timeout waiting for {entity_id}={expected}, last={last!r}")


def wait_light(
    client: HAClient,
    entity_id: str,
    expected_state: str,
    *,
    brightness: int | None = None,
    timeout_s: int,
    poll_s: float,
) -> dict[str, Any]:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = client.get_state(entity_id)
        state = str(last.get("state") or "")
        attrs = dict(last.get("attributes") or {})
        current_brightness = attrs.get("brightness")
        brightness_matches = brightness is None or int(current_brightness or 0) == brightness
        if state == expected_state and brightness_matches:
            return last
        time.sleep(poll_s)
    raise HAApiError(
        f"timeout waiting for {entity_id} state={expected_state!r} brightness={brightness!r}; "
        f"last={last}"
    )


def diagnostics_root(client: HAClient, entry_id: str) -> dict[str, Any]:
    raw = client.get(f"/api/diagnostics/config_entry/{entry_id}")
    if not isinstance(raw, dict):
        raise HAApiError(f"invalid diagnostics payload: {type(raw)}")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise HAApiError("diagnostics payload missing data object")
    return data


def configured_reaction_summary(client: HAClient, entry_id: str) -> dict[str, Any]:
    plugins = diagnostics_root(client, entry_id).get("runtime", {}).get("plugins", {})
    if not isinstance(plugins, dict):
        return {}
    summary = plugins.get("configured_reaction_summary", {})
    return dict(summary) if isinstance(summary, dict) else {}


def configured_reactions(client: HAClient, entry_id: str) -> dict[str, Any]:
    entry = diagnostics_root(client, entry_id).get("entry", {})
    if not isinstance(entry, dict):
        return {}
    options = entry.get("options", {})
    if not isinstance(options, dict):
        return {}
    reactions = options.get("reactions", {})
    if not isinstance(reactions, dict):
        return {}
    configured = reactions.get("configured", {})
    return dict(configured) if isinstance(configured, dict) else {}


def find_smart_lighting_reaction_id(
    client: HAClient,
    entry_id: str,
    *,
    room_id: str = ENTRY_ROOM_ID,
) -> str | None:
    active_ids = {
        str(item) for item in configured_reaction_summary(client, entry_id).get("reaction_ids") or []
    }
    for reaction_id, cfg in configured_reactions(client, entry_id).items():
        if not isinstance(cfg, dict):
            continue
        if (
            cfg.get("reaction_type") == "room_smart_lighting_assist"
            and cfg.get("room_id") == room_id
            and str(reaction_id) in active_ids
        ):
            return str(reaction_id)
    return None


def engine_diagnostics(client: HAClient, entry_id: str) -> dict[str, Any]:
    engine = diagnostics_root(client, entry_id).get("runtime", {}).get("engine", {})
    return dict(engine) if isinstance(engine, dict) else {}


def reaction_diagnostics(client: HAClient, entry_id: str, reaction_id: str) -> dict[str, Any]:
    reactions = engine_diagnostics(client, entry_id).get("reactions", {})
    if not isinstance(reactions, dict):
        return {}
    value = reactions.get(reaction_id, {})
    return dict(value) if isinstance(value, dict) else {}


def wait_canonical_room_occupied(
    client: HAClient,
    entry_id: str,
    room_id: str,
    occupied: bool,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last: list[str] = []
    while time.time() < deadline:
        snapshot = engine_diagnostics(client, entry_id).get("snapshot", {})
        rooms = snapshot.get("occupied_rooms", []) if isinstance(snapshot, dict) else []
        last = [str(item) for item in rooms] if isinstance(rooms, list) else []
        if (room_id in set(last)) is occupied:
            return
        time.sleep(poll_s)
    raise HAApiError(
        f"timeout waiting for canonical room occupancy {room_id}={occupied}; "
        f"last occupied_rooms={last}"
    )


def wait_for_reaction_id(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    *,
    timeout_s: int,
    poll_s: float,
) -> None:
    deadline = time.time() + timeout_s
    last: dict[str, Any] = {}
    while time.time() < deadline:
        last = configured_reaction_summary(client, entry_id)
        if reaction_id in {str(item) for item in last.get("reaction_ids") or []}:
            return
        time.sleep(poll_s)
    raise HAApiError(f"reaction {reaction_id!r} not visible in diagnostics; last={last}")


def recompute_now(client: HAClient) -> None:
    client.call_service("heima", "command", {"command": "recompute_now"})


def reload_entry(client: HAClient, entry_id: str) -> None:
    client.call_service(
        "heima",
        "command",
        {"command": "dev_reload", "target": {"entry_id": entry_id}},
    )
    time.sleep(2.0)


def reset_lab(client: HAClient, *, timeout_s: int, poll_s: float) -> None:
    client.call_service(
        "heima",
        "set_override",
        {"scope": "lighting_room_hold", "id": ENTRY_ROOM_ID, "override": False},
    )
    client.call_service("script", "turn_on", {"entity_id": RESET_SCRIPT})
    client.wait_state(MOTION_SENSOR, "off", timeout_s, poll_s)
    client.wait_state(LIGHT_ENTITY, "off", timeout_s, poll_s)


def set_studio_occupied(client: HAClient, occupied: bool, *, timeout_s: int, poll_s: float) -> None:
    service = "turn_on" if occupied else "turn_off"
    expected = "on" if occupied else "off"
    client.call_service("input_boolean", service, {"entity_id": MOTION_RAW})
    client.wait_state(MOTION_SENSOR, expected, timeout_s, poll_s)
    recompute_now(client)


def set_indoor_lux(client: HAClient, value: float, *, timeout_s: int, poll_s: float) -> None:
    client.call_service("input_number", "set_value", {"entity_id": LUX_INPUT, "value": value})
    wait_numeric_state(client, LUX_SENSOR, value, timeout_s=timeout_s, poll_s=poll_s)


def set_outdoor_lux_if_available(
    client: HAClient, value: float, *, timeout_s: int, poll_s: float
) -> bool:
    if not client.entity_exists(OUTDOOR_LUX_INPUT):
        return False
    client.call_service(
        "input_number", "set_value", {"entity_id": OUTDOOR_LUX_INPUT, "value": value}
    )
    wait_numeric_state(client, OUTDOOR_LUX_INPUT, value, timeout_s=timeout_s, poll_s=poll_s)
    return True


def smart_lighting_cfg(
    *,
    reaction_id: str,
    brightness: int = 144,
    color_temp_kelvin: int | None = 2900,
    timeout_s: int = 30,
    dim_warning_s: int = 10,
    outdoor_lux_signal: str | None = None,
) -> dict[str, Any]:
    dim_ratio = max(0.0, min(1.0, float(dim_warning_s) / float(timeout_s or 1)))
    cfg: dict[str, Any] = {
        "reaction_type": "room_smart_lighting_assist",
        "reaction_class": "RoomSmartLightingAssistReaction",
        "enabled": True,
        "room_id": ENTRY_ROOM_ID,
        "indoor_lux_signal": "room_lux",
        "primary_signal_name": "room_lux",
        "primary_signal_entities": [LUX_SENSOR],
        "primary_bucket": "dim",
        "primary_bucket_match_mode": "lte",
        "lux_on_buckets": ["dark", "dim"],
        "room_type": "generic",
        "suppress_on_states": ["away", "vacation"],
        "night_mode_states": ["sleeping"],
        "timeout_mode": "fixed",
        "base_timeout_min": 1,
        "fast_exit_timeout_s": timeout_s,
        "dim_ratio": dim_ratio,
        "entity_steps": [
            {
                "entity_id": LIGHT_ENTITY,
                "action": "on",
                "brightness": brightness,
                "color_temp_kelvin": color_temp_kelvin,
                "rgb_color": None,
            }
        ],
        "source_template_id": "room.smart_lighting_assist.basic",
        "source_proposal_identity_key": (
            f"room_smart_lighting_assist|room={ENTRY_ROOM_ID}|primary=room_lux"
        ),
        "source_request": f"live-test:{reaction_id}",
        "origin": "admin_authored",
    }
    if outdoor_lux_signal:
        cfg["outdoor_lux_signal"] = outdoor_lux_signal
        cfg["outdoor_lux_scale"] = {
            "bright": 0.5,
            "dark": 1.0,
        }
    return cfg


def upsert_smart_lighting_reaction(
    client: HAClient,
    entry_id: str,
    reaction_id: str,
    cfg: dict[str, Any],
) -> None:
    updates: dict[str, dict[str, Any]] = {}
    for existing_id, existing_cfg in configured_reactions(client, entry_id).items():
        if (
            existing_id != reaction_id
            and isinstance(existing_cfg, dict)
            and existing_cfg.get("reaction_type") == "room_smart_lighting_assist"
            and existing_cfg.get("room_id") == ENTRY_ROOM_ID
            and str(existing_cfg.get("source_request") or "").startswith("live-test:")
        ):
            disabled = dict(existing_cfg)
            disabled["enabled"] = False
            updates[str(existing_id)] = disabled
    updates[reaction_id] = cfg
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {
                "configured": updates,
                "labels": {reaction_id: f"Live smart lighting {ENTRY_ROOM_ID}"},
            },
        },
    )


def disable_conflicting_lighting_reactions(
    client: HAClient,
    entry_id: str,
    *,
    keep_reaction_id: str,
) -> dict[str, dict[str, Any]]:
    updates: dict[str, dict[str, Any]] = {}
    originals: dict[str, dict[str, Any]] = {}
    for existing_id, existing_cfg in configured_reactions(client, entry_id).items():
        if str(existing_id) == keep_reaction_id or not isinstance(existing_cfg, dict):
            continue
        if existing_cfg.get("enabled") is False:
            continue
        reaction_type = str(existing_cfg.get("reaction_type") or "").strip()
        if reaction_type not in CONFLICTING_LIGHTING_REACTION_TYPES:
            continue
        if existing_cfg.get("room_id") != ENTRY_ROOM_ID and not _targets_light_entity(
            existing_cfg, LIGHT_ENTITY
        ):
            continue
        disabled = dict(existing_cfg)
        disabled["enabled"] = False
        originals[str(existing_id)] = dict(existing_cfg)
        updates[str(existing_id)] = disabled
    if updates:
        _upsert_configured_reaction_updates(client, entry_id, updates)
    return originals


def restore_configured_reactions(
    client: HAClient,
    entry_id: str,
    originals: dict[str, dict[str, Any]],
) -> None:
    if originals:
        _upsert_configured_reaction_updates(client, entry_id, originals)


def _upsert_configured_reaction_updates(
    client: HAClient,
    entry_id: str,
    updates: dict[str, dict[str, Any]],
) -> None:
    client.call_service(
        "heima",
        "command",
        {
            "command": "upsert_configured_reactions",
            "target": {"entry_id": entry_id},
            "params": {"configured": updates, "labels": {}},
        },
    )


def _targets_light_entity(cfg: dict[str, Any], entity_id: str) -> bool:
    for step in list(cfg.get("entity_steps") or []):
        if isinstance(step, dict) and step.get("entity_id") == entity_id:
            return True
    for profile in list(cfg.get("profiles") or []):
        if not isinstance(profile, dict):
            continue
        for step in list(profile.get("entity_steps") or []):
            if isinstance(step, dict) and step.get("entity_id") == entity_id:
                return True
    return False


def manual_light_on(client: HAClient, brightness: int, color_temp_kelvin: int) -> None:
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": LIGHT_BRIGHTNESS, "value": brightness},
    )
    client.call_service(
        "input_number",
        "set_value",
        {"entity_id": LIGHT_COLOR_TEMP, "value": color_temp_kelvin},
    )
    client.call_service("light", "turn_on", {"entity_id": LIGHT_ENTITY})
