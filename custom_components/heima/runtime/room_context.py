"""Room-scoped device context derived from configured HA entities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ..const import OPT_ACTIVITY_BINDINGS, OPT_HOUSE_STATE_CONFIG, OPT_ROOMS
from .media_activity import media_entity_is_active
from .normalization.service import InputNormalizer


@dataclass(frozen=True)
class RoomDeviceContext:
    """Canonical per-room device context for house-state inference."""

    room_id: str
    media_on: bool = False
    lights_on: bool = False
    work_activity: bool = False
    pc_active: bool = False

    def as_dict(self) -> dict[str, Any]:
        """Serialize context to snapshot/canonical state storage."""
        return {
            "room_id": self.room_id,
            "media_on": self.media_on,
            "lights_on": self.lights_on,
            "work_activity": self.work_activity,
            "pc_active": self.pc_active,
        }

    @classmethod
    def from_dict(cls, raw: Any) -> "RoomDeviceContext | None":
        """Deserialize a context payload, ignoring malformed records."""
        if not isinstance(raw, dict):
            return None
        room_id = str(raw.get("room_id") or "").strip()
        if not room_id:
            return None
        return cls(
            room_id=room_id,
            media_on=bool(raw.get("media_on", False)),
            lights_on=bool(raw.get("lights_on", False)),
            work_activity=bool(raw.get("work_activity", False)),
            pc_active=bool(raw.get("pc_active", False)),
        )


class RoomDeviceContextBuilder:
    """Build room-scoped context from user-configured entities and HA areas."""

    def __init__(self, hass: HomeAssistant, normalizer: InputNormalizer) -> None:
        self._hass = hass
        self._normalizer = normalizer
        self._entity_to_room: dict[str, str] = {}
        self._stale = True

    @property
    def entity_to_room(self) -> dict[str, str]:
        """Return the current configured entity to room mapping."""
        return dict(self._entity_to_room)

    def mark_stale(self) -> None:
        """Mark cached area mapping stale; next compute rebuilds it."""
        self._stale = True

    def compute(
        self,
        *,
        options: dict[str, Any],
        lights_on: dict[str, bool] | None = None,
    ) -> dict[str, RoomDeviceContext]:
        """Return per-room context for configured entities only."""
        entity_roles = _configured_entity_roles(options, lights_on=lights_on)
        if self._stale:
            self._entity_to_room = self._build_entity_to_room(options, entity_roles)
            self._stale = False

        by_room: dict[str, RoomDeviceContext] = {}
        for entity_id, roles in entity_roles.items():
            room_id = self._entity_to_room.get(entity_id)
            if not room_id:
                continue
            current = by_room.setdefault(room_id, RoomDeviceContext(room_id=room_id))
            media_on = current.media_on
            lights_room_on = current.lights_on
            work_activity = current.work_activity
            pc_active = current.pc_active

            if "media" in roles and _media_is_on(self._hass, self._normalizer, entity_id):
                media_on = True
            if "work_activity" in roles and _normalizer_is_on(self._normalizer, entity_id):
                work_activity = True
            if "pc_active" in roles and _normalizer_is_on(self._normalizer, entity_id):
                pc_active = True
            if "light" in roles and bool((lights_on or {}).get(entity_id, False)):
                lights_room_on = True

            by_room[room_id] = RoomDeviceContext(
                room_id=room_id,
                media_on=media_on,
                lights_on=lights_room_on,
                work_activity=work_activity,
                pc_active=pc_active,
            )
        return dict(sorted(by_room.items()))

    def _build_entity_to_room(
        self,
        options: dict[str, Any],
        entity_roles: dict[str, set[str]],
    ) -> dict[str, str]:
        try:
            entity_registry = er.async_get(self._hass)
            device_registry = dr.async_get(self._hass)
        except (TypeError, AttributeError):
            return {}

        area_to_room = _area_to_room(options)
        if not area_to_room:
            return {}

        mapping: dict[str, str] = {}
        for entity_id in sorted(entity_roles):
            area_id = _entity_area_id(
                entity_id,
                entity_registry=entity_registry,
                device_registry=device_registry,
            )
            room_id = area_to_room.get(area_id)
            if room_id:
                mapping[entity_id] = room_id
        return mapping


def serialize_room_device_context(
    context: dict[str, RoomDeviceContext],
) -> dict[str, dict[str, Any]]:
    """Serialize a room context mapping."""
    return {room_id: ctx.as_dict() for room_id, ctx in sorted(context.items())}


def deserialize_room_device_context(raw: Any) -> dict[str, RoomDeviceContext]:
    """Deserialize a room context mapping."""
    if not isinstance(raw, dict):
        return {}
    result: dict[str, RoomDeviceContext] = {}
    for key, value in raw.items():
        payload = dict(value) if isinstance(value, dict) else {}
        payload.setdefault("room_id", str(key))
        ctx = RoomDeviceContext.from_dict(payload)
        if ctx is not None:
            result[ctx.room_id] = ctx
    return dict(sorted(result.items()))


def _configured_entity_roles(
    options: dict[str, Any],
    *,
    lights_on: dict[str, bool] | None,
) -> dict[str, set[str]]:
    roles: dict[str, set[str]] = {}
    house_state_cfg = options.get(OPT_HOUSE_STATE_CONFIG, {})
    if not isinstance(house_state_cfg, dict):
        house_state_cfg = {}
    for entity_id in _entity_list(house_state_cfg.get("media_active_entities")):
        roles.setdefault(entity_id, set()).add("media")
    for entity_id in _entity_list(house_state_cfg.get("work_activity_entities")):
        roles.setdefault(entity_id, set()).add("work_activity")

    pc_entity = _configured_pc_entity(options.get(OPT_ACTIVITY_BINDINGS, {}))
    if pc_entity:
        roles.setdefault(pc_entity, set()).add("pc_active")

    for entity_id in _entity_list(list((lights_on or {}).keys())):
        roles.setdefault(entity_id, set()).add("light")
    return roles


def _entity_list(raw: Any) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw.strip()] if raw.strip() else []
    if isinstance(raw, dict):
        return [str(key).strip() for key, value in raw.items() if value and str(key).strip()]
    if isinstance(raw, (list, tuple, set)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _configured_pc_entity(raw_bindings: Any) -> str:
    if not isinstance(raw_bindings, dict):
        return ""
    raw_pc = raw_bindings.get("pc_active", {})
    if not isinstance(raw_pc, dict):
        return ""
    return str(raw_pc.get("entity_id") or raw_pc.get("pc_power_entity") or "").strip()


def _area_to_room(options: dict[str, Any]) -> dict[str, str]:
    rooms = options.get(OPT_ROOMS, [])
    if not isinstance(rooms, list):
        return {}
    mapping: dict[str, str] = {}
    for room in rooms:
        if not isinstance(room, dict):
            continue
        room_id = str(room.get("room_id") or "").strip()
        area_id = str(room.get("area_id") or "").strip()
        if room_id and area_id:
            mapping[area_id] = room_id
    return mapping


def _entity_area_id(
    entity_id: str,
    *,
    entity_registry: Any,
    device_registry: Any,
) -> str:
    entities = getattr(entity_registry, "entities", {})
    entry = entities.get(entity_id)
    if entry is None:
        return ""
    area_id = str(getattr(entry, "area_id", "") or "").strip()
    if area_id:
        return area_id
    device_id = str(getattr(entry, "device_id", "") or "").strip()
    if not device_id:
        return ""
    device = getattr(device_registry, "devices", {}).get(device_id)
    return str(getattr(device, "area_id", "") or "").strip()


def _normalizer_is_on(normalizer: InputNormalizer, entity_id: str) -> bool:
    return normalizer.boolean_signal(entity_id).state == "on"


def _media_is_on(hass: HomeAssistant, normalizer: InputNormalizer, entity_id: str) -> bool:
    state_obj = hass.states.get(entity_id)
    raw_state = getattr(state_obj, "state", None) if state_obj is not None else None
    return media_entity_is_active(entity_id, str(raw_state) if raw_state is not None else None) or (
        normalizer.boolean_signal(entity_id).state == "on"
    )
