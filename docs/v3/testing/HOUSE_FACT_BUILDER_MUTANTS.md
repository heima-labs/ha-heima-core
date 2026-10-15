# HouseFact builder — mutation review, 2026-10-15

Fresh mutmut3.8/Python3.14.5, only contracts/house_facts.py, all tests/v3,
seed3145, four children: **233 generated,189 killed,44 survived; zero errors,
timeouts, skipped, untested or interrupted.** Every survivor is a fixed-error
prose change preserving exception type; exact diffs below. No raw100% score claim.
Permanent scope grows22→23modules; this run does not refresh unchanged modules.

The first fresh run killed187 and left46. Two real test gaps survived: returning
hash(None) or hash(canonical_json_bytes(None)) for all Provenance values. Equal
values still had equal hashes, so that alone did not enforce hashing from canonical
content. Added the contract check hash(how)==hash(canonical_json_bytes(how)) across
the canonical-semantics fixtures; restarted in a fresh mutants directory. Production
source stayed unchanged. Final survivor IDs/diffs match the inspected first-run
prose set, excluding those two now-killed hash mutations.

Eleven semantic supplements killed with a clean110-test baseline: frozen/slots for
HouseFact,Provenance,FactBuildResult (6); omission sentinel replaced with None;
erasing unavailable values; losing evidence diagnostics; native Python fact and
provenance equality (True versus1 would collapse). Decorators/sentinel live outside
ordinary function mutation. init=False/eq=False declaration flags do not add runtime
logic here because constructors/equality/hash methods are explicitly defined;
the actual methods are mutated and tested. No new application size limit/constant
was introduced; existing payload validators retain their own evidence.

Commands in a fresh source/tests copy with scoped only_mutate:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_house_facts.py
```

Run /private/tmp/heima-v3-house-facts/mutants; final log
/private/tmp/heima-house-facts-mutmut-final.log; supplement log
/private/tmp/heima-house-facts-supplements-final.log. Every supplement selected its
named test, required pytest exit1 and ran after a clean baseline. Missing selection,
collection errors and unrelated initial failures do not count as kills. Temporary
artifacts supplement these retained exact survivor diffs/proofs. No live HA, source
authorization, SQL fact write, decoder or ARM-throughput claim.

## Individually inspected survivors

### xǁProvenanceǁ__init____mutmut_1

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_1: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError(None)
```

### xǁProvenanceǁ__init____mutmut_2

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_2: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError("XXConstruct provenance through build_house_factXX")
```

### xǁProvenanceǁ__init____mutmut_3

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_3: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError("construct provenance through build_house_fact")
```

### xǁProvenanceǁ__init____mutmut_4

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_4: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError("CONSTRUCT PROVENANCE THROUGH BUILD_HOUSE_FACT")
```

### xǁHouseFactǁ__init____mutmut_1

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_1: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError(None)
```

### xǁHouseFactǁ__init____mutmut_2

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_2: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError("XXConstruct facts through build_house_factXX")
```

### xǁHouseFactǁ__init____mutmut_3

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_3: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError("construct facts through build_house_fact")
```

### xǁHouseFactǁ__init____mutmut_4

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_4: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError("CONSTRUCT FACTS THROUGH BUILD_HOUSE_FACT")
```

### x__confidence_pair__mutmut_3

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_3: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,6 +1,6 @@
 def _confidence_pair(confidence: float | None, available: bool) -> None:
     if type(available) is not bool:
-        raise TypeError("Fact availability must be boolean")
+        raise TypeError(None)
     if available != (confidence is not None):
         raise ValueError("Fact confidence and availability are inconsistent")
     if confidence is None:
```

### x__confidence_pair__mutmut_4

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_4: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,6 +1,6 @@
 def _confidence_pair(confidence: float | None, available: bool) -> None:
     if type(available) is not bool:
-        raise TypeError("Fact availability must be boolean")
+        raise TypeError("XXFact availability must be booleanXX")
     if available != (confidence is not None):
         raise ValueError("Fact confidence and availability are inconsistent")
     if confidence is None:
```

### x__confidence_pair__mutmut_5

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_5: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,6 +1,6 @@
 def _confidence_pair(confidence: float | None, available: bool) -> None:
     if type(available) is not bool:
-        raise TypeError("Fact availability must be boolean")
+        raise TypeError("fact availability must be boolean")
     if available != (confidence is not None):
         raise ValueError("Fact confidence and availability are inconsistent")
     if confidence is None:
```

### x__confidence_pair__mutmut_6

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_6: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,6 +1,6 @@
 def _confidence_pair(confidence: float | None, available: bool) -> None:
     if type(available) is not bool:
-        raise TypeError("Fact availability must be boolean")
+        raise TypeError("FACT AVAILABILITY MUST BE BOOLEAN")
     if available != (confidence is not None):
         raise ValueError("Fact confidence and availability are inconsistent")
     if confidence is None:
```

### x__confidence_pair__mutmut_9

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_9: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -2,7 +2,7 @@
     if type(available) is not bool:
         raise TypeError("Fact availability must be boolean")
     if available != (confidence is not None):
-        raise ValueError("Fact confidence and availability are inconsistent")
+        raise ValueError(None)
     if confidence is None:
         return
     if type(confidence) not in (int, float):
```

### x__confidence_pair__mutmut_10

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_10: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -2,7 +2,7 @@
     if type(available) is not bool:
         raise TypeError("Fact availability must be boolean")
     if available != (confidence is not None):
-        raise ValueError("Fact confidence and availability are inconsistent")
+        raise ValueError("XXFact confidence and availability are inconsistentXX")
     if confidence is None:
         return
     if type(confidence) not in (int, float):
```

### x__confidence_pair__mutmut_11

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_11: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -2,7 +2,7 @@
     if type(available) is not bool:
         raise TypeError("Fact availability must be boolean")
     if available != (confidence is not None):
-        raise ValueError("Fact confidence and availability are inconsistent")
+        raise ValueError("fact confidence and availability are inconsistent")
     if confidence is None:
         return
     if type(confidence) not in (int, float):
```

### x__confidence_pair__mutmut_12

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_12: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -2,7 +2,7 @@
     if type(available) is not bool:
         raise TypeError("Fact availability must be boolean")
     if available != (confidence is not None):
-        raise ValueError("Fact confidence and availability are inconsistent")
+        raise ValueError("FACT CONFIDENCE AND AVAILABILITY ARE INCONSISTENT")
     if confidence is None:
         return
     if type(confidence) not in (int, float):
```

### x__confidence_pair__mutmut_16

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_16: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -6,7 +6,7 @@
     if confidence is None:
         return
     if type(confidence) not in (int, float):
-        raise TypeError("Fact confidence must be a primitive number")
+        raise TypeError(None)
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
         raise ValueError("Fact confidence is outside its finite unit interval")
```

### x__confidence_pair__mutmut_17

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_17: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -6,7 +6,7 @@
     if confidence is None:
         return
     if type(confidence) not in (int, float):
-        raise TypeError("Fact confidence must be a primitive number")
+        raise TypeError("XXFact confidence must be a primitive numberXX")
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
         raise ValueError("Fact confidence is outside its finite unit interval")
```

### x__confidence_pair__mutmut_18

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_18: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -6,7 +6,7 @@
     if confidence is None:
         return
     if type(confidence) not in (int, float):
-        raise TypeError("Fact confidence must be a primitive number")
+        raise TypeError("fact confidence must be a primitive number")
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
         raise ValueError("Fact confidence is outside its finite unit interval")
```

### x__confidence_pair__mutmut_19

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_19: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -6,7 +6,7 @@
     if confidence is None:
         return
     if type(confidence) not in (int, float):
-        raise TypeError("Fact confidence must be a primitive number")
+        raise TypeError("FACT CONFIDENCE MUST BE A PRIMITIVE NUMBER")
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
         raise ValueError("Fact confidence is outside its finite unit interval")
