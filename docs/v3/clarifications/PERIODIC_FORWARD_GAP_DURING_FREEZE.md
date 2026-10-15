# Claude prompt — periodic forward detection while an earlier backward floor holds

Status: RESOLVED by approved CA4-102, 2026-10-15. Authoritative planning working copy
on feat/v3-planning, base 0b82d61, contains uncommitted CA4-102 edits to Layer 0
§3.5/§10/§13, review and backlog. Codex has made no planning edits.

A gap's end rule is fixed by its own correction: forward or backward ahead of the
floor ends at the first post-detection cycle, even if frozen; backward behind waits
for wall strictly above the floor. Detection point does not change the rule; gaps
remain independent. Implemented and tested in runtime/clock.py; evidence in
../testing/CYCLE_CLOCK.md and CYCLE_CLOCK_CA4102_MUTANT_REVIEW.md. An end remains an
intent, not durable acknowledgement (§4.4).

The original prompt below is historical and must not be treated as an open question.

## Prompt

Read current Layer 0 §3.5 (Forward jump, Backward jump, Detection by the periodic
check), §4.4 durable boundary acknowledgement, clock diagnostics and §13; include
CA4-98's reviewed boundary rules. The following is an executable implementation
counterexample, not a proposed normative rule.

### Approved text and exact ambiguity

- Forward jump: gap from last cycle before correction to first cycle after it.
- Backward jump below floor: first frozen cycle to the first cycle whose wall exceeds
  the floor; older gaps remain independently open until their rule is satisfied.
- Periodic detection: last cycle to first later cycle, "or later under the
  frozen-floor rule above". The text does not explicitly distinguish a forward
  correction that occurs while an earlier backward correction still holds the floor.

Current code chooses different bounds for the new forward gap by detection path.
CycleClock.next_cycle checks backward AND behind before choosing frozen bounds.
CycleClock.compare sets await_floor_recovery from behind alone; ClockGap.finish
also waits whenever the next tick is behind its floor. Thus the same new forward
correction ends at the first cycle in one path and stays open in the other.

### Reproducer (relative wall seconds)

1. Durable floor = 100. At monotonic 0, wall = 90. Bootstrap produces cycle
   100.000001 and an earlier backward/frozen gap.
2. At monotonic 1, wall = 94: wall advanced 4 s over 1 monotonic s, so this is a
   new +3 s discontinuity, with wall still below the floor.
3. Detection at a cycle: new forward gap is 100.000001 -> 100.000002, closed intent.
4. Detection at the periodic check: new forward gap starts at 100.000001; the next
   cycle at monotonic 2 / wall 95 is 100.000002. finish(tick) still has end=None and
   await_floor_recovery=True. The old backward gap remains separately open in both.

Verified using current APIs:

```python
from datetime import UTC, datetime, timedelta
from custom_components.heima.v3.contracts.instants import format_instant
from custom_components.heima.v3.runtime.clock import CycleClock

anchor = datetime(2026, 1, 1, tzinfo=UTC)
def at(seconds):
    return format_instant(anchor + timedelta(seconds=seconds))

direct = CycleClock(at(100))
direct.next_cycle(at(90), 0)
print(direct.next_cycle(at(94), 1_000_000_000).comparison.gap)

periodic = CycleClock(at(100))
periodic.next_cycle(at(90), 0)
comparison = periodic.compare(at(94), 1_000_000_000)
tick = periodic.next_cycle(at(95), 2_000_000_000)
print(comparison.gap.finish(tick))
```

### Requested bounded specification decision

Define whether this new forward gap closes at the first post-detection cycle or
inherits frozen-floor waiting, and make both detection paths explicit and coherent.
Keep the earlier backward gap independent. Reconcile §3.5, §13 and diagnostics;
retain the >1 s threshold, unchanged due/basis, elapsed monotonic waits and §4.4's
durable acknowledgement requirement. If the periodic sentence intends a different
policy, state its reason rather than inferring a fix from current code.

Return the normative sections and acceptance examples through the existing
registry/backlog/review workflow. Codex will then implement the chosen gap mode;
it has not silently changed ClockGap or either detection path in this review.
