# Asyncio monotonic timer adapter

Implemented against planning 9cd077e, Layer 0 §3.1, and the developer's Raspberry Pi
through desktop requirement. This completes the concrete countdown mechanism for
the existing AtJobScheduler port; HA bootstrap/lifecycle wiring is still absent.

## Design and source references

AsyncioMonotonicTimer receives the existing loop. It creates no loop, worker, thread,
per-job task, polling cadence or blocking operation. All access belongs to that loop
thread. Timer resolution is read once from standard monotonic clock metadata; an
alternative loop must supply its matching resolution explicitly. No device minimum,
grace period or lateness-discard threshold is introduced.

A finite nonnegative delay is converted once into a monotonic deadline. TwoSum
recovers binary64 addition error: only a rounded-down sum is advanced to the next
representable float. The result is the smallest float at or after the exact sum.
This avoids collapsing a tiny positive wait at a large uptime; exact sums are left
unchanged. These are ephemeral execution numbers, not canonical contract timestamps.
Unrepresentable deadlines reject before creating a timer.
Numerical reference: [Ogita, Rump and Oishi, Accurate Sum and Dot Product,
Algorithm 3.1](https://www.tuhh.de/ti3/paper/rump/OgRuOi05.pdf).

The initial call_at uses that deadline. Every wake checks loop.time first. A wake
before the deadline re-arms at the later of the original deadline and the first
float strictly beyond now + clock_resolution; this puts the next request beyond
the documented early-wakeup horizon rather than making a ready-loop busy wait.
No wall-clock read or duration recomputation occurs. A late wake delivers once.
The handle clears its owner callback before delivery or cancellation and cancels
its latest backend handle, including a re-armed one. Owner exceptions propagate
without enabling duplicate delivery.

Python documents one-clock-resolution early delivery and unspecified ordering of
equal deadlines: [Python 3.14 event-loop methods](https://docs.python.org/3.14/library/asyncio-eventloop.html#asyncio.loop.call_later).
The adapter checks deadlines rather than treating callback arrival as proof of expiry.

HA integration must use this port on HA's loop, keep owner handoffs brief, cancel
scheduler registrations on unload, and emit admission/technical diagnostics at its
runtime boundary. This slice does not create that boundary. Closed-loop scheduling
errors propagate. It adds no retry/failover policy for a closing or failed event loop.

## Five-method evidence

### Decision tables

| Input/state | Outcome | Test family |
|---|---|---|
| Zero/signed-zero delay | Defer; deadline is current monotonic instant | zero_tiny_and_exact |
| Positive finite delay | Minimum elapsed deadline, never inline | zero_tiny_and_exact, real_asyncio |
| Bool/wrong type/negative/nonfinite/overflow integer | Reject, no registration | invalid_delay |
| Unrepresentable monotonic sum | Reject before scheduling | callback_and_unrepresentable |
| Exact/upward-rounded/downward-rounded sum | Smallest float not before exact sum | property_deadline |
| Early wake | No owner handoff, re-arm beyond early horizon | early_wake, property_early |
| At or after deadline | Handoff once, no further countdown | at_or_after |
| Cancelled/consumed wake | No work | cancel_releases, at_or_after |
| Cancel after early re-arm | Cancel latest backend handle | cancel_releases |
| Callback raises | Consumed timer cannot deliver again | callback_exception |
| Missing vs explicit clock metadata | Read default once vs use explicit value | clock_metadata |
| Invalid resolution | Reject | invalid_resolution |
| Backend scheduling fails | Propagate, no backend registration | scheduling_failure |

### Boundary value analysis

Delay -smallest subnormal/zero/+smallest subnormal, ordinary integers/fractions,
NaN/infinities and overflow integer; zero resolution versus positive values.
Monotonic instants immediately before/at/after deadline; 1 ns, 1 ms and 1 s injected
resolution (test cases, not supported-device claims). Maximum binary64 sums that
overflow, and max finite uptime plus tiny positive wait whose ceiling is infinite,
reject. Exact additions add no extra ULP or resolution. Cancellation before/after
an early re-arm and duplicate wakeups are covered.

### MC/DC

The only new compound Boolean decision is not-finite OR negative delay. Inf/1
holds the negative predicate false and changes finiteness; -1/1 holds finite true
and changes negativity. Existing invalid_delay and zero_tiny_and_exact families
exercise those pairs. Other gates are single predicates with both outcomes tested.
This evidence is independent of the 64-statement/18-branch coverage report.

### Property-based testing

Hypothesis seed 3145. 100 examples compare scheduled deadlines with an independent
exact Fraction sum: result is at or above the exact value and its predecessor is
below it. Generated origins include negative references, large uptimes and tiny
subnormal waits. Fifty examples generate early wakeup/lateness/cancellation and
prove absence of early/duplicate delivery. Fractions are test oracles only; no
Fraction/Decimal value enters runtime payloads or duration contracts.

### Mutation testing

Fresh mutmut 3.8.0 run on adapters/ha/monotonic_timer.py, all tests/v3 selected:
117 generated, 92 killed, 25 survived, no errors/timeouts/untested. Reviewed survivors:
24 alter uncontracted exception prose; one alters typing.cast's type argument, which
has no runtime effect. Exact diffs in MONOTONIC_ADAPTER_MUTANT_REVIEW.md. No known
non-equivalent behavioral survivor remains; raw mutation score is not 100%.

## Results and limits

286 tests pass (41 new), seed 3145. Ruff lint/format and mypy pass. New module:
64 statements/18 branches covered. Fake-loop tests include scheduler/adapter
replacement after early wakeup. Two actual Python event-loop cases prove deferred
zero-delay delivery and minimum positive duration; the 10 s watchdog is a test
hang guard, not an approved runtime latency requirement. Import provenance checks
ensure mutation tests execute the copied source.

No Raspberry Pi/ARM or HA workload benchmark has run. No bound on latency, CPU or
memory is claimed, no isolated HA lifecycle harness exists yet. Cycle-clock/gaps,
recurrence/DST, diagnostic emission, persistence and HA bootstrap remain pending.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```

For the exact 117-mutant scope, copy source/tests/config to a fresh temp directory
and narrow only_mutate to adapters/ha/monotonic_timer.py before mutmut run
--max-children 4. Default workspace scope includes all six implemented modules.
