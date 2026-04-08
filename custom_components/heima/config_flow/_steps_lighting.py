"""Options flow: Lighting steps (per-room scenes + zones)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import OPT_LIGHTING_ROOMS, OPT_LIGHTING_ZONES
from ._common import (
    _entity_selector,
    _is_valid_slug,
    _scene_selector,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _LightingStepsMixin:
    """Mixin for lighting steps."""

    # ---- Lighting: per-room scenes ----

    async def async_step_lighting_rooms_menu(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return self.async_show_menu(
            step_id="lighting_rooms_menu",
            menu_options=[
                "lighting_rooms_edit",
                "lighting_rooms_save",
                "lighting_rooms_next",
            ],
            description_placeholders={"summary": self._lighting_menu_summary()},
        )

    async def async_step_lighting_rooms_edit(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        room_ids = self._room_ids()
        if not room_ids:
            return await self.async_step_lighting_zones_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("room"): vol.In(room_ids)})
            return self.async_show_form(step_id="lighting_rooms_edit", data_schema=schema)

        self._editing_lighting_room_id = user_input.get("room")
        return await self.async_step_lighting_rooms_edit_form()

    async def async_step_lighting_rooms_edit_form(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        if user_input is None:
            existing = self._find_by_key(
                self._lighting_rooms(), "room_id", self._editing_lighting_room_id or ""
            ) or {"room_id": self._editing_lighting_room_id}
            return self.async_show_form(
                step_id="lighting_rooms_edit_form",
                data_schema=self._lighting_room_schema(existing),
            )

        user_input = self._normalize_lighting_room_payload(user_input)
        errors = self._validate_lighting_room_payload(user_input)
        if errors:
            return self.async_show_form(
                step_id="lighting_rooms_edit_form",
                data_schema=self._lighting_room_schema(user_input),
                errors=errors,
            )

        rooms = self._lighting_rooms()
        updated = [r for r in rooms if r.get("room_id") != user_input.get("room_id")]
        updated.append(user_input)
        self._store_list(OPT_LIGHTING_ROOMS, updated)
        self._editing_lighting_room_id = None
        return await self.async_step_lighting_rooms_menu()

    async def async_step_lighting_rooms_next(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return await self.async_step_lighting_zones_menu()

    async def async_step_lighting_rooms_save(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Persist options and close the flow from Lighting Rooms menu."""
        return self.async_create_entry(title="", data=self._finalize_options())

    # ---- Schema / validator / normalizer ----

    def _lighting_room_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        schema = vol.Schema(
            {
                vol.Required("room_id", default=defaults.get("room_id", "")): cv.string,
                vol.Optional("scene_evening"): _scene_selector(),
                vol.Optional("scene_relax"): _scene_selector(),
                vol.Optional("scene_night"): _scene_selector(),
                vol.Optional("scene_off"): _scene_selector(),
                vol.Optional(
                    "enable_manual_hold", default=defaults.get("enable_manual_hold", True)
                ): bool,
            }
        )
        return self._with_suggested(schema, defaults)

    def _validate_lighting_room_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        if self._editing_lighting_room_id is not None:
            errors.update(
                self._error_if_immutable_changed(payload, "room_id", self._editing_lighting_room_id)
            )
        if not payload.get("room_id"):
            errors["room_id"] = "required"
        elif not _is_valid_slug(payload.get("room_id", "")):
            errors["room_id"] = "invalid_slug"
        elif payload.get("room_id", "").startswith("heima_"):
            errors["room_id"] = "reserved_prefix"
        elif payload.get("room_id") not in set(self._room_ids()):
            errors["room_id"] = "unknown_room"
        return errors

    def _normalize_lighting_room_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["room_id"] = str(data.get("room_id", "")).strip()
        for key in ("scene_evening", "scene_relax", "scene_night", "scene_off"):
            if data.get(key):
                data[key] = str(data[key])
            elif key in data and data[key] in ("", []):
                data.pop(key, None)
        data["enable_manual_hold"] = bool(data.get("enable_manual_hold", True))
        return data

    def _remove_lighting_room_mapping(self, room_id: str) -> None:
        rooms = [r for r in self._lighting_rooms() if r.get("room_id") != room_id]
        self._store_list(OPT_LIGHTING_ROOMS, rooms)

    # ---- Lighting: zones ----

    async def async_step_lighting_zones_menu(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return self.async_show_menu(
            step_id="lighting_zones_menu",
            menu_options=[
                "lighting_zones_add",
                "lighting_zones_edit",
                "lighting_zones_remove",
                "lighting_zones_save",
                "lighting_zones_next",
            ],
        )

    async def async_step_lighting_zones_add(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        if user_input is None:
            return self.async_show_form(
                step_id="lighting_zones_add", data_schema=self._lighting_zone_schema()
            )

        user_input = self._normalize_lighting_zone_payload(user_input)
        errors = self._validate_lighting_zone_payload(user_input, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="lighting_zones_add",
                data_schema=self._lighting_zone_schema(user_input),
                errors=errors,
            )

        zones = self._lighting_zones()
        zones.append(user_input)
        self._store_list(OPT_LIGHTING_ZONES, zones)
        return await self.async_step_lighting_zones_menu()

    async def async_step_lighting_zones_edit(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        zones = self._lighting_zones()
        if not zones:
            return await self.async_step_lighting_zones_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("zone"): vol.In([z["zone_id"] for z in zones])})
            return self.async_show_form(step_id="lighting_zones_edit", data_schema=schema)

        self._editing_zone_id = user_input.get("zone")
        return await self.async_step_lighting_zones_edit_form()

    async def async_step_lighting_zones_edit_form(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        zones = self._lighting_zones()
        if user_input is None:
            existing = self._find_by_key(zones, "zone_id", self._editing_zone_id or "") or {}
            return self.async_show_form(
                step_id="lighting_zones_edit_form",
                data_schema=self._lighting_zone_schema(existing),
            )

        user_input = self._normalize_lighting_zone_payload(user_input)
        errors = self._validate_lighting_zone_payload(user_input, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="lighting_zones_edit_form",
                data_schema=self._lighting_zone_schema(user_input),
                errors=errors,
            )

        updated = []
        for zone in zones:
            if zone.get("zone_id") == self._editing_zone_id:
                updated.append(user_input)
            else:
                updated.append(zone)
        self._store_list(OPT_LIGHTING_ZONES, updated)
        self._editing_zone_id = None
        return await self.async_step_lighting_zones_menu()

    async def async_step_lighting_zones_remove(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        zones = self._lighting_zones()
        if not zones:
            return await self.async_step_lighting_zones_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("zone"): vol.In([z["zone_id"] for z in zones])})
            return self.async_show_form(step_id="lighting_zones_remove", data_schema=schema)

        self._removing_zone_id = user_input.get("zone")
        return await self.async_step_lighting_zones_remove_confirm()

    async def async_step_lighting_zones_remove_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        zone_id = getattr(self, "_removing_zone_id", None)
        if not zone_id:
            return await self.async_step_lighting_zones_menu()

        zones = self._lighting_zones()
        existing = self._find_by_key(zones, "zone_id", zone_id) or {}
        zone_label = existing.get("display_name") or zone_id

        if user_input is None:
            schema = vol.Schema({vol.Required("confirm", default=False): bool})
            return self.async_show_form(
                step_id="lighting_zones_remove_confirm",
                data_schema=schema,
                description_placeholders={"zone_label": zone_label},
            )

        if not bool(user_input.get("confirm")):
            self._removing_zone_id = None
            return await self.async_step_lighting_zones_menu()

        updated = [z for z in zones if z.get("zone_id") != zone_id]
        self._store_list(OPT_LIGHTING_ZONES, updated)
        self._removing_zone_id = None
        return await self.async_step_lighting_zones_menu()

    async def async_step_lighting_zones_next(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return await self.async_step_init()

    async def async_step_lighting_zones_save(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Persist options and close the flow from Lighting Zones menu."""
        return self.async_create_entry(title="", data=self._finalize_options())

    # ---- Schema / validator / normalizer ----

    def _lighting_zone_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        schema = vol.Schema(
            {
                vol.Required("zone_id", default=defaults.get("zone_id", "")): cv.string,
                vol.Optional("display_name", default=defaults.get("display_name", "")): cv.string,
                vol.Required("rooms"): cv.multi_select(self._room_ids()),
            }
        )
        return self._with_suggested(schema, defaults)

    def _validate_lighting_zone_payload(self, payload: dict[str, Any], is_edit: bool) -> dict[str, str]:
        errors: dict[str, str] = {}
        zone_id = payload.get("zone_id", "")
        if is_edit:
            errors.update(self._error_if_immutable_changed(payload, "zone_id", self._editing_zone_id))
        if not zone_id:
            errors["zone_id"] = "required"
        elif not _is_valid_slug(zone_id):
            errors["zone_id"] = "invalid_slug"
        if zone_id.startswith("heima_"):
            errors["zone_id"] = "reserved_prefix"

        existing_ids = {z["zone_id"] for z in self._lighting_zones()}
        if not is_edit:
            if zone_id in existing_ids:
                errors["zone_id"] = "duplicate"
        elif zone_id in (existing_ids - {self._editing_zone_id}):
            errors["zone_id"] = "duplicate"

        rooms = payload.get("rooms", [])
        if not rooms:
            errors["rooms"] = "required"
        else:
            unknown_rooms = [r for r in rooms if r not in set(self._room_ids())]
            if unknown_rooms:
                errors["rooms"] = "unknown_room"
        return errors

    def _normalize_lighting_zone_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["zone_id"] = str(data.get("zone_id", "")).strip()
        data["display_name"] = str(data.get("display_name", "") or "").strip()
        data["rooms"] = self._normalize_multi_value(data.get("rooms"))
        return data

    def _remove_room_from_zones(self, room_id: str) -> None:
        zones = []
        for zone in self._lighting_zones():
            rooms = [r for r in zone.get("rooms", []) if r != room_id]
            if not rooms:
                continue
            updated = dict(zone)
            updated["rooms"] = rooms
            zones.append(updated)
        self._store_list(OPT_LIGHTING_ZONES, zones)
