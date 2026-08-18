# Runtime Checkpoint and Power Recovery Spec

**Status:** Planned — not implemented on `main`
**Date:** 2026-08-17
**Scope:** Runtime checkpointing, Home Assistant restart recovery, power outage recovery,
startup stabilization, observability
**Related specs:** `core/admin_observability_panel_spec.md`,
`core/manual_hold_framework_spec.md`, `core/apply_step_contract.md`,
`core/resident_runtime_confirmation_spec.md`, `core/runtime_scheduler_spec.md`,
`core/events_and_notifications_spec.md`, `core/event_catalog_spec.md`,
`core/security_mismatch_generalization_spec.md`, `domains/house_state_spec.md`,
`domains/heating_spec.md`, `domains/security_presence_simulation_spec.md`

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

## Architecture Integration

### Recovery State Is Engine Context, Not A Domain

Recovery classification does not run as a core domain and is not a plugin. It runs as a core
runtime facility, in the same category as the Runtime Scheduler (`core/runtime_scheduler_spec.md`)
and the Manual Hold Manager (`core/manual_hold_framework_spec.md`): a shared component consulted
directly by domains, plugins, and the apply layer, not a node in the fixed core DAG
(`People -> Occupancy -> Activity -> HouseState`, then plugins).

Recovery state is computed once per evaluation cycle, before the core DAG runs, from current raw HA
entity state and the persisted checkpoint. It is exposed as read-only context for the remainder of
that same cycle.

This follows the same treatment already given to wall-clock time: time is context, not a domain
output, and is available to every domain within the current cycle without violating the rule that
domains read CanonicalState from the previous cycle. Recovery state is context in the same sense.
That rule governs domain-to-domain data flow inside the DAG; it does not apply to engine-computed
pre-DAG context, exactly as it does not apply to the current timestamp.

Consequence: recovery state must never lag by a full evaluation cycle. A mass-unavailable
transition detected at the start of a cycle must be visible, in that same cycle, to House State,
Security, Heating, the Manual Hold Manager, and anomaly analyzers before they act on it.

### Exposure

Recovery state is not plugin state and must not use the `plugin_id.key` CanonicalState namespace
reserved for plugins. It is exposed under a reserved engine-owned namespace (e.g. `runtime.recovery.*`),
read-only for all consumers.

Consumers must treat this namespace as computed context: never write to it, and never treat its
absence as an error before the runtime checkpoint/recovery component has finished initializing for
the current cycle.

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

### Degraded Recovery

A bounded-but-open-ended runtime mode entered when `startup_recovery` or `power_recovery` cannot
complete because critical entity availability remains below threshold after the stabilization
window elapses. Heima may operate in a limited mode; observability must make the degraded reason
explicit. `degraded_timeout_s` does not force a further state transition — it is the threshold
after which degraded recovery becomes admin-notifiable (see Notification routing in Event Catalog
Additions). Heima remains in `degraded_recovery` until critical entity availability recovers above
threshold, at which point normal Exit Conditions apply.

### Recovery Settling

A transitional sub-phase of `startup_recovery` or `power_recovery`, entered once critical entity
availability has crossed back above threshold but the minimum stabilization window has not yet
elapsed. The same suppression rules as the parent recovery state apply (learning, anomaly
detection, non-critical applies). `recovery_settling` exits to `normal` when Exit Conditions are
met, or reverts to `startup_recovery`/`power_recovery` if critical entity availability drops back
below threshold before the window elapses.

### Unknown During Downtime

A diagnostic label for an entity state difference observed after an HA/Heima restart whose cause
cannot be determined. Used when Heima cannot tell whether a difference is due to power restore,
manual action during downtime, or device behavior. Never used to activate an implicit manual hold
or to classify a change as Heima-owned.

### Power Restore Candidate

A diagnostic label for an entity state difference observed after an HA/Heima restart that
plausibly matches the entity's power-on/restore behavior (for example, a light or switch returning
to its power-on default). Higher confidence than `unknown_during_downtime`, but still not used to
activate an implicit manual hold. Surfaced as entity impact detail per Lighting and Switches below.

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

