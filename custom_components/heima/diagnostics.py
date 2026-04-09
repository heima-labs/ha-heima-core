"""Diagnostics support for Heima."""

# mypy: disable-error-code=dict-item

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import DIAGNOSTICS_REDACT_KEYS, DOMAIN
from .room_inventory import build_room_inventory_summary
from .runtime.analyzers import builtin_learning_pattern_plugin_descriptors
from .runtime.reactions import create_builtin_reaction_plugin_registry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = data.get("coordinator")

    learning_plugins = _learning_plugin_diagnostics(coordinator)
    proposal_diagnostics = coordinator._proposal_engine.diagnostics() if coordinator else {}
    proposal_diagnostics = _enrich_proposals_with_followups(
        proposal_diagnostics,
        entry=entry,
    )

    payload = {
        "entry": {
            "title": entry.title,
            "version": entry.version,
            "minor_version": getattr(entry, "minor_version", None),
            "options": dict(entry.options),
        },
        "runtime": {
            "data": getattr(coordinator, "data", None),
            "engine": coordinator.engine.diagnostics() if coordinator else {},
            "scheduler": coordinator.scheduler.diagnostics() if coordinator else {},
            "event_store": coordinator._event_store.diagnostics() if coordinator else {},
            "proposals": proposal_diagnostics,
            "plugins": {
                "learning_pattern_plugins": learning_plugins,
                "learning_summary": _learning_summary_diagnostics(
                    learning_plugins,
                    proposal_diagnostics,
                ),
                "lighting_summary": _lighting_summary_diagnostics(
                    proposal_diagnostics,
                    coordinator,
                ),
                "calendar_summary": _calendar_summary_diagnostics(coordinator),
                "house_state_summary": _house_state_summary_diagnostics(coordinator),
                "security_camera_evidence_summary": _security_camera_evidence_summary_diagnostics(
                    coordinator
                ),
                "ha_backed_reconciliation_summary": _ha_backed_reconciliation_summary_diagnostics(
                    coordinator
                ),
                "ha_backed_room_inventory_summary": _ha_backed_room_inventory_summary_diagnostics(
                    hass,
                    entry,
                ),
                "security_presence_summary": _security_presence_summary_diagnostics(coordinator),
                "composite_summary": _composite_summary_diagnostics(
                    proposal_diagnostics,
                    coordinator,
                ),
                "configured_reaction_summary": _configured_reaction_summary_diagnostics(
                    coordinator
                ),
                "reaction_plugins": _reaction_plugin_diagnostics(coordinator),
            },
        },
    }

    return async_redact_data(payload, DIAGNOSTICS_REDACT_KEYS)


def _learning_plugin_diagnostics(coordinator: Any) -> list[dict[str, Any]]:
    if coordinator:
        registry = getattr(coordinator, "learning_plugin_registry", None)
        if registry is not None and hasattr(registry, "diagnostics"):
            return list(registry.diagnostics())
    return [
        {
            "plugin_id": descriptor.plugin_id,
            "analyzer_id": descriptor.analyzer_id,
            "plugin_family": descriptor.plugin_family,
            "proposal_types": list(descriptor.proposal_types),
            "reaction_targets": list(descriptor.reaction_targets),
            "supports_admin_authored": descriptor.supports_admin_authored,
            "admin_authored_templates": [
                {
                    "template_id": item.template_id,
                    "reaction_type": item.reaction_type,
                    "title": item.title,
                    "description": item.description,
                    "config_schema_id": item.config_schema_id,
                    "implemented": item.implemented,
                    "flow_step_id": item.flow_step_id,
                }
                for item in descriptor.admin_authored_templates
            ],
            "enabled": True,
        }
        for descriptor in builtin_learning_pattern_plugin_descriptors()
    ]


def _reaction_plugin_diagnostics(coordinator: Any) -> list[dict[str, Any]]:
    if coordinator:
        engine = getattr(coordinator, "engine", None)
        registry = getattr(engine, "_reaction_plugin_registry", None)
        if registry is not None and hasattr(registry, "diagnostics"):
            return list(registry.diagnostics())
    return create_builtin_reaction_plugin_registry().diagnostics()


def _ha_backed_reconciliation_summary_diagnostics(coordinator: Any) -> dict[str, Any]:
    if coordinator is None:
        return {}
    summary = getattr(coordinator, "ha_backed_reconciliation_summary", {})
    return dict(summary or {})


def _ha_backed_room_inventory_summary_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    try:
        rooms = list(dict(entry.options).get("rooms") or [])
        return build_room_inventory_summary(hass, rooms)
    except Exception:
        return {}


