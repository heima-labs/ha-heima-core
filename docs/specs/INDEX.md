# Heima — Specifications Index
## Canonical Specs Structure

**Last verified against code:** 2026-04-03 (`main`)

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
- root-level `docs/specs/heima_*` files are compatibility redirect stubs only and should not be
  treated as living specifications

Related practical guides live outside this tree:
- `docs/guides/scene_and_script_usage.md`
- `docs/guides/plugin_authoring.md`

## Core

- `core/core_product_spec.md` — current product semantics (consolidated)
- `core/options_flow_spec.md` — configuration and options flow
- `core/options_flow_ux_spec.md` — current bounded UX/session contract for the options flow
- `core/events_and_notifications_spec.md` — event model + routing model (consolidated)
- `core/runtime_scheduler_spec.md` — runtime timer scheduler
- `core/house_state_override_spec.md` — `heima.set_mode` semantics
- `core/reactive_behavior_spec.md` — behavior/reaction runtime

## Domains

- `domains/house_state_spec.md` — current house-state candidate/hysteresis contract
- `domains/calendar_domain_spec.md` — current calendar domain contract and house-state integration
- `domains/heating_spec.md` — heating domain (implemented/partial)
- `domains/security_presence_simulation_spec.md` — security-owned occupancy simulation capability (draft)
- `domains/watering_spec.md` — watering domain (planned)

## Learning

- `learning/learning_system_spec.md` — event store, analyzers, proposals
- `learning/proposal_lifecycle_spec.md` — v1 proposal identity, refresh, and staleness
- `learning/admin_authored_automation_spec.md` — admin-requested automations and follow-up tuning
- `learning/inference_engine_spec.md` — inference v2 draft

## RFC / Historical

- `rfc/policy_plugin_framework_spec.md`
- `rfc/extension_strategy_solution_a.md`
- `rfc/constraints_dependencies_spec.md`
- `rfc/domain_framework_spec.md`
- `rfc/input_normalization_layer_spec.md`
- `rfc/mapping_model_spec.md`
- `rfc/event_catalog_spec.md`
- `rfc/security_mismatch_generalization_spec.md`
- `rfc/notification_recipients_spec.md`
- `rfc/heima_v2_emotion_ieq_research_note.md`
- `rfc/heima_spec_v1.md`
- `rfc/heima_spec_v1_1_behavior_framework.md`

## Compatibility Notes

Legacy root-level spec filenames are kept as thin redirect stubs for compatibility.
They remain referenced by some older docs and guides, but they are not canonical.
