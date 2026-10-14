# Temporal mutant review

188 generated, 110 killed, 78 survived, no timeout/error/untested.
Each survivor reviewed below; no known non-equivalent survivor remains.

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_3: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def parse_instant(value: object) -> datetime:
     """Validate exact canonical text and return a temporary UTC datetime."""
     if type(value) is not str:
-        raise TypeError("Instant must be canonical text")
+        raise TypeError(None)
     if _INSTANT.fullmatch(value) is None:
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_4: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def parse_instant(value: object) -> datetime:
     """Validate exact canonical text and return a temporary UTC datetime."""
     if type(value) is not str:
-        raise TypeError("Instant must be canonical text")
+        raise TypeError("XXInstant must be canonical textXX")
     if _INSTANT.fullmatch(value) is None:
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_5: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def parse_instant(value: object) -> datetime:
     """Validate exact canonical text and return a temporary UTC datetime."""
     if type(value) is not str:
-        raise TypeError("Instant must be canonical text")
+        raise TypeError("instant must be canonical text")
     if _INSTANT.fullmatch(value) is None:
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_6

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_6: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def parse_instant(value: object) -> datetime:
     """Validate exact canonical text and return a temporary UTC datetime."""
     if type(value) is not str:
-        raise TypeError("Instant must be canonical text")
+        raise TypeError("INSTANT MUST BE CANONICAL TEXT")
     if _INSTANT.fullmatch(value) is None:
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_9

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_9: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if type(value) is not str:
         raise TypeError("Instant must be canonical text")
     if _INSTANT.fullmatch(value) is None:
-        raise ValueError("Instant must have six fractional digits and +00:00")
+        raise ValueError(None)
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
         raise ValueError("Instant must not require normalization")
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_10

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_10: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if type(value) is not str:
         raise TypeError("Instant must be canonical text")
     if _INSTANT.fullmatch(value) is None:
-        raise ValueError("Instant must have six fractional digits and +00:00")
+        raise ValueError("XXInstant must have six fractional digits and +00:00XX")
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
         raise ValueError("Instant must not require normalization")
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_11

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_11: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if type(value) is not str:
         raise TypeError("Instant must be canonical text")
     if _INSTANT.fullmatch(value) is None:
-        raise ValueError("Instant must have six fractional digits and +00:00")
+        raise ValueError("instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
         raise ValueError("Instant must not require normalization")
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_12

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_12: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if type(value) is not str:
         raise TypeError("Instant must be canonical text")
     if _INSTANT.fullmatch(value) is None:
-        raise ValueError("Instant must have six fractional digits and +00:00")
+        raise ValueError("INSTANT MUST HAVE SIX FRACTIONAL DIGITS AND +00:00")
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
         raise ValueError("Instant must not require normalization")
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_19

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_19: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -6,5 +6,5 @@
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
-        raise ValueError("Instant must not require normalization")
+        raise ValueError(None)
     return parsed
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_20

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_20: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -6,5 +6,5 @@
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
-        raise ValueError("Instant must not require normalization")
+        raise ValueError("XXInstant must not require normalizationXX")
     return parsed
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_21

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_21: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -6,5 +6,5 @@
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
-        raise ValueError("Instant must not require normalization")
+        raise ValueError("instant must not require normalization")
     return parsed
```

## custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_22

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_parse_instant__mutmut_22: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -6,5 +6,5 @@
         raise ValueError("Instant must have six fractional digits and +00:00")
     parsed = datetime.fromisoformat(value)
     if parsed.isoformat(timespec="microseconds") != value:
-        raise ValueError("Instant must not require normalization")
+        raise ValueError("INSTANT MUST NOT REQUIRE NORMALIZATION")
     return parsed
```

## custom_components.heima.v3.contracts.instants.x_validate_instant__mutmut_3

Runtime equivalent typing.cast; the value returned is unchanged.

```diff
# custom_components.heima.v3.contracts.instants.x_validate_instant__mutmut_3: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,4 +1,4 @@
 def validate_instant(value: object) -> EvidenceInstant:
     """Return a semantic string type only after format/calendar validation."""
     parse_instant(value)
-    return EvidenceInstant(cast(str, value))
+    return EvidenceInstant(cast(None, value))
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_2

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_2: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def format_instant(value: datetime) -> EvidenceInstant:
     """Explicit producer normalization; never repair a contract-field string."""
     if not isinstance(value, datetime):
-        raise TypeError("Producer instant must be datetime")
+        raise TypeError(None)
     if value.utcoffset() is None:
         raise ValueError("Producer instant must have a timezone")
     try:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_3: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def format_instant(value: datetime) -> EvidenceInstant:
     """Explicit producer normalization; never repair a contract-field string."""
     if not isinstance(value, datetime):
-        raise TypeError("Producer instant must be datetime")
+        raise TypeError("XXProducer instant must be datetimeXX")
     if value.utcoffset() is None:
         raise ValueError("Producer instant must have a timezone")
     try:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_4: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def format_instant(value: datetime) -> EvidenceInstant:
     """Explicit producer normalization; never repair a contract-field string."""
     if not isinstance(value, datetime):
-        raise TypeError("Producer instant must be datetime")
+        raise TypeError("producer instant must be datetime")
     if value.utcoffset() is None:
         raise ValueError("Producer instant must have a timezone")
     try:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_5: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -1,7 +1,7 @@
 def format_instant(value: datetime) -> EvidenceInstant:
     """Explicit producer normalization; never repair a contract-field string."""
     if not isinstance(value, datetime):
-        raise TypeError("Producer instant must be datetime")
+        raise TypeError("PRODUCER INSTANT MUST BE DATETIME")
     if value.utcoffset() is None:
         raise ValueError("Producer instant must have a timezone")
     try:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_7

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_7: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if not isinstance(value, datetime):
         raise TypeError("Producer instant must be datetime")
     if value.utcoffset() is None:
-        raise ValueError("Producer instant must have a timezone")
+        raise ValueError(None)
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_8

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_8: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if not isinstance(value, datetime):
         raise TypeError("Producer instant must be datetime")
     if value.utcoffset() is None:
-        raise ValueError("Producer instant must have a timezone")
+        raise ValueError("XXProducer instant must have a timezoneXX")
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_9

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_9: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if not isinstance(value, datetime):
         raise TypeError("Producer instant must be datetime")
     if value.utcoffset() is None:
-        raise ValueError("Producer instant must have a timezone")
+        raise ValueError("producer instant must have a timezone")
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_10

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_10: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -3,7 +3,7 @@
     if not isinstance(value, datetime):
         raise TypeError("Producer instant must be datetime")
     if value.utcoffset() is None:
-        raise ValueError("Producer instant must have a timezone")
+        raise ValueError("PRODUCER INSTANT MUST HAVE A TIMEZONE")
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_16

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_16: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -7,5 +7,5 @@
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
-        raise ValueError("Producer instant is outside the supported calendar") from error
+        raise ValueError(None) from error
     return EvidenceInstant(text)
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_17

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_17: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -7,5 +7,5 @@
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
-        raise ValueError("Producer instant is outside the supported calendar") from error
+        raise ValueError("XXProducer instant is outside the supported calendarXX") from error
     return EvidenceInstant(text)
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_18

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_18: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -7,5 +7,5 @@
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
-        raise ValueError("Producer instant is outside the supported calendar") from error
+        raise ValueError("producer instant is outside the supported calendar") from error
     return EvidenceInstant(text)
```

## custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_19

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.instants.x_format_instant__mutmut_19: survived
--- custom_components/heima/v3/contracts/instants.py
+++ custom_components/heima/v3/contracts/instants.py
@@ -7,5 +7,5 @@
     try:
         text = value.astimezone(UTC).isoformat(timespec="microseconds")
     except (ValueError, OverflowError) as error:
-        raise ValueError("Producer instant is outside the supported calendar") from error
+        raise ValueError("PRODUCER INSTANT IS OUTSIDE THE SUPPORTED CALENDAR") from error
     return EvidenceInstant(text)
```

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_6

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_9

Runtime equivalent typing.cast; the value returned is unchanged.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_14

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_15

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_16

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_17

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_23

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_24

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_25

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x_validate_duration__mutmut_26

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_13

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_14

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_15

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁAtJobǁ__post_init____mutmut_16

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_6

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_8

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_9

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_10

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁ__post_init____mutmut_11

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_2

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁWeeklyRecurrenceǁmatches__mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_2

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_2: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError(None)
```

## custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError("XXInterval recurrence requires WindowXX")
```

## custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError("interval recurrence requires window")
```

## custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁIntervalRecurrenceǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -1,3 +1,3 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, Window):
-        raise TypeError("Interval recurrence requires Window")
+        raise TypeError("INTERVAL RECURRENCE REQUIRES WINDOW")
```

## custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, (WeeklyRecurrence, IntervalRecurrence)):
-        raise TypeError("Cron entry requires a recurrence pattern")
+        raise TypeError(None)
```

## custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_6

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, (WeeklyRecurrence, IntervalRecurrence)):
-        raise TypeError("Cron entry requires a recurrence pattern")
+        raise TypeError("XXCron entry requires a recurrence patternXX")
```

## custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_7

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, (WeeklyRecurrence, IntervalRecurrence)):
-        raise TypeError("Cron entry requires a recurrence pattern")
+        raise TypeError("cron entry requires a recurrence pattern")
```

## custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_8

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

```diff
# custom_components.heima.v3.contracts.timing.xǁCronEntryǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/contracts/timing.py
+++ custom_components/heima/v3/contracts/timing.py
@@ -3,4 +3,4 @@
     _validate_text(self.owner)
     _validate_text(self.label)
     if not isinstance(self.pattern, (WeeklyRecurrence, IntervalRecurrence)):
-        raise TypeError("Cron entry requires a recurrence pattern")
+        raise TypeError("CRON ENTRY REQUIRES A RECURRENCE PATTERN")
```

## custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_6

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_7

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_8

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.xǁCalendarWindowǁ__post_init____mutmut_9

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_6

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_11

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_12

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_13

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_civil_component__mutmut_14

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_3

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_4

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_5

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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

## custom_components.heima.v3.contracts.timing.x__validate_text__mutmut_6

Equivalent to the declared contract: same rejection and exception category; generic prose is not a stable diagnostic code.

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
