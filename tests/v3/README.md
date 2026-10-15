# V3 behavioral tests

Run `.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145`.
Install runtime/development locks first; tests import real packages and the mutated
copy under mutmut, without HA/V2 import shims. Default mutation scope: fifteen modules.

## Current contracts

CronEntry accepts IntervalRecurrence only (CA4-101). WeeklyRecurrence remains a value
for descriptor windows/bucketing. next_weekly_occurrence returns requested civil date
and canonical physical start. Layer-5 activation owns served dates, equal-start merge,
remaining-time admission and timezone re-arm; those session tests await L5 code.

## Evidence index under docs/v3/testing

- PAYLOAD_CONTRACT.md / PAYLOAD_MUTANT_REVIEW.md: shared canonical payloads.
- TIMING_CONTRACT.md: temporal foundation history; CA4101_OCCURRENCES.md is current.
- ATJOB_DISPATCH.md: shared monotonic admission, replacement and stale deliveries.
- MONOTONIC_ADAPTER.md: early-wakeup/coarse-clock and real stdlib-loop cases.
- CYCLE_CLOCK.md / CA499_EXECUTION_REFERENCES.md: cycle floor and paired basis clocks.
- CA4100_DEADLINES.md: exact canonical-decimal deadline construction/overflow.
- CA4101_OCCURRENCES.md / CA4101_MUTANT_REVIEW.md: interval-only CronEntry and
  requested-date-preserving weekly occurrences, DST and calendar boundaries.
- INTERVAL_LIFECYCLE.md: process-local standing interval rules, faults and re-arm.
- JOB_CALLBACK_BOUNDARY.md: shared owner fault isolation and wrapped one-shot tests.

Supplemental mutation runners: mutation_constants.py, mutation_timing.py,
mutation_clock.py, mutation_deadlines.py, mutation_interval_recurrences.py,
mutation_weekly_occurrence.py. The new weekly runner checks immutable metadata and
replacement of requested date with shifted start date. Actual HA/persistence wiring,
calendar staging, durable gap acknowledgement and ARM benchmarks remain separate.

Timing clock integration: `docs/v3/testing/TIMING_CLOCK_BRIDGE.md` and its mutant
review. `mutation_timing_clock.py` covers three public frozen clock/failure records.
Host capture and 60-second component composition are tested; actual HA lifecycle,
diagnostic publishers and durable continuity watermark/gap implementation remain future.

Observation coverage foundation: `docs/v3/testing/OBSERVATION_COVERAGE.md` and its
mutant review. Supplement: `mutation_observation.py`. Covers value invariants and
composition of already request-clipped process/required-stream results; actual gap
timeline assessment, SQLite durability and historical record assembly remain future.

History intervals and latest critical review: `docs/v3/testing/HISTORY_INTERVALS_AND_REVIEW.md`,
`CRITICAL_REVIEW_20261015.md` and `HISTORY_INTERVAL_REVIEW_MUTANTS.md`. Supplemental
`mutation_history_intervals.py` covers empty-property logic outside mutmut scope.
Fraction countdown regressions and year-1 weekly regression are now in the gate.
Periodic forward-gap behavior during an earlier freeze awaits a normative handoff.
