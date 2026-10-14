# V3 behavioral tests

Run `.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145`.
Install both runtime and development locks first. Tests import the real packages,
including the mutated copy under mutmut; no HA or V2 parent shim is used.
See `docs/v3/testing/PAYLOAD_CONTRACT.md` for the five-method evidence and the
supplementary module/decorator mutation runner.

Temporal contract evidence: `docs/v3/testing/TIMING_CONTRACT.md`.
Dispatcher evidence: `docs/v3/testing/ATJOB_DISPATCH.md`; its fake monotonic timer
exercises replacement/cancellation/re-arm and stale callbacks without sleeps or HA.
Default mutation scope includes all five implemented modules and the whole V3 suite.

Concrete timer evidence: `docs/v3/testing/MONOTONIC_ADAPTER.md`, with early-wakeup/
coarse-clock simulations, exact-sum properties, scheduler integration and two real
stdlib event-loop cases. The default mutation scope now includes six modules.

Cycle-clock evidence: `docs/v3/testing/CYCLE_CLOCK.md`, including exact threshold
boundaries and simulated clock regressions/long pauses. `mutation_clock.py` covers
the threshold constant and frozen-result declarations. Default scope: seven modules.

Current scheduling API/evidence: `docs/v3/testing/CA499_EXECUTION_REFERENCES.md`.
Scheduler calls use explicit paired execution references; the former single-instant
argument is rejected. `mutation_clock.py` now verifies five supplemental mutations.

Weekly calculator evidence: `docs/v3/testing/WEEKLY_RECURRENCE.md` and
`WEEKLY_MUTANT_REVIEW.md`. Current default mutation scope: eight modules.
Interval deadline precision awaits a normative clarification; no full CronEntry
service or timezone-change replay guard is implemented yet.

CA4-100 evidence: `docs/v3/testing/CA4100_DEADLINES.md` and `CA4100_MUTANT_REVIEW.md`.
`mutation_deadlines.py` checks immutable overflow diagnostics. Default scope nine
modules; interval representation resolved. Full lifecycle/calendar/HA integration
remains separate from single-arm calculation and admission.
