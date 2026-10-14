# AtJob dispatch surviving-mutant review

Fresh mutmut 3.8.0 run: 95 generated, 87 killed, 8 survived. Scoped runtime/timing.py
with tests/v3, seed 3145. All eight survivors reviewed below. The contract requires
TypeError and no scheduling/state change; generic exception wording is not a stable
product contract or a runtime diagnostic schema. Each mutation retains that behavior.
They are equivalent for the tested contract, not byte-for-byte identical exceptions.
No tests were added merely to enforce uncontracted capitalization/prose.

## register mutant 2

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_2: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: EvidenceInstant, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError(None)
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## register mutant 3

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_3: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: EvidenceInstant, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError("XXRegistration requires AtJobXX")
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## register mutant 4

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_4: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: EvidenceInstant, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError("registration requires atjob")
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## register mutant 5

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_5: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -1,6 +1,6 @@
 def register(self, job: AtJob, now: EvidenceInstant, callback: JobCallback) -> None:
     if not isinstance(job, AtJob):
-        raise TypeError("Registration requires AtJob")
+        raise TypeError("REGISTRATION REQUIRES ATJOB")
     if not callable(callback):
         raise TypeError("Registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
```

## register mutant 8

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_8: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError(None)
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     delay = max(0.0, (parse_instant(validated.due) - parse_instant(now)).total_seconds())
```

## register mutant 9

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_9: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError("XXRegistration requires an owner callbackXX")
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     delay = max(0.0, (parse_instant(validated.due) - parse_instant(now)).total_seconds())
```

## register mutant 10

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_10: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError("registration requires an owner callback")
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     delay = max(0.0, (parse_instant(validated.due) - parse_instant(now)).total_seconds())
```

## register mutant 11

Classification: generic TypeError prose only; rejection and pending state unchanged.

```diff
# custom_components.heima.v3.runtime.timing.xǁAtJobSchedulerǁregister__mutmut_11: survived
--- custom_components/heima/v3/runtime/timing.py
+++ custom_components/heima/v3/runtime/timing.py
@@ -2,7 +2,7 @@
     if not isinstance(job, AtJob):
         raise TypeError("Registration requires AtJob")
     if not callable(callback):
-        raise TypeError("Registration requires an owner callback")
+        raise TypeError("REGISTRATION REQUIRES AN OWNER CALLBACK")
     # Revalidate at admission, including a subtype/reconstructed object.
     validated = AtJob(job.job_id, job.owner, job.due, job.label, job.basis)
     delay = max(0.0, (parse_instant(validated.due) - parse_instant(now)).total_seconds())
```
