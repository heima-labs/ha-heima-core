# Source/Location critical review — mutation evidence, 2026-10-15

Fresh mutmut3.8/Python3.14.5, both changed modules contracts/location.py and
contracts/fact_sources.py, all tests/v3, seed3145, four children:
**339 generated,253 killed,86 survived; zero errors/timeouts/skipped/untested/
interrupted.** All86 inspected:84 generic exception-prose variants,1 equivalent
Location recovery guard widening,1 UTF-8 codec-name case variant. Source28 and
Location58 survivors. No raw100% score claim. Repository22-module default scope
is unchanged; this run refreshes only these two modules.

Re-ran existing supplements against current source:5 Location seeds (updated their
code anchors after centralizing identity),18 source frozen/slots/vocabulary/default
seeds. Added6 direct review seeds: virtual Location validation/encoding/equality/hash,
re-admitting extended runtime sources and re-admitting extended fingerprint sources.
All29 killed; clean baselines Location120,source172,combined292 focused instances.
Each seed selected its named behavioral test and required pytest exit1, not a
collection error or missing test selection. No application constants/decorator
logic silently omitted. Source and Location declaration flags retain explicit
supplementary coverage outside mutmut function scope.

Reproduce in a fresh source/tests copy with scoped pyproject only_mutate:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_location.py
.venv-v3/bin/python tests/v3/mutation_fact_sources.py
.venv-v3/bin/python tests/v3/mutation_source_location_review.py
```

Run /private/tmp/heima-v3-source-location-review/mutants; log
/private/tmp/heima-contract-review-mutmut.log. Temporary artifacts are supplementary;
exact survivor diffs and reasons follow. Core seven regression instances were shown
failing on committed0207174 before fixes; two new PBTs and full1252-test suite pass.
No validation here certifies a Python sandbox, actual HA authorization/redaction,
producer admission or throughput on ARM. Those are separate unimplemented boundaries.

## Individually inspected survivors

### x__text__mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__text__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -2,4 +2,4 @@
     if value is None and optional:
         return
     if type(value) is not str:
-        raise TypeError("Source fields require primitive strings")
+        raise TypeError(None)
```

### x__text__mutmut_7

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__text__mutmut_7: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -2,4 +2,4 @@
     if value is None and optional:
         return
     if type(value) is not str:
-        raise TypeError("Source fields require primitive strings")
+        raise TypeError("XXSource fields require primitive stringsXX")
```

### x__text__mutmut_8

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__text__mutmut_8: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -2,4 +2,4 @@
     if value is None and optional:
         return
     if type(value) is not str:
-        raise TypeError("Source fields require primitive strings")
+        raise TypeError("source fields require primitive strings")
```

### x__text__mutmut_9

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__text__mutmut_9: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -2,4 +2,4 @@
     if value is None and optional:
         return
     if type(value) is not str:
-        raise TypeError("Source fields require primitive strings")
+        raise TypeError("SOURCE FIELDS REQUIRE PRIMITIVE STRINGS")
```

### x__closed__mutmut_3

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__closed__mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,4 +1,4 @@
 def _closed(value: object, vocabulary: tuple[object, ...]) -> None:
     _text(value)
     if value not in vocabulary:
-        raise ValueError("Source vocabulary value is unknown")
+        raise ValueError(None)
```

### x__closed__mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__closed__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,4 +1,4 @@
 def _closed(value: object, vocabulary: tuple[object, ...]) -> None:
     _text(value)
     if value not in vocabulary:
-        raise ValueError("Source vocabulary value is unknown")
+        raise ValueError("XXSource vocabulary value is unknownXX")
```

### x__closed__mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__closed__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,4 +1,4 @@
 def _closed(value: object, vocabulary: tuple[object, ...]) -> None:
     _text(value)
     if value not in vocabulary:
-        raise ValueError("Source vocabulary value is unknown")
+        raise ValueError("source vocabulary value is unknown")
```

### x__closed__mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x__closed__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,4 +1,4 @@
 def _closed(value: object, vocabulary: tuple[object, ...]) -> None:
     _text(value)
     if value not in vocabulary:
