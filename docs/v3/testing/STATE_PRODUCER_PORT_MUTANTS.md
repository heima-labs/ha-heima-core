# State producer port mutation review

Verified fresh mutmut3.8 run: only runtime/state_producers.py, all tests/v3,
seed3145, `.venv-v3/bin/mutmut run --max-children 4`.
226generated,161killed,65equivalent survivors (60 generic prose,3 redundant optional
validation fields,2 discarded opaque placeholder variants). Zero errors,timeouts,
skipped,untested,interrupted. Every survivor diff and proof is below.

Earlier campaigns are discarded evidence, not merged into final counts. They
recorded6 and7 timeouts; a focused clean property run then reproduced a Hypothesis
FlakyFailure from its default200ms execution deadline (393.79ms versus2.19ms for
the same case). Disabled deadline only for the two new functional properties,
retaining examples/seed/shrinking. These tests specify semantics, not throughput.
Restarted fresh; verified run has zero timeouts and no flaky test failure.

Initial inspection also found a non-equivalent surviving default-UUID seed in the
staging-only validation object. Strengthened the no-UUID test to patch before
staging as well as build; production already passed the placeholder explicitly.
The final campaign kills that mutant. No production behavior change needed.

12 semantic supplements in tests/v3/mutation_state_producers.py, clean22-test
baseline:6 immutable/slots decorators, pre/post fence omission, value equality in
place of snapshot identity, omitted-versus-None evidence, mutable registration map,
and lost diagnostics. All killed by selected named behavioral tests with pytest
exit1; collection errors/no-selection/passing mutants are not counted as kills.
Module-level omission sentinel and decorators lie outside mutmut function scope.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_3

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.claim) is not StaticStateClaim:
-        raise TypeError("Fixed-source producer requires a concrete static claim")
+        raise TypeError(None)
     if type(self.source) is not FactSourceFingerprint:
         raise TypeError("Fixed-source producer requires a source fingerprint")
     FactSourceFingerprint.__post_init__(self.source)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.claim) is not StaticStateClaim:
-        raise TypeError("Fixed-source producer requires a concrete static claim")
+        raise TypeError("XXFixed-source producer requires a concrete static claimXX")
     if type(self.source) is not FactSourceFingerprint:
         raise TypeError("Fixed-source producer requires a source fingerprint")
     FactSourceFingerprint.__post_init__(self.source)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_5

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.claim) is not StaticStateClaim:
-        raise TypeError("Fixed-source producer requires a concrete static claim")
+        raise TypeError("fixed-source producer requires a concrete static claim")
     if type(self.source) is not FactSourceFingerprint:
         raise TypeError("Fixed-source producer requires a source fingerprint")
     FactSourceFingerprint.__post_init__(self.source)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_6

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.claim) is not StaticStateClaim:
-        raise TypeError("Fixed-source producer requires a concrete static claim")
+        raise TypeError("FIXED-SOURCE PRODUCER REQUIRES A CONCRETE STATIC CLAIM")
     if type(self.source) is not FactSourceFingerprint:
         raise TypeError("Fixed-source producer requires a source fingerprint")
     FactSourceFingerprint.__post_init__(self.source)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_9

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -2,7 +2,7 @@
     if type(self.claim) is not StaticStateClaim:
         raise TypeError("Fixed-source producer requires a concrete static claim")
     if type(self.source) is not FactSourceFingerprint:
-        raise TypeError("Fixed-source producer requires a source fingerprint")
+        raise TypeError(None)
     FactSourceFingerprint.__post_init__(self.source)
     source = self.source
     validate_runtime_source_shape(
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_10

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_10: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -2,7 +2,7 @@
     if type(self.claim) is not StaticStateClaim:
         raise TypeError("Fixed-source producer requires a concrete static claim")
     if type(self.source) is not FactSourceFingerprint:
-        raise TypeError("Fixed-source producer requires a source fingerprint")
+        raise TypeError("XXFixed-source producer requires a source fingerprintXX")
     FactSourceFingerprint.__post_init__(self.source)
     source = self.source
     validate_runtime_source_shape(
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_11

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_11: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -2,7 +2,7 @@
     if type(self.claim) is not StaticStateClaim:
         raise TypeError("Fixed-source producer requires a concrete static claim")
     if type(self.source) is not FactSourceFingerprint:
-        raise TypeError("Fixed-source producer requires a source fingerprint")
+        raise TypeError("fixed-source producer requires a source fingerprint")
     FactSourceFingerprint.__post_init__(self.source)
     source = self.source
     validate_runtime_source_shape(
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_12

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -2,7 +2,7 @@
     if type(self.claim) is not StaticStateClaim:
         raise TypeError("Fixed-source producer requires a concrete static claim")
     if type(self.source) is not FactSourceFingerprint:
-        raise TypeError("Fixed-source producer requires a source fingerprint")
+        raise TypeError("FIXED-SOURCE PRODUCER REQUIRES A SOURCE FINGERPRINT")
     FactSourceFingerprint.__post_init__(self.source)
     source = self.source
     validate_runtime_source_shape(
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_18

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_18: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -9,7 +9,7 @@
         FactSource(
             source.kind,
             source.source_id,
-            source.source_type,
+            None,
             source.configuration_fingerprint,
             source.route_fingerprint,
             source.actor_type,
```

Equivalent: optional fields are already validated on the original fingerprint. This temporary FactSource is used only for production kind/actor mode validation, then discarded; the original source is separately canonical-encoded and copied unchanged into the actual profile.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_19

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_19: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
             source.kind,
             source.source_id,
             source.source_type,
-            source.configuration_fingerprint,
+            None,
             source.route_fingerprint,
             source.actor_type,
             correlation_id="staging",
```

Equivalent: optional fields are already validated on the original fingerprint. This temporary FactSource is used only for production kind/actor mode validation, then discarded; the original source is separately canonical-encoded and copied unchanged into the actual profile.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_20

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_20: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -11,7 +11,7 @@
             source.source_id,
             source.source_type,
             source.configuration_fingerprint,
-            source.route_fingerprint,
+            None,
             source.actor_type,
             correlation_id="staging",
         )
```

Equivalent: optional fields are already validated on the original fingerprint. This temporary FactSource is used only for production kind/actor mode validation, then discarded; the original source is separately canonical-encoded and copied unchanged into the actual profile.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_30

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_30: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -13,7 +13,7 @@
             source.configuration_fingerprint,
             source.route_fingerprint,
             source.actor_type,
-            correlation_id="staging",
+            correlation_id="XXstagingXX",
         )
     )
     canonical_json_bytes(source)
```

Equivalent: a different explicit opaque staging placeholder is validated and discarded. It is never a causal origin, persisted record or emitted source; runtime correlation is a separate explicit argument. Removing the explicit placeholder (UUID fallback) is non-equivalent and is killed by the strengthened no-UUID test.

## custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_31

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedStateProducerRegistrationǁ__post_init____mutmut_31: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -13,7 +13,7 @@
             source.configuration_fingerprint,
             source.route_fingerprint,
             source.actor_type,
-            correlation_id="staging",
+            correlation_id="STAGING",
         )
     )
     canonical_json_bytes(source)
```

Equivalent: a different explicit opaque staging placeholder is validated and discarded. It is never a causal origin, persisted record or emitted source; runtime correlation is a separate explicit argument. Removing the explicit placeholder (UUID fallback) is non-equivalent and is killed by the strengthened no-UUID test.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_1

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_1: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use prepare_state_producer_generation")
+    raise TypeError(None)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_2

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_2: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use prepare_state_producer_generation")
+    raise TypeError("XXUse prepare_state_producer_generationXX")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_3

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_3: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use prepare_state_producer_generation")
+    raise TypeError("use prepare_state_producer_generation")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁ__init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Use prepare_state_producer_generation")
+    raise TypeError("USE PREPARE_STATE_PRODUCER_GENERATION")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -7,7 +7,7 @@
         it only through the durable composed commit and cycle-boundary swap.
         """
     if type(claim) is not StaticStateClaim:
-        raise TypeError("Producer binding requires a concrete static claim")
+        raise TypeError(None)
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -7,7 +7,7 @@
         it only through the durable composed commit and cycle-boundary swap.
         """
     if type(claim) is not StaticStateClaim:
-        raise TypeError("Producer binding requires a concrete static claim")
+        raise TypeError("XXProducer binding requires a concrete static claimXX")
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -7,7 +7,7 @@
         it only through the durable composed commit and cycle-boundary swap.
         """
     if type(claim) is not StaticStateClaim:
-        raise TypeError("Producer binding requires a concrete static claim")
+        raise TypeError("producer binding requires a concrete static claim")
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -7,7 +7,7 @@
         it only through the durable composed commit and cycle-boundary swap.
         """
     if type(claim) is not StaticStateClaim:
-        raise TypeError("Producer binding requires a concrete static claim")
+        raise TypeError("PRODUCER BINDING REQUIRES A CONCRETE STATIC CLAIM")
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_10

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_10: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
         raise TypeError("Producer binding requires a concrete static claim")
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
-        raise ValueError("Fixed-source producer was not prepared")
+        raise ValueError(None)
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_11

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_11: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
         raise TypeError("Producer binding requires a concrete static claim")
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
-        raise ValueError("Fixed-source producer was not prepared")
+        raise ValueError("XXFixed-source producer was not preparedXX")
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_12

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_12: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
         raise TypeError("Producer binding requires a concrete static claim")
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
-        raise ValueError("Fixed-source producer was not prepared")
+        raise ValueError("fixed-source producer was not prepared")
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_13

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_13: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
         raise TypeError("Producer binding requires a concrete static claim")
     registration = self._producers.get((claim.fact_type, claim.where))
     if registration is None:
-        raise ValueError("Fixed-source producer was not prepared")
+        raise ValueError("FIXED-SOURCE PRODUCER WAS NOT PREPARED")
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_15

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_15: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -12,7 +12,7 @@
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
     if registration.claim != claim:
-        raise ValueError("Producer claim differs from its prepared declaration")
+        raise ValueError(None)
     if not callable(read_active):
         raise TypeError("Producer binding requires an active-generation reader")
     port = object.__new__(FixedSourceStateProducer)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_16

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_16: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -12,7 +12,7 @@
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
     if registration.claim != claim:
-        raise ValueError("Producer claim differs from its prepared declaration")
+        raise ValueError("XXProducer claim differs from its prepared declarationXX")
     if not callable(read_active):
         raise TypeError("Producer binding requires an active-generation reader")
     port = object.__new__(FixedSourceStateProducer)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_17

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_17: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -12,7 +12,7 @@
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
     if registration.claim != claim:
-        raise ValueError("Producer claim differs from its prepared declaration")
+        raise ValueError("producer claim differs from its prepared declaration")
     if not callable(read_active):
         raise TypeError("Producer binding requires an active-generation reader")
     port = object.__new__(FixedSourceStateProducer)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_18

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_18: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -12,7 +12,7 @@
     if registration is None:
         raise ValueError("Fixed-source producer was not prepared")
     if registration.claim != claim:
-        raise ValueError("Producer claim differs from its prepared declaration")
+        raise ValueError("PRODUCER CLAIM DIFFERS FROM ITS PREPARED DECLARATION")
     if not callable(read_active):
         raise TypeError("Producer binding requires an active-generation reader")
     port = object.__new__(FixedSourceStateProducer)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_21

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_21: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -14,7 +14,7 @@
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
-        raise TypeError("Producer binding requires an active-generation reader")
+        raise TypeError(None)
     port = object.__new__(FixedSourceStateProducer)
     object.__setattr__(port, "_generation", self)
     object.__setattr__(port, "_registration", registration)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_22

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_22: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -14,7 +14,7 @@
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
-        raise TypeError("Producer binding requires an active-generation reader")
+        raise TypeError("XXProducer binding requires an active-generation readerXX")
     port = object.__new__(FixedSourceStateProducer)
     object.__setattr__(port, "_generation", self)
     object.__setattr__(port, "_registration", registration)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_23

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_23: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -14,7 +14,7 @@
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
-        raise TypeError("Producer binding requires an active-generation reader")
+        raise TypeError("producer binding requires an active-generation reader")
     port = object.__new__(FixedSourceStateProducer)
     object.__setattr__(port, "_generation", self)
     object.__setattr__(port, "_registration", registration)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_24

```diff
# custom_components.heima.v3.runtime.state_producers.xǁPreparedStateProducerGenerationǁbind__mutmut_24: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -14,7 +14,7 @@
     if registration.claim != claim:
         raise ValueError("Producer claim differs from its prepared declaration")
     if not callable(read_active):
-        raise TypeError("Producer binding requires an active-generation reader")
+        raise TypeError("PRODUCER BINDING REQUIRES AN ACTIVE-GENERATION READER")
     port = object.__new__(FixedSourceStateProducer)
     object.__setattr__(port, "_generation", self)
     object.__setattr__(port, "_registration", registration)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_1

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_1: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Bind a producer through a prepared generation")
+    raise TypeError(None)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_2

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_2: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Bind a producer through a prepared generation")
+    raise TypeError("XXBind a producer through a prepared generationXX")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_3

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_3: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Bind a producer through a prepared generation")
+    raise TypeError("bind a producer through a prepared generation")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ__init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Bind a producer through a prepared generation")
+    raise TypeError("BIND A PRODUCER THROUGH A PREPARED GENERATION")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_2

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_2: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,3 +1,3 @@
 def _require_active(self) -> None:
     if self._read_active() is not self._generation:
-        raise InactiveProducerGeneration("Producer generation is not active")
+        raise InactiveProducerGeneration(None)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,3 +1,3 @@
 def _require_active(self) -> None:
     if self._read_active() is not self._generation:
-        raise InactiveProducerGeneration("Producer generation is not active")
+        raise InactiveProducerGeneration("XXProducer generation is not activeXX")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,3 +1,3 @@
 def _require_active(self) -> None:
     if self._read_active() is not self._generation:
-        raise InactiveProducerGeneration("Producer generation is not active")
+        raise InactiveProducerGeneration("producer generation is not active")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁ_require_active__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,3 +1,3 @@
 def _require_active(self) -> None:
     if self._read_active() is not self._generation:
-        raise InactiveProducerGeneration("Producer generation is not active")
+        raise InactiveProducerGeneration("PRODUCER GENERATION IS NOT ACTIVE")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
     The composition/layer definitions must belong to this candidate manifest.
     """
     if type(manifest) is not ComposedGenerationManifest:
-        raise TypeError("Producer generation requires a concrete manifest")
+        raise TypeError(None)
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
     The composition/layer definitions must belong to this candidate manifest.
     """
     if type(manifest) is not ComposedGenerationManifest:
-        raise TypeError("Producer generation requires a concrete manifest")
+        raise TypeError("XXProducer generation requires a concrete manifestXX")
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
     The composition/layer definitions must belong to this candidate manifest.
     """
     if type(manifest) is not ComposedGenerationManifest:
-        raise TypeError("Producer generation requires a concrete manifest")
+        raise TypeError("producer generation requires a concrete manifest")
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -10,7 +10,7 @@
     The composition/layer definitions must belong to this candidate manifest.
     """
     if type(manifest) is not ComposedGenerationManifest:
-        raise TypeError("Producer generation requires a concrete manifest")
+        raise TypeError("PRODUCER GENERATION REQUIRES A CONCRETE MANIFEST")
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_10

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_10: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -13,7 +13,7 @@
         raise TypeError("Producer generation requires a concrete manifest")
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
-        raise TypeError("Producer generation requires composed declarations")
+        raise TypeError(None)
     if type(registrations) is not tuple:
         raise TypeError("Fixed-source registrations require an immutable tuple")
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_11

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_11: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -13,7 +13,7 @@
         raise TypeError("Producer generation requires a concrete manifest")
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
-        raise TypeError("Producer generation requires composed declarations")
+        raise TypeError("XXProducer generation requires composed declarationsXX")
     if type(registrations) is not tuple:
         raise TypeError("Fixed-source registrations require an immutable tuple")
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_12

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_12: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -13,7 +13,7 @@
         raise TypeError("Producer generation requires a concrete manifest")
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
-        raise TypeError("Producer generation requires composed declarations")
+        raise TypeError("producer generation requires composed declarations")
     if type(registrations) is not tuple:
         raise TypeError("Fixed-source registrations require an immutable tuple")
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_13

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_13: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -13,7 +13,7 @@
         raise TypeError("Producer generation requires a concrete manifest")
     ComposedGenerationManifest.__post_init__(manifest)
     if type(composition) is not ComposedFactProducers:
-        raise TypeError("Producer generation requires composed declarations")
+        raise TypeError("PRODUCER GENERATION REQUIRES COMPOSED DECLARATIONS")
     if type(registrations) is not tuple:
         raise TypeError("Fixed-source registrations require an immutable tuple")
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_16

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_16: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -15,7 +15,7 @@
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
     if type(registrations) is not tuple:
-        raise TypeError("Fixed-source registrations require an immutable tuple")
+        raise TypeError(None)
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
     declared = frozenset(composition.state_claims)
     for registration in registrations:
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_17

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_17: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -15,7 +15,7 @@
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
     if type(registrations) is not tuple:
-        raise TypeError("Fixed-source registrations require an immutable tuple")
+        raise TypeError("XXFixed-source registrations require an immutable tupleXX")
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
     declared = frozenset(composition.state_claims)
     for registration in registrations:
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_18

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_18: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -15,7 +15,7 @@
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
     if type(registrations) is not tuple:
-        raise TypeError("Fixed-source registrations require an immutable tuple")
+        raise TypeError("fixed-source registrations require an immutable tuple")
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
     declared = frozenset(composition.state_claims)
     for registration in registrations:
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_19

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_19: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -15,7 +15,7 @@
     if type(composition) is not ComposedFactProducers:
         raise TypeError("Producer generation requires composed declarations")
     if type(registrations) is not tuple:
-        raise TypeError("Fixed-source registrations require an immutable tuple")
+        raise TypeError("FIXED-SOURCE REGISTRATIONS REQUIRE AN IMMUTABLE TUPLE")
     producers: dict[_StateKey, FixedStateProducerRegistration] = {}
     declared = frozenset(composition.state_claims)
     for registration in registrations:
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_25

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_25: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -20,7 +20,7 @@
     declared = frozenset(composition.state_claims)
     for registration in registrations:
         if type(registration) is not FixedStateProducerRegistration:
-            raise TypeError("Fixed-source registrations require concrete records")
+            raise TypeError(None)
         FixedStateProducerRegistration.__post_init__(registration)
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_26

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_26: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -20,7 +20,7 @@
     declared = frozenset(composition.state_claims)
     for registration in registrations:
         if type(registration) is not FixedStateProducerRegistration:
-            raise TypeError("Fixed-source registrations require concrete records")
+            raise TypeError("XXFixed-source registrations require concrete recordsXX")
         FixedStateProducerRegistration.__post_init__(registration)
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_27

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_27: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -20,7 +20,7 @@
     declared = frozenset(composition.state_claims)
     for registration in registrations:
         if type(registration) is not FixedStateProducerRegistration:
-            raise TypeError("Fixed-source registrations require concrete records")
+            raise TypeError("fixed-source registrations require concrete records")
         FixedStateProducerRegistration.__post_init__(registration)
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_28

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_28: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -20,7 +20,7 @@
     declared = frozenset(composition.state_claims)
     for registration in registrations:
         if type(registration) is not FixedStateProducerRegistration:
-            raise TypeError("Fixed-source registrations require concrete records")
+            raise TypeError("FIXED-SOURCE REGISTRATIONS REQUIRE CONCRETE RECORDS")
         FixedStateProducerRegistration.__post_init__(registration)
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_39

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_39: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -25,7 +25,7 @@
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
         if owned_claim not in declared:
-            raise ValueError("Fixed-source producer has no matching static declaration")
+            raise ValueError(None)
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
             raise ValueError("Fixed-source producer registered twice")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_40

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_40: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -25,7 +25,7 @@
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
         if owned_claim not in declared:
-            raise ValueError("Fixed-source producer has no matching static declaration")
+            raise ValueError("XXFixed-source producer has no matching static declarationXX")
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
             raise ValueError("Fixed-source producer registered twice")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_41

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_41: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -25,7 +25,7 @@
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
         if owned_claim not in declared:
-            raise ValueError("Fixed-source producer has no matching static declaration")
+            raise ValueError("fixed-source producer has no matching static declaration")
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
             raise ValueError("Fixed-source producer registered twice")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_42

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_42: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -25,7 +25,7 @@
         claim = registration.claim
         owned_claim = StaticStateClaim(claim.fact_type, claim.where, claim.owner_id)
         if owned_claim not in declared:
-            raise ValueError("Fixed-source producer has no matching static declaration")
+            raise ValueError("FIXED-SOURCE PRODUCER HAS NO MATCHING STATIC DECLARATION")
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
             raise ValueError("Fixed-source producer registered twice")
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_45

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_45: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -28,7 +28,7 @@
             raise ValueError("Fixed-source producer has no matching static declaration")
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
-            raise ValueError("Fixed-source producer registered twice")
+            raise ValueError(None)
         source = registration.source
         owned_source = FactSourceFingerprint(
             source.kind,
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_46

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_46: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -28,7 +28,7 @@
             raise ValueError("Fixed-source producer has no matching static declaration")
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
-            raise ValueError("Fixed-source producer registered twice")
+            raise ValueError("XXFixed-source producer registered twiceXX")
         source = registration.source
         owned_source = FactSourceFingerprint(
             source.kind,
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_47

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_47: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -28,7 +28,7 @@
             raise ValueError("Fixed-source producer has no matching static declaration")
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
-            raise ValueError("Fixed-source producer registered twice")
+            raise ValueError("fixed-source producer registered twice")
         source = registration.source
         owned_source = FactSourceFingerprint(
             source.kind,
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

## custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_48

```diff
# custom_components.heima.v3.runtime.state_producers.x_prepare_state_producer_generation__mutmut_48: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -28,7 +28,7 @@
             raise ValueError("Fixed-source producer has no matching static declaration")
         key = (owned_claim.fact_type, owned_claim.where)
         if key in producers:
-            raise ValueError("Fixed-source producer registered twice")
+            raise ValueError("FIXED-SOURCE PRODUCER REGISTERED TWICE")
         source = registration.source
         owned_source = FactSourceFingerprint(
             source.kind,
```

Equivalent: only generic rejection wording changes; exception class and control flow are preserved.

Post-campaign tests add wrong-location binding and explicit absence of pattern
lookup in the per-fact path; source unchanged. Final22-test baseline and all12
supplements were rerun after these additions. Full V3 suite1664 passed.
