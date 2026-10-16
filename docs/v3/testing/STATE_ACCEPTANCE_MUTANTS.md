# Live state acceptance and producer guard mutation review

Scope: runtime/state_acceptance.py and runtime/state_producers.py; all tests/v3,
seed 3145, mutmut 3.8, `mutmut run --max-children 4`. Final fresh verification: 447 generated, 302 killed, 145 reviewed equivalent
survivors; zero errors, timeouts, skipped, untested or interrupted mutants. Default permanent scope is restored to 29 modules.

The initial campaign found one non-equivalent survivor: changing the default
cycle-id seed from 0 to 1. Tests always passed an explicit seed via their fixture.
Strengthened the constructor behavior test to construct without that keyword and
assert the first accepted AppendOrder(1,1). Production was already correct. The
initial cached rerun is not final verification; the final campaign uses a new
mutants directory and the strengthened test.

Fourteen semantic seeds in mutation_state_acceptance.py are killed on a clean
38-test baseline: public record frozen/slots, omission sentinel, forgetting current,
value-only comparison, closing cycle, finally-unlock, per-cycle ordinal reset,
post-diagnostic generation check, expected port generation. Thirteen port semantic
seeds in mutation_state_producers.py are killed on a clean 23-test baseline (the
previous 12 plus omission of the explicit guard's installed-snapshot check).
Each kill requires pytest exit 1 and a named behavioral test failure; collection
errors or no selection do not qualify. Decorators/module sentinel and omitted
statements are supplemented because function mutation does not cover them fully.
The private _CurrentState wrapper has no independently exposed record API.

Reviewed equivalent survivors: 136 generic exception-prose changes, 4 inaccessible
or behaviorally equal initial sentinels, 3 redundant temporary source validators,
2 discarded staging placeholder changes. Every exact diff and proof follows.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_3

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.cycle_id) is not int:
-        raise TypeError("Cycle id must be a primitive integer")
+        raise TypeError(None)
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.cycle_id) is not int:
-        raise TypeError("Cycle id must be a primitive integer")
+        raise TypeError("XXCycle id must be a primitive integerXX")
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.cycle_id) is not int:
-        raise TypeError("Cycle id must be a primitive integer")
+        raise TypeError("cycle id must be a primitive integer")
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_6

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.cycle_id) is not int:
-        raise TypeError("Cycle id must be a primitive integer")
+        raise TypeError("CYCLE ID MUST BE A PRIMITIVE INTEGER")
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_9

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,6 +2,6 @@
     if type(self.cycle_id) is not int:
         raise TypeError("Cycle id must be a primitive integer")
     if type(self.ordinal) is not int:
-        raise TypeError("Append ordinal must be a primitive integer")
+        raise TypeError(None)
     if self.ordinal < 1:
         raise ValueError("Accepted append ordinals start at one")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_10

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_10: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,6 +2,6 @@
     if type(self.cycle_id) is not int:
         raise TypeError("Cycle id must be a primitive integer")
     if type(self.ordinal) is not int:
-        raise TypeError("Append ordinal must be a primitive integer")
+        raise TypeError("XXAppend ordinal must be a primitive integerXX")
     if self.ordinal < 1:
         raise ValueError("Accepted append ordinals start at one")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_11

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_11: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,6 +2,6 @@
     if type(self.cycle_id) is not int:
         raise TypeError("Cycle id must be a primitive integer")
     if type(self.ordinal) is not int:
-        raise TypeError("Append ordinal must be a primitive integer")
+        raise TypeError("append ordinal must be a primitive integer")
     if self.ordinal < 1:
         raise ValueError("Accepted append ordinals start at one")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_12

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,6 +2,6 @@
     if type(self.cycle_id) is not int:
         raise TypeError("Cycle id must be a primitive integer")
     if type(self.ordinal) is not int:
-        raise TypeError("Append ordinal must be a primitive integer")
+        raise TypeError("APPEND ORDINAL MUST BE A PRIMITIVE INTEGER")
     if self.ordinal < 1:
         raise ValueError("Accepted append ordinals start at one")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_15

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_15: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -4,4 +4,4 @@
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
-        raise ValueError("Accepted append ordinals start at one")
+        raise ValueError(None)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_16

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_16: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -4,4 +4,4 @@
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
-        raise ValueError("Accepted append ordinals start at one")
+        raise ValueError("XXAccepted append ordinals start at oneXX")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_17

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_17: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -4,4 +4,4 @@
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
-        raise ValueError("Accepted append ordinals start at one")
+        raise ValueError("accepted append ordinals start at one")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_18

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAppendOrderǁ__post_init____mutmut_18: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -4,4 +4,4 @@
     if type(self.ordinal) is not int:
         raise TypeError("Append ordinal must be a primitive integer")
     if self.ordinal < 1:
