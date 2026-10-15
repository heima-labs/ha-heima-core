# Critical SQLite review — mutation evidence, 2026-10-15

Fresh mutmut 3.8, Python 3.14.5 / SQLite 3.53.1, only sqlite_transactions.py,
all tests/v3, seed3145, four children. **153 generated, 82 killed, 71 survived;
zero timeout/error/skipped/untested/interrupted.** All 71 survivors inspected below:
55 generic prose, 11 SQL-case equivalents, 2 overwritten initial timeout variants,
3 private setup/falsey equivalents. No raw 100% score claim.

The first fresh run had 81 kills and 72 survivors. The extra survivor changed
cached_statements=0 to 1. This was a real test gap, not equivalent: repeating the
same failed SQL with a new key persisted an orphan fact. Added a native regression,
proved it passes with cache0 and fails on actual database contents with cache1,
then restarted from a fresh mutants directory. Final source is unchanged from the
first run; final survivor names/diffs match its inspected set minus that exact seed.

Five supplemental mutations killed after clean54-test baseline: allowing SQL after
implicit rollback, re-enabling cache128, early result before COMMIT, ROLLBACK instead
of COMMIT, allowing explicit callback transaction control. Every seed ran its named
behavioral regression with pytest exit1; collection errors do not count. Automated
mutmut also killed cache1 and removing the cache argument. Existing imported SQLite
constants remain covered by semantic supplements; no new excluded dataclasses or
application constants. This scope does not refresh mutation evidence for unchanged
coverage/accounting/clock modules.

Reproduction in a fresh source/tests copy with scoped pyproject only_mutate:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_sqlite_transactions.py
```

Final run: /private/tmp/heima-sqlite-critical-review/mutants;
log: /private/tmp/heima-sqlite-critical-mutmut-final.log.
The repository's permanent 19-module mutation scope is unchanged. Temporary result
paths are supplementary; exact survivor diffs and reasons are retained here.

## Individually inspected survivors

### x__outside_event_loop__mutmut_1

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_9

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_10

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_11

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_17

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
     # otherwise write in autocommit after SQLite rolls back the whole batch.
     connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_18

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
     # otherwise write in autocommit after SQLite rolls back the whole batch.
     connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_19

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
     # otherwise write in autocommit after SQLite rolls back the whole batch.
     connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_20

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
     # Authorization runs at preparation, not execution. Cached statements could
     # otherwise write in autocommit after SQLite rolls back the whole batch.
     connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_27

Initial connect timeout is overwritten by the first explicit PRAGMA busy_timeout before lock-sensitive SQL. Final timeout verification and actual lock behavior are unchanged.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_27: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -8,7 +8,7 @@
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
     # Authorization runs at preparation, not execution. Cached statements could
     # otherwise write in autocommit after SQLite rolls back the whole batch.
-    connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
+    connection = connect(path, autocommit=True, cached_statements=0)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_30

Initial connect timeout is overwritten by the first explicit PRAGMA busy_timeout before lock-sensitive SQL. Final timeout verification and actual lock behavior are unchanged.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_30: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -8,7 +8,7 @@
         raise ValueError("SQLite lock timeout is outside its integer-millisecond range")
     # Authorization runs at preparation, not execution. Cached statements could
     # otherwise write in autocommit after SQLite rolls back the whole batch.
-    connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
+    connection = connect(path, timeout=1.0, autocommit=True, cached_statements=0)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_36

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_36: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -11,7 +11,7 @@
     connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
-        if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
+        if connection.execute("pragma busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_37

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_37: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -11,7 +11,7 @@
     connection = connect(path, timeout=0.0, autocommit=True, cached_statements=0)
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
-        if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
+        if connection.execute("PRAGMA BUSY_TIMEOUT").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_39

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_39: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError(None)
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_40

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_40: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError("XXSQLite lock timeout was not establishedXX")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_41

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_41: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError("sqlite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_42

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_42: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -12,7 +12,7 @@
     try:
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
-            raise RuntimeError("SQLite lock timeout was not established")
+            raise RuntimeError("SQLITE LOCK TIMEOUT WAS NOT ESTABLISHED")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_45

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_45: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -13,7 +13,7 @@
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
-        if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
+        if connection.execute("pragma journal_mode=wal").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_46

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_46: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -13,7 +13,7 @@
         connection.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
-        if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
+        if connection.execute("PRAGMA JOURNAL_MODE=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_50

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_50: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -14,7 +14,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError(None)
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_51

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_51: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -14,7 +14,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError("XXSQLite WAL mode was not establishedXX")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_52

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_52: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -14,7 +14,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError("sqlite wal mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_53

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_53: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -14,7 +14,7 @@
         if connection.execute("PRAGMA busy_timeout").fetchone() != (busy_timeout_ms,):
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
-            raise RuntimeError("SQLite WAL mode was not established")
+            raise RuntimeError("SQLITE WAL MODE WAS NOT ESTABLISHED")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_56

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_56: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -15,7 +15,7 @@
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
-        connection.execute("PRAGMA synchronous=FULL")
+        connection.execute("pragma synchronous=full")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_57

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_57: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -15,7 +15,7 @@
             raise RuntimeError("SQLite lock timeout was not established")
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
-        connection.execute("PRAGMA synchronous=FULL")
+        connection.execute("PRAGMA SYNCHRONOUS=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_60

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_60: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -16,7 +16,7 @@
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
-        if connection.execute("PRAGMA synchronous").fetchone() != (2,):
+        if connection.execute("pragma synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_61

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_61: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -16,7 +16,7 @@
         if connection.execute("PRAGMA journal_mode=WAL").fetchone() != ("wal",):
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
-        if connection.execute("PRAGMA synchronous").fetchone() != (2,):
+        if connection.execute("PRAGMA SYNCHRONOUS").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_64

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_64: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,7 +17,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError(None)
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_65

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_65: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,7 +17,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError("XXSQLite FULL synchronization was not establishedXX")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_66

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_66: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,7 +17,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError("sqlite full synchronization was not established")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_67

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_67: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -17,7 +17,7 @@
             raise RuntimeError("SQLite WAL mode was not established")
         connection.execute("PRAGMA synchronous=FULL")
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
-            raise RuntimeError("SQLite FULL synchronization was not established")
+            raise RuntimeError("SQLITE FULL SYNCHRONIZATION WAS NOT ESTABLISHED")
     except BaseException as error:
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_70

Private rollback selector None is falsey like False; both skip the same branch, with no serialized or public difference.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_70: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -19,7 +19,7 @@
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
-        _discard_and_raise(connection, error, rollback=False)
+        _discard_and_raise(connection, error, rollback=None)
     self._connection = connection
     self._owner_thread = get_ident()
     self._closed = False
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_74

Supported native setup has no transaction or installed authorizer. Resetting absent authorizer is idempotent; in_transaction is false so no ROLLBACK occurs. Not equivalent under an artificial fault inserted solely in that added no-op reset; that is outside this equivalence claim.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_74: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -19,7 +19,7 @@
         if connection.execute("PRAGMA synchronous").fetchone() != (2,):
             raise RuntimeError("SQLite FULL synchronization was not established")
     except BaseException as error:
-        _discard_and_raise(connection, error, rollback=False)
+        _discard_and_raise(connection, error, rollback=True)
     self._connection = connection
     self._owner_thread = get_ident()
     self._closed = False
```

