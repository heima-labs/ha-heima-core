"""Options flow: People (named + anonymous) steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import OPT_PEOPLE_DEBUG_ALIASES, OPT_PEOPLE_NAMED, OPT_PEOPLE_ANON
from ..runtime.normalization.config import (
    GROUP_PRESENCE_STRATEGY_CONTRACT,
    normalize_signal_set_strategy_fields,
    validate_signal_set_strategy_fields,
)
from ._common import (
    PEOPLE_GROUP_LOGIC,
    PRESENCE_METHODS,
    _entity_selector,
    _format_source_weights,
    _is_valid_slug,
    _multiline_text_selector,
    _object_selector,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _PeopleStepsMixin:
    """Mixin for people (named + anonymous) steps."""

    async def _async_bootstrap_ha_bindings(self) -> None:
        importer = getattr(super(), "_async_bootstrap_ha_bindings", None)
        if callable(importer):
            await importer()
        self._import_people_from_ha_if_empty()

    # ---- Named people menu ----

    async def async_step_people_menu(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        self._import_people_from_ha_if_empty()
        return self.async_show_menu(
            step_id="people_menu",
            menu_options=[
                "people_add",
                "people_edit",
                "people_remove",
                "people_anonymous",
                "people_debug_aliases",
                "people_save",
                "people_next",
            ],
            description_placeholders={"summary": self._people_menu_summary()},
        )

    async def async_step_people_add(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        errors: dict[str, str] = {}
        if user_input is None:
            return self.async_show_form(step_id="people_add", data_schema=self._people_schema())

        user_input = self._normalize_people_payload(user_input)
        errors = self._validate_people_payload(user_input, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="people_add", data_schema=self._people_schema(user_input), errors=errors
            )

        people = self._people_named()
        people.append(user_input)
        people[-1]["source"] = "ha_person_registry"
        people[-1]["ha_source_name"] = str(people[-1].get("display_name") or people[-1].get("slug") or "")
        people[-1]["ha_sync_status"] = "configured"
        people[-1]["heima_reviewed"] = True
        self._store_list(OPT_PEOPLE_NAMED, people)
        return await self.async_step_people_menu()

    async def async_step_people_edit(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        people = self._people_named()
        if not people:
            return await self.async_step_people_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("person"): vol.In(self._people_choice_map(people))})
            return self.async_show_form(step_id="people_edit", data_schema=schema)

        self._editing_person_slug = user_input.get("person")
        return await self.async_step_people_edit_form()

    async def async_step_people_edit_form(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        people = self._people_named()
        if user_input is None:
            existing = self._find_by_key(people, "slug", self._editing_person_slug or "") or {}
            return self.async_show_form(
                step_id="people_edit_form", data_schema=self._people_schema(existing)
            )

        user_input = self._normalize_people_payload(user_input)
        errors = self._validate_people_payload(user_input, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="people_edit_form", data_schema=self._people_schema(user_input), errors=errors
            )

        updated = []
        for person in people:
            if person.get("slug") == self._editing_person_slug:
                user_input["source"] = "ha_person_registry"
                user_input["ha_source_name"] = str(
                    user_input.get("display_name") or user_input.get("slug") or ""
                )
                user_input["ha_sync_status"] = "configured"
                user_input["heima_reviewed"] = True
                updated.append(user_input)
            else:
                updated.append(person)
        self._store_list(OPT_PEOPLE_NAMED, updated)
        self._editing_person_slug = None
        return await self.async_step_people_menu()

    async def async_step_people_remove(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        people = self._people_named()
        if not people:
            return await self.async_step_people_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("person"): vol.In(self._people_choice_map(people))})
            return self.async_show_form(step_id="people_remove", data_schema=schema)

        self._removing_person_slug = user_input.get("person")
        return await self.async_step_people_remove_confirm()

    async def async_step_people_remove_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        slug = getattr(self, "_removing_person_slug", None)
        if not slug:
            return await self.async_step_people_menu()

        people = self._people_named()
        existing = self._find_by_key(people, "slug", slug) or {}
        person_label = existing.get("display_name") or slug

        if user_input is None:
            schema = vol.Schema({vol.Required("confirm", default=False): bool})
            return self.async_show_form(
                step_id="people_remove_confirm",
                data_schema=schema,
                description_placeholders={"person_label": person_label},
            )

        if not bool(user_input.get("confirm")):
            self._removing_person_slug = None
            return await self.async_step_people_menu()

        updated = [p for p in people if p.get("slug") != slug]
        self._store_list(OPT_PEOPLE_NAMED, updated)
        self._removing_person_slug = None
        return await self.async_step_people_menu()

    async def async_step_people_anonymous(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        current = dict(self.options.get(OPT_PEOPLE_ANON, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="people_anonymous", data_schema=self._people_anonymous_schema(current)
            )

        self._update_options({OPT_PEOPLE_ANON: self._normalize_people_anonymous_payload(user_input)})
        return await self.async_step_people_menu()

    async def async_step_people_debug_aliases(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        current = dict(self.options.get(OPT_PEOPLE_DEBUG_ALIASES, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="people_debug_aliases",
                data_schema=self._people_debug_aliases_schema(current),
                description_placeholders={"debug_aliases_help": self._people_debug_aliases_help()},
            )

        payload = self._normalize_people_debug_aliases_payload(user_input)
        self._update_options({OPT_PEOPLE_DEBUG_ALIASES: payload})
        return await self.async_step_people_menu()

    async def async_step_people_next(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return await self.async_step_init()

    async def async_step_people_save(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        """Persist options and close the flow from People menu."""
        return self.async_create_entry(title="", data=self._finalize_options())

    # ---- Schemas ----

    def _people_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = dict(defaults or {})
        defaults["source_weights"] = _format_source_weights(defaults.get("source_weights"))
        schema = vol.Schema(
            {
                vol.Required("slug", default=defaults.get("slug", "")): cv.string,
                vol.Optional("display_name", default=defaults.get("display_name", "")): cv.string,
                vol.Required(
                    "presence_method", default=defaults.get("presence_method", "ha_person")
                ): vol.In(PRESENCE_METHODS),
                vol.Optional("person_entity"): _entity_selector(["person"]),
                vol.Optional("sources"): _entity_selector(
                    ["binary_sensor", "sensor", "device_tracker"], multiple=True
                ),
                vol.Optional(
                    "group_strategy", default=defaults.get("group_strategy", "quorum")
                ): vol.In(PEOPLE_GROUP_LOGIC),
                vol.Optional("required", default=defaults.get("required", 1)): cv.positive_int,
                vol.Optional("weight_threshold"): vol.Coerce(float),
                vol.Optional("source_weights"): _multiline_text_selector(),
                vol.Optional("arrive_hold_s", default=defaults.get("arrive_hold_s", 10)): cv.positive_int,
                vol.Optional("leave_hold_s", default=defaults.get("leave_hold_s", 120)): cv.positive_int,
                vol.Optional(
                    "enable_override", default=defaults.get("enable_override", False)
                ): bool,
            }
        )
        return self._with_suggested(schema, defaults)

    def _people_anonymous_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = dict(defaults or {})
        defaults["source_weights"] = _format_source_weights(defaults.get("source_weights"))
        schema = vol.Schema(
            {
                vol.Optional("enabled", default=defaults.get("enabled", False)): bool,
                vol.Optional("sources"): _entity_selector(
                    ["binary_sensor", "sensor", "device_tracker"], multiple=True
                ),
                vol.Optional(
                    "group_strategy", default=defaults.get("group_strategy", "quorum")
                ): vol.In(PEOPLE_GROUP_LOGIC),
                vol.Optional("required", default=defaults.get("required", 1)): cv.positive_int,
                vol.Optional("weight_threshold"): vol.Coerce(float),
                vol.Optional("source_weights"): _multiline_text_selector(),
                vol.Optional(
                    "anonymous_count_weight", default=defaults.get("anonymous_count_weight", 1)
                ): cv.positive_int,
                vol.Optional("arrive_hold_s", default=defaults.get("arrive_hold_s", 10)): cv.positive_int,
                vol.Optional("leave_hold_s", default=defaults.get("leave_hold_s", 120)): cv.positive_int,
            }
        )
        return self._with_suggested(schema, defaults)

    def _people_debug_aliases_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = dict(defaults or {})
        schema = vol.Schema(
            {
                vol.Optional("enabled", default=defaults.get("enabled", False)): bool,
                vol.Optional("aliases", default=defaults.get("aliases", {})): _object_selector(),
            }
        )
        return self._with_suggested(schema, defaults)

    # ---- Validators ----

    def _validate_people_payload(self, payload: dict[str, Any], is_edit: bool) -> dict[str, str]:
        errors: dict[str, str] = {}
        slug = payload.get("slug", "")
        if is_edit:
            errors.update(self._error_if_immutable_changed(payload, "slug", self._editing_person_slug))
        if not slug:
            errors["slug"] = "required"
        elif not _is_valid_slug(slug):
            errors["slug"] = "invalid_slug"
        if slug.startswith("heima_"):
            errors["slug"] = "reserved_prefix"

        existing_slugs = {p["slug"] for p in self._people_named()}
        if not is_edit:
            if slug in existing_slugs:
                errors["slug"] = "duplicate"
        elif slug in (existing_slugs - {self._editing_person_slug}):
            errors["slug"] = "duplicate"

        method = payload.get("presence_method")
        person_entity = str(payload.get("person_entity") or "").strip()
        if not person_entity:
            errors["person_entity"] = "required"
        elif person_entity not in self._ha_person_entity_ids():
            errors["person_entity"] = "unknown_person"

        existing_person_entities = {
            str(p.get("person_entity") or "").strip()
            for p in self._people_named()
            if str(p.get("person_entity") or "").strip()
        }
        if is_edit:
            existing_person = self._find_by_key(self._people_named(), "slug", self._editing_person_slug or "")
            existing_entity = str((existing_person or {}).get("person_entity") or "").strip()
            existing_person_entities.discard(existing_entity)
        if person_entity and person_entity in existing_person_entities:
            errors["person_entity"] = "duplicate_person_entity"

        if method == "quorum":
            sources = payload.get("sources", [])
            required = int(payload.get("required", 1))
            if not sources:
                errors["sources"] = "required"
            elif payload.get("group_strategy", "quorum") == "quorum" and required > len(sources):
                errors["required"] = "invalid_required"
            if payload.get("group_strategy") == "weighted_quorum":
                errors.update(
                    validate_signal_set_strategy_fields(
                        payload=payload,
                        strategy_key="group_strategy",
                        sources=sources,
                        contract=GROUP_PRESENCE_STRATEGY_CONTRACT,
                    )
                )
        return errors

    # ---- Normalization (called by base _finalize_options too) ----

    def _normalize_people_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["slug"] = str(data.get("slug", "")).strip()
        data["display_name"] = str(data.get("display_name", "") or "").strip()
        data["presence_method"] = str(data.get("presence_method", "ha_person"))
        if data.get("person_entity"):
            data["person_entity"] = str(data["person_entity"])
        for key in ("source", "ha_source_name", "ha_sync_status", "heima_reviewed"):
            if key in payload:
                data[key] = payload[key]
        data["sources"] = self._normalize_multi_value(data.get("sources"))
        normalize_signal_set_strategy_fields(
            data,
            strategy_key="group_strategy",
            contract=GROUP_PRESENCE_STRATEGY_CONTRACT,
        )
        return data

    def _ha_person_states(self) -> list[Any]:
        states = getattr(getattr(self, "hass", None), "states", None)
        async_all = getattr(states, "async_all", None)
        if not callable(async_all):
            return []
        try:
            all_states = list(async_all())
        except TypeError:
            all_states = list(async_all("person"))
        return [state for state in all_states if str(getattr(state, "entity_id", "")).startswith("person.")]

    def _ha_person_entity_ids(self) -> set[str]:
        return {str(getattr(state, "entity_id", "")).strip() for state in self._ha_person_states()}

    def _import_people_from_ha_if_empty(self) -> None:
        if self._people_named():
            return
        imported: list[dict[str, Any]] = []
        for state in self._ha_person_states():
            entity_id = str(getattr(state, "entity_id", "")).strip()
            if not entity_id:
                continue
            slug = entity_id.split(".", 1)[1]
            display_name = str(getattr(state, "name", None) or getattr(state, "attributes", {}).get("friendly_name") or slug)
            imported.append(
                {
                    "slug": slug,
                    "display_name": display_name,
                    "presence_method": "ha_person",
                    "person_entity": entity_id,
                    "arrive_hold_s": 10,
                    "leave_hold_s": 120,
                    "enable_override": False,
                }
            )
        if imported:
            self._store_list(OPT_PEOPLE_NAMED, imported)

    def _normalize_people_anonymous_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["sources"] = self._normalize_multi_value(data.get("sources"))
        normalize_signal_set_strategy_fields(
            data,
            strategy_key="group_strategy",
            contract=GROUP_PRESENCE_STRATEGY_CONTRACT,
        )
        return data

    def _normalize_people_debug_aliases_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        aliases = data.get("aliases")
        normalized_aliases: dict[str, dict[str, Any]] = {}
        if isinstance(aliases, dict):
            for alias_slug, raw in aliases.items():
                if not str(alias_slug).strip() or not isinstance(raw, dict):
                    continue
                item = dict(raw)
                item["mode"] = str(item.get("mode") or "alias_person").strip() or "alias_person"
                if item.get("person_entity"):
                    item["person_entity"] = str(item["person_entity"]).strip()
                if item.get("display_name"):
                    item["display_name"] = str(item["display_name"]).strip()
                if item.get("synthetic_state"):
                    item["synthetic_state"] = str(item["synthetic_state"]).strip()
                normalized_aliases[str(alias_slug).strip()] = item
        return {"enabled": bool(data.get("enabled", False)), "aliases": normalized_aliases}

    def _people_choice_map(self, people: list[dict[str, Any]]) -> dict[str, str]:
        return {
            self._people_choice_label(person): str(person.get("slug") or "")
            for person in people
            if str(person.get("slug") or "").strip()
        }

    def _people_choice_label(self, person: dict[str, Any]) -> str:
        label = str(person.get("display_name") or person.get("slug") or "").strip()
        status = str(person.get("ha_sync_status") or "").strip()
        if status == "new":
            return f"{label} [new]"
        if status == "configured":
            return f"{label} [configured]"
        if status == "orphaned":
            return f"{label} [orphaned]"
        return label

    def _people_debug_aliases_help(self) -> str:
        language = str(getattr(self, "_flow_language", lambda: "en")() or "en").lower()
        if language.startswith("it"):
            return (
                "Usa questa sezione solo per test/debug. "
                "Shape alias_slug -> {mode, person_entity?, display_name?, synthetic_state?}. "
                "mode: alias_person | synthetic. "
                "Esempio: "
                '{"demo_alex":{"mode":"alias_person","person_entity":"person.stefano","display_name":"Demo Alex"},'
                '"guest_test":{"mode":"synthetic","display_name":"Guest Test","synthetic_state":"home"}}'
            )
        return (
            "Use this section only for test/debug. "
            "Shape alias_slug -> {mode, person_entity?, display_name?, synthetic_state?}. "
            "mode: alias_person | synthetic. "
            "Example: "
            '{"demo_alex":{"mode":"alias_person","person_entity":"person.stefano","display_name":"Demo Alex"},'
            '"guest_test":{"mode":"synthetic","display_name":"Guest Test","synthetic_state":"home"}}'
        )
