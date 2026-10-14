# Current CA4-99 checkpoint

Execution references are now separate per basis. Read
[CA499_EXECUTION_REFERENCES.md](CA499_EXECUTION_REFERENCES.md) for the current API,
355-test evidence, paired clock reads, exact regression and mutation results.
Earlier evidence below is historical where superseded, especially single-instant
scheduler calls and the execution-reference ambiguity.

# Layer-0 AtJob dispatch

Implemented against planning 9cd077e (clean), Layer 0 §3.1 and the re-arm portion
of §3.5; Layer 5 §6.0 keeps owner activation/arm-revision checks. This is a bounded
process-local dispatcher, not all Timing or all Layer 0.

## Implementation choices and boundaries

AtJobScheduler takes an explicit MonotonicTimer port. register receives a validated
AtJob, canonical current cycle instant and synchronous owner callback. All mutation
and dispatch are serialized on the same event loop. call_later uses monotonic time,
never calls inline (even delay zero), and returns an idempotent nonblocking cancel
handle. Timer-port failure leaves no callback registered. These are adapter
requirements; this block has no concrete HA/asyncio timer adapter yet.

Each (owner, job_id) has one process-local arm token. A replaced/cancelled arm's
queued timer callback is discarded. Due-now/past requests defer with zero delay;
duration is computed once. rearm_wall_clock keeps due unchanged, uses supplied
current instant, and replaces only wall_clock arms. Elapsed arms remain untouched.
The job is retired before handoff, so delivery can register a new arm with the same
key. Callback exceptions propagate without making the consumed arm pending again.

Admission reconstructs AtJob to revalidate its fields before touching the timer.
Rejected admission preserves existing pending jobs. A timer scheduling failure also
preserves the previous arm. cancel and cancel_all are idempotent. cancel_all empties
current registrations; it does not permanently disable later registration.

A callback already handed to its owner cannot be retracted. Layer 5 must check its
own generation/activation/selected step/revision before acting. Scheduler tokens
are transient and never persisted. pending_jobs is an immutable snapshot, not an
ordering guarantee or persistence API.

No scheduler heap/thread/worker is introduced: the timer adapter owns countdowns.
No ambient wall clock, sleeps, HA objects, storage or numeric policy is added.
Clock-discontinuity detection and cycle-instant generation remain separate work.
Invalid-job diagnostic emission belongs to the future runtime admission boundary;
this internal dispatcher propagates TypeError/ValueError and never arms the invalid
job. No claim that the complete §3.1 service/diagnostic contract is implemented.

## Five-method evidence

### Decision table

| Conditions | Outcome | Test family |
|---|---|---|
| Due before/at/after supplied instant | Deferred zero/positive monotonic delay | deadline_boundaries |
| Same owner and job_id | Replace, cancel old timer, stale callback no-op | replacement |
| Same job_id, other owner; same owner, other id | Independent registrations | owner_scopes |
| Missing/already cancelled key | Idempotent no-op | owner_scopes, cancel_all |
| Active arm token | Retire and hand off once | deadline_boundaries, delivery_retires |
| Missing/replaced arm token | No delivery | owner_scopes, replacement |
| Wall correction + elapsed arm | Original countdown untouched | only_wall_clock, property_wall_correction |
| Wall correction + wall_clock arm | Same due, new countdown; zero if passed | only_wall_clock, repeated_wall_rearm |
| Invalid job/instant/callback | Reject, no timer/state change | invalid_dynamic_job, invalid_admission_inputs |
| Timer scheduling failure on replacement | Old registration remains usable | timer_failure |
| Owner callback raises | Arm stays consumed | owner_exception |

### Boundary value analysis

Due-now difference: -1 s, -1 microsecond, zero, +1 microsecond, +1 s.
Callback tests inspect just before and at a due; repeated delivery is suppressed.
Wall correction examples: same instant, forward beyond due, backward before due.
Empty registry, repeated cancellation, equal job_id across owners and distinct
job_id within one owner are exercised. No arbitrary schedule horizon is introduced.

### MC/DC