def _learning_summary_diagnostics(
    learning_plugins: list[dict[str, Any]],
    proposal_diagnostics: dict[str, Any],
) -> dict[str, Any]:
    proposals = list(proposal_diagnostics.get("proposals") or [])
    by_type: dict[str, list[dict[str, Any]]] = {}
    for proposal in proposals:
        if not isinstance(proposal, dict):
            continue
        proposal_type = str(proposal.get("type") or "").strip()
        if not proposal_type:
            continue
        by_type.setdefault(proposal_type, []).append(proposal)

    family_summary: dict[str, dict[str, Any]] = {}
    plugin_summary: dict[str, dict[str, Any]] = {}
    unclaimed_types: set[str] = set(by_type)

    for plugin in learning_plugins:
        if not isinstance(plugin, dict):
            continue
        plugin_id = str(plugin.get("plugin_id") or "")
        family = str(plugin.get("plugin_family") or "unknown")
        proposal_types = [str(item) for item in plugin.get("proposal_types") or [] if str(item)]
        plugin_proposals = [
            proposal
            for proposal_type in proposal_types
            for proposal in by_type.get(proposal_type, [])
        ]
        for proposal_type in proposal_types:
            unclaimed_types.discard(proposal_type)

        plugin_stats = _proposal_status_counts(plugin_proposals)
        plugin_stats.update(
            {
                "plugin_family": family,
                "proposal_types": proposal_types,
                "supports_admin_authored": bool(plugin.get("supports_admin_authored") is True),
                "admin_authored_templates": _template_ids(
                    plugin.get("admin_authored_templates") or []
                ),
                "implemented_admin_authored_templates": _template_ids(
                    plugin.get("admin_authored_templates") or [],
                    implemented_only=True,
                ),
                "unimplemented_admin_authored_templates": _template_ids(
                    plugin.get("admin_authored_templates") or [],
                    implemented_only=False,
                    invert_implemented=True,
                ),
                "top_examples": _top_proposal_examples(plugin_proposals),
            }
        )
        plugin_summary[plugin_id] = plugin_stats

        family_entry = family_summary.setdefault(
            family,
            {
                "plugins": [],
                "proposal_types": set(),
                "admin_authored_templates": set(),
                "implemented_admin_authored_templates": set(),
                "unimplemented_admin_authored_templates": set(),
                "admin_authorable": False,
                "total": 0,
                "pending": 0,
                "accepted": 0,
                "rejected": 0,
                "stale_pending": 0,
                "top_examples": [],
            },
        )
        family_entry["plugins"].append(plugin_id)
        family_entry["proposal_types"].update(proposal_types)
        family_entry["admin_authorable"] = family_entry["admin_authorable"] or bool(
            plugin.get("supports_admin_authored") is True
        )
        family_entry["admin_authored_templates"].update(
            plugin_summary[plugin_id]["admin_authored_templates"]
        )
        family_entry["implemented_admin_authored_templates"].update(
            plugin_summary[plugin_id]["implemented_admin_authored_templates"]
        )
        family_entry["unimplemented_admin_authored_templates"].update(
            plugin_summary[plugin_id]["unimplemented_admin_authored_templates"]
        )
        family_entry["total"] += plugin_stats["total"]
        family_entry["pending"] += plugin_stats["pending"]
        family_entry["accepted"] += plugin_stats["accepted"]
        family_entry["rejected"] += plugin_stats["rejected"]
        family_entry["stale_pending"] += plugin_stats["stale_pending"]
        family_entry["top_examples"].extend(plugin_stats["top_examples"])

    for family, stats in family_summary.items():
        stats["plugins"] = sorted(stats["plugins"])
        stats["proposal_types"] = sorted(stats["proposal_types"])
        stats["admin_authored_templates"] = sorted(stats["admin_authored_templates"])
        stats["implemented_admin_authored_templates"] = sorted(
            stats["implemented_admin_authored_templates"]
        )
        stats["unimplemented_admin_authored_templates"] = sorted(
            stats["unimplemented_admin_authored_templates"]
        )
        stats["top_examples"] = stats["top_examples"][:3]

    enabled_families = sorted(
        family
        for family, stats in family_summary.items()
        if any(
            plugin.get("enabled") is True
            for plugin in learning_plugins
            if isinstance(plugin, dict) and str(plugin.get("plugin_family") or "") == family
        )
    )
    disabled_families = sorted(
        {
            str(plugin.get("plugin_family") or "unknown")
            for plugin in learning_plugins
            if isinstance(plugin, dict) and plugin.get("enabled") is False
        }
    )

    return {
        "plugin_count": len(plugin_summary),
        "family_count": len(family_summary),
        "proposal_total": int(proposal_diagnostics.get("total") or 0),
        "pending_total": int(proposal_diagnostics.get("pending") or 0),
        "pending_stale_total": int(proposal_diagnostics.get("pending_stale") or 0),
        "config_source": "learning.enabled_plugin_families",
        "enabled_plugin_families": enabled_families,
        "disabled_plugin_families": disabled_families,
        "families": family_summary,
        "plugins": plugin_summary,
        "unclaimed_proposal_types": sorted(unclaimed_types),
    }


