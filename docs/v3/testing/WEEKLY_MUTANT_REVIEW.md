# Weekly mutation review — 2026-10-14

Fresh mutmut 3.8 run, recurrence.py only; whole V3 test selection with seed 3145.
Command: `.venv-v3/bin/mutmut run` in an isolated source/test mirror with the
single-module only_mutate entry. Final: 129 generated, 91 killed, 5 timeout,
33 survived; no skipped/error result. Timeouts are reported separately from kills.
Default repository scope adds this module to the preceding seven modules.

Two fresh reruns followed test strengthening, with old mutation caches moved aside.
The final run kills ambient-local-date mutation plan_weekly_job 45 and normal-time
round-trip-zone mutation _civil_due 8. The former needed a Los Angeles civil date
behind UTC; Tokyo alone did not distinguish the mutant. The latter needed host-zone
variation. This exposed real test gaps, now closed.

## Survivor assessment

- plan_weekly_job 2–5, 7–10, 12–15, 17–20, 82–89: 24 generic exception-message
  changes. Exception types and rejection behavior are preserved; prose is not
  part of the domain contract.
- plan_weekly_job 47: range(8) -> range(9). A nonempty weekly set already yields
  its first future occurrence in the initial eight dates; an extra date is never
  reached in a supported successful calculation. Calendar exhaustion still fails.
- _civil_due 2/11: UTC conversion becomes host conversion. astimezone(None)
  returns an aware fixed-offset representation of the same instant. Comparisons,
  arithmetic and final canonical UTC conversion preserve observable output; the
  production code explicitly uses UTC to avoid relying on ambient representation.
- _civil_due 6: omitted fold defaults to 0 on the newly constructed civil datetime.
- _civil_due 29/30/31/35: altered midpoint arithmetic still selects an interior
  point and converges to the same first valid microsecond for real IANA gaps.
  For a day-sized initial interval, /86400 uses a small positive interior point;
  after the first iteration delta.days is zero. The +1 multipliers merely move
  an interior probe. /2 rather than //2 rounds a midpoint but remains strictly
  interior for every delta >=2 µs. These change the search path, not its result.
- _civil_due 38: >= vs > civil gap predicate is equivalent because requested is
  nonexistent; no UTC probe maps to exactly the missing local value.

Five timeouts (_civil_due 20/26/27/28/36) mutate search termination/progress
arithmetic, causing nontermination under the gap tests. No executable logic lies
outside function scope in this new module, so no supplementary decorator/constant
mutation is required for this slice. No 100% mutation-score claim is made.

## Exact non-killed mutation diffs

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_2: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     recurrence service must also track served occurrences during clock/zone changes.
     """
     if not isinstance(entry, CronEntry):
-        raise TypeError("Weekly planning requires CronEntry")
+        raise TypeError(None)
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_3: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     recurrence service must also track served occurrences during clock/zone changes.
     """
     if not isinstance(entry, CronEntry):
-        raise TypeError("Weekly planning requires CronEntry")
+        raise TypeError("XXWeekly planning requires CronEntryXX")
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_4: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     recurrence service must also track served occurrences during clock/zone changes.
     """
     if not isinstance(entry, CronEntry):
-        raise TypeError("Weekly planning requires CronEntry")
+        raise TypeError("weekly planning requires cronentry")
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_5: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     recurrence service must also track served occurrences during clock/zone changes.
     """
     if not isinstance(entry, CronEntry):
-        raise TypeError("Weekly planning requires CronEntry")
+        raise TypeError("WEEKLY PLANNING REQUIRES CRONENTRY")
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_7: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Weekly planning requires CronEntry")
     if not isinstance(entry.pattern, WeeklyRecurrence):
-        raise TypeError("Weekly planning requires WeeklyRecurrence")
+        raise TypeError(None)
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_8: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Weekly planning requires CronEntry")
     if not isinstance(entry.pattern, WeeklyRecurrence):
