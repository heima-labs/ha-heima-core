from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima import _async_entry_updated
from custom_components.heima.const import DOMAIN


@pytest.mark.asyncio
async def test_entry_updated_normalizes_redacted_reactions_before_reload():
    coordinator = SimpleNamespace(
        last_options_snapshot={},
        async_reload_options=AsyncMock(),
    )
    hass = SimpleNamespace(
        data={DOMAIN: {"entry-1": {"coordinator": coordinator}}},
        config_entries=SimpleNamespace(async_update_entry=MagicMock()),
    )
    entry = SimpleNamespace(
        entry_id="entry-1",
        options={
            "reactions": {
                "configured": {
                    "bad": {
                        "reaction_class": "RoomLightingAssistReaction",
                        "room_id": "studio",
                        "primary_signal_entities": ["sensor.studio_lux"],
                        "primary_threshold": 120.0,
                        "primary_signal_name": "room_lux",
                        "entity_steps": [{"entity_id": "**REDACTED**", "action": "on"}],
                    },
                    "good": {
                        "reaction_class": "PresencePatternReaction",
                        "weekday": 1,
                        "median_arrival_min": 480,
                        "window_half_min": 15,
                        "pre_condition_min": 20,
                        "min_arrivals": 5,
                        "steps": [],
                    },
                },
                "labels": {"bad": "Broken studio lights", "good": "Presence"},
                "muted": ["bad", "good"],
            }
        },
    )

    await _async_entry_updated(hass, entry)

    hass.config_entries.async_update_entry.assert_called_once()
    normalized_options = hass.config_entries.async_update_entry.call_args.kwargs["options"]
    assert "bad" not in normalized_options["reactions"]["configured"]
    assert "bad" not in normalized_options["reactions"]["labels"]
    assert "bad" not in normalized_options["reactions"]["muted"]
    assert normalized_options["reactions"]["configured"]["good"]["reaction_type"] == (
        "presence_preheat"
    )
    coordinator.async_reload_options.assert_not_awaited()
    # snapshot intentionally NOT updated: the second _async_entry_updated invocation
    # (scheduled by async_update_entry) will detect the delta and call async_reload_options
    assert coordinator.last_options_snapshot == {}