-        raise ValueError("Source vocabulary value is unknown")
+        raise ValueError("SOURCE VOCABULARY VALUE IS UNKNOWN")
```

### x_fact_source_fingerprint__mutmut_3

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the concrete source shape; validate correlation, then exclude it."""
     if type(source) is not FactSource:
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError(None)
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_fact_source_fingerprint__mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the concrete source shape; validate correlation, then exclude it."""
     if type(source) is not FactSource:
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError("XXFact source fingerprint requires a FactSourceXX")
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_fact_source_fingerprint__mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the concrete source shape; validate correlation, then exclude it."""
     if type(source) is not FactSource:
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError("fact source fingerprint requires a factsource")
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_fact_source_fingerprint__mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the concrete source shape; validate correlation, then exclude it."""
     if type(source) is not FactSource:
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError("FACT SOURCE FINGERPRINT REQUIRES A FACTSOURCE")
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_validate_runtime_source_shape__mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -7,7 +7,7 @@
     from its verified boundary. Do not deserialize arbitrary source data as authority.
     """
     if type(test_mode) is not bool:
-        raise TypeError("Source validation mode must be boolean")
+        raise TypeError(None)
     if type(source) not in (FactSource, ApplyStepSource):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -7,7 +7,7 @@
     from its verified boundary. Do not deserialize arbitrary source data as authority.
     """
     if type(test_mode) is not bool:
-        raise TypeError("Source validation mode must be boolean")
+        raise TypeError("XXSource validation mode must be booleanXX")
     if type(source) not in (FactSource, ApplyStepSource):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -7,7 +7,7 @@
     from its verified boundary. Do not deserialize arbitrary source data as authority.
     """
     if type(test_mode) is not bool:
-        raise TypeError("Source validation mode must be boolean")
+        raise TypeError("source validation mode must be boolean")
     if type(source) not in (FactSource, ApplyStepSource):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_7

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_7: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -7,7 +7,7 @@
     from its verified boundary. Do not deserialize arbitrary source data as authority.
     """
     if type(test_mode) is not bool:
-        raise TypeError("Source validation mode must be boolean")
+        raise TypeError("SOURCE VALIDATION MODE MUST BE BOOLEAN")
     if type(source) not in (FactSource, ApplyStepSource):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_10

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_10: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if type(source) not in (FactSource, ApplyStepSource):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError(None)
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_11

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_11: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if type(source) not in (FactSource, ApplyStepSource):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError("XXRuntime source shape requires a typed sourceXX")
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_12

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_12: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if type(source) not in (FactSource, ApplyStepSource):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError("runtime source shape requires a typed source")
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_13

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_13: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if type(source) not in (FactSource, ApplyStepSource):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError("RUNTIME SOURCE SHAPE REQUIRES A TYPED SOURCE")
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_19

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_19: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -15,6 +15,6 @@
     else:
         ApplyStepSource.__post_init__(source)
     if source.kind == "legacy":
-        raise ValueError("Archive sources cannot enter the V3 runtime")
+        raise ValueError(None)
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
         raise ValueError("Test sources cannot enter production data")
```

### x_validate_runtime_source_shape__mutmut_20

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_20: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -15,6 +15,6 @@
     else:
         ApplyStepSource.__post_init__(source)
     if source.kind == "legacy":
-        raise ValueError("Archive sources cannot enter the V3 runtime")
+        raise ValueError("XXArchive sources cannot enter the V3 runtimeXX")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
         raise ValueError("Test sources cannot enter production data")
```

### x_validate_runtime_source_shape__mutmut_21

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_21: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -15,6 +15,6 @@
     else:
         ApplyStepSource.__post_init__(source)
     if source.kind == "legacy":
-        raise ValueError("Archive sources cannot enter the V3 runtime")
+        raise ValueError("archive sources cannot enter the v3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
         raise ValueError("Test sources cannot enter production data")
```

### x_validate_runtime_source_shape__mutmut_22

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_22: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -15,6 +15,6 @@
     else:
         ApplyStepSource.__post_init__(source)
     if source.kind == "legacy":
-        raise ValueError("Archive sources cannot enter the V3 runtime")
+        raise ValueError("ARCHIVE SOURCES CANNOT ENTER THE V3 RUNTIME")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
         raise ValueError("Test sources cannot enter production data")
```

### x_validate_runtime_source_shape__mutmut_32

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_32: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError(None)
```

### x_validate_runtime_source_shape__mutmut_33

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_33: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError("XXTest sources cannot enter production dataXX")
```

### x_validate_runtime_source_shape__mutmut_34

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_34: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError("test sources cannot enter production data")
```

