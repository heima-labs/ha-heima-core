# Heima — Security Camera Evidence Provider Spec

**Status:** Draft
**Last Updated:** 2026-04-07

## Purpose

Define a narrow Heima capability that ingests camera-derived evidence already exposed by Home
Assistant and turns it into structured security signals.

This capability is intended to answer questions such as:
- someone may have returned home
- a vehicle is present in the garage or driveway
- the garage is open while the house is armed away
- motion or person evidence exists in a protected area

This capability is **security-owned**, but it is not a standalone product domain.
It is a bounded **runtime evidence provider** whose primary consumer is `SecurityDomain`.

It is not a general camera or video platform.

---

## 1. Product Scope

The capability SHOULD consume:
- HA `binary_sensor` camera motion signals
- HA `binary_sensor` person-detected signals
- HA `binary_sensor` vehicle-detected signals
- optional correlated entities such as:
  - door contact
  - garage contact
  - lock state

The capability SHOULD NOT directly own:
- video streams
- clips
- snapshots as a core contract
- face recognition
- identity matching
- CV inference inside Heima

The capability exists to turn already-available HA signals into:
- security evidence
- corroboration
- return-home hints
- asset/context flags

---

## 2. Provider Name and Placement

Recommended identifier:
- provider / family: `security_camera_evidence`

Primary consumer:
- `SecurityDomain`

Secondary consumers:
- `PeopleDomain` via bounded hints only
- `HouseStateDomain` only indirectly and conservatively
- future notification or audit surfaces

The provider must not write house state directly.
It should publish a structured evidence result that downstream domains may consume.

---

## 3. High-Level Model

Each configured source represents one monitored camera context.

The provider does not expose “raw camera state” as its main abstraction.
It exposes normalized evidence records.

Examples:
- `entry_person_detected`
- `entry_motion_detected`
- `garage_vehicle_present`
- `garage_person_detected`
- `garage_motion_detected`

Each evidence record should carry at least:
- `kind`
- `role`
- `active`
- `confidence`
- `source_entities`
- `last_seen_ts`

---

## 4. Roles

The first version should support a small, explicit role set:
- `entry`
- `garage`
- `driveway`
- `perimeter`
- `indoor_sensitive`

Recommended v1 slice:
- `entry`
- `garage`

Rationale:
- these roles are strong enough for useful security logic
- they avoid turning the feature into a generic spatial taxonomy too early

---

## 5. Config Shape

Recommended placement:
- under `security`

Suggested shape:

```yaml
security:
  camera_evidence_sources:
    - id: front_door_cam
      display_name: Front Door Camera
      enabled: true
      role: entry
      motion_entity: binary_sensor.front_cam_motion
      person_entity: binary_sensor.front_cam_person
      vehicle_entity: null
      contact_entity: binary_sensor.front_door_contact
      return_home_contributor: true
      security_priority: high

    - id: garage_cam
      display_name: Garage Camera
      enabled: true
      role: garage
      motion_entity: binary_sensor.garage_motion
      person_entity: binary_sensor.garage_person
      vehicle_entity: binary_sensor.garage_vehicle
      contact_entity: binary_sensor.garage_door_contact
      return_home_contributor: true
      security_priority: high
```

Minimum source fields:
- `id`
- `enabled`
- `role`

Optional evidence bindings:
- `motion_entity`
- `person_entity`
- `vehicle_entity`
- `contact_entity`

Optional policy flags:
- `return_home_contributor`
- `security_priority`

---

## 6. Runtime Contract

The provider should read configured camera evidence sources each evaluation cycle and produce a
`SecurityCameraEvidenceResult`.

Suggested result fields:
- `active_evidence`
- `entry_person_active`
- `garage_vehicle_active`
- `garage_motion_active`
- `return_home_hint`
- `security_breach_candidates`
- `unavailable_sources`

The result should be consumable by `SecurityDomain` without the rest of the runtime needing to know
camera-specific implementation details.

