# Weekly next-due calculation — 2026-10-14

> Superseded scope notes: see CA4101_OCCURRENCES.md. Initial V3 CronEntry is
> interval-only; weekly calculation returns an occurrence for descriptor consumers.
> Generic weekly lifecycle is outside Initial V3, not pending clarification.

Scope: pure `runtime/recurrence.py::plan_weekly_job`, owning Layer 0 §3.1 and §13,
canonical instants from Layer 1 §4; clean planning `d58431c`.
Inputs are a validated weekly CronEntry, a paired execution reading and an explicit
configured ZoneInfo. Output is one strictly future wall_clock AtJob with the same
owner/id/label. The history floor does not select a weekly due.

No timer, HA timezone listener, recurrence lifecycle, persistence or served-occurrence
ledger is implemented here. A future coordinator must invalidate weekly arms on
timezone changes and prevent replay of served occurrences after clock/zone changes.
The independent interval precision contradiction is in clarifications/INTERVAL_PRECISION.md.

## Calculation and hardware scope

Calendar candidates cover today through the same weekday next week. Each local
candidate is converted to UTC before comparison. Valid and repeated civil times use
the first occurrence; a round-trip detects missing times. The two hypothetical folds
bracket a gap; binary search finds its first valid instant to microsecond precision.
This handles half-hour and skipped-day transitions without scanning every second.
ZoneInfo is injected already resolved. The calculation has no I/O or waits.
No Raspberry Pi/ARM benchmark or real HA integration is claimed.

Timezone behavior is supported by [Python ZoneInfo documentation](https://docs.python.org/3.14/library/zoneinfo.html)
and [PEP 495, Mind the Gap](https://peps.python.org/pep-0495/#mind-the-gap).

## Decision table

| Condition | Outcome | Test |
| --- | --- | --- |
| Normal local minute, future | That UTC instant | normal minute, explicit zones, PBT |
| Today due equal/past | Next permitted weekday | exact due BVA, PBT |
| Missing minute | First valid instant after gap | Rome, Lord Howe, Apia |
| Repeated minute before first | First occurrence only | Rome fold boundary |
| First occurrence passed, second still ahead | Next weekly occurrence | Rome/history fold tests |
| Configured date differs from host date | Use configured date | Tokyo and Los Angeles |
| Wrong input shapes | Reject before calculating | boundary shape tests |
| No representable future date | Explicit ValueError | calendar exhaustion |

## Boundary Value Analysis

Rome spring endpoint and first autumn occurrence at −1 µs, exactly, +1 µs;
ordinary due at the same three boundaries. Second autumn occurrence does not revive
the served civil request. Generated weekdays include 0/6, hour 0/23, minute 0/59,
single/all weekdays; supported calendar exhaustion is explicit. Spring/autumn weekly
UTC separations are 167/169 hours while the resident's requested hour remains fixed.
Half-hour/day-long gaps demonstrate the policy is not hard-coded to an hour.

## MC/DC

No compound Boolean decision is introduced: input gates, weekday membership,
future comparison, round-trip equality, search termination and search direction
are separate decisions. Thus compound-condition independence has no applicable
construct in this slice. Decision outcomes are exercised by the table and boundaries;
this is not a claim that branch coverage certifies MC/DC.

## Property-Based Testing

Hypothesis seed 3145; generated UTC readings, nonempty weekday sets and civil
components. Due is strictly future and at most seven days away, matches the standing
pattern, has zero seconds/microseconds and preserves identity/basis. Changing only
cycle_instant leaves due unchanged. Expected DST instants are literal independent
examples. All weekly tests run with host timezone UTC and Europe/Rome to expose
ambient-zone dependencies; the fixture restores the process timezone afterwards.

## Verification

See WEEKLY_MUTANT_REVIEW.md for mutation scope and survivor assessment. The final
suite/check results are recorded in WORKING_CONTEXT.md. Existing V3 tests remain
part of the regression gate. No live HA, durable recurring configuration or replay
guard verification is claimed by this pure calculator slice.
