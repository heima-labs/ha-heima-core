# Clock regression without a frozen cycle — resolved by CA4-98

**Status:** resolved in planning `dd89383`, verified against current Layer 0
§§3.5/10/13 and CA4-98 review. The original counterexample below is historical.

## Definitive rules and implementation mapping

- Backward correction >1 s always requires clock_regression, wall_clock re-arm
  and a process-wide gap. Above the floor: last cycle before detection to first
  cycle after detection. Below the floor at cycle start: first frozen cycle to
  first cycle whose wall exceeds the floor.
- Periodic detection acts at the check. Gap starts at the last cycle, end pending;
  a later cycle supplies the end, with delayed closure under the frozen-floor rule.
  Comparison baseline updates at the check, so the correction is not detected twice.
- Small backward correction <=1 s: no gap/re-arm; diagnostic only below the floor.
- Floor means previous cycle +1 microsecond. Detection point and floor position
  are returned with the classified comparison for runtime diagnostics.

runtime/clock.py now exposes immutable ClockGap boundary intents and finish(tick),
plus diagnostic/re-arm requirements and detection metadata. These are process-local
mechanism outputs, not a durable schema, persistence acknowledgement or historical
read completeness proof. The future coordinator must consume each intent and retain
an open intent across cycles; it owns delivery/persistence, not this pure helper.

## Original clarification draft (superseded)


Authoritative source checked: planning 9cd077e, Layer 0 §3.5, §3.1 and §4.4.
Prepared for Claude review at the developer's explicit request; planning remains read-only. This draft is not
an approved alternative gap rule, an opened issue, or a message sent to Claude.

## Established rules

Layer 0 §3.5, **Clock discontinuity**, classifies a difference greater than one
second between elapsed wall and monotonic time as a discontinuity, in either
direction. It requires wall_clock job re-arm. The **Backward jump** paragraph
requires a process-wide gap from the first frozen cycle instant until the first
cycle whose wall reading exceeds the floor. It emits clock_regression.
Layer 0 §3.1 keeps elapsed countdowns unchanged and re-arms wall_clock deadlines.
Layer 0 §4.4 persists observation boundaries; uncertain metadata cannot certify
historical completeness. The §3.5 check also runs in §4.4's 60-second recurrence.

## Counterexample

| Reading | Wall | Monotonic | Cycle instant |
|---|---|---|---|
| Previous | 12:00:00 UTC | 0 s | 12:00:00 UTC |
| After a -2 s correction | 12:00:58 UTC | 60 s | 12:00:58 UTC |

Elapsed wall = 58 s, elapsed monotonic = 60 s, difference = -2 s. This is a
specified backward discontinuity. The wall reading is still later than the previous
cycle, so max(wall, previous_cycle + 1 microsecond) uses wall directly. No cycle
freezes and the declared gap-start condition never occurs. A periodic check can
observe this same case even before an evaluation cycle runs.

This is relevant to slow hardware or infrequent evaluations, not only an artificial
input. The classifier must detect the -2 s correction, keep cycle instants increasing
and request wall_clock re-arm; none of these facts determines the required gap bounds.

## Decision needed in the authoritative specification

Define the start/end of a backward clock_discontinuity gap when the wall clock stays
above the cycle floor, including detection by the periodic check. Confirm the
clock_regression diagnostic condition in that case. Preserve the >1 s threshold,
small-correction handling, elapsed countdowns, wall_clock re-arm, bootstrap/downtime
separation and conservative §4.4 acknowledgement rules. Reconcile acceptance cases.

## Implementation status

runtime/clock.py classifies this case as backward and marks re-arm required; its
cycle result correctly reports wall_behind_floor=False. The exact example is a
regression scenario in test_cycle_clock.py. No alternative gap boundaries or
runtime diagnostic policy were implemented. Existing freeze-cycle cases likewise
return facts for the future runtime boundary; gap persistence is still pending.
