# Heima — Security Camera Evidence Provider Roadmap

**Status:** Planned
**Last Updated:** 2026-04-07
**Branch:** `feat/security-camera-evidence`

Related spec:
- [security_camera_evidence_spec.md](/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component/docs/specs/domains/security_camera_evidence_spec.md)

## Goal

Build a narrow, product-grade `security_camera_evidence` capability that:
- consumes camera-derived HA entities already available in Home Assistant
- produces structured evidence for `SecurityDomain`
- exposes bounded return-home hints without assigning person identity directly

Architecturally, this capability should be implemented as a **security-owned runtime evidence
provider**, not as a standalone product domain.

This roadmap is intentionally scoped to:
- security evidence
- garage / entry use cases
- strong diagnostics and explainability

It is explicitly not a roadmap for:
- video handling
- clip/snapshot management
- computer vision inside Heima
- direct person identification

## Development Principles

- consume HA evidence, do not build a camera platform
- keep `SecurityDomain` as the primary decision-maker
- keep `PeopleDomain` integration secondary and hint-based
- prefer a few strong roles over a broad camera taxonomy
- make unavailability and weak evidence readable in diagnostics
- keep the provider reusable by avoiding dependencies on downstream semantic domains

## Recommended Delivery Order

1. `SCE-A1` config and provider skeleton
2. `SCE-A2` evidence normalization
3. `SCE-A3` security-domain integration
4. `SCE-A4` return-home hints
5. `SCE-A5` diagnostics and tooling
6. `SCE-A6` validation

## DAG Placement

Recommended v1 insertion point in the hardcoded runtime DAG:

`InputNormalizer -> SecurityCameraEvidenceProvider -> People -> Occupancy -> Calendar -> HouseState -> Lighting -> Heating -> Security -> Apply`

Reasoning:
- the provider depends on normalized HA entities and configured camera bindings only
- it should run before `SecurityDomain` so security can consume its result natively
- it should also run before `PeopleDomain` so bounded future hints such as `return_home_hint`
  remain reusable without depending on `SecurityDomain` internals
- it should not be modeled as a child domain of `security`

Implementation guidance for v1:
- add a first-class runtime provider node in `engine.py`
- keep product semantics owned by `SecurityDomain`
- keep provider output as a typed result bag entry, not direct house-state mutation

## SCE-A1 — Config and Provider Skeleton

Objective:
- make camera evidence a first-class, bounded runtime evidence provider

Tasks:
- define config shape under `security`
- add normalized source model for:
  - `id`
  - `display_name`
  - `enabled`
  - `role`
  - `motion_entity`
  - `person_entity`
  - `vehicle_entity`
  - `contact_entity`
  - `return_home_contributor`
  - `security_priority`
- add `SecurityCameraEvidenceProvider`
- add empty `SecurityCameraEvidenceResult`
- wire the provider into engine evaluation order in a bounded way

Likely files:
- `custom_components/heima/runtime/domains/security_camera_evidence.py`
- `custom_components/heima/runtime/engine.py`
- `custom_components/heima/config_flow/_steps_security.py`
- `custom_components/heima/models.py` or equivalent typed config path if needed

Exit criteria:
- provider exists in runtime
- config can represent camera evidence sources
- engine can evaluate the provider safely even with zero sources configured

## SCE-A2 — Evidence Normalization

Objective:
- normalize configured camera entities into structured evidence records

Tasks:
- read configured HA entities
- produce evidence records for:
  - motion
  - person
  - vehicle
- support initial roles:
  - `entry`
  - `garage`
- include:
  - `active`
  - `role`
  - `kind`
  - `source_entities`
  - `last_seen_ts`
  - bounded confidence
- add debounce / hold behavior where needed to reduce burst noise
- define unavailable / partial-source handling

Likely files:
- `custom_components/heima/runtime/domains/security_camera_evidence.py`
- maybe shared helper module for evidence typing

