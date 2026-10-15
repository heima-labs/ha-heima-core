# Fact-type claim mutation review

Fresh mutmut3.8 campaign on fact_types.py and the refactored house_facts.py;
all tests/v3, seed3145, command `.venv-v3/bin/mutmut run --max-children 4`.
380 generated:302 killed,75 equivalent survivors (72 generic-prose,3 zip-strict
variants),3 timeouts; no errors,skips,untested,interrupted. Exact diffs below.

Initial campaign:302 killed,76 survivors,2 timeouts. It exposed a genuine test
gap: replacing continue with break after an equivalent pair skipped later
conflicts. Added test_equivalent_pair_does_not_skip_later_conflicts and restarted
from a fresh mutants directory; this mutant is killed in the final campaign.
No production fix was necessary. Added a finite-product traversal monitor to
catch out-of-domain states/repeated exploration without machine-speed thresholds.

All three timeout mutants are non-equivalent defects, not equivalents. The
campaign may encounter a looping selected test before reaching the guard test.
Reproduced their exact source diffs individually through mutation_fact_types.py,
selecting test_wildcard_search_stays_within_finite_product; all three killed with
pytest exit1. BoundedQueue monitors the mathematical domain and maximum three
outgoing edges per product state, not a product limit on pattern length/time.

Supplements:2 new frozen/slots mutants +3 timeout diffs killed after a clean
91-test baseline. Re-ran all11 existing HouseFact semantic supplements after its
refactor, clean110-test baseline. Command `.venv-v3/bin/python
 tests/v3/mutation_fact_types.py` and equivalent mutation_house_facts.py runner.
The final a/b monitor row was added after the 380-mutant campaign to kill the
third timeout deterministically; the source did not change. Its first targeted
probe passed all three older guard rows, so that attempted kill was rejected
and the independent unequal-literal row added before the successful rerun.
No collection/no-selection or passing mutant result counted as a kill. Production type alias
FactEmissionKind is not independently executable: runtime vocabulary validation
is exercised by state/event acceptance and unknown-kind rejection.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_3

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,6 +1,6 @@
 def _segments(pattern: str) -> tuple[str, ...]:
     if type(pattern) is not str:
-        raise TypeError("Fact identifiers require primitive strings")
+        raise TypeError(None)
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
         raise ValueError("Fact identifiers require nonempty dotted segments")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,6 +1,6 @@
 def _segments(pattern: str) -> tuple[str, ...]:
     if type(pattern) is not str:
-        raise TypeError("Fact identifiers require primitive strings")
+        raise TypeError("XXFact identifiers require primitive stringsXX")
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
         raise ValueError("Fact identifiers require nonempty dotted segments")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_5

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,6 +1,6 @@
 def _segments(pattern: str) -> tuple[str, ...]:
     if type(pattern) is not str:
-        raise TypeError("Fact identifiers require primitive strings")
+        raise TypeError("fact identifiers require primitive strings")
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
         raise ValueError("Fact identifiers require nonempty dotted segments")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_6

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,6 +1,6 @@
 def _segments(pattern: str) -> tuple[str, ...]:
     if type(pattern) is not str:
-        raise TypeError("Fact identifiers require primitive strings")
+        raise TypeError("FACT IDENTIFIERS REQUIRE PRIMITIVE STRINGS")
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
         raise ValueError("Fact identifiers require nonempty dotted segments")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -2,4 +2,4 @@
     """Validate one concrete identifier, never a wildcard claim."""
     _segments(fact_type)
     if "*" in fact_type:
-        raise ValueError("Concrete fact identifiers cannot contain wildcards")
+        raise ValueError(None)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_5

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -2,4 +2,4 @@
     """Validate one concrete identifier, never a wildcard claim."""
     _segments(fact_type)
     if "*" in fact_type:
-        raise ValueError("Concrete fact identifiers cannot contain wildcards")
+        raise ValueError("XXConcrete fact identifiers cannot contain wildcardsXX")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_6

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -2,4 +2,4 @@
     """Validate one concrete identifier, never a wildcard claim."""
     _segments(fact_type)
     if "*" in fact_type:
-        raise ValueError("Concrete fact identifiers cannot contain wildcards")
+        raise ValueError("concrete fact identifiers cannot contain wildcards")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_7

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type__mutmut_7: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -2,4 +2,4 @@
     """Validate one concrete identifier, never a wildcard claim."""
     _segments(fact_type)
     if "*" in fact_type:
-        raise ValueError("Concrete fact identifiers cannot contain wildcards")
+        raise ValueError("CONCRETE FACT IDENTIFIERS CANNOT CONTAIN WILDCARDS")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,7 +1,7 @@
 def __post_init__(self) -> None:
     _segments(self.fact_type_pattern)
     if type(self.owner_id) is not str:
-        raise TypeError("Fact claim owner must be a primitive string")
+        raise TypeError(None)
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_5

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,7 +1,7 @@
 def __post_init__(self) -> None:
     _segments(self.fact_type_pattern)
     if type(self.owner_id) is not str:
-        raise TypeError("Fact claim owner must be a primitive string")
+        raise TypeError("XXFact claim owner must be a primitive stringXX")
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_6

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,7 +1,7 @@
 def __post_init__(self) -> None:
     _segments(self.fact_type_pattern)
     if type(self.owner_id) is not str:
-        raise TypeError("Fact claim owner must be a primitive string")
+        raise TypeError("fact claim owner must be a primitive string")
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_7

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,7 +1,7 @@
 def __post_init__(self) -> None:
     _segments(self.fact_type_pattern)
     if type(self.owner_id) is not str:
-        raise TypeError("Fact claim owner must be a primitive string")
+        raise TypeError("FACT CLAIM OWNER MUST BE A PRIMITIVE STRING")
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_11

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_11: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -4,6 +4,6 @@
         raise TypeError("Fact claim owner must be a primitive string")
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
-        raise TypeError("Fact emission kind must be a primitive string")
+        raise TypeError(None)
     if self.emission_kind not in ("state", "event"):
         raise ValueError("Unknown fact emission kind")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_12

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -4,6 +4,6 @@
         raise TypeError("Fact claim owner must be a primitive string")
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
-        raise TypeError("Fact emission kind must be a primitive string")
+        raise TypeError("XXFact emission kind must be a primitive stringXX")
     if self.emission_kind not in ("state", "event"):
         raise ValueError("Unknown fact emission kind")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_13

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_13: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -4,6 +4,6 @@
         raise TypeError("Fact claim owner must be a primitive string")
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
-        raise TypeError("Fact emission kind must be a primitive string")
+        raise TypeError("fact emission kind must be a primitive string")
     if self.emission_kind not in ("state", "event"):
         raise ValueError("Unknown fact emission kind")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_14

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_14: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -4,6 +4,6 @@
         raise TypeError("Fact claim owner must be a primitive string")
     canonical_json_bytes(self.owner_id)
     if type(self.emission_kind) is not str:
-        raise TypeError("Fact emission kind must be a primitive string")
+        raise TypeError("FACT EMISSION KIND MUST BE A PRIMITIVE STRING")
     if self.emission_kind not in ("state", "event"):
         raise ValueError("Unknown fact emission kind")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_20

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_20: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -6,4 +6,4 @@
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
     if self.emission_kind not in ("state", "event"):
-        raise ValueError("Unknown fact emission kind")
+        raise ValueError(None)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_21

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_21: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -6,4 +6,4 @@
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
     if self.emission_kind not in ("state", "event"):
-        raise ValueError("Unknown fact emission kind")
+        raise ValueError("XXUnknown fact emission kindXX")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_22

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_22: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -6,4 +6,4 @@
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
     if self.emission_kind not in ("state", "event"):
-        raise ValueError("Unknown fact emission kind")
+        raise ValueError("unknown fact emission kind")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_23

