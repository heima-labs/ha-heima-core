"""Options flow: discovery and installation validation steps."""

# mypy: disable-error-code=attr-defined

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from ..const import OPT_ACTIVITY_BINDINGS, OPT_DISCOVERY, OPT_ROOMS
from ..discovery import (
    DiscoveredBindingCandidate,
    DiscoveryReport,
    candidate_by_id,
    candidate_label,
    discover_binding_candidates,
)
from ..validation import ValidationReport, build_validation_report, validation_summary_text

if TYPE_CHECKING:
    from homeassistant.data_entry_flow import FlowResult

_DISCOVERY_ACTION_LABELS = {
    "en": {
        "accept_all": "Accept all",
        "accept_non_ambiguous": "Accept non-ambiguous",
        "accept_selected": "Accept selected",
        "reject_all": "Reject all",
    },
    "it": {
        "accept_all": "Accetta tutto",
        "accept_non_ambiguous": "Accetta non ambigue",
        "accept_selected": "Accetta selezionate",
        "reject_all": "Rifiuta tutto",
    },
}

_VALIDATION_ACTION_LABELS = {
    "en": {
        "back": "Back",
        "save": "Save",
    },
    "it": {
        "back": "Indietro",
        "save": "Salva",
    },
}

_DISCOVERY_EMPTY_SUMMARY = {
    "en": "No discovery candidates found.",
    "it": "Nessun candidato di discovery trovato.",
}


