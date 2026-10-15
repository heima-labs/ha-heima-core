# Current CA4-102 checkpoint — 2026-10-15

Source of truth: planning **working copy**, feat/v3-planning at base 0b82d61 with
uncommitted CA4-102 changes; Layer 0 §3.5/§10/§13, review CA4-102 and backlog entry.
No planning edits by Codex. This section supersedes historical descriptions below
that made any frozen tick delay a non-frozen-mode gap.

## Behavior and impact

Each correction opens an independent immutable boundary intent. Both compare and
next_cycle select await_floor_recovery only for backward discontinuity AND behind
floor. finish never changes this mode. False closes at the first tick strictly after
start even if that tick is frozen; True waits until raw wall strictly exceeds the
current tick's floor. An already ended intent never changes. Periodic detection
still opens at the preceding cycle; cycle detection of a frozen backward correction
starts at the detecting frozen cycle, per CA4-98. The **end rule**, not necessarily
the start instant, is independent of detection point.

The exact 100/90 -> 94 reproducer now closes the new forward gap at 100.000002 in
both paths, while the bootstrap backward gap remains open until recovery. Forward
recovery closes both independent gaps on the same cycle; a further -5 s opens its
own frozen gap; -0.5 s while frozen emits only the regression requirement. A periodic
backward-ahead gap still ends on the first later cycle if a subsequent -0.5 s
correction freezes that tick. This removes the old promotion expectation in the test
formerly named test_ca498_periodic_gap_waits_if_next_cycle_freezes.

Production search: only clock.py reads await_floor_recovery or implements finish;
TimingClock returns the immutable comparison/tick to its observer without managing
open gap state. Existing timing-clock tests remain green. No diagnostics emitter,
active gap registry, persistence or §4.4 acknowledgement is implemented by this patch.
Elapsed scheduling, due, basis and re-arm are unchanged and covered by the full suite.

## Five-method evidence

- Decision table: test_ca4102_gap_mode_decision_table_and_mcdc crosses direction,
  behind/ahead and cycle_start/periodic_check. Separate scenarios cover all executable
  rows in review CA4-102: exact reproducer, recovery of both gaps, further backward
  gap, small regression and immutable intents. Durable acknowledgement is a future
  storage integration obligation; an end here does not claim completeness.
- BVA: open_floor_boundaries crosses both directions and detection paths at floor-1us,
  floor and floor+1us. discontinuity_threshold_boundaries checks each direction at
  1s-1us, exactly 1s, 1s+1us. frozen_gap_finish_requires_wall_strictly_above_floor checks
  the recovery floor at -1us/0/+1us; first_cycle_end_excludes_the_start_cycle_itself
  checks the end's strict lower boundary. Existing nanosecond threshold tests remain.
- MC/DC, backward AND behind, in **both** detection paths: decision-table rows
  backward/behind => True; forward/behind => False changes only direction;
  backward/ahead => False changes only behind. Forward/ahead completes the table.
  finish's end/strict-start/mode/behind/strict-recovery guards each have tests; no new
  compound Boolean condition is introduced there.
- PBT: test_property_ca4102_gap_ends_independent_of_detection_path generates 100
  sequences (1..35 signed microsecond corrections). Paired clocks receive the same
  wall/monotonic samples at cycles, one with a preceding periodic comparison. Every
  open intent keeps its mode; all corresponding end instants agree at each step and
  after recovery; no correction is detected twice. Start differences for frozen
  backward gaps are intentionally preserved. Hypothesis seed 3145, with shrinking.
- Mutation: fresh clock.py-only mutmut 3.8 run against all tests/v3: 216 generated,
  199 killed, 17 reviewed equivalents, no timeout/error/skipped/untested. Initial run
  exposed missing strict-start boundary coverage; added that behavioral test and ran
  again with a fresh mutant directory. Five supplemental threshold/frozen-decorator
  mutations killed with a clean baseline. Exact diffs in
  [CYCLE_CLOCK_CA4102_MUTANT_REVIEW.md](CYCLE_CLOCK_CA4102_MUTANT_REVIEW.md).

Before code changes, new tests reproduced **5 failures**, 40 passes (45 new instances).
The added mutation-driven strict-start case brings the final addition to 46 instances.
Final focused suite: **101 passed**; full V3 suite: **633 passed**, seed 3145. Ruff
lint/format, mypy (21 sources), diff hygiene pass. No HA run, ARM timing benchmark,
SQLite acknowledgement or deploy evidence is claimed.