-        raise TypeError("Weekly planning requires WeeklyRecurrence")
+        raise TypeError("XXWeekly planning requires WeeklyRecurrenceXX")
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_9: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Weekly planning requires CronEntry")
     if not isinstance(entry.pattern, WeeklyRecurrence):
-        raise TypeError("Weekly planning requires WeeklyRecurrence")
+        raise TypeError("weekly planning requires weeklyrecurrence")
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_10: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Weekly planning requires CronEntry")
     if not isinstance(entry.pattern, WeeklyRecurrence):
-        raise TypeError("Weekly planning requires WeeklyRecurrence")
+        raise TypeError("WEEKLY PLANNING REQUIRES WEEKLYRECURRENCE")
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_12: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Weekly planning requires paired execution references")
+        raise TypeError(None)
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly planning requires the configured ZoneInfo")
     # Revalidate staging shapes before applying calendar arithmetic.
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_13: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Weekly planning requires paired execution references")
+        raise TypeError("XXWeekly planning requires paired execution referencesXX")
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly planning requires the configured ZoneInfo")
     # Revalidate staging shapes before applying calendar arithmetic.
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_14: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Weekly planning requires paired execution references")
+        raise TypeError("weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly planning requires the configured ZoneInfo")
     # Revalidate staging shapes before applying calendar arithmetic.
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_15: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(entry.pattern, WeeklyRecurrence):
         raise TypeError("Weekly planning requires WeeklyRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Weekly planning requires paired execution references")
+        raise TypeError("WEEKLY PLANNING REQUIRES PAIRED EXECUTION REFERENCES")
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly planning requires the configured ZoneInfo")
     # Revalidate staging shapes before applying calendar arithmetic.
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_17: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -11,7 +11,7 @@
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly planning requires the configured ZoneInfo")
+        raise TypeError(None)
     # Revalidate staging shapes before applying calendar arithmetic.
     pattern = WeeklyRecurrence(entry.pattern.weekdays, entry.pattern.hour, entry.pattern.minute)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_18: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -11,7 +11,7 @@
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly planning requires the configured ZoneInfo")
+        raise TypeError("XXWeekly planning requires the configured ZoneInfoXX")
     # Revalidate staging shapes before applying calendar arithmetic.
     pattern = WeeklyRecurrence(entry.pattern.weekdays, entry.pattern.hour, entry.pattern.minute)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_19: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -11,7 +11,7 @@
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly planning requires the configured ZoneInfo")
+        raise TypeError("weekly planning requires the configured zoneinfo")
     # Revalidate staging shapes before applying calendar arithmetic.
     pattern = WeeklyRecurrence(entry.pattern.weekdays, entry.pattern.hour, entry.pattern.minute)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_20: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -11,7 +11,7 @@
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Weekly planning requires paired execution references")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly planning requires the configured ZoneInfo")
+        raise TypeError("WEEKLY PLANNING REQUIRES THE CONFIGURED ZONEINFO")
     # Revalidate staging shapes before applying calendar arithmetic.
     pattern = WeeklyRecurrence(entry.pattern.weekdays, entry.pattern.hour, entry.pattern.minute)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_47: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -20,7 +20,7 @@
     try:
         local_day = wall.astimezone(time_zone).date()
         # Today through the same weekday next week, inclusive; not a time horizon.
