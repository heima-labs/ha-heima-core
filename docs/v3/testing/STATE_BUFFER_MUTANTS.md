# State transition buffer mutation review

Scope: only runtime/state_buffer.py, all tests/v3, seed 3145, mutmut 3.8,
`mutmut run --max-children 4`. Final fresh campaign: 102 generated, 61 killed, 41 reviewed equivalent survivors
(40 generic prose, 1 behaviorally equal initial sentinel); zero errors, timeouts,
skipped, untested or interrupted mutants.
The permanent mutation scope includes 30 modules after restoring the normal config.

Eight semantic supplements in tests/v3/mutation_state_buffer.py pass a clean
28-test baseline and each kill their selected mutation: module default removed,
append direction reversed, evict latest rather than predecessor, mutable snapshot,
forgotten maintenance boundary, ignored per-stream extension, shared staging map,
forgotten global append boundary. Each requires pytest exit 1 and a named test
failure; collection errors/no selection do not count. No new public dataclass
record/decorator exists in this slice. No surviving non-equivalent mutant was
found in the initial campaign; the final fresh run includes the final cross-stream
ordering test. Exact diffs and proofs for all equivalent survivors are below.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -2,7 +2,7 @@
     owned: dict[FactIdentityKey, Window] = {}
     for key, horizon in horizons.items():
         if type(key) is not FactIdentityKey:
-            raise TypeError("State buffer requires registered state identity keys")
+            raise TypeError(None)
         if not isinstance(horizon, Window):
             raise TypeError("State buffer horizon requires Window")
         validated = Window(horizon.seconds)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_5

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_5: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -2,7 +2,7 @@
     owned: dict[FactIdentityKey, Window] = {}
     for key, horizon in horizons.items():
         if type(key) is not FactIdentityKey:
-            raise TypeError("State buffer requires registered state identity keys")
+            raise TypeError("XXState buffer requires registered state identity keysXX")
         if not isinstance(horizon, Window):
             raise TypeError("State buffer horizon requires Window")
         validated = Window(horizon.seconds)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_6

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_6: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -2,7 +2,7 @@
     owned: dict[FactIdentityKey, Window] = {}
     for key, horizon in horizons.items():
         if type(key) is not FactIdentityKey:
-            raise TypeError("State buffer requires registered state identity keys")
+            raise TypeError("state buffer requires registered state identity keys")
         if not isinstance(horizon, Window):
             raise TypeError("State buffer horizon requires Window")
         validated = Window(horizon.seconds)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_7

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_7: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -2,7 +2,7 @@
     owned: dict[FactIdentityKey, Window] = {}
     for key, horizon in horizons.items():
         if type(key) is not FactIdentityKey:
-            raise TypeError("State buffer requires registered state identity keys")
+            raise TypeError("STATE BUFFER REQUIRES REGISTERED STATE IDENTITY KEYS")
         if not isinstance(horizon, Window):
             raise TypeError("State buffer horizon requires Window")
         validated = Window(horizon.seconds)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_9

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_9: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -4,7 +4,7 @@
         if type(key) is not FactIdentityKey:
             raise TypeError("State buffer requires registered state identity keys")
         if not isinstance(horizon, Window):
-            raise TypeError("State buffer horizon requires Window")
+            raise TypeError(None)
         validated = Window(horizon.seconds)
         owned[key] = Window(max(_DEFAULT_HORIZON_SECONDS, validated.seconds))
     self._horizons = MappingProxyType(owned)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_10

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_10: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -4,7 +4,7 @@
         if type(key) is not FactIdentityKey:
             raise TypeError("State buffer requires registered state identity keys")
         if not isinstance(horizon, Window):
-            raise TypeError("State buffer horizon requires Window")
+            raise TypeError("XXState buffer horizon requires WindowXX")
         validated = Window(horizon.seconds)
         owned[key] = Window(max(_DEFAULT_HORIZON_SECONDS, validated.seconds))
     self._horizons = MappingProxyType(owned)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_11

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_11: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -4,7 +4,7 @@
         if type(key) is not FactIdentityKey:
             raise TypeError("State buffer requires registered state identity keys")
         if not isinstance(horizon, Window):
