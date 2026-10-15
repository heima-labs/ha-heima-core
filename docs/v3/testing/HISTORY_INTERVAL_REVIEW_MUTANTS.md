# Historical interval and critical review mutations — 2026-10-15

Fresh mutmut 3.8, history_intervals.py + timing.py + recurrence.py; whole V3 suite,
seed3145: 364 generated, 291 killed, 5 timeout, 68 survived, no skipped/error.

Survivor assessment:
- 56 generic error-prose variants: history interval 16, interval planner 12, weekly
  calculator 16, scheduler validation 12. Rejection types/side effects preserved.
- Weekly range(9) instead of range(8): extra date never reached for first valid due.
- Weekly past-candidate <= vs <: equality remains rejected by the UTC future gate.
- Weekly physical > vs >=: equality cannot reach that point after the civil <=
  prefilter (normal/fold equality has equal local fields; gap endpoint is later than
  the impossible request). No equality replay is admitted by that isolated mutant.
- Countdown <= vs <: delta zero still computes float zero exactly, identical output.
- Eight _civil_due search/representation equivalents retain WEEKLY_MUTANT_REVIEW.md
  reasoning: aware host representation/implicit fold0, valid interior probes, equality
  unreachable in a missing local time. Five nontermination mutations are timeouts,
  separate from assertion kills. No known behavioral survivor remains.

Mutmut leaves @property empty unmutated. Supplement mutation_history_intervals.py
kills its threshold, exclusion-sum, ignored-start and ignored-end mutations plus
frozen-result removal. Clean baseline. An initial expected-name mismatch was rejected;
final harness identifies the first actual touching-boundary failure and exits 1.
Weekly occurrence supplement: 2 killed with baseline pass. No score threshold added.

## Exact non-killed mutation diffs

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -2,7 +2,7 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end < start:
-        raise ValueError("History interval end precedes start")
+        raise ValueError(None)
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -2,7 +2,7 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end < start:
-        raise ValueError("History interval end precedes start")
+        raise ValueError("XXHistory interval end precedes startXX")
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -2,7 +2,7 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end < start:
-        raise ValueError("History interval end precedes start")
+        raise ValueError("history interval end precedes start")
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -2,7 +2,7 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end < start:
-        raise ValueError("History interval end precedes start")
+        raise ValueError("HISTORY INTERVAL END PRECEDES START")
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -4,6 +4,6 @@
     if end < start:
         raise ValueError("History interval end precedes start")
     if type(self.include_start) is not bool:
-        raise TypeError("Start inclusion must be boolean")
+        raise TypeError(None)
     if type(self.include_end) is not bool:
         raise TypeError("End inclusion must be boolean")
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_13: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -4,6 +4,6 @@
     if end < start:
         raise ValueError("History interval end precedes start")
     if type(self.include_start) is not bool:
-        raise TypeError("Start inclusion must be boolean")
+        raise TypeError("XXStart inclusion must be booleanXX")
     if type(self.include_end) is not bool:
         raise TypeError("End inclusion must be boolean")
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_14: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -4,6 +4,6 @@
     if end < start:
         raise ValueError("History interval end precedes start")
     if type(self.include_start) is not bool:
-        raise TypeError("Start inclusion must be boolean")
+        raise TypeError("start inclusion must be boolean")
     if type(self.include_end) is not bool:
         raise TypeError("End inclusion must be boolean")
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_15: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -4,6 +4,6 @@
     if end < start:
         raise ValueError("History interval end precedes start")
     if type(self.include_start) is not bool:
-        raise TypeError("Start inclusion must be boolean")
+        raise TypeError("START INCLUSION MUST BE BOOLEAN")
     if type(self.include_end) is not bool:
         raise TypeError("End inclusion must be boolean")
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_18: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -6,4 +6,4 @@
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
-        raise TypeError("End inclusion must be boolean")
+        raise TypeError(None)
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_19: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -6,4 +6,4 @@
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
-        raise TypeError("End inclusion must be boolean")
+        raise TypeError("XXEnd inclusion must be booleanXX")
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_20: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -6,4 +6,4 @@
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
-        raise TypeError("End inclusion must be boolean")
+        raise TypeError("end inclusion must be boolean")
```

```diff
# custom_components.heima.v3.contracts.history_intervals.xǁHistoryIntervalǁ__post_init____mutmut_21: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -6,4 +6,4 @@
     if type(self.include_start) is not bool:
         raise TypeError("Start inclusion must be boolean")
     if type(self.include_end) is not bool:
-        raise TypeError("End inclusion must be boolean")
+        raise TypeError("END INCLUSION MUST BE BOOLEAN")
```

```diff
# custom_components.heima.v3.contracts.history_intervals.x__validated_interval__mutmut_2: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -1,4 +1,4 @@
 def _validated_interval(value: HistoryInterval) -> HistoryInterval:
     if not isinstance(value, HistoryInterval):
-        raise TypeError("Historical intersection requires HistoryInterval")
+        raise TypeError(None)
     return HistoryInterval(value.start, value.end, value.include_start, value.include_end)
```

```diff
# custom_components.heima.v3.contracts.history_intervals.x__validated_interval__mutmut_3: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -1,4 +1,4 @@
 def _validated_interval(value: HistoryInterval) -> HistoryInterval:
     if not isinstance(value, HistoryInterval):
-        raise TypeError("Historical intersection requires HistoryInterval")
+        raise TypeError("XXHistorical intersection requires HistoryIntervalXX")
     return HistoryInterval(value.start, value.end, value.include_start, value.include_end)
```

```diff
# custom_components.heima.v3.contracts.history_intervals.x__validated_interval__mutmut_4: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -1,4 +1,4 @@
 def _validated_interval(value: HistoryInterval) -> HistoryInterval:
     if not isinstance(value, HistoryInterval):
-        raise TypeError("Historical intersection requires HistoryInterval")
+        raise TypeError("historical intersection requires historyinterval")
     return HistoryInterval(value.start, value.end, value.include_start, value.include_end)
```

```diff
# custom_components.heima.v3.contracts.history_intervals.x__validated_interval__mutmut_5: survived
--- custom_components/heima/v3/contracts/history_intervals.py
+++ custom_components/heima/v3/contracts/history_intervals.py
@@ -1,4 +1,4 @@
 def _validated_interval(value: HistoryInterval) -> HistoryInterval:
     if not isinstance(value, HistoryInterval):
-        raise TypeError("Historical intersection requires HistoryInterval")
+        raise TypeError("HISTORICAL INTERSECTION REQUIRES HISTORYINTERVAL")
     return HistoryInterval(value.start, value.end, value.include_start, value.include_end)
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
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_2: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     This is a pure occurrence calculation, not a standing CronEntry definition.
     """
     if not isinstance(pattern, WeeklyRecurrence):
-        raise TypeError("Weekly calculation requires WeeklyRecurrence")
+        raise TypeError(None)
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly calculation requires the configured ZoneInfo")
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_3: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     This is a pure occurrence calculation, not a standing CronEntry definition.
     """
     if not isinstance(pattern, WeeklyRecurrence):
-        raise TypeError("Weekly calculation requires WeeklyRecurrence")
+        raise TypeError("XXWeekly calculation requires WeeklyRecurrenceXX")
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly calculation requires the configured ZoneInfo")
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_4: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     This is a pure occurrence calculation, not a standing CronEntry definition.
     """
     if not isinstance(pattern, WeeklyRecurrence):
-        raise TypeError("Weekly calculation requires WeeklyRecurrence")
+        raise TypeError("weekly calculation requires weeklyrecurrence")
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly calculation requires the configured ZoneInfo")
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_5: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -7,7 +7,7 @@
     This is a pure occurrence calculation, not a standing CronEntry definition.
     """
     if not isinstance(pattern, WeeklyRecurrence):
