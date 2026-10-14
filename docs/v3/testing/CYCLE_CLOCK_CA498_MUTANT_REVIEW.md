# CA4-98 clock mutation review

Fresh final scope: runtime/clock.py, all tests/v3, Hypothesis seed 3145.
198 generated, 185 killed, 13 survived. All survivors inspected below. The first
CA4-98 run exposed three behavioral survivors in periodic floor metadata; boundary/
empty-bootstrap assertions now kill them. No raw 100% mutation score is claimed.

## xǁClockDiscontinuityDetectorǁ__init____mutmut_6

Equivalent private initial sentinel: unused before the first successful comparison, which replaces it. Rejected readings leave the comparison uninitialized; no supported public behavior observes this initial value.

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

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_12

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_13

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_14

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_33

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_34

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_35

Generic exception prose only; exception type and state-preserving rejection unchanged.

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

## xǁClockDiscontinuityDetectorǁcompare__mutmut_36

Generic exception prose only; exception type and state-preserving rejection unchanged.

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