-        raise ValueError("Accepted append ordinals start at one")
+        raise ValueError("ACCEPTED APPEND ORDINALS START AT ONE")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_3

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_3: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.fact) is not HouseFact:
-        raise TypeError("A transition requires a concrete fact")
+        raise TypeError(None)
     if type(self.order) is not AppendOrder:
         raise TypeError("A transition requires a concrete append order")
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.fact) is not HouseFact:
-        raise TypeError("A transition requires a concrete fact")
+        raise TypeError("XXA transition requires a concrete factXX")
     if type(self.order) is not AppendOrder:
         raise TypeError("A transition requires a concrete append order")
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.fact) is not HouseFact:
-        raise TypeError("A transition requires a concrete fact")
+        raise TypeError("a transition requires a concrete fact")
     if type(self.order) is not AppendOrder:
         raise TypeError("A transition requires a concrete append order")
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_6

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_6: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,6 +1,6 @@
 def __post_init__(self) -> None:
     if type(self.fact) is not HouseFact:
-        raise TypeError("A transition requires a concrete fact")
+        raise TypeError("A TRANSITION REQUIRES A CONCRETE FACT")
     if type(self.order) is not AppendOrder:
         raise TypeError("A transition requires a concrete append order")
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_9

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_9: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,5 +2,5 @@
     if type(self.fact) is not HouseFact:
         raise TypeError("A transition requires a concrete fact")
     if type(self.order) is not AppendOrder:
-        raise TypeError("A transition requires a concrete append order")
+        raise TypeError(None)
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_10

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_10: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,5 +2,5 @@
     if type(self.fact) is not HouseFact:
         raise TypeError("A transition requires a concrete fact")
     if type(self.order) is not AppendOrder:
-        raise TypeError("A transition requires a concrete append order")
+        raise TypeError("XXA transition requires a concrete append orderXX")
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_11

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_11: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,5 +2,5 @@
     if type(self.fact) is not HouseFact:
         raise TypeError("A transition requires a concrete fact")
     if type(self.order) is not AppendOrder:
-        raise TypeError("A transition requires a concrete append order")
+        raise TypeError("a transition requires a concrete append order")
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_12

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁAcceptedStateTransitionǁ__post_init____mutmut_12: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,5 +2,5 @@
     if type(self.fact) is not HouseFact:
         raise TypeError("A transition requires a concrete fact")
     if type(self.order) is not AppendOrder:
-        raise TypeError("A transition requires a concrete append order")
+        raise TypeError("A TRANSITION REQUIRES A CONCRETE APPEND ORDER")
     AppendOrder.__post_init__(self.order)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_1

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_1: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Begin a cycle through StateAcceptanceCoordinator")
+    raise TypeError(None)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_2

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_2: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Begin a cycle through StateAcceptanceCoordinator")
+    raise TypeError("XXBegin a cycle through StateAcceptanceCoordinatorXX")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_3

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_3: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Begin a cycle through StateAcceptanceCoordinator")
+    raise TypeError("begin a cycle through stateacceptancecoordinator")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateCycleContextǁ__init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,2 +1,2 @@
 def __init__(self) -> None:
-    raise TypeError("Begin a cycle through StateAcceptanceCoordinator")
+    raise TypeError("BEGIN A CYCLE THROUGH STATEACCEPTANCECOORDINATOR")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -6,7 +6,7 @@
     last_cycle_id: int = 0,
 ) -> None:
     if not callable(read_active):
-        raise TypeError("Coordinator requires an active-generation reader")
+        raise TypeError(None)
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -6,7 +6,7 @@
     last_cycle_id: int = 0,
 ) -> None:
     if not callable(read_active):
-        raise TypeError("Coordinator requires an active-generation reader")
+        raise TypeError("XXCoordinator requires an active-generation readerXX")
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_6

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_6: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -6,7 +6,7 @@
     last_cycle_id: int = 0,
 ) -> None:
     if not callable(read_active):
