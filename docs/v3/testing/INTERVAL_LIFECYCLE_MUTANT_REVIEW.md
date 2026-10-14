# Interval lifecycle mutation review — 2026-10-14

Fresh mutmut 3.8 run with only interval_recurrences.py, whole V3 suite, seed3145.
119 generated: 107 killed, 12 survived, no timeout/skipped/error. Default repository
scope includes the new module alongside the nine preceding modules.

Survivors are register 2–5/7–10/13–16: generic validation exception prose changes.
Rejection types and side effects are unchanged; that wording is not a domain contract.
Diagnostic strings for actual owner/infrastructure faults are tested as transported
inputs, distinct from prescribing generic constructor error wording.

Initial _rearm mutants 7/19/24 dropped overflow entry or error message. Strengthened
those diagnostic assertions, moved aside cache and ran fresh. Final run kills all
three. No executable behavioral survivor remains. No optional score threshold.
Supplement mutation_interval_recurrences.py has a passing baseline and kills all
three public diagnostic immutability removals. Private _Registration's immutable
flag is a construction convention without externally observable mutation paths.

## Exact surviving mutation diffs

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
