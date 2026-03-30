"""Config flow for Heima."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from ..const import (
    CONF_ENGINE_ENABLED,
    CONF_LANGUAGE,
    CONF_TIMEZONE,
    DEFAULT_ENGINE_ENABLED,
    DEFAULT_LIGHTING_APPLY_MODE,
    OPT_CALENDAR,
    OPT_HEATING,
    OPT_LIGHTING_APPLY_MODE,
    OPT_LIGHTING_ROOMS,
    OPT_LIGHTING_ZONES,
    OPT_NOTIFICATIONS,
    OPT_PEOPLE_ANON,
    OPT_PEOPLE_NAMED,
    OPT_REACTIONS,
    OPT_ROOMS,
    OPT_SECURITY,
)
from ._common import _default_language, _default_timezone
from ._steps_calendar import _CalendarStepsMixin
from ._steps_general import _GeneralStepsMixin
from ._steps_heating import _HeatingStepsMixin
from ._steps_learning import _LearningStepsMixin
from ._steps_lighting import _LightingStepsMixin
from ._steps_notifications import _NotificationsStepsMixin
from ._steps_people import _PeopleStepsMixin
from ._steps_reactions import _ReactionsStepsMixin
from ._steps_rooms import _RoomsStepsMixin
from ._steps_security import _SecurityStepsMixin

_LOGGER = logging.getLogger(__name__)


class HeimaConfigFlow(config_entries.ConfigFlow, domain="heima"):
    """Handle a config flow for Heima."""

    VERSION = 1
    MINOR_VERSION = 1

    async def _async_ensure_admin_access(self) -> FlowResult | None:
        """Abort when the current flow user is not a Home Assistant admin."""
        cached = getattr(self, "_admin_access_granted", None)
        if cached is True:
            return None
        if cached is False:
            return self.async_abort(reason="admin_required")
        user_id = str(self.context.get("user_id") or "").strip()
        if not user_id:
            self._admin_access_granted = False
            return self.async_abort(reason="admin_required")
        user = await self.hass.auth.async_get_user(user_id)
        if user is None or not getattr(user, "is_admin", False):
            self._admin_access_granted = False
            return self.async_abort(reason="admin_required")
        self._admin_access_granted = True
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if (abort_result := await self._async_ensure_admin_access()) is not None:
            return abort_result
        if user_input is None:
            schema = vol.Schema(
                {
                    vol.Optional(CONF_ENGINE_ENABLED, default=DEFAULT_ENGINE_ENABLED): bool,
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        options = {
            CONF_ENGINE_ENABLED: user_input.get(CONF_ENGINE_ENABLED, DEFAULT_ENGINE_ENABLED),
            CONF_TIMEZONE: _default_timezone(self.hass),
            CONF_LANGUAGE: _default_language(self.hass),
            OPT_LIGHTING_APPLY_MODE: DEFAULT_LIGHTING_APPLY_MODE,
        }
        return self.async_create_entry(title="Heima", data={}, options=options)

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "HeimaOptionsFlowHandler":
        return HeimaOptionsFlowHandler(config_entry)


class HeimaOptionsFlowHandler(
    _GeneralStepsMixin,
    _PeopleStepsMixin,
    _RoomsStepsMixin,
    _LightingStepsMixin,
    _HeatingStepsMixin,
    _SecurityStepsMixin,
    _NotificationsStepsMixin,
    _ReactionsStepsMixin,
    _CalendarStepsMixin,
    _LearningStepsMixin,
    config_entries.OptionsFlow,
):
    """Handle Heima options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry
        self.options = dict(config_entry.options)
        self._editing_person_slug: str | None = None
        self._editing_room_id: str | None = None
        self._editing_zone_id: str | None = None
        self._editing_lighting_room_id: str | None = None
        self._editing_heating_house_state: str | None = None
        self._editing_heating_branch: str | None = None

    # ---- Toplevel menu (CF2) ----

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "people_menu",
                "rooms_menu",
                "lighting_rooms_menu",
                "heating",
                "security",
                "notifications",
                "calendar",
                "learning",
                "reactions",
                "reactions_edit",
                "proposals",
                "save",
            ],
            description_placeholders=self._init_status_block(),
        )

    async def async_step_save(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Persist options and close the flow from the toplevel menu."""
        return self.async_create_entry(title="", data=self._finalize_options())

    def _update_options(self, updates: dict[str, Any]) -> None:
        """Persist options keys immediately to disk.

        Triggers selective reload via _async_entry_updated:
        - structural keys (people, rooms, zones) → full HA reload
        - runtime keys → coordinator.async_reload_options() only
        """
        self.options.update(updates)
        config_entries = getattr(getattr(self, "hass", None), "config_entries", None)
        config_entry = getattr(self, "_config_entry", None)
        if config_entries is not None and config_entry is not None:
            config_entries.async_update_entry(config_entry, options=dict(self.options))

    # ---- Shared state helpers ----

    def _people_named(self) -> list[dict[str, Any]]:
        return list(self.options.get(OPT_PEOPLE_NAMED, []))

    def _rooms(self) -> list[dict[str, Any]]:
        return list(self.options.get(OPT_ROOMS, []))

    def _lighting_rooms(self) -> list[dict[str, Any]]:
        return list(self.options.get(OPT_LIGHTING_ROOMS, []))

    def _lighting_zones(self) -> list[dict[str, Any]]:
        return list(self.options.get(OPT_LIGHTING_ZONES, []))

    def _heating_config(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_HEATING, {}))

    def _heating_override_branches(self) -> dict[str, dict[str, Any]]:
        branches = self._heating_config().get("override_branches", {})
        return dict(branches) if isinstance(branches, dict) else {}

    # ---- Summary helpers (for description_placeholders) ----

    def _init_status_block(self) -> dict[str, str]:
        """Return description_placeholders for the init menu.

        All labels live in translations. This method provides only values.
        Boolean states (engine on/off) are localised via CONF_LANGUAGE.
        """
        lang = self.options.get(CONF_LANGUAGE, "it")
        is_it = lang.startswith("it")
        engine_on = self.options.get(CONF_ENGINE_ENABLED, True)
        return {
            "engine_status": ("attivo" if engine_on else "disabilitato") if is_it else ("enabled" if engine_on else "disabled"),
            "people_summary": self._people_menu_summary(),
            "rooms_summary": self._rooms_menu_summary(),
            "lighting_summary": self._lighting_menu_summary(),
            "heating_summary": self._heating_menu_summary(),
            "security_summary": self._security_menu_summary(),
            "calendar_summary": self._calendar_menu_summary(),
            "pending_proposals_summary": self._pending_proposals_summary(),
        }

    def _people_menu_summary(self) -> str:
        people = self._people_named()
        if not people:
            return "—"
        names = [p.get("display_name") or p.get("slug", "") for p in people]
        return f"{len(people)}: {', '.join(names)}"

    def _rooms_menu_summary(self) -> str:
        rooms = self._rooms()
        if not rooms:
            return "—"
        names = [r.get("display_name") or r.get("room_id", "") for r in rooms]
        return f"{len(rooms)}: {', '.join(names)}"

    def _lighting_menu_summary(self) -> str:
        return f"{len(self._lighting_rooms())}/{len(self._rooms())}"

    def _heating_menu_summary(self) -> str:
        cfg = self._heating_config()
        thermostat = cfg.get("climate_entity") or "—"
        branches = self._heating_override_branches()
        configured = len([v for v in branches.values() if v.get("branch")])
        return f"{thermostat} | {configured}"

    def _pending_proposals_summary(self) -> str:
        coordinator = None
        try:
            domain_data = getattr(getattr(self, "hass", None), "data", {}).get(DOMAIN, {})
            if isinstance(domain_data, dict):
                entry_data = domain_data.get(getattr(self._config_entry, "entry_id", None), {})
                if isinstance(entry_data, dict):
                    coordinator = entry_data.get("coordinator")
        except Exception:
            coordinator = None
        proposal_engine = getattr(coordinator, "proposal_engine", None)
        pending_fn = getattr(proposal_engine, "pending_proposals", None)
        pending = pending_fn() if callable(pending_fn) else []
        if not pending:
            return "—"
        return str(len(pending))

    def _room_ids(self) -> list[str]:
        return [room["room_id"] for room in self._rooms()]

    def _zone_ids(self) -> list[str]:
        return [zone["zone_id"] for zone in self._lighting_zones()]

    def _find_by_key(
        self, items: list[dict[str, Any]], key: str, value: str
    ) -> dict[str, Any] | None:
        for item in items:
            if item.get(key) == value:
                return item
        return None

    def _store_list(self, key: str, items: list[dict[str, Any]]) -> None:
        self._update_options({key: items})

    def _with_suggested(
        self, schema: vol.Schema, defaults: dict[str, Any] | None
    ) -> vol.Schema:
        """Populate form values without turning optional cleared fields into sticky defaults."""
        return self.add_suggested_values_to_schema(schema, defaults or {})

    def _normalize_multi_value(self, value: Any) -> list[str]:
        """Normalize selector/cv.multi_select outputs to a stable list[str]."""
        if value is None:
            return []
        if isinstance(value, dict):
            return [str(k) for k, enabled in value.items() if enabled]
        if isinstance(value, (list, tuple, set)):
            return [str(v) for v in value if str(v)]
        if isinstance(value, str):
            return [value] if value else []
        return [str(value)]

    def _error_if_immutable_changed(
        self, payload: dict[str, Any], field: str, expected_value: str | None
    ) -> dict[str, str]:
        if expected_value is None:
            return {}
        if str(payload.get(field, "")) != expected_value:
            return {field: "immutable"}
        return {}

    # ---- Finalize ----

    def _finalize_options(self) -> dict[str, Any]:
        """Return a coherent options snapshot before persisting."""
        options = dict(self.options)

        room_ids = {str(r.get("room_id")) for r in options.get(OPT_ROOMS, []) if r.get("room_id")}
        lighting_rooms = []
        for room_cfg in options.get(OPT_LIGHTING_ROOMS, []):
            room_id = str(room_cfg.get("room_id", "")).strip()
            if not room_id or room_id not in room_ids:
                continue
            lighting_rooms.append(self._normalize_lighting_room_payload(room_cfg))
        options[OPT_LIGHTING_ROOMS] = lighting_rooms

        lighting_zones = []
        for zone_cfg in options.get(OPT_LIGHTING_ZONES, []):
            zone = self._normalize_lighting_zone_payload(zone_cfg)
            zone["rooms"] = [r for r in zone.get("rooms", []) if r in room_ids]
            if not zone.get("rooms"):
                continue
            lighting_zones.append(zone)
        options[OPT_LIGHTING_ZONES] = lighting_zones

        if OPT_PEOPLE_NAMED in options:
            options[OPT_PEOPLE_NAMED] = [
                self._normalize_people_payload(p) for p in options.get(OPT_PEOPLE_NAMED, [])
            ]
        if OPT_ROOMS in options:
            normalized_rooms: list[dict[str, Any]] = []
            for room in options.get(OPT_ROOMS, []):
                room_norm = self._normalize_room_payload(room)
                if "occupancy_mode" not in room and not room_norm.get("sources"):
                    room_norm["occupancy_mode"] = "none"
                normalized_rooms.append(room_norm)
            options[OPT_ROOMS] = normalized_rooms
        if OPT_NOTIFICATIONS in options:
            options[OPT_NOTIFICATIONS] = self._normalize_notifications_payload(
                options.get(OPT_NOTIFICATIONS, {})
            )
        if OPT_PEOPLE_ANON in options:
            options[OPT_PEOPLE_ANON] = self._normalize_people_anonymous_payload(
                options.get(OPT_PEOPLE_ANON, {})
            )
        if OPT_HEATING in options:
            options[OPT_HEATING] = self._normalize_heating_payload(options.get(OPT_HEATING, {}))

        if OPT_REACTIONS in options:
            muted = self._normalize_multi_value(
                options.get(OPT_REACTIONS, {}).get("muted", [])
            )
            options[OPT_REACTIONS] = {"muted": muted}

        self.options = options
        return options