-        raise TypeError("Coordinator requires an active-generation reader")
+        raise TypeError("coordinator requires an active-generation reader")
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_7

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_7: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -6,7 +6,7 @@
     last_cycle_id: int = 0,
 ) -> None:
     if not callable(read_active):
-        raise TypeError("Coordinator requires an active-generation reader")
+        raise TypeError("COORDINATOR REQUIRES AN ACTIVE-GENERATION READER")
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_10

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_10: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -8,7 +8,7 @@
     if not callable(read_active):
         raise TypeError("Coordinator requires an active-generation reader")
     if not callable(report_diagnostics):
-        raise TypeError("Coordinator requires a diagnostic sink")
+        raise TypeError(None)
     if type(last_cycle_id) is not int:
         raise TypeError("Cycle id seed must be a primitive integer")
     self._read_active = read_active
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_11

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_11: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -8,7 +8,7 @@
     if not callable(read_active):
         raise TypeError("Coordinator requires an active-generation reader")
     if not callable(report_diagnostics):
-        raise TypeError("Coordinator requires a diagnostic sink")
+        raise TypeError("XXCoordinator requires a diagnostic sinkXX")
     if type(last_cycle_id) is not int:
         raise TypeError("Cycle id seed must be a primitive integer")
     self._read_active = read_active
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_12

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_12: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -8,7 +8,7 @@
     if not callable(read_active):
         raise TypeError("Coordinator requires an active-generation reader")
     if not callable(report_diagnostics):
