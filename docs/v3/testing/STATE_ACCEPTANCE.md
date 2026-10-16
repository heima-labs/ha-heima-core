# Live state acceptance and coordinator order — impact before implementation

Parent `4cef5a9` (local commit only; upstream remains `47a4dd4`). Planning `aa4455a`
read-only with unchanged CA4-106 edits in L6/L8/registry/backlog. Read L0 §4.0,
§4.1/§4.2/§4.7, §3.5, §5.2, registry L0-STATE-HISTORY and L0-FROZEN-HISTORY.

In-memory current index and explicit cycle-context coordinator. A cycle
captures installed generation, supplied cycle instant and origin; stale handles
cannot mutate a later cycle. Primitive integer cycle ids allocated monotonically
from an explicit process seed (default 0); cross-restart seed restoration belongs
to the future durable coordinator. One-based append ordinal makes 0 mean no appends.
The same allocator can serve later event owners; no event path implemented now.

Build only through exact fixed-source ports; expose expected-generation guard
there so a port captured against another snapshot cannot pass a cycle. Consume
bounded diagnostics through a prompt explicit sink, compare canonical state
fingerprint against live current, allocate only on change, update live current,
return immutable(fact,AppendOrder) metadata to future buffer/queue owner. Preserve
on/off/on in one instant. No raw externally-constructed fact admission API.

No growing per-process journal/retry queue added: caller must synchronously forward
each returned transition to the future short-term buffer/durable queue before
next admission. This component is the live comparison/order step, not the full
atomic buffer+queue publication integration or persistence. Forced baselines,
retention/overflow, snapshots/subscribers and generation invalidations remain
separate owners. Current dictionary retains the last accepted fact per key.

All mutation methods reject reentrancy; diagnostics must not block or publish HA
calls. Build/diagnostic/fingerprint failures leave index and order unchanged.
Recheck captured generation after callbacks before any state change. Closing a
failed cycle is permitted so cleanup cannot strand a stale handle; accepted live
transitions do not roll back with a later durable failure.

Five-method plan: changed/unchanged/availability/confidence/source decision rows;
cycle/time/ordinal and stale-context boundaries; MC/DC if compound predicates;
PBT run-length transition preservation and increasing orders. Fresh mutation on
new coordinator and touched port plus immutable/reentrancy/order semantic seeds.

## Verification results

38 coordinator tests and 23 producer-port tests pass (61 focused); full V3 suite:
1703 passed, seed 3145. Ruff lint and format pass (91 files); mypy passes (35 source
files). Native arm64 Python 3.14.5. No HA integration, crash or hardware throughput
claim is made by these in-memory tests.

Decision table covers unchanged/value/evidence/confidence/availability and source
changes. Boundaries cover cycle-time equality/regression, ordinal one/reset, stale
and closed handles, malformed inputs, and build/diagnostic failures. Reentrancy
and late generation changes cannot mutate the index/order. No compound Boolean
predicate is introduced: MC/DC is not applicable to the sequential single-condition
guards. Two seeded properties preserve run-length state transitions, current state,
and order within one cycle and across many cycles; timing deadlines are disabled
locally because these are semantic properties, not throughput assertions.

Mutation results and every survivor proof are recorded in
[STATE_ACCEPTANCE_MUTANTS.md](STATE_ACCEPTANCE_MUTANTS.md). The permanent mutation
scope now includes 29 modules. No dependency, persistence schema, HA public
contract or product policy changed.