The recovery critical set is related to, but not identical to, the entity-trigger set. Entity
triggers decide when Heima should evaluate. Recovery critical entities decide whether the current HA
state is complete enough to trust. Therefore the recovery critical set must also include configured
actuators and configured apply targets even when those entities are not state-change triggers for
normal evaluation.

If a configured critical entity is absent from the HA state machine during evaluation, Heima must
classify it as unavailable for recovery purposes. Missing critical entities are runtime evidence, not
only a diagnostics concern: they count in both the unavailable numerator and the critical-entity
denominator.

## Runtime Checkpoint Contract

### Storage Semantics

The checkpoint must be persisted in Home Assistant storage under the Heima integration namespace.
Checkpoint persistence uses a dedicated HA `Store`, separate from snapshots, approvals, proposal
lifecycle state, and event storage:

```yaml
storage_key: heima_runtime_checkpoints
storage_version: 1
data:
  entries:
    <config_entry_id>: <runtime_checkpoint>
```

The dedicated store is the normative storage shape for AQ. Checkpoints are operational recovery
state with different retention, write cadence, redaction, and failure semantics from learning
snapshots or admin proposal state. Keeping them separate prevents checkpoint churn from rewriting
larger stores and lets recovery code fail closed if the checkpoint store is unreadable.

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
  active_implicit_holds: [...]  # diagnostics-only, never restored after restart; see Manual Hold below
  pending_applies: [...]  # diagnostics-only, never restore-eligible; see Pending Applies below

runtime_confirmations:
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
  vacation_curve_start_temp: number | null   # only when heima_branch == vacation_curve
  vacation_curve_started_at: iso8601 | null  # only when heima_branch == vacation_curve

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
- The checkpoint critical-entity list must use the same source of truth as runtime recovery
  classification. A target may not be critical for power recovery while being omitted from the
  checkpoint comparison set.

## Checkpoint Write Policy

### Required Write Triggers

Heima must write a checkpoint:

- after a stable house-state change;
- after a security-state change;
- after a successful apply that changes a critical target;
- after a manual hold is activated, cleared, or materially changed;
- after a runtime confirmation is created, approved, dismissed, cancelled, or times out;
- after recovery exits (a transition from any recovery state — `startup_recovery`, `power_recovery`,
  `degraded_recovery`, or `recovery_settling` — back to `normal`);
- periodically when runtime state changed since the previous checkpoint.

### Periodic Write Cadence

Periodic checkpoint writes must be registered as a keyed job on the Runtime Scheduler
(`core/runtime_scheduler_spec.md`, `job_id=recovery.checkpoint.write`, `owner=recovery`), not
implemented as an ad hoc timer. Keyed scheduling already provides the debounce/replace semantics
this policy needs: re-registering the same `job_id` after a material change replaces the pending
timer instead of stacking a second one.

Target default:

- 60 seconds when relevant runtime state changed;
- no periodic write when nothing material changed;
- debounce writes to avoid storage churn, via keyed job replacement rather than bespoke debounce
  logic.

The implementation may use a longer interval if Home Assistant storage pressure requires it, but
must still write after important changes.

### Shutdown Write

If Home Assistant provides a reliable stop/unload hook, Heima should attempt a final checkpoint with
`reason=shutdown`.

This checkpoint is best-effort only. Recovery must not depend on it being present.

Checkpoint writes must be guarded at the public write boundary. By default,
`async_write_runtime_checkpoint` must refuse to write while recovery is active, including service
commands and shutdown writes. A force path may exist only for explicit diagnostics/tests and must be
auditable.

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
- the latest checkpoint cannot be read or fails validation.

When both the current Home Assistant start timestamp and checkpoint `ha_started_at` are known, a
changed value is reported as `restarted_since_checkpoint=true` and confirms that startup recovery is
required. It does not by itself make a fresh, parseable checkpoint unusable: Scenario B depends on
using that checkpoint as a comparison hint after HA restarts.

