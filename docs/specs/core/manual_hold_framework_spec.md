# Manual Hold Framework Spec

**Status:** Active — initial runtime contract implemented on `feat/v2`  
**Date:** 2026-06-25  
**Motivation source:** Phase AE audit and Phase AB smart-lighting manual override behavior

## Purpose

Manual hold is the runtime mechanism that makes Heima stop acting when a human has taken direct
control of an actuator.

This spec defines one shared manual-hold framework for all automations instead of keeping separate
domain-specific implementations for lighting, heating, camera privacy, and future entity actions.

The framework must support both:

- **implicit holds**, derived from an external state change that was not caused by Heima;
- **explicit holds**, derived from configured helper entities such as `input_boolean.*`.

## Existing Overlap

This construct intentionally overlaps with and should absorb these existing mechanisms:

| Existing mechanism | Current behavior | Target relationship |
|---|---|---|
| Smart-lighting manual override | `RoomSmartLightingAssistReaction` owns pending applies, external OFF -> `manual_override_active`, external ON -> `manual_on_hold`. | Move classification and hold state to the shared framework; keep smart-lighting release policy as a domain-specific policy. |
| `LightingReactionGuardBehavior` | Blocks reaction-generated `lighting` steps when `heima_lighting_hold_{room_id}` is active. | Replace with a manual-hold policy for room-scoped lighting holds. |
| Heating manual hold | Heating domain checks `heima_heating_manual_hold` and climate manual override. | Represent as domain/entity-scoped explicit or implicit holds. |
| `EntityReactionGuardBehavior` | Generic apply filter exists but is not wired into runtime; derives helper names from target entity. | Replace or refactor into a thin adapter around the shared framework. |
| AE `manual_hold_entity` | Validated in camera evidence config, but not consumed by runtime. | Become an explicit hold source for camera privacy scopes. |

Normative rule:

- No new automation type should implement its own manual-hold state machine unless the shared
  framework cannot express its required scope or release policy.

## Goals

1. Classify actuator state changes as Heima-owned or external.
2. Activate a manual hold when an external change means the user has taken control.
3. Allow configured helper entities to activate explicit holds.
4. Block automatic apply steps whose scope is currently held.
5. Keep release semantics configurable per automation family.
6. Expose diagnostics explaining why a step was held and how the hold can clear.

## Non-goals

- Persistent cross-restart manual hold history for implicit holds.
- Replacing proposal approval, reaction muting, or engine enable/disable.
- Inferring user intent from long historical behavior.
- Bypassing safety constraints. Manual hold is an additional block, not a safety override.

## Core Concepts

### ManualHoldScope

A hold applies to a scope, not only to an entity.

```python
@dataclass(frozen=True)
class ManualHoldScope:
    domain: str              # "light", "switch", "climate", "lighting", ...
    subject_type: str        # "entity" | "room" | "reaction" | "domain"
    subject_id: str          # entity_id, room_id, reaction_id, or domain key
```

Examples:

| Use case | Scope |
|---|---|
| Smart lighting room override | `ManualHoldScope("light", "room", "studio")` |
| Camera privacy switch | `ManualHoldScope("switch", "entity", "switch.front_door_privacy")` |
| Heating global manual hold | `ManualHoldScope("climate", "domain", "heating")` |
| One specific reaction | `ManualHoldScope("light", "reaction", "smart-lighting-studio")` |

### ManualHoldReason

```python
@dataclass(frozen=True)
class ManualHoldReason:
    kind: str                # "external_off" | "external_on" | "helper_on" | "domain_override"
    source_entity: str       # entity that caused or represents the hold
    message: str
```

### ManualHoldState

```python
@dataclass
class ManualHoldState:
    scope: ManualHoldScope
    reason: ManualHoldReason
    started_monotonic: float
    expires_monotonic: float | None
    release_policy: str      # "timer" | "presence_cycle" | "helper_off" | "manual_clear"
```

Implicit holds are in-memory. Explicit helper-backed holds are re-derived from current HA/helper
state after restart or options reload.

