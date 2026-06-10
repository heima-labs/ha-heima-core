"""Shared identity helpers for learned and configured reaction contracts."""

from __future__ import annotations

from typing import Any


def composite_room_proposal_identity_key(
    *,
    reaction_type: str,
    cfg: dict[str, Any],
) -> str:
    """Return the learned composite proposal identity."""
    primary_signal = str(cfg.get("primary_signal_name") or "").strip().lower()
    primary_suffix = f"|primary={primary_signal}" if primary_signal else ""
    house_state_filter = cfg.get("house_state_filter") or None
    house_state_suffix = f"|house_state={house_state_filter}" if house_state_filter else ""
    return f"{reaction_type}|room={cfg.get('room_id')}{primary_suffix}{house_state_suffix}"


def admin_room_signal_assist_identity_key(
    *,
    room_id: str,
    primary_signal_name: str,
    primary_trigger_mode: str,
) -> str:
    """Return the admin-authored identity for a room signal assist request."""
    primary_signal = primary_signal_name.strip().lower()
    trigger_mode = primary_trigger_mode.strip().lower()
    return f"room_signal_assist|room={room_id}|primary={primary_signal}|mode={trigger_mode}"


def composite_configured_reaction_slot_key(
    *,
    reaction_type: str,
    cfg: dict[str, Any],
) -> str:
    """Return the configured composite slot used to target existing reactions."""
    room_id = str(cfg.get("room_id") or "").strip()
    house_state_filter = str(cfg.get("house_state_filter") or "").strip()
    house_state_suffix = f"|house_state={house_state_filter}" if house_state_filter else ""

    if reaction_type in {
        "room_signal_assist",
        "room_cooling_assist",
        "room_air_quality_assist",
    }:
        primary_signal = str(cfg.get("primary_signal_name") or "").strip().lower()
        primary_trigger_mode = str(cfg.get("primary_trigger_mode") or "").strip().lower()
        trigger_mode_suffix = (
            f"|mode={primary_trigger_mode}" if reaction_type == "room_signal_assist" else ""
        )
        return (
            f"{reaction_type}|room={room_id}|primary={primary_signal}"
            f"{trigger_mode_suffix}{house_state_suffix}"
        )

    if reaction_type in {
        "room_darkness_lighting_assist",
        "room_contextual_lighting_assist",
    }:
        primary_signal = str(cfg.get("primary_signal_name") or "").strip().lower()
        return f"{reaction_type}|room={room_id}|primary={primary_signal}{house_state_suffix}"

    if reaction_type == "room_vacancy_lighting_off":
        return f"{reaction_type}|room={room_id}"

    return ""
