# Clock-gap durability — mutation review, 2026-10-15

Fresh mutmut 3.8, Python 3.14.5, only storage/clock_gaps.py, all tests/v3,
seed3145, four children: **205 generated, 165 killed, 40 survived; zero timeout,
error, skipped or untested.** All forty surviving diffs are inspected below.
They alter generic TypeError/ValueError prose only; there is no specified message
text contract. No non-equivalent survivor remains. No raw 100% score is claimed.

The first fresh run had 164 killed and 41 survivors. One behavioral survivor
(ClockGapDurability.__post_init__ mutant14) always validated a point at gap.start,
skipping actual pending-end validation when no closing receipt existed. Added two
cases with malformed/reversed pending ends, including forged state passed to early
empty/before-gap reads. Clean baseline passes; this mutant is now killed. The final
run used a new mutants directory, avoiding cached outcomes after test changes.

## Reproduction and tool limits

Copy current source/tests, pytest-v3.ini and pyproject.toml into a fresh temporary
work directory. Narrow only_mutate to storage/clock_gaps.py there, retain all tests/v3
and seed3145, then run:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_clock_gap_durability.py
```

Run path /private/tmp/heima-v3-clock-gap-durability, final log
/private/tmp/heima-durable-gaps-mutmut-final.log. Repository default adds this module
to the previous sixteen; the scoped result does not claim a fresh run for unchanged
modules. All executable function bodies are in scope. There are no new module constants
or properties outside the mutator scope. The two frozen declarations are tested by the
supplement: clean 56-test baseline, then each mutable declaration must fail with pytest
exit1 in test_receipts_and_durability_snapshots_are_immutable. Both mutants were killed.

## Individually inspected survivors

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_3

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.gap_id) is not str:
-        raise TypeError("Clock gap id must be text")
+        raise TypeError(None)
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_4

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.gap_id) is not str:
-        raise TypeError("Clock gap id must be text")
+        raise TypeError("XXClock gap id must be textXX")
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_5

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.gap_id) is not str:
-        raise TypeError("Clock gap id must be text")
+        raise TypeError("clock gap id must be text")
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_6

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.gap_id) is not str:
-        raise TypeError("Clock gap id must be text")
+        raise TypeError("CLOCK GAP ID MUST BE TEXT")
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_8

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if type(self.gap_id) is not str:
         raise TypeError("Clock gap id must be text")
     if not self.gap_id:
-        raise ValueError("Clock gap id must be nonempty")
+        raise ValueError(None)
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_9

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if type(self.gap_id) is not str:
         raise TypeError("Clock gap id must be text")
     if not self.gap_id:
-        raise ValueError("Clock gap id must be nonempty")
+        raise ValueError("XXClock gap id must be nonemptyXX")
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_10

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_10: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if type(self.gap_id) is not str:
         raise TypeError("Clock gap id must be text")
     if not self.gap_id:
-        raise ValueError("Clock gap id must be nonempty")
+        raise ValueError("clock gap id must be nonempty")
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_11

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_11: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if type(self.gap_id) is not str:
         raise TypeError("Clock gap id must be text")
     if not self.gap_id:
-        raise ValueError("Clock gap id must be nonempty")
+        raise ValueError("CLOCK GAP ID MUST BE NONEMPTY")
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_14

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_14: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -4,7 +4,7 @@
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
-        raise TypeError("Clock gap boundary must be text")
+        raise TypeError(None)
     if self.boundary not in ("opening", "closing"):
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_15

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_15: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -4,7 +4,7 @@
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
-        raise TypeError("Clock gap boundary must be text")
+        raise TypeError("XXClock gap boundary must be textXX")
     if self.boundary not in ("opening", "closing"):
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_16

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_16: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -4,7 +4,7 @@
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
-        raise TypeError("Clock gap boundary must be text")
+        raise TypeError("clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_17

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_17: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -4,7 +4,7 @@
     if not self.gap_id:
         raise ValueError("Clock gap id must be nonempty")
     if type(self.boundary) is not str:
-        raise TypeError("Clock gap boundary must be text")
+        raise TypeError("CLOCK GAP BOUNDARY MUST BE TEXT")
     if self.boundary not in ("opening", "closing"):
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_23

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_23: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -6,7 +6,7 @@
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
-        raise ValueError("Unknown clock gap boundary")
+        raise ValueError(None)
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
         raise TypeError("Boundary inclusion must be boolean")
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_24

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_24: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -6,7 +6,7 @@
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
-        raise ValueError("Unknown clock gap boundary")
+        raise ValueError("XXUnknown clock gap boundaryXX")
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
         raise TypeError("Boundary inclusion must be boolean")
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_25

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_25: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -6,7 +6,7 @@
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
-        raise ValueError("Unknown clock gap boundary")
+        raise ValueError("unknown clock gap boundary")
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
         raise TypeError("Boundary inclusion must be boolean")
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_26

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_26: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -6,7 +6,7 @@
     if type(self.boundary) is not str:
         raise TypeError("Clock gap boundary must be text")
     if self.boundary not in ("opening", "closing"):
-        raise ValueError("Unknown clock gap boundary")
+        raise ValueError("UNKNOWN CLOCK GAP BOUNDARY")
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
         raise TypeError("Boundary inclusion must be boolean")
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_30

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_30: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,4 +9,4 @@
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
-        raise TypeError("Boundary inclusion must be boolean")
+        raise TypeError(None)
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_31

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_31: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,4 +9,4 @@
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
-        raise TypeError("Boundary inclusion must be boolean")
+        raise TypeError("XXBoundary inclusion must be booleanXX")
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_32

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_32: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,4 +9,4 @@
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
-        raise TypeError("Boundary inclusion must be boolean")
+        raise TypeError("boundary inclusion must be boolean")
```

