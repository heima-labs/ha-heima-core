# Location — mutation review, 2026-10-15

Fresh mutmut3.8, native Python3.14.5, only contracts/location.py, all tests/v3,
seed3145, four children: **177 generated,119 killed,58 survived; zero timeout,
error, skipped, untested or interrupted.** Every survivor inspected below:
56 generic error-prose variants, one equivalent guarded-key branch widening,
one UTF-8 codec-name case variant. No raw 100% score claim. Existing modules'
mutation evidence was not refreshed; permanent default scope grows20→21modules.

Five semantic supplements killed after a clean114-test baseline: removing frozen,
removing slots, UTF-16 sorting for the semantic room set, equality ignoring IDs,
and hash ignoring IDs. Each runs its named behavioral test and requires pytest
exit1; collection errors or zero selected tests do not count. Frozen/slots decorator
flags are not normally function mutants. No application constants were excluded.

Reproduction from fresh source/tests copy with scoped pyproject only_mutate:

```bash
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
.venv-v3/bin/mutmut show '<full id>'
.venv-v3/bin/python tests/v3/mutation_location.py
```

Run /private/tmp/heima-v3-location/mutants; log /private/tmp/heima-location-mutmut.log.
Temporary artifacts are supplementary; exact diffs/proofs are retained here.

## Individually inspected survivors

### x__identifier__mutmut_3

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Equivalent wider candidate branch: all items are already validated nonempty strings. Keys with scope rooms and fewer than three entries still fail Location cardinality; other scopes with three or more entries can enter the branch but the final result.key == key comparison cannot pass because its leading scope is rooms. Correctly shaped casa/room/zone already returned earlier. Exactly the same keys succeed; all additionally visited inputs still raise ValueError. Only generic rejection prose/extra work on invalid keys differs, not an observable domain rule.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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
     return canonical_json_bytes(location.key).decode("utf-8")
```

### x_location_key_json__mutmut_3

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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
     return canonical_json_bytes(location.key).decode("utf-8")
```

### x_location_key_json__mutmut_4

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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
     return canonical_json_bytes(location.key).decode("utf-8")
```

### x_location_key_json__mutmut_5

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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
     return canonical_json_bytes(location.key).decode("utf-8")
```

### x_location_key_json__mutmut_9

UTF-8 and utf-8 name the same Python codec. The same canonical bytes decode to identical text and errors.

```diff
# custom_components.heima.v3.contracts.location.x_location_key_json__mutmut_9: survived
--- custom_components/heima/v3/contracts/location.py
+++ custom_components/heima/v3/contracts/location.py
@@ -2,4 +2,4 @@
     """Canonical scalar key text for identity storage and follow-up projections."""
     if not isinstance(location, Location):
         raise TypeError("Location key encoding requires a Location")
-    return canonical_json_bytes(location.key).decode("utf-8")
+    return canonical_json_bytes(location.key).decode("UTF-8")
```

### x_location_from_key_json__mutmut_3

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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

Generic exception prose only; type, rejected input, identity/hash, serialization and result are unchanged. No public message-text contract exists.

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
