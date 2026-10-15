# CA4-102 clock mutation review — 2026-10-15

Fresh mutmut 3.8 run scoped to custom_components/heima/v3/runtime/clock.py, all
 tests/v3, Hypothesis seed 3145. Native Python 3.14.5, four children. **216 generated,
199 killed, 17 survived; zero timeout, error, skipped or untested.** No raw 100% score
is claimed. Each surviving diff is reviewed below: sixteen alter generic exception
prose (not a specified message contract); one changes an unread initial sentinel.
There are no surviving behavioral changes to either gap-mode selection or finish.

The initial fresh run was 216/198/18. The extra survivor changed finish's strict
start exclusion from <= to <: an open first-cycle-mode gap could end on its own start
cycle. Added test_ca4102_first_cycle_end_excludes_the_start_cycle_itself; baseline
passes, mutant fails. Reran in a fresh directory; this mutant is now killed. No test
expects the old frozen-tick promotion. Tests for the new rule first failed on prior
source (5 regression/property failures), then passed after the bounded two-site fix.

## Reproduce and tool limits

In a new temporary copy of the current custom_components, tests, pytest-v3.ini and
pyproject.toml, narrow **only_mutate** to runtime/clock.py (leave the repository's
15-module default unchanged). Preserve test selection tests/v3 and seed 3145. Run:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full mutant id>'
.venv-v3/bin/python tests/v3/mutation_clock.py
```

Use an empty mutants directory for each full run: test changes alone must not reuse
cached outcomes. CA4-102 run paths: /private/tmp/heima-v3-ca4102, logs
/private/tmp/ca4102-mutmut-final.log. The repository's pyproject.toml is not narrowed.
These temporary paths are execution evidence, not required permanent artifacts.

mutmut mutates function bodies, not frozen decorators or module constants, and
excludes some property bodies. Existing tests/v3/mutation_clock.py supplements the
threshold constant and four frozen result dataclasses. It ran with a clean baseline:
execution_reading_mutable, gap_mutable, threshold_plus_nanosecond, comparison_mutable,
cycle_tick_mutable all killed by their expected behavioral tests (pytest exit 1).
Unchanged comparison properties remain covered by existing functional tests; the
changed compare and finish bodies are in the tool's scope. No hardware, persistence
or complete-runtime claim follows from this mutation result.

## Individually inspected survivors

### xǁExecutionClockReadingǁ__post_init____mutmut_4

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -2,4 +2,4 @@
     parse_instant(self.wall)
     parse_instant(self.cycle_instant)
     if self.cycle_instant < self.wall:
-        raise ValueError("Cycle-instant reference must not precede wall time")
+        raise ValueError(None)
```

### xǁExecutionClockReadingǁ__post_init____mutmut_5

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -2,4 +2,4 @@
     parse_instant(self.wall)
     parse_instant(self.cycle_instant)
     if self.cycle_instant < self.wall:
-        raise ValueError("Cycle-instant reference must not precede wall time")
+        raise ValueError("XXCycle-instant reference must not precede wall timeXX")
```

### xǁExecutionClockReadingǁ__post_init____mutmut_6

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -2,4 +2,4 @@
     parse_instant(self.wall)
     parse_instant(self.cycle_instant)
     if self.cycle_instant < self.wall:
-        raise ValueError("Cycle-instant reference must not precede wall time")
+        raise ValueError("cycle-instant reference must not precede wall time")
```

### xǁExecutionClockReadingǁ__post_init____mutmut_7

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -2,4 +2,4 @@
     parse_instant(self.wall)
     parse_instant(self.cycle_instant)
     if self.cycle_instant < self.wall:
-        raise ValueError("Cycle-instant reference must not precede wall time")
+        raise ValueError("CYCLE-INSTANT REFERENCE MUST NOT PRECEDE WALL TIME")
```

### xǁClockDiscontinuityDetectorǁ__init____mutmut_6

Equivalent private bootstrap sentinel: no successful comparison reads it before replacing it; validation failures leave the uninitialized branch active. Public state/results are unchanged.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁ__init____mutmut_6: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -1,4 +1,4 @@
 def __init__(self, durable_floor: EvidenceInstant | None = None) -> None:
     self._durable_floor = None if durable_floor is None else validate_instant(durable_floor)
-    self._previous_wall: EvidenceInstant | None = None
+    self._previous_wall: EvidenceInstant | None = ""
     self._previous_monotonic_ns: int | None = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_5

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_5: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -1,7 +1,7 @@
 def compare(self, wall: EvidenceInstant, monotonic_ns: int) -> ClockComparison:
     validated = validate_instant(wall)
     if type(monotonic_ns) is not int:
-        raise TypeError("Monotonic reading must be a non-boolean integer")
+        raise TypeError(None)
     if monotonic_ns < 0:
         raise ValueError("Monotonic reading must be nonnegative")
     direction: Literal["forward", "backward"] | None = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_6

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_6: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -1,7 +1,7 @@
 def compare(self, wall: EvidenceInstant, monotonic_ns: int) -> ClockComparison:
     validated = validate_instant(wall)
     if type(monotonic_ns) is not int:
-        raise TypeError("Monotonic reading must be a non-boolean integer")
+        raise TypeError("XXMonotonic reading must be a non-boolean integerXX")
     if monotonic_ns < 0:
         raise ValueError("Monotonic reading must be nonnegative")
     direction: Literal["forward", "backward"] | None = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_7

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_7: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -1,7 +1,7 @@
 def compare(self, wall: EvidenceInstant, monotonic_ns: int) -> ClockComparison:
     validated = validate_instant(wall)
     if type(monotonic_ns) is not int:
-        raise TypeError("Monotonic reading must be a non-boolean integer")
+        raise TypeError("monotonic reading must be a non-boolean integer")
     if monotonic_ns < 0:
         raise ValueError("Monotonic reading must be nonnegative")
     direction: Literal["forward", "backward"] | None = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_8

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_8: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -1,7 +1,7 @@
 def compare(self, wall: EvidenceInstant, monotonic_ns: int) -> ClockComparison:
     validated = validate_instant(wall)
     if type(monotonic_ns) is not int:
-        raise TypeError("Monotonic reading must be a non-boolean integer")
+        raise TypeError("MONOTONIC READING MUST BE A NON-BOOLEAN INTEGER")
     if monotonic_ns < 0:
         raise ValueError("Monotonic reading must be nonnegative")
     direction: Literal["forward", "backward"] | None = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_11

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_11: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -3,7 +3,7 @@
     if type(monotonic_ns) is not int:
         raise TypeError("Monotonic reading must be a non-boolean integer")
     if monotonic_ns < 0:
-        raise ValueError("Monotonic reading must be nonnegative")
+        raise ValueError(None)
     direction: Literal["forward", "backward"] | None = None
     adjustment = None
     bootstrap_offset = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_12

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_12: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -3,7 +3,7 @@
     if type(monotonic_ns) is not int:
         raise TypeError("Monotonic reading must be a non-boolean integer")
     if monotonic_ns < 0:
-        raise ValueError("Monotonic reading must be nonnegative")
+        raise ValueError("XXMonotonic reading must be nonnegativeXX")
     direction: Literal["forward", "backward"] | None = None
     adjustment = None
     bootstrap_offset = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_13

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_13: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -3,7 +3,7 @@
     if type(monotonic_ns) is not int:
         raise TypeError("Monotonic reading must be a non-boolean integer")
     if monotonic_ns < 0:
-        raise ValueError("Monotonic reading must be nonnegative")
+        raise ValueError("monotonic reading must be nonnegative")
     direction: Literal["forward", "backward"] | None = None
     adjustment = None
     bootstrap_offset = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_14

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_14: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -3,7 +3,7 @@
     if type(monotonic_ns) is not int:
         raise TypeError("Monotonic reading must be a non-boolean integer")
     if monotonic_ns < 0:
-        raise ValueError("Monotonic reading must be nonnegative")
+        raise ValueError("MONOTONIC READING MUST BE NONNEGATIVE")
     direction: Literal["forward", "backward"] | None = None
     adjustment = None
     bootstrap_offset = None
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_33

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_33: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -16,7 +16,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError(None)
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_34

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_34: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -16,7 +16,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError("XXMonotonic clock must not regress within a processXX")
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_35

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_35: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -16,7 +16,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError("monotonic clock must not regress within a process")
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```

### xǁClockDiscontinuityDetectorǁcompare__mutmut_36

Generic exception prose only. The exception class, rejection boundary and state preservation remain identical; this message text is not an approved public contract.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_36: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -16,7 +16,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError("MONOTONIC CLOCK MUST NOT REGRESS WITHIN A PROCESS")
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```
