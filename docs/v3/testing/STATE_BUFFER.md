# Short-term state-transition buffer — impact before implementation

Parent `816e784`; upstream remains `47a4dd4`. Planning `aa4455a` read-only,
with Claude CA4-106 edits confined to L6/L8 and navigation/review files.
Owning L0 §4.0–§4.3 and §13 buffer horizon / sparse state reconstruction rules.

Implement a state-only retention subcomponent, not a complete persistence service:
`runtime/state_buffer.py` consumes immutable AcceptedStateTransition outputs. The
caller supplies registered state keys and their staged horizons; each addressed
stream uses max(900 seconds, declared Window). Owned immutable horizon snapshots
never call upward or resolve patterns while appending. No event admission, current
index mutation, durable queue, generation activation or SQLite writes here.

Keep each stream's accepted transitions in append order; preserve same-cycle
on/off/on and use immutable tuple snapshots for readers. Reject invalid/repeated/
backward append positions before mutation. One cycle must have one instant; a
later cycle has a later instant. Gaps in ordinal/cycle ids are valid (other owners
and unchanged evaluations can occupy them).

Explicit maintenance, outside evaluation, receives a non-regressing cycle-clock
instant; never raw wall time. Future appends may not predate that instant. Remove
only superseded transitions whose successor was already in effect at the horizon
start, retaining the final at-or-before-start predecessor even if arbitrarily old.
Deadline comparisons use shared canonical decimal derive_instant; overflowing
expiration means not yet evictable, not failed admission. Old immutable snapshots
remain valid while maintenance replaces live deque contents. No ad hoc policy
query or claim of complete observation coverage is exposed by a raw records
snapshot. Frozen barrier views/source-age coverage and generation shrink/swap are
future integrations. No fixed byte quota invented for this buffer.

Files: new state_buffer.py, focused behavioral tests and mutation supplement;
mutation scope, README and working/resume context. No dependency, HA public
contract or durable schema change.

Five-method plan: table below/default/above horizon, per-key isolation, state-order
acceptance; boundaries ±1 microsecond around expiry and same-time groups; MC/DC
where compound decisions occur; generated pruning preserving a predecessor and
all later transitions / monotonic surviving suffix; mutation scoped to new module
plus semantic decorator/removal seeds.
## Evidence

28 focused tests and 1731 full V3 tests pass (seed 3145); Ruff lint/format 94 files,
mypy 36 source files. Native arm64 Python 3.14.5; no HA runtime, crash, disk or
hardware-throughput validation is claimed. Full current-index/order suite remains
green; those components are unchanged.

Decision rows:

| Condition | Result |
| --- | --- |
| Declared horizon below / equal to / above 900 s | 900 s / 900 s / declared horizon |
| Extended key and ordinary unrelated key | Independent 3600 s and 900 s horizons |
| No successor | Keep latest indefinitely |
| Successor expiration before / at / after maintenance | Evict / evict / keep predecessor |
| Expiration beyond supported calendar | Keep records; admission remains valid |
| Same cycle, later ordinal, same instant | Append |
| Later cycle and later instant, with gaps in ids/ordinals | Append |
| Duplicate/regressing order, including across keys | Reject before mutation |
| Different instant within cycle, or non-increasing instant in later cycle | Reject |
| Append before maintenance instant | Reject; equal instant allowed |
| Regressing maintenance or maintenance before last append | Reject |

BVA covers ±1 µs around successor expiration and maintenance/append boundaries,
900 s ±1 µs, tiny/huge horizons, empty registered inventory, empty streams and
one/multiple same-time records. A 900.0000001 s horizon expires at the next
representable microsecond, never early. Sparse predecessor and on/off/on fixtures
check reconstruction requirements. Caller declaration map is snapshotted.

MC/DC is N/A: production has only sequential single-condition guards and no
compound Boolean decisions. One generated property checks that retention leaves
a suffix containing the final predecessor and all later transitions, preserves
the latest state and is idempotent; oracle selects predecessor/changes by the
requested window, rather than copying the deque eviction loop. Timing deadline
is disabled locally for this semantic property.

Mutation tool results and exact survivor diffs/proofs are in
[STATE_BUFFER_MUTANTS.md](STATE_BUFFER_MUTANTS.md). Eight semantic seeds test the
module-level default, append direction, wrong-end eviction, immutable snapshots,
maintenance boundary, per-key extension, owned horizons and global append order.
All are killed by named behavioral assertions on a clean 28-test baseline.

## Limits and next integration

The horizon map is already compiled by trusted staging: all registered state
keys are present, each value is that key's maximum declared need (use default
Window(900) for no requirement). Typed requirement union / event stream support
and atomic generation replacement are not implemented by this class. Retention
has no invented global cap. Diagnostics for aggregate bytes and declared horizons,
barrier/source-age-aware FrozenHistoryView, previous-cycle snapshots and durable
queue/overflow/recovery still belong to later owners. No current index is changed
by maintenance, and forced durable baselines must not be appended as live edges.