### x_validate_runtime_source_shape__mutmut_35

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_35: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError("TEST SOURCES CANNOT ENTER PRODUCTION DATA")
```

### x__identifier__mutmut_3

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_3: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def _identifier(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Location identifiers must be strings")
+        raise TypeError(None)
     if not value:
         raise ValueError("Location identifiers must be nonempty")
```

### x__identifier__mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_4: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def _identifier(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Location identifiers must be strings")
+        raise TypeError("XXLocation identifiers must be stringsXX")
     if not value:
         raise ValueError("Location identifiers must be nonempty")
```

### x__identifier__mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_5: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def _identifier(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Location identifiers must be strings")
+        raise TypeError("location identifiers must be strings")
     if not value:
         raise ValueError("Location identifiers must be nonempty")
```

### x__identifier__mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_6: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def _identifier(value: object) -> None:
     if type(value) is not str:
-        raise TypeError("Location identifiers must be strings")
+        raise TypeError("LOCATION IDENTIFIERS MUST BE STRINGS")
     if not value:
         raise ValueError("Location identifiers must be nonempty")
```

### x__identifier__mutmut_8

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_8: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,4 +2,4 @@
     if type(value) is not str:
         raise TypeError("Location identifiers must be strings")
     if not value:
-        raise ValueError("Location identifiers must be nonempty")
+        raise ValueError(None)
```

### x__identifier__mutmut_9

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_9: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,4 +2,4 @@
     if type(value) is not str:
         raise TypeError("Location identifiers must be strings")
     if not value:
-        raise ValueError("Location identifiers must be nonempty")
+        raise ValueError("XXLocation identifiers must be nonemptyXX")
```

### x__identifier__mutmut_10

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_10: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,4 +2,4 @@
     if type(value) is not str:
         raise TypeError("Location identifiers must be strings")
     if not value:
-        raise ValueError("Location identifiers must be nonempty")
+        raise ValueError("location identifiers must be nonempty")
```

### x__identifier__mutmut_11

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x__identifier__mutmut_11: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,4 +2,4 @@
     if type(value) is not str:
         raise TypeError("Location identifiers must be strings")
     if not value:
-        raise ValueError("Location identifiers must be nonempty")
+        raise ValueError("LOCATION IDENTIFIERS MUST BE NONEMPTY")
```

### xǁLocationǁ__post_init____mutmut_3

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.scope) is not str:
-        raise TypeError("Location scope must be a string")
+        raise TypeError(None)
     if self.scope not in ("casa", "room", "zone", "rooms"):
         raise ValueError("Unknown Location scope")
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
```

### xǁLocationǁ__post_init____mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.scope) is not str:
-        raise TypeError("Location scope must be a string")
+        raise TypeError("XXLocation scope must be a stringXX")
     if self.scope not in ("casa", "room", "zone", "rooms"):
         raise ValueError("Unknown Location scope")
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
```

### xǁLocationǁ__post_init____mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.scope) is not str:
-        raise TypeError("Location scope must be a string")
+        raise TypeError("location scope must be a string")
     if self.scope not in ("casa", "room", "zone", "rooms"):
         raise ValueError("Unknown Location scope")
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
```

### xǁLocationǁ__post_init____mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.scope) is not str:
-        raise TypeError("Location scope must be a string")
+        raise TypeError("LOCATION SCOPE MUST BE A STRING")
     if self.scope not in ("casa", "room", "zone", "rooms"):
         raise ValueError("Unknown Location scope")
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
```

### xǁLocationǁ__post_init____mutmut_16

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_16: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,7 +2,7 @@
     if type(self.scope) is not str:
         raise TypeError("Location scope must be a string")
     if self.scope not in ("casa", "room", "zone", "rooms"):
-        raise ValueError("Unknown Location scope")
+        raise ValueError(None)
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
```

### xǁLocationǁ__post_init____mutmut_17

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_17: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,7 +2,7 @@
     if type(self.scope) is not str:
         raise TypeError("Location scope must be a string")
     if self.scope not in ("casa", "room", "zone", "rooms"):
-        raise ValueError("Unknown Location scope")
+        raise ValueError("XXUnknown Location scopeXX")
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
```

### xǁLocationǁ__post_init____mutmut_18

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_18: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,7 +2,7 @@
     if type(self.scope) is not str:
         raise TypeError("Location scope must be a string")
     if self.scope not in ("casa", "room", "zone", "rooms"):
-        raise ValueError("Unknown Location scope")
+        raise ValueError("unknown location scope")
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
```

