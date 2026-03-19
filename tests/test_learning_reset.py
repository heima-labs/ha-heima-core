from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.heima.coordinator import HeimaCoordinator
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
