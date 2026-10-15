# Continuity prefix accounting — mutation review, 2026-10-15

Fresh mutmut 3.8, Python 3.14.5, only storage/continuity_accounting.py, all tests/v3,
seed3145, four children: **138 generated, 97 killed, 41 survived; zero timeout,
error, skipped or untested.** Forty survivors alter generic exception prose; one
is equivalent because the subsequent empty-intersection guard handles equality.
All diffs and individual assessments appear below. No raw 100% score claimed.

Initial run: 96 killed,42 survivors. One behavioral survivor replaced continue by
break for an empty clipped range, skipping validation of later malformed snapshot
entries. Added test_empty_straddling_range_does_not_skip_validation_of_later_snapshot_entries
and reran from a new mutants directory. That mutant is now killed.

During initial implementation the generated property independently found a real bug:
a pending range straddling an already-proved barrier was treated as a new obligation.
Two literal regression instances failed before the clipping fix, two resolved-outcome
instances passed. The fix excludes empty (previous,target] intersections while still
validating the entire supplied snapshot. This was a development bug, not a defect
claimed in the previous committed implementation, which had no accounting module.

## Reproduction and limits

Use a fresh temporary source/tests copy with pytest-v3.ini and pyproject.toml. Narrow
only_mutate to storage/continuity_accounting.py there and retain all tests/v3 seed3145.
Start with an empty mutants directory:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_continuity_accounting.py
```

Run path /private/tmp/heima-v3-continuity-accounting; final log
/private/tmp/heima-accounting-mutmut-final.log. Default repository scope adds this
module to the prior seventeen; the scoped result is not a fresh run of unchanged
modules. New executable function bodies are in scope. There are no new properties
or module constants excluded by the tool. Frozen declarations are supplemented:
clean 66-test baseline, then each mutable declaration must produce pytest exit1 in
test_snapshot_types_are_immutable_and_revalidated. Both were killed.

## Individually inspected survivors

### x__sequence__mutmut_3

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_3: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -1,5 +1,5 @@
 def _sequence(value: int, minimum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Accounting sequence must be a non-boolean integer")
+        raise TypeError(None)
     if value < minimum:
         raise ValueError("Accounting sequence is below its minimum")
```