### xǁLocationǁ__post_init____mutmut_19

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_19: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,7 +2,7 @@
     if type(self.scope) is not str:
         raise TypeError("Location scope must be a string")
     if self.scope not in ("casa", "room", "zone", "rooms"):
-        raise ValueError("Unknown Location scope")
+        raise ValueError("UNKNOWN LOCATION SCOPE")
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
```

### xǁLocationǁ__post_init____mutmut_35

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_35: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -6,7 +6,7 @@
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
-        raise ValueError("Location fields do not match its scope")
+        raise ValueError(None)
     if self.scope == "room":
         _identifier(self.room_id)
     elif self.scope == "zone":
```

### xǁLocationǁ__post_init____mutmut_36

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_36: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -6,7 +6,7 @@
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
-        raise ValueError("Location fields do not match its scope")
+        raise ValueError("XXLocation fields do not match its scopeXX")
     if self.scope == "room":
         _identifier(self.room_id)
     elif self.scope == "zone":
```

### xǁLocationǁ__post_init____mutmut_37

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_37: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -6,7 +6,7 @@
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
-        raise ValueError("Location fields do not match its scope")
+        raise ValueError("location fields do not match its scope")
     if self.scope == "room":
         _identifier(self.room_id)
     elif self.scope == "zone":
```

### xǁLocationǁ__post_init____mutmut_38

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_38: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -6,7 +6,7 @@
     actual = (self.room_id is not None, self.zone_id is not None, self.room_ids is not None)
     expected = (self.scope == "room", self.scope == "zone", self.scope == "rooms")
     if actual != expected:
-        raise ValueError("Location fields do not match its scope")
+        raise ValueError("LOCATION FIELDS DO NOT MATCH ITS SCOPE")
     if self.scope == "room":
         _identifier(self.room_id)
     elif self.scope == "zone":
```

### xǁLocationǁ__post_init____mutmut_52

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_52: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -13,7 +13,7 @@
         _identifier(self.zone_id)
     elif self.scope == "rooms":
         if type(self.room_ids) is not frozenset:
-            raise TypeError("Multiple-room Location requires a frozenset")
+            raise TypeError(None)
         if len(self.room_ids) < 2:
             raise ValueError("Multiple-room Location needs at least two identifiers")
         for identifier in self.room_ids:
```

### xǁLocationǁ__post_init____mutmut_53

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_53: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -13,7 +13,7 @@
         _identifier(self.zone_id)
     elif self.scope == "rooms":
         if type(self.room_ids) is not frozenset:
-            raise TypeError("Multiple-room Location requires a frozenset")
+            raise TypeError("XXMultiple-room Location requires a frozensetXX")
         if len(self.room_ids) < 2:
             raise ValueError("Multiple-room Location needs at least two identifiers")
         for identifier in self.room_ids:
```

### xǁLocationǁ__post_init____mutmut_54

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_54: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -13,7 +13,7 @@
         _identifier(self.zone_id)
     elif self.scope == "rooms":
         if type(self.room_ids) is not frozenset:
-            raise TypeError("Multiple-room Location requires a frozenset")
+            raise TypeError("multiple-room location requires a frozenset")
         if len(self.room_ids) < 2:
             raise ValueError("Multiple-room Location needs at least two identifiers")
         for identifier in self.room_ids:
```

### xǁLocationǁ__post_init____mutmut_55

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_55: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -13,7 +13,7 @@
         _identifier(self.zone_id)
     elif self.scope == "rooms":
         if type(self.room_ids) is not frozenset:
-            raise TypeError("Multiple-room Location requires a frozenset")
+            raise TypeError("MULTIPLE-ROOM LOCATION REQUIRES A FROZENSET")
         if len(self.room_ids) < 2:
             raise ValueError("Multiple-room Location needs at least two identifiers")
         for identifier in self.room_ids:
```

### xǁLocationǁ__post_init____mutmut_58

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_58: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -15,6 +15,6 @@
         if type(self.room_ids) is not frozenset:
             raise TypeError("Multiple-room Location requires a frozenset")
         if len(self.room_ids) < 2:
-            raise ValueError("Multiple-room Location needs at least two identifiers")
+            raise ValueError(None)
         for identifier in self.room_ids:
             _identifier(identifier)
```

