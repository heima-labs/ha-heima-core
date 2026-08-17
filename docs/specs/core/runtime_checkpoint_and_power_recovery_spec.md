# Runtime Checkpoint and Power Recovery Spec

**Status:** Draft vNext
**Date:** 2026-08-17
**Scope:** Runtime checkpointing, Home Assistant restart recovery, power outage recovery,
startup stabilization, observability
**Related specs:** `core/admin_observability_panel_spec.md`,
`core/manual_hold_framework_spec.md`, `core/apply_step_contract.md`,
`core/resident_runtime_confirmation_spec.md`, `core/runtime_scheduler_spec.md`,
`domains/house_state_spec.md`, `domains/heating_spec.md`,
`domains/security_presence_simulation_spec.md`

## Purpose

Heima must behave conservatively and explainably when the home loses power, when Home Assistant
restarts, or when many devices temporarily become unavailable.

Power failures create two different runtime problems:

1. Home Assistant may stay online while parts of the house go offline.
2. Home Assistant may shut down and later restart without observing what happened during downtime.

This spec defines a shared runtime checkpoint and recovery model so Heima can:

- avoid treating outage-related state changes as normal human behavior;
- avoid creating false manual holds from power-restore state changes;
- avoid learning from incomplete or unstable snapshots;
- avoid firing non-critical automations during startup instability;
- explain recovery state in the admin observability panel.

## Product Principle

Runtime recovery is an explanation and guardrail layer, not a restore engine.

Normative rule:

> Heima must never blindly restore old checkpoint state over current Home Assistant state.

Home Assistant's current entity states remain the physical source of truth after startup. The Heima
runtime checkpoint is a recovery hint used to classify uncertainty, stabilize evaluation, and
preserve short-lived context where doing so is safe.

## Scenarios

### Scenario A — Home Assistant Survives on Battery or UPS

Home Assistant and Heima remain running, but some or all home devices may lose power or network.

Expected observations:

- large groups of entities may become `unavailable` or `unknown`;
- gateways may disappear, making battery sensors unreachable;
- routers, bridges, alarm panels, climate devices, and switches may recover at different times;
- Heima may continue receiving partial signals;
- periodic fallback evaluations may still run;
- runtime memory remains available.

Risk:

- partial data can be mistaken for real absence, occupancy loss, manual overrides, device faults,
  or learned behavior changes.

Target behavior:

- detect degraded power/connectivity conditions while HA remains online;
- enter a recovery/degraded mode when too many critical entities become unavailable;
- suppress learning and absence-based anomalies while recovery is active;
- classify outage-related state changes as recovery transitions, not external manual actions;
- avoid non-critical apply steps until the house state is stable again.

### Scenario B — Home Assistant Shuts Down

Home Assistant and Heima stop running. Heima does not observe the outage period.

Expected observations after power returns:

- Home Assistant restarts;
- Heima runtime memory starts empty except for persisted stores and the latest runtime checkpoint;
- devices report current physical state in bursts;
- some entities may restore old HA state before real device state is available;
- runtime event buffers and decision traces from before restart may be gone or partial.

Risk:

- Heima may interpret the first post-startup snapshot as normal current behavior;
- state changes that happened while HA was down may be misclassified as user actions;
- runtime confirmations or pending applies may be stale;
- automations may fire before devices have settled.

Target behavior:

- load the latest checkpoint if it is valid and recent enough;
- compare it with current HA state without overwriting HA state;
- mark differences as `unknown_during_downtime` or `power_restore_candidate`;
- enter startup recovery for a bounded stabilization window;
- invalidate unsafe runtime-only pending work;
- restart normal automation only after a stable post-recovery snapshot.

## Goals

1. Persist a compact runtime checkpoint with enough context to reason about restart recovery.
2. Detect startup and power-restore conditions.
3. Stabilize runtime evaluation after restart or mass entity recovery.
4. Prevent false manual holds caused by power restore.
5. Prevent false learning/anomaly signals from unavailable or incomplete data.
6. Expose recovery state and checkpoint metadata in diagnostics and admin observability.
7. Preserve safety-critical behavior where delaying would be worse than acting.

