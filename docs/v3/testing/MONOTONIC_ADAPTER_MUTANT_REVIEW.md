# Monotonic adapter surviving-mutant review

Fresh mutmut 3.8.0 run: 117 generated, 92 killed, 25 survived. Mutated
adapters/ha/monotonic_timer.py with all tests/v3 and seed 3145. Each survivor below
was inspected. Generic exception prose is not an approved contract; exception type,
rejection and timer behavior are retained. typing.cast's type argument is erased at
runtime; this mutation would fail type checking but does not alter timer behavior.

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_3

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_3: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,6 +1,6 @@
 def call_later(self, seconds: float, callback: Callable[[], None]) -> TimerHandle:
     if type(seconds) not in (int, float):
-        raise TypeError("Timer delay must be a non-boolean number")
+        raise TypeError(None)
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_4

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_4: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,6 +1,6 @@
 def call_later(self, seconds: float, callback: Callable[[], None]) -> TimerHandle:
     if type(seconds) not in (int, float):
-        raise TypeError("Timer delay must be a non-boolean number")
+        raise TypeError("XXTimer delay must be a non-boolean numberXX")
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_5

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_5: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,6 +1,6 @@
 def call_later(self, seconds: float, callback: Callable[[], None]) -> TimerHandle:
     if type(seconds) not in (int, float):
-        raise TypeError("Timer delay must be a non-boolean number")
+        raise TypeError("timer delay must be a non-boolean number")
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_6

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_6: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,6 +1,6 @@
 def call_later(self, seconds: float, callback: Callable[[], None]) -> TimerHandle:
     if type(seconds) not in (int, float):
-        raise TypeError("Timer delay must be a non-boolean number")
+        raise TypeError("TIMER DELAY MUST BE A NON-BOOLEAN NUMBER")
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_9

Runtime-equivalent typing.cast annotation.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_9: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -2,7 +2,7 @@
     if type(seconds) not in (int, float):
         raise TypeError("Timer delay must be a non-boolean number")
     try:
-        delay = float(cast(int | float, seconds))
+        delay = float(cast(None, seconds))
     except OverflowError as error:
         raise ValueError("Timer delay must be finite") from error
     if not isfinite(delay) or delay < 0:
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_14

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_14: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -4,7 +4,7 @@
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
-        raise ValueError("Timer delay must be finite") from error
+        raise ValueError(None) from error
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_15

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_15: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -4,7 +4,7 @@
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
-        raise ValueError("Timer delay must be finite") from error
+        raise ValueError("XXTimer delay must be finiteXX") from error
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_16

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_16: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -4,7 +4,7 @@
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
-        raise ValueError("Timer delay must be finite") from error
+        raise ValueError("timer delay must be finite") from error
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_17

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_17: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -4,7 +4,7 @@
     try:
         delay = float(cast(int | float, seconds))
     except OverflowError as error:
-        raise ValueError("Timer delay must be finite") from error
+        raise ValueError("TIMER DELAY MUST BE FINITE") from error
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_23

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_23: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -6,7 +6,7 @@
     except OverflowError as error:
         raise ValueError("Timer delay must be finite") from error
     if not isfinite(delay) or delay < 0:
-        raise ValueError("Timer delay must be finite and nonnegative")
+        raise ValueError(None)
     if not callable(callback):
         raise TypeError("Timer callback must be callable")
     deadline = _deadline_after(self._loop.time(), delay)
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_24

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_24: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -6,7 +6,7 @@
     except OverflowError as error:
         raise ValueError("Timer delay must be finite") from error
     if not isfinite(delay) or delay < 0:
-        raise ValueError("Timer delay must be finite and nonnegative")
+        raise ValueError("XXTimer delay must be finite and nonnegativeXX")
     if not callable(callback):
         raise TypeError("Timer callback must be callable")
     deadline = _deadline_after(self._loop.time(), delay)
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_25

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_25: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -6,7 +6,7 @@
     except OverflowError as error:
         raise ValueError("Timer delay must be finite") from error
     if not isfinite(delay) or delay < 0:
-        raise ValueError("Timer delay must be finite and nonnegative")
+        raise ValueError("timer delay must be finite and nonnegative")
     if not callable(callback):
         raise TypeError("Timer callback must be callable")
     deadline = _deadline_after(self._loop.time(), delay)
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_26

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_26: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -6,7 +6,7 @@
     except OverflowError as error:
         raise ValueError("Timer delay must be finite") from error
     if not isfinite(delay) or delay < 0:
