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
from ..runtime.notifications import (
    AUDIENCE_POLICY_OBSERVABILITY,
    AUDIENCE_POLICY_VALUES,
    AUDIENCE_TARGET_ROLES,
    DEFAULT_AGGREGATION,
    DEFAULT_AUDIENCE_POLICY,
    DEFAULT_AUDIENCE_TARGETS,
    DEFAULT_PERSISTENCE_THRESHOLDS,
    DEFAULT_STARTUP_NOTIFICATION_GRACE_S,
    normalize_notification_policy_config,
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

    _NOISY_RESIDENT_POLICY_FAMILIES = frozenset(
        {"people", "reaction", "house_state", "occupancy_mismatch"}
    )
    _RESIDENT_PUSH_POLICIES = frozenset(
        {
            "residents",
            "residents_and_admins",
            "residents_and_admins_after_persistence",
            "residents_and_admins_when_critical_else_admins_after_persistence",
        }
    )

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
                    {vol.Required("group_id"): vol.In(self._notification_group_choice_map(groups))}
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
                    {vol.Required("group_id"): vol.In(self._notification_group_choice_map(groups))}
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

    async def async_step_notification_delivery_policy(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        notifications = normalize_notification_policy_config(self._notifications_config())
        if user_input is None:
            return self.async_show_form(
                step_id="notification_delivery_policy",
                data_schema=self._notification_delivery_policy_schema(notifications),
                description_placeholders={
                    "summary": self._notification_delivery_policy_summary(notifications)
                },
            )

        errors = self._validate_notification_delivery_policy_payload(user_input)
        if errors:
            return self.async_show_form(
                step_id="notification_delivery_policy",
                data_schema=self._notification_delivery_policy_schema(user_input),
                errors=errors,
                description_placeholders={
                    "summary": self._notification_delivery_policy_summary(notifications)
                },
            )

        updated = self._normalize_notification_delivery_policy_payload(user_input)
        next_notifications = self._notifications_config()
        next_notifications.update(updated)
        self._update_options({OPT_NOTIFICATIONS: next_notifications})
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

    async def async_step_execution_policy_profiles(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        profiles = self._execution_policy_profiles()
        menu_options = ["execution_policy_profile_add"]
        if profiles:
            menu_options.extend(
                ["execution_policy_profile_edit", "execution_policy_profile_delete"]
            )
        menu_options.append("execution_policy_profiles_done")
        return self.async_show_menu(
            step_id="execution_policy_profiles",
            menu_options=menu_options,
            description_placeholders={
                "summary": self._execution_policy_profiles_summary(profiles),
            },
        )

    async def async_step_execution_policy_profile_add(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        if user_input is None:
            return self.async_show_form(
                step_id="execution_policy_profile_add",
                data_schema=self._execution_policy_profile_schema(),
            )

        payload = self._normalize_execution_policy_profile_payload(user_input)
        errors = self._validate_execution_policy_profile_payload(payload, is_edit=False)
        if errors:
            return self.async_show_form(
                step_id="execution_policy_profile_add",
                data_schema=self._execution_policy_profile_schema(payload),
                errors=errors,
            )

        reactions = self._reactions_config()
        profiles = dict(reactions.get("execution_policy_profiles", {}))
        profiles[payload["profile_id"]] = self._execution_policy_profile_from_payload(payload)
        reactions["execution_policy_profiles"] = profiles
        self._update_options({"reactions": reactions})
        return await self.async_step_execution_policy_profiles()

    async def async_step_execution_policy_profile_edit(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        profiles = self._execution_policy_profiles()
        if not profiles:
            return await self.async_step_execution_policy_profiles()
        if user_input is None:
            return self.async_show_form(
                step_id="execution_policy_profile_edit",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile_id"): vol.In(
                            self._execution_policy_profile_choice_map(profiles)
                        )
                    }
                ),
            )

        self._editing_execution_policy_profile_id = self._resolve_choice_value(
            self._execution_policy_profile_choice_map(profiles),
            user_input.get("profile_id"),
        )
        return await self.async_step_execution_policy_profile_edit_form()

    async def async_step_execution_policy_profile_edit_form(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        profile_id = str(getattr(self, "_editing_execution_policy_profile_id", "") or "").strip()
        profiles = self._execution_policy_profiles()
        if not profile_id or profile_id not in profiles:
            self._editing_execution_policy_profile_id = None
            return await self.async_step_execution_policy_profiles()

        if user_input is None:
            return self.async_show_form(
                step_id="execution_policy_profile_edit_form",
                data_schema=self._execution_policy_profile_schema(
                    self._execution_policy_profile_defaults(profile_id, profiles[profile_id]),
                    is_edit=True,
                ),
            )

        payload = self._normalize_execution_policy_profile_payload(user_input)
        errors = self._validate_execution_policy_profile_payload(payload, is_edit=True)
        if errors:
            return self.async_show_form(
                step_id="execution_policy_profile_edit_form",
                data_schema=self._execution_policy_profile_schema(payload, is_edit=True),
                errors=errors,
            )

        reactions = self._reactions_config()
        updated = dict(reactions.get("execution_policy_profiles", {}))
        updated[profile_id] = self._execution_policy_profile_from_payload(payload)
        reactions["execution_policy_profiles"] = updated
        self._update_options({"reactions": reactions})
        self._editing_execution_policy_profile_id = None
        return await self.async_step_execution_policy_profiles()

    async def async_step_execution_policy_profile_delete(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        profiles = self._execution_policy_profiles()
        if not profiles:
            return await self.async_step_execution_policy_profiles()
        if user_input is None:
            return self.async_show_form(
                step_id="execution_policy_profile_delete",
                data_schema=vol.Schema(
                    {
                        vol.Required("profile_id"): vol.In(
                            self._execution_policy_profile_choice_map(profiles)
                        )
                    }
                ),
            )

        self._editing_execution_policy_profile_id = self._resolve_choice_value(
            self._execution_policy_profile_choice_map(profiles),
            user_input.get("profile_id"),
        )
        return await self.async_step_execution_policy_profile_delete_confirm()

    async def async_step_execution_policy_profile_delete_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> "FlowResult":
        profile_id = str(getattr(self, "_editing_execution_policy_profile_id", "") or "").strip()
        profiles = self._execution_policy_profiles()
        if not profile_id or profile_id not in profiles:
            self._editing_execution_policy_profile_id = None
            return await self.async_step_execution_policy_profiles()

        references = self._execution_policy_profile_references(profile_id)
        if references:
            return self.async_show_form(
                step_id="execution_policy_profile_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                errors={"base": "execution_policy_profile_in_use"},
                description_placeholders={
                    "profile_id": profile_id,
                    "references": ", ".join(references),
                },
            )

        if user_input is None or not bool(user_input.get("confirm", False)):
            return self.async_show_form(
                step_id="execution_policy_profile_delete_confirm",
                data_schema=vol.Schema({vol.Optional("confirm", default=False): bool}),
                description_placeholders={"profile_id": profile_id, "references": ""},
            )

        reactions = self._reactions_config()
        updated = dict(reactions.get("execution_policy_profiles", {}))
        updated.pop(profile_id, None)
        reactions["execution_policy_profiles"] = updated
        self._update_options({"reactions": reactions})
        self._editing_execution_policy_profile_id = None
        return await self.async_step_execution_policy_profiles()

    async def async_step_execution_policy_profiles_done(
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
                vol.Optional("audience_targets"): _object_selector(),
                vol.Optional("audience_policy"): _object_selector(),
                vol.Optional("persistence_thresholds"): _object_selector(),
                vol.Optional("aggregation"): _object_selector(),
                vol.Optional("enabled_event_categories"): cv.multi_select(
                    EVENT_CATEGORIES_TOGGLEABLE
                ),
                vol.Optional(
                    "startup_notification_grace_s",
                    default=defaults.get("startup_notification_grace_s", 300),
                ): _NON_NEGATIVE_INT,
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

    def _notification_delivery_policy_schema(
        self, defaults: dict[str, Any] | None = None
    ) -> vol.Schema:
        normalized = normalize_notification_policy_config(defaults or {})
        choices = self._notification_route_target_choice_map()
        policy = normalized["audience_policy"]
        thresholds = normalized["persistence_thresholds"]
        aggregation = normalized["aggregation"]
        burst = aggregation["global_burst_limit"]
        targets = normalized["audience_targets"]
        return vol.Schema(
            {
                vol.Optional(
                    "audience_admin_targets",
                    default=list(targets.get("admins", DEFAULT_AUDIENCE_TARGETS["admins"])),
                ): cv.multi_select(choices),
                vol.Optional(
                    "audience_resident_targets",
                    default=list(targets.get("residents", DEFAULT_AUDIENCE_TARGETS["residents"])),
                ): cv.multi_select(choices),
                vol.Required(
                    "people_push",
                    default=policy.get("people", DEFAULT_AUDIENCE_POLICY["people"])["push"],
                ): vol.In(sorted(AUDIENCE_POLICY_VALUES)),
                vol.Required(
                    "reaction_push",
                    default=policy.get("reaction", DEFAULT_AUDIENCE_POLICY["reaction"])["push"],
                ): vol.In(sorted(AUDIENCE_POLICY_VALUES)),
                vol.Required(
                    "occupancy_mismatch_push",
                    default=policy.get(
                        "occupancy_mismatch", DEFAULT_AUDIENCE_POLICY["occupancy_mismatch"]
                    )["push"],
                ): vol.In(sorted(AUDIENCE_POLICY_VALUES)),
                vol.Required(
                    "security_presence_mismatch_push",
                    default=policy.get(
                        "security_presence_mismatch",
                        DEFAULT_AUDIENCE_POLICY["security_presence_mismatch"],
                    )["push"],
                ): vol.In(sorted(AUDIENCE_POLICY_VALUES)),
                vol.Required(
                    "system_config_issue_push",
                    default=policy.get(
                        "system_config_issue", DEFAULT_AUDIENCE_POLICY["system_config_issue"]
                    )["push"],
                ): vol.In(sorted(AUDIENCE_POLICY_VALUES)),
                vol.Optional(
                    "startup_notification_grace_s",
                    default=normalized.get(
                        "startup_notification_grace_s", DEFAULT_STARTUP_NOTIFICATION_GRACE_S
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "occupancy_mismatch_persist_s",
                    default=thresholds.get(
                        "occupancy_mismatch",
                        DEFAULT_PERSISTENCE_THRESHOLDS["occupancy_mismatch"],
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "security_presence_mismatch_persist_s",
                    default=thresholds.get(
                        "security_presence_mismatch",
                        DEFAULT_PERSISTENCE_THRESHOLDS["security_presence_mismatch"],
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "mismatch_window_s",
                    default=aggregation.get(
                        "mismatch_window_s", DEFAULT_AGGREGATION["mismatch_window_s"]
                    ),
                ): _NON_NEGATIVE_INT,
                vol.Optional(
                    "global_burst_max_notifications",
                    default=burst.get(
                        "max_notifications",
                        DEFAULT_AGGREGATION["global_burst_limit"]["max_notifications"],
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "global_burst_window_s",
                    default=burst.get("window_s", DEFAULT_AGGREGATION["global_burst_limit"]["window_s"]),
                ): vol.All(vol.Coerce(int), vol.Range(min=10)),
                vol.Optional("confirm_noisy_resident_push", default=False): bool,
            }
        )

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

        audience_targets = payload.get("audience_targets")
        if isinstance(audience_targets, dict):
            available_targets = recipient_ids | group_ids
            for role, targets in audience_targets.items():
                if str(role) not in AUDIENCE_TARGET_ROLES:
                    return {"audience_targets": "unknown_target"}
                for target in _parse_multiline_items(targets):
                    if target == AUDIENCE_POLICY_OBSERVABILITY:
                        return {"audience_targets": "unknown_target"}
                    if target not in available_targets:
                        return {"audience_targets": "unknown_target"}

        audience_policy = payload.get("audience_policy")
        if isinstance(audience_policy, dict):
            for raw_policy in audience_policy.values():
                push = ""
                if isinstance(raw_policy, dict):
                    push = str(raw_policy.get("push") or "").strip()
                elif raw_policy is not None:
                    push = str(raw_policy).strip()
                if push and push not in AUDIENCE_POLICY_VALUES:
                    return {"audience_policy": "invalid_policy"}

        return {}

    def _validate_notification_delivery_policy_payload(
        self, payload: dict[str, Any]
    ) -> dict[str, str]:
        available = set(self._notification_recipients()) | set(self._notification_groups())
        admin_targets = _parse_multiline_items(payload.get("audience_admin_targets"))
        resident_targets = _parse_multiline_items(payload.get("audience_resident_targets"))
        for target in admin_targets + resident_targets:
            if target == AUDIENCE_POLICY_OBSERVABILITY or target not in available:
                return {"audience_admin_targets": "unknown_target"}

        noisy_enabled = self._notification_delivery_policy_noisy_resident_families(payload)
        if noisy_enabled and not bool(payload.get("confirm_noisy_resident_push", False)):
            return {"confirm_noisy_resident_push": "required"}
        return {}

    def _normalize_notification_delivery_policy_payload(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        current = normalize_notification_policy_config(self._notifications_config())
        policy = dict(current["audience_policy"])
        policy["people"] = {"push": str(payload.get("people_push"))}
        policy["reaction"] = {"push": str(payload.get("reaction_push"))}
        policy["occupancy_mismatch"] = {"push": str(payload.get("occupancy_mismatch_push"))}
        policy["security_presence_mismatch"] = {
            "push": str(payload.get("security_presence_mismatch_push"))
        }
        policy["system_config_issue"] = {"push": str(payload.get("system_config_issue_push"))}
        return normalize_notification_policy_config(
            {
                **self._notifications_config(),
                "audience_targets": {
                    "admins": _parse_multiline_items(payload.get("audience_admin_targets")),
                    "residents": _parse_multiline_items(payload.get("audience_resident_targets")),
                },
                "audience_policy": policy,
                "startup_notification_grace_s": int(
                    payload.get("startup_notification_grace_s", DEFAULT_STARTUP_NOTIFICATION_GRACE_S)
                ),
                "persistence_thresholds": {
                    **current["persistence_thresholds"],
                    "occupancy_mismatch": int(payload.get("occupancy_mismatch_persist_s", 600)),
                    "security_presence_mismatch": int(
                        payload.get("security_presence_mismatch_persist_s", 300)
                    ),
                },
                "aggregation": {
                    **current["aggregation"],
                    "mismatch_window_s": int(payload.get("mismatch_window_s", 300)),
                    "global_burst_limit": {
                        "max_notifications": int(
                            payload.get("global_burst_max_notifications", 2)
                        ),
                        "window_s": int(payload.get("global_burst_window_s", 60)),
                    },
                },
            },
            sanitize_unresolved_targets=True,
        )

    def _notification_delivery_policy_noisy_resident_families(
        self, payload: dict[str, Any]
    ) -> list[str]:
        field_by_family = {
            "people": "people_push",
            "reaction": "reaction_push",
            "occupancy_mismatch": "occupancy_mismatch_push",
        }
        noisy: list[str] = []
        for family, field in field_by_family.items():
            policy = str(payload.get(field) or "").strip()
            if family in self._NOISY_RESIDENT_POLICY_FAMILIES and policy in self._RESIDENT_PUSH_POLICIES:
                noisy.append(family)
        return noisy

    def _notification_delivery_policy_summary(self, notifications: dict[str, Any]) -> str:
        normalized = normalize_notification_policy_config(notifications)
        policy = normalized["audience_policy"]
        targets = normalized["audience_targets"]
        return (
            f"admins={', '.join(targets.get('admins', [])) or '-'}; "
            f"residents={', '.join(targets.get('residents', [])) or '-'}; "
            f"people={policy.get('people', {}).get('push', '')}; "
            f"reaction={policy.get('reaction', {}).get('push', '')}; "
            f"occupancy={policy.get('occupancy_mismatch', {}).get('push', '')}; "
            f"security={policy.get('security_presence_mismatch', {}).get('push', '')}"
        )

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
        return normalize_notification_policy_config(data, sanitize_unresolved_targets=True)

    def _notifications_config(self) -> dict[str, Any]:
        return dict(self.options.get(OPT_NOTIFICATIONS, {}))

    def _reactions_config(self) -> dict[str, Any]:
        reactions = self.options.get("reactions")
        return dict(reactions) if isinstance(reactions, dict) else {}

    def _notification_recipients(self) -> dict[str, list[str]]:
        return _parse_multiline_mapping(self._notifications_config().get("recipients"))

    def _notification_groups(self) -> dict[str, list[str]]:
        return _parse_multiline_mapping(self._notifications_config().get("recipient_groups"))

    def _available_notify_service_options(
        self,
        *,
        include: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, str]:
        services: set[str] = set()
        hass_services = getattr(getattr(self, "hass", None), "services", None)
        service_map_getter = getattr(hass_services, "async_services", None)
        if callable(service_map_getter):
            raw_services = service_map_getter()
            notify_services = (
                raw_services.get("notify", {}) if isinstance(raw_services, dict) else {}
            )
            if isinstance(notify_services, dict):
                services.update(
                    _normalize_notify_service_name(service)
                    for service in notify_services
                    if _normalize_notify_service_name(service)
                )
        for configured_services in self._notification_recipients().values():
            services.update(
                _normalize_notify_service_name(service)
                for service in configured_services
                if _normalize_notify_service_name(service)
            )
        services.update(self._notification_service_capabilities())
        for service in include or []:
            normalized = _normalize_notify_service_name(service)
            if normalized:
                services.add(normalized)
        return {service: f"notify.{service}" for service in sorted(services)}

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
        service_list = _notification_service_list(services)
        service_options = self._available_notify_service_options(include=service_list)
        service_field: Any
        service_default: Any
        if service_options:
            service_field = cv.multi_select(service_options)
            service_default = service_list
        else:
            service_field = str
            service_default = str(services or "")
        schema = vol.Schema(
            {
                vol.Required(
                    "recipient_id",
                    default=str(defaults.get("recipient_id") or ""),
                ): str,
                vol.Required(
                    "notify_services",
                    default=service_default,
                ): service_field,
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

    def _notification_recipient_multiselect_options(
        self,
        *,
        include: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, str]:
        recipients = self._notification_recipients()
        labels = self._notification_people_display_names()
        options = {
            recipient_id: labels.get(recipient_id, recipient_id)
            for recipient_id in sorted(recipients)
        }
        for recipient_id in include or []:
            normalized = str(recipient_id or "").strip()
            if normalized:
                options.setdefault(normalized, labels.get(normalized, normalized))
        return options

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
        member_list = _parse_multiline_items(members)
        member_options = self._notification_recipient_multiselect_options(include=member_list)
        member_field: Any
        member_default: Any
        if member_options:
            member_field = cv.multi_select(member_options)
            member_default = member_list
        else:
            member_field = str
            member_default = str(members or "")
        return vol.Schema(
            {
                vol.Required("group_id", default=str(defaults.get("group_id") or "")): str,
                vol.Required("members", default=member_default): member_field,
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

    def _notification_group_multiselect_options(
        self,
        *,
        include: list[str] | tuple[str, ...] | set[str] | None = None,
    ) -> dict[str, str]:
        options = {group_id: group_id for group_id in sorted(self._notification_groups())}
        for group_id in include or []:
            normalized = str(group_id or "").strip()
            if normalized:
                options.setdefault(normalized, normalized)
        return options

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
            choices[recipient_id] = f"Recipient: {recipient_id}"
        for group_id in sorted(self._notification_groups()):
            choices[group_id] = f"Group: {group_id}"
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
        service_name = _normalize_notify_service_name(defaults.get("service_name"))
        service_options = self._available_notify_service_options(include=[service_name])
        service_field: Any = vol.In(service_options) if service_options else str
        return vol.Schema(
            {
                vol.Required(
                    "service_name",
                    default=service_name,
                ): service_field,
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

    def _execution_policy_profiles(self) -> dict[str, dict[str, Any]]:
        profiles = self._reactions_config().get("execution_policy_profiles")
        if not isinstance(profiles, dict):
            return {}
        return {str(key): dict(value) for key, value in profiles.items() if isinstance(value, dict)}

    def _execution_policy_profile_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        is_edit: bool = False,
    ) -> vol.Schema:
        defaults = defaults or {}
        confirmation_recipients = _parse_multiline_items(
            defaults.get("confirmation_target_recipients")
        )
        confirmation_groups = _parse_multiline_items(defaults.get("confirmation_target_groups"))
        promotion_recipients = _parse_multiline_items(defaults.get("promotion_target_recipients"))
        promotion_groups = _parse_multiline_items(defaults.get("promotion_target_groups"))
        recipient_options = self._notification_recipient_multiselect_options(
            include=[*confirmation_recipients, *promotion_recipients]
        )
        group_options = self._notification_group_multiselect_options(
            include=[*confirmation_groups, *promotion_groups]
        )
        return vol.Schema(
            {
                vol.Required("profile_id", default=str(defaults.get("profile_id") or "")): str,
                vol.Required("mode", default=str(defaults.get("mode") or "ask_residents")): vol.In(
                    {"auto_apply": "Apply automatically", "ask_residents": "Ask residents"}
                ),
                vol.Optional(
                    "confirmation_target_recipients",
                    default=confirmation_recipients
                    if recipient_options
                    else str(defaults.get("confirmation_target_recipients") or ""),
                ): cv.multi_select(recipient_options) if recipient_options else str,
                vol.Optional(
                    "confirmation_target_groups",
                    default=confirmation_groups
                    if group_options
                    else str(defaults.get("confirmation_target_groups") or ""),
                ): cv.multi_select(group_options) if group_options else str,
                vol.Optional(
                    "confirmation_use_default_route_targets",
                    default=bool(defaults.get("confirmation_use_default_route_targets", True)),
                ): bool,
                vol.Optional(
                    "confirmation_expires_in_minutes",
                    default=int(defaults.get("confirmation_expires_in_minutes") or 10),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "confirmation_on_timeout",
                    default=str(defaults.get("confirmation_on_timeout") or "skip"),
                ): vol.In({"skip": "Skip", "apply": "Apply"}),
                vol.Optional(
                    "promotion_enabled",
                    default=bool(defaults.get("promotion_enabled", True)),
                ): bool,
                vol.Optional(
                    "promotion_target_recipients",
                    default=promotion_recipients
                    if recipient_options
                    else str(defaults.get("promotion_target_recipients") or ""),
                ): cv.multi_select(recipient_options) if recipient_options else str,
                vol.Optional(
                    "promotion_target_groups",
                    default=promotion_groups
                    if group_options
                    else str(defaults.get("promotion_target_groups") or ""),
                ): cv.multi_select(group_options) if group_options else str,
                vol.Optional(
                    "promotion_min_samples",
                    default=int(defaults.get("promotion_min_samples") or 5),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
                vol.Optional(
                    "promotion_min_approval_rate",
                    default=float(defaults.get("promotion_min_approval_rate") or 0.8),
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=1)),
                vol.Optional(
                    "promotion_min_distinct_days",
                    default=int(defaults.get("promotion_min_distinct_days") or 3),
                ): vol.All(vol.Coerce(int), vol.Range(min=0)),
                vol.Optional(
                    "promotion_reminder_interval_days",
                    default=int(defaults.get("promotion_reminder_interval_days") or 7),
                ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            }
        )

    def _normalize_execution_policy_profile_payload(
        self, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "profile_id": str(payload.get("profile_id") or "").strip(),
            "mode": str(payload.get("mode") or "auto_apply").strip(),
            "confirmation_target_recipients": _parse_multiline_items(
                payload.get("confirmation_target_recipients")
            ),
            "confirmation_target_groups": _parse_multiline_items(
                payload.get("confirmation_target_groups")
            ),
            "confirmation_use_default_route_targets": bool(
                payload.get("confirmation_use_default_route_targets", True)
            ),
            "confirmation_expires_in_minutes": int(
                payload.get("confirmation_expires_in_minutes") or 10
            ),
            "confirmation_on_timeout": str(payload.get("confirmation_on_timeout") or "skip"),
            "promotion_enabled": bool(payload.get("promotion_enabled", True)),
            "promotion_target_recipients": _parse_multiline_items(
                payload.get("promotion_target_recipients")
            ),
            "promotion_target_groups": _parse_multiline_items(
                payload.get("promotion_target_groups")
            ),
            "promotion_min_samples": int(payload.get("promotion_min_samples") or 5),
            "promotion_min_approval_rate": float(payload.get("promotion_min_approval_rate") or 0.8),
            "promotion_min_distinct_days": int(payload.get("promotion_min_distinct_days") or 3),
            "promotion_reminder_interval_days": int(
                payload.get("promotion_reminder_interval_days") or 7
            ),
        }

    def _validate_execution_policy_profile_payload(
        self,
        payload: dict[str, Any],
        *,
        is_edit: bool,
    ) -> dict[str, str]:
        profile_id = str(payload.get("profile_id") or "").strip()
        if not profile_id or not _is_valid_slug(profile_id):
            return {"profile_id": "invalid_slug"}
        if is_edit and profile_id != getattr(self, "_editing_execution_policy_profile_id", None):
            return {"profile_id": "immutable_field"}
        profiles = self._execution_policy_profiles()
        if not is_edit and profile_id in profiles:
            return {"profile_id": "already_exists"}
        if payload.get("mode") not in {"auto_apply", "ask_residents"}:
            return {"mode": "invalid_option"}

        recipients = set(self._notification_recipients())
        groups = set(self._notification_groups())
        for field in ("confirmation_target_recipients", "promotion_target_recipients"):
            if any(item not in recipients for item in payload.get(field, [])):
                return {field: "unknown_recipient"}
        for field in ("confirmation_target_groups", "promotion_target_groups"):
            if any(item not in groups for item in payload.get(field, [])):
                return {field: "unknown_target"}
        if payload.get("mode") == "ask_residents":
            target_errors = self._validate_runtime_confirmation_targets(
                target_recipients=list(payload.get("confirmation_target_recipients", [])),
                target_groups=list(payload.get("confirmation_target_groups", [])),
                use_default_route_targets=bool(
                    payload.get("confirmation_use_default_route_targets", True)
                ),
            )
            if target_errors:
                return target_errors
        return {}

    def _execution_policy_profile_from_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        mode = str(payload.get("mode") or "auto_apply")
        policy: dict[str, Any] = {"mode": mode}
        if mode == "ask_residents":
            policy["confirmation"] = {
                "target_recipients": list(payload.get("confirmation_target_recipients", [])),
                "target_groups": list(payload.get("confirmation_target_groups", [])),
                "use_default_route_targets": bool(
                    payload.get("confirmation_use_default_route_targets", True)
                ),
                "expires_in_minutes": int(payload.get("confirmation_expires_in_minutes") or 10),
                "on_timeout": str(payload.get("confirmation_on_timeout") or "skip"),
            }
            policy["promotion"] = {
                "enabled": bool(payload.get("promotion_enabled", True)),
                "target_recipients": list(payload.get("promotion_target_recipients", [])),
                "target_groups": list(payload.get("promotion_target_groups", [])),
                "min_samples": int(payload.get("promotion_min_samples") or 5),
                "min_approval_rate": float(payload.get("promotion_min_approval_rate") or 0.8),
                "min_distinct_days": int(payload.get("promotion_min_distinct_days") or 3),
                "reminder_interval_days": int(payload.get("promotion_reminder_interval_days") or 7),
            }
        return policy

    def _execution_policy_profile_defaults(
        self, profile_id: str, profile: dict[str, Any]
    ) -> dict[str, Any]:
        confirmation = profile.get("confirmation")
        confirmation = dict(confirmation) if isinstance(confirmation, dict) else {}
        promotion = profile.get("promotion")
        promotion = dict(promotion) if isinstance(promotion, dict) else {}
        return {
            "profile_id": profile_id,
            "mode": str(profile.get("mode") or "auto_apply"),
            "confirmation_target_recipients": ", ".join(
                _parse_multiline_items(confirmation.get("target_recipients"))
            ),
            "confirmation_target_groups": ", ".join(
                _parse_multiline_items(confirmation.get("target_groups"))
            ),
            "confirmation_use_default_route_targets": bool(
                confirmation.get("use_default_route_targets", True)
            ),
            "confirmation_expires_in_minutes": int(confirmation.get("expires_in_minutes") or 10),
            "confirmation_on_timeout": str(confirmation.get("on_timeout") or "skip"),
            "promotion_enabled": bool(promotion.get("enabled", True)),
            "promotion_target_recipients": ", ".join(
                _parse_multiline_items(promotion.get("target_recipients"))
            ),
            "promotion_target_groups": ", ".join(
                _parse_multiline_items(promotion.get("target_groups"))
            ),
            "promotion_min_samples": int(promotion.get("min_samples") or 5),
            "promotion_min_approval_rate": float(promotion.get("min_approval_rate") or 0.8),
            "promotion_min_distinct_days": int(promotion.get("min_distinct_days") or 3),
            "promotion_reminder_interval_days": int(promotion.get("reminder_interval_days") or 7),
        }

    def _execution_policy_profile_choice_map(
        self, profiles: dict[str, dict[str, Any]]
    ) -> dict[str, str]:
        return {
            f"{profile_id} ({str(profile.get('mode') or 'auto_apply')})": profile_id
            for profile_id, profile in sorted(profiles.items())
        }

    def _execution_policy_profiles_summary(self, profiles: dict[str, dict[str, Any]]) -> str:
        if not profiles:
            return "No execution policy profiles configured."
        return "\n".join(
            f"{profile_id}: {str(profile.get('mode') or 'auto_apply')}"
            for profile_id, profile in sorted(profiles.items())
        )

    def _execution_policy_profile_references(self, profile_id: str) -> list[str]:
        configured = self._reactions_config().get("configured")
        if not isinstance(configured, dict):
            return []
        return [
            f"reaction:{reaction_id}"
            for reaction_id, cfg in sorted(configured.items())
            if isinstance(cfg, dict) and str(cfg.get("execution_policy_ref") or "") == profile_id
        ]

    def _validate_runtime_confirmation_targets(
        self,
        *,
        target_recipients: list[str],
        target_groups: list[str],
        use_default_route_targets: bool,
    ) -> dict[str, str]:
        """Validate ask-residents routing can reach at least one actionable service."""
        recipients = self._notification_recipients()
        groups = self._notification_groups()
        if any(recipient_id not in recipients for recipient_id in target_recipients):
            return {"confirmation_target_recipients": "unknown_recipient"}
        if any(group_id not in groups for group_id in target_groups):
            return {"confirmation_target_groups": "unknown_target"}

        targets: list[str] = []
        seen_targets: set[str] = set()

        def add_target(target: str) -> None:
            normalized = str(target or "").strip()
            if not normalized or normalized in seen_targets:
                return
            seen_targets.add(normalized)
            targets.append(normalized)

        for recipient_id in target_recipients:
            add_target(recipient_id)
        for group_id in target_groups:
            add_target(group_id)
        if use_default_route_targets:
            for target in _parse_multiline_items(self._notifications_config().get("route_targets")):
                add_target(target)

        capabilities = self._notification_service_capabilities()
        actionable_routes = 0
        unresolved_default_target = False
        for target in targets:
            services: list[str] = []
            if target in recipients:
                services.extend(recipients.get(target, []))
            elif target in groups:
                for recipient_id in groups.get(target, []):
                    services.extend(recipients.get(recipient_id, []))
            else:
                unresolved_default_target = True
                continue
            for service in services:
                service_name = _normalize_notify_service_name(service)
                capability = capabilities.get(service_name, {})
                if bool(capability.get("supports_actions", False)):
                    actionable_routes += 1

        if unresolved_default_target:
            return {"base": "unknown_target"}
        if actionable_routes <= 0:
            return {"base": "no_actionable_route"}
        return {}


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
