# Fact state mutation review

Fresh mutmut 3.8 run, scoped to contracts/fact_state.py, seed3145, all tests/v3.
Command: `.venv-v3/bin/mutmut run --max-children 4`.
95 generated: 79 killed, 16 equivalent survivors, zero errors, timeouts, skipped,
untested or interrupted. All 16 diffs reviewed below; no semantic survivor waived.

Six semantic supplements (tests/v3/mutation_fact_state.py), passing 51-test baseline:
FactIdentityKey and FactChangeFingerprint frozen/slots flags; inspecting unavailable
value; native bool/numeric equality. Each selected test killed its mutant with
pytest exit1 (collection/no-selection is not a kill). No production constant added.
Generated dataclass equality/hash are covered by identity field, Location and hash
fixtures; manual fingerprint equality/hash are in the mutmut function scope.

## custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_1

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_1: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state identity through fact_identity_key")
+    raise TypeError(None)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_2

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_2: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state identity through fact_identity_key")
+    raise TypeError("XXExtract a state identity through fact_identity_keyXX")
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_3

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state identity through fact_identity_key")
+    raise TypeError("extract a state identity through fact_identity_key")
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactIdentityKeyǁ__init____mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state identity through fact_identity_key")
+    raise TypeError("EXTRACT A STATE IDENTITY THROUGH FACT_IDENTITY_KEY")
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_1

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_1: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state fingerprint through fact_change_fingerprint")
+    raise TypeError(None)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_2

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_2: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state fingerprint through fact_change_fingerprint")
+    raise TypeError("XXExtract a state fingerprint through fact_change_fingerprintXX")
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_3

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state fingerprint through fact_change_fingerprint")
+    raise TypeError("extract a state fingerprint through fact_change_fingerprint")
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_state.xǁFactChangeFingerprintǁ__init____mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Extract a state fingerprint through fact_change_fingerprint")
+    raise TypeError("EXTRACT A STATE FINGERPRINT THROUGH FACT_CHANGE_FINGERPRINT")
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_3

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     construction will have its own validated boundary.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State identity requires a concrete HouseFact")
+        raise TypeError(None)
     key = object.__new__(FactIdentityKey)
     object.__setattr__(key, "fact_type", fact.fact_type)
     object.__setattr__(key, "where", fact.where)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     construction will have its own validated boundary.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State identity requires a concrete HouseFact")
+        raise TypeError("XXState identity requires a concrete HouseFactXX")
     key = object.__new__(FactIdentityKey)
     object.__setattr__(key, "fact_type", fact.fact_type)
     object.__setattr__(key, "where", fact.where)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_5

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     construction will have its own validated boundary.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State identity requires a concrete HouseFact")
+        raise TypeError("state identity requires a concrete housefact")
     key = object.__new__(FactIdentityKey)
     object.__setattr__(key, "fact_type", fact.fact_type)
     object.__setattr__(key, "where", fact.where)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_6

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_identity_key__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     construction will have its own validated boundary.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State identity requires a concrete HouseFact")
+        raise TypeError("STATE IDENTITY REQUIRES A CONCRETE HOUSEFACT")
     key = object.__new__(FactIdentityKey)
     object.__setattr__(key, "fact_type", fact.fact_type)
     object.__setattr__(key, "where", fact.where)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_3

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_3: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     and immutable. Unavailable value is undefined and must not even be projected.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State fingerprint requires a concrete HouseFact")
+        raise TypeError(None)
     result = object.__new__(FactChangeFingerprint)
     object.__setattr__(result, "available", fact.how.available)
     object.__setattr__(result, "confidence", fact.how.confidence)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_4

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_4: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     and immutable. Unavailable value is undefined and must not even be projected.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State fingerprint requires a concrete HouseFact")
+        raise TypeError("XXState fingerprint requires a concrete HouseFactXX")
     result = object.__new__(FactChangeFingerprint)
     object.__setattr__(result, "available", fact.how.available)
     object.__setattr__(result, "confidence", fact.how.confidence)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_5

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_5: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     and immutable. Unavailable value is undefined and must not even be projected.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State fingerprint requires a concrete HouseFact")
+        raise TypeError("state fingerprint requires a concrete housefact")
     result = object.__new__(FactChangeFingerprint)
     object.__setattr__(result, "available", fact.how.available)
     object.__setattr__(result, "confidence", fact.how.confidence)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.

## custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_6

```diff
# custom_components.heima.v3.contracts.fact_state.x_fact_change_fingerprint__mutmut_6: survived
--- custom_components/heima/v3/contracts/fact_state.py
+++ custom_components/heima/v3/contracts/fact_state.py
@@ -5,7 +5,7 @@
     and immutable. Unavailable value is undefined and must not even be projected.
     """
     if type(fact) is not HouseFact:
-        raise TypeError("State fingerprint requires a concrete HouseFact")
+        raise TypeError("STATE FINGERPRINT REQUIRES A CONCRETE HOUSEFACT")
     result = object.__new__(FactChangeFingerprint)
     object.__setattr__(result, "available", fact.how.available)
     object.__setattr__(result, "confidence", fact.how.confidence)
```

Equivalent: changes only generic TypeError prose; exception class and rejection remain unchanged.