### x__sequence__mutmut_4

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_4: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -1,5 +1,5 @@
 def _sequence(value: int, minimum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Accounting sequence must be a non-boolean integer")
+        raise TypeError("XXAccounting sequence must be a non-boolean integerXX")
     if value < minimum:
         raise ValueError("Accounting sequence is below its minimum")
```

### x__sequence__mutmut_5

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_5: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -1,5 +1,5 @@
 def _sequence(value: int, minimum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Accounting sequence must be a non-boolean integer")
+        raise TypeError("accounting sequence must be a non-boolean integer")
     if value < minimum:
         raise ValueError("Accounting sequence is below its minimum")
```

### x__sequence__mutmut_6

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_6: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -1,5 +1,5 @@
 def _sequence(value: int, minimum: int) -> None:
     if type(value) is not int:
-        raise TypeError("Accounting sequence must be a non-boolean integer")
+        raise TypeError("ACCOUNTING SEQUENCE MUST BE A NON-BOOLEAN INTEGER")
     if value < minimum:
         raise ValueError("Accounting sequence is below its minimum")
```

### x__sequence__mutmut_8

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_8: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Accounting sequence must be a non-boolean integer")
     if value < minimum:
-        raise ValueError("Accounting sequence is below its minimum")
+        raise ValueError(None)
```

### x__sequence__mutmut_9

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_9: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Accounting sequence must be a non-boolean integer")
     if value < minimum:
-        raise ValueError("Accounting sequence is below its minimum")
+        raise ValueError("XXAccounting sequence is below its minimumXX")
```

### x__sequence__mutmut_10

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_10: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Accounting sequence must be a non-boolean integer")
     if value < minimum:
-        raise ValueError("Accounting sequence is below its minimum")
+        raise ValueError("accounting sequence is below its minimum")
```

### x__sequence__mutmut_11

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x__sequence__mutmut_11: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,4 +2,4 @@
     if type(value) is not int:
         raise TypeError("Accounting sequence must be a non-boolean integer")
     if value < minimum:
-        raise ValueError("Accounting sequence is below its minimum")
+        raise ValueError("ACCOUNTING SEQUENCE IS BELOW ITS MINIMUM")
```

### xǁDurabilityRangeǁ__post_init____mutmut_12

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,6 +2,6 @@
     _sequence(self.first_sequence, 1)
     _sequence(self.last_sequence, self.first_sequence)
     if type(self.outcome) is not str:
-        raise TypeError("Durability outcome must be text")
+        raise TypeError(None)
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
         raise ValueError("Unknown durability outcome")
```

### xǁDurabilityRangeǁ__post_init____mutmut_13

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_13: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,6 +2,6 @@
     _sequence(self.first_sequence, 1)
     _sequence(self.last_sequence, self.first_sequence)
     if type(self.outcome) is not str:
-        raise TypeError("Durability outcome must be text")
+        raise TypeError("XXDurability outcome must be textXX")
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
         raise ValueError("Unknown durability outcome")
```

### xǁDurabilityRangeǁ__post_init____mutmut_14

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_14: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,6 +2,6 @@
     _sequence(self.first_sequence, 1)
     _sequence(self.last_sequence, self.first_sequence)
     if type(self.outcome) is not str:
-        raise TypeError("Durability outcome must be text")
+        raise TypeError("durability outcome must be text")
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
         raise ValueError("Unknown durability outcome")
```

### xǁDurabilityRangeǁ__post_init____mutmut_15

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_15: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -2,6 +2,6 @@
     _sequence(self.first_sequence, 1)
     _sequence(self.last_sequence, self.first_sequence)
     if type(self.outcome) is not str:
-        raise TypeError("Durability outcome must be text")
+        raise TypeError("DURABILITY OUTCOME MUST BE TEXT")
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
         raise ValueError("Unknown durability outcome")
```

### xǁDurabilityRangeǁ__post_init____mutmut_25

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_25: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -4,4 +4,4 @@
     if type(self.outcome) is not str:
         raise TypeError("Durability outcome must be text")
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
-        raise ValueError("Unknown durability outcome")
+        raise ValueError(None)
```

### xǁDurabilityRangeǁ__post_init____mutmut_26

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_26: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -4,4 +4,4 @@
     if type(self.outcome) is not str:
         raise TypeError("Durability outcome must be text")
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
-        raise ValueError("Unknown durability outcome")
+        raise ValueError("XXUnknown durability outcomeXX")
```

### xǁDurabilityRangeǁ__post_init____mutmut_27

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_27: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -4,4 +4,4 @@
     if type(self.outcome) is not str:
         raise TypeError("Durability outcome must be text")
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
-        raise ValueError("Unknown durability outcome")
+        raise ValueError("unknown durability outcome")
```

### xǁDurabilityRangeǁ__post_init____mutmut_28

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.xǁDurabilityRangeǁ__post_init____mutmut_28: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -4,4 +4,4 @@
     if type(self.outcome) is not str:
         raise TypeError("Durability outcome must be text")
     if self.outcome not in ("pending", "written", "loss_pending", "loss_declared"):
-        raise ValueError("Unknown durability outcome")
+        raise ValueError("UNKNOWN DURABILITY OUTCOME")
```

### x_continuity_barrier_accounted__mutmut_2

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_2: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -16,7 +16,7 @@
     overall observation coverage and global-overflow closure remain separate checks.
     """
     if not isinstance(barrier, ContinuityAccountingBarrier):
-        raise TypeError("Accounting requires a continuity barrier")
+        raise TypeError(None)
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
```

### x_continuity_barrier_accounted__mutmut_3

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_3: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -16,7 +16,7 @@
     overall observation coverage and global-overflow closure remain separate checks.
     """
     if not isinstance(barrier, ContinuityAccountingBarrier):
-        raise TypeError("Accounting requires a continuity barrier")
+        raise TypeError("XXAccounting requires a continuity barrierXX")
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
```

### x_continuity_barrier_accounted__mutmut_4

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_4: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -16,7 +16,7 @@
     overall observation coverage and global-overflow closure remain separate checks.
     """
     if not isinstance(barrier, ContinuityAccountingBarrier):
-        raise TypeError("Accounting requires a continuity barrier")
+        raise TypeError("accounting requires a continuity barrier")
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
```

### x_continuity_barrier_accounted__mutmut_5

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_5: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -16,7 +16,7 @@
     overall observation coverage and global-overflow closure remain separate checks.
     """
     if not isinstance(barrier, ContinuityAccountingBarrier):
-        raise TypeError("Accounting requires a continuity barrier")
+        raise TypeError("ACCOUNTING REQUIRES A CONTINUITY BARRIER")
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
```

### x_continuity_barrier_accounted__mutmut_17

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_17: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -20,7 +20,7 @@
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
-        raise ValueError("Previous accounting prefix exceeds the chosen barrier")
+        raise ValueError(None)
     if type(inventory_complete) is not bool:
         raise TypeError("Accounting inventory completeness must be boolean")
     if producer_blocked_at is not None:
```

### x_continuity_barrier_accounted__mutmut_18

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_18: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -20,7 +20,7 @@
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
-        raise ValueError("Previous accounting prefix exceeds the chosen barrier")
+        raise ValueError("XXPrevious accounting prefix exceeds the chosen barrierXX")
     if type(inventory_complete) is not bool:
         raise TypeError("Accounting inventory completeness must be boolean")
     if producer_blocked_at is not None:
```

### x_continuity_barrier_accounted__mutmut_19

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_19: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -20,7 +20,7 @@
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
-        raise ValueError("Previous accounting prefix exceeds the chosen barrier")
+        raise ValueError("previous accounting prefix exceeds the chosen barrier")
     if type(inventory_complete) is not bool:
         raise TypeError("Accounting inventory completeness must be boolean")
     if producer_blocked_at is not None:
```

### x_continuity_barrier_accounted__mutmut_20

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_20: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -20,7 +20,7 @@
     barrier = ContinuityAccountingBarrier(barrier.through_sequence, barrier.observed_at)
     _sequence(previously_accounted_through, 0)
     if previously_accounted_through > barrier.through_sequence:
-        raise ValueError("Previous accounting prefix exceeds the chosen barrier")
+        raise ValueError("PREVIOUS ACCOUNTING PREFIX EXCEEDS THE CHOSEN BARRIER")
     if type(inventory_complete) is not bool:
         raise TypeError("Accounting inventory completeness must be boolean")
     if producer_blocked_at is not None:
```

### x_continuity_barrier_accounted__mutmut_23

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_23: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -22,7 +22,7 @@
     if previously_accounted_through > barrier.through_sequence:
         raise ValueError("Previous accounting prefix exceeds the chosen barrier")
     if type(inventory_complete) is not bool:
-        raise TypeError("Accounting inventory completeness must be boolean")
+        raise TypeError(None)
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
```

### x_continuity_barrier_accounted__mutmut_24

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_24: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -22,7 +22,7 @@
     if previously_accounted_through > barrier.through_sequence:
         raise ValueError("Previous accounting prefix exceeds the chosen barrier")
     if type(inventory_complete) is not bool:
-        raise TypeError("Accounting inventory completeness must be boolean")
+        raise TypeError("XXAccounting inventory completeness must be booleanXX")
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
```

### x_continuity_barrier_accounted__mutmut_25

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_25: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -22,7 +22,7 @@
     if previously_accounted_through > barrier.through_sequence:
         raise ValueError("Previous accounting prefix exceeds the chosen barrier")
     if type(inventory_complete) is not bool:
-        raise TypeError("Accounting inventory completeness must be boolean")
+        raise TypeError("accounting inventory completeness must be boolean")
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
```

### x_continuity_barrier_accounted__mutmut_26

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_26: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -22,7 +22,7 @@
     if previously_accounted_through > barrier.through_sequence:
         raise ValueError("Previous accounting prefix exceeds the chosen barrier")
     if type(inventory_complete) is not bool:
-        raise TypeError("Accounting inventory completeness must be boolean")
+        raise TypeError("ACCOUNTING INVENTORY COMPLETENESS MUST BE BOOLEAN")
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
```

### x_continuity_barrier_accounted__mutmut_31

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_31: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -26,7 +26,7 @@
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
-        raise TypeError("Accounting ranges must be an immutable tuple")
+        raise TypeError(None)
     ready = inventory_complete
     if producer_blocked_at is not None:
         if producer_blocked_at <= barrier.observed_at:
```

### x_continuity_barrier_accounted__mutmut_32

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_32: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -26,7 +26,7 @@
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
-        raise TypeError("Accounting ranges must be an immutable tuple")
+        raise TypeError("XXAccounting ranges must be an immutable tupleXX")
     ready = inventory_complete
     if producer_blocked_at is not None:
         if producer_blocked_at <= barrier.observed_at:
```

### x_continuity_barrier_accounted__mutmut_33

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_33: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -26,7 +26,7 @@
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
-        raise TypeError("Accounting ranges must be an immutable tuple")
+        raise TypeError("accounting ranges must be an immutable tuple")
     ready = inventory_complete
     if producer_blocked_at is not None:
         if producer_blocked_at <= barrier.observed_at:
```

### x_continuity_barrier_accounted__mutmut_34

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_34: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -26,7 +26,7 @@
     if producer_blocked_at is not None:
         parse_instant(producer_blocked_at)
     if type(ranges) is not tuple:
-        raise TypeError("Accounting ranges must be an immutable tuple")
+        raise TypeError("ACCOUNTING RANGES MUST BE AN IMMUTABLE TUPLE")
     ready = inventory_complete
     if producer_blocked_at is not None:
         if producer_blocked_at <= barrier.observed_at:
```

### x_continuity_barrier_accounted__mutmut_44

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_44: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -35,7 +35,7 @@
     previous_end = 0
     for item in ranges:
         if not isinstance(item, DurabilityRange):
-            raise TypeError("Accounting requires DurabilityRange inputs")
+            raise TypeError(None)
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
             raise ValueError("Accounting ranges must be ordered and disjoint")
```

### x_continuity_barrier_accounted__mutmut_45

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_45: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -35,7 +35,7 @@
     previous_end = 0
     for item in ranges:
         if not isinstance(item, DurabilityRange):
-            raise TypeError("Accounting requires DurabilityRange inputs")
+            raise TypeError("XXAccounting requires DurabilityRange inputsXX")
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
             raise ValueError("Accounting ranges must be ordered and disjoint")
```

### x_continuity_barrier_accounted__mutmut_46

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_46: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -35,7 +35,7 @@
     previous_end = 0
     for item in ranges:
         if not isinstance(item, DurabilityRange):
-            raise TypeError("Accounting requires DurabilityRange inputs")
+            raise TypeError("accounting requires durabilityrange inputs")
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
             raise ValueError("Accounting ranges must be ordered and disjoint")
```

### x_continuity_barrier_accounted__mutmut_47

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_47: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -35,7 +35,7 @@
     previous_end = 0
     for item in ranges:
         if not isinstance(item, DurabilityRange):
-            raise TypeError("Accounting requires DurabilityRange inputs")
+            raise TypeError("ACCOUNTING REQUIRES DURABILITYRANGE INPUTS")
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
             raise ValueError("Accounting ranges must be ordered and disjoint")
```

### x_continuity_barrier_accounted__mutmut_56

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_56: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -38,7 +38,7 @@
             raise TypeError("Accounting requires DurabilityRange inputs")
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
-            raise ValueError("Accounting ranges must be ordered and disjoint")
+            raise ValueError(None)
         previous_end = interval.last_sequence
         if interval.last_sequence <= previously_accounted_through:
             continue
```

### x_continuity_barrier_accounted__mutmut_57

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_57: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -38,7 +38,7 @@
             raise TypeError("Accounting requires DurabilityRange inputs")
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
-            raise ValueError("Accounting ranges must be ordered and disjoint")
+            raise ValueError("XXAccounting ranges must be ordered and disjointXX")
         previous_end = interval.last_sequence
         if interval.last_sequence <= previously_accounted_through:
             continue
```

### x_continuity_barrier_accounted__mutmut_58

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_58: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -38,7 +38,7 @@
             raise TypeError("Accounting requires DurabilityRange inputs")
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
-            raise ValueError("Accounting ranges must be ordered and disjoint")
+            raise ValueError("accounting ranges must be ordered and disjoint")
         previous_end = interval.last_sequence
         if interval.last_sequence <= previously_accounted_through:
             continue
```

### x_continuity_barrier_accounted__mutmut_59

Generic exception prose only; there is no message-text contract. Rejection class, boundary and observable accounting result are unchanged.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_59: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -38,7 +38,7 @@
             raise TypeError("Accounting requires DurabilityRange inputs")
         interval = DurabilityRange(item.first_sequence, item.last_sequence, item.outcome)
         if interval.first_sequence <= previous_end:
-            raise ValueError("Accounting ranges must be ordered and disjoint")
+            raise ValueError("ACCOUNTING RANGES MUST BE ORDERED AND DISJOINT")
         previous_end = interval.last_sequence
         if interval.last_sequence <= previously_accounted_through:
             continue
```

### x_continuity_barrier_accounted__mutmut_61

Equivalent fast-path boundary. If last==previous, the clipped start is at least previous+1 while end is at most previous. The later end<start guard therefore continues identically. Validation and previous_end assignment occur before either path, so no invalid evidence is hidden.

```diff
# custom_components.heima.v3.storage.continuity_accounting.x_continuity_barrier_accounted__mutmut_61: survived
--- custom_components/heima/v3/storage/continuity_accounting.py
+++ custom_components/heima/v3/storage/continuity_accounting.py
@@ -40,7 +40,7 @@
         if interval.first_sequence <= previous_end:
             raise ValueError("Accounting ranges must be ordered and disjoint")
         previous_end = interval.last_sequence
-        if interval.last_sequence <= previously_accounted_through:
+        if interval.last_sequence < previously_accounted_through:
             continue
         if interval.first_sequence > barrier.through_sequence:
             continue
```
