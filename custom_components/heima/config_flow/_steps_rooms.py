"""Options flow: Rooms steps."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv

from ..const import OPT_ROOMS
from ..room_inventory import build_room_inventory_summary
from ..room_sources import (
    format_room_signals_for_form,
    normalize_room_signal_config,
    normalize_room_signals,
    room_learning_source_entity_ids,
    room_occupancy_source_entity_ids,
)
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

    _editing_lighting_room_id: str | None

    async def _async_bootstrap_ha_bindings(self) -> None:
        importer = getattr(super(), "_async_bootstrap_ha_bindings", None)
        if callable(importer):
            await importer()
        sync_bindings = getattr(self, "_sync_ha_backed_bindings", None)
        if callable(sync_bindings):
            sync_bindings()

    async def async_step_rooms_menu(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        sync_bindings = getattr(self, "_sync_ha_backed_bindings", None)
        if callable(sync_bindings):
            sync_bindings()
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
            return self.async_show_form(
                step_id="rooms_add",
                data_schema=self._room_schema(),
                description_placeholders=self._room_signal_placeholders({}),
            )

        user_input = self._normalize_room_payload(user_input)
        errors = self._validate_room_payload(user_input, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="rooms_add",
                data_schema=self._room_schema(user_input),
                errors=errors,
                description_placeholders=self._room_signal_placeholders(user_input),
            )

        user_input = await self._async_ensure_room_area(user_input)
        if not user_input.get("area_id"):
            return self.async_show_form(
                step_id="rooms_add",
                data_schema=self._room_schema(user_input),
                errors={"area_id": "area_sync_failed"},
                description_placeholders=self._room_signal_placeholders(user_input),
            )
        rooms = self._rooms()
        user_input["source"] = "ha_area_registry"
        user_input["ha_source_name"] = str(
            user_input.get("display_name") or user_input.get("room_id") or ""
        )
        user_input["ha_sync_status"] = "configured"
        user_input["heima_reviewed"] = True
        rooms.append(user_input)
        self._store_list(OPT_ROOMS, rooms)
        return await self.async_step_rooms_menu()

    async def async_step_rooms_edit(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        rooms = self._rooms()
        if not rooms:
            return await self.async_step_rooms_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("room"): vol.In(self._room_choice_map(rooms))})
            return self.async_show_form(step_id="rooms_edit", data_schema=schema)

        self._editing_room_id = self._resolve_choice_value(
            self._room_choice_map(rooms), user_input.get("room")
        )
        return await self.async_step_rooms_edit_actions()

    async def async_step_rooms_edit_actions(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        room_id = str(getattr(self, "_editing_room_id", "") or "").strip()
        if not room_id:
            return await self.async_step_rooms_menu()

        room = self._find_by_key(self._rooms(), "room_id", room_id) or {}
        room_label = str(room.get("display_name") or room_id).strip()
        return self.async_show_menu(
            step_id="rooms_edit_actions",
            menu_options=[
                "rooms_edit_form",
                "rooms_edit_lighting",
            ],
            description_placeholders={"room_label": room_label},
        )

    async def async_step_rooms_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        rooms = self._rooms()
        if user_input is None:
            existing = self._find_by_key(rooms, "room_id", self._editing_room_id or "") or {}
            return self.async_show_form(
                step_id="rooms_edit_form",
                data_schema=self._room_schema(existing),
                description_placeholders=self._room_form_placeholders(existing),
            )

        raw_input = dict(user_input)
        user_input = self._normalize_room_payload(user_input)
        errors = self._validate_room_payload(user_input, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="rooms_edit_form",
                data_schema=self._room_schema(raw_input),
                errors=errors,
                description_placeholders=self._room_form_placeholders(user_input),
            )

        existing_room = self._find_by_key(rooms, "room_id", self._editing_room_id or "") or {}
        user_input = await self._async_ensure_room_area(user_input, existing_room=existing_room)
        if not user_input.get("area_id"):
            return self.async_show_form(
                step_id="rooms_edit_form",
                data_schema=self._room_schema(raw_input),
                errors={"area_id": "area_sync_failed"},
                description_placeholders=self._room_form_placeholders(user_input),
            )
        updated = []
        for room in rooms:
            if room.get("room_id") == self._editing_room_id:
                user_input["source"] = "ha_area_registry"
                user_input["ha_source_name"] = str(
                    user_input.get("display_name") or user_input.get("room_id") or ""
                )
                user_input["ha_sync_status"] = "configured"
                user_input["heima_reviewed"] = True
                updated.append(user_input)
            else:
                updated.append(room)
        self._store_list(OPT_ROOMS, updated)
        self._editing_room_id = None
        return await self.async_step_rooms_menu()

    async def async_step_rooms_edit_lighting(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        room_id = str(getattr(self, "_editing_room_id", "") or "").strip()
        if not room_id:
            return await self.async_step_rooms_menu()
        self._editing_lighting_room_id = room_id
        return await self.async_step_lighting_rooms_edit_form()

    async def async_step_rooms_remove(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        rooms = self._rooms()
        if not rooms:
            return await self.async_step_rooms_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("room"): vol.In(self._room_choice_map(rooms))})
            return self.async_show_form(step_id="rooms_remove", data_schema=schema)

        self._removing_room_id = self._resolve_choice_value(
            self._room_choice_map(rooms), user_input.get("room")
        )
        return await self.async_step_rooms_remove_confirm()

    async def async_step_rooms_remove_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        room_id = getattr(self, "_removing_room_id", None)
        if not room_id:
            return await self.async_step_rooms_menu()

        rooms = self._rooms()
        existing = self._find_by_key(rooms, "room_id", room_id) or {}
        room_label = existing.get("display_name") or room_id

        if user_input is None:
            schema = vol.Schema({vol.Required("confirm", default=False): bool})
            return self.async_show_form(
                step_id="rooms_remove_confirm",
                data_schema=schema,
                description_placeholders={"room_label": room_label},
            )

        if not bool(user_input.get("confirm")):
            self._removing_room_id = None
            return await self.async_step_rooms_menu()

        updated = [r for r in rooms if r.get("room_id") != room_id]
        self._store_list(OPT_ROOMS, updated)
        await self._async_delete_room_area(existing)
        self._remove_lighting_room_mapping(room_id)
        self._remove_room_from_zones(room_id)
        self._removing_room_id = None
        return await self.async_step_rooms_menu()

    async def async_step_rooms_next(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return await self.async_step_init()

    async def async_step_rooms_save(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Persist options and close the flow from Rooms menu."""
        return self.async_create_entry(title="", data=self._finalize_options())

    async def async_step_rooms_import_areas(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        """Force a manual HA rescan for rooms."""
        sync_bindings = getattr(self, "_sync_ha_backed_bindings", None)
        if callable(sync_bindings):
            sync_bindings()
        return await self.async_step_rooms_menu()

    # ---- Schema ----

    def _room_schema(
        self,
        defaults: dict[str, Any] | None = None,
    ) -> vol.Schema:
        defaults = dict(defaults or {})
        defaults["occupancy_sources"] = room_occupancy_source_entity_ids(defaults)
        defaults["learning_sources"] = room_learning_source_entity_ids(defaults)
        defaults["source_weights"] = _format_source_weights(defaults.get("source_weights"))
        defaults["signals"] = format_room_signals_for_form(defaults.get("signals"))
        from homeassistant.helpers.selector import selector as _sel

        schema_dict: dict[Any, Any] = {
            vol.Required("room_id", default=defaults.get("room_id", "")): cv.string,
            vol.Optional("display_name", default=defaults.get("display_name", "")): cv.string,
            vol.Optional("area_id"): _sel({"area": {}}),
            vol.Optional("learning_sources"): _entity_selector(
                ["binary_sensor", "sensor", "switch"], multiple=True
            ),
            vol.Optional(
                "signals", default=defaults.get("signals", "")
            ): _multiline_text_selector(),
            vol.Optional(
                "occupancy_mode", default=defaults.get("occupancy_mode", "derived")
            ): vol.In(ROOM_OCCUPANCY_MODES),
            vol.Optional("occupancy_sources"): _entity_selector(
                ["binary_sensor", "sensor"], multiple=True
            ),
            vol.Optional("logic", default=defaults.get("logic", "any_of")): vol.In(ROOM_LOGIC),
            vol.Optional("weight_threshold"): vol.Coerce(float),
            vol.Optional("source_weights"): _multiline_text_selector(),
            vol.Optional("on_dwell_s", default=defaults.get("on_dwell_s", 5)): cv.positive_int,
            vol.Optional("off_dwell_s", default=defaults.get("off_dwell_s", 120)): cv.positive_int,
            vol.Optional("max_on_s", default=defaults.get("max_on_s")): vol.Any(
                None, cv.positive_int
            ),
        }
        schema = vol.Schema(schema_dict)
        return self._with_suggested(schema, defaults)

    # ---- Validator ----

    def _validate_room_payload(self, payload: dict[str, Any], is_edit: bool) -> dict[str, str]:
        errors: dict[str, str] = {}
        signal_error = str(getattr(self, "_room_signal_validation_error", "") or "").strip()
        if signal_error:
            errors["signals"] = signal_error
        room_id = payload.get("room_id", "")
        if is_edit:
            errors.update(
                self._error_if_immutable_changed(payload, "room_id", self._editing_room_id)
            )
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
            area_reg = self._area_registry()
            area = self._get_area(area_reg, area_id) if area_reg is not None else None
            if area_reg is not None and area is None:
                errors["area_id"] = "unknown_area"
            existing_area_ids = {r.get("area_id") for r in self._rooms() if r.get("area_id")}
            if is_edit:
                existing_room = self._find_by_key(
                    self._rooms(), "room_id", self._editing_room_id or ""
                )
                existing_area_id = existing_room.get("area_id") if existing_room else None
                existing_area_ids.discard(existing_area_id)
            if area_id in existing_area_ids:
                errors["area_id"] = "duplicate"

        occupancy_mode = str(payload.get("occupancy_mode", "derived"))
        if occupancy_mode not in ROOM_OCCUPANCY_MODES:
            errors["occupancy_mode"] = "invalid_option"

        sources = room_occupancy_source_entity_ids(payload)
        if occupancy_mode == "derived" and not sources:
            errors["occupancy_sources"] = "required"
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
        self._room_signal_validation_error = None
        data["room_id"] = str(data.get("room_id", "")).strip()
        data["display_name"] = str(data.get("display_name", "") or "").strip()
        if data.get("area_id"):
            data["area_id"] = str(data["area_id"])
        for key in ("source", "ha_source_name", "ha_sync_status", "heima_reviewed"):
            if key in payload:
                data[key] = payload[key]
        if "occupancy_sources" in data:
            data["occupancy_sources"] = self._normalize_multi_value(data.get("occupancy_sources"))
        if "learning_sources" in data:
            data["learning_sources"] = self._normalize_multi_value(data.get("learning_sources"))
        data = normalize_room_signal_config(data)
        if "signals" in data:
            try:
                data["signals"] = normalize_room_signals(
                    data.get("signals"),
                    state_getter=self.hass.states.get,
                )
            except ValueError as exc:
                self._room_signal_validation_error = str(exc)
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

    def _room_choice_map(self, rooms: list[dict[str, Any]]) -> dict[str, str]:
        return {
            self._room_choice_label(room): str(room.get("room_id") or "")
            for room in rooms
            if str(room.get("room_id") or "").strip()
        }

    def _room_choice_label(self, room: dict[str, Any]) -> str:
        label = str(room.get("display_name") or room.get("room_id") or "").strip()
        status = str(room.get("ha_sync_status") or "").strip()
        if status == "new":
            return f"{label} [new]"
        if status == "configured":
            return f"{label} [configured]"
        if status == "orphaned":
            return f"{label} [orphaned]"
        return label

    def _room_inventory_placeholders(self, room: dict[str, Any]) -> dict[str, str]:
        try:
            summary = build_room_inventory_summary(self.hass, [room])
            item = list(summary.get("rooms") or [{}])[0]
        except Exception:
            item = {}
        area_label = str(item.get("area_id") or "—")
        inventory_entity_total = str(int(item.get("inventory_entity_total") or 0))
        suggested_occupancy = self._format_inventory_list(item.get("suggested_occupancy_sources"))
        suggested_learning = self._format_inventory_list(item.get("suggested_learning_sources"))
        suggested_lighting = self._format_inventory_list(item.get("suggested_lighting_entities"))
        mismatches = self._format_inventory_list(item.get("configured_sources_not_in_area"))
        return {
            "area_label": area_label,
            "inventory_entity_total": inventory_entity_total,
            "suggested_occupancy": suggested_occupancy,
            "suggested_learning": suggested_learning,
            "suggested_lighting": suggested_lighting,
            "configured_mismatch": mismatches,
        }

    def _room_signal_placeholders(self, room: dict[str, Any]) -> dict[str, str]:
        rendered = format_room_signals_for_form(room.get("signals"))
        example = rendered.strip() if rendered.strip() else self._default_room_signals_example()
        return {
            "signals_help": (
                "JSON array of room signals. Each item supports entity_id, signal_name, "
                "device_class, buckets and optional burst_threshold/burst_window_s/burst_direction."
            ),
            "signals_example": example,
        }

    def _room_form_placeholders(self, room: dict[str, Any]) -> dict[str, str]:
        return {
            **self._room_inventory_placeholders(room),
            **self._room_signal_placeholders(room),
        }

    @staticmethod
    def _default_room_signals_example() -> str:
        return (
            "[\n"
            "  {\n"
            '    "entity_id": "sensor.studio_temperature",\n'
            '    "signal_name": "room_temperature",\n'
            '    "device_class": "temperature",\n'
            '    "buckets": [\n'
            '      {"label": "cool", "upper_bound": 20},\n'
            '      {"label": "ok", "upper_bound": 24},\n'
            '      {"label": "warm", "upper_bound": 27},\n'
            '      {"label": "hot", "upper_bound": null}\n'
            "    ],\n"
            '    "burst_threshold": 1.5,\n'
            '    "burst_window_s": 600,\n'
            '    "burst_direction": "up"\n'
            "  }\n"
            "]"
        )

    @staticmethod
    def _format_inventory_list(values: Any) -> str:
        items = [str(item) for item in list(values or []) if str(item)]
        return ", ".join(items) if items else "—"

    async def _async_ensure_room_area(
        self, payload: dict[str, Any], existing_room: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data = dict(payload)
        area_reg = self._area_registry()
        if area_reg is None:
            return data
        area_name = str(data.get("display_name") or data.get("room_id") or "").strip()
        requested_area_id = str(data.get("area_id") or "").strip() or None
        existing_area_id = str((existing_room or {}).get("area_id") or "").strip() or None

        if requested_area_id:
            area = self._get_area(area_reg, requested_area_id)
            if area is not None and area_name and getattr(area, "name", None) != area_name:
                self._update_area(area_reg, requested_area_id, area_name)
            data["area_id"] = requested_area_id
            return data

        if existing_area_id:
            area = self._get_area(area_reg, existing_area_id)
            if area is not None and area_name and getattr(area, "name", None) != area_name:
                self._update_area(area_reg, existing_area_id, area_name)
            data["area_id"] = existing_area_id
            return data

        created = self._create_area(area_reg, area_name or str(data.get("room_id") or "").strip())
        if created is not None:
            data["area_id"] = getattr(created, "id", None)
        return data

    async def _async_delete_room_area(self, room: dict[str, Any]) -> None:
        area_id = str(room.get("area_id") or "").strip()
        if not area_id:
            return
        area_reg = self._area_registry()
        if area_reg is None:
            return
        self._delete_area(area_reg, area_id)

    def _area_registry(self) -> Any | None:
        try:
            return ar.async_get(self.hass)
        except Exception:
            return None

    @staticmethod
    def _get_area(area_reg: Any, area_id: str) -> Any | None:
        getter = getattr(area_reg, "async_get_area", None)
        if callable(getter):
            return getter(area_id)
        lister = getattr(area_reg, "async_list_areas", None)
        if callable(lister):
            for area in lister():
                if getattr(area, "id", None) == area_id:
                    return area
        return None

    @staticmethod
    def _create_area(area_reg: Any, name: str) -> Any | None:
        creator = getattr(area_reg, "async_create", None)
        if callable(creator):
            return creator(name)
        return None

    @staticmethod
    def _update_area(area_reg: Any, area_id: str, name: str) -> Any | None:
        updater = getattr(area_reg, "async_update", None)
        if callable(updater):
            return updater(area_id, name=name)
        return None

    @staticmethod
    def _delete_area(area_reg: Any, area_id: str) -> Any | None:
        deleter = getattr(area_reg, "async_delete", None)
        if callable(deleter):
            return deleter(area_id)
        return None
