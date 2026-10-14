# CA4-99 execution references

Verified planning d58431c (clean): Layer 0 §§3.1/3.5/13 and review CA4-99.

## API and compatibility

ExecutionClockReading is a frozen process-local pair of canonical wall and cycle-
instant references. Construction validates both instants and cycle>=wall. It is not
another history timestamp or persisted schema. CycleClock.read_execution(wall)
computes max(wall,last_cycle+1us), leaving cycle and comparison baselines unchanged.
Cycle starts and periodic comparisons attach their captured pair to ClockComparison.
Standalone ClockDiscontinuityDetector has no history floor and therefore does not
fabricate a complete execution pair.

AtJobScheduler.register(job, paired_reading, callback) selects raw wall for wall_clock
and cycle_instant for elapsed. rearm_wall_clock(paired_reading) uses raw wall, with
unchanged due and replacement key. Admission rebuilds/validates a pair to guard
unvalidated subtypes; failures preserve existing arms. The single-instant API is
intentionally incompatible and rejected, with all existing repository consumers
migrated. No fallback duplicates the two references silently. No public HA contract,
configuration format or durable schema changes exist for this local API transition.

Execution readings are captured at arm/re-arm; callers must not reuse stale snapshots.
The monotonic adapter's early-wakeup and float-deadline protections are unchanged.
A periodic check computes a reference without advancing history. Calendar exhaustion
rejects both a new cycle and a reading requiring an unrepresentable successor.

## Regression evidence

Before correction, actual clock/scheduler + fake timer reproduced wall 100 ->98
at monotonic 1, due 110, cycle 100.000001: assertion for 12s failed because countdown
was 9.999999. After the internal API migration, the same expected countdown passes;
new calls pass the captured pair instead of the obsolete single-instant argument.
Three detection paths (cycle, periodic, bootstrap) now schedule 12s, deliver at
monotonic 13 / corrected wall 110 once, and preserve job_id/due across repeated re-arm.
A 30s elapsed hold under the same floor gets 30s, not 32s. Another case fires a wall
job while history remains floored, proving its due is not used as the cycle instant.

## Five-method evidence

### Decision table

| Conditions | Expected | Tests |
|---|---|---|
| wall_clock + distinct references | due minus wall | basis_selects, regression_due |
| elapsed + distinct references | due minus cycle clock | basis_selects |
| Discontinuity at cycle/periodic/bootstrap | Captured raw wall, same due/key, one delivery | rearm_uses_detection_wall |
| Wall due before/at/after reading | Deferred zero/zero/positive countdown | wall_due_boundaries |
| Existing elapsed arm during wall correction | Original arm unchanged | basis_selects, prior correction properties |
| Invalid pair/single instant | Reject, old arm retained | invalid_execution_pair |
| Between-cycle execution read | Both references, no history/comparison consumption | execution_read_between_cycles |
| Wall due differs from floored history | Firing cycle receives its own floored when | wall_due_and_history |

### Boundaries

Raw wall below/equal/above the cycle floor; wall due -1us/0/+1us; identical pair
fields versus different fields; wrong canonical fields and reversed pair; maximum
calendar successor overflow. Existing >1s discontinuity and deadline tests remain.

### MC/DC

No new compound Boolean decision is introduced by reference selection/pair validation:
selection is one basis predicate, pair ordering is one comparison. Both outcomes
are tested with deliberately different references. Existing clock diagnostic/gap
compound decisions retain their documented independent pairs.

### Property-based testing

Hypothesis seed 3145, max_examples=50. Generated history-floor offsets do not affect
wall countdown for a fixed raw wall and due. Generated execution reads preserve raw
wall, apply the floor, and leave the previous cycle unchanged. Existing registry/
cancellation/elapsed properties were migrated to explicit pairs without altering
expected behavior. Exact example oracles remain 12s/30s and once-only delivery.

### Mutation testing

Fresh mutmut 3.8.0 on runtime/clock.py and runtime/timing.py, all tests/v3 selected:
330 generated, 301 killed, 29 survived; no timeout/error/untested. Twenty-eight
survivors change generic exception prose; one changes an unread private startup
sentinel. All exact diffs reviewed in CA499_MUTANT_REVIEW.md. No known non-equivalent
behavioral survivor remains; raw score is not 100%.
Supplement mutation_clock.py kills all four frozen-result decorators and the
one-second threshold: five targeted mutants, including the new execution pair.

## Results and limitations

355 tests pass (17 added to 338), seed 3145. Ruff lint/format, mypy and patch checks
pass. Both changed modules: all 194 statements covered; 70 reported branches with
three partial paths previously documented for unsupported combinations/no history
floor. Coverage is not MC/DC evidence or a hardware performance result.

Integration tests combine real pure CycleClock and AtJobScheduler with a fake timer,
including bootstrap/periodic/cycle detection and re-arm. Existing two stdlib asyncio
cases still pass. No actual HA periodic service, wall-reader adapter, diagnostic
emission, lifecycle wiring, durable gap/floor acknowledgement, recurring next-due
calculation or ARM workload benchmark is implemented by this slice.

Reproduction: normal tests/v3 commands in TEST_ENVIRONMENT.md. For this exact mutation
scope, copy source/tests/config to a fresh temp directory, narrow only_mutate to the
two modules above, then mutmut run --max-children 4. Default workspace mutation scope
remains all seven implemented modules. No new dependency, tolerance or policy cap.