### Power Recovery Entry Conditions

Heima should enter `power_recovery` when HA stayed online but runtime observes one or more of:

- the fraction of critical entities that are `unavailable` / `unknown` crosses above
  `critical_entity_unavailable_ratio` (default 0.35, see Configuration) — "mass transition";
- mass transition from `unavailable` / `unknown` back to available;
- configured UPS/power sensor indicates outage or restore;
- network/gateway entities indicate outage or restore;
- a large gap in expected periodic snapshots while HA stayed running.

### Degraded Recovery

`degraded_recovery` is entered when `startup_recovery` or `power_recovery` cannot complete because
critical entity availability remains below threshold after the applicable stabilization window
(120 seconds for startup, 60 seconds for power recovery) elapses. See Terminology for full
semantics, including the role of `degraded_timeout_s`.

### Exit Conditions

Heima exits recovery when all are true:

- minimum stabilization window elapsed;
- critical entity availability is above threshold — the same `critical_entity_unavailable_ratio`
  used for Power Recovery Entry Conditions, checked in the opposite direction (fraction unavailable
  below the ratio). The first implementation uses one symmetric ratio with no separate hysteresis
  band;
- at least one stable `HouseSnapshot` has been produced;
- house state was resolved using current HA state;
- no required recovery reconciliation remains pending.

Default stabilization window:

- startup recovery: 120 seconds;
- power recovery after HA stayed online: 60 seconds;
- degraded recovery timeout: 10 minutes.

These values should be configurable later, but the first implementation may use constants if
configuration would materially increase scope.

### Deadline Rechecks Must Be Scheduled

Heima's evaluation cycle is event-driven with a 300-second fallback (see architecture
non-negotiable: time is context, not trigger). All stabilization windows above default to less than
300 seconds. If no entity state change happens to trigger a re-evaluation during the window, exit
from recovery must not silently wait for the 300-second fallback — that would delay stabilization
well past its stated default.

Two one-shot Runtime Scheduler jobs are involved, registered at different moments, not both at
initial recovery entry:

- `job_id=recovery.stabilization` (`owner=recovery`) is registered the moment
  `startup_recovery` or `power_recovery` is entered, firing at the applicable stabilization window
  (120s / 60s), so Exit Conditions are rechecked regardless of entity churn.
- `job_id=recovery.degraded_timeout` (`owner=recovery`) becomes due only after
  `degraded_recovery` is actually entered — i.e., when the stabilization deadline job fires without
  Exit Conditions being met. Implementations may keep the same job idempotently scheduled while the
  runtime remains in `degraded_recovery`, but must not move it later. It fires at
  `degraded_timeout_s` (default 600s) *after entering `degraded_recovery`*, which is when
  Notification routing's admin-notify threshold applies (not
  600s after the original outage/restart).

Both jobs are cancelled/replaced if recovery exits earlier through a normal evaluation cycle.

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

- classify as `external`, per the existing State Change Classification contract in
  `core/manual_hold_framework_spec.md`; recovery does not add a new classification value to that
  contract;
- before activating an implicit hold, the Manual Hold Manager checks engine-level recovery state
  via the `runtime.recovery.*` context (see Architecture Integration); if recovery is active for
  the affected scope, implicit hold activation is skipped by default;
- tag the suppressed activation `recovery_state_change` in diagnostics/observability only — this is
  a diagnostic label, not a manual-hold classification value;
- record diagnostics explaining the suppression.

Explicit helper-backed holds are re-derived from current helper state after startup, per
`core/manual_hold_framework_spec.md`.

Implicit in-memory holds are never restored from the checkpoint after a restart. This matches
`core/manual_hold_framework_spec.md`'s explicit non-goal ("persistent cross-restart manual hold
history for implicit holds") and its existing rule that implicit holds are in-memory only. The
checkpoint's `manual_hold.active_implicit_holds` field (see Minimum Checkpoint Payload) is
diagnostics-only, mirroring `pending_applies` and `runtime_confirmation.pending_request_ids`: it
explains what was active right before shutdown, but no runtime logic reads it back to reconstruct
hold state. After a restart, any actuator state that would have matched a pre-restart implicit hold
is simply subject to the normal recovery classification rules above (`external`, gated activation).

