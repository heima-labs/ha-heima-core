# CA4-100 mutation review — 2026-10-14

Fresh mutmut 3.8, deadlines.py and recurrence.py; whole V3 selection, seed3145.
239 generated: 180 killed, 5 timeout, 54 survived, no skipped/error. Unchanged
weekly functions retain the assessment of 33 survivors and 5 timeouts in
WEEKLY_MUTANT_REVIEW.md. Timeouts are separate from assertion kills.

New code's 21 survivors: derive_instant 5–8/11–14 (8 generic exception prose),
22 (ASCII encoding alias, identical bytes); plan_interval_job 2–5/7–10/12–15
(12 generic exception prose). Rejection types and behavior are unchanged;
error prose is not part of these domain contracts. No behavioral survivor remains.

Initial remaining-headroom mutants 40/42/43 survived; meaningful remaining
seconds/day boundaries and overflow by 1 µs kill all three in the fresh run.
Supplementary frozen Unrepresentable decorator mutation is killed with a passing
clean baseline: `.venv-v3/bin/python tests/v3/mutation_deadlines.py`.
No optional mutation score threshold is assumed.

## Exact non-killed mutation diffs

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_5: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -8,7 +8,7 @@
     """
     start = parse_instant(anchor)
     if not isinstance(duration, Window):
-        raise TypeError("Deadline construction requires Window")
+        raise TypeError(None)
     if type(strictly_after) is not bool:
         raise TypeError("Strict deadline selection must be boolean")
     validated = Window(duration.seconds)
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_6: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -8,7 +8,7 @@
     """
     start = parse_instant(anchor)
     if not isinstance(duration, Window):
-        raise TypeError("Deadline construction requires Window")
+        raise TypeError("XXDeadline construction requires WindowXX")
     if type(strictly_after) is not bool:
         raise TypeError("Strict deadline selection must be boolean")
     validated = Window(duration.seconds)
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_7: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -8,7 +8,7 @@
     """
     start = parse_instant(anchor)
     if not isinstance(duration, Window):
-        raise TypeError("Deadline construction requires Window")
+        raise TypeError("deadline construction requires window")
     if type(strictly_after) is not bool:
         raise TypeError("Strict deadline selection must be boolean")
     validated = Window(duration.seconds)
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_8: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -8,7 +8,7 @@
     """
     start = parse_instant(anchor)
     if not isinstance(duration, Window):
-        raise TypeError("Deadline construction requires Window")
+        raise TypeError("DEADLINE CONSTRUCTION REQUIRES WINDOW")
     if type(strictly_after) is not bool:
         raise TypeError("Strict deadline selection must be boolean")
     validated = Window(duration.seconds)
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_11: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -10,7 +10,7 @@
     if not isinstance(duration, Window):
         raise TypeError("Deadline construction requires Window")
     if type(strictly_after) is not bool:
-        raise TypeError("Strict deadline selection must be boolean")
+        raise TypeError(None)
     validated = Window(duration.seconds)
     numerator, denominator = Decimal(
         canonical_json_bytes(validated.seconds).decode("ascii")
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_12: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -10,7 +10,7 @@
     if not isinstance(duration, Window):
         raise TypeError("Deadline construction requires Window")
     if type(strictly_after) is not bool:
-        raise TypeError("Strict deadline selection must be boolean")
+        raise TypeError("XXStrict deadline selection must be booleanXX")
     validated = Window(duration.seconds)
     numerator, denominator = Decimal(
         canonical_json_bytes(validated.seconds).decode("ascii")
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_13: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -10,7 +10,7 @@
     if not isinstance(duration, Window):
         raise TypeError("Deadline construction requires Window")
     if type(strictly_after) is not bool:
-        raise TypeError("Strict deadline selection must be boolean")
+        raise TypeError("strict deadline selection must be boolean")
     validated = Window(duration.seconds)
     numerator, denominator = Decimal(
         canonical_json_bytes(validated.seconds).decode("ascii")
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_14: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -10,7 +10,7 @@
     if not isinstance(duration, Window):
         raise TypeError("Deadline construction requires Window")
     if type(strictly_after) is not bool:
-        raise TypeError("Strict deadline selection must be boolean")
+        raise TypeError("STRICT DEADLINE SELECTION MUST BE BOOLEAN")
     validated = Window(duration.seconds)
     numerator, denominator = Decimal(
         canonical_json_bytes(validated.seconds).decode("ascii")
```

```diff
# custom_components.heima.v3.contracts.deadlines.x_derive_instant__mutmut_22: survived
--- custom_components/heima/v3/contracts/deadlines.py
+++ custom_components/heima/v3/contracts/deadlines.py
@@ -13,7 +13,7 @@
         raise TypeError("Strict deadline selection must be boolean")
     validated = Window(duration.seconds)
     numerator, denominator = Decimal(
-        canonical_json_bytes(validated.seconds).decode("ascii")
+        canonical_json_bytes(validated.seconds).decode("ASCII")
     ).as_integer_ratio()
     whole, remainder = divmod(numerator * 1_000_000, denominator)
     if strictly_after or remainder:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_2: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -1,7 +1,7 @@
 def plan_interval_job(entry: CronEntry, now: ExecutionClockReading) -> AtJob | Unrepresentable:
     """Plan one elapsed arm against the captured cycle-instant clock."""
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval planning requires CronEntry")
+        raise TypeError(None)
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_3: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -1,7 +1,7 @@
 def plan_interval_job(entry: CronEntry, now: ExecutionClockReading) -> AtJob | Unrepresentable:
     """Plan one elapsed arm against the captured cycle-instant clock."""
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval planning requires CronEntry")
+        raise TypeError("XXInterval planning requires CronEntryXX")
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_4: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -1,7 +1,7 @@
 def plan_interval_job(entry: CronEntry, now: ExecutionClockReading) -> AtJob | Unrepresentable:
     """Plan one elapsed arm against the captured cycle-instant clock."""
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval planning requires CronEntry")
+        raise TypeError("interval planning requires cronentry")
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_5: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -1,7 +1,7 @@
 def plan_interval_job(entry: CronEntry, now: ExecutionClockReading) -> AtJob | Unrepresentable:
     """Plan one elapsed arm against the captured cycle-instant clock."""
     if not isinstance(entry, CronEntry):
-        raise TypeError("Interval planning requires CronEntry")
+        raise TypeError("INTERVAL PLANNING REQUIRES CRONENTRY")
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_7: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -3,7 +3,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval planning requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval planning requires IntervalRecurrence")
+        raise TypeError(None)
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Interval planning requires paired execution references")
     pattern = IntervalRecurrence(entry.pattern.interval)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_8: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -3,7 +3,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval planning requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval planning requires IntervalRecurrence")
+        raise TypeError("XXInterval planning requires IntervalRecurrenceXX")
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Interval planning requires paired execution references")
     pattern = IntervalRecurrence(entry.pattern.interval)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_9: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -3,7 +3,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval planning requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval planning requires IntervalRecurrence")
+        raise TypeError("interval planning requires intervalrecurrence")
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Interval planning requires paired execution references")
     pattern = IntervalRecurrence(entry.pattern.interval)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_10: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -3,7 +3,7 @@
     if not isinstance(entry, CronEntry):
         raise TypeError("Interval planning requires CronEntry")
     if not isinstance(entry.pattern, IntervalRecurrence):
-        raise TypeError("Interval planning requires IntervalRecurrence")
+        raise TypeError("INTERVAL PLANNING REQUIRES INTERVALRECURRENCE")
     if not isinstance(now, ExecutionClockReading):
         raise TypeError("Interval planning requires paired execution references")
     pattern = IntervalRecurrence(entry.pattern.interval)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_12: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Interval planning requires paired execution references")
+        raise TypeError(None)
     pattern = IntervalRecurrence(entry.pattern.interval)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
     reading = ExecutionClockReading(now.wall, now.cycle_instant)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_13: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Interval planning requires paired execution references")
+        raise TypeError("XXInterval planning requires paired execution referencesXX")
     pattern = IntervalRecurrence(entry.pattern.interval)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
     reading = ExecutionClockReading(now.wall, now.cycle_instant)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_14: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Interval planning requires paired execution references")
+        raise TypeError("interval planning requires paired execution references")
     pattern = IntervalRecurrence(entry.pattern.interval)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
     reading = ExecutionClockReading(now.wall, now.cycle_instant)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_plan_interval_job__mutmut_15: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -5,7 +5,7 @@
     if not isinstance(entry.pattern, IntervalRecurrence):
         raise TypeError("Interval planning requires IntervalRecurrence")
     if not isinstance(now, ExecutionClockReading):
-        raise TypeError("Interval planning requires paired execution references")
+        raise TypeError("INTERVAL PLANNING REQUIRES PAIRED EXECUTION REFERENCES")
     pattern = IntervalRecurrence(entry.pattern.interval)
     validated = CronEntry(entry.job_id, entry.owner, pattern, entry.label)
     reading = ExecutionClockReading(now.wall, now.cycle_instant)
```

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