def _enrich_proposals_with_followups(
    proposal_diagnostics: dict[str, Any],
    *,
    entry: ConfigEntry,
) -> dict[str, Any]:
    if not isinstance(proposal_diagnostics, dict):
        return {}
    proposals = proposal_diagnostics.get("proposals")
    if not isinstance(proposals, list):
        return proposal_diagnostics
    configured = (
        dict(dict(entry.options).get("reactions", {})).get("configured", {})
        if isinstance(dict(entry.options).get("reactions", {}), dict)
        else {}
    )
    if not isinstance(configured, dict) or not configured:
        return proposal_diagnostics

    configured_by_identity: dict[str, tuple[str, dict[str, Any]]] = {}
    configured_by_lighting_slot: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for reaction_id, cfg in configured.items():
        if not isinstance(cfg, dict):
            continue
        identity_key = str(cfg.get("source_proposal_identity_key") or "").strip()
        if identity_key:
            configured_by_identity.setdefault(identity_key, (str(reaction_id), dict(cfg)))
            slot_key = _lighting_slot_key_from_identity(identity_key)
            if slot_key:
                configured_by_lighting_slot.setdefault(slot_key, []).append(
                    (str(reaction_id), dict(cfg))
                )

    if not configured_by_identity and not configured_by_lighting_slot:
        return proposal_diagnostics

    enriched: list[dict[str, Any]] = []
    for proposal in proposals:
        if not isinstance(proposal, dict):
            enriched.append(proposal)
            continue
        item = dict(proposal)
        identity_key = str(item.get("identity_key") or "").strip()
        if not identity_key:
            enriched.append(item)
            continue
        target = configured_by_identity.get(identity_key)
        if target is None:
            slot_key = _lighting_slot_key_from_identity(identity_key)
            if slot_key:
                slot_targets = configured_by_lighting_slot.get(slot_key) or []
                if len(slot_targets) == 1:
                    target = slot_targets[0]
        if target is None:
            enriched.append(item)
            continue
        reaction_id, cfg = target
        if str(item.get("followup_kind") or "discovery") == "discovery":
            item["followup_kind"] = "tuning_suggestion"
        if not str(item.get("target_reaction_id") or "").strip():
            item["target_reaction_id"] = reaction_id
        if not str(item.get("target_reaction_class") or "").strip():
            item["target_reaction_class"] = str(cfg.get("reaction_class") or "")
        if not str(item.get("target_reaction_origin") or "").strip():
            item["target_reaction_origin"] = str(cfg.get("origin") or "")
        if not str(item.get("target_template_id") or "").strip():
            item["target_template_id"] = str(cfg.get("source_template_id") or "")
        enriched.append(item)

    updated = dict(proposal_diagnostics)
    updated["proposals"] = enriched
    updated["tuning_pending"] = sum(
        1
        for proposal in enriched
        if isinstance(proposal, dict)
        and str(proposal.get("status") or "") == "pending"
        and str(proposal.get("followup_kind") or "") == "tuning_suggestion"
    )
    return updated


def _configured_reaction_summary_diagnostics(coordinator: Any) -> dict[str, Any]:
    if coordinator is None:
        return {}
    engine = getattr(coordinator, "engine", None)
    if engine is None:
        return {}
    reactions = _reaction_sensor_payload(getattr(engine, "_state", None))  # noqa: SLF001
    if not reactions:
        return {
            "total": 0,
            "by_origin": {},
            "by_author_kind": {},
            "by_template_id": {},
            "reaction_ids": [],
        }

    by_origin: dict[str, int] = {}
    by_author_kind: dict[str, int] = {}
    by_template_id: dict[str, int] = {}
    by_identity_key: dict[str, list[str]] = {}
    by_lighting_slot: dict[str, list[str]] = {}
    reaction_ids: list[str] = []
    for reaction_id, raw in reactions.items():
        if not isinstance(raw, dict):
            continue
        reaction_ids.append(str(reaction_id))
        origin = str(raw.get("origin") or "unspecified")
        by_origin[origin] = by_origin.get(origin, 0) + 1
        author_kind = str(raw.get("author_kind") or "unspecified")
        by_author_kind[author_kind] = by_author_kind.get(author_kind, 0) + 1
        template_id = str(raw.get("source_template_id") or "unspecified")
        by_template_id[template_id] = by_template_id.get(template_id, 0) + 1
        identity_key = str(raw.get("source_proposal_identity_key") or "").strip()
        if identity_key:
            by_identity_key.setdefault(identity_key, []).append(str(reaction_id))
            slot_key = _lighting_slot_key_from_identity(identity_key)
            if slot_key:
                by_lighting_slot.setdefault(slot_key, []).append(str(reaction_id))

    identity_collisions = {
        key: sorted(ids) for key, ids in sorted(by_identity_key.items()) if len(ids) > 1
    }
    lighting_slot_collisions = {
        key: sorted(ids) for key, ids in sorted(by_lighting_slot.items()) if len(ids) > 1
    }

    return {
        "total": len(reaction_ids),
        "by_origin": dict(sorted(by_origin.items())),
        "by_author_kind": dict(sorted(by_author_kind.items())),
        "by_template_id": dict(sorted(by_template_id.items())),
        "identity_collisions": identity_collisions,
        "lighting_slot_collisions": lighting_slot_collisions,
        "reaction_ids": sorted(reaction_ids),
    }