### xǁLocationǁ__post_init____mutmut_59

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_59: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -15,6 +15,6 @@
         if type(self.room_ids) is not frozenset:
             raise TypeError("Multiple-room Location requires a frozenset")
         if len(self.room_ids) < 2:
-            raise ValueError("Multiple-room Location needs at least two identifiers")
+            raise ValueError("XXMultiple-room Location needs at least two identifiersXX")
         for identifier in self.room_ids:
             _identifier(identifier)
```

### xǁLocationǁ__post_init____mutmut_60

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_60: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -15,6 +15,6 @@
         if type(self.room_ids) is not frozenset:
             raise TypeError("Multiple-room Location requires a frozenset")
         if len(self.room_ids) < 2:
-            raise ValueError("Multiple-room Location needs at least two identifiers")
+            raise ValueError("multiple-room location needs at least two identifiers")
         for identifier in self.room_ids:
             _identifier(identifier)
```

### xǁLocationǁ__post_init____mutmut_61

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.xǁLocationǁ__post_init____mutmut_61: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -15,6 +15,6 @@
         if type(self.room_ids) is not frozenset:
             raise TypeError("Multiple-room Location requires a frozenset")
         if len(self.room_ids) < 2:
-            raise ValueError("Multiple-room Location needs at least two identifiers")
+            raise ValueError("MULTIPLE-ROOM LOCATION NEEDS AT LEAST TWO IDENTIFIERS")
         for identifier in self.room_ids:
             _identifier(identifier)
```

### x_location_from_key__mutmut_3

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_3: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key(key: LocationKey) -> Location:
     """Recover the canonical key; never normalize malformed persisted identity."""
     if type(key) is not tuple:
-        raise TypeError("Location key must be a tuple")
+        raise TypeError(None)
     if not key:
         raise ValueError("Location key cannot be empty")
     for item in key:
```

### x_location_from_key__mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_4: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key(key: LocationKey) -> Location:
     """Recover the canonical key; never normalize malformed persisted identity."""
     if type(key) is not tuple:
-        raise TypeError("Location key must be a tuple")
+        raise TypeError("XXLocation key must be a tupleXX")
     if not key:
         raise ValueError("Location key cannot be empty")
     for item in key:
```

### x_location_from_key__mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_5: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key(key: LocationKey) -> Location:
     """Recover the canonical key; never normalize malformed persisted identity."""
     if type(key) is not tuple:
-        raise TypeError("Location key must be a tuple")
+        raise TypeError("location key must be a tuple")
     if not key:
         raise ValueError("Location key cannot be empty")
     for item in key:
```

### x_location_from_key__mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_6: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key(key: LocationKey) -> Location:
     """Recover the canonical key; never normalize malformed persisted identity."""
     if type(key) is not tuple:
-        raise TypeError("Location key must be a tuple")
+        raise TypeError("LOCATION KEY MUST BE A TUPLE")
     if not key:
         raise ValueError("Location key cannot be empty")
     for item in key:
```

### x_location_from_key__mutmut_8

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_8: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -3,7 +3,7 @@
     if type(key) is not tuple:
         raise TypeError("Location key must be a tuple")
     if not key:
-        raise ValueError("Location key cannot be empty")
+        raise ValueError(None)
     for item in key:
         _identifier(item)
     scope = key[0]
```

### x_location_from_key__mutmut_9

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_9: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -3,7 +3,7 @@
     if type(key) is not tuple:
         raise TypeError("Location key must be a tuple")
     if not key:
-        raise ValueError("Location key cannot be empty")
+        raise ValueError("XXLocation key cannot be emptyXX")
     for item in key:
         _identifier(item)
     scope = key[0]
```

### x_location_from_key__mutmut_10

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_10: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -3,7 +3,7 @@
     if type(key) is not tuple:
         raise TypeError("Location key must be a tuple")
     if not key:
-        raise ValueError("Location key cannot be empty")
+        raise ValueError("location key cannot be empty")
     for item in key:
         _identifier(item)
     scope = key[0]
```

### x_location_from_key__mutmut_11

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_11: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -3,7 +3,7 @@
     if type(key) is not tuple:
         raise TypeError("Location key must be a tuple")
     if not key:
-        raise ValueError("Location key cannot be empty")
+        raise ValueError("LOCATION KEY CANNOT BE EMPTY")
     for item in key:
         _identifier(item)
     scope = key[0]
