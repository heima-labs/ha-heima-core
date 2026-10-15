# Known observation gap clipping — mutation review, 2026-10-15

Fresh mutmut 3.8, native Python 3.14.5, only contracts/observation_gaps.py,
all tests/v3, seed3145, four children. **52 generated, 40 killed, 12 survived;
no timeout, error, skipped or untested.** Each surviving diff is shown below.
All twelve alter generic exception prose; exception types, validation boundaries
and result behavior are unchanged. There is no specified message-text contract.
No non-equivalent survivor was identified and no raw 100% score is claimed.

## Reproduction and limits

Copy current custom_components, tests, pytest-v3.ini and pyproject.toml to a fresh
temporary directory; narrow only_mutate there to observation_gaps.py and retain
all tests/v3 with seed3145. Use an empty mutants directory, then run:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_observation_gaps.py
```

Run evidence: /private/tmp/heima-v3-gap-clipping,
/private/tmp/heima-gap-clipping-mutmut.log. The permanent default scope adds the new
module to the previous fifteen; the scoped run does not claim fresh mutation results
for unchanged modules. Tests run against the instrumented copy under mutmut.

The function mutator does not alter the frozen dataclass declaration. Supplemental
mutation_observation_gaps.py first verifies a clean 58-test baseline, then removes
frozen=True and requires pytest exit1 in test_input_shapes_and_immutable_result.
That mutation was killed. An initial test collection failure due to a reserved pytest
parameter name was corrected before baseline validation; it is not mutation evidence.

## Individually inspected survivors

### xǁObservationGapǁ__post_init____mutmut_2

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.xǁObservationGapǁ__post_init____mutmut_2: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, HistoryInterval):
-        raise TypeError("Observation gap requires a HistoryInterval")
+        raise TypeError(None)
     # Reuse the authoritative geometry and closed-reason validators, including
     # reconstructed inputs; no second reason list or endpoint convention.
     intersect_history_intervals(self.interval, self.interval)
```

### xǁObservationGapǁ__post_init____mutmut_3

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.xǁObservationGapǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, HistoryInterval):
-        raise TypeError("Observation gap requires a HistoryInterval")
+        raise TypeError("XXObservation gap requires a HistoryIntervalXX")
     # Reuse the authoritative geometry and closed-reason validators, including
     # reconstructed inputs; no second reason list or endpoint convention.
     intersect_history_intervals(self.interval, self.interval)
```

### xǁObservationGapǁ__post_init____mutmut_4

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.xǁObservationGapǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, HistoryInterval):
-        raise TypeError("Observation gap requires a HistoryInterval")
+        raise TypeError("observation gap requires a historyinterval")
     # Reuse the authoritative geometry and closed-reason validators, including
     # reconstructed inputs; no second reason list or endpoint convention.
     intersect_history_intervals(self.interval, self.interval)
```

### xǁObservationGapǁ__post_init____mutmut_5

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.xǁObservationGapǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if not isinstance(self.interval, HistoryInterval):
-        raise TypeError("Observation gap requires a HistoryInterval")
+        raise TypeError("OBSERVATION GAP REQUIRES A HISTORYINTERVAL")
     # Reuse the authoritative geometry and closed-reason validators, including
     # reconstructed inputs; no second reason list or endpoint convention.
     intersect_history_intervals(self.interval, self.interval)
```

### x_clip_observation_gaps__mutmut_8

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_8: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -11,7 +11,7 @@
     """
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError(None)
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
```

### x_clip_observation_gaps__mutmut_9

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_9: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -11,7 +11,7 @@
     """
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError("XXObservation gaps must be an immutable tupleXX")
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
```

### x_clip_observation_gaps__mutmut_10

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_10: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -11,7 +11,7 @@
     """
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError("observation gaps must be an immutable tuple")
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
```

### x_clip_observation_gaps__mutmut_11

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_11: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -11,7 +11,7 @@
     """
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError("OBSERVATION GAPS MUST BE AN IMMUTABLE TUPLE")
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
```

### x_clip_observation_gaps__mutmut_14

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_14: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -15,7 +15,7 @@
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError(None)
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```

### x_clip_observation_gaps__mutmut_15

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_15: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -15,7 +15,7 @@
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError("XXClipping requires ObservationGap inputsXX")
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```

### x_clip_observation_gaps__mutmut_16

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_16: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -15,7 +15,7 @@
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError("clipping requires observationgap inputs")
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```

### x_clip_observation_gaps__mutmut_17

Generic TypeError prose only; validation and public result behavior unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_clip_observation_gaps__mutmut_17: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -15,7 +15,7 @@
     clipped = []
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError("CLIPPING REQUIRES OBSERVATIONGAP INPUTS")
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```
