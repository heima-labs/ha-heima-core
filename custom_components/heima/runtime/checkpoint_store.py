"""Runtime checkpoint persistence for recovery."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

CHECKPOINT_SCHEMA_VERSION = 1
MAX_CHECKPOINT_ENTITIES = 256
MAX_CHECKPOINT_ENTRIES = 16
MAX_STRING_VALUE_LEN = 512
MAX_LIST_VALUE_LEN = 32
MAX_DICT_VALUE_LEN = 64

_ATTRIBUTE_ALLOWLIST: dict[str, set[str]] = {
    "alarm_control_panel": set(),
    "binary_sensor": {"device_class"},
    "climate": {
        "current_temperature",
        "hvac_action",
        "hvac_mode",
        "preset_mode",
        "temperature",
    },
    "cover": {"current_position"},
    "fan": {"percentage", "preset_mode"},
    "light": {"brightness", "color_mode", "color_temp_kelvin", "rgb_color"},
    "lock": set(),
    "media_player": {"media_content_type", "source", "state"},
    "person": set(),
    "sensor": {"device_class", "unit_of_measurement"},
    "switch": set(),
}


@dataclass(frozen=True)
class CheckpointEntityState:
    """Allowlisted state for a critical HA entity."""

    entity_id: str
    domain: str
    state: str
    attributes: dict[str, Any] = field(default_factory=dict)
    last_changed: str | None = None
    last_updated: str | None = None

    def as_dict(self) -> dict[str, Any]:
        """Serialize the entity state."""
        return {
            "entity_id": self.entity_id,
            "domain": self.domain,
            "state": self.state,
            "attributes": dict(self.attributes),
            "last_changed": self.last_changed,
            "last_updated": self.last_updated,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CheckpointEntityState | None":
        """Deserialize an entity state, ignoring malformed payloads."""
        entity_id = str(raw.get("entity_id") or "").strip()
        domain = str(raw.get("domain") or "").strip()
        state = str(raw.get("state") or "").strip()
        if not entity_id or not domain or not state:
            return None
        attributes = raw.get("attributes")
        return cls(
            entity_id=entity_id,
            domain=domain,
            state=state,
            attributes=dict(attributes) if isinstance(attributes, dict) else {},
            last_changed=_optional_str(raw.get("last_changed")),
            last_updated=_optional_str(raw.get("last_updated")),
        )

    @classmethod
    def from_ha_state(cls, entity_id: str, state_obj: Any) -> "CheckpointEntityState":
        """Build a redacted checkpoint state from a HA State-like object."""
        domain = entity_id.split(".", 1)[0]
        return cls(
            entity_id=entity_id,
            domain=domain,
            state=str(getattr(state_obj, "state", "unknown") or "unknown"),
            attributes=allowlisted_attributes(
                domain,
                getattr(state_obj, "attributes", {}) or {},
            ),
            last_changed=_dt_to_str(getattr(state_obj, "last_changed", None)),
            last_updated=_dt_to_str(getattr(state_obj, "last_updated", None)),
        )


@dataclass(frozen=True)
class RuntimeCheckpoint:
    """Versioned runtime checkpoint persisted outside the main runtime stores."""

    entry_id: str
    reason: str
    ha_started_at: str | None = None
    heima_started_at: str | None = None
    runtime: dict[str, Any] = field(default_factory=dict)
    critical_entities: tuple[CheckpointEntityState, ...] = ()
    manual_hold: dict[str, Any] = field(default_factory=dict)
    runtime_confirmations: dict[str, Any] = field(default_factory=dict)
    heating: dict[str, Any] = field(default_factory=dict)
    observability: dict[str, Any] = field(default_factory=dict)
    schema_version: int = CHECKPOINT_SCHEMA_VERSION
    checkpoint_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        """Serialize the checkpoint for HA storage."""
        return {
            "schema_version": self.schema_version,
            "checkpoint_id": self.checkpoint_id,
            "entry_id": self.entry_id,
            "created_at": self.created_at,
            "ha_started_at": self.ha_started_at,
            "heima_started_at": self.heima_started_at,
            "reason": self.reason,
            "runtime": _json_safe_dict(self.runtime),
            "critical_entities": [
                entity.as_dict() for entity in self.critical_entities[:MAX_CHECKPOINT_ENTITIES]
            ],
            "manual_hold": _json_safe_dict(self.manual_hold),
            "runtime_confirmations": _json_safe_dict(self.runtime_confirmations),
            "heating": _json_safe_dict(self.heating),
            "observability": _json_safe_dict(self.observability),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RuntimeCheckpoint | None":
        """Deserialize a checkpoint, tolerating future schema additions."""
        try:
            schema_version = int(raw.get("schema_version", CHECKPOINT_SCHEMA_VERSION))
        except (TypeError, ValueError):
            return None
        if schema_version < 1:
            return None
        entry_id = str(raw.get("entry_id") or "").strip()
        checkpoint_id = str(raw.get("checkpoint_id") or "").strip()
        created_at = str(raw.get("created_at") or "").strip()
        reason = str(raw.get("reason") or "unknown").strip() or "unknown"
        if not entry_id or not checkpoint_id or not created_at:
            return None

        entities = []
        entities_raw = raw.get("critical_entities")
        if isinstance(entities_raw, list):
            for item in entities_raw[:MAX_CHECKPOINT_ENTITIES]:
                if not isinstance(item, dict):
                    continue
                entity = CheckpointEntityState.from_dict(item)
                if entity is not None:
                    entities.append(entity)

        return cls(
            schema_version=schema_version,
            checkpoint_id=checkpoint_id,
            entry_id=entry_id,
            created_at=created_at,
            ha_started_at=_optional_str(raw.get("ha_started_at")),
            heima_started_at=_optional_str(raw.get("heima_started_at")),
            reason=reason,
            runtime=_dict_or_empty(raw.get("runtime")),
            critical_entities=tuple(entities),
            manual_hold=_dict_or_empty(raw.get("manual_hold")),
            runtime_confirmations=_dict_or_empty(raw.get("runtime_confirmations")),
            heating=_dict_or_empty(raw.get("heating")),
            observability=_dict_or_empty(raw.get("observability")),
        )

    def semantic_key(self) -> str:
        """Return a stable key for write-on-change deduplication."""
        payload = self.as_dict()
        payload.pop("checkpoint_id", None)
        payload.pop("created_at", None)
        payload.pop("reason", None)
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def diagnostics(self) -> dict[str, Any]:
        """Return redacted checkpoint diagnostics."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at,
            "entry_id": self.entry_id,
            "reason": self.reason,
            "ha_started_at": self.ha_started_at,
            "heima_started_at": self.heima_started_at,
            "schema_version": self.schema_version,
            "critical_entity_count": len(self.critical_entities),
            "runtime_keys": sorted(self.runtime),
            "manual_hold_keys": sorted(self.manual_hold),
            "runtime_confirmation_keys": sorted(self.runtime_confirmations),
            "heating_keys": sorted(self.heating),
            "observability_keys": sorted(self.observability),
        }