-            raise TypeError("State buffer horizon requires Window")
+            raise TypeError("state buffer horizon requires window")
         validated = Window(horizon.seconds)
         owned[key] = Window(max(_DEFAULT_HORIZON_SECONDS, validated.seconds))
     self._horizons = MappingProxyType(owned)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_12

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_12: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -4,7 +4,7 @@
         if type(key) is not FactIdentityKey:
             raise TypeError("State buffer requires registered state identity keys")
         if not isinstance(horizon, Window):
-            raise TypeError("State buffer horizon requires Window")
+            raise TypeError("STATE BUFFER HORIZON REQUIRES WINDOW")
         validated = Window(horizon.seconds)
         owned[key] = Window(max(_DEFAULT_HORIZON_SECONDS, validated.seconds))
     self._horizons = MappingProxyType(owned)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_25

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ__init____mutmut_25: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -12,4 +12,4 @@
         key: deque() for key in owned
     }
     self._last: AcceptedStateTransition | None = None
-    self._maintenance_when: EvidenceInstant | None = None
+    self._maintenance_when: EvidenceInstant | None = ""
```

Equivalent on valid public inputs: every canonical EvidenceInstant is greater than the empty string. The extra initial comparison therefore cannot reject an append or maintenance call. parse_instant rejects malformed maintenance inputs first; accepted facts already have canonical instants. Successful maintenance overwrites the sentinel, and no public API exposes its initial value.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,4 +1,4 @@
 def _stream(self, key: FactIdentityKey) -> deque[AcceptedStateTransition]:
     if type(key) is not FactIdentityKey:
-        raise TypeError("State buffer lookup requires a state identity key")
+        raise TypeError(None)
     return self._streams[key]
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,4 +1,4 @@
 def _stream(self, key: FactIdentityKey) -> deque[AcceptedStateTransition]:
     if type(key) is not FactIdentityKey:
-        raise TypeError("State buffer lookup requires a state identity key")
+        raise TypeError("XXState buffer lookup requires a state identity keyXX")
     return self._streams[key]
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,4 +1,4 @@
 def _stream(self, key: FactIdentityKey) -> deque[AcceptedStateTransition]:
     if type(key) is not FactIdentityKey:
-        raise TypeError("State buffer lookup requires a state identity key")
+        raise TypeError("state buffer lookup requires a state identity key")
     return self._streams[key]
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁ_stream__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,4 +1,4 @@
 def _stream(self, key: FactIdentityKey) -> deque[AcceptedStateTransition]:
     if type(key) is not FactIdentityKey:
-        raise TypeError("State buffer lookup requires a state identity key")
+        raise TypeError("STATE BUFFER LOOKUP REQUIRES A STATE IDENTITY KEY")
     return self._streams[key]
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,7 +1,7 @@
 def append(self, transition: AcceptedStateTransition) -> None:
     """Append one already accepted state transition, never deduplicate values."""
     if type(transition) is not AcceptedStateTransition:
-        raise TypeError("State buffer requires an accepted state transition")
+        raise TypeError(None)
     AcceptedStateTransition.__post_init__(transition)
     stream = self._stream(fact_identity_key(transition.fact))
     when, order = transition.fact.when, transition.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,7 +1,7 @@
 def append(self, transition: AcceptedStateTransition) -> None:
     """Append one already accepted state transition, never deduplicate values."""
     if type(transition) is not AcceptedStateTransition:
-        raise TypeError("State buffer requires an accepted state transition")
+        raise TypeError("XXState buffer requires an accepted state transitionXX")
     AcceptedStateTransition.__post_init__(transition)
     stream = self._stream(fact_identity_key(transition.fact))
     when, order = transition.fact.when, transition.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,7 +1,7 @@
 def append(self, transition: AcceptedStateTransition) -> None:
     """Append one already accepted state transition, never deduplicate values."""
     if type(transition) is not AcceptedStateTransition:
-        raise TypeError("State buffer requires an accepted state transition")
+        raise TypeError("state buffer requires an accepted state transition")
     AcceptedStateTransition.__post_init__(transition)
     stream = self._stream(fact_identity_key(transition.fact))
     when, order = transition.fact.when, transition.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -1,7 +1,7 @@
 def append(self, transition: AcceptedStateTransition) -> None:
     """Append one already accepted state transition, never deduplicate values."""
     if type(transition) is not AcceptedStateTransition:
-        raise TypeError("State buffer requires an accepted state transition")
+        raise TypeError("STATE BUFFER REQUIRES AN ACCEPTED STATE TRANSITION")
     AcceptedStateTransition.__post_init__(transition)
     stream = self._stream(fact_identity_key(transition.fact))
     when, order = transition.fact.when, transition.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_14

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_14: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -7,7 +7,7 @@
     when, order = transition.fact.when, transition.order
     if self._maintenance_when is not None:
         if when < self._maintenance_when:
-            raise ValueError("Append predates the maintenance clock")
+            raise ValueError(None)
     previous = self._last
     if previous is not None:
         before = previous.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_15

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_15: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -7,7 +7,7 @@
     when, order = transition.fact.when, transition.order
     if self._maintenance_when is not None:
         if when < self._maintenance_when:
-            raise ValueError("Append predates the maintenance clock")
+            raise ValueError("XXAppend predates the maintenance clockXX")
     previous = self._last
     if previous is not None:
         before = previous.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_16

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_16: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -7,7 +7,7 @@
     when, order = transition.fact.when, transition.order
     if self._maintenance_when is not None:
         if when < self._maintenance_when:
-            raise ValueError("Append predates the maintenance clock")
+            raise ValueError("append predates the maintenance clock")
     previous = self._last
     if previous is not None:
         before = previous.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_17

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_17: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -7,7 +7,7 @@
     when, order = transition.fact.when, transition.order
     if self._maintenance_when is not None:
         if when < self._maintenance_when:
-            raise ValueError("Append predates the maintenance clock")
+            raise ValueError("APPEND PREDATES THE MAINTENANCE CLOCK")
     previous = self._last
     if previous is not None:
         before = previous.order
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_22

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_22: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -12,7 +12,7 @@
     if previous is not None:
         before = previous.order
         if (order.cycle_id, order.ordinal) <= (before.cycle_id, before.ordinal):
-            raise ValueError("State append order must increase strictly")
+            raise ValueError(None)
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_23

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_23: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -12,7 +12,7 @@
     if previous is not None:
         before = previous.order
         if (order.cycle_id, order.ordinal) <= (before.cycle_id, before.ordinal):
-            raise ValueError("State append order must increase strictly")
+            raise ValueError("XXState append order must increase strictlyXX")
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_24

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_24: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -12,7 +12,7 @@
     if previous is not None:
         before = previous.order
         if (order.cycle_id, order.ordinal) <= (before.cycle_id, before.ordinal):
-            raise ValueError("State append order must increase strictly")
+            raise ValueError("state append order must increase strictly")
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_25

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_25: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -12,7 +12,7 @@
     if previous is not None:
         before = previous.order
         if (order.cycle_id, order.ordinal) <= (before.cycle_id, before.ordinal):
-            raise ValueError("State append order must increase strictly")
+            raise ValueError("STATE APPEND ORDER MUST INCREASE STRICTLY")
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_28

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_28: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -15,7 +15,7 @@
             raise ValueError("State append order must increase strictly")
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
-                raise ValueError("One cycle must have one instant")
+                raise ValueError(None)
         elif when <= previous.fact.when:
             raise ValueError("A later cycle must have a later instant")
     stream.append(transition)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_29

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_29: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -15,7 +15,7 @@
             raise ValueError("State append order must increase strictly")
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
-                raise ValueError("One cycle must have one instant")
+                raise ValueError("XXOne cycle must have one instantXX")
         elif when <= previous.fact.when:
             raise ValueError("A later cycle must have a later instant")
     stream.append(transition)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_30

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_30: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -15,7 +15,7 @@
             raise ValueError("State append order must increase strictly")
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
-                raise ValueError("One cycle must have one instant")
+                raise ValueError("one cycle must have one instant")
         elif when <= previous.fact.when:
             raise ValueError("A later cycle must have a later instant")
     stream.append(transition)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_31

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_31: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -15,7 +15,7 @@
             raise ValueError("State append order must increase strictly")
         if order.cycle_id == before.cycle_id:
             if when != previous.fact.when:
-                raise ValueError("One cycle must have one instant")
+                raise ValueError("ONE CYCLE MUST HAVE ONE INSTANT")
         elif when <= previous.fact.when:
             raise ValueError("A later cycle must have a later instant")
     stream.append(transition)
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_33

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_33: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -17,6 +17,6 @@
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
         elif when <= previous.fact.when:
-            raise ValueError("A later cycle must have a later instant")
+            raise ValueError(None)
     stream.append(transition)
     self._last = transition
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_34

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_34: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -17,6 +17,6 @@
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
         elif when <= previous.fact.when:
-            raise ValueError("A later cycle must have a later instant")
+            raise ValueError("XXA later cycle must have a later instantXX")
     stream.append(transition)
     self._last = transition
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_35

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_35: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -17,6 +17,6 @@
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
         elif when <= previous.fact.when:
-            raise ValueError("A later cycle must have a later instant")
+            raise ValueError("a later cycle must have a later instant")
     stream.append(transition)
     self._last = transition
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_36

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁappend__mutmut_36: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -17,6 +17,6 @@
             if when != previous.fact.when:
                 raise ValueError("One cycle must have one instant")
         elif when <= previous.fact.when:
-            raise ValueError("A later cycle must have a later instant")
+            raise ValueError("A LATER CYCLE MUST HAVE A LATER INSTANT")
     stream.append(transition)
     self._last = transition
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -8,7 +8,7 @@
     parse_instant(now)
     if self._maintenance_when is not None:
         if now < self._maintenance_when:
-            raise ValueError("Maintenance clock cannot regress")
+            raise ValueError(None)
     if self._last is not None:
         if now < self._last.fact.when:
             raise ValueError("Maintenance cannot predate accepted records")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -8,7 +8,7 @@
     parse_instant(now)
     if self._maintenance_when is not None:
         if now < self._maintenance_when:
-            raise ValueError("Maintenance clock cannot regress")
+            raise ValueError("XXMaintenance clock cannot regressXX")
     if self._last is not None:
         if now < self._last.fact.when:
             raise ValueError("Maintenance cannot predate accepted records")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -8,7 +8,7 @@
     parse_instant(now)
     if self._maintenance_when is not None:
         if now < self._maintenance_when:
-            raise ValueError("Maintenance clock cannot regress")
+            raise ValueError("maintenance clock cannot regress")
     if self._last is not None:
         if now < self._last.fact.when:
             raise ValueError("Maintenance cannot predate accepted records")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_7

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_7: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -8,7 +8,7 @@
     parse_instant(now)
     if self._maintenance_when is not None:
         if now < self._maintenance_when:
-            raise ValueError("Maintenance clock cannot regress")
+            raise ValueError("MAINTENANCE CLOCK CANNOT REGRESS")
     if self._last is not None:
         if now < self._last.fact.when:
             raise ValueError("Maintenance cannot predate accepted records")
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_10

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_10: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -11,7 +11,7 @@
             raise ValueError("Maintenance clock cannot regress")
     if self._last is not None:
         if now < self._last.fact.when:
-            raise ValueError("Maintenance cannot predate accepted records")
+            raise ValueError(None)
     removed = 0
     for key, stream in self._streams.items():
         while len(stream) > 1:
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_11

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_11: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -11,7 +11,7 @@
             raise ValueError("Maintenance clock cannot regress")
     if self._last is not None:
         if now < self._last.fact.when:
-            raise ValueError("Maintenance cannot predate accepted records")
+            raise ValueError("XXMaintenance cannot predate accepted recordsXX")
     removed = 0
     for key, stream in self._streams.items():
         while len(stream) > 1:
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_12

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_12: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -11,7 +11,7 @@
             raise ValueError("Maintenance clock cannot regress")
     if self._last is not None:
         if now < self._last.fact.when:
-            raise ValueError("Maintenance cannot predate accepted records")
+            raise ValueError("maintenance cannot predate accepted records")
     removed = 0
     for key, stream in self._streams.items():
         while len(stream) > 1:
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_13

```diff
# custom_components.heima.v3.runtime.state_buffer.xǁStateTransitionBufferǁmaintain__mutmut_13: survived
--- custom_components/heima/v3/runtime/state_buffer.py
+++ custom_components/heima/v3/runtime/state_buffer.py
@@ -11,7 +11,7 @@
             raise ValueError("Maintenance clock cannot regress")
     if self._last is not None:
         if now < self._last.fact.when:
-            raise ValueError("Maintenance cannot predate accepted records")
+            raise ValueError("MAINTENANCE CANNOT PREDATE ACCEPTED RECORDS")
     removed = 0
     for key, stream in self._streams.items():
         while len(stream) > 1:
```

Equivalent under the contract: only generic error prose changes. The exception type, rejection point, retained records and append/maintenance state are unchanged; exact prose is not specified.
