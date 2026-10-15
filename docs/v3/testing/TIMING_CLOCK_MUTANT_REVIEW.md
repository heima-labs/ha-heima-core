# Timing clock bridge mutation review — 2026-10-15

Fresh mutmut 3.8: runtime/timing.py, runtime/timing_clock.py,
adapters/ha/clock_source.py, whole V3 suite, seed3145.
168 generated, 156 killed, 12 survived, no timeout/error/skipped.
Survivors are existing scheduler register 2–5/8–11 and _validated_reading 2–5:
generic validation exception prose, preserving rejection types and side effects.
No behavioral survivor. No optional score threshold introduced.

Supplement mutation_timing_clock.py: clean baseline; frozen removals for ClockSample,
ClockRearmFault and WallClockRearmFailure all killed by their observable result tests.
Initial mutation baseline exposed a test incorrectly requiring object identity for
an intentionally reconstructed accepted AtJob; corrected it to contract equality
before the fresh successful mutation run. This was a test-oracle issue, not a code
change. No initial failed baseline is counted as killed mutants.

## Exact surviving diffs

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