### Pending Applies

Pending applies are short-lived (`PendingApply.ttl`, default 5.0 seconds per
`core/manual_hold_framework_spec.md`) and must not be blindly restored. This distinguishes the two
recovery scenarios sharply:

During HA-online power recovery (Scenario A, in-memory registry never serialized):

- pending applies may still match if within TTL and the entity transition is observed normally;
- if a mass restore is in progress, pending-apply matching should be conservative.

After an HA/Heima restart (Scenario B, checkpoint-based):

- any real restart or outage takes far longer than the pending-apply TTL, so a checkpointed pending
  apply is always past its TTL by the time it could be read back;
- checkpointed pending applies are therefore never restore-eligible and must not be used to classify
  post-restart entity changes as Heima-owned;
- `manual_hold.pending_applies` in the checkpoint payload is diagnostics-only — the same treatment
  already given to `runtime_confirmation.pending_request_ids` below — kept for post-mortem
  explanation ("what was Heima about to do"), not for recovery decisions.

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
- apply plans may be generated but blocked with `blocked_by="recovery:<state>"`, where `<state>` is
  the current recovery state (`startup_recovery`, `power_recovery`, `degraded_recovery`, or
  `recovery_settling`);
- apply steps may bypass the recovery block only through an explicit closed-vocabulary
  `recovery_policy` on the `ApplyStep`. Default is `block`. Unknown values fail closed as `block`.
  The first allowed policy is `allow_when_inputs_stable`, used for camera privacy policies only when
  the alarm/security input is current and not `unknown`/`unavailable`;
