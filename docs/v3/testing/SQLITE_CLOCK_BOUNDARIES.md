# SQLite clock boundaries — implementation slice

## Impact and choices before implementation

Planning 37986ea read-only: Layer 0 §3.5 independent per-correction gaps, §4.2
end-of-cycle atomicity, §4.4 durable acknowledgement, §4.6 queued continuity items.
Existing ClockGapBoundaryReceipt owns field validation; ClockGapDurability owns
matching complete runtime intents and independently arriving receipts. The approved
SQLiteTransactionWriter owns transaction lifetime and post-COMMIT publication.

This slice adds a callable immutable ClockGapBoundaryWrite, plus transactional
schema preparation. The callable can join other SQL work in the same writer.run
callback, including future facts/marker operations. Its result is a candidate until
writer.run succeeds. Never publish the inner callback result. No per-boundary flush,
queue admission, thread/executor or automatic retry policy is introduced.

Storage decision: one narrow version-named `clock_gap_boundaries_v1` STRICT table,
composite primary key (gap_id,boundary), canonical UTC TEXT when, INTEGER inclusion
0/1. Separate immutable boundary rows preserve independent gaps and out-of-order
acknowledgements. The key is this operation's reconciliation identity: equal replay
returns matching data after COMMIT; altered time/inclusion rejects and rolls back.
No generic operation journal is needed for this immutable insert-only operation;
future mutable operations must define their own stable identity/reconciliation.
A mutable one-row-per-gap upsert was rejected because it can overwrite independent
boundary intent or turn a conflicting replay into silent success. JSON blobs would
hide the uniqueness/correlation fields. A general fact schema is outside this slice.
The version-named table scopes the first schema without assigning a global user_version
or pretending V2 migration exists; future schema changes require explicit review.

No timestamps or inclusions are inferred, no gap ID allocated, and no opening is
required before a closing row (the existing durability API admits out-of-order
receipts). The future runtime owner must supply a valid matched ClockGap intent;
this table is not a substitute for that cross-boundary validation. Retention,
startup enumeration and actual historical timeline assembly remain future work;
this slice does not introduce a deletion or retention policy.

## Planned verification

Decision table: new / identical / changed time / changed inclusion × side;
independent IDs/sides; shared batch failure; commit uncertainty before/after actual
COMMIT. BVA: empty ID rejected, minimal ID, Unicode/quoted ID, first/last canonical
instant, inclusion booleans, same vs one-microsecond-different boundary. MC/DC:
each equality field changes independently; transaction presence independently rejects
schema/application outside a batch. PBT: replay and order independence on a fresh
on-disk DB with a dictionary oracle, plus conflict rollback. Mutation: fresh scoped
mutmut and SQL/frozen-value semantic supplements. Final results recorded below.


## Final evidence

39 new focused instances; full V3 **960 passed**, seed3145. Real temporary on-disk
SQLite verifies no reader-visible boundary before COMMIT, atomic rollback with
fixture facts, exact immutable replay, differing time/inclusion rejection,
independent IDs/sides, closing-first delivery, re-open and explicit reconciliation
after both pre-COMMIT and post-actual-COMMIT errors. Integration uses the committed
closing receipt in ClockGapDurability to release only that gap's coverage restriction.
Validation includes reconstructed invalid operations, canonical minimum/maximum
instants and explicit booleans, raw Unicode/quote/NUL-containing IDs with no added
normalization. First storage choice used gap_id <> '' rather than SQL length because
SQLite's length stops at NUL while the existing nonempty-string validator accepts it;
tests cover that boundary without changing the domain.

MC/DC for stored!=expected: same key/data succeeds; time alone or inclusion alone
changes rejection; id and side independently change identity and create separate
rows. Transaction presence independently controls schema/write admission. BVA and
PBT evidence as described above: thirty generated fresh databases with dictionary
oracle and reversed exact replay. Ruff lint/format63files,mypy26sources,diff check
pass. Fresh mutation45generated,33killed,12individually reviewed generic-prose
equivalents; zero errors/timeouts/skipped/untested/interrupted, five supplements
killed. See SQLITE_CLOCK_BOUNDARIES_MUTANTS.md for exact diffs and limits.

The future owner must allocate gap IDs uniquely across restarts for the retained
store. No allocator or pruning policy is introduced here: future retention must
preserve identity/reconciliation guarantees. Reconciliation is explicit submission
of this immutable operation on a replacement writer; no generic blind retry was
added. Callers must propagate failed operations so the writer can roll back the
entire enclosing batch. No live HA, real power cut, ARM throughput or deployment
verification ran. SQLite metadata staging uses only temporary test databases.