class _DiscoveryValidationStepsMixin:
    """Mixin for entity discovery and installation validation options steps."""

    async def async_step_discovery(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        report = self._discovery_report()
        choices = {
            candidate.candidate_id: candidate_label(candidate) for candidate in report.candidates
        }
        if user_input is None:
            action_labels = self._localized_labels(_DISCOVERY_ACTION_LABELS)
            schema = vol.Schema(
                {
                    vol.Required("action", default="accept_non_ambiguous"): vol.In(action_labels),
                    vol.Optional("accepted_candidates", default=[]): cv.multi_select(choices),
                }
            )
            return self.async_show_form(
                step_id="discovery",
                data_schema=schema,
                description_placeholders=self._discovery_placeholders(report),
            )

        action = str(user_input.get("action") or "").strip()
        accepted_ids: set[str] = set()
        if action == "accept_all":
            accepted_ids = {candidate.candidate_id for candidate in report.candidates}
        elif action == "accept_non_ambiguous":
            accepted_ids = {
                candidate.candidate_id for candidate in report.candidates if not candidate.ambiguous
            }
        elif action == "accept_selected":
            accepted_ids = set(self._normalize_multi_value(user_input.get("accepted_candidates")))
        elif action == "reject_all":
            accepted_ids = set()
        else:
            return self.async_show_form(
                step_id="discovery",
                data_schema=vol.Schema({vol.Required("action"): cv.string}),
                errors={"action": "invalid_option"},
                description_placeholders=self._discovery_placeholders(report),
            )

        accepted = [
            candidate
            for candidate_id in sorted(accepted_ids)
            if (candidate := candidate_by_id(report, candidate_id)) is not None
        ]
        self._apply_discovery_candidates(accepted)
        self._store_discovery_review(report, accepted)
        return await self.async_step_init()

    async def async_step_validation(self, user_input: dict[str, Any] | None = None) -> "FlowResult":
        report = await self._validation_report()
        if user_input is None:
            action_labels = self._localized_labels(_VALIDATION_ACTION_LABELS)
            return self.async_show_form(
                step_id="validation",
                data_schema=vol.Schema(
                    {vol.Required("action", default="back"): vol.In(action_labels)}
                ),
                description_placeholders=self._validation_placeholders(report),
            )
        action = str(user_input.get("action") or "back").strip()
        if action == "save":
            return await self.async_step_save()
        return await self.async_step_init()

    def _discovery_summary(self) -> str:
        report = self._discovery_report()
        if not report.candidates:
            return "0"
        grouped = report.as_dict()["by_category"]
        return ", ".join(f"{key} {value}" for key, value in sorted(grouped.items()))

    def _discovery_report(self) -> DiscoveryReport:
        try:
            entity_registry = er.async_get(self.hass)
            device_registry = dr.async_get(self.hass)
            area_registry = ar.async_get(self.hass)
        except Exception:
            return DiscoveryReport(candidates=())
        states = getattr(getattr(self, "hass", None), "states", None)
        async_all = getattr(states, "async_all", None)
        all_states = list(async_all()) if callable(async_all) else []
        return discover_binding_candidates(
            entity_entries=list(getattr(entity_registry, "entities", {}).values()),
            device_entries=dict(getattr(device_registry, "devices", {}) or {}),
            area_entries={
                str(getattr(area, "id", "") or ""): area
                for area in getattr(area_registry, "async_list_areas", lambda: [])()
                if str(getattr(area, "id", "") or "")
            },
            state_by_entity={
                str(getattr(state, "entity_id", "") or ""): state
                for state in all_states
                if str(getattr(state, "entity_id", "") or "")
            },
        )

    def _discovery_placeholders(self, report: DiscoveryReport) -> dict[str, str]:
        if not report.candidates:
            return {
                "summary": _DISCOVERY_EMPTY_SUMMARY[self._flow_language()],
                "suggestions": "",
            }
        grouped = report.as_dict()["by_category"]
        summary = ", ".join(f"{key}: {value}" for key, value in sorted(grouped.items()))
        suggestions = "\n".join(candidate_label(candidate) for candidate in report.candidates)
        return {"summary": summary, "suggestions": suggestions}

    def _apply_discovery_candidates(self, candidates: list[DiscoveredBindingCandidate]) -> None:
        if not candidates:
            return
        rooms = self._rooms()
        room_updates = [dict(room) for room in rooms]
        rooms_changed = False
        activity_bindings = dict(self.options.get(OPT_ACTIVITY_BINDINGS, {}) or {})
        activity_changed = False

        for candidate in candidates:
            if candidate.suggested_binding == "room_occupancy_source" and candidate.area_id:
                for room in room_updates:
                    if str(room.get("area_id") or "") != candidate.area_id:
                        continue
                    sources = list(room.get("occupancy_sources") or room.get("sources") or [])
                    if candidate.entity_id not in sources:
                        sources.append(candidate.entity_id)
                        room["occupancy_sources"] = sources
                        rooms_changed = True
                    break
            elif candidate.suggested_binding == "activity_shower_humidity":
                shower = dict(activity_bindings.get("shower_running", {}) or {})
                if not shower.get("entity_id") and not shower.get("bathroom_humidity_entity"):
                    shower["bathroom_humidity_entity"] = candidate.entity_id
                    activity_bindings["shower_running"] = shower
                    activity_changed = True

        if rooms_changed:
            self._store_list(OPT_ROOMS, room_updates)
        if activity_changed:
            self._update_options({OPT_ACTIVITY_BINDINGS: activity_bindings})

    def _store_discovery_review(
        self,
        report: DiscoveryReport,
        accepted: list[DiscoveredBindingCandidate],
    ) -> None:
        accepted_ids = {candidate.candidate_id for candidate in accepted}
        payload = {
            "last_reviewed_candidates": [candidate.as_dict() for candidate in report.candidates],
            "accepted_candidate_ids": sorted(accepted_ids),
            "rejected_candidate_ids": sorted(
                candidate.candidate_id
                for candidate in report.candidates
                if candidate.candidate_id not in accepted_ids
            ),
        }
        self._update_options({OPT_DISCOVERY: payload})

    async def _validation_report(self) -> ValidationReport:
        coordinator = self._coordinator()
        if coordinator is not None and hasattr(coordinator, "async_validate_config"):
            return await coordinator.async_validate_config()
        return self._local_validation_report()

    def _validation_summary_sync(self) -> str:
        return self._local_validation_report().summary

    def _validation_placeholders(self, report: ValidationReport) -> dict[str, str]:
        return {
            "summary": report.summary,
            "details": validation_summary_text(report),
        }

    def _local_validation_report(self) -> ValidationReport:
        return build_validation_report(
            options=self._entry_options_snapshot(),
            snapshot_count=0,
            approval_count=0,
            pending_proposal_count=0,
        )