def _lighting_summary_diagnostics(
    proposal_diagnostics: dict[str, Any],
    coordinator: Any,
) -> dict[str, Any]:
    proposals = list(proposal_diagnostics.get("proposals") or [])
    lighting_pending = [
        dict(item)
        for item in proposals
        if isinstance(item, dict)
        and str(item.get("type") or "") == "lighting_scene_schedule"
        and str(item.get("status") or "") == "pending"
    ]

    pending_by_room: dict[str, int] = {}
    pending_tuning_total = 0
    pending_discovery_total = 0
    pending_tuning_examples: list[dict[str, Any]] = []
    pending_discovery_examples: list[dict[str, Any]] = []
    for proposal in lighting_pending:
        config_summary = _safe_dict(proposal.get("config_summary"))
        room_id = str(config_summary.get("room_id") or "").strip()
        if room_id:
            pending_by_room[room_id] = pending_by_room.get(room_id, 0) + 1
        example = {
            "id": proposal.get("id"),
            "label": str(proposal.get("description") or "").strip(),
            "room_id": room_id,
            "slot_key": _lighting_slot_key_from_identity(
                str(proposal.get("identity_key") or "").strip()
            ),
            "confidence": proposal.get("confidence"),
        }
        if str(proposal.get("followup_kind") or "") == "tuning_suggestion":
            pending_tuning_total += 1
            if len(pending_tuning_examples) < 3:
                pending_tuning_examples.append(example)
        else:
            pending_discovery_total += 1
            if len(pending_discovery_examples) < 3:
                pending_discovery_examples.append(example)

    active = _active_reaction_items(coordinator)
    configured_by_room: dict[str, int] = {}
    configured_by_slot: dict[str, int] = {}
    configured_total = 0
    for _reaction_id, cfg in active:
        reaction_type = str(cfg.get("reaction_type") or "").strip()
        reaction_class = str(cfg.get("reaction_class") or "").strip()
        identity_key = str(cfg.get("source_proposal_identity_key") or "").strip()
        is_lighting = (
            reaction_type == "lighting_scene_schedule"
            or reaction_class == "LightingScheduleReaction"
            or identity_key.startswith("lighting_scene_schedule|")
        )
        if not is_lighting:
            continue
        configured_total += 1
        room_id = str(cfg.get("room_id") or "").strip()
        if not room_id and identity_key.startswith("lighting_scene_schedule|"):
            room_id = _lighting_room_from_identity(identity_key)
        if room_id:
            configured_by_room[room_id] = configured_by_room.get(room_id, 0) + 1
        slot_key = _lighting_followup_slot_key(cfg)
        if not slot_key and identity_key:
            slot_key = _lighting_slot_key_from_identity(identity_key)
        if slot_key:
            configured_by_slot[slot_key] = configured_by_slot.get(slot_key, 0) + 1

    configured_summary = _configured_reaction_summary_diagnostics(coordinator)

    return {
        "configured_total": configured_total,
        "configured_by_room": dict(sorted(configured_by_room.items())),
        "configured_by_slot": dict(sorted(configured_by_slot.items())),
        "pending_total": len(lighting_pending),
        "pending_tuning_total": pending_tuning_total,
        "pending_discovery_total": pending_discovery_total,
        "pending_by_room": dict(sorted(pending_by_room.items())),
        "pending_tuning_examples": pending_tuning_examples,
        "pending_discovery_examples": pending_discovery_examples,
        "slot_collisions": dict(configured_summary.get("lighting_slot_collisions") or {}),
    }


def _calendar_summary_diagnostics(coordinator: Any) -> dict[str, Any]:
    if coordinator is None:
        return {}
    engine = getattr(coordinator, "engine", None)
    if engine is None:
        return {}

    engine_diag = engine.diagnostics() if hasattr(engine, "diagnostics") else {}
    calendar_diag = dict(engine_diag.get("calendar") or {})
    state = getattr(engine, "_state", None)
    calendar_result = getattr(state, "calendar_result", None) if state is not None else None

    configured_entities: list[str] = []
    options = getattr(getattr(coordinator, "_entry", None), "options", None)
    if isinstance(options, dict):
        calendar_cfg = dict(options.get("calendar", {}) or {})
        configured_entities = [
            str(item).strip()
            for item in list(calendar_cfg.get("calendar_entities") or [])
            if str(item).strip()
        ]

    cache_ts = calendar_diag.get("cache_ts")
    cached_events_count = int(calendar_diag.get("cached_events_count") or 0)
    current_events_count = 0
    upcoming_events_count = cached_events_count
    is_vacation_active = False
    is_wfh_today = False
    is_office_today = False
    next_vacation: dict[str, Any] | None = None

    if calendar_result is not None:
        current_events = list(getattr(calendar_result, "current_events", []) or [])
        upcoming_events = list(getattr(calendar_result, "upcoming_events", []) or [])
        current_events_count = len(current_events)
        upcoming_events_count = len(upcoming_events)
        is_vacation_active = bool(getattr(calendar_result, "is_vacation_active", False))
        is_wfh_today = bool(getattr(calendar_result, "is_wfh_today", False))
        is_office_today = bool(getattr(calendar_result, "is_office_today", False))
        next_raw = getattr(calendar_result, "next_vacation", None)
        if next_raw is not None:
            next_vacation = {
                "summary": str(getattr(next_raw, "summary", "") or "").strip(),
                "start": getattr(getattr(next_raw, "start", None), "isoformat", lambda: None)(),
                "calendar_entity": str(getattr(next_raw, "calendar_entity", "") or "").strip(),
            }

    return {
        "configured_entities": configured_entities,
        "current_events_count": current_events_count,
        "upcoming_events_count": upcoming_events_count,
        "cache_ts": cache_ts,
        "cached_events_count": cached_events_count,
        "is_vacation_active": is_vacation_active,
        "is_wfh_today": is_wfh_today,
        "is_office_today": is_office_today,
        "next_vacation": next_vacation,
    }


def _house_state_summary_diagnostics(coordinator: Any) -> dict[str, Any]:
    if coordinator is None:
        return {}
    engine = getattr(coordinator, "engine", None)
    if engine is None:
        return {}

    state = getattr(engine, "_state", None)
    engine_diag = engine.diagnostics() if hasattr(engine, "diagnostics") else {}
    house_diag = dict(engine_diag.get("house_state") or {})
    calendar_result = getattr(state, "calendar_result", None) if state is not None else None

    resolution_trace = dict(house_diag.get("resolution_trace") or {})
    decision = dict(resolution_trace.get("decision") or {})
    active_candidates = list(resolution_trace.get("active_candidates") or [])
    pending_candidate = (
        str(decision.get("source_candidate") or "").strip()
        if str(decision.get("action") or "") == "pending"
        else ""
    )
    pending_remaining_s = (
        decision.get("pending_remaining_s")
        if str(decision.get("action") or "") == "pending"
        else None
    )

    calendar_context = {
        "is_vacation_active": bool(getattr(calendar_result, "is_vacation_active", False))
        if calendar_result is not None
        else False,
        "is_wfh_today": bool(getattr(calendar_result, "is_wfh_today", False))
        if calendar_result is not None
        else False,
        "is_office_today": bool(getattr(calendar_result, "is_office_today", False))
        if calendar_result is not None
        else False,
    }

    return {
        "state": getattr(state, "get_sensor", lambda _k: None)("heima_house_state")
        if state is not None
        else None,
        "reason": getattr(state, "get_sensor", lambda _k: None)("heima_house_state_reason")
        if state is not None
        else None,
        "resolution_path": resolution_trace.get("resolution_path"),
        "winning_reason": resolution_trace.get("winning_reason"),
        "sticky_retention": bool(resolution_trace.get("sticky_retention")),
        "active_candidates": active_candidates,
        "pending_candidate": pending_candidate,
        "pending_remaining_s": pending_remaining_s,
        "calendar_context": calendar_context,
    }


