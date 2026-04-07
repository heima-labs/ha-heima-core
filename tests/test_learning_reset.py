from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.coordinator import HeimaCoordinator
from custom_components.heima.runtime.analyzers.registry import LearningPluginRegistry
from custom_components.heima.runtime.behaviors.base import HeimaBehavior
from custom_components.heima.runtime.engine import HeimaEngine
from custom_components.heima.runtime.reactions.base import HeimaReaction
from custom_components.heima.runtime.snapshot import DecisionSnapshot


class _ResetBehavior(HeimaBehavior):
    def __init__(self) -> None:
        self.reset_called = False

    @property
    def behavior_id(self) -> str:
        return "reset_behavior"

    def reset_learning_state(self) -> None:
        self.reset_called = True


class _ResetReaction(HeimaReaction):
    def __init__(self) -> None:
        self.reset_called = False

    @property
    def reaction_id(self) -> str:
        return "reset_reaction"

    def reset_learning_state(self) -> None:
        self.reset_called = True


def _build_engine() -> HeimaEngine:
    hass = MagicMock()
    hass.states.get.return_value = None
    hass.services.async_services.return_value = {}
    entry = SimpleNamespace(entry_id="test-entry", options={})
    return HeimaEngine(hass, entry)


def test_engine_reset_learning_state_clears_snapshot_history_and_dispatches_hooks():
    engine = _build_engine()
    behavior = _ResetBehavior()
    reaction = _ResetReaction()
    engine.register_behavior(behavior)
    engine.register_reaction(reaction)
    engine._snapshot_buffer.push(DecisionSnapshot.empty())

    engine.reset_learning_state()

    assert engine.snapshot_history == []
    assert behavior.reset_called is True
    assert reaction.reset_called is True


@pytest.mark.asyncio
async def test_coordinator_learning_reset_flushes_and_resets_runtime_state():
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._event_store = SimpleNamespace(
        async_clear=AsyncMock(),
        async_flush=AsyncMock(),
    )
    coordinator._proposal_engine = SimpleNamespace(async_clear=AsyncMock())
    coordinator.engine = SimpleNamespace(reset_learning_state=MagicMock())
    coordinator._write_event_store_sensor = MagicMock()
    coordinator.async_refresh = AsyncMock()

    await coordinator.async_reset_learning_data()

    coordinator._event_store.async_clear.assert_awaited_once()
    coordinator._event_store.async_flush.assert_awaited_once()
    coordinator._proposal_engine.async_clear.assert_awaited_once()
    coordinator.engine.reset_learning_state.assert_called_once()
    coordinator._write_event_store_sensor.assert_called_once()
    coordinator.async_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_coordinator_learning_run_refreshes_runtime_state():
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator._proposal_engine = SimpleNamespace(async_run=AsyncMock())
    coordinator._write_event_store_sensor = MagicMock()
    coordinator.async_refresh = AsyncMock()

    await coordinator.async_run_learning_now()

    coordinator._proposal_engine.async_run.assert_awaited_once()
    coordinator._write_event_store_sensor.assert_called_once()
    coordinator.async_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_coordinator_upsert_configured_reactions_updates_entry_options():
    config_entries = MagicMock()
    hass = SimpleNamespace(config_entries=config_entries)
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.hass = hass
    coordinator.entry = SimpleNamespace(
        options={
            "reactions": {
                "configured": {"r1": {"reaction_class": "LightingScheduleReaction"}},
                "labels": {"r1": "Existing"},
            }
        }
    )

    await coordinator.async_upsert_configured_reactions(
        {"r2": {"reaction_class": "LightingScheduleReaction", "room_id": "living"}},
        label_updates={"r2": "New reaction"},
    )

    config_entries.async_update_entry.assert_called_once()
    _, kwargs = config_entries.async_update_entry.call_args
    updated = kwargs["options"]["reactions"]
    assert updated["configured"]["r1"]["reaction_class"] == "LightingScheduleReaction"
    assert updated["configured"]["r2"]["room_id"] == "living"
    assert updated["labels"]["r2"] == "New reaction"


