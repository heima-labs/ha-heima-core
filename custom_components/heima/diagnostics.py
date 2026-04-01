"""Diagnostics support for Heima."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.redact import async_redact_data

from .const import DIAGNOSTICS_REDACT_KEYS, DOMAIN
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
                "supports_admin_authored": bool(
                    plugin.get("supports_admin_authored") is True
                ),
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
                configured_by_lighting_slot.setdefault(slot_key, []).append((str(reaction_id), dict(cfg)))

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
    payload = engine._state.get_sensor("heima_reactions_active") if hasattr(engine, "_state") else None  # noqa: SLF001
    if not isinstance(payload, str) or not payload.strip():
        return {
            "total": 0,
            "by_origin": {},
            "by_author_kind": {},
            "by_template_id": {},
            "reaction_ids": [],
        }
    import json

    try:
        reactions = json.loads(payload)
    except Exception:  # noqa: BLE001
        return {
            "total": 0,
            "by_origin": {},
            "by_author_kind": {},
            "by_template_id": {},
            "reaction_ids": [],
        }
    if not isinstance(reactions, dict):
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
        key: sorted(ids)
        for key, ids in sorted(by_identity_key.items())
        if len(ids) > 1
    }
    lighting_slot_collisions = {
        key: sorted(ids)
        for key, ids in sorted(by_lighting_slot.items())
        if len(ids) > 1
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
