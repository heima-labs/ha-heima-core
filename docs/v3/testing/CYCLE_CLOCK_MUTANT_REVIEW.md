# Cycle clock surviving-mutant review

Fresh second mutmut run: 125 generated, 112 killed, 13 survived, runtime/clock.py
with all tests/v3 and seed 3145. The first run had two additional behavioral survivors:
returned wall=None and first-cycle wall_behind_floor=None. New direct assertions now
kill them. All remaining survivor diffs were reviewed below.

## xǁClockDiscontinuityDetectorǁ__init____mutmut_6

Equivalent private startup sentinel: previous_wall is not read while previous_monotonic_ns is None. A successful first comparison replaces both; rejected input replaces neither. No public behavior observes the initial sentinel.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_5

Uncontracted generic error prose; rejection/state preservation unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_6

Uncontracted generic error prose; rejection/state preservation unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_7

Uncontracted generic error prose; rejection/state preservation unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_8

Uncontracted generic error prose; rejection/state preservation unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_11

Uncontracted generic error prose; rejection/state preservation unchanged.

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
     previous_mono = self._previous_monotonic_ns
```

## xǁClockDiscontinuityDetectorǁcompare__mutmut_12

Uncontracted generic error prose; rejection/state preservation unchanged.

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
     previous_mono = self._previous_monotonic_ns
```

## xǁClockDiscontinuityDetectorǁcompare__mutmut_13

Uncontracted generic error prose; rejection/state preservation unchanged.

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
     previous_mono = self._previous_monotonic_ns
```

## xǁClockDiscontinuityDetectorǁcompare__mutmut_14

Uncontracted generic error prose; rejection/state preservation unchanged.

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
     previous_mono = self._previous_monotonic_ns
```

## xǁClockDiscontinuityDetectorǁcompare__mutmut_31

Uncontracted generic error prose; rejection/state preservation unchanged.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_31: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -14,7 +14,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError(None)
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```

## xǁClockDiscontinuityDetectorǁcompare__mutmut_32

Uncontracted generic error prose; rejection/state preservation unchanged.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_32: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -14,7 +14,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError("XXMonotonic clock must not regress within a processXX")
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```

## xǁClockDiscontinuityDetectorǁcompare__mutmut_33

Uncontracted generic error prose; rejection/state preservation unchanged.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_33: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -14,7 +14,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError("monotonic clock must not regress within a process")
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```

## xǁClockDiscontinuityDetectorǁcompare__mutmut_34

Uncontracted generic error prose; rejection/state preservation unchanged.

```diff
# custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_34: survived
--- custom_components/heima/v3/runtime/clock.py
+++ custom_components/heima/v3/runtime/clock.py
@@ -14,7 +14,7 @@
                 direction = "backward"
     else:
         if monotonic_ns < previous_mono:
-            raise ValueError("Monotonic clock must not regress within a process")
+            raise ValueError("MONOTONIC CLOCK MUST NOT REGRESS WITHIN A PROCESS")
         previous_wall = self._previous_wall
         assert previous_wall is not None
         adjustment = _difference_ns(validated, previous_wall) - (monotonic_ns - previous_mono)
```
