# CA4-99 mutation review

Fresh run: runtime/clock.py + runtime/timing.py, all tests/v3, seed 3145.
330 generated, 301 killed, 29 survived. All survivor diffs inspected below.
Generic exception wording is not a stable runtime diagnostic schema. Error type,
rejection and state preservation remain unchanged. One private initial sentinel is
replaced before it can participate in any measured comparison.

## custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_4

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_5

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_6

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁExecutionClockReadingǁ__post_init____mutmut_7

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁ__init____mutmut_6

Equivalent unread initial private wall sentinel: previous_monotonic_ns is None until a successful sample replaces both fields; rejected input replaces neither. No public behavior observes this initial value.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_5

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_6

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_7

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_8

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_11

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_12

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_13

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_14

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_33

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_34

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_35

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.clock.xǁClockDiscontinuityDetectorǁcompare__mutmut_36

Generic exception prose only; error type and state/scheduling behavior retained.

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

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_2

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_2: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: ExecutionClockReading, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError(None)
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_3

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_3: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: ExecutionClockReading, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError("XXRegistration requires AtJobXX")
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_4

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_4: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: ExecutionClockReading, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError("registration requires atjob")
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_5

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_5: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: ExecutionClockReading, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError("REGISTRATION REQUIRES ATJOB")
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_8

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_8: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError(None)
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     reading = _validated_reading(now)
```

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_9

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_9: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError("XXRegistration requires an owner callbackXX")
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     reading = _validated_reading(now)
```

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_10

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_10: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError("registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     reading = _validated_reading(now)
```

## custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_11

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_11: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError("REGISTRATION REQUIRES AN OWNER CALLBACK")
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     reading = _validated_reading(now)
```

## custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_2

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_2: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,4 +1,4 @@
 def _validated_reading(reading: ExecutionClockReading) -> ExecutionClockReading:
     if not isinstance(reading, ExecutionClockReading):
-        raise TypeError("Scheduling requires paired execution references")
+        raise TypeError(None)
     return ExecutionClockReading(reading.wall, reading.cycle_instant)
```

## custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_3

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_3: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,4 +1,4 @@
 def _validated_reading(reading: ExecutionClockReading) -> ExecutionClockReading:
     if not isinstance(reading, ExecutionClockReading):
-        raise TypeError("Scheduling requires paired execution references")
+        raise TypeError("XXScheduling requires paired execution referencesXX")
     return ExecutionClockReading(reading.wall, reading.cycle_instant)
```

## custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_4

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_4: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,4 +1,4 @@
 def _validated_reading(reading: ExecutionClockReading) -> ExecutionClockReading:
     if not isinstance(reading, ExecutionClockReading):
-        raise TypeError("Scheduling requires paired execution references")
+        raise TypeError("scheduling requires paired execution references")
     return ExecutionClockReading(reading.wall, reading.cycle_instant)
```

## custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_5

Generic exception prose only; error type and state/scheduling behavior retained.

```diff
# custom_components.heima.v3.runtime.timing.x__validated_reading__mutmut_5: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,4 +1,4 @@
 def _validated_reading(reading: ExecutionClockReading) -> ExecutionClockReading:
     if not isinstance(reading, ExecutionClockReading):
-        raise TypeError("Scheduling requires paired execution references")
+        raise TypeError("SCHEDULING REQUIRES PAIRED EXECUTION REFERENCES")
     return ExecutionClockReading(reading.wall, reading.cycle_instant)
```
