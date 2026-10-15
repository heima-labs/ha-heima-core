# Composed generation mutation review

Fresh mutmut3.8 scope: contracts/generations.py, all tests/v3, seed3145;
command `.venv-v3/bin/mutmut run --max-children 4`.
47generated,23killed,24equivalent generic-prose survivors; zero errors,timeouts,
skips,untested,interrupted. All24 diffs individually reviewed below.

An initial clean-baseline attempt rejected a test fixture: Hypothesis permutations
returns a list, so the property had to construct the specified tuple before
checking canonical order. This was fixed without a production change and a fresh
mutants directory used. That failed-baseline attempt is not a mutation result.

12 semantic supplements, passing75-test baseline: frozen/slots flags for both
records, each adjacent canonical-order swap, adding unknown layer7, omitted UTC
validation, omitted Unicode validation and omitted nested-reference revalidation.
All killed via selected behavioral tests with pytest exit1. Two nested-reference
metadata cases added after the47-mutant campaign, production source unchanged.
An earlier layer-removal seed failed during collection because global valid
reference fixtures instantiate all layers: it was rejected and is not counted.
Order swaps and added-vocabulary seeds run and fail inside named test bodies.

No compound Boolean decision exists in changed production functions; sequential
guards and tuple/order equality checks are tested directly. No module constants
or decorators outside the tool's function scope are silently counted as mutated.

## custom_components.heima.v3.contracts.generations.x__text__mutmut_3

```diff
# custom_components.heima.v3.contracts.generations.x__text__mutmut_3: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,4 +1,4 @@
 def _text(value: str) -> None:
     if type(value) is not str:
-        raise TypeError("Generation metadata requires primitive strings")
+        raise TypeError(None)
     canonical_json_bytes(value)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.x__text__mutmut_4

```diff
# custom_components.heima.v3.contracts.generations.x__text__mutmut_4: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,4 +1,4 @@
 def _text(value: str) -> None:
     if type(value) is not str:
-        raise TypeError("Generation metadata requires primitive strings")
+        raise TypeError("XXGeneration metadata requires primitive stringsXX")
     canonical_json_bytes(value)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.x__text__mutmut_5

```diff
# custom_components.heima.v3.contracts.generations.x__text__mutmut_5: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,4 +1,4 @@
 def _text(value: str) -> None:
     if type(value) is not str:
-        raise TypeError("Generation metadata requires primitive strings")
+        raise TypeError("generation metadata requires primitive strings")
     canonical_json_bytes(value)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.x__text__mutmut_6

```diff
# custom_components.heima.v3.contracts.generations.x__text__mutmut_6: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,4 +1,4 @@
 def _text(value: str) -> None:
     if type(value) is not str:
-        raise TypeError("Generation metadata requires primitive strings")
+        raise TypeError("GENERATION METADATA REQUIRES PRIMITIVE STRINGS")
     canonical_json_bytes(value)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_3

```diff
# custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     _text(self.layer)
     if self.layer not in _LAYER_ORDER:
-        raise ValueError("Unknown configuration layer")
+        raise ValueError(None)
     _text(self.generation_id)
     _text(self.definition_fingerprint)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_4

```diff
# custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     _text(self.layer)
     if self.layer not in _LAYER_ORDER:
-        raise ValueError("Unknown configuration layer")
+        raise ValueError("XXUnknown configuration layerXX")
     _text(self.generation_id)
     _text(self.definition_fingerprint)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_5

```diff
# custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     _text(self.layer)
     if self.layer not in _LAYER_ORDER:
-        raise ValueError("Unknown configuration layer")
+        raise ValueError("unknown configuration layer")
     _text(self.generation_id)
     _text(self.definition_fingerprint)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_6

```diff
# custom_components.heima.v3.contracts.generations.xǁLayerGenerationRefǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     _text(self.layer)
     if self.layer not in _LAYER_ORDER:
-        raise ValueError("Unknown configuration layer")
+        raise ValueError("UNKNOWN CONFIGURATION LAYER")
     _text(self.generation_id)
     _text(self.definition_fingerprint)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_6

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -3,7 +3,7 @@
     if self.previous_composed_generation_id is not None:
         _text(self.previous_composed_generation_id)
     if type(self.layers) is not tuple:
-        raise TypeError("Layer generations require an immutable tuple")
+        raise TypeError(None)
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
             raise TypeError("Layer generations require concrete references")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_7

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -3,7 +3,7 @@
     if self.previous_composed_generation_id is not None:
         _text(self.previous_composed_generation_id)
     if type(self.layers) is not tuple:
-        raise TypeError("Layer generations require an immutable tuple")
+        raise TypeError("XXLayer generations require an immutable tupleXX")
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
             raise TypeError("Layer generations require concrete references")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_8

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_8: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -3,7 +3,7 @@
     if self.previous_composed_generation_id is not None:
         _text(self.previous_composed_generation_id)
     if type(self.layers) is not tuple:
-        raise TypeError("Layer generations require an immutable tuple")
+        raise TypeError("layer generations require an immutable tuple")
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
             raise TypeError("Layer generations require concrete references")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_9

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -3,7 +3,7 @@
     if self.previous_composed_generation_id is not None:
         _text(self.previous_composed_generation_id)
     if type(self.layers) is not tuple:
-        raise TypeError("Layer generations require an immutable tuple")
+        raise TypeError("LAYER GENERATIONS REQUIRE AN IMMUTABLE TUPLE")
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
             raise TypeError("Layer generations require concrete references")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_12

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -6,7 +6,7 @@
         raise TypeError("Layer generations require an immutable tuple")
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
-            raise TypeError("Layer generations require concrete references")
+            raise TypeError(None)
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
         raise ValueError("Manifest requires every layer once in canonical order")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_13

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_13: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -6,7 +6,7 @@
         raise TypeError("Layer generations require an immutable tuple")
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
-            raise TypeError("Layer generations require concrete references")
+            raise TypeError("XXLayer generations require concrete referencesXX")
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
         raise ValueError("Manifest requires every layer once in canonical order")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_14

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_14: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -6,7 +6,7 @@
         raise TypeError("Layer generations require an immutable tuple")
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
-            raise TypeError("Layer generations require concrete references")
+            raise TypeError("layer generations require concrete references")
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
         raise ValueError("Manifest requires every layer once in canonical order")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_15

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_15: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -6,7 +6,7 @@
         raise TypeError("Layer generations require an immutable tuple")
     for ref in self.layers:
         if type(ref) is not LayerGenerationRef:
-            raise TypeError("Layer generations require concrete references")
+            raise TypeError("LAYER GENERATIONS REQUIRE CONCRETE REFERENCES")
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
         raise ValueError("Manifest requires every layer once in canonical order")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_19

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_19: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -9,7 +9,7 @@
             raise TypeError("Layer generations require concrete references")
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
-        raise ValueError("Manifest requires every layer once in canonical order")
+        raise ValueError(None)
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
         raise TypeError("Invalidated dependents require an immutable tuple")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_20

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_20: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -9,7 +9,7 @@
             raise TypeError("Layer generations require concrete references")
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
-        raise ValueError("Manifest requires every layer once in canonical order")
+        raise ValueError("XXManifest requires every layer once in canonical orderXX")
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
         raise TypeError("Invalidated dependents require an immutable tuple")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_21

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_21: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -9,7 +9,7 @@
             raise TypeError("Layer generations require concrete references")
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
-        raise ValueError("Manifest requires every layer once in canonical order")
+        raise ValueError("manifest requires every layer once in canonical order")
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
         raise TypeError("Invalidated dependents require an immutable tuple")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_22

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_22: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -9,7 +9,7 @@
             raise TypeError("Layer generations require concrete references")
         LayerGenerationRef.__post_init__(ref)
     if tuple(ref.layer for ref in self.layers) != _LAYER_ORDER:
-        raise ValueError("Manifest requires every layer once in canonical order")
+        raise ValueError("MANIFEST REQUIRES EVERY LAYER ONCE IN CANONICAL ORDER")
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
         raise TypeError("Invalidated dependents require an immutable tuple")
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_26

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_26: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -12,7 +12,7 @@
         raise ValueError("Manifest requires every layer once in canonical order")
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
-        raise TypeError("Invalidated dependents require an immutable tuple")
+        raise TypeError(None)
     for dependent in self.invalidated_dependents:
         _text(dependent)
     _text(self.actor_ref)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_27

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_27: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -12,7 +12,7 @@
         raise ValueError("Manifest requires every layer once in canonical order")
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
-        raise TypeError("Invalidated dependents require an immutable tuple")
+        raise TypeError("XXInvalidated dependents require an immutable tupleXX")
     for dependent in self.invalidated_dependents:
         _text(dependent)
     _text(self.actor_ref)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_28

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_28: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -12,7 +12,7 @@
         raise ValueError("Manifest requires every layer once in canonical order")
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
-        raise TypeError("Invalidated dependents require an immutable tuple")
+        raise TypeError("invalidated dependents require an immutable tuple")
     for dependent in self.invalidated_dependents:
         _text(dependent)
     _text(self.actor_ref)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.

## custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_29

```diff
# custom_components.heima.v3.contracts.generations.xǁComposedGenerationManifestǁ__post_init____mutmut_29: survived
--- custom_components/heima/v3/contracts/generations.py
+++ custom_components/heima/v3/contracts/generations.py
@@ -12,7 +12,7 @@
         raise ValueError("Manifest requires every layer once in canonical order")
     _text(self.impact_fingerprint)
     if type(self.invalidated_dependents) is not tuple:
-        raise TypeError("Invalidated dependents require an immutable tuple")
+        raise TypeError("INVALIDATED DEPENDENTS REQUIRE AN IMMUTABLE TUPLE")
     for dependent in self.invalidated_dependents:
         _text(dependent)
     _text(self.actor_ref)
```

Equivalent: generic exception wording only; rejection and exception class are preserved.