Exit criteria:
- a configured source produces stable evidence records
- unavailable sources are visible and do not crash the domain

## SCE-A3 — SecurityDomain Integration

Objective:
- turn normalized camera evidence into actionable security context

Tasks:
- add domain result consumption in `SecurityDomain`
- keep `SecurityDomain` as the only decision-maker for alert severity and final events
- define first breach-candidate rules:
  - `armed_away + entry person`
  - `armed_away + garage open + garage person`
  - `armed_away + garage open + garage vehicle`
- define severity shaping:
  - informational
  - suspicious
  - strong evidence
- ensure camera evidence does not bypass existing security guardrails

Likely files:
- `custom_components/heima/runtime/domains/security.py`
- `custom_components/heima/runtime/domains/security_camera_evidence.py`
- related diagnostics surfaces

Exit criteria:
- security diagnostics show breach candidates driven by camera evidence
- false positives from missing entities are not promoted into alerts
- no security-only internal coupling is required for future provider reuse

## SCE-A4 — Return-Home Hints

Objective:
- expose bounded “someone may have returned” hints without assigning identity

Tasks:
- derive `return_home_hint` from:
  - `entry person`
  - `garage vehicle`
  - `garage person`
  - optional contact correlation
- expose hint as part of the domain result
- decide whether the first consumer is:
  - `PeopleDomain`
  - or only diagnostics / security for v1

Recommended first choice:
- expose the hint first
- consume it later only after diagnostics prove it is stable

Exit criteria:
- return-home hint exists and is explainable
- no direct named-person assignment occurs

## SCE-A5 — Diagnostics and Tooling

Objective:
- make the provider operationally readable

Tasks:
- diagnostics summary:
  - configured sources
  - active evidence
  - unavailable sources
  - active breach candidates
  - active return-home hints
- add CLI/tooling sections if warranted
- add review/admin-readable output for the source model
- decide whether example dashboard surfaces should be added now or later

Likely files:
- `custom_components/heima/diagnostics.py`
- `scripts/diagnostics.py`
- `scripts/learning_audit.py` only if useful
- dashboard examples if needed

Exit criteria:
- an admin can understand what the camera evidence provider currently sees
- active/inactive/unavailable states are easy to inspect

## SCE-A6 — Validation

Objective:
- validate the first production-worthy slice end-to-end

Tasks:
- unit tests for:
  - source parsing
  - evidence normalization
  - role handling
  - unavailable entity handling
  - security candidate generation
- live or fake-house tests for:
  - `entry person while armed_away`
  - `garage open + vehicle/person while armed_away`
  - return-home hint activation
- diagnostics verification

Likely files:
- new runtime provider tests
- integration/e2e tests
- fake-house scenarios when the test house becomes available

Exit criteria:
- first slice works in both unit and environment-backed validation

## First Slice Recommendation

The first coding slice should be:

### Slice 1
- `SCE-A1`
- minimal `SCE-A2`

That means:
- define config shape
- create the domain
- normalize only:
  - `entry person`
  - `garage person`
  - `garage vehicle`
- no PeopleDomain consumption yet
- no broad role taxonomy yet

Why:
- it proves the model
- it immediately supports valuable security use cases
- it keeps the blast radius small

## Open Decisions

These decisions should be made before or during `SCE-A3`:

1. Should the domain live strictly under `security`, or have its own top-level runtime slot?
   Recommendation:
   - own runtime provider node
   - security-owned semantics
   - not a standalone product domain

2. Should return-home hints remain diagnostics-only in the first implementation?
   Recommendation:
   - yes

3. Should `driveway` be in the first slice?
   Recommendation:
   - no

4. Should snapshots/clips appear in diagnostics?
   Recommendation:
   - not in the first slice

## Recommended Next Step

Implement `SCE-A1` and the minimum viable `SCE-A2` on this branch before expanding into:
- richer role coverage
- PeopleDomain consumption
- dashboard/UI polishing