class RuntimeCheckpointStore:
    """Durable one-checkpoint-per-entry store for recovery."""

    STORAGE_KEY = "heima_runtime_checkpoints"
    STORAGE_VERSION = 1
    _SAVE_DELAY_S = 5

    def __init__(self, hass: HomeAssistant) -> None:
        self._store: Store[dict[str, Any]] = Store(
            hass,
            version=self.STORAGE_VERSION,
            key=self.STORAGE_KEY,
        )
        self._checkpoints: dict[str, RuntimeCheckpoint] = {}
        self._loaded = False
        self._load_errors = 0

    async def async_load(self) -> None:
        """Load persisted checkpoints."""
        raw = await self._store.async_load()
        entries_raw: Any = {}
        if isinstance(raw, dict):
            data = raw.get("data")
            if isinstance(data, dict):
                entries_raw = data.get("entries", {})

        self._checkpoints.clear()
        self._load_errors = 0
        if isinstance(entries_raw, dict):
            for entry_id, payload in entries_raw.items():
                if not isinstance(payload, dict):
                    self._load_errors += 1
                    continue
                checkpoint = RuntimeCheckpoint.from_dict(payload)
                if checkpoint is None:
                    self._load_errors += 1
                    continue
                self._checkpoints[str(entry_id)] = checkpoint
        self._loaded = True

    async def async_save_checkpoint(
        self,
        checkpoint: RuntimeCheckpoint,
        *,
        flush: bool = False,
    ) -> None:
        """Replace the checkpoint for an entry and persist it."""
        if not self._loaded:
            await self.async_load()
        self._checkpoints[checkpoint.entry_id] = checkpoint
        self._evict_extra_entries()
        if flush:
            await self.async_flush()
        else:
            self._schedule_save()

    async def async_flush(self) -> None:
        """Immediately persist the in-memory checkpoint map."""
        if not self._loaded:
            await self.async_load()
        await self._store.async_save(self._serialize())

    def checkpoint_for_entry(self, entry_id: str) -> RuntimeCheckpoint | None:
        """Return the latest checkpoint for an entry."""
        return self._checkpoints.get(entry_id)

    def diagnostics(self) -> dict[str, Any]:
        """Return redacted storage diagnostics."""
        return {
            "storage_key": self.STORAGE_KEY,
            "storage_version": self.STORAGE_VERSION,
            "loaded": self._loaded,
            "entry_count": len(self._checkpoints),
            "load_errors": self._load_errors,
            "checkpoints": {
                entry_id: checkpoint.diagnostics()
                for entry_id, checkpoint in sorted(self._checkpoints.items())
            },
        }

    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._serialize, self._SAVE_DELAY_S)

    def _serialize(self) -> dict[str, Any]:
        return {
            "data": {
                "entries": {
                    entry_id: checkpoint.as_dict()
                    for entry_id, checkpoint in sorted(self._checkpoints.items())
                }
            }
        }

    def _evict_extra_entries(self) -> None:
        if len(self._checkpoints) <= MAX_CHECKPOINT_ENTRIES:
            return
        ordered = sorted(self._checkpoints.values(), key=lambda item: item.created_at)
        for checkpoint in ordered[: len(self._checkpoints) - MAX_CHECKPOINT_ENTRIES]:
            self._checkpoints.pop(checkpoint.entry_id, None)