def _security_presence_summary_diagnostics(coordinator: Any) -> dict[str, Any]:
    active = _active_reaction_items(coordinator)
    configured_total = 0
    active_tonight_total = 0
    ready_tonight_total = 0
    waiting_for_darkness_total = 0
    insufficient_evidence_total = 0
    muted_total = 0
    blocked_total = 0
    configured_by_room: dict[str, int] = {}
    source_room_counts: dict[str, int] = {}
    blocked_by_reason: dict[str, int] = {}
    blocked_by_class: dict[str, int] = {}
    operational_state_counts: dict[str, int] = {}
    source_profile_kind_counts: dict[str, int] = {}
    examples: list[dict[str, Any]] = []
    ready_examples: list[dict[str, Any]] = []
    waiting_for_darkness_examples: list[dict[str, Any]] = []
    insufficient_evidence_examples: list[dict[str, Any]] = []

    for reaction_id, cfg in active:
        reaction_type = str(cfg.get("reaction_type") or "").strip()
        reaction_class = str(cfg.get("reaction_class") or "").strip()
        template_id = str(cfg.get("source_template_id") or "").strip()
        is_security_presence = (
            reaction_type == "vacation_presence_simulation"
            or reaction_class == "VacationPresenceSimulationReaction"
            or template_id == "security.vacation_presence_simulation.basic"
        )
        if not is_security_presence:
            continue

        configured_total += 1
        active_tonight = bool(cfg.get("active_tonight") is True)
        muted = bool(cfg.get("muted") is True)
        blocked_reason = str(cfg.get("blocked_reason") or "").strip()
        operational_state = str(cfg.get("operational_state") or "").strip()
        source_profile_kind = str(cfg.get("source_profile_kind") or "").strip()
        plan_count = int(cfg.get("tonight_plan_count") or 0)
        if muted:
            muted_total += 1
            operational_state = "muted"
        if not operational_state:
            operational_state = _security_presence_operational_state_fallback(
                blocked_reason=blocked_reason,
                plan_count=plan_count,
            )
        if active_tonight:
            active_tonight_total += 1
        if source_profile_kind:
            source_profile_kind_counts[source_profile_kind] = (
                source_profile_kind_counts.get(source_profile_kind, 0) + 1
            )
        if operational_state:
            operational_state_counts[operational_state] = (
                operational_state_counts.get(operational_state, 0) + 1
            )
        if plan_count > 0 or blocked_reason == "awaiting_next_planned_activation":
            ready_tonight_total += 1
        if blocked_reason == "outside_not_dark":
            waiting_for_darkness_total += 1
        if blocked_reason in {
            "insufficient_learned_evidence",
            "insufficient_source_strength",
            "no_suitable_recent_sources",
        }:
            insufficient_evidence_total += 1
        if blocked_reason:
            blocked_total += 1
            blocked_by_reason[blocked_reason] = blocked_by_reason.get(blocked_reason, 0) + 1
            reason_class = _security_presence_blocked_reason_class(blocked_reason)
            blocked_by_class[reason_class] = blocked_by_class.get(reason_class, 0) + 1

        allowed_rooms = [
            str(item).strip() for item in list(cfg.get("allowed_rooms") or []) if str(item).strip()
        ]
        source_rooms = [
            str(item).strip() for item in list(cfg.get("source_rooms") or []) if str(item).strip()
        ]
        for room_id in allowed_rooms:
            configured_by_room[room_id] = configured_by_room.get(room_id, 0) + 1
        for room_id in source_rooms:
            source_room_counts[room_id] = source_room_counts.get(room_id, 0) + 1

        if len(examples) < 3:
            examples.append(
                {
                    "reaction_id": reaction_id,
                    "allowed_rooms": allowed_rooms,
                    "source_rooms": source_rooms,
                    "active_tonight": active_tonight,
                    "muted": muted,
                    "operational_state": operational_state,
                    "blocked_reason": blocked_reason,
                    "source_profile_kind": source_profile_kind,
                    "tonight_plan_count": plan_count,
                    "next_planned_activation": cfg.get("next_planned_activation"),
                }
            )

        example = {
            "reaction_id": reaction_id,
            "allowed_rooms": allowed_rooms,
            "source_rooms": source_rooms,
            "source_profile_kind": source_profile_kind,
            "muted": muted,
            "operational_state": operational_state,
            "tonight_plan_count": plan_count,
            "next_planned_activation": cfg.get("next_planned_activation"),
            "tonight_plan_preview": [
                {
                    "room_id": str(item.get("room_id") or ""),
                    "due_local": str(item.get("due_local") or ""),
                    "jitter_min": int(item.get("jitter_min") or 0),
                    "selection_reason": str(item.get("selection_reason") or ""),
                }
                for item in list(cfg.get("tonight_plan_preview") or [])[:3]
                if isinstance(item, dict)
            ],
            "selected_sources": [
                {
                    "reaction_id": str(item.get("reaction_id") or ""),
                    "room_id": str(item.get("room_id") or ""),
                    "selection_reason": str(item.get("selection_reason") or ""),
                    "score": item.get("score"),
                }
                for item in list(cfg.get("selected_source_trace") or [])[:3]
                if isinstance(item, dict)
            ],
            "excluded_sources": [
                {
                    "reaction_id": str(item.get("reaction_id") or ""),
                    "room_id": str(item.get("room_id") or ""),
                    "exclusion_reason": str(item.get("exclusion_reason") or ""),
                    "score": item.get("score"),
                }
                for item in list(cfg.get("excluded_source_trace") or [])[:3]
                if isinstance(item, dict)
            ],
        }
        if (plan_count > 0 or blocked_reason == "awaiting_next_planned_activation") and len(
            ready_examples
        ) < 3:
            ready_examples.append(dict(example))
        if blocked_reason == "outside_not_dark" and len(waiting_for_darkness_examples) < 3:
            waiting_for_darkness_examples.append(dict(example))
        if (
            blocked_reason
            in {
                "insufficient_learned_evidence",
                "insufficient_source_strength",
                "no_suitable_recent_sources",
            }
            and len(insufficient_evidence_examples) < 3
        ):
            insufficient_evidence_examples.append(dict(example))

    return {
        "configured_total": configured_total,
        "active_tonight_total": active_tonight_total,
        "ready_tonight_total": ready_tonight_total,
        "waiting_for_darkness_total": waiting_for_darkness_total,
        "insufficient_evidence_total": insufficient_evidence_total,
        "muted_total": muted_total,
        "blocked_total": blocked_total,
        "configured_by_room": dict(sorted(configured_by_room.items())),
        "source_room_counts": dict(sorted(source_room_counts.items())),
        "blocked_by_class": dict(sorted(blocked_by_class.items())),
        "blocked_by_reason": dict(sorted(blocked_by_reason.items())),
        "operational_state_counts": dict(sorted(operational_state_counts.items())),
        "source_profile_kind_counts": dict(sorted(source_profile_kind_counts.items())),
        "examples": examples,
        "ready_examples": ready_examples,
        "waiting_for_darkness_examples": waiting_for_darkness_examples,
        "insufficient_evidence_examples": insufficient_evidence_examples,
    }