```diff
# custom_components.heima.v3.contracts.fact_types.xǁFactTypeClaimǁ__post_init____mutmut_23: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -6,4 +6,4 @@
     if type(self.emission_kind) is not str:
         raise TypeError("Fact emission kind must be a primitive string")
     if self.emission_kind not in ("state", "event"):
-        raise ValueError("Unknown fact emission kind")
+        raise ValueError("UNKNOWN FACT EMISSION KIND")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_3

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -5,7 +5,7 @@
     exact state locations, then resolve kind/owner into producer-specific ports.
     """
     if type(claims) is not tuple:
-        raise TypeError("Fact claim validation requires an immutable tuple")
+        raise TypeError(None)
     for claim in claims:
         if type(claim) is not FactTypeClaim:
             raise TypeError("Fact claim validation requires concrete claims")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -5,7 +5,7 @@
     exact state locations, then resolve kind/owner into producer-specific ports.
     """
     if type(claims) is not tuple:
-        raise TypeError("Fact claim validation requires an immutable tuple")
+        raise TypeError("XXFact claim validation requires an immutable tupleXX")
     for claim in claims:
         if type(claim) is not FactTypeClaim:
             raise TypeError("Fact claim validation requires concrete claims")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_5

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -5,7 +5,7 @@
     exact state locations, then resolve kind/owner into producer-specific ports.
     """
     if type(claims) is not tuple:
-        raise TypeError("Fact claim validation requires an immutable tuple")
+        raise TypeError("fact claim validation requires an immutable tuple")
     for claim in claims:
         if type(claim) is not FactTypeClaim:
             raise TypeError("Fact claim validation requires concrete claims")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_6

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -5,7 +5,7 @@
     exact state locations, then resolve kind/owner into producer-specific ports.
     """
     if type(claims) is not tuple:
-        raise TypeError("Fact claim validation requires an immutable tuple")
+        raise TypeError("FACT CLAIM VALIDATION REQUIRES AN IMMUTABLE TUPLE")
     for claim in claims:
         if type(claim) is not FactTypeClaim:
             raise TypeError("Fact claim validation requires concrete claims")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_9

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_9: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -8,7 +8,7 @@
         raise TypeError("Fact claim validation requires an immutable tuple")
     for claim in claims:
         if type(claim) is not FactTypeClaim:
-            raise TypeError("Fact claim validation requires concrete claims")
+            raise TypeError(None)
         FactTypeClaim.__post_init__(claim)
     for left, right in combinations(claims, 2):
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_10

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_10: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -8,7 +8,7 @@
         raise TypeError("Fact claim validation requires an immutable tuple")
     for claim in claims:
         if type(claim) is not FactTypeClaim:
-            raise TypeError("Fact claim validation requires concrete claims")
+            raise TypeError("XXFact claim validation requires concrete claimsXX")
         FactTypeClaim.__post_init__(claim)
     for left, right in combinations(claims, 2):
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_11

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_11: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -8,7 +8,7 @@
         raise TypeError("Fact claim validation requires an immutable tuple")
     for claim in claims:
         if type(claim) is not FactTypeClaim:
-            raise TypeError("Fact claim validation requires concrete claims")
+            raise TypeError("fact claim validation requires concrete claims")
         FactTypeClaim.__post_init__(claim)
     for left, right in combinations(claims, 2):
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_12

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_12: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -8,7 +8,7 @@
         raise TypeError("Fact claim validation requires an immutable tuple")
     for claim in claims:
         if type(claim) is not FactTypeClaim:
-            raise TypeError("Fact claim validation requires concrete claims")
+            raise TypeError("FACT CLAIM VALIDATION REQUIRES CONCRETE CLAIMS")
         FactTypeClaim.__post_init__(claim)
     for left, right in combinations(claims, 2):
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_27

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_27: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -14,4 +14,4 @@
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
             continue
         if fact_type_patterns_overlap(left.fact_type_pattern, right.fact_type_pattern):
-            raise ValueError("Overlapping fact claims disagree on owner or emission kind")
+            raise ValueError(None)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_28

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_28: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -14,4 +14,4 @@
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
             continue
         if fact_type_patterns_overlap(left.fact_type_pattern, right.fact_type_pattern):
-            raise ValueError("Overlapping fact claims disagree on owner or emission kind")
+            raise ValueError("XXOverlapping fact claims disagree on owner or emission kindXX")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_29

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_29: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -14,4 +14,4 @@
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
             continue
         if fact_type_patterns_overlap(left.fact_type_pattern, right.fact_type_pattern):
-            raise ValueError("Overlapping fact claims disagree on owner or emission kind")
+            raise ValueError("overlapping fact claims disagree on owner or emission kind")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_30

```diff
# custom_components.heima.v3.contracts.fact_types.x_validate_fact_type_claims__mutmut_30: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -14,4 +14,4 @@
         if left.owner_id == right.owner_id and left.emission_kind == right.emission_kind:
             continue
         if fact_type_patterns_overlap(left.fact_type_pattern, right.fact_type_pattern):