```

### x__confidence_pair__mutmut_25

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_25: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -9,4 +9,4 @@
         raise TypeError("Fact confidence must be a primitive number")
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
-        raise ValueError("Fact confidence is outside its finite unit interval")
+        raise ValueError(None)
```

### x__confidence_pair__mutmut_26

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_26: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -9,4 +9,4 @@
         raise TypeError("Fact confidence must be a primitive number")
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
-        raise ValueError("Fact confidence is outside its finite unit interval")
+        raise ValueError("XXFact confidence is outside its finite unit intervalXX")
```

### x__confidence_pair__mutmut_27

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_27: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -9,4 +9,4 @@
         raise TypeError("Fact confidence must be a primitive number")
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
-        raise ValueError("Fact confidence is outside its finite unit interval")
+        raise ValueError("fact confidence is outside its finite unit interval")
```

### x__confidence_pair__mutmut_28

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_28: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -9,4 +9,4 @@
         raise TypeError("Fact confidence must be a primitive number")
     # Bounds also reject infinities/NaN without converting an arbitrary large int.
     if not 0 <= confidence <= 1:
-        raise ValueError("Fact confidence is outside its finite unit interval")
+        raise ValueError("FACT CONFIDENCE IS OUTSIDE ITS FINITE UNIT INTERVAL")
```

### x_build_house_fact__mutmut_5

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_5: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -16,7 +16,7 @@
     The runtime must verify admission and consume diagnostics before accepting it.
     """
     if type(fact_type) is not str:
-        raise TypeError("Fact type must be a primitive string")
+        raise TypeError(None)
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
         raise ValueError("Fact type must have nonempty concrete dotted segments")
     canonical_json_bytes(fact_type)
```

### x_build_house_fact__mutmut_6

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_6: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -16,7 +16,7 @@
     The runtime must verify admission and consume diagnostics before accepting it.
     """
     if type(fact_type) is not str:
-        raise TypeError("Fact type must be a primitive string")
+        raise TypeError("XXFact type must be a primitive stringXX")
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
         raise ValueError("Fact type must have nonempty concrete dotted segments")
     canonical_json_bytes(fact_type)
```

### x_build_house_fact__mutmut_7

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_7: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -16,7 +16,7 @@
     The runtime must verify admission and consume diagnostics before accepting it.
     """
     if type(fact_type) is not str:
-        raise TypeError("Fact type must be a primitive string")
+        raise TypeError("fact type must be a primitive string")
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
         raise ValueError("Fact type must have nonempty concrete dotted segments")
     canonical_json_bytes(fact_type)
```

### x_build_house_fact__mutmut_8

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_8: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -16,7 +16,7 @@
     The runtime must verify admission and consume diagnostics before accepting it.
     """
     if type(fact_type) is not str:
-        raise TypeError("Fact type must be a primitive string")
+        raise TypeError("FACT TYPE MUST BE A PRIMITIVE STRING")
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
         raise ValueError("Fact type must have nonempty concrete dotted segments")
     canonical_json_bytes(fact_type)
```

### x_build_house_fact__mutmut_16

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_16: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -18,7 +18,7 @@
     if type(fact_type) is not str:
         raise TypeError("Fact type must be a primitive string")
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
-        raise ValueError("Fact type must have nonempty concrete dotted segments")
+        raise ValueError(None)
     canonical_json_bytes(fact_type)
     parse_instant(when)
     _confidence_pair(confidence, available)
```

### x_build_house_fact__mutmut_17

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_17: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -18,7 +18,7 @@
     if type(fact_type) is not str:
         raise TypeError("Fact type must be a primitive string")
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
-        raise ValueError("Fact type must have nonempty concrete dotted segments")
+        raise ValueError("XXFact type must have nonempty concrete dotted segmentsXX")
     canonical_json_bytes(fact_type)
     parse_instant(when)
     _confidence_pair(confidence, available)
```