There is no new compound Boolean decision in this module. Each admission, key,
basis and stale-arm gate is a single predicate, with both outcomes covered. Missing
arm and mismatched token are separate guards. MC/DC is not inferred from branch
coverage. Existing shared AtJob validators retain their prior MC/DC evidence.

### Property-based testing

Hypothesis seed 3145, 50 examples per property. Generated register/cancel sequences
across owners/keys deliver only the last surviving registration per key; forcing
all recorded callbacks afterwards produces no duplicate. Generated forward/backward
wall corrections preserve an elapsed arm's original monotonic deadline. Oracles
use latest selected revisions and an elapsed boundary, not a copy of scheduler code.

The fake timer uses a priority queue and deterministic monotonic advances, without
sleep or real wall-clock reads. The property uses exactly representable half-second
advances around its ten-second boundary; an initial decimal accumulation assertion
was fixed in the test to avoid floating-point error in the fake clock.

### Mutation testing

mutmut 3.8.0, fresh temporary copy, only runtime/timing.py mutated; all tests/v3
selected. 95 mutants: 87 killed, 8 survived, no timeout/error/untested. All survivors
change generic TypeError prose only; see ATJOB_MUTANT_REVIEW.md for exact diffs.
No non-equivalent behavioral survivor found, and no 100% raw score claimed.
An import-provenance test confirms the mutated source tree is used.

## Verification and next work

241 tests passed (25 new), seed 3145. New module: 59 statements/18 branches covered.
Ruff lint/format, mypy and patch hygiene pass. No concrete timer-adapter, HA/live,
restart/storage, recurrence next-due/DST or cycle-clock diagnostic/gap evidence yet.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```

Mutation reproduction: copy source/tests/config to a temporary directory and set
only_mutate to runtime/timing.py there, then mutmut run --max-children 4. Workspace
mutmut defaults now select tests/v3 and all five implemented modules, so its full
run has a broader scope than the 95-mutant report above.


## Hardware portability requirement — 2026-10-14

The developer explicitly requires correct operation on Raspberry Pi through desktop
hardware. Canonical microsecond timestamp precision is a data representation, not a
promise of microsecond timer resolution or real-time dispatch latency.

Added four behavioral tests: generated callback lateness (0..3600 seconds in the test
generator, not a runtime cutoff), invalidation/replacement of overdue callbacks before
dispatch, and a reversed-order burst of 1000 equal deadlines. Original due remains
unchanged, only the current arm delivers once, and equal-deadline ordering is not
assumed. These are simulated workload cases, not performance benchmarks or a capacity
limit. Complete suite: 245 passed, seed 3145; lint/format pass. Production source was
unchanged, so the previous 95-mutant report remains scoped to that same source revision;
no new mutation run or hardware benchmark is claimed.

Adapter issue found through official documentation: Python 3.14 asyncio call_later
and call_at can run up to one clock-resolution early. A bare delegation cannot be
assumed to implement a strict minimum elapsed deadline; concrete timer implementation
must account for clock resolution and check the monotonic deadline before handoff,
without busy waiting or re-reading wall time for elapsed waits.
Source: https://docs.python.org/3.14/library/asyncio-eventloop.html#asyncio.loop.call_later

Owner callbacks must be brief handoffs into the engine; blocking I/O and heavy CPU
work must not execute inside a timer callback. This follows existing CODE_RULES and
HA event-loop requirements, not a newly chosen lateness/discard policy.
Source: https://developers.home-assistant.io/docs/asyncio_blocking_operations/

Remaining verification before claiming hardware portability: concrete adapter tests
with coarse clocks and early wakeups, loop backlog/late dispatch, cancellation during
backlog, same-deadline bursts and repeated replacements; measure latency, loop occupancy,
peak memory and cancelled-handle cleanup on actual ARM hardware and desktop hardware
once an isolated HA harness is available. Wall-clock re-arm traverses pending jobs,
so its load also needs measurement. No supported-device list, lateness threshold,
minimum duration, admission cap or benchmark pass/fail limit was decided here.