- if a step would also be blocked by an active manual hold, the two filters are independent: neither
  overwrites the other's `blocked_by` reason, per the existing rule in
  `core/manual_hold_framework_spec.md` ("manual hold must not overwrite an existing `blocked_by`
  reason"). Recovery blocking runs first in the apply pipeline, so a step blocked by recovery keeps
  `blocked_by="recovery:<state>"` even if a manual hold would independently also block it;
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

All domain checks below read the `runtime.recovery.*` context (see Architecture Integration), not
a domain output.

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

Security-relevant consequences of recovery must be emitted through the existing `security.*` event
family owned by the Security domain, not through the `system.recovery_*` catalog defined in this
spec. This follows the "more specific domain owns the condition" rule in Event Catalog Additions
below.

Concretely, `security_state_unavailable` is not a new event type: it is emitted as the existing
`security.mismatch` event (`core/security_mismatch_generalization_spec.md`) with
`subtype=security_state_unavailable`, the same pattern already used for
`subtype=armed_away_but_home`. `key` follows the existing convention:
`security.mismatch.security_state_unavailable`. This spec does not define a new security event
contract; it only supplies a new subtype value under the existing one.

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

If the `vacation_curve` branch (`domains/heating_spec.md` §6.5/6.7) was active before restart,
Heima must restore `start_temp` and the branch activation timestamp from the checkpoint rather than
recapturing `start_temp` from the post-restart setpoint. Recapturing on every restart would silently
alter the ramp curve. If the checkpoint does not have these fields (older schema, missing
checkpoint), Heima may recapture as if the branch were newly activated, but must record this as a
diagnostic so the discontinuity is explainable.

### Lighting and Switches

Many lights and switches have power-on defaults.

During recovery:

- light/switch changes caused by restore must not create implicit manual holds;
- smart-lighting reactions must not immediately reapply scenes until stabilization exits;
- restore-plausible changes are labeled `power_restore_candidate` (see Terminology) and exposed as
  entity impact detail.

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

This spec adds `recovery` as a new top-level key to the `HeimaObservabilitySnapshot` contract
defined in `core/admin_observability_panel_spec.md`, alongside the existing `manual_holds`,
`runtime_confirmations`, and `notifications` keys — the same category of cross-cutting facility
(see Architecture Integration), not nested under `runtime`.

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
  settling_started_at: iso8601 | null
  degraded_started_at: iso8601 | null
  stabilization_deadline_at: iso8601 | null
  degraded_timeout_at: iso8601 | null
  checkpoint:
    checkpoint_id: string | null
    created_at: iso8601 | null
    age_s: number | null
    reason: string | null
    valid: boolean
    ha_started_at: iso8601 | null
    heima_started_at: iso8601 | null
    restarted_since_checkpoint: boolean | null
  ha:
    restarted_since_checkpoint: boolean | null
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

- `system.recovery_startup_started`;
- `system.recovery_power_outage_suspected`;
- `system.recovery_power_restored`;
- `system.recovery_stabilization_started`;
- `system.recovery_completed`;
- `system.recovery_degraded`;
- `system.recovery_checkpoint_written`;
- `system.recovery_checkpoint_invalid`.

## Event Catalog Additions

Recovery lifecycle events use the existing `system` family (`core/event_catalog_spec.md`), typed
`system.recovery_*` so they fall under the existing `system.*` default audience mapping in
`core/events_and_notifications_spec.md` without requiring a new closed-vocabulary family.

Severity uses the unified `debug | info | warning | error | critical` enum, consolidated across
`core/event_catalog_spec.md` and this codebase (see Open Questions). None of the events below are
`debug` or `critical` — recovery lifecycle events are not themselves safety-critical; security
consequences route through `security.*` as noted above.

Events whose condition is owned by a more specific domain (for example
`security_state_unavailable`, see Domain-Specific Notes -> Security) must be emitted through that
domain's existing event family instead of a `system.recovery_*` type.

`key` follows `core/event_catalog_spec.md` convention: `key = type` for all events below, since each
is a singleton per recovery cycle per config entry (no per-room/per-entity dedup granularity is
needed).

| Event type | Key | Severity | Meaning |
|---|---|---|---|
| `system.recovery_startup_started` | `system.recovery_startup_started` | `info` | Heima entered startup recovery after HA/integration startup. |
| `system.recovery_power_outage_suspected` | `system.recovery_power_outage_suspected` | `warning` | Mass unavailability or power signal suggests outage while HA stayed online. |
| `system.recovery_power_restored` | `system.recovery_power_restored` | `info` | Critical entities are returning after suspected outage. |
| `system.recovery_stabilization_started` | `system.recovery_stabilization_started` | `info` | Recovery entered the stabilization window. |
| `system.recovery_completed` | `system.recovery_completed` | `info` | Recovery exited and normal runtime resumed. |
| `system.recovery_degraded` | `system.recovery_degraded` | `warning` | Recovery could not complete because critical inputs remain unavailable. |
| `system.recovery_checkpoint_written` | `system.recovery_checkpoint_written` | `info` | Runtime checkpoint persisted. |
| `system.recovery_checkpoint_invalid` | `system.recovery_checkpoint_invalid` | `warning` | Stored checkpoint could not be used. |

Notification routing should follow `core/events_and_notifications_spec.md`. The `system.*` default
audience mapping is admins/observability, not observability-only — routing for each recovery event
is stated explicitly below rather than assumed quiet by default:

- `system.recovery_startup_started` (`info`): the `system.*` default would push admins immediately,
  but this is a startup-derived configuration-summary event — the category the Startup Grace Period
  (`startup_notification_grace_s`, default 300s) exists to cover — so it is suppressed during the
  grace period, observability only;
- `system.recovery_power_outage_suspected` (`warning`): not a startup-derived configuration-summary
  event — it is entered mid-session while HA stays online — so the Startup Grace Period category
  does not apply. This pushes to admins immediately per the standard
  `system.*` default — intentional, an admin should learn promptly that the house may have lost
  power;
- `system.recovery_power_restored` / `system.recovery_stabilization_started` /
  `system.recovery_completed` (`info`): admins/observability per the standard `system.*` default;
  these are low-urgency status events, not gated further by this spec;
- `system.recovery_degraded` (`warning`): admins/observability per the standard `system.*` default
  on entry; if degraded recovery persists, admins are additionally notified once
  `degraded_timeout_s` (default 600s, see Configuration and Terminology -> Degraded Recovery) is
  reached, reusing the existing state timeout as the persistence threshold rather than defining a
  separate `persistence_thresholds.*` entry;
- `system.recovery_checkpoint_written` / `system.recovery_checkpoint_invalid`: admins/observability
  per the standard `system.*` default;
- security-relevant recovery consequences are carried by `security.mismatch` with
  `subtype=security_state_unavailable` (see Domain-Specific Notes -> Security), and follow
  `security.*` audience policy, not a `system.recovery_*` exception;
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
- recovery blocks non-critical apply with `blocked_by="recovery:<state>"`;
- a step already blocked by recovery is not overwritten by a subsequently-evaluated manual hold
  block, and vice versa;
- recovery does not create implicit manual holds for restore changes, and implicit holds are never
  restored from a checkpoint after restart;
- `recovery.stabilization` fires and is rechecked even with zero entity state changes
  during the window (no reliance on the 300s evaluation fallback);
- `recovery.degraded_timeout` is not registered at initial recovery entry and does not move later
  while already in `degraded_recovery`.

Integration tests:

- HA restart with valid checkpoint;
- HA restart with stale checkpoint;
- climate state changed during downtime;
- light state changed during downtime;
- camera privacy switch state changed during downtime;
- pending runtime confirmation before restart is forgotten and cannot apply stale steps;
- restart mid-`vacation_curve` restores `vacation_curve_start_temp`/`vacation_curve_started_at` from
  the checkpoint instead of recapturing the setpoint;
- `system.recovery_startup_started` does not push during the startup grace period;
- `system.recovery_power_outage_suspected` pushes to admins immediately when entered mid-session
  (no startup grace, no persistence gate);
- `security_state_unavailable` is emitted as `security.mismatch` with
  `subtype=security_state_unavailable`, not as a `system.recovery_*` type.

Live tests:

- controlled restart of the HA test container;
- simulated unavailable/available burst for critical entities;
- observability export contains recovery state and checkpoint metadata.

## Open Questions

1. Should admins be able to manually end recovery from the observability panel?
2. Should recovery windows be configurable in the first implementation or only after field testing?

Resolved:

- `ha_started_at` is best-effort. Heima stores it when HA exposes a parseable start timestamp and
  reports `restarted_since_checkpoint=null` when it cannot determine the answer reliably.
- The first action family explicitly allowed during recovery is security camera privacy policy
  enforcement, and only through `recovery_policy=allow_when_inputs_stable`.

Resolved: the severity vocabulary this spec depends on (`debug | info | warning | error | critical`)
has been consolidated across `core/event_catalog_spec.md`, `core/admin_observability_panel_spec.md`,
`core/security_mismatch_generalization_spec.md`, `HeimaEvent.severity` (now a typed `EventSeverity`
Literal in `custom_components/heima/runtime/contracts.py`), and all event-emission call sites. No
longer an open question.

Resolved: checkpoint persistence uses a dedicated HA `Store` with
`storage_key=heima_runtime_checkpoints`, storing one latest checkpoint per config entry. It is not
stored inside learning snapshots, approval records, proposal lifecycle state, or event storage.

## Acceptance Criteria

- Heima writes compact runtime checkpoints after important runtime changes.
- After HA restart, Heima enters startup recovery and exposes why.
- During recovery, non-critical apply steps are blocked with explicit recovery reasons.
- During recovery, learning and absence-based anomaly rules do not consume unstable snapshots.
- Power-restore actuator changes do not create implicit manual holds.
- After stabilization, Heima exits recovery and resumes normal runtime from current HA state.
- Admin observability shows checkpoint age, recovery state, entity differences, and blocked actions.
- The implementation is covered by unit, integration, and live restart tests.
