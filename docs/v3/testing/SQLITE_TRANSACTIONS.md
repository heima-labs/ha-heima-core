# Worker-owned SQLite transaction boundary — 2026-10-15

## Sources and bounded implementation choices

Planning clean/read-only 37986ea: Layer 0 §4.2 atomic end-of-cycle facts+marker,
§4.4 durable confirmation/watermark and §4.6 ordered retry/loss declarations. The
approved engine design is SQLite WAL with synchronous=FULL, one serialized writer
outside the HA event loop. No planning edits, dependency or Git/deploy policy changes.

storage/sqlite_transactions.py adds SQLiteTransactionWriter(path,busy_timeout_ms=...),
run(operation) and close(). It owns a real on-disk native sqlite3 connection, verifies
WAL/FULL and the explicitly supplied busy timeout, and uses SQL BEGIN IMMEDIATE,
COMMIT and ROLLBACK. Python autocommit=True avoids implicit transaction ownership;
Connection.commit/rollback methods and the connection context manager would not provide
this boundary in that mode. See [Python transaction control](https://docs.python.org/3.14/library/sqlite3.html#transaction-control-via-the-autocommit-attribute).

The busy timeout is a required integer in SQLite's native millisecond interface,
0..2147483647; no operational default, retry cadence or Window/deadline rounding rule
is introduced. Values outside the representable range reject before opening a file.
The native timeout is set before journal/schema/transaction SQL and then read back.
See [SQLite busy timeout](https://sqlite.org/c3ref/busy_timeout.html) and
[WAL/FULL durability setting](https://sqlite.org/pragma.html#pragma_synchronous).

The writer enforces creator-thread affinity and rejects open/run/close while an event
loop is running on that thread. The host must supply a dedicated worker and its
existing bounded queue; this primitive adds no executor or second queue. It does not
choose the V3 database location, fact/metadata tables, schema version, checkpoint cadence,
retention, HA lifecycle, range assembler or actual watermark transaction.

## Transaction and failure behavior

| Stage | Database effect | Result/publication |
| --- | --- | --- |
| Setup or BEGIN failure | no operation accepted | exception; connection discarded |
| Operation/SQL failure | explicit rollback attempted, then close | no result |
| Failure before COMMIT completes | rollback if transaction still active, then close | no result |
| Driver error after a real COMMIT | whole transaction may already be durable | no result; reconcile by operation identity before retry |
| COMMIT succeeds | all operation statements durable together | return operation result |
| Later close error | cannot undo a prior successful commit | close error exposed |

No automatic retry occurs. Any transaction failure retires the connection. Rollback,
authorizer reset and close errors are preserved with the original failure in a
BaseExceptionGroup (ordinary ExceptionGroup when applicable). Cancellation/other
BaseException paths do not bypass cleanup. Normal close is idempotent on the owner
worker; nested run/close operations reject.

Internal storage callbacks must not publish results before run returns or leak live
connections/cursors to another thread. A SQLite authorizer rejects accidental callback
transaction and savepoint control, preventing COMMIT/BEGIN from splitting the batch.
It is removed for the owner's COMMIT/rollback. See [SQLite authorization](https://sqlite.org/c3ref/set_authorizer.html).
Callbacks are trusted Python code, not an untrusted SQL interface: they must not replace
the authorizer or connection configuration. Unexpected loss of transaction ownership
also rejects. Reusing a warmed connection still denies a callback's cached COMMIT.

A transaction result may be a candidate ClockGapBoundaryReceipt, but this primitive
does not implement production boundary-row correlation or a receipt issuer. The future
domain operation must write the matching row and return the matching receipt only via
this post-COMMIT result. No application schema is created by this module. Tables used
below are synthetic test fixtures, not a selected HouseFact or marker SQL schema.

## Five-method evidence

48 focused instances on actual temporary on-disk databases; Python3.14.5/SQLite3.53.1.

- Decision tables: setup verification/BEGIN/body/pre-COMMIT/post-COMMIT failure/success;
  independent rollback+close failures; authorizer cleanup; ordinary/BaseException groups;
  owner/wrong worker/event-loop calls; nested calls/close and prohibited SQL control.
- BVA: busy timeout -1/0/+1 and max-1/max/max+1; bool/float/nonfinite/path errors;
  empty fact batch and failure before/after marker; closed/idempotent close; unsupported
  in-memory WAL; real lock contention with zero wait and explicit reconnection.
- MC/DC: timeout rejection is A OR B, A=ms<0, B=ms>MAX. Valid0 => FF, -1 => TF,
  MAX+1 => FT; each independently changes rejection. Authorizer action membership,
  ownership, transaction presence and cleanup-count checks are single predicates and
  have decision/boundary cases. No branch metric is claimed as MC/DC certification.
- PBT: 30 generated lists of fact values and cuts before each statement, before/after
  the marker, or no cut. A fresh real database per example must show all facts+marker
  or neither via an independent reopened connection. Deadline=None avoids treating
  storage speed as correctness on slower hardware; no performance threshold is chosen.
- Mutation: fresh sqlite_transactions.py-only mutmut, all tests/v3:144 generated,
  73 killed,71 contract-equivalent survivors (55 error prose,11 SQL case,5 internal/
  overwritten setup variants), no timeout/error/untested/interrupted. Exact individual
  diffs/proofs in SQLITE_TRANSACTIONS_MUTANTS.md. Three supplements kill early result
  publication, ROLLBACK in place of COMMIT and allowing callback transaction control
  after a clean 48-test baseline. Tests first reproduced the partial-commit callback
  regression before adding the authorizer. Mutation-runner selection and test abort
  handling were corrected transparently; see the mutation review.

Independent reads see neither facts nor marker during the operation and both after
run returns. Real uniqueness-constraint failure rolls both back. A post-COMMIT injected
failure deliberately demonstrates an uncertain result with a fully committed database,
so a future retry owner must reconcile using stable operation ids. A dedicated
single-worker executor test runs real SQL off the main event loop and observes its
scheduled callback. This is not a production async host or cancellation controller.

## Validation and remaining work

915 V3 tests pass (48 above committed867), seed3145. Ruff lint/format60files,mypy25sources,
diff hygiene pass. Default mutation scope nineteen modules. No new dependency,
production database/schema, HA deployment, ARM throughput or power-cut test is claimed.
Only temporary test databases were written. Parent671f3b4 contains the previous
accounting gate; this transaction boundary remains uncommitted pending review.

Next implement domain SQL operations and idempotent reconciliation, matching committed
rows to receipts/accounting ranges and writing the watermark only after the complete
barrier proof. Concrete schema/worker lifecycle and bounded retry integration remain
implementation work. A cancelled await does not itself prove a worker's SQLite operation
was rolled back; that lifecycle is outside this primitive.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/storage/test_sqlite_transactions.py --hypothesis-seed=3145 -q
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145 -q
.venv-v3/bin/python tests/v3/mutation_sqlite_transactions.py
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```