### xǁClockGapBoundaryReceiptǁ__post_init____mutmut_33

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapBoundaryReceiptǁ__post_init____mutmut_33: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,4 +9,4 @@
         raise ValueError("Unknown clock gap boundary")
     parse_instant(self.when)
     if type(self.includes_boundary) is not bool:
-        raise TypeError("Boundary inclusion must be boolean")
+        raise TypeError("BOUNDARY INCLUSION MUST BE BOOLEAN")
```

### xǁClockGapDurabilityǁ__post_init____mutmut_2

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_2: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.gap, ClockGap):
-        raise TypeError("Durability requires a ClockGap intent")
+        raise TypeError(None)
     if type(self.gap.await_floor_recovery) is not bool:
         raise TypeError("Clock gap end rule must be boolean")
     end = self.gap.start if self.gap.end is None else self.gap.end
```

### xǁClockGapDurabilityǁ__post_init____mutmut_3

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.gap, ClockGap):
-        raise TypeError("Durability requires a ClockGap intent")
+        raise TypeError("XXDurability requires a ClockGap intentXX")
     if type(self.gap.await_floor_recovery) is not bool:
         raise TypeError("Clock gap end rule must be boolean")
     end = self.gap.start if self.gap.end is None else self.gap.end
```

### xǁClockGapDurabilityǁ__post_init____mutmut_4

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.gap, ClockGap):
-        raise TypeError("Durability requires a ClockGap intent")
+        raise TypeError("durability requires a clockgap intent")
     if type(self.gap.await_floor_recovery) is not bool:
         raise TypeError("Clock gap end rule must be boolean")
     end = self.gap.start if self.gap.end is None else self.gap.end
```

### xǁClockGapDurabilityǁ__post_init____mutmut_5

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.gap, ClockGap):
-        raise TypeError("Durability requires a ClockGap intent")
+        raise TypeError("DURABILITY REQUIRES A CLOCKGAP INTENT")
     if type(self.gap.await_floor_recovery) is not bool:
         raise TypeError("Clock gap end rule must be boolean")
     end = self.gap.start if self.gap.end is None else self.gap.end
```

### xǁClockGapDurabilityǁ__post_init____mutmut_8

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if not isinstance(self.gap, ClockGap):
         raise TypeError("Durability requires a ClockGap intent")
     if type(self.gap.await_floor_recovery) is not bool:
-        raise TypeError("Clock gap end rule must be boolean")
+        raise TypeError(None)
     end = self.gap.start if self.gap.end is None else self.gap.end
     HistoryInterval(self.gap.start, end, self.include_start, self.include_end)
     # Validate the id even if neither boundary has a receipt yet.
```

### xǁClockGapDurabilityǁ__post_init____mutmut_9

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if not isinstance(self.gap, ClockGap):
         raise TypeError("Durability requires a ClockGap intent")
     if type(self.gap.await_floor_recovery) is not bool:
-        raise TypeError("Clock gap end rule must be boolean")
+        raise TypeError("XXClock gap end rule must be booleanXX")
     end = self.gap.start if self.gap.end is None else self.gap.end
     HistoryInterval(self.gap.start, end, self.include_start, self.include_end)
     # Validate the id even if neither boundary has a receipt yet.
```

### xǁClockGapDurabilityǁ__post_init____mutmut_10

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_10: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if not isinstance(self.gap, ClockGap):
         raise TypeError("Durability requires a ClockGap intent")
     if type(self.gap.await_floor_recovery) is not bool:
-        raise TypeError("Clock gap end rule must be boolean")
+        raise TypeError("clock gap end rule must be boolean")
     end = self.gap.start if self.gap.end is None else self.gap.end
     HistoryInterval(self.gap.start, end, self.include_start, self.include_end)
     # Validate the id even if neither boundary has a receipt yet.
```

### xǁClockGapDurabilityǁ__post_init____mutmut_11

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ__post_init____mutmut_11: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -2,7 +2,7 @@
     if not isinstance(self.gap, ClockGap):
         raise TypeError("Durability requires a ClockGap intent")
     if type(self.gap.await_floor_recovery) is not bool:
-        raise TypeError("Clock gap end rule must be boolean")
+        raise TypeError("CLOCK GAP END RULE MUST BE BOOLEAN")
     end = self.gap.start if self.gap.end is None else self.gap.end
     HistoryInterval(self.gap.start, end, self.include_start, self.include_end)
     # Validate the id even if neither boundary has a receipt yet.
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_3

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_3: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -8,7 +8,7 @@
     if receipt is None:
         return
     if not isinstance(receipt, ClockGapBoundaryReceipt):
