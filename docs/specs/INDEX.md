# Heima — Specifications Index
## Canonical Specs Structure

**Last verified against code:** 2026-04-23 (`main`)

This folder is organized by maturity and scope:

- `core/` → implemented contracts used by runtime and UI
- `domains/` → per-domain specs
- `learning/` → learning/inference pipeline specs
- `rfc/` → future architecture and historical baseline specs

Interpretation notes:
- documents under `core/`, `domains/`, and `learning/` are the canonical v1.x contract unless
  they explicitly say `Draft`, `Target vNext`, or `RFC`
- documents under `rfc/` are not the source of truth for current runtime behavior unless they
  explicitly say `Implemented on main`
- legacy root-level `docs/specs/heima_*` redirect stubs have been removed; use only the canonical
  paths listed below

Related practical guides live outside this tree:
- `docs/guides/scene_and_script_usage.md`
- `docs/guides/plugin_authoring.md`
- `docs/guides/options_flow_configuration_guide.md`

## Core

- `core/core_product_spec.md` — current product semantics (consolidated)
- `core/options_flow_spec.md` — configuration and options flow
- `core/options_flow_ux_spec.md` — current bounded UX/session contract for the options flow
- `core/events_and_notifications_spec.md` — event model + routing model (consolidated)
- `core/event_catalog_spec.md` — stable canonical event taxonomy and payload envelope
- `core/notification_recipients_spec.md` — logical notification recipients, groups, and routing rules
- `core/security_mismatch_generalization_spec.md` — canonical `security.mismatch` taxonomy and compatibility contract
- `core/runtime_scheduler_spec.md` — runtime timer scheduler
- `core/house_state_override_spec.md` — `heima.set_mode` semantics
- `core/reactive_behavior_spec.md` — behavior/reaction runtime
- `core/reaction_identity_spec.md` — canonical `reaction_type` identity and persisted reaction contract
- `core/scheduled_routine_spec.md` — bounded admin-authored time-based routine contract
- `core/contextual_room_lighting_assist_spec.md` — contextual room-lighting reaction contract
- `core/heima_test_house_spec.md` — planned internal subproject for the official fake-house live test lab
- `core/heima_monitoring_spec.md` — monitoring surfaces, learning review, and ongoing operability contract
- `core/ha_backed_people_rooms_spec.md` — reconciliation model for HA-backed people and rooms, including discovery, notification, and edit-first UX
- `core/ha_backed_room_inventory_spec.md` — synced HA-derived room inventory and suggested bindings for the `Rooms` flow
- `core/people_presence_rules_spec.md` — per-person `presence_rule` contract for presence aggregation (`observer | resident | recurrent`)

## Domains

- `domains/house_state_spec.md` — current house-state candidate/hysteresis contract
- `domains/calendar_domain_spec.md` — current calendar domain contract and house-state integration
- `domains/heating_spec.md` — heating domain (implemented/partial)
- `domains/security_camera_evidence_spec.md` — security-owned camera evidence provider for alerts and return-home hints (draft)
- `domains/security_camera_evidence_roadmap.md` — staged development plan for the security camera evidence provider
- `domains/security_presence_simulation_spec.md` — security-owned occupancy simulation capability (draft)
- `domains/watering_spec.md` — watering domain (planned)

## Learning

- `learning/learning_system_spec.md` — event store, analyzers, proposals
- `learning/canonical_signal_pipeline_spec.md` — canonical signal and burst pipeline used by learning/proposals
- `learning/proposal_lifecycle_spec.md` — v1 proposal identity, refresh, and staleness
- `learning/context_conditioned_lighting_learning_spec.md` — learned context-scoped lighting proposals and review contract
- `learning/admin_authored_automation_spec.md` — admin-requested automations and follow-up tuning
- `learning/inference_engine_spec.md` — inference v2 draft

## Adapters

Spec per custom integration esterne che normalizzano fonti dati verso il contratto Heima.
Ogni adapter vive in un repo separato sotto `heima-labs/`.

- `adapters/external_context_contract.md` — contratto normativo v1.0: entity ID, semantica, degradazione, versioning
- `adapters/owm_adapter_spec.md` — adapter OpenWeatherMap (`heima-labs/ha-heima-owm-adapter`)
- `adapters/protezione_civile_adapter_spec.md` — adapter Protezione Civile italiana (`heima-labs/ha-heima-pc-adapter`)

## RFC / Historical

- `rfc/scheduled_routine_development_plan.md` — [historical/deprecated] implementation plan superseded by `core/scheduled_routine_spec.md`
- `rfc/policy_plugin_framework_spec.md`
- `rfc/extension_strategy_solution_a.md`
- `rfc/constraints_dependencies_spec.md`
- `rfc/domain_framework_spec.md`
- `rfc/input_normalization_layer_spec.md`
- `rfc/improvement_proposals_rfc.md`
- `rfc/mapping_model_spec.md`
- `rfc/heima_v2_emotion_ieq_research_note.md`
- `rfc/heima_spec_v1.md`
- `rfc/heima_spec_v1_1_behavior_framework.md`

## DAG Evolution Note

**v1** uses a **hardcoded DAG** defined in `engine.py`. Domain evaluation order is fixed:
`InputNormalizer → People → Occupancy → Calendar → HouseState → Lighting → Heating → Security → Apply`.
No plugin registration mechanism exists in v1.

**v2** (RFC — `heima_v2_spec.md`) introduces a **declarative DAG** with `depends_on` and topological sort.
Core domains (People, Occupancy, HouseState) remain fixed-order; plugin domains are sorted by dependency graph.

These are **not alternative implementations**. v2 replaces v1 when implemented and scheduled.
Until then, the v1 hardcoded order is the only runtime contract.

## Compatibility Notes

Older references to removed root-level spec filenames should be updated in-place rather than
reintroduced as redirect stubs.