## Pending Apply Provenance

The framework must keep the smart-lighting invariant: Heima must not mistake its own service call
for a user override.

### PendingApply

```python
@dataclass
class PendingApply:
    entity_id: str
    expected_domain: str
    expected_state: str | None
    timestamp: float
    ttl: float = 5.0
    expected_attributes: dict[str, Any] = field(default_factory=dict)
    source_reaction_id: str | None = None
    source_reaction_type: str | None = None
    scope: ManualHoldScope | None = None
```

The execution layer registers a pending apply:

- after apply-plan filtering;
- immediately before `async_call`;
- for entity-based domains that support manual-hold classification.

Initial supported domains:

| Domain | Expected state | Attribute matching |
|---|---|---|
| `light` | `on` / `off` | brightness +/- 5, color temperature +/- 100 K when present |
| `switch` | `on` / `off` | no attribute matching |
| `input_boolean` | `on` / `off` | no attribute matching |
| `climate` | optional, domain-specific | deferred to heating implementation |

Normative rule:

- Pending apply registration must not happen inside `Reaction.evaluate()`, because later filters may
  block the step.

## State Change Classification

For every tracked actuator state change:

1. Resolve the entity's manual-hold scope(s).
2. Try to match and consume a pending apply for that entity.
3. If a pending apply matches, classify as `heima_owned` and do not activate a hold.
4. If no pending apply matches, classify as `external`.
5. Route the external change to the scope's hold policy.

HA context IDs are not the primary mechanism. They may be diagnostic metadata only.

## Hold Policies

Each automation family may define how external changes map to hold state.

### Smart Lighting Policy

Current behavior must be preserved:

- External `off` on an active profile light:
  - cancel pending dim/off sequence;
  - activate room-scoped `external_off` hold;
  - suppress automatic turn-on until release.
- External `on` while the room automation is active or would be active:
  - activate room-scoped `external_on` hold;
  - suppress profile re-application.
- `external_off` clears on the first of:
  - `manual_override_window_min` expiry;
  - presence lost and then re-detected.
- `external_on` clears only on presence lost and then re-detected.

### Camera Privacy Policy

Target behavior for AE:

- `privacy_entity` maps to an entity-scoped switch hold:
  `ManualHoldScope("switch", "entity", privacy_entity)`.
- Configured `manual_hold_entity` maps to an explicit helper-backed hold for that scope.
- External state changes on `privacy_entity` activate an implicit hold for that entity unless
  matched by a pending Heima apply.
- The default release policy for implicit camera privacy holds is `manual_clear` unless configured
  otherwise. Heima must not automatically resume changing camera privacy after a user manually
  changes it without an explicit release rule.

### Heating Policy

Target behavior:

- `heima_heating_manual_hold` becomes a domain-scoped explicit hold:
  `ManualHoldScope("climate", "domain", "heating")`.
- Future per-thermostat manual override can become entity-scoped:
  `ManualHoldScope("climate", "entity", climate_entity)`.
- Release policy remains helper-off or explicit user action unless a domain-specific policy is
  approved.

## Apply Filtering

The engine apply-filter phase must query manual hold state before executing entity actions.

Conceptual API:

```python
class ManualHoldManager:
    def register_scope(self, scope: ManualHoldScope, policy: ManualHoldPolicy) -> None: ...
    def register_explicit_hold_entity(self, scope: ManualHoldScope, entity_id: str) -> None: ...
    def register_pending_apply(self, step: ApplyStep) -> None: ...
    def handle_state_changed(self, entity_id: str, new_state: Any) -> None: ...
    def held_reason_for_step(self, step: ApplyStep) -> str: ...
    def release_scope(self, scope: ManualHoldScope, *, reason: str) -> None: ...
    def diagnostics(self) -> dict[str, Any]: ...
```

Apply filtering rule:

- If `held_reason_for_step(step)` returns a non-empty value, the engine sets
  `step.blocked_by = "manual_hold:<scope>:<reason>"`.