## Reproduction

Use the native .venv-v3 and dedicated configs. To keep generated caches outside the
workspace, set PYTHONDONTWRITEBYTECODE=1, HYPOTHESIS_STORAGE_DIRECTORY to a temp path,
pytest -p no:cacheprovider and mypy --cache-dir to a temp path.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/runtime/test_cycle_clock.py --hypothesis-seed=3145 -q
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145 -q
.venv-v3/bin/python tests/v3/mutation_clock.py
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```

---

# Historical checkpoints (superseded where inconsistent with CA4-102)

# Current CA4-99 checkpoint

Execution references are now separate per basis. Read
[CA499_EXECUTION_REFERENCES.md](CA499_EXECUTION_REFERENCES.md) for the current API,
355-test evidence, paired clock reads, exact regression and mutation results.
Earlier evidence below is historical where superseded, especially single-instant
scheduler calls and the execution-reference ambiguity.

# Cycle clock — current CA4-98 status

Current source/spec checkpoint: planning `dd89383`, Layer 0 §§3.5/10/13.
The former ambiguity is resolved by CA4-98. Earlier evidence below describes the
pre-CA4-98 revision and is historical where superseded here.

## CA4-98 implementation

ClockComparison carries cycle_start/periodic_check detection point, exact bootstrap
floor offset where available, wall_behind_floor, diagnostic requirement, re-arm
requirement and a ClockGap boundary intent. Runtime emission/wiring remains pending.
The floor comparison was corrected from wall<previous to wall<previous+1us; a regression
test failed on the former equality case before the fix. Canonical microsecond text
allows the periodic check to use equivalent wall<=previous without calendar overflow.

At a non-frozen detecting cycle, gap start=previous cycle, end=current cycle. At a
frozen detecting cycle, start=current frozen cycle, end pending. At a periodic check,
start=last cycle, end pending. Gap.finish(tick) produces a new boundary intent on a
later cycle, waiting through freeze and, for frozen intervals, until wall is strictly
above that cycle's floor. It is idempotent for an already closed intent. The caller
retains independent intents; no merging, queue, persistence schema or acknowledgement
policy was introduced. Before any history floor exists, comparisons can report clock
facts but cannot fabricate a preceding-cycle boundary. Periodic services are not
bootstrapped by this helper.

Small negative correction AND wall below floor requires clock_regression. Backward
discontinuities always require it, even above floor. Forward jumps never require the
regression diagnostic solely from a positive correction. Pure results neither emit
diagnostics nor certify a durable gap. Historical reads remain a future persistence
responsibility; an end intent is not durable confirmation.

## Five-method evidence for this change

- Decision tables: detecting cycle above/below floor, periodic above/below floor,
  small negative correction above/below floor, forward discontinuity, pending/closed
  gap and eventual floor recovery. CA498 test families exercise each row.
- Boundaries: wall 1 us below/at/above previous, at/above previous+1us; gap start versus
  later cycles; recovery exactly at floor versus strictly above; unchanged >1 s
  nanosecond tests remain. Bootstrap offsets distinguish unknown elapsed measurement.
- MC/DC: correction<0 AND wall_behind_floor. Tests use (-0.4 wall,0.1 mono) as both-true,
  (0 wall,0 mono) keeps behind true but changes negativity, and (0.5 wall,1 mono)
  keeps correction=-0.5 but changes behind. Each changes diagnostic outcome independently.
- Properties: generated backward jumps still above floor produce adjacent-cycle bounds
  and required diagnostic; earlier monotonicity/exact-drift properties remain.
- Mutation: fresh runtime/clock.py run: 198 total, 185 killed, 13 survivors, no errors/
  timeouts/untested. Twelve generic-error prose variants and one unread private startup
  sentinel; exact diffs in CYCLE_CLOCK_CA498_MUTANT_REVIEW.md. First run found missing
  periodic floor assertions; added them and reran without cached mutant results.
  Supplement mutation_clock.py kills threshold and all three frozen-result decorators:
  four targeted mutants total.

Current suite: **336 passed** (17 added to previous 319), seed 3145. Ruff lint/format,
mypy and patch hygiene pass. No new dependency, policy threshold, HA/ARM benchmark,
actual diagnostic emission, periodic scheduling, scheduler re-arm orchestration or
persistence acknowledgement is claimed. Clock descriptor additions have defaults;
existing internal consumers retain the previous comparison fields. Only the corrected
floor equality behavior intentionally changes, as required by the authoritative spec.

## Earlier evidence — historical source revision


Scope: Layer 0 §3.5 against planning 9cd077e, with Layer 1 §4 canonical instants.
This is the deterministic clock foundation. It does not implement gap persistence,
HA clock reads, engine barriers, diagnostics or timer/periodic-service wiring.

## API and design

CycleClock takes the latest known durable instant, or None for an empty new store.
next_cycle receives canonical wall text and nonnegative monotonic integer nanoseconds.
It produces max(wall, previous + 1 microsecond), returns the previous instant and a
wall_behind_floor flag, and advances its process-local floor. Its results retain no
datetime. No clock read or I/O occurs inside the component; Layer 0 will supply paired
readings at the future adapter boundary. Different cycles are strictly increasing;
equal raw wall readings are accepted. Calendar overflow fails without partially
updating state.

ClockDiscontinuityDetector shares a comparison baseline across cycle and periodic
checks. CycleClock.compare updates that baseline without generating a cycle.
Integer arithmetic computes wall-elapsed minus monotonic-elapsed; >+1 s is forward,
<-1 s backward, inclusive +/-1 s creates no discontinuity. Equal monotonic readings
are allowed; a regressing reading or bool/wrong type rejects without consuming state.
This is a within-process elapsed counter and is never restored from persistence.

Bootstrap has no elapsed measurement (adjustment_ns=None). A reading more than one
second below the durable floor is backward; a forward difference remains downtime,
not an inferred clock jump. The first valid sample establishes the in-process
comparison baseline. ClockComparison.requires_wall_clock_rearm returns whether a
classified discontinuity exists. It is an explicit request fact, not a performed
scheduler operation. wall_behind_floor is likewise a comparison fact, not a complete
clock_regression diagnostic policy.

A large pause in the event loop alone does not imply a discontinuity: when elapsed
wall and monotonic readings agree, adjustment is zero. The clock's monotonic units
and threshold are exact integers, independent of float uptime precision and CPU speed.
No hardware precision/latency claim or new tolerance/minimum is introduced.

## Specification clarification

Layer 0 §3.5's backward-gap start assumes a frozen cycle. Between readings 60 seconds
apart, a -2 second correction advances the wall by 58 seconds: detected backward,
yet no frozen cycle exists. See ../clarifications/CLOCK_GAP_BOUNDARIES.md. Gap bounds
and the corresponding diagnostic condition need authoritative clarification. This
module reports the independent established facts; it does not choose those policies.

## Five-method evidence

### Decision table

| Condition | Outcome | Test family |
|---|---|---|
| No durable floor/first sample | First cycle uses wall; no fabricated elapsed interval | first_installation |
| Wall before/equal/after previous cycle | Floor +1 microsecond / +1 microsecond / wall | cycle_floor |
| Bootstrap wall more than 1 s behind floor | Backward classification | bootstrap_backward |
| Bootstrap wall at -1 s or forward | No inferred discontinuity | bootstrap_backward |
| Adjustment strictly beyond +/-1 s | Forward/backward + re-arm required | exact_nanosecond |
| Adjustment within inclusive limits | No discontinuity | exact_nanosecond |
| Long elapsed time with agreeing clocks | Ordinary progress | slow_hardware |
| Backward correction while wall still advances | Backward classification, no freeze | backward_correction |
| Wall still behind prior cycle | Strict microsecond progress until caught up | regression_keeps |
| Periodic check without cycle | Update comparison baseline, retain cycle floor | periodic_comparison |
| Invalid/regressing monotonic reading or malformed wall | Reject and preserve state | invalid_monotonic, monotonic_regression |
| Unrepresentable next cycle | Reject and preserve both baselines | calendar_floor_overflow |

### Boundary value analysis

Before/equal/after cycle floor; previous +1 microsecond; repeated same readings;
bootstrap threshold -1,000,001/-1,000,000/-999,999 microseconds. Normal comparison
threshold +/-1,000,000,000 nanoseconds plus one nanosecond on either side. Zero and
negative monotonic readings, bool/noninteger inputs, microseconds across midnight,
maximum supported calendar and long pauses are tested.

### MC/DC

No new compound Boolean decision exists in this module. Threshold and startup
conditions are separate single-predicate branches with both outcomes tested;
max selects between wall and a strict successor. This is not a claim that branch
coverage proves MC/DC. The prior canonical-instant validator retains its own evidence.

### Property-based testing

Hypothesis seed 3145, 50 examples per property. Generated oscillating wall inputs
produce strictly increasing cycles at or above wall, preserve ordinary future wall
values and advance exactly one microsecond when floored. Generated elapsed time plus
a signed correction yields exactly that correction independent of elapsed duration.
Oracles assert monotonicity, canonical round trips and correction relations, not a
copy of production clock state transitions.

### Mutation testing

Fresh mutmut 3.8.0, runtime/clock.py only, all tests/v3 selected: 125 generated,
112 killed, 13 survived, no errors/timeouts/untested. Twelve survivors change generic
exception prose; one changes an unread initial private wall sentinel which is replaced
before the elapsed baseline is ever used. Exact diffs and rationale in
CYCLE_CLOCK_MUTANT_REVIEW.md. A first run exposed unchecked result wall/False fields;
stronger assertions killed those two behavioral mutants in a fresh second run.
No known non-equivalent behavioral survivor remains; raw score is not 100%.

Supplement tests/v3/mutation_clock.py kills a one-nanosecond threshold change and
removal of frozen metadata on both outcome dataclasses. The runner checks a passing
baseline, fails each mutant in a named test, and works in a temporary copy.

## Results and limits

319 tests pass (33 new), seed 3145. 68 clock statements/18 branches covered.
Ruff lint/format, mypy, three supplementary mutations and patch hygiene pass.
No real-clock adapter, ARM benchmark, 60-second CronEntry service, durable floor
loading, ingress normalization/engine barrier, diagnostic emission, scheduler
re-arm wiring or gap persistence is claimed. The clarification blocks gap-boundary
policy; the validated instant/classification slice remains usable independently.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145
.venv-v3/bin/python tests/v3/mutation_clock.py
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```