### x_build_house_fact__mutmut_18

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_18: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -18,7 +18,7 @@
     if type(fact_type) is not str:
         raise TypeError("Fact type must be a primitive string")
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
-        raise ValueError("Fact type must have nonempty concrete dotted segments")
+        raise ValueError("fact type must have nonempty concrete dotted segments")
     canonical_json_bytes(fact_type)
     parse_instant(when)
     _confidence_pair(confidence, available)
```

### x_build_house_fact__mutmut_19

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_19: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -18,7 +18,7 @@
     if type(fact_type) is not str:
         raise TypeError("Fact type must be a primitive string")
     if "*" in fact_type or any(not segment for segment in fact_type.split(".")):
-        raise ValueError("Fact type must have nonempty concrete dotted segments")
+        raise ValueError("FACT TYPE MUST HAVE NONEMPTY CONCRETE DOTTED SEGMENTS")
     canonical_json_bytes(fact_type)
     parse_instant(when)
     _confidence_pair(confidence, available)
```

### x_build_house_fact__mutmut_27

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_27: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -23,7 +23,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError(None)
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

### x_build_house_fact__mutmut_28

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_28: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -23,7 +23,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError("XXFact location must be a LocationXX")
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

### x_build_house_fact__mutmut_29

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_29: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -23,7 +23,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError("fact location must be a location")
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

### x_build_house_fact__mutmut_30

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_30: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -23,7 +23,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError("FACT LOCATION MUST BE A LOCATION")
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

### x_build_house_fact__mutmut_47

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_47: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -28,7 +28,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError(None)
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

### x_build_house_fact__mutmut_48

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_48: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -28,7 +28,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError("XXA fact requires a fact-side sourceXX")
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

### x_build_house_fact__mutmut_49

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_49: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -28,7 +28,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError("a fact requires a fact-side source")
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

### x_build_house_fact__mutmut_50

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_50: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -28,7 +28,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError("A FACT REQUIRES A FACT-SIDE SOURCE")
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

### x_house_fact_canonical_bytes__mutmut_3

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_3: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,7 +1,7 @@
 def house_fact_canonical_bytes(fact: HouseFact) -> bytes:
     """Encode a builder output; this is not untrusted-input admission/decoding."""
     if type(fact) is not HouseFact:
-        raise TypeError("Fact encoding requires a concrete HouseFact")
+        raise TypeError(None)
     location = fact.where
     return canonical_json_bytes(
         {
```

### x_house_fact_canonical_bytes__mutmut_4

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_4: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,7 +1,7 @@
 def house_fact_canonical_bytes(fact: HouseFact) -> bytes:
     """Encode a builder output; this is not untrusted-input admission/decoding."""
     if type(fact) is not HouseFact:
-        raise TypeError("Fact encoding requires a concrete HouseFact")
+        raise TypeError("XXFact encoding requires a concrete HouseFactXX")
     location = fact.where
     return canonical_json_bytes(
         {
```

### x_house_fact_canonical_bytes__mutmut_5

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_5: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,7 +1,7 @@
 def house_fact_canonical_bytes(fact: HouseFact) -> bytes:
     """Encode a builder output; this is not untrusted-input admission/decoding."""
     if type(fact) is not HouseFact:
-        raise TypeError("Fact encoding requires a concrete HouseFact")
+        raise TypeError("fact encoding requires a concrete housefact")
     location = fact.where
     return canonical_json_bytes(
         {
```

### x_house_fact_canonical_bytes__mutmut_6

Generic exception prose only; type, rejection/constructor boundary, prepared fields,
canonical equality/hash and returned diagnostics remain identical. No public
error-message text contract exists.

```diff
# custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_6: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,7 +1,7 @@
 def house_fact_canonical_bytes(fact: HouseFact) -> bytes:
     """Encode a builder output; this is not untrusted-input admission/decoding."""
     if type(fact) is not HouseFact:
-        raise TypeError("Fact encoding requires a concrete HouseFact")
+        raise TypeError("FACT ENCODING REQUIRES A CONCRETE HOUSEFACT")
     location = fact.where
     return canonical_json_bytes(
         {
```