-            raise ValueError("Overlapping fact claims disagree on owner or emission kind")
+            raise ValueError("OVERLAPPING FACT CLAIMS DISAGREE ON OWNER OR EMISSION KIND")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__patterns_overlap__mutmut_10

```diff
# custom_components.heima.v3.contracts.fact_types.x__patterns_overlap__mutmut_10: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,4 +1,4 @@
 def _patterns_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
     if len(left) != len(right):
         return False
-    return all(_segments_overlap(a, b) for a, b in zip(left, right, strict=True))
+    return all(_segments_overlap(a, b) for a, b in zip(left, right, strict=None))
```

Equivalent: the function already rejects unequal segment counts before zip; strict=None/False/omitted cannot change matching for equal lengths.

## custom_components.heima.v3.contracts.fact_types.x__patterns_overlap__mutmut_13

```diff
# custom_components.heima.v3.contracts.fact_types.x__patterns_overlap__mutmut_13: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,4 +1,4 @@
 def _patterns_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
     if len(left) != len(right):
         return False
-    return all(_segments_overlap(a, b) for a, b in zip(left, right, strict=True))
+    return all(_segments_overlap(a, b) for a, b in zip(left, right, ))
```

Equivalent: the function already rejects unequal segment counts before zip; strict=None/False/omitted cannot change matching for equal lengths.

## custom_components.heima.v3.contracts.fact_types.x__patterns_overlap__mutmut_14

```diff
# custom_components.heima.v3.contracts.fact_types.x__patterns_overlap__mutmut_14: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -1,4 +1,4 @@
 def _patterns_overlap(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
     if len(left) != len(right):
         return False
-    return all(_segments_overlap(a, b) for a, b in zip(left, right, strict=True))
+    return all(_segments_overlap(a, b) for a, b in zip(left, right, strict=False))
```

Equivalent: the function already rejects unequal segment counts before zip; strict=None/False/omitted cannot change matching for equal lengths.

## custom_components.heima.v3.contracts.fact_types.x__segments_overlap__mutmut_10

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments_overlap__mutmut_10: timeout
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -9,7 +9,7 @@
         state = (i, j)
         if state in visited:
             continue
-        visited.add(state)
+        visited.add(None)
         if i == len(left) and j == len(right):
             return True
         a = left[i] if i < len(left) else None
```

Non-equivalent termination defect. Killed by the matching named finite-product supplement (pytest exit1), not waived as equivalent.

## custom_components.heima.v3.contracts.fact_types.x__segments_overlap__mutmut_33

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments_overlap__mutmut_33: timeout
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -18,7 +18,7 @@
             pending.append((i + 1, j))
         if b == "*":
             pending.append((i, j + 1))
-        if a is None or b is None:
+        if a is None and b is None:
             continue
         if a == "*" or b == "*" or a == b:
             pending.append((i if a == "*" else i + 1, j if b == "*" else j + 1))
```

Non-equivalent termination defect. Killed by the matching named finite-product supplement (pytest exit1), not waived as equivalent.

## custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_1

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_1: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError(None)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_2

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_2: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError("XXConstruct provenance through build_house_factXX")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_3

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_3: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError("construct provenance through build_house_fact")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_4

