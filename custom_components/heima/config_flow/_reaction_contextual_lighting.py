"""Shared contextual lighting policy form helpers."""

# mypy: ignore-errors

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from ._common import _multiline_text_selector

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult


class _ContextualLightingPolicyFormMixin:
    """Mixin for contextual lighting policy form schemas and preset contracts."""

    @staticmethod
    def _contextual_lighting_preset_options() -> dict[str, str]:
        return {
            preset_id: payload["label"]
            for preset_id, payload in _ContextualLightingPolicyFormMixin._contextual_lighting_preset_catalog().items()
        }

    @staticmethod
    def _contextual_lighting_preset_label(preset: str) -> str:
        catalog = _ContextualLightingPolicyFormMixin._contextual_lighting_preset_catalog()
        payload = catalog.get(preset) or catalog["all_day_adaptive"]
        return str(payload["label"])

    @staticmethod
    def _contextual_lighting_preset_description(preset: str) -> str:
        catalog = _ContextualLightingPolicyFormMixin._contextual_lighting_preset_catalog()
        payload = catalog.get(preset) or catalog["all_day_adaptive"]
        return str(payload["description"])

    @staticmethod
    def _contextual_lighting_preset_previews() -> str:
        catalog = _ContextualLightingPolicyFormMixin._contextual_lighting_preset_catalog()
        return "\n".join(
            f"- {payload['label']}: {payload['description']}" for payload in catalog.values()
        )

    def _contextual_lighting_policy_editor_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        include_enabled: bool,
        include_delete: bool,
    ) -> vol.Schema:
        defaults = defaults or {}
        preset_options = self._contextual_lighting_preset_options()
        if str(defaults.get("preset") or "").strip() == "custom":
            preset_options = {**preset_options, "custom": "Custom JSON"}
        schema_fields: dict[Any, Any] = {
            vol.Required(
                "preset",
                default=defaults.get("preset", "all_day_adaptive"),
            ): vol.In(preset_options),
            vol.Required(
                "config_json",
                default=defaults.get("config_json", ""),
            ): _multiline_text_selector(),
        }
        if include_enabled:
            schema_fields[vol.Optional("enabled", default=True)] = bool
        if include_delete:
            schema_fields[vol.Optional("delete_reaction", default=False)] = bool
        return self._with_suggested(vol.Schema(schema_fields), defaults)

    def _show_contextual_lighting_policy_editor(
        self,
        *,
        step_id: str,
        defaults: dict[str, Any],
        errors: dict[str, str] | None = None,
        template_title: str = "",
        template_description: str = "",
        reaction_description: str = "",
        room_id: str = "",
        include_enabled: bool,
        include_delete: bool,
    ) -> "FlowResult":
        preset = str(defaults.get("preset") or "all_day_adaptive")
        return self.async_show_form(
            step_id=step_id,
            data_schema=self._contextual_lighting_policy_editor_schema(
                defaults,
                include_enabled=include_enabled,
                include_delete=include_delete,
            ),
            errors=errors,
            description_placeholders={
                "template_title": template_title,
                "template_description": template_description,
                "reaction_description": reaction_description,
                "room_id": room_id,
                "preset_label": self._contextual_lighting_preset_label(preset)
                if preset != "custom"
                else "Custom JSON",
                "preset_description": self._contextual_lighting_preset_description(preset)
                if preset != "custom"
                else "Editing a custom contract that no longer matches a built-in preset.",
                "policy_summary": self._contextual_lighting_policy_summary(
                    str(defaults.get("config_json") or "")
                ),
            },
        )

    @staticmethod
    def _contextual_lighting_policy_json(*, preset: str, light_entities: list[str]) -> str:
        contract = _ContextualLightingPolicyFormMixin._contextual_lighting_contract_from_preset(
            preset=preset,
            light_entities=light_entities,
        )
        return json.dumps(contract, indent=2, sort_keys=True)

    @staticmethod
    def _contextual_lighting_contract_from_preset(
        *, preset: str, light_entities: list[str]
    ) -> dict[str, Any]:
        entities = [
            str(entity_id).strip() for entity_id in light_entities if str(entity_id).strip()
        ]

        def _profile(brightness: int, color_temp_kelvin: int) -> dict[str, Any]:
            return {
                "entity_steps": [
                    {
                        "entity_id": entity_id,
                        "action": "on",
                        "brightness": brightness,
                        "color_temp_kelvin": color_temp_kelvin,
                    }
                    for entity_id in entities
                ]
            }

        catalog = _ContextualLightingPolicyFormMixin._contextual_lighting_preset_catalog()
        payload = catalog.get(preset) or catalog["all_day_adaptive"]
        template = dict(payload.get("contract") or {})
        profiles = dict(template.get("profiles") or {})
        materialized_profiles: dict[str, Any] = {}
        for profile_name, profile_cfg in profiles.items():
            step_cfg = dict(profile_cfg or {})
            brightness = int(step_cfg.get("brightness", 120))
            color_temp_kelvin = int(step_cfg.get("color_temp_kelvin", 3200))
            materialized_profiles[str(profile_name)] = _profile(brightness, color_temp_kelvin)
        return {
            "profiles": materialized_profiles,
            "rules": list(template.get("rules") or []),
            "default_profile": str(template.get("default_profile") or "").strip(),
            "followup_window_s": int(template.get("followup_window_s", 900)),
        }

    @staticmethod
    def _contextual_lighting_policy_summary(config_json: str) -> str:
        try:
            payload = json.loads(config_json)
        except (TypeError, ValueError, json.JSONDecodeError):
            return "—"
        if not isinstance(payload, dict):
            return "—"
        profiles = dict(payload.get("profiles") or {})
        rules = list(payload.get("rules") or [])
        default_profile = str(payload.get("default_profile") or "").strip()
        profile_names = ", ".join(sorted(profiles)[:4]) or "-"
        rule_summaries: list[str] = []
        for index, raw_rule in enumerate(rules[:3], start=1):
            if not isinstance(raw_rule, dict):
                continue
            profile = str(raw_rule.get("profile") or "").strip() or "-"
            bits: list[str] = []
            states = [
                str(v).strip() for v in list(raw_rule.get("house_state_in") or []) if str(v).strip()
            ]
            if states:
                bits.append(f"house={','.join(states)}")
            reasons = [
                str(v).strip()
                for v in list(raw_rule.get("occupancy_reason_in") or [])
                if str(v).strip()
            ]
            if reasons:
                bits.append(f"reason={','.join(reasons)}")
            time_window = raw_rule.get("time_window")
            if isinstance(time_window, dict):
                start = str(time_window.get("start") or "").strip()
                end = str(time_window.get("end") or "").strip()
                if start and end:
                    bits.append(f"time={start}-{end}")
            suffix = f" ({'; '.join(bits)})" if bits else ""
            rule_summaries.append(f"{index}. {profile}{suffix}")
        ambient_modulation = dict(payload.get("ambient_modulation") or {})
        ambient_signal = str(ambient_modulation.get("source_signal_name") or "").strip()
        ambient_line = f"\nambient={ambient_signal}" if ambient_signal else ""
        rules_block = "\n".join(rule_summaries) if rule_summaries else "—"
        return (
            f"profiles={len(profiles)} [{profile_names}]"
            f"\nrules={len(rules)}"
            f"\ndefault={default_profile or '-'}"
            f"\n{rules_block}"
            f"{ambient_line}"
        )

    @staticmethod
    def _contextual_lighting_policy_for_form(cfg: dict[str, Any]) -> str:
        payload = {
            "profiles": dict(cfg.get("profiles") or {}),
            "rules": list(cfg.get("rules") or []),
            "default_profile": str(cfg.get("default_profile") or "").strip(),
            "ambient_modulation": dict(cfg.get("ambient_modulation") or {}),
            "followup_window_s": int(cfg.get("followup_window_s", 900)),
        }
        return json.dumps(payload, indent=2, sort_keys=True)

    @staticmethod
    def _contextual_lighting_light_entities_from_cfg(cfg: dict[str, Any]) -> list[str]:
        entity_ids: list[str] = []
        seen: set[str] = set()
        for profile in dict(cfg.get("profiles") or {}).values():
            if not isinstance(profile, dict):
                continue
            for raw_step in list(profile.get("entity_steps") or []):
                if not isinstance(raw_step, dict):
                    continue
                entity_id = str(raw_step.get("entity_id") or "").strip()
                if not entity_id or entity_id in seen:
                    continue
                seen.add(entity_id)
                entity_ids.append(entity_id)
        return entity_ids

    @staticmethod
    def _contextual_lighting_preset_from_cfg(cfg: dict[str, Any]) -> str:
        light_entities = (
            _ContextualLightingPolicyFormMixin._contextual_lighting_light_entities_from_cfg(cfg)
        )
        current = {
            "profiles": dict(cfg.get("profiles") or {}),
            "rules": list(cfg.get("rules") or []),
            "default_profile": str(cfg.get("default_profile") or "").strip(),
            "followup_window_s": int(cfg.get("followup_window_s", 900)),
        }
        for preset in _ContextualLightingPolicyFormMixin._contextual_lighting_preset_options():
            if (
                _ContextualLightingPolicyFormMixin._contextual_lighting_contract_from_preset(
                    preset=preset,
                    light_entities=light_entities,
                )
                == current
            ):
                return preset
        return "custom"

    def _normalize_contextual_policy_editor_submission(
        self,
        *,
        user_input: dict[str, Any],
        defaults: dict[str, Any],
        light_entities: list[str],
        allow_custom_preset: bool = False,
    ) -> tuple[str, str]:
        selected_preset = str(user_input.get("preset") or defaults.get("preset") or "").strip()
        valid_presets = set(self._contextual_lighting_preset_options())
        if allow_custom_preset:
            valid_presets.add("custom")
        if selected_preset not in valid_presets:
            selected_preset = str(defaults.get("preset") or "all_day_adaptive")
        submitted_json = str(user_input.get("config_json") or "").strip()
        default_json = str(defaults.get("config_json") or "").strip()
        default_preset = str(defaults.get("preset") or "").strip()
        if (
            selected_preset != "custom"
            and selected_preset != default_preset
            and submitted_json == default_json
        ):
            submitted_json = self._contextual_lighting_policy_json(
                preset=selected_preset,
                light_entities=light_entities,
            )
        return selected_preset, submitted_json

    @staticmethod
    def _contextual_lighting_preset_catalog() -> dict[str, dict[str, Any]]:
        return {
            "daytime_focus": {
                "label": "Daytime focus",
                "description": "Cooler, brighter light during the day. Soft fallback after hours.",
                "contract": {
                    "profiles": {
                        "daytime_focus": {"brightness": 190, "color_temp_kelvin": 4300},
                        "after_hours_soft": {"brightness": 110, "color_temp_kelvin": 3000},
                        "night_navigation": {"brightness": 25, "color_temp_kelvin": 2200},
                    },
                    "rules": [
                        {
                            "profile": "daytime_focus",
                            "time_window": {"start": "08:00", "end": "18:30"},
                        },
                        {
                            "profile": "after_hours_soft",
                            "time_window": {"start": "18:30", "end": "23:30"},
                        },
                        {
                            "profile": "night_navigation",
                            "time_window": {"start": "23:30", "end": "06:30"},
                        },
                    ],
                    "default_profile": "after_hours_soft",
                    "followup_window_s": 900,
                },
            },
            "evening_warmth": {
                "label": "Evening warmth",
                "description": "Neutral daytime fallback with warmer evening emphasis.",
                "contract": {
                    "profiles": {
                        "daytime_neutral": {"brightness": 130, "color_temp_kelvin": 3400},
                        "evening_warmth": {"brightness": 95, "color_temp_kelvin": 2600},
                        "night_navigation": {"brightness": 20, "color_temp_kelvin": 2200},
                    },
                    "rules": [
                        {
                            "profile": "daytime_neutral",
                            "time_window": {"start": "08:00", "end": "18:30"},
                        },
                        {
                            "profile": "evening_warmth",
                            "time_window": {"start": "18:30", "end": "23:30"},
                        },
                        {
                            "profile": "night_navigation",
                            "time_window": {"start": "23:30", "end": "06:30"},
                        },
                    ],
                    "default_profile": "daytime_neutral",
                    "followup_window_s": 900,
                },
            },
            "night_navigation": {
                "label": "Night navigation",
                "description": "Minimal warm light by night, restrained brightness elsewhere.",
                "contract": {
                    "profiles": {
                        "daytime_low": {"brightness": 90, "color_temp_kelvin": 3200},
                        "night_navigation": {"brightness": 18, "color_temp_kelvin": 2200},
                    },
                    "rules": [
                        {
                            "profile": "night_navigation",
                            "time_window": {"start": "22:30", "end": "06:30"},
                        }
                    ],
                    "default_profile": "daytime_low",
                    "followup_window_s": 900,
                },
            },
            "all_day_adaptive": {
                "label": "All-day adaptive",
                "description": "Working daylight, softer daytime fallback, warm evening, dim night.",
                "contract": {
                    "profiles": {
                        "workday_focus": {"brightness": 180, "color_temp_kelvin": 4300},
                        "day_generic": {"brightness": 140, "color_temp_kelvin": 3600},
                        "evening_relax": {"brightness": 100, "color_temp_kelvin": 2700},
                        "night_navigation": {"brightness": 25, "color_temp_kelvin": 2200},
                    },
                    "rules": [
                        {
                            "profile": "workday_focus",
                            "house_state_in": ["working"],
                            "time_window": {"start": "08:00", "end": "18:30"},
                        },
                        {
                            "profile": "day_generic",
                            "house_state_in": ["home", "relax"],
                            "time_window": {"start": "08:00", "end": "18:30"},
                        },
                        {
                            "profile": "evening_relax",
                            "time_window": {"start": "18:30", "end": "23:30"},
                        },
                        {
                            "profile": "night_navigation",
                            "time_window": {"start": "23:30", "end": "06:30"},
                        },
                    ],
                    "default_profile": "day_generic",
                    "followup_window_s": 900,
                },
            },
        }
