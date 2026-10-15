# Source values — mutation evidence, 2026-10-15

Fresh mutmut3.8, Python3.14.5, only contracts/fact_sources.py, all tests/v3,
seed3145, four children: **134 generated,106 killed,28 survived; zero errors,
timeouts, skipped, untested or interrupted.** All28 survivors change generic
exception prose only, preserving the exception type; exact diffs below.
No raw100% score claim. Permanent default scope grows21→22modules; this scoped
run does not refresh earlier modules' mutation evidence.

First trial:131generated,102killed,29survived. One was a real test gap: changing
runtime shape mode's default to test_mode=True went undetected because the mode
table passed an explicit flag. Added four default-mode regressions. Internal review
also reproduced a source validation bypass via overridden subclass __post_init__:
two runtime checks and fingerprint extraction accepted invalid excluded correlation.
All three regressions first failed; explicit base-validator dispatch fixes them.
Source changed, so restarted mutation in a fresh mutants directory. The final run
killed the default-mode mutant; all final survivors were individually re-inspected.

Eighteen supplements killed after a clean169-test baseline: frozen/slots on each of
three value types (6), fact/action/actor literal vocabularies (3), and all nine
specified source data defaults including UUID safety nets and heima actor defaults.
These decorators/module declarations are outside ordinary function mutation. Each
seed ran its named behavioral regression with pytest exit1; collection errors and
zero selected tests never count. No module logic was silently excluded.

Reproduction in fresh source/tests copy, scoped pyproject:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_fact_sources.py
```

Run /private/tmp/heima-v3-fact-source/mutants;
log /private/tmp/heima-source-mutmut-final.log, supplement log
/private/tmp/heima-source-supplements-final.log. Temporary artifacts are supplementary;
exact survivor diffs/reasons retained below. Green shape tests do not prove authority
checks, verified HA ingress, generation bindings or redaction; those remain future.

## Individually inspected survivors

### x__text__mutmut_6

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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

### x_fact_source_fingerprint__mutmut_2

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_2: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the stable source; revalidate correlation too, then exclude it."""
     if not isinstance(source, FactSource):
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError(None)
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_fact_source_fingerprint__mutmut_3

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the stable source; revalidate correlation too, then exclude it."""
     if not isinstance(source, FactSource):
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError("XXFact source fingerprint requires a FactSourceXX")
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_fact_source_fingerprint__mutmut_4

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the stable source; revalidate correlation too, then exclude it."""
     if not isinstance(source, FactSource):
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError("fact source fingerprint requires a factsource")
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_fact_source_fingerprint__mutmut_5

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_fact_source_fingerprint__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -1,7 +1,7 @@
 def fact_source_fingerprint(source: FactSource) -> FactSourceFingerprint:
     """Extract the stable source; revalidate correlation too, then exclude it."""
     if not isinstance(source, FactSource):
-        raise TypeError("Fact source fingerprint requires a FactSource")
+        raise TypeError("FACT SOURCE FINGERPRINT REQUIRES A FACTSOURCE")
     FactSource.__post_init__(source)
     return FactSourceFingerprint(
         source.kind,
```

### x_validate_runtime_source_shape__mutmut_4

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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
     if not isinstance(source, (FactSource, ApplyStepSource)):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_5

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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
     if not isinstance(source, (FactSource, ApplyStepSource)):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_6

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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
     if not isinstance(source, (FactSource, ApplyStepSource)):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_7

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

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
     if not isinstance(source, (FactSource, ApplyStepSource)):
         raise TypeError("Runtime source shape requires a typed source")
     if isinstance(source, FactSource):
```

### x_validate_runtime_source_shape__mutmut_9

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_9: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if not isinstance(source, (FactSource, ApplyStepSource)):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError(None)
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_10

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_10: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if not isinstance(source, (FactSource, ApplyStepSource)):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError("XXRuntime source shape requires a typed sourceXX")
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_11

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_11: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if not isinstance(source, (FactSource, ApplyStepSource)):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError("runtime source shape requires a typed source")
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_12

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_12: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -9,7 +9,7 @@
     if type(test_mode) is not bool:
         raise TypeError("Source validation mode must be boolean")
     if not isinstance(source, (FactSource, ApplyStepSource)):
-        raise TypeError("Runtime source shape requires a typed source")
+        raise TypeError("RUNTIME SOURCE SHAPE REQUIRES A TYPED SOURCE")
     if isinstance(source, FactSource):
         FactSource.__post_init__(source)
     else:
```

### x_validate_runtime_source_shape__mutmut_18

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_18: survived
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

### x_validate_runtime_source_shape__mutmut_19

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_19: survived
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

### x_validate_runtime_source_shape__mutmut_20

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_20: survived
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

### x_validate_runtime_source_shape__mutmut_21

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_21: survived
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

### x_validate_runtime_source_shape__mutmut_31

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_31: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError(None)
```

### x_validate_runtime_source_shape__mutmut_32

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_32: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError("XXTest sources cannot enter production dataXX")
```

### x_validate_runtime_source_shape__mutmut_33

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_33: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError("test sources cannot enter production data")
```

### x_validate_runtime_source_shape__mutmut_34

Generic error prose only; exception type, rejection, field validation, data mode and
stable fingerprint remain identical. No public error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.fact_sources.x_validate_runtime_source_shape__mutmut_34: survived
--- custom_components/heima/v3/contracts/fact_sources.py
+++ custom_components/heima/v3/contracts/fact_sources.py
@@ -17,4 +17,4 @@
     if source.kind == "legacy":
         raise ValueError("Archive sources cannot enter the V3 runtime")
     if not test_mode and (source.kind == "test" or source.actor_type == "test"):
-        raise ValueError("Test sources cannot enter production data")
+        raise ValueError("TEST SOURCES CANNOT ENTER PRODUCTION DATA")
```
