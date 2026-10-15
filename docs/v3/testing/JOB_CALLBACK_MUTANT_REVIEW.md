# Shared callback mutation review — 2026-10-14

Fresh mutmut 3.8 on interval_recurrences.py and job_callbacks.py, whole V3 suite,
seed3145. 144 generated, 124 killed, 20 survived, no timeout/skipped/error.
Survivors: interval register 2–5/7–10/13–16 (12 already reviewed generic admission
exception prose) and isolate_job_callback 3–6/9–12 (8 generic validation prose).
They preserve rejection types and side effects; this wording is not a contract.
No behavioral survivor remains. No numerical mutation score gate introduced.

Supplement mutation_interval_recurrences.py now targets job_callbacks.py for
JobCallbackFault and interval_recurrences.py for the two interval diagnostics,
restoring both originals before each mutation. Clean baseline passes; all three
immutability removals are killed by their corresponding lifecycle tests.

## Exact surviving diffs

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_2: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -1,6 +1,6 @@
 def register(self, entry: CronEntry, callback: JobCallback) -> Unrepresentable | None:
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval lifecycle requires CronEntry")
+        raise TypeError(None)
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_3: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -1,6 +1,6 @@
 def register(self, entry: CronEntry, callback: JobCallback) -> Unrepresentable | None:
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval lifecycle requires CronEntry")
+        raise TypeError("XXInterval lifecycle requires CronEntryXX")
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_4: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -1,6 +1,6 @@
 def register(self, entry: CronEntry, callback: JobCallback) -> Unrepresentable | None:
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval lifecycle requires CronEntry")
+        raise TypeError("interval lifecycle requires cronentry")
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_5: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -1,6 +1,6 @@
 def register(self, entry: CronEntry, callback: JobCallback) -> Unrepresentable | None:
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval lifecycle requires CronEntry")
+        raise TypeError("INTERVAL LIFECYCLE REQUIRES CRONENTRY")
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_7: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -2,7 +2,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval lifecycle requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval lifecycle requires IntervalRecurrence")
+        raise TypeError(None)
     if not callable(callback):
         raise TypeError("Interval lifecycle requires an owner callback")
     validated = CronEntry(
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_8: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -2,7 +2,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval lifecycle requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval lifecycle requires IntervalRecurrence")
+        raise TypeError("XXInterval lifecycle requires IntervalRecurrenceXX")
     if not callable(callback):
         raise TypeError("Interval lifecycle requires an owner callback")
     validated = CronEntry(
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_9: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -2,7 +2,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval lifecycle requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval lifecycle requires IntervalRecurrence")
+        raise TypeError("interval lifecycle requires intervalrecurrence")
     if not callable(callback):
         raise TypeError("Interval lifecycle requires an owner callback")
     validated = CronEntry(
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_10: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -2,7 +2,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval lifecycle requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval lifecycle requires IntervalRecurrence")
+        raise TypeError("INTERVAL LIFECYCLE REQUIRES INTERVALRECURRENCE")
     if not callable(callback):
         raise TypeError("Interval lifecycle requires an owner callback")
     validated = CronEntry(
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_13: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -4,7 +4,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
-        raise TypeError("Interval lifecycle requires an owner callback")
+        raise TypeError(None)
     validated = CronEntry(
         entry.job_id, entry.owner, IntervalRecurrence(entry.pattern.interval), entry.label
     )
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_14: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -4,7 +4,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
-        raise TypeError("Interval lifecycle requires an owner callback")
+        raise TypeError("XXInterval lifecycle requires an owner callbackXX")
     validated = CronEntry(
         entry.job_id, entry.owner, IntervalRecurrence(entry.pattern.interval), entry.label
     )
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_15: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -4,7 +4,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
-        raise TypeError("Interval lifecycle requires an owner callback")
+        raise TypeError("interval lifecycle requires an owner callback")
     validated = CronEntry(
         entry.job_id, entry.owner, IntervalRecurrence(entry.pattern.interval), entry.label
     )
```

```diff
# custom_components.heima.v3.runtime.interval_recurrences.xǁIntervalRecurrencesǁregister__mutmut_16: survived
--- custom_components/heima/v3/runtime/interval_recurrences.py
+++ custom_components/heima/v3/runtime/interval_recurrences.py
@@ -4,7 +4,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval lifecycle requires IntervalRecurrence")
     if not callable(callback):
-        raise TypeError("Interval lifecycle requires an owner callback")
+        raise TypeError("INTERVAL LIFECYCLE REQUIRES AN OWNER CALLBACK")
     validated = CronEntry(
         entry.job_id, entry.owner, IntervalRecurrence(entry.pattern.interval), entry.label
     )
```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_3: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -3,7 +3,7 @@
 ) -> JobCallback:
     """Wrap an owner for the shared dispatcher; report must log/publish without raising."""
     if not callable(callback):
-        raise TypeError("Fault isolation requires an owner callback")
+        raise TypeError(None)
     if not callable(report):
         raise TypeError("Fault isolation requires a diagnostic sink")

```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_4: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -3,7 +3,7 @@
 ) -> JobCallback:
     """Wrap an owner for the shared dispatcher; report must log/publish without raising."""
     if not callable(callback):
-        raise TypeError("Fault isolation requires an owner callback")
+        raise TypeError("XXFault isolation requires an owner callbackXX")
     if not callable(report):
         raise TypeError("Fault isolation requires a diagnostic sink")

```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_5: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -3,7 +3,7 @@
 ) -> JobCallback:
     """Wrap an owner for the shared dispatcher; report must log/publish without raising."""
     if not callable(callback):
-        raise TypeError("Fault isolation requires an owner callback")
+        raise TypeError("fault isolation requires an owner callback")
     if not callable(report):
         raise TypeError("Fault isolation requires a diagnostic sink")

```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_6: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -3,7 +3,7 @@
 ) -> JobCallback:
     """Wrap an owner for the shared dispatcher; report must log/publish without raising."""
     if not callable(callback):
-        raise TypeError("Fault isolation requires an owner callback")
+        raise TypeError("FAULT ISOLATION REQUIRES AN OWNER CALLBACK")
     if not callable(report):
         raise TypeError("Fault isolation requires a diagnostic sink")

```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_9: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -5,7 +5,7 @@
     if not callable(callback):
         raise TypeError("Fault isolation requires an owner callback")
     if not callable(report):
-        raise TypeError("Fault isolation requires a diagnostic sink")
+        raise TypeError(None)

     def isolated(job: AtJob) -> None:
         fault = invoke_job_callback(job, callback)
```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_10: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -5,7 +5,7 @@
     if not callable(callback):
         raise TypeError("Fault isolation requires an owner callback")
     if not callable(report):
-        raise TypeError("Fault isolation requires a diagnostic sink")
+        raise TypeError("XXFault isolation requires a diagnostic sinkXX")

     def isolated(job: AtJob) -> None:
         fault = invoke_job_callback(job, callback)
```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_11: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -5,7 +5,7 @@
     if not callable(callback):
         raise TypeError("Fault isolation requires an owner callback")
     if not callable(report):
-        raise TypeError("Fault isolation requires a diagnostic sink")
+        raise TypeError("fault isolation requires a diagnostic sink")

     def isolated(job: AtJob) -> None:
         fault = invoke_job_callback(job, callback)
```

```diff
# custom_components.heima.v3.runtime.job_callbacks.x_isolate_job_callback__mutmut_12: survived
--- custom_components/heima/v3/runtime/job_callbacks.py
+++ custom_components/heima/v3/runtime/job_callbacks.py
@@ -5,7 +5,7 @@
     if not callable(callback):
         raise TypeError("Fault isolation requires an owner callback")
     if not callable(report):
-        raise TypeError("Fault isolation requires a diagnostic sink")
+        raise TypeError("FAULT ISOLATION REQUIRES A DIAGNOSTIC SINK")

     def isolated(job: AtJob) -> None:
         fault = invoke_job_callback(job, callback)
```