The result should also be safe for bounded reuse by other domains.
This is the main reason the capability should exist as a provider node rather than as a private
`SecurityDomain` implementation detail.

### 6.1 DAG Insertion Point

Recommended v1 insertion point in the hardcoded runtime DAG:

`InputNormalizer -> SecurityCameraEvidenceProvider -> People -> Occupancy -> Calendar -> HouseState -> Lighting -> Heating -> Security -> Apply`

Rationale:
- the provider depends only on normalized HA evidence and configured source bindings
- it should not depend on downstream semantic domains in order to stay reusable
- `SecurityDomain` remains the primary consumer, but `PeopleDomain` may later consume bounded
  hints such as `return_home_hint`
- embedding camera evidence logic inside `SecurityDomain` would make reuse by `PeopleDomain` or
  future house-state logic too tightly coupled to security internals

In v1 this should be implemented as a **first-class runtime provider node**, not as a new product
domain and not as a child domain under `security`.

---

## 7. SecurityDomain Integration

This is the primary reason for the provider to exist.

Recommended first-order rules:
- `armed_away + entry person evidence` -> security alert candidate
- `armed_away + garage open + garage vehicle/person evidence` -> strong alert candidate
- `armed_away + indoor_sensitive motion/person evidence` -> high-severity alert candidate

The provider should not decide final notification behavior itself.
It should provide structured input for `SecurityDomain`.

Recommended v1 relationship:
- `security_camera_evidence` computes evidence
- `SecurityDomain` decides severity and resulting events

---

## 8. Return-Home Hints

Camera evidence is useful for return-home detection, but should be treated as a hint, not as direct
person identity.

Good examples:
- `entry person detected`
- `garage vehicle detected`
- `garage person detected`
- `entry person + door opened shortly after`

Recommended rule:
- the provider MAY expose `return_home_hint = true`
- the provider MUST NOT directly mark a named person as home

This hint may later be used by `PeopleDomain` or another bounded consumer as corroboration for:
- anonymous presence
- return-home inference

---

## 9. Vehicle and Asset Signals

The provider may also expose asset-level context that is useful for security logic.

Useful examples:
- vehicle present in garage
- vehicle present in driveway
- repeated motion in protected camera area

This should be modeled as context/evidence, not as person identity.

Example:
- `garage_vehicle_active = true` can strengthen:
  - arrival suspicion
  - garage security mismatch
  - away-mode alert interpretation

---

## 10. Guardrails

Mandatory guardrails:
- no direct identity assignment from camera evidence
- no requirement for Heima to process video directly
- clear handling of unavailable camera entities
- debounce / hold semantics for bursty evidence
- diagnostics for suppressed or ignored evidence

Camera signals are often noisy.
The system should prefer conservative corroboration over aggressive certainty.

---

## 11. Diagnostics

The provider should expose a readable diagnostics surface.

Minimum expectation:
- configured sources
- active evidence
- unavailable sources
- active return-home hints
- active breach candidates
- correlation notes, where applicable

Examples:
- `entry person detected`
- `garage open + vehicle detected`
- `garage motion detected while armed away`

---

## 12. Recommended V1 Slice

The first implementation SHOULD stay narrow.

Recommended roles:
- `entry`
- `garage`

Recommended evidence kinds:
- `motion`
- `person`
- `vehicle`

Recommended consumers for v1:
- `SecurityDomain`
- diagnostics surfaces

Deferred consumers:
- `PeopleDomain`
- `HouseStateDomain`

This keeps the provider reusable without forcing multi-domain behavioral changes into the first
slice.

Recommended use cases:
1. `armed_away + entry person`
2. `armed_away + garage open + garage vehicle/person`
3. `return_home_hint` from `entry` or `garage`

This is enough to create real product value without turning the feature into a broad camera system.

---

## 13. Future Expansion

Possible later work:
- `driveway` and `perimeter` roles
- stronger correlation with locks and door sensors
- package/visitor style future features
- optional snapshot links in diagnostics

These are explicitly out of scope for the first slice.