- Manual hold must not overwrite an existing `blocked_by` reason.
- Manual hold filtering happens after reaction steps are merged into the apply plan and before
  execution.

## Scope Resolution From ApplyStep

Each automation that emits entity steps must provide enough metadata to resolve hold scope.

Preferred sources:

1. `ApplyStep.source = "reaction:<id>"` to resolve reaction-owned scope.
2. `ApplyStep.params["entity_id"]` for entity-scoped actions.
3. Domain-specific ownership mapping, such as room ID for smart lighting.

The framework must not infer reaction ownership from entity ID alone when registering pending
applies. Entity-only inference is allowed only for entity-scoped hold checks.

## Diagnostics

Diagnostics must expose:

- active holds by scope;
- reason kind and source entity;
- age and expiry when applicable;
- explicit hold helper state;
- pending apply count by domain;
- blocked apply count by scope;
- last external change per tracked scope.

Example:

```json
{
  "active_holds": [
    {
      "scope": "switch:entity:switch.front_door_privacy",
      "reason": "helper_on",
      "source_entity": "input_boolean.front_door_privacy_hold",
      "release_policy": "helper_off"
    }
  ],
  "pending_applies": {
    "light": 1,
    "switch": 0
  }
}
```

## Options Flow Contract

Automation configuration may declare explicit hold helpers.

Examples:

```yaml
manual_hold_entity: input_boolean.front_door_privacy_hold
```

or, for room-scoped automations:

```yaml
manual_hold_entity: input_boolean.studio_lighting_hold
```

Validation rules:

- explicit hold helpers must be `input_boolean.*` unless a future spec approves other helper types;
- helper-backed holds are optional;
- missing helper does not disable implicit external override detection for automations that support
  it.

## Migration Plan

### Phase MH1 — Framework skeleton

- Status: implemented.
- Added `ManualHoldScope`, `ManualHoldReason`, `ManualHoldState`, `PendingApply`, and
  `ManualHoldManager`.
- Wired manager into engine diagnostics.

### Phase MH2 — Smart-lighting adoption

- Status: implemented.
- Moved pending apply storage and external state-change classification from
  `RoomSmartLightingAssistReaction` into `ManualHoldManager`.
- Current smart-lighting release policy remains reaction-owned.

### Phase MH3 — Central apply-filter integration

- Status: implemented.
- Added manager-backed hold filtering after domain/reaction steps are merged and before execution.
- Existing `blocked_by` reasons are preserved.
- Pending apply registration remains after filtering and immediately before service calls.

### Phase MH4 — AE camera privacy adoption

- Status: implemented.
- Registered privacy switch scopes from `camera_evidence_sources`.
- Used `manual_hold_entity` as explicit hold source.
- Registered pending switch applies before executing `switch.turn_on` / `switch.turn_off`.
- Routed `switch.*` state changes for configured `privacy_entity` values to the manager.
- Blocked privacy switch steps while held.

### Phase MH5 — Legacy guard cleanup

- Status: implemented.
- Removed `EntityReactionGuardBehavior`.
- Removed `LightingReactionGuardBehavior`.
- Replaced lighting room manual-hold runtime blocking with manager-backed room scopes.

### Phase MH6 — Heating adoption

- Status: implemented for explicit heating hold.
- Represented `heima_heating_manual_hold` through a manager-backed domain scope.
- Preserved current heating behavior.

## Acceptance Criteria

- [x] Smart-lighting manual OFF still suppresses automatic turn-on.
- [x] Smart-lighting manual ON still suppresses profile re-application.
- [x] Heima-owned light changes do not activate manual hold.
- [x] Camera privacy `switch.*` changes made by Heima do not activate manual hold.
- [x] Camera privacy `switch.*` changes made externally activate hold for that camera scope.
- [x] `manual_hold_entity` blocks camera privacy actions while on.
- [x] Held steps are marked with `blocked_by` and are not executed.
- [x] Diagnostics show active holds and pending applies.
- [ ] Full `scripts/ci_local.sh` pass documented.
