# Producer staging mutation review

Fresh mutmut3.8 campaign: only runtime/producer_staging.py, all tests/v3,
seed3145, `.venv-v3/bin/mutmut run --max-children 4`.
213 generated,149 killed,64 equivalent survivors; zero errors,timeouts,skips,
untested or interrupted. All64 exact diffs below are generic TypeError/ValueError
wording only; no semantic survivor waived.

Initial campaign148killed/65survivors exposed a real test gap: inventory canonical
encoding could disappear while the invalid-room inventory was rejected later as a
missing producer room. Isolated malformed inventory checks with no static claims,
and added independent zone-surrogate input. Production source unchanged. Restarted
with a fresh mutants directory; the canonical_json_bytes(None) mutant is now killed.

23 semantic supplements in tests/v3/mutation_producer_staging.py: omit each of15
reservations, alter a reserved owner/kind, and frozen/slots flags for all3 staging
records. All killed via selected named behavioral tests after a passing focused
baseline. Collection/no-selection is not a kill. Module-level immutable reservation
constants and dataclass decorators lie outside mutmut function mutation scope;
these supplements exercise them explicitly. Default type annotations/Final do not
add an independently executable runtime policy.

## custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_3

```diff
# custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_3: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,4 +1,4 @@
 def _owner(owner_id: str) -> None:
     if type(owner_id) is not str:
-        raise TypeError("Producer owner requires a primitive string")
+        raise TypeError(None)
     canonical_json_bytes(owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_4

```diff
# custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_4: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,4 +1,4 @@
 def _owner(owner_id: str) -> None:
     if type(owner_id) is not str:
-        raise TypeError("Producer owner requires a primitive string")
+        raise TypeError("XXProducer owner requires a primitive stringXX")
     canonical_json_bytes(owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_5

```diff
# custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_5: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,4 +1,4 @@
 def _owner(owner_id: str) -> None:
     if type(owner_id) is not str:
-        raise TypeError("Producer owner requires a primitive string")
+        raise TypeError("producer owner requires a primitive string")
     canonical_json_bytes(owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_6

```diff
# custom_components.heima.v3.runtime.producer_staging.x__owner__mutmut_6: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,4 +1,4 @@
 def _owner(owner_id: str) -> None:
     if type(owner_id) is not str:
-        raise TypeError("Producer owner requires a primitive string")
+        raise TypeError("PRODUCER OWNER REQUIRES A PRIMITIVE STRING")
     canonical_json_bytes(owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_4

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -2,7 +2,7 @@
     validate_fact_type(self.fact_type)
     _owner(self.owner_id)
     if not isinstance(self.where, Location):
-        raise TypeError("Static state claim requires a Location")
+        raise TypeError(None)
     where = Location(
         self.where.scope, self.where.room_id, self.where.zone_id, self.where.room_ids
     )
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_5

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -2,7 +2,7 @@
     validate_fact_type(self.fact_type)
     _owner(self.owner_id)
     if not isinstance(self.where, Location):
-        raise TypeError("Static state claim requires a Location")
+        raise TypeError("XXStatic state claim requires a LocationXX")
     where = Location(
         self.where.scope, self.where.room_id, self.where.zone_id, self.where.room_ids
     )
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_6

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -2,7 +2,7 @@
     validate_fact_type(self.fact_type)
     _owner(self.owner_id)
     if not isinstance(self.where, Location):
-        raise TypeError("Static state claim requires a Location")
+        raise TypeError("static state claim requires a location")
     where = Location(
         self.where.scope, self.where.room_id, self.where.zone_id, self.where.room_ids
     )
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_7

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁStaticStateClaimǁ__post_init____mutmut_7: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -2,7 +2,7 @@
     validate_fact_type(self.fact_type)
     _owner(self.owner_id)
     if not isinstance(self.where, Location):
-        raise TypeError("Static state claim requires a Location")
+        raise TypeError("STATIC STATE CLAIM REQUIRES A LOCATION")
     where = Location(
         self.where.scope, self.where.room_id, self.where.zone_id, self.where.room_ids
     )
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_1

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_1: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Resolve a fact type through composed producer staging")
+    raise TypeError(None)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_2

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_2: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Resolve a fact type through composed producer staging")
+    raise TypeError("XXResolve a fact type through composed producer stagingXX")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_3

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_3: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Resolve a fact type through composed producer staging")
+    raise TypeError("resolve a fact type through composed producer staging")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_4

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁFactTypeBindingǁ__init____mutmut_4: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Resolve a fact type through composed producer staging")
+    raise TypeError("RESOLVE A FACT TYPE THROUGH COMPOSED PRODUCER STAGING")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_1

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_1: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use compose_fact_producers")
+    raise TypeError(None)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_2

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_2: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use compose_fact_producers")
+    raise TypeError("XXUse compose_fact_producersXX")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_3

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_3: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use compose_fact_producers")
+    raise TypeError("use compose_fact_producers")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_4

```diff
# custom_components.heima.v3.runtime.producer_staging.xǁComposedFactProducersǁ__init____mutmut_4: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use compose_fact_producers")
+    raise TypeError("USE COMPOSE_FACT_PRODUCERS")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_8

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_8: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -6,7 +6,7 @@
     for claim in claims:
         if fact_type_matches(claim.fact_type_pattern, fact_type):
             if claim.owner_id != owner_id:
-                raise ValueError("Fact type belongs to another producer owner")
+                raise ValueError(None)
             binding = object.__new__(FactTypeBinding)
             object.__setattr__(binding, "fact_type", fact_type)
             object.__setattr__(binding, "owner_id", owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_9

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_9: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -6,7 +6,7 @@
     for claim in claims:
         if fact_type_matches(claim.fact_type_pattern, fact_type):
             if claim.owner_id != owner_id:
-                raise ValueError("Fact type belongs to another producer owner")
+                raise ValueError("XXFact type belongs to another producer ownerXX")
             binding = object.__new__(FactTypeBinding)
             object.__setattr__(binding, "fact_type", fact_type)
             object.__setattr__(binding, "owner_id", owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_10

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_10: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -6,7 +6,7 @@
     for claim in claims:
         if fact_type_matches(claim.fact_type_pattern, fact_type):
             if claim.owner_id != owner_id:
-                raise ValueError("Fact type belongs to another producer owner")
+                raise ValueError("fact type belongs to another producer owner")
             binding = object.__new__(FactTypeBinding)
             object.__setattr__(binding, "fact_type", fact_type)
             object.__setattr__(binding, "owner_id", owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_11

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_11: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -6,7 +6,7 @@
     for claim in claims:
         if fact_type_matches(claim.fact_type_pattern, fact_type):
             if claim.owner_id != owner_id:
-                raise ValueError("Fact type belongs to another producer owner")
+                raise ValueError("FACT TYPE BELONGS TO ANOTHER PRODUCER OWNER")
             binding = object.__new__(FactTypeBinding)
             object.__setattr__(binding, "fact_type", fact_type)
             object.__setattr__(binding, "owner_id", owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_38

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_38: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -12,4 +12,4 @@
             object.__setattr__(binding, "owner_id", owner_id)
             object.__setattr__(binding, "emission_kind", claim.emission_kind)
             return binding
-    raise ValueError("Fact type has no composed producer claim")
+    raise ValueError(None)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_39

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_39: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -12,4 +12,4 @@
             object.__setattr__(binding, "owner_id", owner_id)
             object.__setattr__(binding, "emission_kind", claim.emission_kind)
             return binding
-    raise ValueError("Fact type has no composed producer claim")
+    raise ValueError("XXFact type has no composed producer claimXX")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_40

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_40: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -12,4 +12,4 @@
             object.__setattr__(binding, "owner_id", owner_id)
             object.__setattr__(binding, "emission_kind", claim.emission_kind)
             return binding
-    raise ValueError("Fact type has no composed producer claim")
+    raise ValueError("fact type has no composed producer claim")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_41

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_type__mutmut_41: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -12,4 +12,4 @@
             object.__setattr__(binding, "owner_id", owner_id)
             object.__setattr__(binding, "emission_kind", claim.emission_kind)
             return binding
-    raise ValueError("Fact type has no composed producer claim")
+    raise ValueError("FACT TYPE HAS NO COMPOSED PRODUCER CLAIM")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_3

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_3: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,6 +1,6 @@
 def _inventory(ids: frozenset[str]) -> None:
     if type(ids) is not frozenset:
-        raise TypeError("Producer location inventory requires a frozenset")
+        raise TypeError(None)
     for identifier in ids:
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_4

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_4: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,6 +1,6 @@
 def _inventory(ids: frozenset[str]) -> None:
     if type(ids) is not frozenset:
-        raise TypeError("Producer location inventory requires a frozenset")
+        raise TypeError("XXProducer location inventory requires a frozensetXX")
     for identifier in ids:
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_5

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_5: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,6 +1,6 @@
 def _inventory(ids: frozenset[str]) -> None:
     if type(ids) is not frozenset:
-        raise TypeError("Producer location inventory requires a frozenset")
+        raise TypeError("producer location inventory requires a frozenset")
     for identifier in ids:
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_6

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_6: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,6 +1,6 @@
 def _inventory(ids: frozenset[str]) -> None:
     if type(ids) is not frozenset:
-        raise TypeError("Producer location inventory requires a frozenset")
+        raise TypeError("PRODUCER LOCATION INVENTORY REQUIRES A FROZENSET")
     for identifier in ids:
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_9

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_9: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -3,7 +3,7 @@
         raise TypeError("Producer location inventory requires a frozenset")
     for identifier in ids:
         if type(identifier) is not str:
-            raise TypeError("Producer inventory identifiers must be primitive strings")
+            raise TypeError(None)
         if not identifier:
             raise ValueError("Producer inventory identifiers must be nonempty")
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_10

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_10: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -3,7 +3,7 @@
         raise TypeError("Producer location inventory requires a frozenset")
     for identifier in ids:
         if type(identifier) is not str:
-            raise TypeError("Producer inventory identifiers must be primitive strings")
+            raise TypeError("XXProducer inventory identifiers must be primitive stringsXX")
         if not identifier:
             raise ValueError("Producer inventory identifiers must be nonempty")
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_11

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_11: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -3,7 +3,7 @@
         raise TypeError("Producer location inventory requires a frozenset")
     for identifier in ids:
         if type(identifier) is not str:
-            raise TypeError("Producer inventory identifiers must be primitive strings")
+            raise TypeError("producer inventory identifiers must be primitive strings")
         if not identifier:
             raise ValueError("Producer inventory identifiers must be nonempty")
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_12

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_12: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -3,7 +3,7 @@
         raise TypeError("Producer location inventory requires a frozenset")
     for identifier in ids:
         if type(identifier) is not str:
-            raise TypeError("Producer inventory identifiers must be primitive strings")
+            raise TypeError("PRODUCER INVENTORY IDENTIFIERS MUST BE PRIMITIVE STRINGS")
         if not identifier:
             raise ValueError("Producer inventory identifiers must be nonempty")
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_14

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_14: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -5,5 +5,5 @@
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
         if not identifier:
-            raise ValueError("Producer inventory identifiers must be nonempty")
+            raise ValueError(None)
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_15

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_15: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -5,5 +5,5 @@
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
         if not identifier:
-            raise ValueError("Producer inventory identifiers must be nonempty")
+            raise ValueError("XXProducer inventory identifiers must be nonemptyXX")
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_16

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_16: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -5,5 +5,5 @@
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
         if not identifier:
-            raise ValueError("Producer inventory identifiers must be nonempty")
+            raise ValueError("producer inventory identifiers must be nonempty")
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_17

```diff
# custom_components.heima.v3.runtime.producer_staging.x__inventory__mutmut_17: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -5,5 +5,5 @@
         if type(identifier) is not str:
             raise TypeError("Producer inventory identifiers must be primitive strings")
         if not identifier:
-            raise ValueError("Producer inventory identifiers must be nonempty")
+            raise ValueError("PRODUCER INVENTORY IDENTIFIERS MUST BE NONEMPTY")
     canonical_json_bytes(sorted(ids))
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_5

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_5: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,7 +1,7 @@
 def _resolve_location(where: Location, rooms: frozenset[str], zones: frozenset[str]) -> None:
     if where.scope == "room":
         if where.room_id not in rooms:
-            raise ValueError("Producer room is not registered")
+            raise ValueError(None)
     elif where.scope == "zone":
         if where.zone_id not in zones:
             raise ValueError("Producer zone is not registered")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_6

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_6: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,7 +1,7 @@
 def _resolve_location(where: Location, rooms: frozenset[str], zones: frozenset[str]) -> None:
     if where.scope == "room":
         if where.room_id not in rooms:
-            raise ValueError("Producer room is not registered")
+            raise ValueError("XXProducer room is not registeredXX")
     elif where.scope == "zone":
         if where.zone_id not in zones:
             raise ValueError("Producer zone is not registered")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_7

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_7: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,7 +1,7 @@
 def _resolve_location(where: Location, rooms: frozenset[str], zones: frozenset[str]) -> None:
     if where.scope == "room":
         if where.room_id not in rooms:
-            raise ValueError("Producer room is not registered")
+            raise ValueError("producer room is not registered")
     elif where.scope == "zone":
         if where.zone_id not in zones:
             raise ValueError("Producer zone is not registered")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_8

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_8: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -1,7 +1,7 @@
 def _resolve_location(where: Location, rooms: frozenset[str], zones: frozenset[str]) -> None:
     if where.scope == "room":
         if where.room_id not in rooms:
-            raise ValueError("Producer room is not registered")
+            raise ValueError("PRODUCER ROOM IS NOT REGISTERED")
     elif where.scope == "zone":
         if where.zone_id not in zones:
             raise ValueError("Producer zone is not registered")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_13

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_13: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -4,7 +4,7 @@
             raise ValueError("Producer room is not registered")
     elif where.scope == "zone":
         if where.zone_id not in zones:
-            raise ValueError("Producer zone is not registered")
+            raise ValueError(None)
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_14

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_14: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -4,7 +4,7 @@
             raise ValueError("Producer room is not registered")
     elif where.scope == "zone":
         if where.zone_id not in zones:
-            raise ValueError("Producer zone is not registered")
+            raise ValueError("XXProducer zone is not registeredXX")
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_15

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_15: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -4,7 +4,7 @@
             raise ValueError("Producer room is not registered")
     elif where.scope == "zone":
         if where.zone_id not in zones:
-            raise ValueError("Producer zone is not registered")
+            raise ValueError("producer zone is not registered")
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_16

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_16: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -4,7 +4,7 @@
             raise ValueError("Producer room is not registered")
     elif where.scope == "zone":
         if where.zone_id not in zones:
-            raise ValueError("Producer zone is not registered")
+            raise ValueError("PRODUCER ZONE IS NOT REGISTERED")
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_23

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_23: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -8,4 +8,4 @@
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
-            raise ValueError("Producer rooms are not all registered")
+            raise ValueError(None)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_24

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_24: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -8,4 +8,4 @@
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
-            raise ValueError("Producer rooms are not all registered")
+            raise ValueError("XXProducer rooms are not all registeredXX")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_25

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_25: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -8,4 +8,4 @@
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
-            raise ValueError("Producer rooms are not all registered")
+            raise ValueError("producer rooms are not all registered")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_26

```diff
# custom_components.heima.v3.runtime.producer_staging.x__resolve_location__mutmut_26: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -8,4 +8,4 @@
     elif where.scope == "rooms":
         assert where.room_ids is not None
         if not where.room_ids.issubset(rooms):
-            raise ValueError("Producer rooms are not all registered")
+            raise ValueError("PRODUCER ROOMS ARE NOT ALL REGISTERED")
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_4

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_4: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -13,7 +13,7 @@
     """
     validate_fact_type_claims(type_claims)
     if type(state_claims) is not tuple:
-        raise TypeError("Static state claim snapshot requires a tuple")
+        raise TypeError(None)
     _inventory(room_ids)
     _inventory(zone_ids)
     claims = CORE_FACT_TYPE_CLAIMS + tuple(
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_5

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_5: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -13,7 +13,7 @@
     """
     validate_fact_type_claims(type_claims)
     if type(state_claims) is not tuple:
-        raise TypeError("Static state claim snapshot requires a tuple")
+        raise TypeError("XXStatic state claim snapshot requires a tupleXX")
     _inventory(room_ids)
     _inventory(zone_ids)
     claims = CORE_FACT_TYPE_CLAIMS + tuple(
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_6

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_6: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -13,7 +13,7 @@
     """
     validate_fact_type_claims(type_claims)
     if type(state_claims) is not tuple:
-        raise TypeError("Static state claim snapshot requires a tuple")
+        raise TypeError("static state claim snapshot requires a tuple")
     _inventory(room_ids)
     _inventory(zone_ids)
     claims = CORE_FACT_TYPE_CLAIMS + tuple(
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_7

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_7: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -13,7 +13,7 @@
     """
     validate_fact_type_claims(type_claims)
     if type(state_claims) is not tuple:
-        raise TypeError("Static state claim snapshot requires a tuple")
+        raise TypeError("STATIC STATE CLAIM SNAPSHOT REQUIRES A TUPLE")
     _inventory(room_ids)
     _inventory(zone_ids)
     claims = CORE_FACT_TYPE_CLAIMS + tuple(
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_24

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_24: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -25,7 +25,7 @@
     seen: set[tuple[str, Location]] = set()
     for state in state_claims:
         if type(state) is not StaticStateClaim:
-            raise TypeError("Static producer composition requires concrete state claims")
+            raise TypeError(None)
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_25

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_25: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -25,7 +25,7 @@
     seen: set[tuple[str, Location]] = set()
     for state in state_claims:
         if type(state) is not StaticStateClaim:
-            raise TypeError("Static producer composition requires concrete state claims")
+            raise TypeError("XXStatic producer composition requires concrete state claimsXX")
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_26

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_26: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -25,7 +25,7 @@
     seen: set[tuple[str, Location]] = set()
     for state in state_claims:
         if type(state) is not StaticStateClaim:
-            raise TypeError("Static producer composition requires concrete state claims")
+            raise TypeError("static producer composition requires concrete state claims")
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_27

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_27: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -25,7 +25,7 @@
     seen: set[tuple[str, Location]] = set()
     for state in state_claims:
         if type(state) is not StaticStateClaim:
-            raise TypeError("Static producer composition requires concrete state claims")
+            raise TypeError("STATIC PRODUCER COMPOSITION REQUIRES CONCRETE STATE CLAIMS")
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_37

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_37: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -29,7 +29,7 @@
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
-            raise ValueError("Duplicate static state producer identity")
+            raise ValueError(None)
         seen.add(key)
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_38

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_38: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -29,7 +29,7 @@
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
-            raise ValueError("Duplicate static state producer identity")
+            raise ValueError("XXDuplicate static state producer identityXX")
         seen.add(key)
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_39

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_39: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -29,7 +29,7 @@
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
-            raise ValueError("Duplicate static state producer identity")
+            raise ValueError("duplicate static state producer identity")
         seen.add(key)
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_40

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_40: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -29,7 +29,7 @@
         owned = StaticStateClaim(state.fact_type, state.where, state.owner_id)
         key = (owned.fact_type, owned.where)
         if key in seen:
-            raise ValueError("Duplicate static state producer identity")
+            raise ValueError("DUPLICATE STATIC STATE PRODUCER IDENTITY")
         seen.add(key)
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_58

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_58: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -34,7 +34,7 @@
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
         if binding.emission_kind != "state":
-            raise ValueError("Static state producer cannot claim an event type")
+            raise ValueError(None)
         accepted.append(owned)
     result = object.__new__(ComposedFactProducers)
     object.__setattr__(result, "type_claims", claims)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_59

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_59: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -34,7 +34,7 @@
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
         if binding.emission_kind != "state":
-            raise ValueError("Static state producer cannot claim an event type")
+            raise ValueError("XXStatic state producer cannot claim an event typeXX")
         accepted.append(owned)
     result = object.__new__(ComposedFactProducers)
     object.__setattr__(result, "type_claims", claims)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_60

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_60: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -34,7 +34,7 @@
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
         if binding.emission_kind != "state":
-            raise ValueError("Static state producer cannot claim an event type")
+            raise ValueError("static state producer cannot claim an event type")
         accepted.append(owned)
     result = object.__new__(ComposedFactProducers)
     object.__setattr__(result, "type_claims", claims)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.

## custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_61

```diff
# custom_components.heima.v3.runtime.producer_staging.x_compose_fact_producers__mutmut_61: survived
--- custom_components/heima/v3/runtime/producer_staging.py
+++ custom_components/heima/v3/runtime/producer_staging.py
@@ -34,7 +34,7 @@
         _resolve_location(owned.where, room_ids, zone_ids)
         binding = _resolve_type(claims, owned.fact_type, owned.owner_id)
         if binding.emission_kind != "state":
-            raise ValueError("Static state producer cannot claim an event type")
+            raise ValueError("STATIC STATE PRODUCER CANNOT CLAIM AN EVENT TYPE")
         accepted.append(owned)
     result = object.__new__(ComposedFactProducers)
     object.__setattr__(result, "type_claims", claims)
```

Equivalent: only generic error prose changes; rejection and exception class are unchanged.
