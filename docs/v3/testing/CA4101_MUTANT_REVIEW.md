# CA4-101 mutation review — 2026-10-15

Fresh mutmut 3.8 on contracts/timing.py and runtime/recurrence.py, whole V3 suite,
seed3145: 305 generated, 210 killed, 5 timeout, 90 survived, no skipped/error.
Survivors: 80 generic validation prose (52 timing, 12 interval planner, 16 weekly
calculator), 1 typing.cast first argument (runtime identity), 9 equivalent search
variants (range(9), plus eight previously reviewed _civil_due variants). Ordinary
error text is not a stable diagnostic code; rejection types/side effects are retained.

Search variants retain prior WEEKLY_MUTANT_REVIEW.md assessments: the ninth date
is not reached after a valid first weekly candidate; UTC->aware host conversion
changes representation before canonical output, not the physical instant; omitted
fold defaults to zero; interior-point changes still converge to the same endpoint;
>= vs > cannot equal an impossible local gap value. Five timeout mutations destroy
termination/progress and are separate from assertion kills. No behavioral survivor.

Supplement mutation_timing.py: 10 killed with baseline pass. New
mutation_weekly_occurrence.py: immutable-result removal and requested-date replaced
with actual-start-date both killed by Apia metadata test. No score gate introduced.

## Exact non-killed mutation diffs

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_3: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,7 +1,7 @@
 def validate_duration(value: object) -> float:
     """Normalize a positive finite non-boolean duration, including fractions."""
     if type(value) not in (int, float):
-        raise TypeError("Duration must be a non-boolean number")
+        raise TypeError(None)
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_4: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,7 +1,7 @@
 def validate_duration(value: object) -> float:
     """Normalize a positive finite non-boolean duration, including fractions."""
     if type(value) not in (int, float):
-        raise TypeError("Duration must be a non-boolean number")
+        raise TypeError("XXDuration must be a non-boolean numberXX")
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,7 +1,7 @@
 def validate_duration(value: object) -> float:
     """Normalize a positive finite non-boolean duration, including fractions."""
     if type(value) not in (int, float):
-        raise TypeError("Duration must be a non-boolean number")
+        raise TypeError("duration must be a non-boolean number")
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_6: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,7 +1,7 @@
 def validate_duration(value: object) -> float:
     """Normalize a positive finite non-boolean duration, including fractions."""
     if type(value) not in (int, float):
-        raise TypeError("Duration must be a non-boolean number")
+        raise TypeError("DURATION MUST BE A NON-BOOLEAN NUMBER")
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_9: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,7 +3,7 @@
     if type(value) not in (int, float):
         raise TypeError("Duration must be a non-boolean number")
     try:
-        seconds = float(cast(int | float, value))
+        seconds = float(cast(None, value))
     except OverflowError as error:
         raise ValueError("Duration must be finite") from error
     if not isfinite(seconds) or seconds <= 0:
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_14: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
-        raise ValueError("Duration must be finite") from error
+        raise ValueError(None) from error
     if not isfinite(seconds) or seconds <= 0:
         raise ValueError("Duration must be positive and finite")
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_15: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
-        raise ValueError("Duration must be finite") from error
+        raise ValueError("XXDuration must be finiteXX") from error
     if not isfinite(seconds) or seconds <= 0:
         raise ValueError("Duration must be positive and finite")
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_16: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
-        raise ValueError("Duration must be finite") from error
+        raise ValueError("duration must be finite") from error
     if not isfinite(seconds) or seconds <= 0:
         raise ValueError("Duration must be positive and finite")
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_17: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
     try:
         seconds = float(cast(int | float, value))
     except OverflowError as error:
-        raise ValueError("Duration must be finite") from error
+        raise ValueError("DURATION MUST BE FINITE") from error
     if not isfinite(seconds) or seconds <= 0:
         raise ValueError("Duration must be positive and finite")
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_23: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -7,5 +7,5 @@
     except OverflowError as error:
         raise ValueError("Duration must be finite") from error
     if not isfinite(seconds) or seconds <= 0:
