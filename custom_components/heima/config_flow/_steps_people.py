"""Options flow: People (named + anonymous) steps."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from ..const import OPT_PEOPLE_NAMED, OPT_PEOPLE_ANON
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
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _PeopleStepsMixin:
    """Mixin for people (named + anonymous) steps."""

    # ---- Named people menu ----

    async def async_step_people_menu(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        return self.async_show_menu(
            step_id="people_menu",
            menu_options=[
                "people_add",
                "people_edit",
                "people_remove",
                "people_anonymous",
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
        self._store_list(OPT_PEOPLE_NAMED, people)
        return await self.async_step_people_menu()

    async def async_step_people_edit(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        people = self._people_named()
        if not people:
            return await self.async_step_people_menu()

        if user_input is None:
            schema = vol.Schema({vol.Required("person"): vol.In([p["slug"] for p in people])})
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
            schema = vol.Schema({vol.Required("person"): vol.In([p["slug"] for p in people])})
            return self.async_show_form(step_id="people_remove", data_schema=schema)

        slug = user_input.get("person")
        updated = [p for p in people if p.get("slug") != slug]
        self._store_list(OPT_PEOPLE_NAMED, updated)
        return await self.async_step_people_menu()

    async def async_step_people_anonymous(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        current = dict(self.options.get(OPT_PEOPLE_ANON, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="people_anonymous", data_schema=self._people_anonymous_schema(current)
            )

        self._update_options({OPT_PEOPLE_ANON: self._normalize_people_anonymous_payload(user_input)})
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
        if method == "ha_person" and not payload.get("person_entity"):
            errors["person_entity"] = "required"
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
        data["sources"] = self._normalize_multi_value(data.get("sources"))
        normalize_signal_set_strategy_fields(
            data,
            strategy_key="group_strategy",
            contract=GROUP_PRESENCE_STRATEGY_CONTRACT,
        )
        return data

    def _normalize_people_anonymous_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        data = dict(payload)
        data["sources"] = self._normalize_multi_value(data.get("sources"))
        normalize_signal_set_strategy_fields(
            data,
            strategy_key="group_strategy",
            contract=GROUP_PRESENCE_STRATEGY_CONTRACT,
        )
        return data