## Non-Goals

- Full Home Assistant state backup or restore.
- Replaying missed Home Assistant events from the outage period.
- Persisting every decision trace or runtime event indefinitely.
- Making actionable runtime confirmations fully restart-safe.
- Restoring physical devices to pre-outage state automatically.
- Inferring exact outage cause without reliable input signals.

## Terminology

### Runtime Checkpoint

A persisted compact snapshot of selected Heima runtime state and selected Home Assistant entity
state.

It is used for recovery comparison and diagnostics. It is not used as an authoritative replacement
for current HA state.

### Startup Recovery

A bounded runtime mode entered after Home Assistant or Heima startup when current state may be
incomplete or unstable.

### Power Recovery

A bounded runtime mode entered when Heima detects likely power loss or mass device recovery while
Home Assistant stayed online.

### Stable Snapshot

A post-recovery `HouseSnapshot` produced after critical inputs have been available for the required
stabilization window.

### Critical Entity

An entity whose availability or state materially affects Heima's safety, house-state inference, or
runtime apply decisions.

Examples:

- alarm control panel;
- presence/person entities;
- occupancy source entities;
- room/device gateways when represented as entities;
- configured light/switch/climate targets;
- configured camera privacy switches;
- heating climate entity and heating timing helpers;
- notification helper entities where configured.

## Runtime Checkpoint Contract

### Storage Semantics

The checkpoint must be persisted in Home Assistant storage under the Heima integration namespace.

Properties:

- per config entry;
- atomic write or replace;
- bounded size;
- versioned schema;
- tolerant reader for older versions;
- redacted diagnostics when exported.

Checkpoint persistence must not block the main evaluation path.

### Checkpoint Is Not Source of Truth

On startup:

1. Load latest checkpoint.
2. Read current HA state.
3. Compare checkpoint and current HA state.
4. Classify differences.
5. Continue from current HA state, with recovery guardrails.

The checkpoint must not directly set HA entities, Heima sensors, reaction state, or house state.

### Minimum Checkpoint Payload

```yaml
schema_version: 1
checkpoint_id: string
entry_id: string
created_at: iso8601
ha_started_at: iso8601 | null
heima_started_at: iso8601 | null
reason: periodic | important_change | before_apply | after_apply | shutdown | manual

runtime:
  house_state: string
  house_state_reason: string
  security_state: string
  anyone_home: boolean
  people_present: [string]
  occupied_rooms: [string]
  last_decision: string
  last_snapshot_id: string
  last_snapshot_ts: iso8601 | null

critical_entities:
  - entity_id: string
    domain: string
    state: string
    attributes:
      # allowlisted attributes only
    last_changed: iso8601 | null
    last_updated: iso8601 | null

manual_hold:
  active_explicit_holds: [...]
  active_implicit_holds: [...]
  pending_applies: [...]

runtime_confirmation:
  pending_request_ids: [string]

heating:
  climate_entity: string
  hvac_mode: string | null
  preset_mode: string | null
  target_temperature: number | null
  current_temperature: number | null
  heima_branch: string
  heima_reason: string
  last_applied_target: number | null

observability:
  last_event_ids: [string]
  last_trace_ids: [string]
```

### Attribute Allowlist

Checkpointed attributes must be domain-specific and minimal.

Examples:

| Domain | Attributes |
|---|---|
| `climate` | `hvac_mode`, `preset_mode`, `temperature`, `current_temperature`, `hvac_action` |
| `light` | `brightness`, `color_temp_kelvin`, `rgb_color` |
| `switch` | none by default |
| `alarm_control_panel` | alarm state only unless integration-specific attributes are explicitly needed |
| `person` | none by default |
| `binary_sensor` | `device_class` only when useful |

Normative rule:

- Checkpoint persistence must not store secrets, tokens, auth data, GPS coordinates, or large raw
  attribute blobs.

## Checkpoint Write Policy

### Required Write Triggers

Heima must write a checkpoint:

- after a stable house-state change;
- after a security-state change;
- after a successful apply that changes a critical target;
- after a manual hold is activated, cleared, or materially changed;
- after a runtime confirmation is created, approved, dismissed, cancelled, or times out;
- after startup recovery exits;
- periodically when runtime state changed since the previous checkpoint.

