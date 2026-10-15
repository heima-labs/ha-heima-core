# SQLite transaction boundary — mutation review, 2026-10-15

Fresh mutmut 3.8, native Python3.14.5/SQLite3.53.1, only storage/sqlite_transactions.py,
all tests/v3, seed3145, four children: **144 generated,73 killed,71 survived; zero
error/timeout/skipped/untested/interrupted.** All survivors were individually inspected:
55 generic error-message variants, 11 SQL letter-case variants, two initial timeout
variants overwritten before SQL, a falsey private flag variant, and two setup-cleanup
variants. Exact diffs and contract-equivalence proofs appear below. No raw 100% claim.

The first run had 71 killed,71 survivors and two pytest processes marked interrupted:
mutated cleanup let a test KeyboardInterrupt escape its intended catcher. No human
interrupted the task. Replaced that test signal with a dedicated direct BaseException
subclass (WorkerAbort), retaining actual asyncio.CancelledError tests. This preserves
BaseException cleanup/group coverage while making a bad mutation fail pytest instead
of aborting its process. Added upper-neighbor timeout and real SQL constraint checks,
then reran from a fresh mutants directory. Production source did not change between
runs; final survivor IDs/diffs match the initially inspected surviving set.

During development, a real regression demonstrated that a trusted callback's accidental
COMMIT then BEGIN could leave the first part durable before failing. The new SQLite
authorizer denies callback transaction/savepoint control. The regression first failed
on disk contents, then passed; a warmed-connection test checks statement-cache reuse.

## Reproduction and supplementary evidence

In a fresh temp source/tests copy with pytest-v3.ini/pyproject.toml, narrow only_mutate
to sqlite_transactions.py, retain all tests/v3 and seed3145, then run:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_sqlite_transactions.py
```

Run path /private/tmp/heima-v3-sqlite-transactions, final log
/private/tmp/heima-sqlite-mutmut-final.log. Default repo scope adds this module to the
previous eighteen. The scoped result is not fresh evidence for unchanged modules.
No new frozen dataclasses/properties or application module constants are excluded from
function mutation. Imported SQLite action constants and SQL semantics get targeted
supplements: early return before COMMIT, ROLLBACK instead of COMMIT, and SQLITE_OK
instead of SQLITE_DENY for callback control. All three killed after a clean 48-test
baseline. Each seed runs its named behavioral test explicitly with pytest exit1;
collection errors or zero selected tests are not counted. An initial overly strict
expected-first-failure selection was corrected; its rejection was not counted as a kill.

## Individually inspected survivors

### x__outside_event_loop__mutmut_1

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__outside_event_loop__mutmut_1: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,4 +3,4 @@
         asyncio.get_running_loop()
     except RuntimeError:
         return
-    raise RuntimeError("SQLite writer I/O requires a worker outside the event loop")
+    raise RuntimeError(None)
```

### x__outside_event_loop__mutmut_2

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__outside_event_loop__mutmut_2: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,4 +3,4 @@
         asyncio.get_running_loop()
     except RuntimeError:
         return
-    raise RuntimeError("SQLite writer I/O requires a worker outside the event loop")
+    raise RuntimeError("XXSQLite writer I/O requires a worker outside the event loopXX")
```

### x__outside_event_loop__mutmut_3

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__outside_event_loop__mutmut_3: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,4 +3,4 @@
         asyncio.get_running_loop()
     except RuntimeError:
         return
-    raise RuntimeError("SQLite writer I/O requires a worker outside the event loop")
+    raise RuntimeError("sqlite writer i/o requires a worker outside the event loop")
```

### x__outside_event_loop__mutmut_4

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__outside_event_loop__mutmut_4: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,4 +3,4 @@
         asyncio.get_running_loop()
     except RuntimeError:
         return
