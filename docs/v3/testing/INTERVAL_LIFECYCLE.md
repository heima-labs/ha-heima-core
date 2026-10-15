# Standing interval lifecycle — 2026-10-14

> Superseded scope notes: see CA4101_OCCURRENCES.md. Initial V3 CronEntry is
> interval-only; weekly calculation returns an occurrence for descriptor consumers.
> Generic weekly lifecycle is outside Initial V3, not pending clarification.

Scope: runtime/interval_recurrences.py, IntervalRecurrences, Layer 0 §3.1, §3.5,
§9 callback failures and §10 timing diagnostics; acceptance §13. Checked clean
read-only planning 34ce913. Dependencies: existing CronEntry/IntervalRecurrence,
CA4-100 derive_instant, CA4-99 execution references and AtJobScheduler.

## Mechanism and boundaries

One process-local registration per (owner,job_id), with a revalidated immutable
definition and synchronous owner callback. Registration reads the injected clock,
plans an interval and uses the existing monotonic dispatcher. Replacement publishes
the new registration only after timer admission succeeds; failure preserves the old
registration and timer. Overflow reports IntervalDeadlineRejected before any change.

After delivery, ordinary owner exceptions are converted to JobCallbackFault and
reported. Finally, a still-current registration re-arms from a fresh post-callback
clock capture. Reference identity distinguishes a replacement made by the owner;
cancellation or stop made by the callback prevents old-rule resurrection. Callback
failure still allows re-arm, and unrelated owners continue. Late delivery changes
neither old due nor cadence into a catch-up burst.

Re-arm clock/timer failure or calendar overflow is explicitly diagnosed. The standing
definition remains registered but has no pending timer; no silent retry policy is
invented. A successful registration can arm it again. Initial admission exceptions
propagate to the caller without replacing accepted state. Diagnostic sink is an
explicit infrastructure port requiring non-raising, prompt log/publication and no
durable I/O wait. If that port violates its contract, failure is not swallowed.
Diagnostic records retain strings/typed inputs, not traceback-bearing exceptions.

entries is a tuple of standing definitions; scheduler.pending_jobs supplies due and
basis for inspection. stop cancels this service's keys only, preserving unrelated
shared one-shot jobs; it is idempotent. Recreating the service from standing rules
uses now + interval and never recovers interrupted countdowns.

No HA logger/publisher adapter, persisted configuration, automatic restart restoration,
weekly lifecycle or timezone listener exists in this slice. It does not change the
low-level one-shot dispatcher's callback-error behavior; a future boundary must also
isolate those callbacks. Full weekly served-occurrence handling remains next work.

No new timer loop, sleeps, filesystem access, minimum cadence or hardware threshold.
Each fire touches its own registration; no scan of all rules. Inspection and shutdown
traverse registered rules. Simulated tests do not assert real Pi/ARM execution speed.

## Decision Tables

| Event / condition | Outcome | Test |
| --- | --- | --- |
| Valid first/replacement registration | One future arm, standing snapshot | fresh re-arm, owner replacement, PBT |
| Invalid shape/callback | Reject before clock/timer | wrong shapes |
| Clock/timer error at replacement | Prior definition and arm retained | failed admission |
| Overflow at admission | One diagnostic, no state/timer change | overflow false/true existing |
| Fire, owner returns/fails, registration current | Fresh arm, diagnostic on failure | fresh re-arm, callback failure |
| Owner cancels/stop during callback, returns/fails | No automatic re-arm | cancellation pairs, stop inside callback |
| Owner replaces, returns/fails | Replacement alone continues | replacement pairs |
| Owner attempts failing replacement | Old rule continues | failed reentrant replacement |
| Clock/timer error at automatic re-arm | Diagnosed, standing definition retained | re-arm failure |
| Calendar overflow at automatic re-arm | Diagnosed, no immediate loop | calendar end |
| Cancel missing rule / service stop | Shared unrelated jobs unaffected | missing cancellation, shutdown |
| Stale callback | No delivery or resurrection | shutdown, replacement, PBT |
| Restart from definitions | Fresh now + interval, no missed replay | restart test |

## Boundary Value Analysis

Zero/one/two registered owner keys; identical job_id under distinct owners;
cancellation before/inside/after dispatch; replacement success/failure at admission
and within the callback; callback return/exception while canceling/replacing;
calendar maximum at re-arm. Generated intervals include subnormal floats and
positive durations below 1 µs; each arm remains positive under CA4-100. Clock
capture after owner work uses cycle_instant even when raw wall remains behind.
Existing lower-level exact timer/duration boundaries remain in the regression gate.

## MC/DC

No compound Boolean decision introduced: all type/callability, overflow,
registration identity, optional diagnostic and cancellation checks are separate
single-condition decisions. MC/DC compound independence is therefore inapplicable
to this source slice. Table tests demonstrate those individual outcomes; branch
coverage is not represented as MC/DC certification.

## Property-Based Testing

Hypothesis seed 3145: generated finite positive durations from smallest subnormal
through 60 seconds and 1–15 consecutive fires. One standing rule and one future arm
remain, every delay is positive, the captured due advances, delivered job is the
accepted one, and replaying each stale callback yields no duplicate delivery.
This checks observable lifecycle invariants without reproducing the state machine.

## Verification

469 total V3 tests pass, 24 new, seed3145; lint/format/mypy/diff pass. Fresh mutmut
3.8 on interval_recurrences.py: 119 generated, 107 killed, 12 equivalent survivors,
no timeout/skipped/error. Initial diagnostic-entry/message survivors exposed missing
assertions; fresh final run kills them after test strengthening. Exact diffs and
classification in INTERVAL_LIFECYCLE_MUTANT_REVIEW.md.

mutation_interval_recurrences.py clean baseline passes; three public frozen-record
mutations killed by corresponding diagnostic tests. Private _Registration's frozen
flag has no observable mutation behavior here: no service code mutates or exposes
that record; its structure is exercised through admission and reentrant replacement.
Default mutation scope ten modules. No numerical score threshold introduced.
No live HA, ARM benchmark, durable restart or weekly lifecycle gate has run.