-        raise ValueError("Duration must be positive and finite")
+        raise ValueError(None)
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_24: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -7,5 +7,5 @@
     except OverflowError as error:
         raise ValueError("Duration must be finite") from error
     if not isfinite(seconds) or seconds <= 0:
-        raise ValueError("Duration must be positive and finite")
+        raise ValueError("XXDuration must be positive and finiteXX")
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_25: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -7,5 +7,5 @@
     except OverflowError as error:
         raise ValueError("Duration must be finite") from error
     if not isfinite(seconds) or seconds <= 0:
-        raise ValueError("Duration must be positive and finite")
+        raise ValueError("duration must be positive and finite")
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_26: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -7,5 +7,5 @@
     except OverflowError as error:
         raise ValueError("Duration must be finite") from error
     if not isfinite(seconds) or seconds <= 0:
-        raise ValueError("Duration must be positive and finite")
+        raise ValueError("DURATION MUST BE POSITIVE AND FINITE")
     return seconds
```

```diff
# custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_13: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -4,4 +4,4 @@
     _validate_text(self.label)
     parse_instant(self.due)
     if type(self.basis) is not str or self.basis not in ("elapsed", "wall_clock"):
-        raise ValueError("Job basis must be elapsed or wall_clock")
+        raise ValueError(None)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_14: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -4,4 +4,4 @@
     _validate_text(self.label)
     parse_instant(self.due)
     if type(self.basis) is not str or self.basis not in ("elapsed", "wall_clock"):
-        raise ValueError("Job basis must be elapsed or wall_clock")
+        raise ValueError("XXJob basis must be elapsed or wall_clockXX")
```

```diff
# custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_15: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -4,4 +4,4 @@
     _validate_text(self.label)
     parse_instant(self.due)
     if type(self.basis) is not str or self.basis not in ("elapsed", "wall_clock"):
-        raise ValueError("Job basis must be elapsed or wall_clock")
+        raise ValueError("job basis must be elapsed or wall_clock")
```

```diff
# custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_16: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -4,4 +4,4 @@
     _validate_text(self.label)
     parse_instant(self.due)
     if type(self.basis) is not str or self.basis not in ("elapsed", "wall_clock"):
-        raise ValueError("Job basis must be elapsed or wall_clock")
+        raise ValueError("JOB BASIS MUST BE ELAPSED OR WALL_CLOCK")
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.weekdays) is not frozenset:
-        raise TypeError("Weekdays must be immutable")
+        raise TypeError(None)
     if not self.weekdays:
         raise ValueError("Weekdays must not be empty")
     for day in self.weekdays:
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.weekdays) is not frozenset:
-        raise TypeError("Weekdays must be immutable")
+        raise TypeError("XXWeekdays must be immutableXX")
     if not self.weekdays:
         raise ValueError("Weekdays must not be empty")
     for day in self.weekdays:
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.weekdays) is not frozenset:
-        raise TypeError("Weekdays must be immutable")
+        raise TypeError("weekdays must be immutable")
     if not self.weekdays:
         raise ValueError("Weekdays must not be empty")
     for day in self.weekdays:
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.weekdays) is not frozenset:
-        raise TypeError("Weekdays must be immutable")
+        raise TypeError("WEEKDAYS MUST BE IMMUTABLE")
     if not self.weekdays:
         raise ValueError("Weekdays must not be empty")
     for day in self.weekdays:
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,7 +2,7 @@
     if type(self.weekdays) is not frozenset:
         raise TypeError("Weekdays must be immutable")
     if not self.weekdays:
-        raise ValueError("Weekdays must not be empty")
+        raise ValueError(None)
     for day in self.weekdays:
         _validate_civil_component(day, 6)
     _validate_civil_component(self.hour, 23)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,7 +2,7 @@
     if type(self.weekdays) is not frozenset:
         raise TypeError("Weekdays must be immutable")
     if not self.weekdays:
-        raise ValueError("Weekdays must not be empty")
+        raise ValueError("XXWeekdays must not be emptyXX")
     for day in self.weekdays:
         _validate_civil_component(day, 6)
     _validate_civil_component(self.hour, 23)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_10: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,7 +2,7 @@
     if type(self.weekdays) is not frozenset:
         raise TypeError("Weekdays must be immutable")
     if not self.weekdays:
-        raise ValueError("Weekdays must not be empty")
+        raise ValueError("weekdays must not be empty")
     for day in self.weekdays:
         _validate_civil_component(day, 6)
     _validate_civil_component(self.hour, 23)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_11: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,7 +2,7 @@
     if type(self.weekdays) is not frozenset:
         raise TypeError("Weekdays must be immutable")
     if not self.weekdays:
-        raise ValueError("Weekdays must not be empty")
+        raise ValueError("WEEKDAYS MUST NOT BE EMPTY")
     for day in self.weekdays:
         _validate_civil_component(day, 6)
     _validate_civil_component(self.hour, 23)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_2: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
         next due or apply the scheduler's single-firing/gap policy.
         """
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("A configured ZoneInfo is required")
+        raise TypeError(None)
     local = parse_instant(when).astimezone(time_zone)
     return (
         local.weekday() in self.weekdays
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_3: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
         next due or apply the scheduler's single-firing/gap policy.
         """
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("A configured ZoneInfo is required")
+        raise TypeError("XXA configured ZoneInfo is requiredXX")
     local = parse_instant(when).astimezone(time_zone)
     return (
         local.weekday() in self.weekdays
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_4: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
         next due or apply the scheduler's single-firing/gap policy.
         """
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("A configured ZoneInfo is required")
+        raise TypeError("a configured zoneinfo is required")
     local = parse_instant(when).astimezone(time_zone)
     return (
         local.weekday() in self.weekdays
```

```diff
# custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -5,7 +5,7 @@
         next due or apply the scheduler's single-firing/gap policy.
         """
     if not isinstance(time_zone, ZoneInfo):
-        raise TypeError("A configured ZoneInfo is required")
+        raise TypeError("A CONFIGURED ZONEINFO IS REQUIRED")
     local = parse_instant(when).astimezone(time_zone)
     return (
         local.weekday() in self.weekdays
```

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_2: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,4 +1,4 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError(None)
     object.__setattr__(self, "interval", Window(self.interval.seconds))
```

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,4 +1,4 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError("XXInterval recurrence requires WindowXX")
     object.__setattr__(self, "interval", Window(self.interval.seconds))
```

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,4 +1,4 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError("interval recurrence requires window")
     object.__setattr__(self, "interval", Window(self.interval.seconds))
```

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,4 +1,4 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError("INTERVAL RECURRENCE REQUIRES WINDOW")
     object.__setattr__(self, "interval", Window(self.interval.seconds))
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, IntervalRecurrence):
-        raise TypeError("Cron entry requires IntervalRecurrence")
+        raise TypeError(None)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, IntervalRecurrence):
-        raise TypeError("Cron entry requires IntervalRecurrence")
+        raise TypeError("XXCron entry requires IntervalRecurrenceXX")
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, IntervalRecurrence):
-        raise TypeError("Cron entry requires IntervalRecurrence")
+        raise TypeError("cron entry requires intervalrecurrence")
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, IntervalRecurrence):
-        raise TypeError("Cron entry requires IntervalRecurrence")
+        raise TypeError("CRON ENTRY REQUIRES INTERVALRECURRENCE")
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,6 +2,6 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end <= start:
-        raise ValueError("Calendar end must follow start")
+        raise ValueError(None)
     _validate_text(self.summary)
     _validate_text(self.source_entity)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,6 +2,6 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end <= start:
-        raise ValueError("Calendar end must follow start")
+        raise ValueError("XXCalendar end must follow startXX")
     _validate_text(self.summary)
     _validate_text(self.source_entity)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,6 +2,6 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end <= start:
-        raise ValueError("Calendar end must follow start")
+        raise ValueError("calendar end must follow start")
     _validate_text(self.summary)
     _validate_text(self.source_entity)
