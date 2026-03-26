# Heima — Core Product Spec (Consolidated)

**Status:** Active core product contract
**Last Verified Against Code:** 2026-03-11

## Scope

This document is the consolidated product-level contract previously split across:
- `heima_spec_v1.md`
- `heima_spec_v1_1_behavior_framework.md`
- runtime behavior clarifications now in `core/reactive_behavior_spec.md`

## Normative precedence

This document is normative for the product-level contract of the Heima core.

Interpretation rule:
- if implementation and spec diverge, the divergence must be resolved explicitly
- code is a reference implementation, not the source of truth

## Non-goals

This document does not attempt to:
- duplicate the detailed schema or lifecycle contracts already defined in narrower specs
- prescribe internal module layout
- replace RFCs that define future or deferred extensions

## Product Intent

Heima provides a policy-driven home control plane on top of Home Assistant, based on:
- canonical entities (`heima_*`)
- deterministic evaluation cycle
- safe apply orchestration
- explicit override and observability surfaces

## Administrative Boundary

Heima configuration is part of the administrative control plane of the home.

Normative rule:
- creating or modifying Heima configuration MUST be restricted to Home Assistant administrators

This includes:
- initial setup
- options flow edits
- proposal review and proposal acceptance/rejection
- reaction editing and other persisted behavior changes

## Implemented Core Pillars

- Canonical state evaluation (people, occupancy, house_state, lighting, security, heating)
- Runtime scheduler integration for timed re-evaluations
- Behavior/reaction pipeline with snapshot history
- Notification/event pipeline with routing and gating controls
- Learning proposal pipeline (see `learning/learning_system_spec.md`)

## Canonical Source Specs

- Options/config: `core/options_flow_spec.md`
- Scheduler: `core/runtime_scheduler_spec.md`
- House-state override service: `core/house_state_override_spec.md`
- Reactions: `core/reactive_behavior_spec.md`
- Learning pipeline: `learning/learning_system_spec.md`

These narrower specs define the detailed contracts for their domains. This document is the
top-level consolidation layer that must remain semantically consistent with them.

## Deferred / RFC Areas

- Policy plugin framework: `rfc/policy_plugin_framework_spec.md`
- Inference v2 engine: `learning/inference_engine_spec.md`
- Full cross-domain framework hardening: `rfc/domain_framework_spec.md`
