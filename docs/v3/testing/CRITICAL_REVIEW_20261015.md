# Critical review of recent V3 commits — 2026-10-15

> Follow-up: the third finding is resolved by approved CA4-102 and its implementation.
> See CYCLE_CLOCK.md for current behavior and verification. Original review below is historical.

Scope: commits 0cc0929 (coverage), 6a60bd5 (clock bridge/re-arm), f182a37
(CA4-101/callback boundary), f92639a (interval lifecycle), with timing/weekly/adapter
dependencies and the new bounded historical interval geometry. Normative baseline:
clean planning 0b82d61, read-only. This is local component review, not HA validation.

## Confirmed implementation findings — corrected

### Countdown precision could violate the minimum duration

AtJobScheduler.register and rearm_wall_clock used timedelta.total_seconds(), which
rounds to nearest float. A canonical 1 µs interval is represented by a float slightly
below 1/1_000_000; 2**35 s +1 µs can become exactly 2**35 s, dropping that microsecond.
AsyncioMonotonicTimer's TwoSum guard corrects origin+delay addition, not a duration
already shortened before entering the adapter. Defect existed in the dispatcher
used by recent commits; it was not uniquely introduced by the latest bridge.

Regression uses Fraction to compare the transported float to canonical exact duration,
both bases and multiple magnitudes; six literal cases failed before correction.
Fix: one shared integer-microsecond countdown conversion, with upward float adjustment
only if exact ratio proves round-down. The preceding float is strictly below the
desired duration, demonstrating the minimal representation. due/Window unchanged;
past/equal due still dispatch once immediately. No arbitrary padding or tolerance.

### Calendar lower-bound candidate hid a valid future occurrence

At 0001-01-01T00:00:00+00:00 with Etc/GMT-1 and Monday 00:00, today's requested local
candidate is already past and converts below UTC year 1. Its overflow prematurely
aborted next_weekly_occurrence instead of returning requested 0001-01-08 with physical
start 0001-01-07T23:00:00+00:00. Two host-zone regression instances failed before fix.

Fix: skip past/equal civil candidates before UTC conversion, retaining the physical
UTC comparison for ambiguous hours. Existing gap/fold/Apia behavior remains verified.

## Reproduced specification clarification — open

Forward correction while a previous backward correction still holds the floor:
cycle-start detection creates a closed adjacent-cycle forward gap; periodic detection
keeps the new forward gap open until floor recovery. The prior backward gap is
independent in either path. §3.5's periodic phrase leaves this crossing insufficiently
explicit to choose a product rule in code. Developer authorized preparing the exact
prompt, in ../clarifications/PERIODIC_FORWARD_GAP_DURING_FREEZE.md. ClockGap/CycleClock
were not changed. This is not reported as a resolved code defect or hidden xfail.

## Other reviewed behavior and limits

Coverage construction/composition preserves closed reasons, process coverage and
earliest known limit, with no retention/durability inference. Interval callbacks
retain finally re-arm, replacement/cancellation identity and explicit diagnostic
ports. Safe failed civil re-arm retires stale timers per job and leaves elapsed
untouched. Raw wall versus floored execution references remain distinct. No other
confirmed code defect found in this bounded review; tests are not a proof of full
engine correctness.

Still unimplemented: actual HA lifecycle/logging publication, continuity writer,
durable gap bookkeeping/acknowledgement, full historical read evaluation, SQLite
and L5 session admission. Non-raising diagnostic/observation infrastructure ports
are declared preconditions, not fault-tolerant publishers already supplied here.

## Evidence

Pre-fix focused run: 8 failures / 4 passes. Final local V3 suite: 587 passes,
seed3145; lint/format/mypy/diff pass. New interval decision/BVA/MC/DC/set properties
and float Fraction properties documented in HISTORY_INTERVALS_AND_REVIEW.md.
Fresh mutation: 364 generated, 291 killed, 5 timeouts, 68 equivalents, exact diffs
in HISTORY_INTERVAL_REVIEW_MUTANTS.md. Supplements: 5 interval +2 weekly mutants
killed with clean baselines. No release, deploy, ARM benchmark or live HA evidence.