-        raise ValueError("Timer delay must be finite and nonnegative")
+        raise ValueError("TIMER DELAY MUST BE FINITE AND NONNEGATIVE")
     if not callable(callback):
         raise TypeError("Timer callback must be callable")
     deadline = _deadline_after(self._loop.time(), delay)
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_29

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_29: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -8,6 +8,6 @@
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
-        raise TypeError("Timer callback must be callable")
+        raise TypeError(None)
     deadline = _deadline_after(self._loop.time(), delay)
     return _DeadlineTimer(self._loop, deadline, self._resolution, callback)
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_30

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_30: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -8,6 +8,6 @@
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
-        raise TypeError("Timer callback must be callable")
+        raise TypeError("XXTimer callback must be callableXX")
     deadline = _deadline_after(self._loop.time(), delay)
     return _DeadlineTimer(self._loop, deadline, self._resolution, callback)
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_31

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_31: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -8,6 +8,6 @@
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
-        raise TypeError("Timer callback must be callable")
+        raise TypeError("timer callback must be callable")
     deadline = _deadline_after(self._loop.time(), delay)
     return _DeadlineTimer(self._loop, deadline, self._resolution, callback)
```

## xǁAsyncioMonotonicTimerǁcall_later__mutmut_32

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.xǁAsyncioMonotonicTimerǁcall_later__mutmut_32: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -8,6 +8,6 @@
     if not isfinite(delay) or delay < 0:
         raise ValueError("Timer delay must be finite and nonnegative")
     if not callable(callback):
-        raise TypeError("Timer callback must be callable")
+        raise TypeError("TIMER CALLBACK MUST BE CALLABLE")
     deadline = _deadline_after(self._loop.time(), delay)
     return _DeadlineTimer(self._loop, deadline, self._resolution, callback)
```

## x__deadline_after__mutmut_5

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_5: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,7 +1,7 @@
 def _deadline_after(origin: float, delay: float) -> float:
     deadline = origin + delay
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError(None)
     # TwoSum recovers the addition's rounding error. Advance only a sum rounded
     # down, including a tiny positive delay lost entirely at a large uptime.
     recovered_delay = deadline - origin
```

## x__deadline_after__mutmut_6

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_6: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,7 +1,7 @@
 def _deadline_after(origin: float, delay: float) -> float:
     deadline = origin + delay
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError("XXTimer deadline is not representableXX")
     # TwoSum recovers the addition's rounding error. Advance only a sum rounded
     # down, including a tiny positive delay lost entirely at a large uptime.
     recovered_delay = deadline - origin
```

## x__deadline_after__mutmut_7

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_7: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,7 +1,7 @@
 def _deadline_after(origin: float, delay: float) -> float:
     deadline = origin + delay
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError("timer deadline is not representable")
     # TwoSum recovers the addition's rounding error. Advance only a sum rounded
     # down, including a tiny positive delay lost entirely at a large uptime.
     recovered_delay = deadline - origin
```

## x__deadline_after__mutmut_8

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_8: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -1,7 +1,7 @@
 def _deadline_after(origin: float, delay: float) -> float:
     deadline = origin + delay
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError("TIMER DEADLINE IS NOT REPRESENTABLE")
     # TwoSum recovers the addition's rounding error. Advance only a sum rounded
     # down, including a tiny positive delay lost entirely at a large uptime.
     recovered_delay = deadline - origin
```

## x__deadline_after__mutmut_25

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_25: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -9,5 +9,5 @@
     if error > 0:
         deadline = nextafter(deadline, inf)
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError(None)
     return deadline
```

## x__deadline_after__mutmut_26

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_26: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -9,5 +9,5 @@
     if error > 0:
         deadline = nextafter(deadline, inf)
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError("XXTimer deadline is not representableXX")
     return deadline
```

## x__deadline_after__mutmut_27

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_27: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -9,5 +9,5 @@
     if error > 0:
         deadline = nextafter(deadline, inf)
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError("timer deadline is not representable")
     return deadline
```

## x__deadline_after__mutmut_28

Uncontracted exception prose only; error type and scheduling behavior retained.

```diff
# custom_components.heima.v3.adapters.ha.monotonic_timer.x__deadline_after__mutmut_28: survived
--- custom_components/heima/v3/adapters/ha/monotonic_timer.py
+++ custom_components/heima/v3/adapters/ha/monotonic_timer.py
@@ -9,5 +9,5 @@
     if error > 0:
         deadline = nextafter(deadline, inf)
     if not isfinite(deadline):
-        raise ValueError("Timer deadline is not representable")
+        raise ValueError("TIMER DEADLINE IS NOT REPRESENTABLE")
     return deadline
```
