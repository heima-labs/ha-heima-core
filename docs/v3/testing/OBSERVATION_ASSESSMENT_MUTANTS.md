# Observation coverage assessment — mutation review, 2026-10-15

Fresh mutmut 3.8, Python 3.14.5, only contracts/observation_gaps.py, all tests/v3,
seed3145, four children: **110 generated, 94 killed, 16 survived; zero timeout,
error, skipped or untested.** All sixteen diffs are inspected below: generic
TypeError message changes with unchanged validation classes/boundaries/results.
No behavioral survivor identified; no raw 100% score claimed.

## Reproduction and scope limits

Use a fresh temporary copy of current source/tests, pytest-v3.ini and pyproject.toml.
Narrow only_mutate there to observation_gaps.py, retain all tests/v3 with seed3145,
then run with an empty mutants directory:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_observation_gaps.py
```

Run path /private/tmp/heima-v3-coverage-assessment, log
/private/tmp/heima-assessment-mutmut.log. All ordinary function bodies, including the
shared generator and assessment, are in scope; there are no new property bodies or
module constants. The frozen declaration is outside mutmut's function scope: the
existing supplemental runner passed its clean 58-clipping-test baseline and killed
decorator removal in test_input_shapes_and_immutable_result (pytest exit1).

The final post-run edits only clarify docstrings/comments, without changing tested
executable expressions. The repository's default scope remains sixteen modules;
scoped evidence is not a fresh mutation result for unchanged modules.

## Individually inspected survivors

### xǁObservationGapǁ__post_init____mutmut_2

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

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

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

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

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

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

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

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

### x_assess_observation_coverage__mutmut_3

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_assess_observation_coverage__mutmut_3: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -13,7 +13,7 @@
     producer; they must not be omitted to obtain an optimistic complete result.
     """
     if type(metadata_trustworthy) is not bool:
-        raise TypeError("Continuity metadata trust must be boolean")
+        raise TypeError(None)
     reasons: set[ObservationGapReason] = set()
     first = None
     for gap, overlap in _gap_intersections(request, gaps):
```

### x_assess_observation_coverage__mutmut_4

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_assess_observation_coverage__mutmut_4: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -13,7 +13,7 @@
     producer; they must not be omitted to obtain an optimistic complete result.
     """
     if type(metadata_trustworthy) is not bool:
-        raise TypeError("Continuity metadata trust must be boolean")
+        raise TypeError("XXContinuity metadata trust must be booleanXX")
     reasons: set[ObservationGapReason] = set()
     first = None
     for gap, overlap in _gap_intersections(request, gaps):
```

### x_assess_observation_coverage__mutmut_5

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_assess_observation_coverage__mutmut_5: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -13,7 +13,7 @@
     producer; they must not be omitted to obtain an optimistic complete result.
     """
     if type(metadata_trustworthy) is not bool:
-        raise TypeError("Continuity metadata trust must be boolean")
+        raise TypeError("continuity metadata trust must be boolean")
     reasons: set[ObservationGapReason] = set()
     first = None
     for gap, overlap in _gap_intersections(request, gaps):
```

### x_assess_observation_coverage__mutmut_6

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x_assess_observation_coverage__mutmut_6: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -13,7 +13,7 @@
     producer; they must not be omitted to obtain an optimistic complete result.
     """
     if type(metadata_trustworthy) is not bool:
-        raise TypeError("Continuity metadata trust must be boolean")
+        raise TypeError("CONTINUITY METADATA TRUST MUST BE BOOLEAN")
     reasons: set[ObservationGapReason] = set()
     first = None
     for gap, overlap in _gap_intersections(request, gaps):
```

### x__gap_intersections__mutmut_8

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_8: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -4,7 +4,7 @@
     """Retain the original opening for §4.4's already-open-gap boundary rule."""
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError(None)
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
             raise TypeError("Clipping requires ObservationGap inputs")
```

### x__gap_intersections__mutmut_9

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_9: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -4,7 +4,7 @@
     """Retain the original opening for §4.4's already-open-gap boundary rule."""
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError("XXObservation gaps must be an immutable tupleXX")
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
             raise TypeError("Clipping requires ObservationGap inputs")
```

### x__gap_intersections__mutmut_10

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_10: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -4,7 +4,7 @@
     """Retain the original opening for §4.4's already-open-gap boundary rule."""
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError("observation gaps must be an immutable tuple")
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
             raise TypeError("Clipping requires ObservationGap inputs")
```

### x__gap_intersections__mutmut_11

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_11: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -4,7 +4,7 @@
     """Retain the original opening for §4.4's already-open-gap boundary rule."""
     request_intersection = intersect_history_intervals(request, request)
     if type(gaps) is not tuple:
-        raise TypeError("Observation gaps must be an immutable tuple")
+        raise TypeError("OBSERVATION GAPS MUST BE AN IMMUTABLE TUPLE")
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
             raise TypeError("Clipping requires ObservationGap inputs")
```

### x__gap_intersections__mutmut_13

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_13: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation gaps must be an immutable tuple")
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError(None)
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```

### x__gap_intersections__mutmut_14

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_14: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation gaps must be an immutable tuple")
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError("XXClipping requires ObservationGap inputsXX")
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```

### x__gap_intersections__mutmut_15

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_15: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation gaps must be an immutable tuple")
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError("clipping requires observationgap inputs")
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```

### x__gap_intersections__mutmut_16

Generic TypeError prose only; no specified message contract changes. Rejection and state/results are unchanged.

```diff
# custom_components.heima.v3.contracts.observation_gaps.x__gap_intersections__mutmut_16: survived
--- custom_components/heima/v3/contracts/observation_gaps.py
+++ custom_components/heima/v3/contracts/observation_gaps.py
@@ -7,7 +7,7 @@
         raise TypeError("Observation gaps must be an immutable tuple")
     for gap in gaps:
         if not isinstance(gap, ObservationGap):
-            raise TypeError("Clipping requires ObservationGap inputs")
+            raise TypeError("CLIPPING REQUIRES OBSERVATIONGAP INPUTS")
         validated = ObservationGap(gap.interval, gap.reason)
         if request_intersection is not None:
             overlap = intersect_history_intervals(request_intersection, validated.interval)
```