### Periodic Write Cadence

Target default:

- 60 seconds when relevant runtime state changed;
- no periodic write when nothing material changed;
- debounce writes to avoid storage churn.

The implementation may use a longer interval if Home Assistant storage pressure requires it, but
must still write after important changes.

### Shutdown Write

If Home Assistant provides a reliable stop/unload hook, Heima should attempt a final checkpoint with
`reason=shutdown`.

This checkpoint is best-effort only. Recovery must not depend on it being present.

## Startup Recovery State Machine

### Recovery States

```text
normal
startup_recovery
power_recovery
degraded_recovery
recovery_settling
```

### Startup Entry Conditions

Heima must enter `startup_recovery` when:

- Home Assistant starts or reloads the integration;
- no valid checkpoint exists;
- the latest checkpoint is older than the configured freshness threshold;
- `ha_started_at` changed since the latest checkpoint;
- the latest checkpoint cannot be read or fails validation.

### Power Recovery Entry Conditions

Heima should enter `power_recovery` when HA stayed online but runtime observes one or more of:

- mass transition of critical entities to `unavailable` / `unknown`;
- mass transition from `unavailable` / `unknown` back to available;
- configured UPS/power sensor indicates outage or restore;
- network/gateway entities indicate outage or restore;
- a large gap in expected periodic snapshots while HA stayed running.

### Degraded Recovery

`degraded_recovery` is used when recovery cannot complete because critical inputs remain
unavailable beyond the stabilization timeout.

Heima may still operate in a limited mode, but observability must make the degraded reason explicit.

### Exit Conditions

Heima exits recovery when all are true:

- minimum stabilization window elapsed;
- critical entity availability is above threshold;
- at least one stable `HouseSnapshot` has been produced;
- house state was resolved using current HA state;
- no required recovery reconciliation remains pending.

Default stabilization window:

- startup recovery: 120 seconds;
- power recovery after HA stayed online: 60 seconds;
- degraded recovery timeout: 10 minutes.

These values should be configurable later, but the first implementation may use constants if
configuration would materially increase scope.

## Runtime Behavior During Recovery

### Learning

During recovery:

- do not submit new learned proposals;
- do not update learned baselines from unstable snapshots;
- do not treat recovery snapshots as positive or negative behavioral evidence;
- mark recovery snapshots with a source/reason so future analyzers can exclude them.

After recovery:

- learning resumes from stable snapshots only.

### Anomaly Detection

During recovery, Heima must suppress anomaly rules whose evidence depends on missing or unstable
signals.

Suppressed examples:

- `sensor_activity_drop`;
- `ghost_activity`;
- `extended_absence`;
- `presence_pattern_drift`;
- lighting/device drift caused only by unavailable/restore transitions.

Not automatically suppressed:

- safety-critical active hazards, if the underlying signal is current and reliable;
- explicit security mismatch if alarm and presence inputs are both available and stable.

### Manual Hold

Power restore must not look like a human manual override.

If an actuator changes state during recovery and there is no matching pending apply:

- classify as `recovery_state_change`, not `external_user_change`;
- do not activate an implicit manual hold by default;
- record diagnostics explaining the classification.

Explicit helper-backed holds are re-derived from current helper state after startup.

Implicit in-memory holds:

- may be restored from checkpoint only if their release policy and scope make restart-safe recovery
  explicit;
- otherwise must be dropped or marked `unknown_after_restart`.

### Pending Applies

Pending applies are short-lived and must not be blindly restored.

On startup:

- pending applies older than their TTL are discarded;
- pending applies without a reliable HA context/provenance are discarded;
- pending applies from before HA downtime must not be used to classify post-restart entity changes
  as Heima-owned.

During HA-online power recovery:

- pending applies may still match if within TTL and the entity transition is observed normally;
- if a mass restore is in progress, pending-apply matching should be conservative.

### Runtime Confirmations

Pending runtime confirmation requests remain governed by
`core/resident_runtime_confirmation_spec.md`.

Current vNext baseline:

- runtime confirmations are in-memory and not fully restart-safe;
- a restart cancels or forgets pending runtime requests;
- old notification responses after restart must not apply stale steps;
- `on_timeout` is not executed for requests lost during restart.

Checkpoint may store pending request IDs for diagnostics only unless a future restart-safe runtime
confirmation store is explicitly implemented.

### Reactions and Apply Steps

During recovery:

- non-critical auto-apply reactions should be suspended;
- reaction evaluation may run in inspection mode for observability;
- apply plans may be generated but blocked with reason `startup_recovery` or `power_recovery`;
- safety-critical reactions may be allowed by explicit policy.

Examples of generally suspendable actions:

- lighting ambience;
- camera privacy comfort policies that are not security-critical;
- heating preference setpoints;
- learned routines;
- notification-only learning prompts.

Examples of actions that may remain eligible:

- alarm/security privacy policies when security state is stable;
- safety shutoff actions;
- explicit admin commands.

## Domain-Specific Notes

### House State

House state during recovery must distinguish:

- the last checkpointed state;
- the current resolved state;
- whether the current state is stable.

`vacation`, `guest`, and explicit override states remain hard signals if their source entities are
available and stable.

If presence signals are unavailable, Heima must not infer `away` only from sensor silence during
recovery.

### Security

Security state is high priority.

If the alarm panel is available and stable, Heima may use current security state even during
recovery.

If the alarm panel is unavailable:

- security-dependent reactions must be blocked unless explicitly safe;
- observability must report `security_state_unavailable`.

### Heating

Heating recovery must preserve current physical climate state as observed from HA.

The checkpoint may explain:

- last Heima branch;
- last Heima target;
- pre-outage setpoint;
- current post-recovery `hvac_mode`, `preset_mode`, and target temperature.

Heima must not reapply heating targets during startup recovery unless:

- heating branch is explicitly safety-critical; or
- recovery has completed; or
- an admin explicitly requests apply.

If current climate state changed while HA was down, classify it as
`unknown_during_downtime`, not as a user manual override and not as Heima-owned.

### Lighting and Switches

Many lights and switches have power-on defaults.

During recovery:

- light/switch changes caused by restore must not create implicit manual holds;
- smart-lighting reactions must not immediately reapply scenes until stabilization exits;
- power-restore state may be exposed as entity impact detail.

### Camera Privacy

Camera privacy policies may be security-sensitive.

During recovery:

- if alarm state is available and stable, security-driven privacy enforcement may run after the
  minimum stabilization window or sooner by explicit policy;
- if alarm state is unavailable, privacy apply should be blocked and surfaced as degraded security
  context;
- manual privacy switch changes during restore must not create permanent implicit holds unless a
  real external change is observed after recovery.

### Vacation Presence Simulation

Vacation presence simulation must not interpret startup/power recovery as human behavior.

During recovery:

- source profile learning is suspended;
- scheduled simulation events may be skipped or delayed until recovery exits;
- skipped/delayed simulation must be observable.

## Observability Requirements

Admin observability must expose:

- current recovery state;
- recovery reason;
- recovery start timestamp;
- stabilization deadline;
- checkpoint age;
- checkpoint reason;
- whether HA restarted since checkpoint;
- critical entity availability summary;
- entity differences between checkpoint and current state;
- blocked apply steps caused by recovery;
- skipped learning/anomaly reasons;
- last stable snapshot timestamp.

Suggested snapshot shape:

```yaml
recovery:
  state: normal | startup_recovery | power_recovery | degraded_recovery | recovery_settling
  reason: string
  started_at: iso8601 | null
  stabilization_deadline: iso8601 | null
  checkpoint:
    checkpoint_id: string | null
    created_at: iso8601 | null
    age_s: number | null
    reason: string | null
    valid: boolean
  ha:
    restarted_since_checkpoint: boolean
    ha_started_at: iso8601 | null
  critical_entities:
    total: number
    available: number
    unavailable: number
    changed_since_checkpoint: number
  blocked_apply_steps:
    total: number
    examples: [...]
```

Runtime Activity must include events such as:

- `recovery.startup_started`;
- `recovery.power_outage_suspected`;
- `recovery.power_restored`;
- `recovery.stabilization_started`;
- `recovery.completed`;
- `recovery.degraded`;
- `recovery.checkpoint_written`;
- `recovery.checkpoint_invalid`.

## Event Catalog Additions

Events should use the `system` family unless a more specific domain owns the condition.

| Event type | Severity | Meaning |
|---|---|---|
| `recovery.startup_started` | `info` | Heima entered startup recovery after HA/integration startup. |
| `recovery.power_outage_suspected` | `warning` | Mass unavailability or power signal suggests outage while HA stayed online. |
| `recovery.power_restored` | `info` | Critical entities are returning after suspected outage. |
| `recovery.completed` | `info` | Recovery exited and normal runtime resumed. |
| `recovery.degraded` | `warning` | Recovery could not complete because critical inputs remain unavailable. |
| `recovery.checkpoint_written` | `debug` or `info` | Runtime checkpoint persisted. |
| `recovery.checkpoint_invalid` | `warning` | Stored checkpoint could not be used. |

Notification routing should follow `events_and_notifications_spec.md`:

- ordinary startup recovery is observability-only;
- degraded recovery may notify admins after persistence threshold;
- security-relevant degraded recovery may notify admins and residents according to audience policy;
- actionable runtime confirmations are not sent during recovery unless explicitly allowed.

## Configuration

Initial implementation may use constants. The long-term configuration model should support:

```yaml
recovery:
  enabled: true
  checkpoint_interval_s: 60
  startup_stabilization_s: 120
  power_restore_stabilization_s: 60
  degraded_timeout_s: 600
  critical_entity_unavailable_ratio: 0.35
  suppress_noncritical_apply: true
  suppress_learning: true
  suppress_absence_anomalies: true
```

These settings should not be exposed before the behavior is proven stable. Defaults must be safe for
non-expert admins.

## Diagnostics and Support

The diagnostics payload must include enough information to answer:

1. Did HA restart?
2. Did Heima load a checkpoint?
3. How old was the checkpoint?
4. Which critical entities changed during downtime or recovery?
5. Which actions were blocked because of recovery?
6. Which learning/anomaly paths were suppressed?
7. When did recovery start and end?

Diagnostics must not require raw Home Assistant logs for normal recovery explanation.

## Testing Requirements

Unit tests:

- checkpoint serialization/deserialization;
- version tolerance;
- redaction;
- write debounce;
- startup recovery entry with no checkpoint;
- startup recovery entry with stale checkpoint;
- recovery exit after stable critical entities;
- mass unavailable -> power recovery;
- mass restore -> settling;
- recovery suppresses learning/anomaly;
- recovery blocks non-critical apply;
- recovery does not create implicit manual holds for restore changes.

Integration tests:

- HA restart with valid checkpoint;
- HA restart with stale checkpoint;
- climate state changed during downtime;
- light state changed during downtime;
- camera privacy switch state changed during downtime;
- pending runtime confirmation before restart is forgotten and cannot apply stale steps.

Live tests:

- controlled restart of the HA test container;
- simulated unavailable/available burst for critical entities;
- observability export contains recovery state and checkpoint metadata.

## Open Questions

1. Which HA source should be used for reliable `ha_started_at` across supported versions?
2. Should checkpoint storage be a separate store file or part of existing coordinator/runtime store?
3. Which action families should be explicitly allowed during recovery in the first implementation?
4. Should admins be able to manually end recovery from the observability panel?
5. Should recovery windows be configurable in the first implementation or only after field testing?

## Acceptance Criteria

- Heima writes compact runtime checkpoints after important runtime changes.
- After HA restart, Heima enters startup recovery and exposes why.
- During recovery, non-critical apply steps are blocked with explicit recovery reasons.
- During recovery, learning and absence-based anomaly rules do not consume unstable snapshots.
- Power-restore actuator changes do not create implicit manual holds.
- After stabilization, Heima exits recovery and resumes normal runtime from current HA state.
- Admin observability shows checkpoint age, recovery state, entity differences, and blocked actions.
- The implementation is covered by unit, integration, and live restart tests.