```

```diff
# custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,6 +2,6 @@
     start = parse_instant(self.start)
     end = parse_instant(self.end)
     if end <= start:
-        raise ValueError("Calendar end must follow start")
+        raise ValueError("CALENDAR END MUST FOLLOW START")
     _validate_text(self.summary)
     _validate_text(self.source_entity)
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_3: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,5 +1,5 @@
 def _validate_civil_component(value: object, maximum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Civil time components must be non-boolean integers")
+        raise TypeError(None)
     if not 0 <= value <= maximum:
         raise ValueError("Civil time component outside its range")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_4: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,5 +1,5 @@
 def _validate_civil_component(value: object, maximum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Civil time components must be non-boolean integers")
+        raise TypeError("XXCivil time components must be non-boolean integersXX")
     if not 0 <= value <= maximum:
         raise ValueError("Civil time component outside its range")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,5 +1,5 @@
 def _validate_civil_component(value: object, maximum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Civil time components must be non-boolean integers")
+        raise TypeError("civil time components must be non-boolean integers")
     if not 0 <= value <= maximum:
         raise ValueError("Civil time component outside its range")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_6: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,5 +1,5 @@
 def _validate_civil_component(value: object, maximum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Civil time components must be non-boolean integers")
+        raise TypeError("CIVIL TIME COMPONENTS MUST BE NON-BOOLEAN INTEGERS")
     if not 0 <= value <= maximum:
         raise ValueError("Civil time component outside its range")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_11: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Civil time components must be non-boolean integers")
     if not 0 <= value <= maximum:
-        raise ValueError("Civil time component outside its range")
+        raise ValueError(None)
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_12: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Civil time components must be non-boolean integers")
     if not 0 <= value <= maximum:
-        raise ValueError("Civil time component outside its range")
+        raise ValueError("XXCivil time component outside its rangeXX")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_13: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Civil time components must be non-boolean integers")
     if not 0 <= value <= maximum:
-        raise ValueError("Civil time component outside its range")
+        raise ValueError("civil time component outside its range")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_14: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Civil time components must be non-boolean integers")
     if not 0 <= value <= maximum:
-        raise ValueError("Civil time component outside its range")
+        raise ValueError("CIVIL TIME COMPONENT OUTSIDE ITS RANGE")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_3: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def _validate_text(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Contract text must be str")
+        raise TypeError(None)
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_4: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def _validate_text(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Contract text must be str")
+        raise TypeError("XXContract text must be strXX")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def _validate_text(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Contract text must be str")
+        raise TypeError("contract text must be str")
```

```diff
# custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_6: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def _validate_text(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Contract text must be str")
+        raise TypeError("CONTRACT TEXT MUST BE STR")
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
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_23: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -15,7 +15,7 @@
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
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_50: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -23,5 +23,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError(None) from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_51: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -23,5 +23,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("XXWeekly due is outside the supported calendarXX") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_52: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -23,5 +23,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("weekly due is outside the supported calendar") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_53: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -23,5 +23,5 @@
                 if due > wall:
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
-        raise ValueError("Weekly due is outside the supported calendar") from error
+        raise ValueError("WEEKLY DUE IS OUTSIDE THE SUPPORTED CALENDAR") from error
     raise ValueError("No future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_54: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -24,4 +24,4 @@
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError(None)
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_55: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -24,4 +24,4 @@
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError("XXNo future weekly due in the supported calendarXX")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_56: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -24,4 +24,4 @@
                     return WeeklyOccurrence(day, format_instant(due))
     except OverflowError as error:
         raise ValueError("Weekly due is outside the supported calendar") from error
-    raise ValueError("No future weekly due in the supported calendar")
+    raise ValueError("no future weekly due in the supported calendar")
```

```diff
# custom_components.heima.v3.runtime.recurrence.x_next_weekly_occurrence__mutmut_57: survived
--- custom_components/heima/v3/runtime/recurrence.py
+++ custom_components/heima/v3/runtime/recurrence.py
@@ -24,4 +24,4 @@
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