@pytest.mark.asyncio
async def test_coordinator_runtime_reload_does_not_reset_or_rerun_proposals():
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(entry_id="entry-1", options={"learning": {}, "rooms": []})
    coordinator.engine = SimpleNamespace(
        async_reload_options=AsyncMock(),
        health=SimpleNamespace(ok=True, reason="ok"),
        snapshot=SimpleNamespace(house_state="home"),
        state=SimpleNamespace(get_sensor=lambda key: "default" if key == "heima_house_state_reason" else ""),
    )
    coordinator._proposal_engine = SimpleNamespace(
        async_run=AsyncMock(),
        async_clear=AsyncMock(),
        set_analyzers=MagicMock(),
        set_learning_plugin_registry=MagicMock(),
    )
    coordinator._context_builder = SimpleNamespace(update_config=MagicMock())
    coordinator._resubscribe_state_changes = MagicMock()
    coordinator._sync_scheduler = MagicMock()
    coordinator.async_refresh = AsyncMock()

    await coordinator.async_reload_options(changed_keys={"calendar"})

    coordinator.engine.async_reload_options.assert_awaited_once()
    coordinator._context_builder.update_config.assert_called_once_with(
        {"learning": {}, "rooms": []}
    )
    coordinator._proposal_engine.async_run.assert_not_called()
    coordinator._proposal_engine.async_clear.assert_not_called()
    coordinator._proposal_engine.set_analyzers.assert_called_once()
    coordinator._resubscribe_state_changes.assert_called_once()
    coordinator._sync_scheduler.assert_called_once()
    coordinator.async_refresh.assert_awaited_once()


@pytest.mark.asyncio
async def test_coordinator_runtime_reload_preserves_existing_proposal_engine_instance():
    proposal_engine = SimpleNamespace(
        async_run=AsyncMock(),
        async_clear=AsyncMock(),
        set_analyzers=MagicMock(),
        set_learning_plugin_registry=MagicMock(),
    )
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(entry_id="entry-1", options={"learning": {}, "rooms": []})
    coordinator.engine = SimpleNamespace(
        async_reload_options=AsyncMock(),
        health=SimpleNamespace(ok=True, reason="ok"),
        snapshot=SimpleNamespace(house_state="home"),
        state=SimpleNamespace(get_sensor=lambda key: "default" if key == "heima_house_state_reason" else ""),
    )
    coordinator._proposal_engine = proposal_engine
    coordinator._context_builder = SimpleNamespace(update_config=MagicMock())
    coordinator._resubscribe_state_changes = MagicMock()
    coordinator._sync_scheduler = MagicMock()
    coordinator.async_refresh = AsyncMock()

    await coordinator.async_reload_options(changed_keys={"notifications"})

    assert coordinator._proposal_engine is proposal_engine
    proposal_engine.set_analyzers.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_runtime_reload_updates_learning_plugin_registry_and_analyzers():
    initial_registry = LearningPluginRegistry()
    updated_registry = LearningPluginRegistry()
    proposal_engine = SimpleNamespace(
        async_run=AsyncMock(),
        async_clear=AsyncMock(),
        set_analyzers=MagicMock(),
        set_learning_plugin_registry=MagicMock(),
    )
    coordinator = HeimaCoordinator.__new__(HeimaCoordinator)
    coordinator.entry = SimpleNamespace(
        entry_id="entry-1",
        options={"learning": {"enabled_plugin_families": ["presence", "lighting"]}, "rooms": []},
    )
    coordinator.engine = SimpleNamespace(
        async_reload_options=AsyncMock(),
        health=SimpleNamespace(ok=True, reason="ok"),
        snapshot=SimpleNamespace(house_state="home"),
        state=SimpleNamespace(get_sensor=lambda key: "default" if key == "heima_house_state_reason" else ""),
    )
    coordinator._proposal_engine = proposal_engine
    coordinator._learning_plugin_registry = initial_registry
    coordinator._context_builder = SimpleNamespace(update_config=MagicMock())
    coordinator._resubscribe_state_changes = MagicMock()
    coordinator._sync_scheduler = MagicMock()
    coordinator.async_refresh = AsyncMock()
    coordinator._build_learning_plugin_registry = MagicMock(return_value=updated_registry)

    await coordinator.async_reload_options(changed_keys={"learning"})

    assert coordinator._learning_plugin_registry is updated_registry
    proposal_engine.set_analyzers.assert_called_once_with(list(updated_registry.analyzers()))