def _security_camera_evidence_summary_diagnostics(coordinator: Any) -> dict[str, Any]:
    engine = getattr(coordinator, "engine", None) if coordinator is not None else None
    diagnostics = (
        engine.diagnostics() if engine is not None and hasattr(engine, "diagnostics") else {}
    )
    section = dict(diagnostics.get("security_camera_evidence") or {})

    configured_sources = [
        dict(item)
        for item in list(section.get("configured_sources") or [])
        if isinstance(item, dict)
    ]
    active_evidence = [
        dict(item) for item in list(section.get("active_evidence") or []) if isinstance(item, dict)
    ]
    unavailable_sources = [
        dict(item)
        for item in list(section.get("unavailable_sources") or [])
        if isinstance(item, dict)
    ]
    security_trace = dict(diagnostics.get("security", {}).get("camera_evidence_trace") or {})
    breach_candidates = [
        dict(item)
        for item in list(security_trace.get("breach_candidates") or [])
        if isinstance(item, dict)
    ]
    return_home_hint_reasons = [
        dict(item)
        for item in list(security_trace.get("return_home_hint_reasons") or [])[:3]
        if isinstance(item, dict)
    ]

    configured_by_role: dict[str, int] = {}
    active_by_role: dict[str, int] = {}
    active_by_kind: dict[str, int] = {}
    source_status_counts = dict(section.get("source_status_counts") or {})
    breach_by_rule: dict[str, int] = {}

    for item in configured_sources:
        role = str(item.get("role") or "").strip()
        if role:
            configured_by_role[role] = configured_by_role.get(role, 0) + 1

    for item in active_evidence:
        role = str(item.get("role") or "").strip()
        kind = str(item.get("kind") or "").strip()
        if role:
            active_by_role[role] = active_by_role.get(role, 0) + 1
        if kind:
            active_by_kind[kind] = active_by_kind.get(kind, 0) + 1

    for item in breach_candidates:
        rule = str(item.get("rule") or "").strip()
        if rule:
            breach_by_rule[rule] = breach_by_rule.get(rule, 0) + 1

    examples: list[dict[str, Any]] = []
    for item in configured_sources[:3]:
        examples.append(
            {
                "source_id": str(item.get("id") or ""),
                "display_name": str(item.get("display_name") or ""),
                "role": str(item.get("role") or ""),
                "status": str(item.get("status") or ""),
                "active_kinds": list(item.get("active_kinds") or []),
                "unavailable_kinds": list(item.get("unavailable_kinds") or []),
                "contact_active": bool(item.get("contact_active")),
                "last_seen_ts": item.get("last_seen_ts"),
            }
        )

    return {
        "configured_total": len(configured_sources),
        "active_evidence_total": len(active_evidence),
        "unavailable_total": len(unavailable_sources),
        "breach_candidate_total": len(breach_candidates),
        "return_home_hint_active": bool(security_trace.get("return_home_hint") is True),
        "configured_by_role": dict(sorted(configured_by_role.items())),
        "active_by_role": dict(sorted(active_by_role.items())),
        "active_by_kind": dict(sorted(active_by_kind.items())),
        "source_status_counts": dict(sorted(source_status_counts.items())),
        "breach_by_rule": dict(sorted(breach_by_rule.items())),
        "examples": examples,
        "breach_candidates": breach_candidates[:3],
        "return_home_hint_reasons": return_home_hint_reasons,
    }


