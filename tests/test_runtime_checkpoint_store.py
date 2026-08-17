"""Tests for runtime checkpoint persistence."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.heima.runtime.checkpoint_store import (
    CheckpointEntityState,
    RuntimeCheckpoint,
    RuntimeCheckpointStore,
    allowlisted_attributes,
)
from custom_components.heima.runtime.engine import HeimaEngine


class _FakeStore:
    next_load: dict[str, Any] | None = None
    instances: list["_FakeStore"] = []

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        self.saved: list[dict[str, Any]] = []
        self.delay_saves: list[float] = []
        _FakeStore.instances.append(self)

    async def async_load(self) -> dict[str, Any] | None:
        return _FakeStore.next_load

    async def async_save(self, payload: dict[str, Any]) -> None:
        self.saved.append(payload)

    def async_delay_save(self, serializer: Any, delay: float) -> None:
        self.delay_saves.append(delay)
        self.saved.append(serializer())


class _FakeStates:
    def __init__(self, states: dict[str, Any] | None = None) -> None:
        self._states = states or {}

    def get(self, entity_id: str) -> Any:
        return self._states.get(entity_id)


class _FakeBus:
    def async_fire(self, _event_type: str, _data: dict[str, Any]) -> None:
        return None


class _FakeServices:
    def async_services(self) -> dict[str, dict[str, Any]]:
        return {}


@pytest.fixture(autouse=True)
def _reset_fake_store() -> None:
    _FakeStore.next_load = None
    _FakeStore.instances.clear()


def test_checkpoint_attribute_allowlist_redacts_unlisted_values() -> None:
    assert allowlisted_attributes(
        "climate",
        {
            "temperature": 19.5,
            "current_temperature": 31.2,
            "access_token": "secret",
            "friendly_name": "Boiler",
        },
    ) == {"current_temperature": 31.2, "temperature": 19.5}
    assert allowlisted_attributes("switch", {"friendly_name": "Camera", "token": "secret"}) == {}


def test_checkpoint_entity_state_from_ha_state_uses_allowlist() -> None:
    state = SimpleNamespace(
        state="heat",
        attributes={"temperature": 20, "password": "secret"},
        last_changed=datetime(2026, 7, 1, tzinfo=UTC),
        last_updated=datetime(2026, 7, 1, 1, tzinfo=UTC),
    )

    checkpoint_state = CheckpointEntityState.from_ha_state("climate.boiler", state)

    assert checkpoint_state.entity_id == "climate.boiler"
    assert checkpoint_state.domain == "climate"
    assert checkpoint_state.attributes == {"temperature": 20}
    assert checkpoint_state.last_changed == "2026-07-01T00:00:00+00:00"


@pytest.mark.asyncio
async def test_runtime_checkpoint_store_loads_tolerantly_and_saves_by_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "custom_components.heima.runtime.checkpoint_store.Store",
        _FakeStore,
    )
    good = RuntimeCheckpoint(entry_id="entry-a", reason="periodic")
    _FakeStore.next_load = {
        "data": {
            "entries": {
                "entry-a": good.as_dict(),
                "broken": {"entry_id": "broken"},
                "not-dict": [],
            }
        }
    }
    store = RuntimeCheckpointStore(SimpleNamespace())

    await store.async_load()

    assert store.checkpoint_for_entry("entry-a") is not None
    assert store.diagnostics()["load_errors"] == 2

    replacement = RuntimeCheckpoint(entry_id="entry-a", reason="scheduled")
    await store.async_save_checkpoint(replacement, flush=True)

    assert store.checkpoint_for_entry("entry-a") == replacement
    assert _FakeStore.instances[-1].saved[-1]["data"]["entries"]["entry-a"]["reason"] == (
        "scheduled"
    )


@pytest.mark.asyncio
async def test_engine_schedules_and_flushes_checkpoint_write() -> None:
    hass = SimpleNamespace(
        states=_FakeStates(
            {
                "climate.boiler": SimpleNamespace(
                    state="heat",
                    attributes={"temperature": 20, "access_token": "secret"},
                    last_changed=None,
                    last_updated=None,
                )
            }
        ),
        bus=_FakeBus(),
        services=_FakeServices(),
    )
    entry = SimpleNamespace(
        entry_id="entry-a",
        options={"heating": {"climate_entity": "climate.boiler"}},
    )
    store = SimpleNamespace(saved=[])

    async def _save(checkpoint: RuntimeCheckpoint, *, flush: bool = False) -> None:
        store.saved.append((checkpoint, flush))

    store.async_save_checkpoint = _save
    engine = HeimaEngine(hass=hass, entry=entry)
    engine.set_runtime_checkpoint_store(store)  # type: ignore[arg-type]

    engine._schedule_runtime_checkpoint_write(reason="unit")
    jobs = engine.scheduled_runtime_jobs()

    assert "recovery.checkpoint.write" in jobs
    await engine.async_write_runtime_checkpoint(reason="scheduled")

    checkpoint, flush = store.saved[-1]
    assert flush is True
    assert checkpoint.entry_id == "entry-a"
    assert checkpoint.critical_entities[0].entity_id == "climate.boiler"
    assert checkpoint.critical_entities[0].attributes == {"temperature": 20}
    assert "recovery.checkpoint.write" not in engine.scheduled_runtime_jobs()


@pytest.mark.asyncio
async def test_engine_checkpoint_write_failure_is_non_fatal() -> None:
    hass = SimpleNamespace(states=_FakeStates(), bus=_FakeBus(), services=_FakeServices())
    entry = SimpleNamespace(entry_id="entry-a", options={})

    async def _save(_checkpoint: RuntimeCheckpoint, *, flush: bool = False) -> None:
        raise RuntimeError("store unavailable")

    store = SimpleNamespace(async_save_checkpoint=_save)
    engine = HeimaEngine(hass=hass, entry=entry)
    engine.set_runtime_checkpoint_store(store)  # type: ignore[arg-type]
    engine._schedule_timed_recheck_deadline(
        job_id="recovery.checkpoint.write",
        deadline=1.0,
        owner="recovery",
        label="Runtime checkpoint write",
    )

    assert await engine.async_write_runtime_checkpoint(reason="scheduled") is False
    assert "recovery.checkpoint.write" not in engine.scheduled_runtime_jobs()
