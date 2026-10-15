# Critical review — SQLite boundary and continuity integration, 2026-10-15

## Scope and contract

Baseline commit `9207821` (SQLite), plus the interfaces introduced in
`671f3b4` (accepted-prefix accounting), `956039d` (durable clock boundaries),
`f628736` and `d965470` (observation assessment and clipping). Read current planning
`37986ea`, clean and read-only: Layer 0 §4.1 CycleCommitMarker, §4.2 atomic failed
batches, §4.4 acknowledgement/watermarks and §4.6 loss/accounting. No specification
change is required for the finding. No production domain SQL schema exists yet.

## P1 — writes after SQLite's implicit rollback escaped batch atomicity (fixed)

`SQLiteTransactionWriter.run` used an explicit transaction and denied callback
COMMIT/ROLLBACK/SAVEPOINT. However, SQLite can itself end a transaction on an error.
The authorizer did not verify transaction ownership before subsequent SQL, so a
callback catching that error could execute a new statement in autocommit mode.
The final `in_transaction` check detected the loss only after the damage.

Native on-disk reproducer, no mocked failure or disabled guard:

```python
def operation(connection):
    connection.execute("INSERT INTO facts VALUES (1, 42)")
    try:
        connection.execute("INSERT OR ROLLBACK INTO facts VALUES (1, 99)")
    except sqlite3.IntegrityError:
        pass
    connection.execute("INSERT INTO markers VALUES (1)")
```

On the committed baseline, `run` raised RuntimeError, but an independent reopened
connection found **no facts and marker 1 durable**. This violates L0 §4.2's rule
that a failed batch creates neither a marker nor a partial successful cycle.
The standalone probe and both cold/warmed regression rows reproduced the defect.
The regression tests first failed on those actual database contents, rather than
merely an exception type mismatch. `INSERT OR ABORT` control rows passed, because
that conflict leaves the enclosing transaction active.

### Correction and cost

The callback authorizer now denies SQL preparation whenever the owned transaction
has ended. Transaction/savepoint control remains denied while it is active. The
connection explicitly sets `cached_statements=0`: SQLite calls the authorizer at
preparation, so cached statements could otherwise bypass the new state check.
The post-operation ownership check and connection retirement remain in place.
Ordinary ABORT conflict handling is still allowed inside the same transaction.
No retries, error recovery transactions, schema or receipt semantics were invented.

This deliberately trades statement-cache reuse for atomicity. Repeated SQL within
a batch must be prepared again; prior authorizer changes already invalidated cache
reuse between operations. No Raspberry Pi throughput benchmark, HA integration,
real disk-failure or power-loss experiment was run. Callbacks remain trusted
internal Python, must not replace authorizers/settings or leak live handles, and
must not publish before `run` returns. This is not an untrusted-code sandbox.

Primary API references: [SQLite conflict handling](https://sqlite.org/lang_conflict.html)
explains transaction-ending ROLLBACK versus statement-only ABORT;
[SQLite authorizer](https://sqlite.org/c3ref/set_authorizer.html) documents compile-time
rather than execution-time checks; [Python sqlite3](https://docs.python.org/3.14/library/sqlite3.html)
documents the prepared-statement cache parameter. The defect and fix above were
verified against actual native Python 3.14.5 / SQLite 3.53.1, not inferred from docs.

## Five-method evidence

| Decision conditions | Expected behavior | Evidence |
| --- | --- | --- |
| Active transaction, ordinary DML | Allowed, committed as one batch | Existing receipt/atomicity tests |
| Active transaction, callback transaction/savepoint control | Denied, whole batch rolled back | Existing control tests |
| ABORT constraint, callback catches, cold/warmed next SQL | Transaction remains active; facts and marker commit together | New decision-table test, two rows |
| ROLLBACK constraint, callback catches, cold/warmed next SQL | Further SQL denied; no partial batch durable; writer retired | New decision-table test, two rows |

MC/DC: active ordinary SQL versus active transaction-control isolates the control
condition; active ordinary SQL versus ordinary SQL after rollback isolates the
`not connection.in_transaction` condition. Both are independent causes of denial.
BVA: zero/one/multiple statements preceding rollback, with cold/warmed statements
and a pre-existing committed row which must survive batch rollback. Cache boundaries
0, 1 and 128 are exercised by the real regression and mutation checks: even a
single cached slot is unsafe when the failed SQL itself is repeated with a new key. PBT: 30
seeded examples vary a 0..8 item prefix, values, warmed marker and execute /
executemany / cursor.execute continuation; the only durable row must be the prior
committed baseline, never any batch fact or marker. Existing failure-cut PBT stays.

Fresh mutation evidence and final validation are recorded in the companion
`SQLITE_CRITICAL_REVIEW_MUTANTS.md` and the final WORKING_CONTEXT checkpoint.

## Integration review and remaining implementation

No further confirmed defect was found in the reviewed pure continuity APIs.
Clock receipt correlation remains explicit (gap identity, side, instant, endpoint),
and pending closing intents do not masquerade as durable ends. Accounting requires
an exhaustive contiguous resolved prefix; loss only resolves after durable loss
metadata. Observation projections remain contributions to combine with mandatory
process and required-stream coverage. None of those value constructors proves that
a database write occurred; the future SQL owner must issue matched receipts only
after successful COMMIT and reconcile uncertain outcomes under stable identities.

Remaining schema/worker/retry-owner/range assembly/watermark/HA lifecycle work is
unimplemented, not certified by this review. No deploy or planning edit occurred.