-        raise TypeError("Weekly calculation requires WeeklyRecurrence")
+        raise TypeError("WEEKLY CALCULATION REQUIRES WEEKLYRECURRENCE")
     if not isinstance(time_zone, ZoneInfo):
         raise TypeError("Weekly calculation requires the configured ZoneInfo")
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_7: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(pattern, WeeklyRecurrence):
         raise TypeError("Weekly calculation requires WeeklyRecurrence")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly calculation requires the configured ZoneInfo")
+        raise TypeError(None)
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
     wall = parse_instant(now)
     try:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_8: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(pattern, WeeklyRecurrence):
         raise TypeError("Weekly calculation requires WeeklyRecurrence")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly calculation requires the configured ZoneInfo")
+        raise TypeError("XXWeekly calculation requires the configured ZoneInfoXX")
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
     wall = parse_instant(now)
     try:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_9: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(pattern, WeeklyRecurrence):
         raise TypeError("Weekly calculation requires WeeklyRecurrence")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly calculation requires the configured ZoneInfo")
+        raise TypeError("weekly calculation requires the configured zoneinfo")
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
     wall = parse_instant(now)
     try:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_10: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -9,7 +9,7 @@
     if not isinstance(pattern, WeeklyRecurrence):
         raise TypeError("Weekly calculation requires WeeklyRecurrence")
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("Weekly calculation requires the configured ZoneInfo")
+        raise TypeError("WEEKLY CALCULATION REQUIRES THE CONFIGURED ZONEINFO")
     pattern = WeeklyRecurrence(pattern.weekdays, pattern.hour, pattern.minute)
     wall = parse_instant(now)
     try:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_24: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -16,7 +16,7 @@
         local_wall = wall.astimezone(time_zone)
         local_day = local_wall.date()
         # Today through the same weekday next week, inclusive; not a time horizon.
-        for offset in range(8):
+        for offset in range(9):
             day = local_day + timedelta(days=offset)
             if day.weekday() in pattern.weekdays:
                 requested = datetime(day.year, day.month, day.day, pattern.hour, pattern.minute)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_40: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -22,7 +22,7 @@
                 requested = datetime(day.year, day.month, day.day, pattern.hour, pattern.minute)
                 # Ignore past civil candidates before UTC conversion: near year 1
                 # they may be outside UTC's calendar while next week remains valid.
-                if requested <= local_wall.replace(tzinfo=None):
+                if requested < local_wall.replace(tzinfo=None):
                     continue
                 due = _civil_due(requested, time_zone)
                 if due > wall:
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_47: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -25,7 +25,7 @@
                 if requested <= local_wall.replace(tzinfo=None):
                     continue
                 due = _civil_due(requested, time_zone)
-                if due > wall:
+                if due >= wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_53: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -28,5 +28,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError(None) from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_54: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -28,5 +28,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("XXWeekly due is outside the supported calendarXX") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_55: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -28,5 +28,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("weekly due is outside the supported calendar") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_56: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -28,5 +28,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("WEEKLY DUE IS OUTSIDE THE SUPPORTED CALENDAR") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_57: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -29,4 +29,4 @@
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError(None)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_58: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -29,4 +29,4 @@
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError("XXNo future weekly due in the supported calendarXX")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_59: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -29,4 +29,4 @@
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError("no future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_60: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -29,4 +29,4 @@
                     return WeeklyOccurrence(day, format_instant(due))
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

```diff
# custom_components.heima.v3.runtime.timing.x__countdown__mutmut_8: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,7 +1,7 @@
 def _countdown(delta: timedelta) -> float:
     """Transport integer microseconds as the least float that cannot fire early."""
     microseconds = (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds
-    if microseconds <= 0:
+    if microseconds < 0:
         return 0.0
     seconds = microseconds / 1_000_000
     numerator, denominator = seconds.as_integer_ratio()
```