def _security_presence_blocked_reason_class(reason: str) -> str:
    value = str(reason or "").strip()
    if value in {"presence_detected"}:
        return "safety_block"
    if value in {"outside_not_dark", "not_in_vacation"}:
        return "context_block"
    if value in {
        "insufficient_learned_evidence",
        "insufficient_source_strength",
        "no_suitable_recent_sources",
    }:
        return "evidence_block"
    if value in {"waiting_for_snapshot", "awaiting_next_planned_activation", "sun_unavailable"}:
        return "readiness_block"
    if not value:
        return "none"
    return "other"


def _security_presence_operational_state_fallback(*, blocked_reason: str, plan_count: int) -> str:
    if plan_count > 0 or blocked_reason == "awaiting_next_planned_activation":
        return "ready_tonight"
    if blocked_reason == "outside_not_dark":
        return "waiting_for_darkness"
    if blocked_reason in {
        "insufficient_learned_evidence",
        "insufficient_source_strength",
        "no_suitable_recent_sources",
    }:
        return "insufficient_evidence"
    if blocked_reason in {"waiting_for_snapshot", "sun_unavailable"}:
        return "waiting_for_readiness"
    if blocked_reason == "presence_detected":
        return "blocked_for_safety"
    if blocked_reason == "not_in_vacation":
        return "blocked_for_context"
    if blocked_reason == "disabled":
        return "disabled"
    return "idle"


def _composite_summary_diagnostics(
    proposal_diagnostics: dict[str, Any],
    coordinator: Any,
) -> dict[str, Any]:
    proposals = list(proposal_diagnostics.get("proposals") or [])
    composite_pending = [
        dict(item)
        for item in proposals
        if isinstance(item, dict)
        and str(item.get("type") or "").strip().startswith("room_")
        and str(item.get("status") or "") == "pending"
    ]

    pending_by_room: dict[str, int] = {}
    pending_by_type: dict[str, int] = {}
    pending_by_primary_signal: dict[str, int] = {}
    pending_tuning_total = 0
    pending_discovery_total = 0
    pending_tuning_examples: list[dict[str, Any]] = []
    pending_discovery_examples: list[dict[str, Any]] = []
    for proposal in composite_pending:
        config_summary = _safe_dict(proposal.get("config_summary"))
        reaction_type = str(proposal.get("type") or "").strip()
        room_id = str(config_summary.get("room_id") or "").strip()
        primary_signal_name = str(config_summary.get("primary_signal_name") or "").strip()
        if room_id:
            pending_by_room[room_id] = pending_by_room.get(room_id, 0) + 1
        if reaction_type:
            pending_by_type[reaction_type] = pending_by_type.get(reaction_type, 0) + 1
        if primary_signal_name:
            pending_by_primary_signal[primary_signal_name] = (
                pending_by_primary_signal.get(primary_signal_name, 0) + 1
            )
        example = {
            "id": proposal.get("id"),
            "type": reaction_type,
            "label": _composite_example_label(reaction_type, room_id, primary_signal_name)
            or str(proposal.get("description") or "").strip(),
            "room_id": room_id,
            "primary_signal_name": primary_signal_name,
            "confidence": proposal.get("confidence"),
        }
        if str(proposal.get("followup_kind") or "") == "tuning_suggestion":
            pending_tuning_total += 1
            if len(pending_tuning_examples) < 3:
                pending_tuning_examples.append(example)
        else:
            pending_discovery_total += 1
            if len(pending_discovery_examples) < 3:
                pending_discovery_examples.append(example)

    active = _active_reaction_items(coordinator)
    configured_total = 0
    configured_by_room: dict[str, int] = {}
    configured_by_type: dict[str, int] = {}
    configured_by_primary_signal: dict[str, int] = {}
    for _reaction_id, cfg in active:
        reaction_type = str(cfg.get("reaction_type") or "").strip()
        reaction_class = str(cfg.get("reaction_class") or "").strip()
        identity_key = str(cfg.get("source_proposal_identity_key") or "").strip()
        is_composite = (
            reaction_type.startswith("room_")
            or reaction_class in {"RoomSignalAssistReaction", "RoomLightingAssistReaction"}
            or identity_key.startswith("room_")
        )
        if not is_composite:
            continue
        configured_total += 1
        if reaction_type:
            configured_by_type[reaction_type] = configured_by_type.get(reaction_type, 0) + 1
        room_id = str(cfg.get("room_id") or "").strip()
        primary_signal_name = str(cfg.get("primary_signal_name") or "").strip()
        if not room_id and "|room=" in identity_key:
            for part in identity_key.split("|"):
                if part.startswith("room="):
                    room_id = part.split("=", 1)[1]
                if part.startswith("primary=") and not primary_signal_name:
                    primary_signal_name = part.split("=", 1)[1]
        if room_id:
            configured_by_room[room_id] = configured_by_room.get(room_id, 0) + 1
        if primary_signal_name:
            configured_by_primary_signal[primary_signal_name] = (
                configured_by_primary_signal.get(primary_signal_name, 0) + 1
            )

    return {
        "configured_total": configured_total,
        "configured_by_room": dict(sorted(configured_by_room.items())),
        "configured_by_type": dict(sorted(configured_by_type.items())),
        "configured_by_primary_signal": dict(sorted(configured_by_primary_signal.items())),
        "pending_total": len(composite_pending),
        "pending_tuning_total": pending_tuning_total,
        "pending_discovery_total": pending_discovery_total,
        "pending_by_room": dict(sorted(pending_by_room.items())),
        "pending_by_type": dict(sorted(pending_by_type.items())),
        "pending_by_primary_signal": dict(sorted(pending_by_primary_signal.items())),
        "pending_tuning_examples": pending_tuning_examples,
        "pending_discovery_examples": pending_discovery_examples,
    }


