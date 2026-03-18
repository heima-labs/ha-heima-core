"""Options flow: Rooms steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import area_registry as ar
from homeassistant.util import slugify

from ..const import OPT_ROOMS
from ..runtime.normalization.config import (
    ROOM_OCCUPANCY_STRATEGY_CONTRACT,
    normalize_signal_set_strategy_fields,
    validate_signal_set_strategy_fields,
)
from ._common import (
    ROOM_LOGIC,
    ROOM_OCCUPANCY_MODES,
    _entity_selector,
    _format_source_weights,
    _is_valid_slug,
    _multiline_text_selector,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _RoomsStepsMixin:
    """Mixin for rooms steps."""

    async def async_step_rooms_menu(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return self.async_show_menu(
            step_id="rooms_menu",
            menu_options=[
                "rooms_add",
                "rooms_edit",
                "rooms_remove",
                "rooms_import_areas",
                "rooms_save",
                "rooms_next",
            ],
            description_placeholders={"summary": self._rooms_menu_summary()},
        )

    async def async_step_rooms_add(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(step_id="rooms_add", data_schema=self._room_schema())

        user_input = self._normalize_room_payload(user_input)
        errors = self._validate_room_payload(user_input, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="rooms_add", data_schema=self._room_schema(user_input), errors=errors
            )

        rooms = self._rooms()
        rooms.append(user_input)
        self._store_list(OPT_ROOMS, rooms)
        return await self.async_step_rooms_menu()

    async def async_step_rooms_edit(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        rooms = self._rooms()
        if not rooms:
            return await self.async_step_rooms_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("room"): vol.In([r["room_id"] for r in rooms])})
            return self.async_show_form(step_id="rooms_edit", data_schema=schema)

        self._editing_room_id = user_input.get("room")
        return await self.async_step_rooms_edit_form()

    async def async_step_rooms_edit_form(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        rooms = self._rooms()
        if user_input is None:
            existing = self._find_by_key(rooms, "room_id", self._editing_room_id or "") or {}
            return self.async_show_form(
                step_id="rooms_edit_form", data_schema=self._room_schema(existing)
            )

        user_input = self._normalize_room_payload(user_input)
        errors = self._validate_room_payload(user_input, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="rooms_edit_form", data_schema=self._room_schema(user_input), errors=errors
            )

        updated = []
        for room in rooms:
            if room.get("room_id") == self._editing_room_id:
                updated.append(user_input)
            else:
                updated.append(room)
        self._store_list(OPT_ROOMS, updated)
        self._editing_room_id = None
        return await self.async_step_rooms_menu()

    async def async_step_rooms_remove(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        rooms = self._rooms()
        if not rooms:
            return await self.async_step_rooms_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("room"): vol.In([r["room_id"] for r in rooms])})
            return self.async_show_form(step_id="rooms_remove", data_schema=schema)

        room_id = user_input.get("room")
        updated = [r for r in rooms if r.get("room_id") != room_id]
        self._store_list(OPT_ROOMS, updated)
        self._remove_lighting_room_mapping(room_id)
        self._remove_room_from_zones(room_id)
        return await self.async_step_rooms_menu()

    async def async_step_rooms_next(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return await self.async_step_init()

    async def async_step_rooms_save(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Persist options and close the flow from Rooms menu."""
        return self.async_create_entry(title="", data=self._finalize_options())

    async def async_step_rooms_import_areas(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Import HA areas as rooms (merge with existing)."""
        area_reg = ar.async_get(self.hass)
        rooms = self._rooms()
        existing_room_ids = {r.get("room_id") for r in rooms}
        existing_area_ids = {r.get("area_id") for r in rooms if r.get("area_id")}

        for area in area_reg.async_list_areas():
            if area.id in existing_area_ids:
                continue
            room_id = slugify(area.name)
            if room_id in existing_room_ids:
                continue
            rooms.append(
                {
                    "room_id": room_id,
                    "display_name": area.name,
                    "area_id": area.id,
                    "occupancy_mode": "none",
                    "sources": [],
                    "logic": "any_of",
                    "on_dwell_s": 5,
                    "off_dwell_s": 120,
                    "max_on_s": None,
                }
            )
            existing_room_ids.add(room_id)

        self._store_list(OPT_ROOMS, rooms)
        return await self.async_step_rooms_menu()

    # ---- Schema ----

    def _room_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = dict(defaults or {})
        defaults["source_weights"] = _format_source_weights(defaults.get("source_weights"))
        from homeassistant.helpers.selector import selector as _sel
        schema = vol.Schema(
            {
                vol.Required("room_id", default=defaults.get("room_id", "")): cv.string,
                vol.Optional("display_name", default=defaults.get("display_name", "")): cv.string,
                vol.Optional("area_id"): _sel({"area": {}}),
                vol.Optional(
                    "occupancy_mode", default=defaults.get("occupancy_mode", "derived")
                ): vol.In(ROOM_OCCUPANCY_MODES),
                vol.Optional("sources"): _entity_selector(["binary_sensor", "sensor"], multiple=True),
                vol.Optional("logic", default=defaults.get("logic", "any_of")): vol.In(ROOM_LOGIC),
                vol.Optional("weight_threshold"): vol.Coerce(float),
                vol.Optional("source_weights"): _multiline_text_selector(),
                vol.Optional("on_dwell_s", default=defaults.get("on_dwell_s", 5)): cv.positive_int,
                vol.Optional("off_dwell_s", default=defaults.get("off_dwell_s", 120)): cv.positive_int,
                vol.Optional("max_on_s", default=defaults.get("max_on_s")): vol.Any(None, cv.positive_int),
            }
        )
        return self._with_suggested(schema, defaults)

    # ---- Validator ----

    def _validate_room_payload(self, payload: dict[str, Any], is_edit: bool) -> dict[str, str]:
        errors: dict[str, str] = {}
        room_id = payload.get("room_id", "")
        if is_edit:
            errors.update(self._error_if_immutable_changed(payload, "room_id", self._editing_room_id))
        if not room_id:
            errors["room_id"] = "required"
        elif not _is_valid_slug(room_id):
            errors["room_id"] = "invalid_slug"
        if room_id.startswith("heima_"):
            errors["room_id"] = "reserved_prefix"

        existing_ids = {r["room_id"] for r in self._rooms()}
        if not is_edit:
            if room_id in existing_ids:
                errors["room_id"] = "duplicate"
        elif room_id in (existing_ids - {self._editing_room_id}):
            errors["room_id"] = "duplicate"

        area_id = payload.get("area_id")
        if area_id:
            existing_area_ids = {r.get("area_id") for r in self._rooms() if r.get("area_id")}
            if is_edit:
                existing_room = self._find_by_key(self._rooms(), "room_id", self._editing_room_id or "")
                existing_area_id = existing_room.get("area_id") if existing_room else None
                existing_area_ids.discard(existing_area_id)
            if area_id in existing_area_ids:
                errors["area_id"] = "duplicate"

        occupancy_mode = str(payload.get("occupancy_mode", "derived"))
        if occupancy_mode not in ROOM_OCCUPANCY_MODES:
            errors["occupancy_mode"] = "invalid_option"

        sources = payload.get("sources", [])
        if occupancy_mode == "derived" and not sources:
            errors["sources"] = "required"
        errors.update(
            validate_signal_set_strategy_fields(
                payload=payload,
                strategy_key="logic",
                sources=sources,
                contract=ROOM_OCCUPANCY_STRATEGY_CONTRACT,
            )
        )
        return errors

    # ---- Normalization ----

    def _normalize_room_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["room_id"] = str(data.get("room_id", "")).strip()
        data["display_name"] = str(data.get("display_name", "") or "").strip()
        if data.get("area_id"):
            data["area_id"] = str(data["area_id"])
        data["sources"] = self._normalize_multi_value(data.get("sources"))
        occupancy_mode = str(data.get("occupancy_mode", "") or "").strip()
        if occupancy_mode not in ROOM_OCCUPANCY_MODES:
            occupancy_mode = "derived"
        data["occupancy_mode"] = occupancy_mode
        normalize_signal_set_strategy_fields(
            data,
            strategy_key="logic",
            contract=ROOM_OCCUPANCY_STRATEGY_CONTRACT,
        )
        return data