```

### x_location_from_key__mutmut_50

Equivalent candidate-branch widening. Correct casa/room/zone keys already return earlier. rooms with too few members still fails cardinality; other prefixes with length>=3 can enter but cannot pass result.key == key because the result prefix is rooms. The same canonical keys succeed and every additional candidate still raises ValueError. Extra work/generic error prose on invalid keys does not change a specified domain rule.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_50: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -13,7 +13,7 @@
         return Location("room", room_id=key[1])
     if scope == "zone" and len(key) == 2:
         return Location("zone", zone_id=key[1])
-    if scope == "rooms" and len(key) >= 3:
+    if scope == "rooms" or len(key) >= 3:
         result = Location("rooms", room_ids=frozenset(key[1:]))
         if result.key == key:
             return result
```

### x_location_from_key__mutmut_66

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_66: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -17,4 +17,4 @@
         result = Location("rooms", room_ids=frozenset(key[1:]))
         if result.key == key:
             return result
-    raise ValueError("Invalid or noncanonical Location key")
+    raise ValueError(None)
```

### x_location_from_key__mutmut_67

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_67: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -17,4 +17,4 @@
         result = Location("rooms", room_ids=frozenset(key[1:]))
         if result.key == key:
             return result
-    raise ValueError("Invalid or noncanonical Location key")
+    raise ValueError("XXInvalid or noncanonical Location keyXX")
```

### x_location_from_key__mutmut_68

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_68: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -17,4 +17,4 @@
         result = Location("rooms", room_ids=frozenset(key[1:]))
         if result.key == key:
             return result
-    raise ValueError("Invalid or noncanonical Location key")
+    raise ValueError("invalid or noncanonical location key")
```

### x_location_from_key__mutmut_69

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key__mutmut_69: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -17,4 +17,4 @@
         result = Location("rooms", room_ids=frozenset(key[1:]))
         if result.key == key:
             return result
-    raise ValueError("Invalid or noncanonical Location key")
+    raise ValueError("INVALID OR NONCANONICAL LOCATION KEY")
```

### x_location_key_json__mutmut_2

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_key_json__mutmut_2: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def location_key_json(location: Location) -> str:
     """Canonical scalar key text for identity storage and follow-up projections."""
     if not isinstance(location, Location):
-        raise TypeError("Location key encoding requires a Location")
+        raise TypeError(None)
     return canonical_json_bytes(_location_key(location)).decode("utf-8")
```

### x_location_key_json__mutmut_3

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_key_json__mutmut_3: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def location_key_json(location: Location) -> str:
     """Canonical scalar key text for identity storage and follow-up projections."""
     if not isinstance(location, Location):
-        raise TypeError("Location key encoding requires a Location")
+        raise TypeError("XXLocation key encoding requires a LocationXX")
     return canonical_json_bytes(_location_key(location)).decode("utf-8")
```

### x_location_key_json__mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_key_json__mutmut_4: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def location_key_json(location: Location) -> str:
     """Canonical scalar key text for identity storage and follow-up projections."""
     if not isinstance(location, Location):
-        raise TypeError("Location key encoding requires a Location")
+        raise TypeError("location key encoding requires a location")
     return canonical_json_bytes(_location_key(location)).decode("utf-8")
```

### x_location_key_json__mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_key_json__mutmut_5: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,5 +1,5 @@
 def location_key_json(location: Location) -> str:
     """Canonical scalar key text for identity storage and follow-up projections."""
     if not isinstance(location, Location):
-        raise TypeError("Location key encoding requires a Location")
+        raise TypeError("LOCATION KEY ENCODING REQUIRES A LOCATION")
     return canonical_json_bytes(_location_key(location)).decode("utf-8")
```

### x_location_key_json__mutmut_10

UTF-8 and utf-8 identify the same Python codec, producing identical text and errors from the same canonical bytes.

```diff
# custom_components.heima.v3.contracts.location.x_location_key_json__mutmut_10: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,4 +2,4 @@
     """Canonical scalar key text for identity storage and follow-up projections."""
     if not isinstance(location, Location):
         raise TypeError("Location key encoding requires a Location")
-    return canonical_json_bytes(_location_key(location)).decode("utf-8")
+    return canonical_json_bytes(_location_key(location)).decode("UTF-8")
```

### x_location_from_key_json__mutmut_3

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_3: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key_json(text: str) -> Location:
     """Decode canonical persisted key text, not a general-purpose JSON document."""
     if type(text) is not str:
-        raise TypeError("Location key JSON must be text")
+        raise TypeError(None)
     decoded = json.loads(text)
     if type(decoded) is not list:
         raise TypeError("Location key JSON must contain an array")
```

### x_location_from_key_json__mutmut_4

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_4: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key_json(text: str) -> Location:
     """Decode canonical persisted key text, not a general-purpose JSON document."""
     if type(text) is not str:
-        raise TypeError("Location key JSON must be text")
+        raise TypeError("XXLocation key JSON must be textXX")
     decoded = json.loads(text)
     if type(decoded) is not list:
         raise TypeError("Location key JSON must contain an array")
```

### x_location_from_key_json__mutmut_5

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_5: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key_json(text: str) -> Location:
     """Decode canonical persisted key text, not a general-purpose JSON document."""
     if type(text) is not str:
-        raise TypeError("Location key JSON must be text")
+        raise TypeError("location key json must be text")
     decoded = json.loads(text)
     if type(decoded) is not list:
         raise TypeError("Location key JSON must contain an array")
```

### x_location_from_key_json__mutmut_6

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_6: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -1,7 +1,7 @@
 def location_from_key_json(text: str) -> Location:
     """Decode canonical persisted key text, not a general-purpose JSON document."""
     if type(text) is not str:
-        raise TypeError("Location key JSON must be text")
+        raise TypeError("LOCATION KEY JSON MUST BE TEXT")
     decoded = json.loads(text)
     if type(decoded) is not list:
         raise TypeError("Location key JSON must contain an array")
```

### x_location_from_key_json__mutmut_11

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_11: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -4,7 +4,7 @@
         raise TypeError("Location key JSON must be text")
     decoded = json.loads(text)
     if type(decoded) is not list:
-        raise TypeError("Location key JSON must contain an array")
+        raise TypeError(None)
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
         raise ValueError("Location key JSON is not canonical")
```

### x_location_from_key_json__mutmut_12

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_12: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -4,7 +4,7 @@
         raise TypeError("Location key JSON must be text")
     decoded = json.loads(text)
     if type(decoded) is not list:
-        raise TypeError("Location key JSON must contain an array")
+        raise TypeError("XXLocation key JSON must contain an arrayXX")
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
         raise ValueError("Location key JSON is not canonical")
```

### x_location_from_key_json__mutmut_13

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_13: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -4,7 +4,7 @@
         raise TypeError("Location key JSON must be text")
     decoded = json.loads(text)
     if type(decoded) is not list:
-        raise TypeError("Location key JSON must contain an array")
+        raise TypeError("location key json must contain an array")
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
         raise ValueError("Location key JSON is not canonical")
```

### x_location_from_key_json__mutmut_14

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_14: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -4,7 +4,7 @@
         raise TypeError("Location key JSON must be text")
     decoded = json.loads(text)
     if type(decoded) is not list:
-        raise TypeError("Location key JSON must contain an array")
+        raise TypeError("LOCATION KEY JSON MUST CONTAIN AN ARRAY")
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
         raise ValueError("Location key JSON is not canonical")
```

### x_location_from_key_json__mutmut_20

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_20: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -7,5 +7,5 @@
         raise TypeError("Location key JSON must contain an array")
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
-        raise ValueError("Location key JSON is not canonical")
+        raise ValueError(None)
     return location
```

### x_location_from_key_json__mutmut_21

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_21: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -7,5 +7,5 @@
         raise TypeError("Location key JSON must contain an array")
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
-        raise ValueError("Location key JSON is not canonical")
+        raise ValueError("XXLocation key JSON is not canonicalXX")
     return location
```

### x_location_from_key_json__mutmut_22

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_22: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -7,5 +7,5 @@
         raise TypeError("Location key JSON must contain an array")
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
-        raise ValueError("Location key JSON is not canonical")
+        raise ValueError("location key json is not canonical")
     return location
```

### x_location_from_key_json__mutmut_23

Generic exception prose only. Exception type, rejection boundary, canonical identity/encoding and source data mode/fingerprint are unchanged; no public message-text contract exists.

```diff
# custom_components.heima.v3.contracts.location.x_location_from_key_json__mutmut_23: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -7,5 +7,5 @@
         raise TypeError("Location key JSON must contain an array")
     location = location_from_key(tuple(decoded))
     if location_key_json(location) != text:
-        raise ValueError("Location key JSON is not canonical")
+        raise ValueError("LOCATION KEY JSON IS NOT CANONICAL")
     return location
```
