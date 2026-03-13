# Heima — Core Product Spec (Consolidated)

**Status:** Implemented/Partial
**Last Verified Against Code:** 2026-03-11

## Scope

This document is the consolidated product-level contract previously split across:
- `heima_spec_v1.md`
- `heima_spec_v1_1_behavior_framework.md`
- runtime behavior clarifications now in `core/reactive_behavior_spec.md`

## Product Intent

Heima provides a policy-driven home control plane on top of Home Assistant, based on:
- canonical entities (`heima_*`)
- deterministic evaluation cycle
- safe apply orchestration
- explicit override and observability surfaces

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

## Deferred / RFC Areas

- Policy plugin framework: `rfc/policy_plugin_framework_spec.md`
- Inference v2 engine: `learning/inference_engine_spec.md`
- Full cross-domain framework hardening: `rfc/domain_framework_spec.md`