```diff
# custom_components.heima.v3.contracts.house_facts.xǁProvenanceǁ__init____mutmut_4: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct provenance through build_house_fact")
+    raise TypeError("CONSTRUCT PROVENANCE THROUGH BUILD_HOUSE_FACT")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_1

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_1: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError(None)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_2

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_2: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError("XXConstruct facts through build_house_factXX")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_3

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_3: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError("construct facts through build_house_fact")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_4

```diff
# custom_components.heima.v3.contracts.house_facts.xǁHouseFactǁ__init____mutmut_4: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Construct facts through build_house_fact")
+    raise TypeError("CONSTRUCT FACTS THROUGH BUILD_HOUSE_FACT")
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_3

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_4

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_5

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_6

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_9

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_10

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_11

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_12

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_16

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_17

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_18

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_19

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_25

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_26

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_27

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x__confidence_pair__mutmut_28

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_10

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_10: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -19,7 +19,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError(None)
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_11

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_11: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -19,7 +19,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError("XXFact location must be a LocationXX")
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_12

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_12: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -19,7 +19,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError("fact location must be a location")
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_13

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_13: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -19,7 +19,7 @@
     parse_instant(when)
     _confidence_pair(confidence, available)
     if not isinstance(where, Location):
-        raise TypeError("Fact location must be a Location")
+        raise TypeError("FACT LOCATION MUST BE A LOCATION")
     location = Location(where.scope, where.room_id, where.zone_id, where.room_ids)
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_30

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_30: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -24,7 +24,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError(None)
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_31

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_31: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -24,7 +24,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError("XXA fact requires a fact-side sourceXX")
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_32

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_32: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -24,7 +24,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError("a fact requires a fact-side source")
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_33

```diff
# custom_components.heima.v3.contracts.house_facts.x_build_house_fact__mutmut_33: survived
--- custom_components/heima/v3/contracts/house_facts.py
+++ custom_components/heima/v3/contracts/house_facts.py
@@ -24,7 +24,7 @@
     location_key_json(location)
     validate_runtime_source_shape(source, test_mode=test_mode)
     if type(source) is not FactSource:
-        raise TypeError("A fact requires a fact-side source")
+        raise TypeError("A FACT REQUIRES A FACT-SIDE SOURCE")
     owned_source = FactSource(
         source.kind,
         source.source_id,
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_3

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_4

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_5

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.house_facts.x_house_fact_canonical_bytes__mutmut_6

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

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_13

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_13: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -3,6 +3,6 @@
         raise TypeError("Fact identifiers require primitive strings")
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
-        raise ValueError("Fact identifiers require nonempty dotted segments")
+        raise ValueError(None)
     canonical_json_bytes(pattern)
     return segments
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_14

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_14: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -3,6 +3,6 @@
         raise TypeError("Fact identifiers require primitive strings")
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
-        raise ValueError("Fact identifiers require nonempty dotted segments")
+        raise ValueError("XXFact identifiers require nonempty dotted segmentsXX")
     canonical_json_bytes(pattern)
     return segments
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_15

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_15: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -3,6 +3,6 @@
         raise TypeError("Fact identifiers require primitive strings")
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
-        raise ValueError("Fact identifiers require nonempty dotted segments")
+        raise ValueError("fact identifiers require nonempty dotted segments")
     canonical_json_bytes(pattern)
     return segments
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_16

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments__mutmut_16: survived
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -3,6 +3,6 @@
         raise TypeError("Fact identifiers require primitive strings")
     segments = tuple(pattern.split("."))
     if any(not segment for segment in segments):
-        raise ValueError("Fact identifiers require nonempty dotted segments")
+        raise ValueError("FACT IDENTIFIERS REQUIRE NONEMPTY DOTTED SEGMENTS")
     canonical_json_bytes(pattern)
     return segments
```

Equivalent: only generic exception prose changes; exception class and rejection behavior are preserved.

## custom_components.heima.v3.contracts.fact_types.x__segments_overlap__mutmut_28

```diff
# custom_components.heima.v3.contracts.fact_types.x__segments_overlap__mutmut_28: timeout
--- custom_components/heima/v3/contracts/fact_types.py
+++ custom_components/heima/v3/contracts/fact_types.py
@@ -16,7 +16,7 @@
         b = right[j] if j < len(right) else None
         if a == "*":
             pending.append((i + 1, j))
-        if b == "*":
+        if b != "*":
             pending.append((i, j + 1))
         if a is None or b is None:
             continue
```

Non-equivalent out-of-domain epsilon transition. Killed by epsilon_on_literal supplement and named finite-product test (pytest exit1).