def _proposal_status_counts(proposals: list[dict[str, Any]]) -> dict[str, int]:
    pending = 0
    accepted = 0
    rejected = 0
    stale_pending = 0
    for proposal in proposals:
        status = str(proposal.get("status") or "")
        if status == "pending":
            pending += 1
            if proposal.get("is_stale") is True:
                stale_pending += 1
        elif status == "accepted":
            accepted += 1
        elif status == "rejected":
            rejected += 1
    return {
        "total": len(proposals),
        "pending": pending,
        "accepted": accepted,
        "rejected": rejected,
        "stale_pending": stale_pending,
    }


def _top_proposal_examples(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = sorted(
        proposals,
        key=lambda item: (
            0 if str(item.get("status") or "") == "pending" else 1,
            -(float(item.get("confidence") or 0.0)),
            str(item.get("updated_at") or ""),
        ),
    )
    examples: list[dict[str, Any]] = []
    for proposal in ranked[:3]:
        examples.append(
            {
                "id": proposal.get("id"),
                "type": proposal.get("type"),
                "status": proposal.get("status"),
                "confidence": proposal.get("confidence"),
                "description": proposal.get("description"),
                "is_stale": proposal.get("is_stale"),
            }
        )
    return examples


def _template_ids(
    templates: list[Any],
    *,
    implemented_only: bool | None = None,
    invert_implemented: bool = False,
) -> list[str]:
    ids: list[str] = []
    for item in templates:
        if isinstance(item, dict):
            implemented = bool(item.get("implemented") is True)
            if implemented_only is True and not implemented:
                continue
            if invert_implemented and implemented:
                continue
            template_id = str(item.get("template_id") or "").strip()
            if template_id:
                ids.append(template_id)
        else:
            if implemented_only is True or invert_implemented:
                continue
            template_id = str(item).strip()
            if template_id:
                ids.append(template_id)
    return ids


def _lighting_slot_key_from_identity(identity_key: str) -> str:
    value = str(identity_key or "").strip()
    if not value.startswith("lighting_scene_schedule|"):
        return ""
    return value.split("|scene=", 1)[0]


def _lighting_room_from_identity(identity_key: str) -> str:
    slot_key = _lighting_slot_key_from_identity(identity_key)
    if not slot_key:
        return ""
    for part in slot_key.split("|"):
        if part.startswith("room="):
            return part.split("=", 1)[1]
    return ""


def _lighting_followup_slot_key(cfg: dict[str, Any]) -> str:
    reaction_type = str(cfg.get("reaction_type") or "").strip()
    reaction_class = str(cfg.get("reaction_class") or "").strip()
    if reaction_type != "lighting_scene_schedule" and reaction_class != "LightingScheduleReaction":
        return ""
    scheduled_min = cfg.get("scheduled_min")
    bucket = None
    if isinstance(scheduled_min, (int, float)):
        bucket = (int(scheduled_min) // 30) * 30
    return (
        f"lighting_scene_schedule|room={cfg.get('room_id')}|weekday={cfg.get('weekday')}"
        f"|bucket={bucket}"
    )


def _composite_example_label(
    reaction_type: str,
    room_id: str,
    primary_signal_name: str,
) -> str:
    reaction_type = str(reaction_type or "").strip()
    room_id = str(room_id or "").strip()
    primary_signal_name = str(primary_signal_name or "").strip()
    if not room_id:
        return ""

    if reaction_type == "room_signal_assist":
        return (
            f"Assist {room_id} · {primary_signal_name}"
            if primary_signal_name
            else f"Assist {room_id}"
        )
    if reaction_type == "room_darkness_lighting_assist":
        return (
            f"Luci {room_id} · {primary_signal_name}" if primary_signal_name else f"Luci {room_id}"
        )
    if reaction_type == "room_cooling_assist":
        return (
            f"Cooling {room_id} · {primary_signal_name}"
            if primary_signal_name
            else f"Cooling {room_id}"
        )
    if reaction_type == "room_air_quality_assist":
        return (
            f"Air quality {room_id} · {primary_signal_name}"
            if primary_signal_name
            else f"Air quality {room_id}"
        )
    return ""


def _active_reaction_items(coordinator: Any) -> list[tuple[str, dict[str, Any]]]:
    if coordinator is None:
        return []
    engine = getattr(coordinator, "engine", None)
    state = getattr(engine, "_state", None)
    reactions = _reaction_sensor_payload(state)
    return [
        (str(reaction_id), dict(cfg))
        for reaction_id, cfg in reactions.items()
        if isinstance(cfg, dict)
    ]


def _reaction_sensor_payload(state: Any) -> dict[str, Any]:
    if state is None:
        return {}

    get_sensor_attributes = getattr(state, "get_sensor_attributes", None)
    if callable(get_sensor_attributes):
        attrs = _safe_dict(get_sensor_attributes("heima_reactions_active"))
        reactions = _safe_dict(attrs.get("reactions"))
        if reactions:
            return reactions

    get_sensor = getattr(state, "get_sensor", None)
    if not callable(get_sensor):
        return {}
    payload = get_sensor("heima_reactions_active")
    if not isinstance(payload, str) or not payload.strip():
        return {}

    import json

    try:
        reactions = json.loads(payload)
    except Exception:  # noqa: BLE001
        return {}
    return _safe_dict(reactions)


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
