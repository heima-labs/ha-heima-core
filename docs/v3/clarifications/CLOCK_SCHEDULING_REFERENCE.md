# Execution clock versus cycle floor — resolved by CA4-99

**Status:** resolved in planning `d58431c`, verified against current Layer 0
§§3.1/3.5/13 and CA4-99 review. The original Claude prompt below is historical.

## Definitive mapping

- wall_clock arm/re-arm uses the unfloored UTC wall reading of that detection.
- elapsed arm uses max(wall, last cycle instant +1us), from which the owner derives due.
  Armed elapsed waits remain monotonic and are not re-armed on wall corrections.
- Reading the cycle-instant clock between cycles neither consumes nor invents a
  history cycle. A firing job requests a cycle; its due is not assigned to history.
- CronEntry's future next-due calculation must choose the same per-basis reference.

ExecutionClockReading(wall, cycle_instant) is the validated immutable internal pair.
CycleClock supplies it in each ClockComparison and via read_execution(wall).
AtJobScheduler.register and rearm_wall_clock now require this pair and select the
correct field internally. The former single-instant API is deliberately rejected;
all repository consumers are tests and were migrated. No public HA or durable schema
exists for this internal API. Runtime callers must capture a current arm-time reading,
not reuse an obsolete snapshot.

The reproducer now re-arms to 12s, including periodic and bootstrap detection.
Elapsed 30s hold remains 30s with frozen floor. Persistence, periodic-service/HA
lifecycle and automatic runtime diagnostic/re-arm wiring are still pending.

## Original prompt (superseded)


Please review this concrete contradiction against current planning specs (checked
at dd89383). Read Layer 0 §3.1 Scheduling semantics, §3.5 Cycle instant/clock
discontinuity and the corresponding §13 acceptance cases before deciding a change.

## Conflicting requirements

- §3.1 requires calculating due minus the current cycle-instant clock at arm/re-arm.
- §3.1 defines wall_clock jobs as externally defined civil/calendar instants and
  says absolute deadlines follow the corrected wall clock.
- §3.5 makes cycle instants strictly increasing after a wall regression, even while
  they are artificially ahead of the wall reading.

## Reproducer

Use relative seconds on a fixed UTC date; all text inputs are canonical instants.

1. Wall=100, monotonic=0, cycle=100. Arm wall_clock job due=110 (10 s).
2. At monotonic=1, wall=98: a backward correction of 3 s is detected. New cycle
   instant=100.000001 because the history floor must remain strictly increasing.
3. Re-arm against unchanged due=110 as §3.1 requires.

Using the stated cycle-instant reference gives 9.999999 s. Using the corrected
wall gives 12 s. The first timer can fire roughly 2 s before the absolute wall due.
This was reproduced with actual CycleClock and AtJobScheduler plus the deterministic
FakeTimer; no HA/live runtime or deployment is involved. AtJobScheduler currently
follows the literal §3.1 reference; the ambiguity is not solved by the monotonic
adapter's minimum-deadline guard.

## Requested clarification

Specify which clock reference is authoritative for wall_clock arm/re-arm when the
cycle clock is floored, including periodic detection and bootstrap. Preserve the
strict history floor, elapsed countdown semantics, immutable canonical due and
no-duplicate delivery. Distinguish execution-time input from the recorded cycle
instant explicitly if required. Do not introduce a lateness/grace threshold or
hardware-specific rounding to conceal the mismatch.

If the answer requires a new product decision, present it to the developer before
changing normative text. Otherwise reconcile owning/dependent sections and acceptance
cases using the spec workflow. Return exact rule, sections and commit for Codex.

Codex has left the scheduler reference unchanged pending clarification. CA4-98's
gap-boundary clarification remains valid and is not reopened by this separate issue.
Do not modify the implementation worktree during the planning change.