def allowlisted_attributes(domain: str, attributes: dict[str, Any]) -> dict[str, Any]:
    """Return JSON-safe allowlisted attributes for checkpoint persistence."""
    allowed = _ATTRIBUTE_ALLOWLIST.get(domain, set())
    if not allowed:
        return {}
    redacted: dict[str, Any] = {}
    for key in sorted(allowed):
        if key not in attributes:
            continue
        value = _json_safe_value(attributes[key])
        if value is not None:
            redacted[key] = value
    return redacted


def _json_safe_dict(raw: dict[str, Any]) -> dict[str, Any]:
    safe = _json_safe_value(raw)
    return dict(safe) if isinstance(safe, dict) else {}


def _json_safe_value(value: Any) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, str):
        return value[:MAX_STRING_VALUE_LEN]
    if isinstance(value, tuple | list):
        return [
            item
            for raw_item in list(value)[:MAX_LIST_VALUE_LEN]
            if (item := _json_safe_value(raw_item)) is not None
        ]
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for raw_key, raw_item in list(value.items())[:MAX_DICT_VALUE_LEN]:
            key = str(raw_key)[:MAX_STRING_VALUE_LEN]
            item = _json_safe_value(raw_item)
            if item is not None:
                safe[key] = item
        return safe
    return None


def _dict_or_empty(raw: Any) -> dict[str, Any]:
    return _json_safe_dict(raw) if isinstance(raw, dict) else {}


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dt_to_str(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return _optional_str(value)
