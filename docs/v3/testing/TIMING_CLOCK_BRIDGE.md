# Timing clock capture and scheduler effects — 2026-10-15

Sources: clean read-only planning 0b82d61, Layer 0 §3.1/§3.5, §4.4 periodic
continuity check, fault/diagnostic sections and §13. Dependencies: CA4-98/99 clock
results, existing AtJobScheduler, IntervalRecurrences and canonical instants.

## Scope and interfaces

SystemClockSource captures canonical UTC via datetime.now(UTC), followed by raw
monotonic_ns at the adapter boundary. These are sequential near-paired observations,
not atomic samples or interpolated timestamps. No ambient clock read enters domain
logic. One real-host test verifies canonical shape and bounded monotonic sample;
this is not a live Home Assistant or hardware performance test.

TimingClock takes explicit CycleClock, ClockSource, scheduler and two nonblocking,
non-raising effect ports. next_cycle/check_periodic capture once, classify with the
same shared comparison baseline and deliver the comparison to observe before
re-arm. Pending civil jobs use that exact captured raw wall. read_execution changes
neither cycle floor nor detector baseline. CycleTick is returned for completion of
pending gap intents; returning/finishing a gap never acknowledges persistence.

observe owns conservative metadata/diagnostics and queuing of persistence effects;
the actual implementation is not present yet. report_rearm_fault receives the
comparison, affected job and error strings. HA startup, a real diagnostic publisher,
durable gaps and the continuity writer remain future integration. The periodic
entry point is composed in tests through an ordinary 60-second IntervalRecurrence;
no second production periodic loop or watermark writer is created here.

## Confirmed scheduler failure defect and fix

Before the fix, a failed civil re-arm preserved its pre-correction monotonic timer.
Reproducer: initial wall 0, due 110; at monotonic 1 wall becomes -2. If replacement
fails, old timer still fires at monotonic 110 while wall is 107, before due. A focused
reproducer demonstrated an owner delivery before the fix; final regression invokes
the stale timer at that old deadline and requires no delivery.

rearm_wall_clock now returns tuple[WallClockRearmFailure,...]. Each failed arm is
cancelled, diagnosed and retired; remaining civil jobs still re-arm, elapsed jobs
are untouched. Successful re-arms keep canonical due/identity. A stale callback
cannot revive the failed arm. Ordinary register replacement failure still preserves
its valid old registration (existing contract/test unchanged). No retry delay or
fallback execution policy introduced. Future owners can react to the explicit fault;
this bridge does not silently certify all jobs as armed after a failure.

Internal return-type change reviewed: the bridge is the runtime consumer and
reports every failure; existing tests/callers inspected. No HA public API, durable
schema, identifier or V2 behavior changed.

## Decision Tables

| Condition | Expected / evidence |
| --- | --- |
| Discontinuity at cycle, periodic check or bootstrap | Re-arm civil jobs against detecting wall; elapsed untouched |
| No discontinuity | Observe classification, no re-arm |
| Small backward correction above/below floor | None / clock_regression only; neither re-arms |
| Periodic correction, next cycle | Immediate pending gap intent, shared baseline prevents duplicate detection |
| Execution-only read | Floor applied without consuming cycle/comparison |
| Re-arm backend fails | Cancel stale arm, report affected job, continue others |
| Invalid monotonic sample | Reject before observation/scheduler effects; valid baseline preserved |
| 60-second ordinary interval fires | Compare without creating cycle; fresh 60-second elapsed re-arm |

Tests in runtime/test_timing_clock.py exercise every row, including forward
classification and per-job partial failure; adapters/test_clock_source.py verifies
capture values and actual raw host sample shape.

## Boundary Value Analysis

No correction, exactly ±1 s and outside threshold via generated integer changes;
small negative corrections above/below cycle floor; periodic detection between
cycles and subsequent cycle; bootstrap with durable floor; old deadline after
failed re-arm; zero/one/two civil failures with elapsed jobs preserved. Exact
nanosecond threshold BVA remains in existing CycleClock tests.

## MC/DC

No compound Boolean condition introduced or changed by the bridge/failure fix.
Basis equality, re-arm-required flag and individual failure handling are separate
single-condition decisions. Existing compound clock/registration rules retain their
previous evidence; this is not a claim that branch coverage certifies MC/DC.

## Property-Based Testing

Hypothesis seed 3145 generates corrections -10..10 seconds against a fixed
30-second monotonic interval. Only |correction| >1 replaces the civil handle;
the replacement countdown equals due minus captured wall. Canonical due/identity
and elapsed handles remain unchanged. Literal regressions cover frozen clocks,
bootstrap and inter-cycle comparison baseline independently of this property.

## Verification

502 V3 tests pass, 16 new, seed3145; Ruff lint/format, mypy and diff pass.
Fresh mutmut on timing.py, timing_clock.py and clock_source.py: 168 generated,
156 killed, 12 equivalent generic-validation-prose survivors; no timeout/error/skip.
Exact diffs in TIMING_CLOCK_MUTANT_REVIEW.md. Supplement mutation_timing_clock.py
clean baseline passes and kills three public frozen-result mutations. Default
mutation scope thirteen modules. No new dependency, threshold or policy. No HA
release/lifecycle harness, ARM benchmark, durable-gap acknowledgement or real
continuity watermark advancement claimed.
