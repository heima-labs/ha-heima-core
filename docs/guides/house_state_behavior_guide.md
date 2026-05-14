# Heima House State Behavior Guide

This guide explains what admins and advanced residents should expect from Heima's house-state logic.

It is not a schema reference. It is a behavioral guide: when signals change, what should Heima do, why might it wait, and how should an admin configure reliable evidence.

Technical references:
- [House State Domain Spec](../specs/domains/house_state_spec.md)
- [House State Override Spec](../specs/core/house_state_override_spec.md)
- [Heima v2 Admin Guide](heima_v2_admin_guide.md)

## What House State Means

`house_state` is Heima's global interpretation of the current home context.

Allowed states:

- `vacation`
- `away`
- `sleeping`
- `guest`
- `working`
- `relax`
- `home`

The current state is exposed through:

- `sensor.heima_house_state`
- `sensor.heima_house_state_reason`
- `sensor.heima_house_state_path`
- `sensor.heima_house_state_active_candidates`
- `sensor.heima_house_state_pending_candidate`
- `sensor.heima_house_state_pending_remaining_s`

## Priority

Heima resolves states in this order:

1. manual override
2. `vacation`
3. `guest`
4. `away`
5. `sleeping`
6. `relax`
7. `working`
8. `home`

This means:

- `vacation`, `guest`, and `away` are hard states.
- `sleeping`, `relax`, `working`, and `home` are home substates.
- `sleeping` wins over `relax` and `working`.
- `relax` wins over `working`.
- `home` is the fallback.

## Why State Changes Are Not Always Immediate

Heima uses candidates and timers.

A signal can make a candidate active, but the effective `house_state` changes only when that candidate satisfies its confirmation rule.

Examples:

- `work_candidate` must remain active for `work_enter_min`.
- `sleep_candidate` must remain active for `sleep_enter_min`.
- `relax` from passive media activity must remain active for `relax_enter_min`.
- `relax` stays active for `relax_exit_min` after passive relax evidence disappears.
- `working` can stay active for `work_activity_grace_min` after work activity disappears, when work activity is required.

This prevents short spikes and sensor gaps from making the house state bounce.

## Sleeping

`sleeping` is conservative on entry and relatively fast on exit.

It can enter when:

- someone is home
- `sleep_window` is active
- media is inactive when `sleep_requires_media_off = true`
- charging corroboration passes when `sleep_charging_min_count` is configured
- the condition persists for `sleep_enter_min`

It exits when:

- someone is home
- `wake_candidate` is active because either `sleep_window` turns off or media becomes active
- the wake condition persists for `sleep_exit_min`

Good sleep evidence:

- explicit sleep window helper
- bedroom routine helper
- phone charging evidence if it is reliable
- media inactive as negative corroboration

Weak sleep evidence:

- a laptop charging
- a computer merely powered on or off
- one-off motion absence without room context

## Working

`working` is intended to mean "the home is in a work-from-home phase", not merely "a computer exists".

Base work evidence:

- someone is home
- `work_window` is active
- workday evidence is positive

Workday evidence is resolved as:

1. calendar office today -> not workday for WFH
2. calendar WFH today -> workday
3. configured `workday_entity` -> normalized boolean
4. no explicit evidence -> true

### Work Activity

Admins can add work activity evidence with:

- `work_activity_entities`
- `work_activity_required`
- `work_activity_grace_min`

Use work activity entities for recent human work activity, not for raw computer power.

Good examples:

- workstation session unlocked and active
- keyboard/mouse input in the last 5-10 minutes
- active video meeting signal
- desk presence plus workstation activity

Bad examples:

- PC powered on
- laptop charging
- device tracker online
- CPU high
- backup/render/download running

### When `work_activity_required = false`

This is the default.

Behavior:

- `work_window + workday` can still enter `working`.
- work activity appears in diagnostics as corroboration.
- existing installations keep their previous behavior.

### When `work_activity_required = true`

Behavior:

- entering `working` requires work activity.
- if work activity is absent, Heima stays or falls back to `home`.
- after `working` is active, short work-activity gaps are tolerated for `work_activity_grace_min`.
- after the grace expires, `working` ends unless activity returns.

Example with:

```text
work_activity_required = true
work_activity_grace_min = 20
work_enter_min = 5
work_activity_entities = [binary_sensor.stefano_mac_active_recent]
```

Expected behavior:

| Situation | Expected state |
|---|---|
| Work window true, Mac activity false | `home` |
| Mac activity true for less than `work_enter_min` | pending `work_candidate` |
| Mac activity true for at least `work_enter_min` | `working` |
| Mac activity false for a short coffee break | still `working` during grace |
| Mac activity false beyond grace | `home` |
| Sleep is confirmed | `sleeping` wins over `working` |

This solves two common edge cases:

- a computer left on overnight does not create `working`
- a short pause during work does not immediately drop `working`

## Relax

`relax` can come from:

- explicit `relax_mode`
- passive media activity

Explicit `relax_mode` enters immediately.

Passive media activity waits for `relax_enter_min`.

When already in `relax`, Heima keeps it for `relax_exit_min` after passive evidence disappears. This avoids bouncing when media briefly pauses or sensors miss a cycle.

## Vacation, Guest, And Away

`vacation` wins when:

- `vacation_mode` is active
- or the calendar indicates an active vacation

`guest` wins when:

- `guest_mode` is active
- and no manual override or vacation state is active

`away` wins when:

- nobody is home
- and no manual override, vacation, or guest state is active

These hard states are intentionally simple and high priority.

## Manual Override

Manual override forces the final house state.

When active:

- it wins over every derived state
- the reason becomes `manual_override:<state>`
- domains consume the overridden state

Use override for temporary control, not for permanent configuration.

## How To Read Diagnostics

Start with:

- `sensor.heima_house_state`
- `sensor.heima_house_state_reason`
- `sensor.heima_house_state_path`

Then inspect:

- `sensor.heima_house_state_active_candidates`
- `sensor.heima_house_state_pending_candidate`
- `sensor.heima_house_state_pending_remaining_s`

Interpretation:

- active candidate: evidence is currently true
- pending candidate: evidence is true but waiting for a timer
- pending remaining: seconds left before the candidate can win
- reason: why the current state won
- path: whether the result came from override, hard state, or home-substate resolution

For deeper inspection, use diagnostics:

```bash
source scripts/.env
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section engine
```

Look for:

- `house_signals_trace`
- `candidate_trace`
- `candidate_summary`
- `timers`
- `resolution_trace`
- `override`

## Configuration Advice

Use strong semantic signals:

- explicit mode helpers
- reliable calendars
- room-local occupancy
- recent input/activity sensors
- meaningful media states

Avoid weak proxies:

- device online
- computer powered on
- battery charging
- broad motion without room context
- CPU usage without human input
- sensors that remain active for background jobs

Tune one thing at a time:

1. first make people/presence stable
2. then configure sleep/work/relax windows
3. then add media or work activity evidence
4. then adjust timers
5. then inspect diagnostics after normal daily usage

## What Not To Expect

Heima does not try to guess a perfect psychological state.

It resolves a small set of operational contexts that other domains can safely consume:

- lighting can choose context-aware behavior
- heating can apply branches by house state
- security presence simulation can run only during vacation
- reactions can gate on house state

If a signal is ambiguous, Heima should either wait, fall back to `home`, or expose diagnostics that explain why the candidate did not win.