-    raise RuntimeError("SQLite writer I/O requires a worker outside the event loop")
+    raise RuntimeError("SQLITE WRITER I/O REQUIRES A WORKER OUTSIDE THE EVENT LOOP")
```

### x__discard_and_raise__mutmut_5

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__discard_and_raise__mutmut_5: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -9,7 +9,7 @@
             errors.append(authorization_error)
         try:
             if connection.in_transaction:
-                connection.execute("ROLLBACK")
+                connection.execute("rollback")
         except BaseException as cleanup_error:
             errors.append(cleanup_error)
     try:
```

### x__discard_and_raise__mutmut_14

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__discard_and_raise__mutmut_14: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,5 +17,5 @@
     except BaseException as close_error:
         errors.append(close_error)
     if len(errors) > 1:
-        raise BaseExceptionGroup("SQLite transaction and cleanup failures", errors)
+        raise BaseExceptionGroup("XXSQLite transaction and cleanup failuresXX", errors)
     raise failure
```

### x__discard_and_raise__mutmut_15

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__discard_and_raise__mutmut_15: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,5 +17,5 @@
     except BaseException as close_error:
         errors.append(close_error)
     if len(errors) > 1:
-        raise BaseExceptionGroup("SQLite transaction and cleanup failures", errors)
+        raise BaseExceptionGroup("sqlite transaction and cleanup failures", errors)
     raise failure
```

### x__discard_and_raise__mutmut_16

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.x__discard_and_raise__mutmut_16: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,5 +17,5 @@
     except BaseException as close_error:
         errors.append(close_error)
     if len(errors) > 1:
-        raise BaseExceptionGroup("SQLite transaction and cleanup failures", errors)
+        raise BaseExceptionGroup("SQLITE TRANSACTION AND CLEANUP FAILURES", errors)
     raise failure
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_2

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_2: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def __init__(self, path: Path, *, busy_timeout_ms: int) -> None:
     _outside_event_loop()
     if not isinstance(path, Path):
-        raise TypeError("SQLite writer requires an explicit database path")
+        raise TypeError(None)
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_3

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_3: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def __init__(self, path: Path, *, busy_timeout_ms: int) -> None:
     _outside_event_loop()
     if not isinstance(path, Path):
-        raise TypeError("SQLite writer requires an explicit database path")
+        raise TypeError("XXSQLite writer requires an explicit database pathXX")
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_4

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_4: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def __init__(self, path: Path, *, busy_timeout_ms: int) -> None:
     _outside_event_loop()
     if not isinstance(path, Path):
-        raise TypeError("SQLite writer requires an explicit database path")
+        raise TypeError("sqlite writer requires an explicit database path")
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_5

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_5: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def __init__(self, path: Path, *, busy_timeout_ms: int) -> None:
     _outside_event_loop()
     if not isinstance(path, Path):
-        raise TypeError("SQLite writer requires an explicit database path")
+        raise TypeError("SQLITE WRITER REQUIRES AN EXPLICIT DATABASE PATH")
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_8

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_8: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if not isinstance(path, Path):
         raise TypeError("SQLite writer requires an explicit database path")
     if type(busy_timeout_ms) is not int:
-        raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
+        raise TypeError(None)
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
     connection = connect(path, timeout=0.0, autocommit=True)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_9

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_9: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if not isinstance(path, Path):
         raise TypeError("SQLite writer requires an explicit database path")
     if type(busy_timeout_ms) is not int:
-        raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
+        raise TypeError("XXSQLite lock timeout must be a non-boolean integer in millisecondsXX")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
     connection = connect(path, timeout=0.0, autocommit=True)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_10

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_10: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if not isinstance(path, Path):
         raise TypeError("SQLite writer requires an explicit database path")
     if type(busy_timeout_ms) is not int:
-        raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
+        raise TypeError("sqlite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
     connection = connect(path, timeout=0.0, autocommit=True)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_11

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_11: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if not isinstance(path, Path):
         raise TypeError("SQLite writer requires an explicit database path")
     if type(busy_timeout_ms) is not int:
-        raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
+        raise TypeError("SQLITE LOCK TIMEOUT MUST BE A NON-BOOLEAN INTEGER IN MILLISECONDS")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
     connection = connect(path, timeout=0.0, autocommit=True)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_17

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_17: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
-        raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
+        raise ValueError(None)
     connection = connect(path, timeout=0.0, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_18

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_18: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
-        raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
+        raise ValueError("XXSQLite lock timeout is outside its integer-millisecond rangeXX")
     connection = connect(path, timeout=0.0, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_19

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_19: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
-        raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
+        raise ValueError("sqlite lock timeout is outside its integer-millisecond range")
     connection = connect(path, timeout=0.0, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_20

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_20: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if type(busy_timeout_ms) is not int:
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
-        raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
+        raise ValueError("SQLITE LOCK TIMEOUT IS OUTSIDE ITS INTEGER-MILLISECOND RANGE")
     connection = connect(path, timeout=0.0, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_26

Equivalent initial connection timeout. SQLite connection creation is followed first by an explicit PRAGMA busy_timeout, before any journal/schema/transaction SQL. That native setting replaces the initial callback, so no actual lock-waiting SQL observes the constructor timeout variant. Final busy_timeout verification remains unchanged.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_26: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -6,7 +6,7 @@
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
-    connection = connect(path, timeout=0.0, autocommit=True)
+    connection = connect(path, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_28

Equivalent initial connection timeout. SQLite connection creation is followed first by an explicit PRAGMA busy_timeout, before any journal/schema/transaction SQL. That native setting replaces the initial callback, so no actual lock-waiting SQL observes the constructor timeout variant. Final busy_timeout verification remains unchanged.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_28: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -6,7 +6,7 @@
         raise TypeError("SQLite lock timeout must be a non-boolean integer in milliseconds")
     if busy_timeout_ms < 0 or busy_timeout_ms > 2_147_483_647:
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
-    connection = connect(path, timeout=0.0, autocommit=True)
+    connection = connect(path, timeout=1.0, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_33

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_33: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -9,7 +9,7 @@
     connection = connect(path, timeout=0.0, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
-        if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
+        if connection.execute("pragma busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_34

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_34: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -9,7 +9,7 @@
     connection = connect(path, timeout=0.0, autocommit=True)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
-        if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
+        if connection.execute("PRAGMA BUSY_TIMEOUT").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_36

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_36: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -10,7 +10,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError(None)
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_37

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_37: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -10,7 +10,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError("XXSQLite lock timeout was not establishedXX")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_38

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_38: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -10,7 +10,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError("sqlite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_39

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_39: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -10,7 +10,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError("SQLITE LOCK TIMEOUT WAS NOT ESTABLISHED")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_42

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_42: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -11,7 +11,7 @@
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
-        if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
+        if connection.execute("pragma journal_mode=wal").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_43

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_43: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -11,7 +11,7 @@
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
-        if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
+        if connection.execute("PRAGMA JOURNAL_MODE=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_47

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_47: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError(None)
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_48

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_48: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError("XXSQLite WAL mode was not establishedXX")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_49

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_49: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError("sqlite wal mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_50

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_50: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError("SQLITE WAL MODE WAS NOT ESTABLISHED")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_53

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_53: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -13,7 +13,7 @@
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
-        connection.execute("PRAGMA synchronous=FULL")
+        connection.execute("pragma synchronous=full")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_54

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_54: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -13,7 +13,7 @@
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
-        connection.execute("PRAGMA synchronous=FULL")
+        connection.execute("PRAGMA SYNCHRONOUS=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_57

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_57: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -14,7 +14,7 @@
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
-        if connection.execute("PRAGMA synchronous").fetchone() != (2,):
+        if connection.execute("pragma synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_58

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_58: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -14,7 +14,7 @@
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
-        if connection.execute("PRAGMA synchronous").fetchone() != (2,):
+        if connection.execute("PRAGMA SYNCHRONOUS").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_61

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_61: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -15,7 +15,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError(None)
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_62

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_62: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -15,7 +15,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError("XXSQLite FULL synchronization was not establishedXX")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_63

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_63: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -15,7 +15,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError("sqlite full synchronization was not established")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_64

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_64: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -15,7 +15,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError("SQLITE FULL SYNCHRONIZATION WAS NOT ESTABLISHED")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_67

Equivalent falsey private rollback selector: None and False both skip the same branch; the argument is neither returned nor serialized.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_67: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,7 +17,7 @@
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
-        _discard_and_raise(connection, error, rollback=False)
+        _discard_and_raise(connection, error, rollback=None)
     self._connection = connection
     self._owner_thread = get_ident()
     self._closed = False
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_71

Equivalent for the supported native connection at setup failure: it is autocommit with no begun transaction or installed authorizer. Resetting the already absent authorizer is idempotent, and the in_transaction guard skips ROLLBACK. Original error, closure and database contents are unchanged. This is not a claim of equivalence under an artificial failure injected solely into that additional no-op reset.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_71: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,7 +17,7 @@
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
-        _discard_and_raise(connection, error, rollback=False)
+        _discard_and_raise(connection, error, rollback=True)
     self._connection = connection
     self._owner_thread = get_ident()
     self._closed = False
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_74

Equivalent private initial falsey sentinel. The flag is only tested for truthiness until an actual close/failure replaces it with True; it is not public state or stored metadata.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_74: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -20,4 +20,4 @@
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
     self._owner_thread = get_ident()
-    self._closed = False
+    self._closed = None
```

### xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_2

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_2: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,4 +1,4 @@
 def _assert_owner(self) -> None:
     _outside_event_loop()
     if get_ident() != self._owner_thread:
-        raise RuntimeError("SQLite writer belongs to another worker thread")
+        raise RuntimeError(None)
```

### xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_3

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_3: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,4 +1,4 @@
 def _assert_owner(self) -> None:
     _outside_event_loop()
     if get_ident() != self._owner_thread:
-        raise RuntimeError("SQLite writer belongs to another worker thread")
+        raise RuntimeError("XXSQLite writer belongs to another worker threadXX")
```

### xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_4

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_4: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,4 +1,4 @@
 def _assert_owner(self) -> None:
     _outside_event_loop()
     if get_ident() != self._owner_thread:
-        raise RuntimeError("SQLite writer belongs to another worker thread")
+        raise RuntimeError("sqlite writer belongs to another worker thread")
```

### xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_5

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_5: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,4 +1,4 @@
 def _assert_owner(self) -> None:
     _outside_event_loop()
     if get_ident() != self._owner_thread:
-        raise RuntimeError("SQLite writer belongs to another worker thread")
+        raise RuntimeError("SQLITE WRITER BELONGS TO ANOTHER WORKER THREAD")
```

### xǁSQLiteTransactionWriterǁrun__mutmut_1

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_1: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def run[T](self, operation: Callable[[Connection], T]) -> T:
     self._assert_owner()
     if self._closed:
-        raise RuntimeError("SQLite writer is closed")
+        raise RuntimeError(None)
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_2

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_2: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def run[T](self, operation: Callable[[Connection], T]) -> T:
     self._assert_owner()
     if self._closed:
-        raise RuntimeError("SQLite writer is closed")
+        raise RuntimeError("XXSQLite writer is closedXX")
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_3

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_3: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def run[T](self, operation: Callable[[Connection], T]) -> T:
     self._assert_owner()
     if self._closed:
-        raise RuntimeError("SQLite writer is closed")
+        raise RuntimeError("sqlite writer is closed")
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_4

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_4: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -1,7 +1,7 @@
 def run[T](self, operation: Callable[[Connection], T]) -> T:
     self._assert_owner()
     if self._closed:
-        raise RuntimeError("SQLite writer is closed")
+        raise RuntimeError("SQLITE WRITER IS CLOSED")
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_7

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_7: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if self._closed:
         raise RuntimeError("SQLite writer is closed")
     if not callable(operation):
-        raise TypeError("SQLite operation must be callable")
+        raise TypeError(None)
     if self._connection.in_transaction:
         raise RuntimeError("SQLite writer does not allow nested transactions")
     try:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_8

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_8: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if self._closed:
         raise RuntimeError("SQLite writer is closed")
     if not callable(operation):
-        raise TypeError("SQLite operation must be callable")
+        raise TypeError("XXSQLite operation must be callableXX")
     if self._connection.in_transaction:
         raise RuntimeError("SQLite writer does not allow nested transactions")
     try:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_9

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_9: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if self._closed:
         raise RuntimeError("SQLite writer is closed")
     if not callable(operation):
-        raise TypeError("SQLite operation must be callable")
+        raise TypeError("sqlite operation must be callable")
     if self._connection.in_transaction:
         raise RuntimeError("SQLite writer does not allow nested transactions")
     try:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_10

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_10: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,7 +3,7 @@
     if self._closed:
         raise RuntimeError("SQLite writer is closed")
     if not callable(operation):
-        raise TypeError("SQLite operation must be callable")
+        raise TypeError("SQLITE OPERATION MUST BE CALLABLE")
     if self._connection.in_transaction:
         raise RuntimeError("SQLite writer does not allow nested transactions")
     try:
```

### xǁSQLiteTransactionWriterǁrun__mutmut_11

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_11: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
-        raise RuntimeError("SQLite writer does not allow nested transactions")
+        raise RuntimeError(None)
     try:
         self._connection.execute("BEGIN IMMEDIATE")
         self._connection.set_authorizer(_operation_authorizer)
```

### xǁSQLiteTransactionWriterǁrun__mutmut_12

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_12: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
-        raise RuntimeError("SQLite writer does not allow nested transactions")
+        raise RuntimeError("XXSQLite writer does not allow nested transactionsXX")
     try:
         self._connection.execute("BEGIN IMMEDIATE")
         self._connection.set_authorizer(_operation_authorizer)
```

### xǁSQLiteTransactionWriterǁrun__mutmut_13

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_13: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
-        raise RuntimeError("SQLite writer does not allow nested transactions")
+        raise RuntimeError("sqlite writer does not allow nested transactions")
     try:
         self._connection.execute("BEGIN IMMEDIATE")
         self._connection.set_authorizer(_operation_authorizer)
```

### xǁSQLiteTransactionWriterǁrun__mutmut_14

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_14: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -5,7 +5,7 @@
     if not callable(operation):
         raise TypeError("SQLite operation must be callable")
     if self._connection.in_transaction:
-        raise RuntimeError("SQLite writer does not allow nested transactions")
+        raise RuntimeError("SQLITE WRITER DOES NOT ALLOW NESTED TRANSACTIONS")
     try:
         self._connection.execute("BEGIN IMMEDIATE")
         self._connection.set_authorizer(_operation_authorizer)
```

### xǁSQLiteTransactionWriterǁrun__mutmut_17

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_17: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -7,7 +7,7 @@
     if self._connection.in_transaction:
         raise RuntimeError("SQLite writer does not allow nested transactions")
     try:
-        self._connection.execute("BEGIN IMMEDIATE")
+        self._connection.execute("begin immediate")
         self._connection.set_authorizer(_operation_authorizer)
         result = operation(self._connection)
         self._connection.set_authorizer(None)
```

### xǁSQLiteTransactionWriterǁrun__mutmut_22

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_22: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         result = operation(self._connection)
         self._connection.set_authorizer(None)
         if not self._connection.in_transaction:
-            raise RuntimeError("SQLite operation changed transaction ownership")
+            raise RuntimeError(None)
         self._connection.execute("COMMIT")
     except BaseException as error:
         # A failed/uncertain transaction is never reused or automatically retried.
```

### xǁSQLiteTransactionWriterǁrun__mutmut_23

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_23: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         result = operation(self._connection)
         self._connection.set_authorizer(None)
         if not self._connection.in_transaction:
-            raise RuntimeError("SQLite operation changed transaction ownership")
+            raise RuntimeError("XXSQLite operation changed transaction ownershipXX")
         self._connection.execute("COMMIT")
     except BaseException as error:
         # A failed/uncertain transaction is never reused or automatically retried.
```

### xǁSQLiteTransactionWriterǁrun__mutmut_24

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_24: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         result = operation(self._connection)
         self._connection.set_authorizer(None)
         if not self._connection.in_transaction:
-            raise RuntimeError("SQLite operation changed transaction ownership")
+            raise RuntimeError("sqlite operation changed transaction ownership")
         self._connection.execute("COMMIT")
     except BaseException as error:
         # A failed/uncertain transaction is never reused or automatically retried.
```

### xǁSQLiteTransactionWriterǁrun__mutmut_25

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_25: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
         result = operation(self._connection)
         self._connection.set_authorizer(None)
         if not self._connection.in_transaction:
-            raise RuntimeError("SQLite operation changed transaction ownership")
+            raise RuntimeError("SQLITE OPERATION CHANGED TRANSACTION OWNERSHIP")
         self._connection.execute("COMMIT")
     except BaseException as error:
         # A failed/uncertain transaction is never reused or automatically retried.
```

### xǁSQLiteTransactionWriterǁrun__mutmut_28

SQL letter case only. SQLite keywords/these pragma names and setting keywords are case-insensitive. Native effects and returned pragma values are identical; fault injection normalizes SQL case too.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_28: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -13,7 +13,7 @@
         self._connection.set_authorizer(None)
         if not self._connection.in_transaction:
             raise RuntimeError("SQLite operation changed transaction ownership")
-        self._connection.execute("COMMIT")
+        self._connection.execute("commit")
     except BaseException as error:
         # A failed/uncertain transaction is never reused or automatically retried.
         self._closed = True
```

### xǁSQLiteTransactionWriterǁclose__mutmut_1

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁclose__mutmut_1: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,6 +3,6 @@
     if self._closed:
         return
     if self._connection.in_transaction:
-        raise RuntimeError("Cannot close SQLite writer during an operation")
+        raise RuntimeError(None)
     self._closed = True
     self._connection.close()
```

### xǁSQLiteTransactionWriterǁclose__mutmut_2

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁclose__mutmut_2: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,6 +3,6 @@
     if self._closed:
         return
     if self._connection.in_transaction:
-        raise RuntimeError("Cannot close SQLite writer during an operation")
+        raise RuntimeError("XXCannot close SQLite writer during an operationXX")
     self._closed = True
     self._connection.close()
```

### xǁSQLiteTransactionWriterǁclose__mutmut_3

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁclose__mutmut_3: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,6 +3,6 @@
     if self._closed:
         return
     if self._connection.in_transaction:
-        raise RuntimeError("Cannot close SQLite writer during an operation")
+        raise RuntimeError("cannot close sqlite writer during an operation")
     self._closed = True
     self._connection.close()
```

### xǁSQLiteTransactionWriterǁclose__mutmut_4

Generic exception/group prose only. Exception types, cleanup members, rejection boundary and commit/result behavior are unchanged; no message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁclose__mutmut_4: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -3,6 +3,6 @@
     if self._closed:
         return
     if self._connection.in_transaction:
-        raise RuntimeError("Cannot close SQLite writer during an operation")
+        raise RuntimeError("CANNOT CLOSE SQLITE WRITER DURING AN OPERATION")
     self._closed = True
     self._connection.close()
```
