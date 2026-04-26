# Heima — Scheduled Routine Spec

**Status:** Active v1.x admin-authored contract  
**Last Verified Against Code:** 2026-04-26

## Purpose

`scheduled_routine` is the bounded Heima family for explicit admin-authored clock-based intent.

It exists for cases such as:
- run a scene on a weekday at a specific time
- run a script on a weekday at a specific time
- turn one or more bounded actuators on or off on a weekday at a specific time

It is explicitly **not**:
- a learned family
- a lighting-only family
- a target for tuning or improvement proposals
- a valid source for `vacation_presence_simulation`
- a generic automation builder with arbitrary conditions or chained delays

## Product Boundary

Normative rules:
- `scheduled_routine` is **admin-authored only**
- no analyzer may emit `scheduled_routine`
- no proposal lifecycle path may rediscover, tune, or improve `scheduled_routine`
- `scheduled_routine` is allowed to express pure time-based intent
- pure time-based learned automations are not part of the active Heima product model

Rationale:
- time alone is acceptable as an explicit human instruction
- time alone is not considered a strong enough behavioral explanation for learned automation

## Supported v1 Scope

Trigger:
- `weekday`
- `scheduled_min`
- `window_half_min`

Bounded guardrails:
- `house_state_in`
- `skip_if_anyone_home`

Supported target domains in v1:
- `scene.*`
- `script.*`
- `light.*`
- `switch.*`
- `input_boolean.*`

Out of scope in v1:
- arbitrary boolean logic
- arbitrary service payload authoring
- per-step delays / chains
- `cover.*`
- `climate.*`
- `media_player.*`

## Persisted Runtime Contract

The normalized configured contract rebuilt by the runtime is:

```python
{
  "reaction_type": "scheduled_routine",
  "weekday": int,           # 0..6
  "scheduled_min": int,     # minutes from midnight
  "window_half_min": int,   # v1 admin-authored currently uses 0
  "house_state_in": list[str],
  "skip_if_anyone_home": bool,
  "routine_kind": str,      # "scene" | "script" | "entity_action"
  "target_entities": list[str],
  "entity_action": str,     # "turn_on" | "turn_off"
  "entity_domains": list[str],
  "steps": list[{"domain": str, "target": str, "action": str, "params": dict}],
}
```

Notes:
- `enabled` is part of the surrounding configured reaction wrapper, not of the normalized
  `scheduled_routine` contract itself
- `plugin_family` and `admin_authored_template_id` are proposal/admin-authored metadata and are not
  part of the normalized runtime contract
- `steps` is the canonical execution payload used by the runtime

## Admin-Authored Proposal Payload

The admin-authored template builder may temporarily carry richer proposal metadata before the
configured reaction is finalized. In that proposal layer, the payload also includes:

```python
{
  "plugin_family": "scheduled_routine",
  "admin_authored_template_id": "scheduled_routine.basic",
}
```

These fields are proposal/template metadata, not runtime execution requirements.

## Identity

### Configured Reaction Identity

Configured reactions use the persisted `reaction_id` key under `options.reactions.configured`.

### Admin-Authored Proposal Identity

The current admin-authored proposal identity key is defined by the template builder and is:

```text
scheduled_routine|weekday={weekday}|scheduled_min={scheduled_min}|kind={routine_kind}|targets={sorted(target_entities)}
```

Normative interpretation:
- this is the template/proposal identity used when materializing a requested admin-authored routine
- it is not a learned analyzer identity
- it intentionally does not include `house_state_in` or `skip_if_anyone_home`

## Runtime Semantics

### Trigger Window

The routine is eligible when local time falls inside the configured weekday/time window:
- centered on `scheduled_min`
- expanded symmetrically by `window_half_min`

### Guardrails

At evaluation time:
- if `house_state_in` is non-empty, current `house_state` must be one of those values
- if `skip_if_anyone_home = true`, the routine is suppressed when `anyone_home = true`

### Once-Per-Day / Idempotence

`scheduled_routine` is a once-per-occurrence reaction.

Normative rules:
- a routine may fire at most once for a given occurrence date
- the runtime tracks this through `last_fired_date`
- re-evaluation within the same day/window must not emit duplicate apply steps

### Restart Behavior

After a Home Assistant restart:
- the runtime reschedules the routine to the **next future slot**
- it does **not** replay missed past windows
- if HA restarts after the current day's window has already passed, that day's occurrence is lost
- the next scheduled execution is the next matching future weekday/time

This is intentional. `scheduled_routine` is a bounded scheduler reaction, not a catch-up job runner.

## Execution Semantics

The runtime executes bounded `steps`-based actions only.

Supported action families in v1:
- `scene.turn_on`
- `script.turn_on`
- `light.turn_on`
- `light.turn_off`
- `switch.turn_on`
- `switch.turn_off`
- `input_boolean.turn_on`
- `input_boolean.turn_off`

Security rule:
- `scene.turn_on` and `light.turn_on` remain subject to the existing `security.armed_away` block
  semantics used by the runtime engine

## Options Flow Contract

The bounded admin-authored template is:
- `scheduled_routine.basic`

Create/edit must use shared schema and normalization core.

The visible fields are:
- `weekday`
- `scheduled_time`
- `routine_kind`
- `target_entities`
- `entity_action` (only for `entity_action`)
- `house_state_in`
- `skip_if_anyone_home`
- `enabled` (edit)
- `delete_reaction` (edit)

The flow must not expose:
- arbitrary free-form conditions
- arbitrary service payloads
- chained steps / delays

## Relationship to Learning

`scheduled_routine` is intentionally outside the learned automation lifecycle.

Normative rules:
- no learning analyzer emits `scheduled_routine`
- `ProposalEngine` does not surface it as discovery
- it does not participate in tuning or improvement follow-up
- review wording must keep it clearly in the admin-authored channel

## Relationship to Vacation Presence Simulation

`scheduled_routine` is not a valid source for `vacation_presence_simulation`.

Rationale:
- `scheduled_routine` represents explicit admin intent
- `vacation_presence_simulation` must derive from learned human behavioral traces, not fixed
  authored schedules