### xǁSQLiteTransactionWriterǁ__init____mutmut_77

Private initial _closed=None is falsey like False. It is only truth-tested before actual failure/close replaces it with True; no persisted/public value changes.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁ__init____mutmut_77: survived
--- custom_components/heima/v3/storage/sqlite_transactions.py
+++ custom_components/heima/v3/storage/sqlite_transactions.py
@@ -22,4 +22,4 @@
         _discard_and_raise(connection, error, rollback=False)
     self._connection = connection
     self._owner_thread = get_ident()
-    self._closed = False
+    self._closed = None
```

### xǁSQLiteTransactionWriterǁ_assert_owner__mutmut_2

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
         self._connection.set_authorizer(partial(_operation_authorizer, self._connection))
```

### xǁSQLiteTransactionWriterǁrun__mutmut_12

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
         self._connection.set_authorizer(partial(_operation_authorizer, self._connection))
```

### xǁSQLiteTransactionWriterǁrun__mutmut_13

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
         self._connection.set_authorizer(partial(_operation_authorizer, self._connection))
```

### xǁSQLiteTransactionWriterǁrun__mutmut_14

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
         self._connection.set_authorizer(partial(_operation_authorizer, self._connection))
```

### xǁSQLiteTransactionWriterǁrun__mutmut_17

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

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
         self._connection.set_authorizer(partial(_operation_authorizer, self._connection))
         result = operation(self._connection)
         self._connection.set_authorizer(None)
```

### xǁSQLiteTransactionWriterǁrun__mutmut_26

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_26: survived
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

### xǁSQLiteTransactionWriterǁrun__mutmut_27

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_27: survived
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

### xǁSQLiteTransactionWriterǁrun__mutmut_28

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_28: survived
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

### xǁSQLiteTransactionWriterǁrun__mutmut_29

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_29: survived
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

### xǁSQLiteTransactionWriterǁrun__mutmut_32

SQL keyword/pragma case only. SQLite effects and returned values are identical; test fault injection also normalizes SQL case.

```diff
# custom_components.heima.v3.storage.sqlite_transactions.xǁSQLiteTransactionWriterǁrun__mutmut_32: survived
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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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

Generic exception/group prose only; exception types, cleanup members and commit/publication behavior are unchanged. No message-text contract exists.

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