-        raise TypeError("Clock gap proof requires a boundary receipt")
+        raise TypeError(None)
     validated = ClockGapBoundaryReceipt(
         receipt.gap_id, receipt.boundary, receipt.when, receipt.includes_boundary
     )
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_4

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_4: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -8,7 +8,7 @@
     if receipt is None:
         return
     if not isinstance(receipt, ClockGapBoundaryReceipt):
-        raise TypeError("Clock gap proof requires a boundary receipt")
+        raise TypeError("XXClock gap proof requires a boundary receiptXX")
     validated = ClockGapBoundaryReceipt(
         receipt.gap_id, receipt.boundary, receipt.when, receipt.includes_boundary
     )
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_5

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_5: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -8,7 +8,7 @@
     if receipt is None:
         return
     if not isinstance(receipt, ClockGapBoundaryReceipt):
-        raise TypeError("Clock gap proof requires a boundary receipt")
+        raise TypeError("clock gap proof requires a boundary receipt")
     validated = ClockGapBoundaryReceipt(
         receipt.gap_id, receipt.boundary, receipt.when, receipt.includes_boundary
     )
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_6

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_6: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -8,7 +8,7 @@
     if receipt is None:
         return
     if not isinstance(receipt, ClockGapBoundaryReceipt):
-        raise TypeError("Clock gap proof requires a boundary receipt")
+        raise TypeError("CLOCK GAP PROOF REQUIRES A BOUNDARY RECEIPT")
     validated = ClockGapBoundaryReceipt(
         receipt.gap_id, receipt.boundary, receipt.when, receipt.includes_boundary
     )
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_29

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_29: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -18,4 +18,4 @@
         else None
     )
     if validated != expected:
-        raise ValueError("Receipt does not match the clock gap boundary")
+        raise ValueError(None)
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_30

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_30: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -18,4 +18,4 @@
         else None
     )
     if validated != expected:
-        raise ValueError("Receipt does not match the clock gap boundary")
+        raise ValueError("XXReceipt does not match the clock gap boundaryXX")
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_31

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_31: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -18,4 +18,4 @@
         else None
     )
     if validated != expected:
-        raise ValueError("Receipt does not match the clock gap boundary")
+        raise ValueError("receipt does not match the clock gap boundary")
```

### xǁClockGapDurabilityǁ_validate_receipt__mutmut_32

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.xǁClockGapDurabilityǁ_validate_receipt__mutmut_32: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -18,4 +18,4 @@
         else None
     )
     if validated != expected:
-        raise ValueError("Receipt does not match the clock gap boundary")
+        raise ValueError("RECEIPT DOES NOT MATCH THE CLOCK GAP BOUNDARY")
```

### x_clock_gap_observation_coverage__mutmut_7

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.x_clock_gap_observation_coverage__mutmut_7: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,7 +9,7 @@
     """
     requested = intersect_history_intervals(request, request)
     if not isinstance(durability, ClockGapDurability):
-        raise TypeError("Clock gap coverage requires explicit durability state")
+        raise TypeError(None)
     state = ClockGapDurability(
         durability.gap_id,
         durability.gap,
```

### x_clock_gap_observation_coverage__mutmut_8

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.x_clock_gap_observation_coverage__mutmut_8: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,7 +9,7 @@
     """
     requested = intersect_history_intervals(request, request)
     if not isinstance(durability, ClockGapDurability):
-        raise TypeError("Clock gap coverage requires explicit durability state")
+        raise TypeError("XXClock gap coverage requires explicit durability stateXX")
     state = ClockGapDurability(
         durability.gap_id,
         durability.gap,
```

### x_clock_gap_observation_coverage__mutmut_9

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.x_clock_gap_observation_coverage__mutmut_9: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,7 +9,7 @@
     """
     requested = intersect_history_intervals(request, request)
     if not isinstance(durability, ClockGapDurability):
-        raise TypeError("Clock gap coverage requires explicit durability state")
+        raise TypeError("clock gap coverage requires explicit durability state")
     state = ClockGapDurability(
         durability.gap_id,
         durability.gap,
```

### x_clock_gap_observation_coverage__mutmut_10

Generic exception prose only; rejection class, boundary and result behavior unchanged.

```diff
# custom_components.heima.v3.storage.clock_gaps.x_clock_gap_observation_coverage__mutmut_10: survived
--- custom_components/heima/v3/storage/clock_gaps.py
+++ custom_components/heima/v3/storage/clock_gaps.py
@@ -9,7 +9,7 @@
     """
     requested = intersect_history_intervals(request, request)
     if not isinstance(durability, ClockGapDurability):
-        raise TypeError("Clock gap coverage requires explicit durability state")
+        raise TypeError("CLOCK GAP COVERAGE REQUIRES EXPLICIT DURABILITY STATE")
     state = ClockGapDurability(
         durability.gap_id,
         durability.gap,
```