-        raise TypeError("Coordinator requires a diagnostic sink")
+        raise TypeError("coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
         raise TypeError("Cycle id seed must be a primitive integer")
     self._read_active = read_active
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_13

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_13: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -8,7 +8,7 @@
     if not callable(read_active):
         raise TypeError("Coordinator requires an active-generation reader")
     if not callable(report_diagnostics):
-        raise TypeError("Coordinator requires a diagnostic sink")
+        raise TypeError("COORDINATOR REQUIRES A DIAGNOSTIC SINK")
     if type(last_cycle_id) is not int:
         raise TypeError("Cycle id seed must be a primitive integer")
     self._read_active = read_active
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_16

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_16: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -10,7 +10,7 @@
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
-        raise TypeError("Cycle id seed must be a primitive integer")
+        raise TypeError(None)
     self._read_active = read_active
     self._report_diagnostics = report_diagnostics
     self._last_cycle_id = last_cycle_id
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_17

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_17: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -10,7 +10,7 @@
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
-        raise TypeError("Cycle id seed must be a primitive integer")
+        raise TypeError("XXCycle id seed must be a primitive integerXX")
     self._read_active = read_active
     self._report_diagnostics = report_diagnostics
     self._last_cycle_id = last_cycle_id
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_18

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_18: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -10,7 +10,7 @@
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
-        raise TypeError("Cycle id seed must be a primitive integer")
+        raise TypeError("cycle id seed must be a primitive integer")
     self._read_active = read_active
     self._report_diagnostics = report_diagnostics
     self._last_cycle_id = last_cycle_id
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_19

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_19: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -10,7 +10,7 @@
     if not callable(report_diagnostics):
         raise TypeError("Coordinator requires a diagnostic sink")
     if type(last_cycle_id) is not int:
-        raise TypeError("Cycle id seed must be a primitive integer")
+        raise TypeError("CYCLE ID SEED MUST BE A PRIMITIVE INTEGER")
     self._read_active = read_active
     self._report_diagnostics = report_diagnostics
     self._last_cycle_id = last_cycle_id
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_23

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_23: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -14,7 +14,7 @@
     self._read_active = read_active
     self._report_diagnostics = report_diagnostics
     self._last_cycle_id = last_cycle_id
-    self._last_when: EvidenceInstant | None = None
+    self._last_when: EvidenceInstant | None = ""
     self._cycle: StateCycleContext | None = None
     self._ordinal = 0
     self._busy = False
```

Equivalent for valid public inputs: before the first successful cycle, every canonical EvidenceInstant is greater than the empty string. The extra comparison therefore cannot reject it. A successful begin replaces this sentinel; malformed input is rejected by parse_instant first. Failed begins leave the same admissible-input behavior.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_25

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_25: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -16,6 +16,6 @@
     self._last_cycle_id = last_cycle_id
     self._last_when: EvidenceInstant | None = None
     self._cycle: StateCycleContext | None = None
-    self._ordinal = 0
+    self._ordinal = None
     self._busy = False
     self._current: dict[FactIdentityKey, _CurrentState] = {}
```

Equivalent for valid public inputs: before the first successful cycle, every canonical EvidenceInstant is greater than the empty string. The extra comparison therefore cannot reject it. A successful begin replaces this sentinel; malformed input is rejected by parse_instant first. Failed begins leave the same admissible-input behavior.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_26

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_26: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -16,6 +16,6 @@
     self._last_cycle_id = last_cycle_id
     self._last_when: EvidenceInstant | None = None
     self._cycle: StateCycleContext | None = None
-    self._ordinal = 0
+    self._ordinal = 1
     self._busy = False
     self._current: dict[FactIdentityKey, _CurrentState] = {}
```

Equivalent for valid public inputs: before the first successful cycle, every canonical EvidenceInstant is greater than the empty string. The extra comparison therefore cannot reject it. A successful begin replaces this sentinel; malformed input is rejected by parse_instant first. Failed begins leave the same admissible-input behavior.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_27

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ__init____mutmut_27: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -17,5 +17,5 @@
     self._last_when: EvidenceInstant | None = None
     self._cycle: StateCycleContext | None = None
     self._ordinal = 0
-    self._busy = False
+    self._busy = None
     self._current: dict[FactIdentityKey, _CurrentState] = {}
```

Equivalent for valid public inputs: before the first successful cycle, every canonical EvidenceInstant is greater than the empty string. The extra comparison therefore cannot reject it. A successful begin replaces this sentinel; malformed input is rejected by parse_instant first. Failed begins leave the same admissible-input behavior.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_2

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_2: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,7 +1,7 @@
 def begin_cycle(self, when: EvidenceInstant, correlation_id: str) -> StateCycleContext:
     with self._mutation():
         if self._cycle is not None:
-            raise RuntimeError("An evaluation cycle is already open")
+            raise RuntimeError(None)
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,7 +1,7 @@
 def begin_cycle(self, when: EvidenceInstant, correlation_id: str) -> StateCycleContext:
     with self._mutation():
         if self._cycle is not None:
-            raise RuntimeError("An evaluation cycle is already open")
+            raise RuntimeError("XXAn evaluation cycle is already openXX")
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,7 +1,7 @@
 def begin_cycle(self, when: EvidenceInstant, correlation_id: str) -> StateCycleContext:
     with self._mutation():
         if self._cycle is not None:
-            raise RuntimeError("An evaluation cycle is already open")
+            raise RuntimeError("an evaluation cycle is already open")
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,7 +1,7 @@
 def begin_cycle(self, when: EvidenceInstant, correlation_id: str) -> StateCycleContext:
     with self._mutation():
         if self._cycle is not None:
-            raise RuntimeError("An evaluation cycle is already open")
+            raise RuntimeError("AN EVALUATION CYCLE IS ALREADY OPEN")
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_9

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_9: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -5,7 +5,7 @@
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
-                raise ValueError("Cycle instant must increase strictly")
+                raise ValueError(None)
         if type(correlation_id) is not str:
             raise TypeError("Cycle origin must be a primitive string")
         canonical_json_bytes(correlation_id)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_10

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_10: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -5,7 +5,7 @@
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
-                raise ValueError("Cycle instant must increase strictly")
+                raise ValueError("XXCycle instant must increase strictlyXX")
         if type(correlation_id) is not str:
             raise TypeError("Cycle origin must be a primitive string")
         canonical_json_bytes(correlation_id)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_11

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_11: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -5,7 +5,7 @@
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
-                raise ValueError("Cycle instant must increase strictly")
+                raise ValueError("cycle instant must increase strictly")
         if type(correlation_id) is not str:
             raise TypeError("Cycle origin must be a primitive string")
         canonical_json_bytes(correlation_id)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_12

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_12: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -5,7 +5,7 @@
         parse_instant(when)
         if self._last_when is not None:
             if when <= self._last_when:
-                raise ValueError("Cycle instant must increase strictly")
+                raise ValueError("CYCLE INSTANT MUST INCREASE STRICTLY")
         if type(correlation_id) is not str:
             raise TypeError("Cycle origin must be a primitive string")
         canonical_json_bytes(correlation_id)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_15

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_15: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -7,7 +7,7 @@
             if when <= self._last_when:
                 raise ValueError("Cycle instant must increase strictly")
         if type(correlation_id) is not str:
-            raise TypeError("Cycle origin must be a primitive string")
+            raise TypeError(None)
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_16

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_16: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -7,7 +7,7 @@
             if when <= self._last_when:
                 raise ValueError("Cycle instant must increase strictly")
         if type(correlation_id) is not str:
-            raise TypeError("Cycle origin must be a primitive string")
+            raise TypeError("XXCycle origin must be a primitive stringXX")
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_17

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_17: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -7,7 +7,7 @@
             if when <= self._last_when:
                 raise ValueError("Cycle instant must increase strictly")
         if type(correlation_id) is not str:
-            raise TypeError("Cycle origin must be a primitive string")
+            raise TypeError("cycle origin must be a primitive string")
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_18

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_18: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -7,7 +7,7 @@
             if when <= self._last_when:
                 raise ValueError("Cycle instant must increase strictly")
         if type(correlation_id) is not str:
-            raise TypeError("Cycle origin must be a primitive string")
+            raise TypeError("CYCLE ORIGIN MUST BE A PRIMITIVE STRING")
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_23

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_23: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -11,7 +11,7 @@
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
-            raise InactiveProducerGeneration("No producer generation is installed")
+            raise InactiveProducerGeneration(None)
         cycle = object.__new__(StateCycleContext)
         object.__setattr__(cycle, "cycle_id", self._last_cycle_id + 1)
         object.__setattr__(cycle, "when", when)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_24

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_24: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -11,7 +11,7 @@
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
-            raise InactiveProducerGeneration("No producer generation is installed")
+            raise InactiveProducerGeneration("XXNo producer generation is installedXX")
         cycle = object.__new__(StateCycleContext)
         object.__setattr__(cycle, "cycle_id", self._last_cycle_id + 1)
         object.__setattr__(cycle, "when", when)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_25

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_25: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -11,7 +11,7 @@
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
-            raise InactiveProducerGeneration("No producer generation is installed")
+            raise InactiveProducerGeneration("no producer generation is installed")
         cycle = object.__new__(StateCycleContext)
         object.__setattr__(cycle, "cycle_id", self._last_cycle_id + 1)
         object.__setattr__(cycle, "when", when)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_26

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁbegin_cycle__mutmut_26: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -11,7 +11,7 @@
         canonical_json_bytes(correlation_id)
         generation = self._read_active()
         if type(generation) is not PreparedStateProducerGeneration:
-            raise InactiveProducerGeneration("No producer generation is installed")
+            raise InactiveProducerGeneration("NO PRODUCER GENERATION IS INSTALLED")
         cycle = object.__new__(StateCycleContext)
         object.__setattr__(cycle, "cycle_id", self._last_cycle_id + 1)
         object.__setattr__(cycle, "when", when)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_2

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_2: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def _require_open(self, cycle: StateCycleContext) -> None:
     if self._cycle is None:
-        raise RuntimeError("No evaluation cycle is open")
+        raise RuntimeError(None)
     if self._cycle is not cycle:
         raise RuntimeError("Cycle context is no longer current")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def _require_open(self, cycle: StateCycleContext) -> None:
     if self._cycle is None:
-        raise RuntimeError("No evaluation cycle is open")
+        raise RuntimeError("XXNo evaluation cycle is openXX")
     if self._cycle is not cycle:
         raise RuntimeError("Cycle context is no longer current")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def _require_open(self, cycle: StateCycleContext) -> None:
     if self._cycle is None:
-        raise RuntimeError("No evaluation cycle is open")
+        raise RuntimeError("no evaluation cycle is open")
     if self._cycle is not cycle:
         raise RuntimeError("Cycle context is no longer current")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def _require_open(self, cycle: StateCycleContext) -> None:
     if self._cycle is None:
-        raise RuntimeError("No evaluation cycle is open")
+        raise RuntimeError("NO EVALUATION CYCLE IS OPEN")
     if self._cycle is not cycle:
         raise RuntimeError("Cycle context is no longer current")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_7

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_7: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,4 +2,4 @@
     if self._cycle is None:
         raise RuntimeError("No evaluation cycle is open")
     if self._cycle is not cycle:
-        raise RuntimeError("Cycle context is no longer current")
+        raise RuntimeError(None)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_8

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_8: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,4 +2,4 @@
     if self._cycle is None:
         raise RuntimeError("No evaluation cycle is open")
     if self._cycle is not cycle:
-        raise RuntimeError("Cycle context is no longer current")
+        raise RuntimeError("XXCycle context is no longer currentXX")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_9

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_9: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,4 +2,4 @@
     if self._cycle is None:
         raise RuntimeError("No evaluation cycle is open")
     if self._cycle is not cycle:
-        raise RuntimeError("Cycle context is no longer current")
+        raise RuntimeError("cycle context is no longer current")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_10

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_open__mutmut_10: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -2,4 +2,4 @@
     if self._cycle is None:
         raise RuntimeError("No evaluation cycle is open")
     if self._cycle is not cycle:
-        raise RuntimeError("Cycle context is no longer current")
+        raise RuntimeError("CYCLE CONTEXT IS NO LONGER CURRENT")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,4 +1,4 @@
 def _require_current(self, cycle: StateCycleContext) -> None:
     self._require_open(cycle)
     if self._read_active() is not cycle.generation:
-        raise InactiveProducerGeneration("Cycle generation is no longer installed")
+        raise InactiveProducerGeneration(None)
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,4 +1,4 @@
 def _require_current(self, cycle: StateCycleContext) -> None:
     self._require_open(cycle)
     if self._read_active() is not cycle.generation:
-        raise InactiveProducerGeneration("Cycle generation is no longer installed")
+        raise InactiveProducerGeneration("XXCycle generation is no longer installedXX")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,4 +1,4 @@
 def _require_current(self, cycle: StateCycleContext) -> None:
     self._require_open(cycle)
     if self._read_active() is not cycle.generation:
-        raise InactiveProducerGeneration("Cycle generation is no longer installed")
+        raise InactiveProducerGeneration("cycle generation is no longer installed")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁ_require_current__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,4 +1,4 @@
 def _require_current(self, cycle: StateCycleContext) -> None:
     self._require_open(cycle)
     if self._read_active() is not cycle.generation:
-        raise InactiveProducerGeneration("Cycle generation is no longer installed")
+        raise InactiveProducerGeneration("CYCLE GENERATION IS NO LONGER INSTALLED")
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def current(self, key: FactIdentityKey) -> AcceptedStateTransition | None:
     if type(key) is not FactIdentityKey:
-        raise TypeError("Live state lookup requires a fact identity key")
+        raise TypeError(None)
     state = self._current.get(key)
     return None if state is None else state.transition
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def current(self, key: FactIdentityKey) -> AcceptedStateTransition | None:
     if type(key) is not FactIdentityKey:
-        raise TypeError("Live state lookup requires a fact identity key")
+        raise TypeError("XXLive state lookup requires a fact identity keyXX")
     state = self._current.get(key)
     return None if state is None else state.transition
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def current(self, key: FactIdentityKey) -> AcceptedStateTransition | None:
     if type(key) is not FactIdentityKey:
-        raise TypeError("Live state lookup requires a fact identity key")
+        raise TypeError("live state lookup requires a fact identity key")
     state = self._current.get(key)
     return None if state is None else state.transition
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁcurrent__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -1,5 +1,5 @@
 def current(self, key: FactIdentityKey) -> AcceptedStateTransition | None:
     if type(key) is not FactIdentityKey:
-        raise TypeError("Live state lookup requires a fact identity key")
+        raise TypeError("LIVE STATE LOOKUP REQUIRES A FACT IDENTITY KEY")
     state = self._current.get(key)
     return None if state is None else state.transition
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -17,7 +17,7 @@
     with self._mutation():
         self._require_current(cycle)
         if type(producer) is not FixedSourceStateProducer:
-            raise TypeError("State admission requires a bound fixed-source producer")
+            raise TypeError(None)
         producer.require_generation(cycle.generation)
         built = producer.build(
             value=value,
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_6

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_6: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -17,7 +17,7 @@
     with self._mutation():
         self._require_current(cycle)
         if type(producer) is not FixedSourceStateProducer:
-            raise TypeError("State admission requires a bound fixed-source producer")
+            raise TypeError("XXState admission requires a bound fixed-source producerXX")
         producer.require_generation(cycle.generation)
         built = producer.build(
             value=value,
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_7

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_7: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -17,7 +17,7 @@
     with self._mutation():
         self._require_current(cycle)
         if type(producer) is not FixedSourceStateProducer:
-            raise TypeError("State admission requires a bound fixed-source producer")
+            raise TypeError("state admission requires a bound fixed-source producer")
         producer.require_generation(cycle.generation)
         built = producer.build(
             value=value,
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_8

```diff
# custom_components.heima.v3.runtime.state_acceptance.xǁStateAcceptanceCoordinatorǁaccept__mutmut_8: survived
--- custom_components/heima/v3/runtime/state_acceptance.py
+++ custom_components/heima/v3/runtime/state_acceptance.py
@@ -17,7 +17,7 @@
     with self._mutation():
         self._require_current(cycle)
         if type(producer) is not FixedSourceStateProducer:
-            raise TypeError("State admission requires a bound fixed-source producer")
+            raise TypeError("STATE ADMISSION REQUIRES A BOUND FIXED-SOURCE PRODUCER")
         producer.require_generation(cycle.generation)
         built = producer.build(
             value=value,
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent for admitted registrations: FactSourceFingerprint already validates the original optional fields. This discarded FactSource validation temporarily sets one optional field to None; canonical validation and the owned immutable copy still use the original fingerprint. Neither source assignment nor admission changes.

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

Equivalent for admitted registrations: FactSourceFingerprint already validates the original optional fields. This discarded FactSource validation temporarily sets one optional field to None; canonical validation and the owned immutable copy still use the original fingerprint. Neither source assignment nor admission changes.

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

Equivalent for admitted registrations: FactSourceFingerprint already validates the original optional fields. This discarded FactSource validation temporarily sets one optional field to None; canonical validation and the owned immutable copy still use the original fingerprint. Neither source assignment nor admission changes.

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

Equivalent: this is an explicitly supplied opaque staging-only correlation in a discarded validation object. Both alternatives are valid and never enter emitted facts, fingerprints, runtime context or persistence.

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

Equivalent: this is an explicitly supplied opaque staging-only correlation in a discarded validation object. Both alternatives are valid and never enter emitted facts, fingerprints, runtime context or persistence.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_2

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_2: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,5 +1,5 @@
 def require_generation(self, expected: PreparedStateProducerGeneration) -> None:
     """Core coordinator guard: require both the captured and installed image."""
     if self._generation is not expected:
-        raise InactiveProducerGeneration("Producer belongs to another cycle generation")
+        raise InactiveProducerGeneration(None)
     self._require_active()
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_3

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_3: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,5 +1,5 @@
 def require_generation(self, expected: PreparedStateProducerGeneration) -> None:
     """Core coordinator guard: require both the captured and installed image."""
     if self._generation is not expected:
-        raise InactiveProducerGeneration("Producer belongs to another cycle generation")
+        raise InactiveProducerGeneration("XXProducer belongs to another cycle generationXX")
     self._require_active()
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_4

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_4: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,5 +1,5 @@
 def require_generation(self, expected: PreparedStateProducerGeneration) -> None:
     """Core coordinator guard: require both the captured and installed image."""
     if self._generation is not expected:
-        raise InactiveProducerGeneration("Producer belongs to another cycle generation")
+        raise InactiveProducerGeneration("producer belongs to another cycle generation")
     self._require_active()
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

## custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_5

```diff
# custom_components.heima.v3.runtime.state_producers.xǁFixedSourceStateProducerǁrequire_generation__mutmut_5: survived
--- custom_components/heima/v3/runtime/state_producers.py
+++ custom_components/heima/v3/runtime/state_producers.py
@@ -1,5 +1,5 @@
 def require_generation(self, expected: PreparedStateProducerGeneration) -> None:
     """Core coordinator guard: require both the captured and installed image."""
     if self._generation is not expected:
-        raise InactiveProducerGeneration("Producer belongs to another cycle generation")
+        raise InactiveProducerGeneration("PRODUCER BELONGS TO ANOTHER CYCLE GENERATION")
     self._require_active()
```

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.

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

Equivalent under the contract: only generic exception prose changes. The rejection point, exception type and all state effects are unchanged; exact prose is not specified.