-        for offset in range(8):
+        for offset in range(9):
             day = local_day + timedelta(days=offset)
             if day.weekday() in pattern.weekdays:
                 requested = datetime(day.year, day.month, day.day, pattern.hour, pattern.minute)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_82: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -34,5 +34,5 @@
                         "wall_clock",
                     )
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError(None) from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_83: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -34,5 +34,5 @@
                         "wall_clock",
                     )
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("XXWeekly due is outside the supported calendarXX") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_84: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -34,5 +34,5 @@
                         "wall_clock",
                     )
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("weekly due is outside the supported calendar") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_85: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -34,5 +34,5 @@
                         "wall_clock",
                     )
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("WEEKLY DUE IS OUTSIDE THE SUPPORTED CALENDAR") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_86: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -35,4 +35,4 @@
                     )
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError(None)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_87: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -35,4 +35,4 @@
                     )
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError("XXNo future weekly due in the supported calendarXX")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_88: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -35,4 +35,4 @@
                     )
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError("no future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_weekly_job__mutmut_89: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -35,4 +35,4 @@
                     )
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError("NO FUTURE WEEKLY DUE IN THE SUPPORTED CALENDAR")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_2: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -1,5 +1,5 @@
 def _civil_due(requested: datetime, time_zone: ZoneInfo) -> datetime:
-    first = requested.replace(tzinfo=time_zone, fold=0).astimezone(UTC)
+    first = requested.replace(tzinfo=time_zone, fold=0).astimezone(None)
     if first.astimezone(time_zone).replace(tzinfo=None) == requested:
         # Also selects fold=0 if the requested local minute occurs twice.
         return first
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_6: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -1,5 +1,5 @@
 def _civil_due(requested: datetime, time_zone: ZoneInfo) -> datetime:
-    first = requested.replace(tzinfo=time_zone, fold=0).astimezone(UTC)
+    first = requested.replace(tzinfo=time_zone, ).astimezone(UTC)
     if first.astimezone(time_zone).replace(tzinfo=None) == requested:
         # Also selects fold=0 if the requested local minute occurs twice.
         return first
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_11: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -3,7 +3,7 @@
     if first.astimezone(time_zone).replace(tzinfo=None) == requested:
         # Also selects fold=0 if the requested local minute occurs twice.
         return first
-    second = requested.replace(tzinfo=time_zone, fold=1).astimezone(UTC)
+    second = requested.replace(tzinfo=time_zone, fold=1).astimezone(None)
     lower, upper = sorted((first, second))
     # The imaginary local time maps to opposite sides of the forward gap under
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_20: timeout
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     lower, upper = sorted((first, second))
     # The imaginary local time maps to opposite sides of the forward gap under
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
-    while upper - lower > timedelta(microseconds=1):
+    while upper - lower >= timedelta(microseconds=1):
         delta = upper - lower
         microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_26: timeout
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
-        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
+        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 - delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_27: timeout
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
-        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
+        microseconds = (delta.days * 86_400 + delta.seconds) / 1_000_000 + delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_28: timeout
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
-        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
+        microseconds = (delta.days * 86_400 - delta.seconds) * 1_000_000 + delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_29: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
-        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
+        microseconds = (delta.days / 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_30: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
-        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
+        microseconds = (delta.days * 86401 + delta.seconds) * 1_000_000 + delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_31: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     # the two folds. Locate its first valid instant, not a same-minute roll-forward.
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
-        microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
+        microseconds = (delta.days * 86_400 + delta.seconds) * 1000001 + delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_35: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -10,7 +10,7 @@
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
         microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
-        middle = lower + timedelta(microseconds=microseconds // 2)
+        middle = lower + timedelta(microseconds=microseconds / 2)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
         else:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_36: timeout
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -10,7 +10,7 @@
     while upper - lower > timedelta(microseconds=1):
         delta = upper - lower
         microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
-        middle = lower + timedelta(microseconds=microseconds // 2)
+        middle = lower + timedelta(microseconds=microseconds // 3)
         if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
             upper = middle
         else:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x__civil_due__mutmut_38: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -11,7 +11,7 @@
         delta = upper - lower
         microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
         middle = lower + timedelta(microseconds=microseconds // 2)
-        if middle.astimezone(time_zone).replace(tzinfo=None) > requested:
+        if middle.astimezone(time_zone).replace(tzinfo=None) >= requested:
             upper = middle
         else:
             lower = middle
```
