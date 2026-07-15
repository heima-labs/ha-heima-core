"""Options flow: Notifications step."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol

from ..const import (
    DEFAULT_ENABLED_EVENT_CATEGORIES,
    DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
    DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S,
    DEFAULT_OCCUPANCY_MISMATCH_POLICY,
    DEFAULT_SECURITY_MISMATCH_EVENT_MODE,
    DEFAULT_SECURITY_MISMATCH_PERSIST_S,
    DEFAULT_SECURITY_MISMATCH_POLICY,
    EVENT_CATEGORIES_TOGGLEABLE,
    OCCUPANCY_MISMATCH_POLICIES,
    OPT_NOTIFICATIONS,
    SECURITY_MISMATCH_EVENT_MODES,
    SECURITY_MISMATCH_POLICIES,
)
from ._common import (
    _NON_NEGATIVE_INT,
    _is_valid_slug,
    _object_selector,
    _parse_multiline_items,
    _parse_multiline_mapping,
)

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

try:
    from homeassistant.helpers import config_validation as cv
except ImportError:
    pass


class _NotificationsStepsMixin:
    """Mixin for notifications step."""

    async def async_step_notification_recipients(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        notifications = self._notifications_config()
        recipients = self._notification_recipients()
        menu_options = ["notification_recipient_add"]
        if recipients:
            menu_options.extend(
                [
                    "notification_recipient_edit",
                    "notification_recipient_delete",
                ]
            )
        menu_options.append("notification_recipients_done")
        return self.async_show_menu(
            step_id="notification_recipients",
            menu_options=menu_options,
            description_placeholders={
                "summary": self._notification_recipients_summary(notifications),
            },
        )

    async def async_step_notification_recipient_add(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        if user_input is None:
            return self.async_show_form(
                step_id="notification_recipient_add",
                data_schema=self._notification_recipient_schema(),
            )

        payload = self._normalize_notification_recipient_payload(user_input)
        errors = self._validate_notification_recipient_payload(payload, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="notification_recipient_add",
                data_schema=self._notification_recipient_schema(payload),
                errors=errors,
            )

        notifications = self._notifications_config()
        recipients = dict(notifications.get("recipients", {}))
        recipients[payload["recipient_id"]] = payload["notify_services"]
        notifications["recipients"] = recipients
        self._update_options({OPT_NOTIFICATIONS: notifications})
        return await self.async_step_notification_recipients()

    async def async_step_notification_recipient_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        recipients = self._notification_recipients()
        if not recipients:
            return await self.async_step_notification_recipients()

        if user_input is None:
            return self.async_show_form(
                step_id="notification_recipient_edit",
                data_schema=vol.Schema(
                    {
                        vol.Required("recipient_id"): vol.In(
                            self._notification_recipient_choice_map(recipients)
                        )
                    }
                ),
            )

        self._editing_notification_recipient_id = self._resolve_choice_value(
            self._notification_recipient_choice_map(recipients),
            user_input.get("recipient_id"),
        )
        return await self.async_step_notification_recipient_edit_form()

    async def async_step_notification_recipient_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        recipient_id = str(getattr(self, "_editing_notification_recipient_id", "") or "").strip()
        recipients = self._notification_recipients()
        if not recipient_id or recipient_id not in recipients:
            self._editing_notification_recipient_id = None
            return await self.async_step_notification_recipients()

        if user_input is None:
            return self.async_show_form(
                step_id="notification_recipient_edit_form",
                data_schema=self._notification_recipient_schema(
                    {
                        "recipient_id": recipient_id,
                        "notify_services": "\n".join(recipients.get(recipient_id, [])),
                    },
                    is_edit=True,
                ),
            )

        payload = self._normalize_notification_recipient_payload(user_input)
        errors = self._validate_notification_recipient_payload(payload, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="notification_recipient_edit_form",
                data_schema=self._notification_recipient_schema(payload, is_edit=True),
                errors=errors,
            )

        notifications = self._notifications_config()
        updated = dict(notifications.get("recipients", {}))
        updated[recipient_id] = payload["notify_services"]
        notifications["recipients"] = updated
        self._update_options({OPT_NOTIFICATIONS: notifications})
        self._editing_notification_recipient_id = None
        return await self.async_step_notification_recipients()

    async def async_step_notification_recipient_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        recipients = self._notification_recipients()
        if not recipients:
            return await self.async_step_notification_recipients()

        if user_input is None:
            return self.async_show_form(
                step_id="notification_recipient_delete",
                data_schema=vol.Schema(
                    {
                        vol.Required("recipient_id"): vol.In(
                            self._notification_recipient_choice_map(recipients)
                        )
                    }
                ),
            )

        self._editing_notification_recipient_id = self._resolve_choice_value(
            self._notification_recipient_choice_map(recipients),
            user_input.get("recipient_id"),
        )
        return await self.async_step_notification_recipient_delete_confirm()

    async def async_step_notification_recipient_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        recipient_id = str(getattr(self, "_editing_notification_recipient_id", "") or "").strip()
        recipients = self._notification_recipients()
        if not recipient_id or recipient_id not in recipients:
            self._editing_notification_recipient_id = None
            return await self.async_step_notification_recipients()

        references = self._notification_recipient_references(recipient_id)
        if references:
            return self.async_show_form(
                step_id="notification_recipient_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                errors={"base": "recipient_in_use"},
                description_placeholders={
                    "recipient_id": recipient_id,
                    "references": ", ".join(references),
                },
            )

        if user_input is None:
            return self.async_show_form(
                step_id="notification_recipient_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                description_placeholders={"recipient_id": recipient_id, "references": ""},
            )

        if not bool(user_input.get("confirm", False)):
            return self.async_show_form(
                step_id="notification_recipient_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                description_placeholders={"recipient_id": recipient_id, "references": ""},
            )

        notifications = self._notifications_config()
        updated = dict(notifications.get("recipients", {}))
        updated.pop(recipient_id, None)
        notifications["recipients"] = updated
        self._update_options({OPT_NOTIFICATIONS: notifications})
        self._editing_notification_recipient_id = None
        return await self.async_step_notification_recipients()

    async def async_step_notification_recipients_done(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        return await self.async_step_init()

    async def async_step_notification_groups(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        groups = self._notification_groups()
        menu_options = ["notification_group_add"]
        if groups:
            menu_options.extend(["notification_group_edit", "notification_group_delete"])
        menu_options.append("notification_groups_done")
        return self.async_show_menu(
            step_id="notification_groups",
            menu_options=menu_options,
            description_placeholders={
                "summary": self._notification_groups_summary(self._notifications_config()),
            },
        )

    async def async_step_notification_group_add(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        if user_input is None:
            return self.async_show_form(
                step_id="notification_group_add",
                data_schema=self._notification_group_schema(),
            )

        payload = self._normalize_notification_group_payload(user_input)
        errors = self._validate_notification_group_payload(payload, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="notification_group_add",
                data_schema=self._notification_group_schema(payload),
                errors=errors,
            )

        notifications = self._notifications_config()
        groups = dict(notifications.get("recipient_groups", {}))
        groups[payload["group_id"]] = payload["members"]
        notifications["recipient_groups"] = groups
        self._update_options({OPT_NOTIFICATIONS: notifications})
        return await self.async_step_notification_groups()

    async def async_step_notification_group_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        groups = self._notification_groups()
        if not groups:
            return await self.async_step_notification_groups()

        if user_input is None:
            return self.async_show_form(
                step_id="notification_group_edit",
                data_schema=vol.Schema(
                    {
                        vol.Required("group_id"): vol.In(
                            self._notification_group_choice_map(groups)
                        )
                    }
                ),
            )

        self._editing_notification_group_id = self._resolve_choice_value(
            self._notification_group_choice_map(groups),
            user_input.get("group_id"),
        )
        return await self.async_step_notification_group_edit_form()

    async def async_step_notification_group_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        group_id = str(getattr(self, "_editing_notification_group_id", "") or "").strip()
        groups = self._notification_groups()
        if not group_id or group_id not in groups:
            self._editing_notification_group_id = None
            return await self.async_step_notification_groups()

        if user_input is None:
            return self.async_show_form(
                step_id="notification_group_edit_form",
                data_schema=self._notification_group_schema(
                    {
                        "group_id": group_id,
                        "members": "\n".join(groups.get(group_id, [])),
                    },
                    is_edit=True,
                ),
            )

        payload = self._normalize_notification_group_payload(user_input)
        errors = self._validate_notification_group_payload(payload, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="notification_group_edit_form",
                data_schema=self._notification_group_schema(payload, is_edit=True),
                errors=errors,
            )

        notifications = self._notifications_config()
        updated = dict(notifications.get("recipient_groups", {}))
        updated[group_id] = payload["members"]
        notifications["recipient_groups"] = updated
        self._update_options({OPT_NOTIFICATIONS: notifications})
        self._editing_notification_group_id = None
        return await self.async_step_notification_groups()

    async def async_step_notification_group_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        groups = self._notification_groups()
        if not groups:
            return await self.async_step_notification_groups()

        if user_input is None:
            return self.async_show_form(
                step_id="notification_group_delete",
                data_schema=vol.Schema(
                    {
                        vol.Required("group_id"): vol.In(
                            self._notification_group_choice_map(groups)
                        )
                    }
                ),
            )

        self._editing_notification_group_id = self._resolve_choice_value(
            self._notification_group_choice_map(groups),
            user_input.get("group_id"),
        )
        return await self.async_step_notification_group_delete_confirm()

    async def async_step_notification_group_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        group_id = str(getattr(self, "_editing_notification_group_id", "") or "").strip()
        groups = self._notification_groups()
        if not group_id or group_id not in groups:
            self._editing_notification_group_id = None
            return await self.async_step_notification_groups()

        references = self._notification_group_references(group_id)
        if references:
            return self.async_show_form(
                step_id="notification_group_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                errors={"base": "group_in_use"},
                description_placeholders={
                    "group_id": group_id,
                    "references": ", ".join(references),
                },
            )

        if user_input is None:
            return self.async_show_form(
                step_id="notification_group_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                description_placeholders={"group_id": group_id, "references": ""},
            )

        if not bool(user_input.get("confirm", False)):
            return self.async_show_form(
                step_id="notification_group_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                description_placeholders={"group_id": group_id, "references": ""},
            )

        notifications = self._notifications_config()
        updated = dict(notifications.get("recipient_groups", {}))
        updated.pop(group_id, None)
        notifications["recipient_groups"] = updated
        self._update_options({OPT_NOTIFICATIONS: notifications})
        self._editing_notification_group_id = None
        return await self.async_step_notification_groups()

    async def async_step_notification_groups_done(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        return await self.async_step_init()

    async def async_step_notification_routes(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        notifications = self._notifications_config()
        choices = self._notification_route_target_choice_map()
        if user_input is None:
            return self.async_show_form(
                step_id="notification_routes",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            "route_targets",
                            default=list(notifications.get("route_targets", [])),
                        ): cv.multi_select(choices)
                    }
                ),
            )

        targets = _parse_multiline_items(user_input.get("route_targets"))
        errors = self._validate_notification_route_targets(targets)
        if errors:
            return self.async_show_form(
                step_id="notification_routes",
                data_schema=vol.Schema(
                    {
                        vol.Optional(
                            "route_targets",
                            default=targets,
                        ): cv.multi_select(choices)
                    }
                ),
                errors=errors,
            )

        notifications["route_targets"] = targets
        self._update_options({OPT_NOTIFICATIONS: notifications})
        return await self.async_step_init()

    async def async_step_notification_services(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        capabilities = self._notification_service_capabilities()
        menu_options = ["notification_service_add"]
        if capabilities:
            menu_options.extend(["notification_service_edit", "notification_service_delete"])
        menu_options.append("notification_services_done")
        return self.async_show_menu(
            step_id="notification_services",
            menu_options=menu_options,
            description_placeholders={
                "summary": self._notification_services_summary(capabilities),
            },
        )

    async def async_step_notification_service_add(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        if user_input is None:
            return self.async_show_form(
                step_id="notification_service_add",
                data_schema=self._notification_service_schema(),
            )

        payload = self._normalize_notification_service_payload(user_input)
        errors = self._validate_notification_service_payload(payload, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="notification_service_add",
                data_schema=self._notification_service_schema(payload),
                errors=errors,
            )

        notifications = self._notifications_config()
        capabilities = self._notification_service_capabilities()
        capabilities[payload["service_name"]] = {
            "supports_actions": bool(payload["supports_actions"])
        }
        notifications["notification_service_capabilities"] = capabilities
        self._update_options({OPT_NOTIFICATIONS: notifications})
        return await self.async_step_notification_services()

    async def async_step_notification_service_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        capabilities = self._notification_service_capabilities()
        if not capabilities:
            return await self.async_step_notification_services()
        if user_input is None:
            return self.async_show_form(
                step_id="notification_service_edit",
                data_schema=vol.Schema(
                    {
                        vol.Required("service_name"): vol.In(
                            self._notification_service_choice_map(capabilities)
                        )
                    }
                ),
            )

        self._editing_notification_service_id = self._resolve_choice_value(
            self._notification_service_choice_map(capabilities),
            user_input.get("service_name"),
        )
        return await self.async_step_notification_service_edit_form()

    async def async_step_notification_service_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        service_name = str(getattr(self, "_editing_notification_service_id", "") or "").strip()
        capabilities = self._notification_service_capabilities()
        if not service_name or service_name not in capabilities:
            self._editing_notification_service_id = None
            return await self.async_step_notification_services()

        if user_input is None:
            current = dict(capabilities.get(service_name, {}))
            return self.async_show_form(
                step_id="notification_service_edit_form",
                data_schema=self._notification_service_schema(
                    {
                        "service_name": service_name,
                        "supports_actions": bool(current.get("supports_actions", False)),
                    },
                    is_edit=True,
                ),
            )

        payload = self._normalize_notification_service_payload(user_input)
        errors = self._validate_notification_service_payload(payload, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="notification_service_edit_form",
                data_schema=self._notification_service_schema(payload, is_edit=True),
                errors=errors,
            )

        notifications = self._notifications_config()
        updated = self._notification_service_capabilities()
        updated[service_name] = {"supports_actions": bool(payload["supports_actions"])}
        notifications["notification_service_capabilities"] = updated
        self._update_options({OPT_NOTIFICATIONS: notifications})
        self._editing_notification_service_id = None
        return await self.async_step_notification_services()

    async def async_step_notification_service_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        capabilities = self._notification_service_capabilities()
        if not capabilities:
            return await self.async_step_notification_services()
        if user_input is None:
            return self.async_show_form(
                step_id="notification_service_delete",
                data_schema=vol.Schema(
                    {
                        vol.Required("service_name"): vol.In(
                            self._notification_service_choice_map(capabilities)
                        )
                    }
                ),
            )

        self._editing_notification_service_id = self._resolve_choice_value(
            self._notification_service_choice_map(capabilities),
            user_input.get("service_name"),
        )
        return await self.async_step_notification_service_delete_confirm()

    async def async_step_notification_service_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        service_name = str(getattr(self, "_editing_notification_service_id", "") or "").strip()
        capabilities = self._notification_service_capabilities()
        if not service_name or service_name not in capabilities:
            self._editing_notification_service_id = None
            return await self.async_step_notification_services()
        if user_input is None or not bool(user_input.get("confirm", False)):
            return self.async_show_form(
                step_id="notification_service_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                description_placeholders={"service_name": service_name},
            )

        notifications = self._notifications_config()
        updated = self._notification_service_capabilities()
        updated.pop(service_name, None)
        notifications["notification_service_capabilities"] = updated
        self._update_options({OPT_NOTIFICATIONS: notifications})
        self._editing_notification_service_id = None
        return await self.async_step_notification_services()

    async def async_step_notification_services_done(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        return await self.async_step_init()

    async def async_step_notifications(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        current = dict(self.options.get(OPT_NOTIFICATIONS, {}))
        if user_input is None:
            return self.async_show_form(
                step_id="notifications", data_schema=self._notifications_schema(current)
            )

        errors = self._validate_notifications_payload(user_input)
        if errors:
            return self.async_show_form(
                step_id="notifications",
                data_schema=self._notifications_schema(user_input),
                errors=errors,
            )

        user_input = self._normalize_notifications_payload(user_input)
        self._update_options({OPT_NOTIFICATIONS: user_input})
        return await self.async_step_init()

    def _notifications_schema(self, defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        schema_defaults = dict(defaults)
        schema = vol.Schema(
            {
                vol.Optional("recipients"): _object_selector(),
                vol.Optional("recipient_groups"): _object_selector(),
                vol.Optional("route_targets"): _object_selector(),
                vol.Optional("notification_service_capabilities"): _object_selector(),
                vol.Optional("enabled_event_categories"): cv.multi_select(
                    EVENT_CATEGORIES_TOGGLEABLE
                ),
                vol.Optional(
                    "dedup_window_s", default=defaults.get("dedup_window_s", 60)
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "rate_limit_per_key_s", default=defaults.get("rate_limit_per_key_s", 300)
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "occupancy_mismatch_policy",
                    default=defaults.get(
                        "occupancy_mismatch_policy", DEFAULT_OCCUPANCY_MISMATCH_POLICY
                    ),
                ): vol.In(OCCUPANCY_MISMATCH_POLICIES),
                vol.Optional(
                    "occupancy_mismatch_min_derived_rooms",
                    default=defaults.get(
                        "occupancy_mismatch_min_derived_rooms",
                        DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "occupancy_mismatch_persist_s",
                    default=defaults.get(
                        "occupancy_mismatch_persist_s", DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "security_mismatch_policy",
                    default=defaults.get(
                        "security_mismatch_policy", DEFAULT_SECURITY_MISMATCH_POLICY
                    ),
                ): vol.In(SECURITY_MISMATCH_POLICIES),
                vol.Optional(
                    "security_mismatch_event_mode",
                    default=defaults.get(
                        "security_mismatch_event_mode",
                        DEFAULT_SECURITY_MISMATCH_EVENT_MODE,
                    ),
                ): vol.In(SECURITY_MISMATCH_EVENT_MODES),
                vol.Optional(
                    "security_mismatch_persist_s",
                    default=defaults.get(
                        "security_mismatch_persist_s", DEFAULT_SECURITY_MISMATCH_PERSIST_S
                    ),
                ): _NON_NEGATIVE_INT,
            }
        )
        defaults_with_categories = dict(schema_defaults)
        defaults_with_categories.setdefault(
            "enabled_event_categories", list(DEFAULT_ENABLED_EVENT_CATEGORIES)
        )
        return self._with_suggested(schema, defaults_with_categories)

    # ---- Normalization ----

    def _validate_notifications_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        recipients = _parse_multiline_mapping(payload.get("recipients"))
        recipient_groups = _parse_multiline_mapping(payload.get("recipient_groups"))
        route_targets = _parse_multiline_items(payload.get("route_targets"))

        recipient_ids = set(recipients)
        group_ids = set(recipient_groups)
        for members in recipient_groups.values():
            if any(member not in recipient_ids for member in members):
                return {"recipient_groups": "unknown_recipient"}

        if any(target not in recipient_ids and target not in group_ids for target in route_targets):
            return {"route_targets": "unknown_target"}

        return {}

    def _normalize_notifications_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        from ..const import EVENT_CATEGORIES_TOGGLEABLE as _ETC

        data = dict(payload)
        data.pop("routes", None)
        data["recipients"] = _parse_multiline_mapping(data.get("recipients"))
        data["recipient_groups"] = _parse_multiline_mapping(data.get("recipient_groups"))
        data["route_targets"] = _parse_multiline_items(data.get("route_targets"))
        data["notification_service_capabilities"] = _normalize_notification_service_capabilities(
            data.get("notification_service_capabilities")
        )
        recipient_ids = set(data["recipients"])
        normalized_groups: dict[str, list[str]] = {}
        for group_id, members in data["recipient_groups"].items():
            valid_members = [m for m in members if m in recipient_ids]
            if valid_members:
                normalized_groups[group_id] = valid_members
        data["recipient_groups"] = normalized_groups
        data["route_targets"] = [
            t for t in data["route_targets"] if t in recipient_ids or t in normalized_groups
        ]
        categories_present = "enabled_event_categories" in data
        categories = self._normalize_multi_value(data.get("enabled_event_categories"))
        if categories_present:
            data["enabled_event_categories"] = [c for c in categories if c in _ETC]
        else:
            data["enabled_event_categories"] = list(DEFAULT_ENABLED_EVENT_CATEGORIES)
        policy = str(data.get("occupancy_mismatch_policy", DEFAULT_OCCUPANCY_MISMATCH_POLICY))
        if policy not in OCCUPANCY_MISMATCH_POLICIES:
            policy = DEFAULT_OCCUPANCY_MISMATCH_POLICY
        data["occupancy_mismatch_policy"] = policy
        data["occupancy_mismatch_min_derived_rooms"] = int(
            data.get(
                "occupancy_mismatch_min_derived_rooms",
                DEFAULT_OCCUPANCY_MISMATCH_MIN_DERIVED_ROOMS,
            )
        )
        data["occupancy_mismatch_persist_s"] = int(
            data.get("occupancy_mismatch_persist_s", DEFAULT_OCCUPANCY_MISMATCH_PERSIST_S)
        )
        security_policy = str(
            data.get("security_mismatch_policy", DEFAULT_SECURITY_MISMATCH_POLICY)
        )
        if security_policy not in SECURITY_MISMATCH_POLICIES:
            security_policy = DEFAULT_SECURITY_MISMATCH_POLICY
        data["security_mismatch_policy"] = security_policy
        security_mode = str(
            data.get("security_mismatch_event_mode", DEFAULT_SECURITY_MISMATCH_EVENT_MODE)
        )
        if security_mode not in SECURITY_MISMATCH_EVENT_MODES:
            security_mode = DEFAULT_SECURITY_MISMATCH_EVENT_MODE
        data["security_mismatch_event_mode"] = security_mode
        data["security_mismatch_persist_s"] = int(
            data.get("security_mismatch_persist_s", DEFAULT_SECURITY_MISMATCH_PERSIST_S)
        )
        return data

    def _notifications_config(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_NOTIFICATIONS, {}))

    def _notification_recipients(self) -> dict[str, list[str]]:
        return _parse_multiline_mapping(self._notifications_config().get("recipients"))

    def _notification_groups(self) -> dict[str, list[str]]:
        return _parse_multiline_mapping(self._notifications_config().get("recipient_groups"))

    def _notification_service_capabilities(self) -> dict[str, dict[str, bool]]:
        return _normalize_notification_service_capabilities(
            self._notifications_config().get("notification_service_capabilities")
        )

    def _notification_recipient_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        is_edit: bool = False,
    ) -> vol.Schema:
        defaults = defaults or {}
        services = defaults.get("notify_services")
        if isinstance(services, list | tuple | set):
            services = "\n".join(str(item) for item in services)
        schema = vol.Schema(
            {
                vol.Required(
                    "recipient_id",
                    default=str(defaults.get("recipient_id") or ""),
                ): str,
                vol.Required(
                    "notify_services",
                    default=str(services or ""),
                ): _multiline_notify_services,
            }
        )
        if is_edit:
            return schema
        return schema

    def _normalize_notification_recipient_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "recipient_id": str(payload.get("recipient_id") or "").strip(),
            "notify_services": _notification_service_list(payload.get("notify_services")),
        }

    def _validate_notification_recipient_payload(
        self,
        payload: dict[str, Any],
        *,
        is_edit: bool,
    ) -> dict[str, str]:
        recipient_id = str(payload.get("recipient_id") or "").strip()
        if not recipient_id or not _is_valid_slug(recipient_id):
            return {"recipient_id": "invalid_slug"}
        if is_edit and recipient_id != getattr(self, "_editing_notification_recipient_id", None):
            return {"recipient_id": "immutable_field"}
        if not payload.get("notify_services"):
            return {"notify_services": "required"}
        recipients = self._notification_recipients()
        if not is_edit and recipient_id in recipients:
            return {"recipient_id": "already_exists"}
        return {}

    def _notification_recipient_choice_map(
        self, recipients: dict[str, list[str]]
    ) -> dict[str, str]:
        people_labels = self._notification_people_display_names()
        choices: dict[str, str] = {}
        for recipient_id in sorted(recipients):
            label = people_labels.get(recipient_id, recipient_id)
            choices[f"{label} ({recipient_id})"] = recipient_id
        return choices

    def _notification_people_display_names(self) -> dict[str, str]:
        people = self.options.get("people_named")
        if not isinstance(people, list):
            return {}
        labels: dict[str, str] = {}
        for person in people:
            if not isinstance(person, dict):
                continue
            slug = str(person.get("slug") or "").strip()
            display_name = str(person.get("display_name") or "").strip()
            if slug and display_name:
                labels[slug] = display_name
        return labels

    def _notification_recipients_summary(self, notifications: dict[str, Any]) -> str:
        recipients = _parse_multiline_mapping(notifications.get("recipients"))
        if not recipients:
            return "No notification recipients configured."
        return "\n".join(
            f"{recipient_id}: {', '.join(services)}"
            for recipient_id, services in sorted(recipients.items())
        )

    def _notification_recipient_references(self, recipient_id: str) -> list[str]:
        notifications = self._notifications_config()
        references: list[str] = []
        groups = _parse_multiline_mapping(notifications.get("recipient_groups"))
        for group_id, members in groups.items():
            if recipient_id in members:
                references.append(f"group:{group_id}")
        if recipient_id in _parse_multiline_items(notifications.get("route_targets")):
            references.append("route_targets")

        reactions = self.options.get("reactions")
        if isinstance(reactions, dict):
            configured = reactions.get("configured")
            if isinstance(configured, dict):
                for reaction_id, cfg in configured.items():
                    if _execution_policy_references_recipient(cfg, recipient_id):
                        references.append(f"reaction:{reaction_id}")
            profiles = reactions.get("execution_policy_profiles")
            if isinstance(profiles, dict):
                for profile_id, profile in profiles.items():
                    if _execution_policy_references_recipient(profile, recipient_id):
                        references.append(f"execution_policy_profile:{profile_id}")
        return references

    def _notification_group_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        is_edit: bool = False,
    ) -> vol.Schema:
        defaults = defaults or {}
        members = defaults.get("members")
        if isinstance(members, list | tuple | set):
            members = "\n".join(str(item) for item in members)
        return vol.Schema(
            {
                vol.Required("group_id", default=str(defaults.get("group_id") or "")): str,
                vol.Required("members", default=str(members or "")): str,
            }
        )

    def _normalize_notification_group_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "group_id": str(payload.get("group_id") or "").strip(),
            "members": _parse_multiline_items(payload.get("members")),
        }

    def _validate_notification_group_payload(
        self,
        payload: dict[str, Any],
        *,
        is_edit: bool,
    ) -> dict[str, str]:
        group_id = str(payload.get("group_id") or "").strip()
        if not group_id or not _is_valid_slug(group_id):
            return {"group_id": "invalid_slug"}
        if is_edit and group_id != getattr(self, "_editing_notification_group_id", None):
            return {"group_id": "immutable_field"}
        groups = self._notification_groups()
        if not is_edit and group_id in groups:
            return {"group_id": "already_exists"}
        recipients = self._notification_recipients()
        members = payload.get("members")
        if not members:
            return {"members": "required"}
        if any(member not in recipients for member in members):
            return {"members": "unknown_recipient"}
        return {}

    def _notification_group_choice_map(self, groups: dict[str, list[str]]) -> dict[str, str]:
        return {
            f"{group_id} ({len(members)} recipient(s))": group_id
            for group_id, members in sorted(groups.items())
        }

    def _notification_groups_summary(self, notifications: dict[str, Any]) -> str:
        groups = _parse_multiline_mapping(notifications.get("recipient_groups"))
        if not groups:
            return "No notification recipient groups configured."
        return "\n".join(
            f"{group_id}: {', '.join(members)}" for group_id, members in sorted(groups.items())
        )

    def _notification_group_references(self, group_id: str) -> list[str]:
        notifications = self._notifications_config()
        references: list[str] = []
        if group_id in _parse_multiline_items(notifications.get("route_targets")):
            references.append("route_targets")

        reactions = self.options.get("reactions")
        if isinstance(reactions, dict):
            configured = reactions.get("configured")
            if isinstance(configured, dict):
                for reaction_id, cfg in configured.items():
                    if _execution_policy_references_group(cfg, group_id):
                        references.append(f"reaction:{reaction_id}")
            profiles = reactions.get("execution_policy_profiles")
            if isinstance(profiles, dict):
                for profile_id, profile in profiles.items():
                    if _execution_policy_references_group(profile, group_id):
                        references.append(f"execution_policy_profile:{profile_id}")
        return references

    def _notification_route_target_choice_map(self) -> dict[str, str]:
        choices: dict[str, str] = {}
        for recipient_id in sorted(self._notification_recipients()):
            choices[f"Recipient: {recipient_id}"] = recipient_id
        for group_id in sorted(self._notification_groups()):
            choices[f"Group: {group_id}"] = group_id
        return choices

    def _validate_notification_route_targets(self, targets: list[str]) -> dict[str, str]:
        available = set(self._notification_recipients()) | set(self._notification_groups())
        if any(target not in available for target in targets):
            return {"route_targets": "unknown_target"}
        return {}

    def _notification_service_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        is_edit: bool = False,
    ) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    "service_name",
                    default=str(defaults.get("service_name") or ""),
                ): str,
                vol.Optional(
                    "supports_actions",
                    default=bool(defaults.get("supports_actions", False)),
                ): bool,
            }
        )

    def _normalize_notification_service_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "service_name": _normalize_notify_service_name(payload.get("service_name")),
            "supports_actions": bool(payload.get("supports_actions", False)),
        }

    def _validate_notification_service_payload(
        self,
        payload: dict[str, Any],
        *,
        is_edit: bool,
    ) -> dict[str, str]:
        service_name = str(payload.get("service_name") or "").strip()
        if not service_name:
            return {"service_name": "required"}
        if is_edit and service_name != getattr(self, "_editing_notification_service_id", None):
            return {"service_name": "immutable_field"}
        capabilities = self._notification_service_capabilities()
        if not is_edit and service_name in capabilities:
            return {"service_name": "already_exists"}
        return {}

    def _notification_service_choice_map(
        self, capabilities: dict[str, dict[str, bool]]
    ) -> dict[str, str]:
        choices: dict[str, str] = {}
        for service_name, capability in sorted(capabilities.items()):
            suffix = "actions" if capability.get("supports_actions", False) else "text only"
            choices[f"notify.{service_name} ({suffix})"] = service_name
        return choices

    def _notification_services_summary(self, capabilities: dict[str, dict[str, bool]]) -> str:
        if not capabilities:
            return "No notification service capabilities configured."
        lines: list[str] = []
        for service_name, capability in sorted(capabilities.items()):
            supports = "supports actions" if capability.get("supports_actions") else "text only"
            lines.append(f"notify.{service_name}: {supports}")
        return "\n".join(lines)


def _normalize_notification_service_capabilities(value: Any) -> dict[str, dict[str, bool]]:
    """Normalize transport capability metadata for concrete notify services."""
    if not isinstance(value, dict):
        return {}
    normalized: dict[str, dict[str, bool]] = {}
    for raw_service, raw_capabilities in value.items():
        service = _normalize_notify_service_name(raw_service)
        if not service:
            continue
        supports_actions = False
        if isinstance(raw_capabilities, dict):
            supports_actions = bool(raw_capabilities.get("supports_actions", False))
        elif isinstance(raw_capabilities, bool):
            supports_actions = raw_capabilities
        normalized[service] = {"supports_actions": supports_actions}
    return normalized


def _normalize_notify_service_name(value: Any) -> str:
    service = str(value or "").strip()
    if service.startswith("notify."):
        service = service.split(".", 1)[1]
    return service


def _multiline_notify_services(value: Any) -> list[str]:
    services = _notification_service_list(value)
    if not services:
        raise vol.Invalid("required")
    return services


def _notification_service_list(value: Any) -> list[str]:
    services: list[str] = []
    seen: set[str] = set()
    for item in _parse_multiline_items(value):
        service = _normalize_notify_service_name(item)
        if not service or service in seen:
            continue
        seen.add(service)
        services.append(service)
    return services


def _execution_policy_references_recipient(value: Any, recipient_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    for policy_key in ("execution_policy", "execution_policy_override"):
        policy = value.get(policy_key)
        if _policy_mapping_references_recipient(policy, recipient_id):
            return True
    return _policy_mapping_references_recipient(value, recipient_id)


def _execution_policy_references_group(value: Any, group_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    for policy_key in ("execution_policy", "execution_policy_override"):
        policy = value.get(policy_key)
        if _policy_mapping_references_group(policy, group_id):
            return True
    return _policy_mapping_references_group(value, group_id)


def _policy_mapping_references_recipient(value: Any, recipient_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    confirmation = value.get("confirmation")
    if isinstance(confirmation, dict) and recipient_id in _parse_multiline_items(
        confirmation.get("target_recipients")
    ):
        return True
    promotion = value.get("promotion")
    return isinstance(promotion, dict) and recipient_id in _parse_multiline_items(
        promotion.get("target_recipients")
    )


def _policy_mapping_references_group(value: Any, group_id: str) -> bool:
    if not isinstance(value, dict):
        return False
    confirmation = value.get("confirmation")
    if isinstance(confirmation, dict) and group_id in _parse_multiline_items(
        confirmation.get("target_groups")
    ):
        return True
    promotion = value.get("promotion")
    return isinstance(promotion, dict) and group_id in _parse_multiline_items(
        promotion.get("target_groups")
    )
