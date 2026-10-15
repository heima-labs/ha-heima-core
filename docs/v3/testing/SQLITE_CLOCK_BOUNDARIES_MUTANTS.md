# SQLite clock boundaries — mutation review, 2026-10-15

Fresh mutmut 3.8 on native Python3.14.5/SQLite3.53.1, only
storage/sqlite_clock_gaps.py, all tests/v3, seed3145, four children:
**45 generated,33 killed,12 survived, zero error/timeout/skipped/untested/interrupted.**
Every survivor changes generic exception prose only; exact diffs below. No raw
100% mutation-score claim. Source modules outside this scope were not refreshed.
Default repository scope grows from19 to20modules.

Five supplemental mutations killed after a clean39-test baseline: removing frozen,
removing slots, overwriting an existing identity using DO UPDATE, ignoring inclusion
on replay, ignoring time+inclusion on replay. Each ran its named behavioral regression
and exited pytest1; collection errors or no selected tests do not count. Dataclass
flags are outside mutmut's ordinary function scope; SQL string semantics get explicit
supplements. No new application module constants are excluded.

Commands in fresh /private/tmp/heima-v3-clock-boundary-sql, scoped pyproject:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_sqlite_clock_gaps.py
```

Run log /private/tmp/heima-clock-sql-mutmut.log. Temporary files are supplementary;
this report retains all exact survivor diffs and reasons. All generic error message
mutations preserve exception types, rejection boundaries, transaction behavior,
correlation and durable rows. Error prose is neither a serialized field nor a public
message-text contract.

## Individually inspected survivors

### x_prepare_clock_gap_schema__mutmut_2

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.x_prepare_clock_gap_schema__mutmut_2: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -5,7 +5,7 @@
     SQLiteTransactionWriter.run during storage staging, outside evaluation cycles.
     """
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap schema requires an explicit transaction")
+        raise RuntimeError(None)
     connection.execute(
         """CREATE TABLE IF NOT EXISTS clock_gap_boundaries_v1 (
             gap_id TEXT NOT NULL CHECK(gap_id <> ''),
```

### x_prepare_clock_gap_schema__mutmut_3

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.x_prepare_clock_gap_schema__mutmut_3: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -5,7 +5,7 @@
     SQLiteTransactionWriter.run during storage staging, outside evaluation cycles.
     """
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap schema requires an explicit transaction")
+        raise RuntimeError("XXClock gap schema requires an explicit transactionXX")
     connection.execute(
         """CREATE TABLE IF NOT EXISTS clock_gap_boundaries_v1 (
             gap_id TEXT NOT NULL CHECK(gap_id <> ''),
```

### x_prepare_clock_gap_schema__mutmut_4

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.x_prepare_clock_gap_schema__mutmut_4: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -5,7 +5,7 @@
     SQLiteTransactionWriter.run during storage staging, outside evaluation cycles.
     """
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap schema requires an explicit transaction")
+        raise RuntimeError("clock gap schema requires an explicit transaction")
     connection.execute(
         """CREATE TABLE IF NOT EXISTS clock_gap_boundaries_v1 (
             gap_id TEXT NOT NULL CHECK(gap_id <> ''),
```

### x_prepare_clock_gap_schema__mutmut_5

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.x_prepare_clock_gap_schema__mutmut_5: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -5,7 +5,7 @@
     SQLiteTransactionWriter.run during storage staging, outside evaluation cycles.
     """
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap schema requires an explicit transaction")
+        raise RuntimeError("CLOCK GAP SCHEMA REQUIRES AN EXPLICIT TRANSACTION")
     connection.execute(
         """CREATE TABLE IF NOT EXISTS clock_gap_boundaries_v1 (
             gap_id TEXT NOT NULL CHECK(gap_id <> ''),
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_11

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_11: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -4,7 +4,7 @@
         self.gap_id, self.boundary, self.when, self.includes_boundary
     )
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap writes require an explicit transaction")
+        raise RuntimeError(None)
     expected = (
         candidate.gap_id,
         candidate.boundary,
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_12

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_12: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -4,7 +4,7 @@
         self.gap_id, self.boundary, self.when, self.includes_boundary
     )
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap writes require an explicit transaction")
+        raise RuntimeError("XXClock gap writes require an explicit transactionXX")
     expected = (
         candidate.gap_id,
         candidate.boundary,
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_13

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_13: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -4,7 +4,7 @@
         self.gap_id, self.boundary, self.when, self.includes_boundary
     )
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap writes require an explicit transaction")
+        raise RuntimeError("clock gap writes require an explicit transaction")
     expected = (
         candidate.gap_id,
         candidate.boundary,
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_14

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_14: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -4,7 +4,7 @@
         self.gap_id, self.boundary, self.when, self.includes_boundary
     )
     if not connection.in_transaction:
-        raise RuntimeError("Clock gap writes require an explicit transaction")
+        raise RuntimeError("CLOCK GAP WRITES REQUIRE AN EXPLICIT TRANSACTION")
     expected = (
         candidate.gap_id,
         candidate.boundary,
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_28

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_28: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -27,5 +27,5 @@
     finally:
         cursor.close()
     if stored != expected:
-        raise ValueError("Clock gap identity already has different boundary data")
+        raise ValueError(None)
     return candidate
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_29

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_29: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -27,5 +27,5 @@
     finally:
         cursor.close()
     if stored != expected:
-        raise ValueError("Clock gap identity already has different boundary data")
+        raise ValueError("XXClock gap identity already has different boundary dataXX")
     return candidate
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_30

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_30: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -27,5 +27,5 @@
     finally:
         cursor.close()
     if stored != expected:
-        raise ValueError("Clock gap identity already has different boundary data")
+        raise ValueError("clock gap identity already has different boundary data")
     return candidate
```

### xǁClockGapBoundaryWriteǁ__call____mutmut_31

Generic error prose only, equivalent for the reasons above.

```diff
# custom_components.heima.v3.storage.sqlite_clock_gaps.xǁClockGapBoundaryWriteǁ__call____mutmut_31: survived
--- custom_components/heima/v3/storage/sqlite_clock_gaps.py
+++ custom_components/heima/v3/storage/sqlite_clock_gaps.py
@@ -27,5 +27,5 @@
     finally:
         cursor.close()
     if stored != expected:
-        raise ValueError("Clock gap identity already has different boundary data")
+        raise ValueError("CLOCK GAP IDENTITY ALREADY HAS DIFFERENT BOUNDARY DATA")
     return candidate
```
