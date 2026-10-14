# Payload mutant review

Run: mutmut 3.8.0, 265 mutants, 231 killed, 34 survived; no timeout/error/untested.
All survivors reviewed below against the runtime contract; no non-equivalent survivor remains.
Type-cast mutants are runtime equivalent, not necessarily statically type-correct.
Generic exception prose is not part of the public contract; PayloadValidationError.code is.

### custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_6

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_6: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -7,4 +7,4 @@
     try:
         return rfc8785.dumps(_project(value, set()))
     except (rfc8785.CanonicalizationError, UnicodeError) as error:
-        raise ValueError("Payload has no valid RFC-8785 representation") from error
+        raise ValueError(None) from error
```

### custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_7

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_7: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -7,4 +7,4 @@
     try:
         return rfc8785.dumps(_project(value, set()))
     except (rfc8785.CanonicalizationError, UnicodeError) as error:
-        raise ValueError("Payload has no valid RFC-8785 representation") from error
+        raise ValueError("XXPayload has no valid RFC-8785 representationXX") from error
```

### custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_8

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_8: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -7,4 +7,4 @@
     try:
         return rfc8785.dumps(_project(value, set()))
     except (rfc8785.CanonicalizationError, UnicodeError) as error:
-        raise ValueError("Payload has no valid RFC-8785 representation") from error
+        raise ValueError("payload has no valid rfc-8785 representation") from error
```

### custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_9

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x_canonical_json_bytes__mutmut_9: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -7,4 +7,4 @@
     try:
         return rfc8785.dumps(_project(value, set()))
     except (rfc8785.CanonicalizationError, UnicodeError) as error:
-        raise ValueError("Payload has no valid RFC-8785 representation") from error
+        raise ValueError("PAYLOAD HAS NO VALID RFC-8785 REPRESENTATION") from error
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_2

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_2: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -1,6 +1,6 @@
 def _project(value: object, ancestors: set[int]) -> JsonValue:
     if isinstance(value, Enum):
-        raise ValueError("Enum objects are not JSON values")
+        raise ValueError("XXEnum objects are not JSON valuesXX")
     if type(value) in (str, int, float, bool) or value is None:
         return cast(JsonScalar, value)
     identity = id(value)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_9

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_9: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -2,7 +2,7 @@
     if isinstance(value, Enum):
         raise ValueError("Enum objects are not JSON values")
     if type(value) in (str, int, float, bool) or value is None:
-        return cast(JsonScalar, value)
+        return cast(None, value)
     identity = id(value)
     if identity in ancestors:
         raise ValueError("Cyclic collections are not JSON values")
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_17

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_17: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -5,7 +5,7 @@
         return cast(JsonScalar, value)
     identity = id(value)
     if identity in ancestors:
-        raise ValueError("Cyclic collections are not JSON values")
+        raise ValueError("XXCyclic collections are not JSON valuesXX")
     ancestors.add(identity)
     try:
         if isinstance(value, (dict, MappingProxyType)):
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_25

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_25: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -11,7 +11,7 @@
         if isinstance(value, (dict, MappingProxyType)):
             mapping: Mapping[object, object] = value
             if any(type(key) is not str for key in mapping):
-                raise ValueError("JSON object keys must be strings")
+                raise ValueError(None)
             return {cast(str, key): _project(item, ancestors) for key, item in mapping.items()}
         if type(value) in (list, tuple):
             return [
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_26

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_26: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -11,7 +11,7 @@
         if isinstance(value, (dict, MappingProxyType)):
             mapping: Mapping[object, object] = value
             if any(type(key) is not str for key in mapping):
-                raise ValueError("JSON object keys must be strings")
+                raise ValueError("XXJSON object keys must be stringsXX")
             return {cast(str, key): _project(item, ancestors) for key, item in mapping.items()}
         if type(value) in (list, tuple):
             return [
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_27

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_27: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -11,7 +11,7 @@
         if isinstance(value, (dict, MappingProxyType)):
             mapping: Mapping[object, object] = value
             if any(type(key) is not str for key in mapping):
-                raise ValueError("JSON object keys must be strings")
+                raise ValueError("json object keys must be strings")
             return {cast(str, key): _project(item, ancestors) for key, item in mapping.items()}
         if type(value) in (list, tuple):
             return [
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_28

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_28: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -11,7 +11,7 @@
         if isinstance(value, (dict, MappingProxyType)):
             mapping: Mapping[object, object] = value
             if any(type(key) is not str for key in mapping):
-                raise ValueError("JSON object keys must be strings")
+                raise ValueError("JSON OBJECT KEYS MUST BE STRINGS")
             return {cast(str, key): _project(item, ancestors) for key, item in mapping.items()}
         if type(value) in (list, tuple):
             return [
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_29

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_29: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -12,7 +12,7 @@
             mapping: Mapping[object, object] = value
             if any(type(key) is not str for key in mapping):
                 raise ValueError("JSON object keys must be strings")
-            return {cast(str, key): _project(item, ancestors) for key, item in mapping.items()}
+            return {cast(None, key): _project(item, ancestors) for key, item in mapping.items()}
         if type(value) in (list, tuple):
             return [
                 _project(item, ancestors) for item in cast(list[object] | tuple[object, ...], value)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_43

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_43: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -15,7 +15,7 @@
             return {cast(str, key): _project(item, ancestors) for key, item in mapping.items()}
         if type(value) in (list, tuple):
             return [
-                _project(item, ancestors) for item in cast(list[object] | tuple[object, ...], value)
+                _project(item, ancestors) for item in cast(None, value)
             ]
         if is_dataclass(value) and not isinstance(value, type):
             if not cast(_DataclassParameters, getattr(type(value), "__dataclass_params__")).frozen:
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_52

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_52: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -18,7 +18,7 @@
                 _project(item, ancestors) for item in cast(list[object] | tuple[object, ...], value)
             ]
         if is_dataclass(value) and not isinstance(value, type):
-            if not cast(_DataclassParameters, getattr(type(value), "__dataclass_params__")).frozen:
+            if not cast(None, getattr(type(value), "__dataclass_params__")).frozen:
                 raise ValueError("Record must be a frozen dataclass")
             return {
                 field.name: _project(getattr(value, field.name), ancestors)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_64

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_64: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -19,7 +19,7 @@
             ]
         if is_dataclass(value) and not isinstance(value, type):
             if not cast(_DataclassParameters, getattr(type(value), "__dataclass_params__")).frozen:
-                raise ValueError("Record must be a frozen dataclass")
+                raise ValueError("XXRecord must be a frozen dataclassXX")
             return {
                 field.name: _project(getattr(value, field.name), ancestors)
                 for field in fields(value)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_65

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_65: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -19,7 +19,7 @@
             ]
         if is_dataclass(value) and not isinstance(value, type):
             if not cast(_DataclassParameters, getattr(type(value), "__dataclass_params__")).frozen:
-                raise ValueError("Record must be a frozen dataclass")
+                raise ValueError("record must be a frozen dataclass")
             return {
                 field.name: _project(getattr(value, field.name), ancestors)
                 for field in fields(value)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_76

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_76: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -24,6 +24,6 @@
                 field.name: _project(getattr(value, field.name), ancestors)
                 for field in fields(value)
             }
-        raise ValueError("Unsupported JSON value type")
+        raise ValueError(None)
     finally:
         ancestors.remove(identity)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_77

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_77: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -24,6 +24,6 @@
                 field.name: _project(getattr(value, field.name), ancestors)
                 for field in fields(value)
             }
-        raise ValueError("Unsupported JSON value type")
+        raise ValueError("XXUnsupported JSON value typeXX")
     finally:
         ancestors.remove(identity)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_78

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_78: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -24,6 +24,6 @@
                 field.name: _project(getattr(value, field.name), ancestors)
                 for field in fields(value)
             }
-        raise ValueError("Unsupported JSON value type")
+        raise ValueError("unsupported json value type")
     finally:
         ancestors.remove(identity)
```

### custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_79

Contract equivalent: error still rejects the same input with ValueError; generic prose is not a diagnostic code or promised message.

```diff
# custom_components.heima.v3.contracts.canonical_json.x__project__mutmut_79: survived
--- custom_components/heima/v3/contracts/canonical_json.py
+++ custom_components/heima/v3/contracts/canonical_json.py
@@ -24,6 +24,6 @@
                 field.name: _project(getattr(value, field.name), ancestors)
                 for field in fields(value)
             }
-        raise ValueError("Unsupported JSON value type")
+        raise ValueError("UNSUPPORTED JSON VALUE TYPE")
     finally:
         ancestors.remove(identity)
```

### custom_components.heima.v3.contracts.payloads.x_freeze_house_fact_value__mutmut_4

Equivalent: None replaces false for a truth-tested context flag; neither is retained in the result.

```diff
# custom_components.heima.v3.contracts.payloads.x_freeze_house_fact_value__mutmut_4: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -1,6 +1,6 @@
 def freeze_house_fact_value(value: object) -> PreparedPayload:
     """Validate a value and return a detached, deeply frozen representation."""
-    frozen = _freeze(value, 0, record_context=False, allow_record=True)
+    frozen = _freeze(value, 0, record_context=None, allow_record=True)
     encoded = canonical_json_bytes(frozen)
     if len(encoded) > MAX_PAYLOAD_BYTES:
         raise PayloadValidationError(PayloadErrorCode.SIZE)
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_9

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_9: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -6,7 +6,7 @@
         return value
     if value_type is str:
         try:
-            cast(str, value).encode("utf-8")
+            cast(None, value).encode("utf-8")
         except UnicodeError as error:
             raise PayloadValidationError(PayloadErrorCode.UNICODE) from error
         return value
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_14

Equivalent codec alias: UTF-8 and utf-8 are the same Python codec.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_14: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -6,7 +6,7 @@
         return value
     if value_type is str:
         try:
-            cast(str, value).encode("utf-8")
+            cast(str, value).encode("UTF-8")
         except UnicodeError as error:
             raise PayloadValidationError(PayloadErrorCode.UNICODE) from error
         return value
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_20

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_20: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -11,7 +11,7 @@
             raise PayloadValidationError(PayloadErrorCode.UNICODE) from error
         return value
     if value_type is int:
-        if not -MAX_SAFE_INTEGER <= cast(int, value) <= MAX_SAFE_INTEGER:
+        if not -MAX_SAFE_INTEGER <= cast(None, value) <= MAX_SAFE_INTEGER:
             raise PayloadValidationError(PayloadErrorCode.INTEGER)
         return value
     if value_type is float:
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_29

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_29: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -15,7 +15,7 @@
             raise PayloadValidationError(PayloadErrorCode.INTEGER)
         return value
     if value_type is float:
-        if not isfinite(cast(float, value)):
+        if not isfinite(cast(None, value)):
             raise PayloadValidationError(PayloadErrorCode.NONFINITE)
         return value
     if value_type is dict:
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_37

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_37: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -21,7 +21,7 @@
     if value_type is dict:
         _check_depth(depth)
         copied = {}
-        for key, item in cast(dict[object, object], value).items():
+        for key, item in cast(None, value).items():
             if type(key) is not str:
                 raise PayloadValidationError(PayloadErrorCode.TYPE)
             frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_46

Equivalent: key is already an exact str; scalar validation does not depend on collection depth or record flags.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_46: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -24,7 +24,7 @@
         for key, item in cast(dict[object, object], value).items():
             if type(key) is not str:
                 raise PayloadValidationError(PayloadErrorCode.TYPE)
-            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
+            frozen_key = _freeze(key, None, record_context=record_context, allow_record=False)
             copied[frozen_key] = _freeze(
                 item, depth + 1, record_context=record_context, allow_record=record_context
             )
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_47

Equivalent: key is already an exact str; scalar validation does not depend on collection depth or record flags.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_47: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -24,7 +24,7 @@
         for key, item in cast(dict[object, object], value).items():
             if type(key) is not str:
                 raise PayloadValidationError(PayloadErrorCode.TYPE)
-            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
+            frozen_key = _freeze(key, depth + 1, record_context=None, allow_record=False)
             copied[frozen_key] = _freeze(
                 item, depth + 1, record_context=record_context, allow_record=record_context
             )
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_48

Equivalent: key is already an exact str; scalar validation does not depend on collection depth or record flags.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_48: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -24,7 +24,7 @@
         for key, item in cast(dict[object, object], value).items():
             if type(key) is not str:
                 raise PayloadValidationError(PayloadErrorCode.TYPE)
-            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
+            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=None)
             copied[frozen_key] = _freeze(
                 item, depth + 1, record_context=record_context, allow_record=record_context
             )
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_53

Equivalent: key is already an exact str; scalar validation does not depend on collection depth or record flags.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_53: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -24,7 +24,7 @@
         for key, item in cast(dict[object, object], value).items():
             if type(key) is not str:
                 raise PayloadValidationError(PayloadErrorCode.TYPE)
-            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
+            frozen_key = _freeze(key, depth - 1, record_context=record_context, allow_record=False)
             copied[frozen_key] = _freeze(
                 item, depth + 1, record_context=record_context, allow_record=record_context
             )
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_54

Equivalent: key is already an exact str; scalar validation does not depend on collection depth or record flags.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_54: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -24,7 +24,7 @@
         for key, item in cast(dict[object, object], value).items():
             if type(key) is not str:
                 raise PayloadValidationError(PayloadErrorCode.TYPE)
-            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
+            frozen_key = _freeze(key, depth + 2, record_context=record_context, allow_record=False)
             copied[frozen_key] = _freeze(
                 item, depth + 1, record_context=record_context, allow_record=record_context
             )
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_55

Equivalent: key is already an exact str; scalar validation does not depend on collection depth or record flags.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_55: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -24,7 +24,7 @@
         for key, item in cast(dict[object, object], value).items():
             if type(key) is not str:
                 raise PayloadValidationError(PayloadErrorCode.TYPE)
-            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=False)
+            frozen_key = _freeze(key, depth + 1, record_context=record_context, allow_record=True)
             copied[frozen_key] = _freeze(
                 item, depth + 1, record_context=record_context, allow_record=record_context
             )
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_84

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_84: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -33,7 +33,7 @@
         _check_depth(depth)
         return tuple(
             _freeze(item, depth + 1, record_context=record_context, allow_record=record_context)
-            for item in cast(list[object] | tuple[object, ...], value)
+            for item in cast(None, value)
         )
     if allow_record and is_dataclass(value) and not isinstance(value, type):
         if not cast(_DataclassParameters, getattr(value_type, "__dataclass_params__")).frozen:
```

### custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_94

Runtime equivalent: typing.cast returns its second argument unchanged; only static annotation differs.

```diff
# custom_components.heima.v3.contracts.payloads.x__freeze__mutmut_94: survived
--- custom_components/heima/v3/contracts/payloads.py
+++ custom_components/heima/v3/contracts/payloads.py
@@ -36,7 +36,7 @@
             for item in cast(list[object] | tuple[object, ...], value)
         )
     if allow_record and is_dataclass(value) and not isinstance(value, type):
-        if not cast(_DataclassParameters, getattr(value_type, "__dataclass_params__")).frozen:
+        if not cast(None, getattr(value_type, "__dataclass_params__")).frozen:
             raise PayloadValidationError(PayloadErrorCode.TYPE)
         _check_depth(depth)
         # Copy only declared data fields. Do not rerun arbitrary __init__/post-init
```