To reproduce the exact 125-mutant scope, copy source/tests/config into a fresh
 temporary directory and narrow only_mutate to runtime/clock.py there before
mutmut run --max-children 4. Default workspace scope includes all seven modules.


## Critical review after CA4-98 — 2026-10-14

Confirmed and fixed one code defect: a forward correction while a prior regression
still freezes cycle instants incorrectly used the backward-gap rule (start=current,
end pending). §3.5 Forward jump requires adjacent-cycle bounds. Frozen-floor bounds
now require backward direction AND wall behind floor. An existing backward gap
remains open independently; closing the new forward gap cannot certify recovery.

Regression test and generated property both failed before the fix (2 failures),
then passed. Example: durable floor 100, initial wall 90; next wall 93 after 1 mono
second detects +2 s but is still below the floor. The new gap spans the two adjacent
cycle instants; the older backward gap still has no end.

Five-method mapping: decision table is forward/backward crossed with frozen/not
frozen (all four rows covered by new and existing tests). Boundary evidence preserves
strict +1 s nanosecond limits and the two adjacent microsecond cycle instants.
MC/DC for backward AND behind: frozen backward baseline; frozen forward changes
only direction; non-frozen backward changes only behind. Each independently changes
selection of the frozen-gap rule. New Hypothesis property generates forward corrections
and different floor values, preserving adjacent-cycle bounds while remaining frozen.

Fresh mutation run: 202 generated, 189 killed, 13 survived, no error/timeout/untested.
All survivors have the same IDs and diffs already reviewed in
CYCLE_CLOCK_CA498_MUTANT_REVIEW.md: generic exception prose and the unread private
startup sentinel. Four supplementary threshold/frozen-decorator mutations still killed.
Current suite: 338 passed, seed 3145; Ruff/type/format/patch pass.

Review also found a separate spec-reference contradiction before clock/scheduler
integration: cycle instant can be ahead of corrected wall, so due-cycle may arm an
absolute wall_clock job too early. Reproducer and Claude prompt in
../clarifications/CLOCK_SCHEDULING_REFERENCE.md. Scheduler behavior remains unchanged
pending authoritative clarification. No claim of HA/ARM, persistence or integration
correctness is made from the pure helper results.
