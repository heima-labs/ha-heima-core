# Observation coverage mutation review — 2026-10-15

Fresh mutmut 3.8, observation.py only, whole V3 suite with seed3145.
115 generated, 67 killed, 48 survived; no timeout/error/skipped.
All survivors change generic exception prose: 40 constructor, 4 composition tuple
shape, 4 input record type. They preserve rejection types and observable coverage
semantics; those human-readable strings are not stable diagnostic codes. No known
behavioral survivor. No score threshold introduced.

Supplement mutation_observation.py: baseline passes and kills frozen-record removal,
dropping process_interruption from closed reasons, and adding made_up. An initial
queue_overflow-removal probe caused eager test fixture collection failure; it is
NOT counted as a behavioral kill. The final target reaches the per-reason assertion
at execution time and must exit 1 in the expected named test.

## Exact surviving mutation diffs

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.status) is not str:
-        raise TypeError("Observation status must be text")
+        raise TypeError(None)
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.status) is not str:
-        raise TypeError("Observation status must be text")
+        raise TypeError("XXObservation status must be textXX")
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.status) is not str:
-        raise TypeError("Observation status must be text")
+        raise TypeError("observation status must be text")
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.status) is not str:
-        raise TypeError("Observation status must be text")
+        raise TypeError("OBSERVATION STATUS MUST BE TEXT")
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -2,7 +2,7 @@
     if type(self.status) is not str:
         raise TypeError("Observation status must be text")
     if self.status not in ("complete", "incomplete"):
-        raise ValueError("Unknown observation status")
+        raise ValueError(None)
     if type(self.reasons) is not tuple:
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_13: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -2,7 +2,7 @@
     if type(self.status) is not str:
         raise TypeError("Observation status must be text")
     if self.status not in ("complete", "incomplete"):
-        raise ValueError("Unknown observation status")
+        raise ValueError("XXUnknown observation statusXX")
     if type(self.reasons) is not tuple:
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_14: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -2,7 +2,7 @@
     if type(self.status) is not str:
         raise TypeError("Observation status must be text")
     if self.status not in ("complete", "incomplete"):
-        raise ValueError("Unknown observation status")
+        raise ValueError("unknown observation status")
     if type(self.reasons) is not tuple:
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_15: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -2,7 +2,7 @@
     if type(self.status) is not str:
         raise TypeError("Observation status must be text")
     if self.status not in ("complete", "incomplete"):
-        raise ValueError("Unknown observation status")
+        raise ValueError("UNKNOWN OBSERVATION STATUS")
     if type(self.reasons) is not tuple:
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_18: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -4,7 +4,7 @@
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
-        raise TypeError("Observation reasons must be an immutable tuple")
+        raise TypeError(None)
     for reason in self.reasons:
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_19: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -4,7 +4,7 @@
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
-        raise TypeError("Observation reasons must be an immutable tuple")
+        raise TypeError("XXObservation reasons must be an immutable tupleXX")
     for reason in self.reasons:
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_20: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -4,7 +4,7 @@
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
-        raise TypeError("Observation reasons must be an immutable tuple")
+        raise TypeError("observation reasons must be an immutable tuple")
     for reason in self.reasons:
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_21: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -4,7 +4,7 @@
     if self.status not in ("complete", "incomplete"):
         raise ValueError("Unknown observation status")
     if type(self.reasons) is not tuple:
-        raise TypeError("Observation reasons must be an immutable tuple")
+        raise TypeError("OBSERVATION REASONS MUST BE AN IMMUTABLE TUPLE")
     for reason in self.reasons:
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_24: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
         if type(reason) is not str:
-            raise TypeError("Observation reason must be text")
+            raise TypeError(None)
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_25: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
         if type(reason) is not str:
-            raise TypeError("Observation reason must be text")
+            raise TypeError("XXObservation reason must be textXX")
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_26: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
         if type(reason) is not str:
-            raise TypeError("Observation reason must be text")
+            raise TypeError("observation reason must be text")
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_27: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation reasons must be an immutable tuple")
     for reason in self.reasons:
         if type(reason) is not str:
-            raise TypeError("Observation reason must be text")
+            raise TypeError("OBSERVATION REASON MUST BE TEXT")
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_29: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
         if reason not in _GAP_REASONS:
-            raise ValueError("Unknown observation gap reason")
+            raise ValueError(None)
     if tuple(sorted(set(self.reasons))) != self.reasons:
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_30: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
         if reason not in _GAP_REASONS:
-            raise ValueError("Unknown observation gap reason")
+            raise ValueError("XXUnknown observation gap reasonXX")
     if tuple(sorted(set(self.reasons))) != self.reasons:
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_31: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
         if reason not in _GAP_REASONS:
-            raise ValueError("Unknown observation gap reason")
+            raise ValueError("unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_32: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
         if type(reason) is not str:
             raise TypeError("Observation reason must be text")
         if reason not in _GAP_REASONS:
-            raise ValueError("Unknown observation gap reason")
+            raise ValueError("UNKNOWN OBSERVATION GAP REASON")
     if tuple(sorted(set(self.reasons))) != self.reasons:
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_37: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -11,7 +11,7 @@
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
-        raise ValueError("Observation reasons must be distinct and ASCII-sorted")
+        raise ValueError(None)
     if self.status == "complete":
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_38: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -11,7 +11,7 @@
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
-        raise ValueError("Observation reasons must be distinct and ASCII-sorted")
+        raise ValueError("XXObservation reasons must be distinct and ASCII-sortedXX")
     if self.status == "complete":
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_39: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -11,7 +11,7 @@
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
-        raise ValueError("Observation reasons must be distinct and ASCII-sorted")
+        raise ValueError("observation reasons must be distinct and ascii-sorted")
     if self.status == "complete":
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_40: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -11,7 +11,7 @@
         if reason not in _GAP_REASONS:
             raise ValueError("Unknown observation gap reason")
     if tuple(sorted(set(self.reasons))) != self.reasons:
-        raise ValueError("Observation reasons must be distinct and ASCII-sorted")
+        raise ValueError("OBSERVATION REASONS MUST BE DISTINCT AND ASCII-SORTED")
     if self.status == "complete":
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_44: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -14,7 +14,7 @@
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
         if self.reasons:
-            raise ValueError("Complete observation cannot have gap reasons")
+            raise ValueError(None)
         if self.first_incomplete_at is not None:
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_45: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -14,7 +14,7 @@
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
         if self.reasons:
-            raise ValueError("Complete observation cannot have gap reasons")
+            raise ValueError("XXComplete observation cannot have gap reasonsXX")
         if self.first_incomplete_at is not None:
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_46: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -14,7 +14,7 @@
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
         if self.reasons:
-            raise ValueError("Complete observation cannot have gap reasons")
+            raise ValueError("complete observation cannot have gap reasons")
         if self.first_incomplete_at is not None:
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_47: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -14,7 +14,7 @@
         raise ValueError("Observation reasons must be distinct and ASCII-sorted")
     if self.status == "complete":
         if self.reasons:
-            raise ValueError("Complete observation cannot have gap reasons")
+            raise ValueError("COMPLETE OBSERVATION CANNOT HAVE GAP REASONS")
         if self.first_incomplete_at is not None:
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_49: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -16,7 +16,7 @@
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
         if self.first_incomplete_at is not None:
-            raise ValueError("Complete observation cannot have an incomplete instant")
+            raise ValueError(None)
     else:
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_50: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -16,7 +16,7 @@
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
         if self.first_incomplete_at is not None:
-            raise ValueError("Complete observation cannot have an incomplete instant")
+            raise ValueError("XXComplete observation cannot have an incomplete instantXX")
     else:
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_51: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -16,7 +16,7 @@
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
         if self.first_incomplete_at is not None:
-            raise ValueError("Complete observation cannot have an incomplete instant")
+            raise ValueError("complete observation cannot have an incomplete instant")
     else:
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_52: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -16,7 +16,7 @@
         if self.reasons:
             raise ValueError("Complete observation cannot have gap reasons")
         if self.first_incomplete_at is not None:
-            raise ValueError("Complete observation cannot have an incomplete instant")
+            raise ValueError("COMPLETE OBSERVATION CANNOT HAVE AN INCOMPLETE INSTANT")
     else:
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_54: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -19,7 +19,7 @@
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
         if not self.reasons:
-            raise ValueError("Incomplete observation requires a gap reason")
+            raise ValueError(None)
         if self.first_incomplete_at is None:
             raise ValueError("Incomplete observation requires its first missing instant")
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_55: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -19,7 +19,7 @@
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
         if not self.reasons:
-            raise ValueError("Incomplete observation requires a gap reason")
+            raise ValueError("XXIncomplete observation requires a gap reasonXX")
         if self.first_incomplete_at is None:
             raise ValueError("Incomplete observation requires its first missing instant")
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_56: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -19,7 +19,7 @@
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
         if not self.reasons:
-            raise ValueError("Incomplete observation requires a gap reason")
+            raise ValueError("incomplete observation requires a gap reason")
         if self.first_incomplete_at is None:
             raise ValueError("Incomplete observation requires its first missing instant")
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_57: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -19,7 +19,7 @@
             raise ValueError("Complete observation cannot have an incomplete instant")
     else:
         if not self.reasons:
-            raise ValueError("Incomplete observation requires a gap reason")
+            raise ValueError("INCOMPLETE OBSERVATION REQUIRES A GAP REASON")
         if self.first_incomplete_at is None:
             raise ValueError("Incomplete observation requires its first missing instant")
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_59: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -21,5 +21,5 @@
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
         if self.first_incomplete_at is None:
-            raise ValueError("Incomplete observation requires its first missing instant")
+            raise ValueError(None)
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_60: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -21,5 +21,5 @@
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
         if self.first_incomplete_at is None:
-            raise ValueError("Incomplete observation requires its first missing instant")
+            raise ValueError("XXIncomplete observation requires its first missing instantXX")
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_61: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -21,5 +21,5 @@
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
         if self.first_incomplete_at is None:
-            raise ValueError("Incomplete observation requires its first missing instant")
+            raise ValueError("incomplete observation requires its first missing instant")
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.xǁObservationCoverageǁ__post_init____mutmut_62: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -21,5 +21,5 @@
         if not self.reasons:
             raise ValueError("Incomplete observation requires a gap reason")
         if self.first_incomplete_at is None:
-            raise ValueError("Incomplete observation requires its first missing instant")
+            raise ValueError("INCOMPLETE OBSERVATION REQUIRES ITS FIRST MISSING INSTANT")
         parse_instant(self.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.x_combine_observation_coverage__mutmut_5: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
     """
     process = _validated_coverage(process)
     if type(required_streams) is not tuple:
-        raise TypeError("Required-stream coverage must be an immutable tuple")
+        raise TypeError(None)
     reasons = set(process.reasons)
     first = process.first_incomplete_at
     for stream in required_streams:
```

```diff
# custom_components.heima.v3.contracts.observation.x_combine_observation_coverage__mutmut_6: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
     """
     process = _validated_coverage(process)
     if type(required_streams) is not tuple:
-        raise TypeError("Required-stream coverage must be an immutable tuple")
+        raise TypeError("XXRequired-stream coverage must be an immutable tupleXX")
     reasons = set(process.reasons)
     first = process.first_incomplete_at
     for stream in required_streams:
```

```diff
# custom_components.heima.v3.contracts.observation.x_combine_observation_coverage__mutmut_7: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
     """
     process = _validated_coverage(process)
     if type(required_streams) is not tuple:
-        raise TypeError("Required-stream coverage must be an immutable tuple")
+        raise TypeError("required-stream coverage must be an immutable tuple")
     reasons = set(process.reasons)
     first = process.first_incomplete_at
     for stream in required_streams:
```

```diff
# custom_components.heima.v3.contracts.observation.x_combine_observation_coverage__mutmut_8: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -9,7 +9,7 @@
     """
     process = _validated_coverage(process)
     if type(required_streams) is not tuple:
-        raise TypeError("Required-stream coverage must be an immutable tuple")
+        raise TypeError("REQUIRED-STREAM COVERAGE MUST BE AN IMMUTABLE TUPLE")
     reasons = set(process.reasons)
     first = process.first_incomplete_at
     for stream in required_streams:
```

```diff
# custom_components.heima.v3.contracts.observation.x__validated_coverage__mutmut_2: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,4 +1,4 @@
 def _validated_coverage(value: ObservationCoverage) -> ObservationCoverage:
     if not isinstance(value, ObservationCoverage):
-        raise TypeError("Coverage composition requires ObservationCoverage")
+        raise TypeError(None)
     return ObservationCoverage(value.status, value.reasons, value.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.x__validated_coverage__mutmut_3: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,4 +1,4 @@
 def _validated_coverage(value: ObservationCoverage) -> ObservationCoverage:
     if not isinstance(value, ObservationCoverage):
-        raise TypeError("Coverage composition requires ObservationCoverage")
+        raise TypeError("XXCoverage composition requires ObservationCoverageXX")
     return ObservationCoverage(value.status, value.reasons, value.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.x__validated_coverage__mutmut_4: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,4 +1,4 @@
 def _validated_coverage(value: ObservationCoverage) -> ObservationCoverage:
     if not isinstance(value, ObservationCoverage):
-        raise TypeError("Coverage composition requires ObservationCoverage")
+        raise TypeError("coverage composition requires observationcoverage")
     return ObservationCoverage(value.status, value.reasons, value.first_incomplete_at)
```

```diff
# custom_components.heima.v3.contracts.observation.x__validated_coverage__mutmut_5: survived
--- custom_components/heima/v3/contracts/observation.py
+++ custom_components/heima/v3/contracts/observation.py
@@ -1,4 +1,4 @@
 def _validated_coverage(value: ObservationCoverage) -> ObservationCoverage:
     if not isinstance(value, ObservationCoverage):
-        raise TypeError("Coverage composition requires ObservationCoverage")
+        raise TypeError("COVERAGE COMPOSITION REQUIRES OBSERVATIONCOVERAGE")
     return ObservationCoverage(value.status, value.reasons, value.first_incomplete_at)
```
