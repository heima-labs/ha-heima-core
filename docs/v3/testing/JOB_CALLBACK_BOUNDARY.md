# Shared job callback fault boundary — 2026-10-14

> Superseded scope notes: see CA4101_OCCURRENCES.md. Initial V3 CronEntry is
> interval-only; weekly calculation returns an occurrence for descriptor consumers.
> Generic weekly lifecycle is outside Initial V3, not pending clarification.

Owning Layer 0 §9 callback fault isolation, §3.1 registration semantics, §10
diagnostics; clean read-only planning 34ce913. This independent slice follows
the unresolved weekly identity case in clarifications/WEEKLY_OCCURRENCE_IDENTITY.md.

## Changes and scope

JobCallbackFault moves to runtime/job_callbacks.py. The interval module imports
and re-exports the same class name for existing consumers. invoke_job_callback
calls the owner once, returns a typed ordinary exception diagnostic, and retains
no traceback-bearing exception. isolate_job_callback binds a reporting sink for
one-shot dispatcher admission. IntervalRecurrences uses the same invocation
boundary within its existing finally-based re-arm.

The diagnostic infrastructure port must log/publish promptly without raising;
its own failure is not disguised as an owner error. BaseException process-control
signals propagate. No wire record, HA public API, durable schema, policy, timer or
dependency changed. The low-level AtJobScheduler remains unchanged: one-shot
owners/coordinators must explicitly supply the isolation wrapper. Actual HA
logging/publication and a complete weekly lifecycle are not implemented here.

## Decision Tables

| Condition | Outcome | Tests |
| --- | --- | --- |
| Owner returns | One invocation, no fault | success, PBT |
| Owner raises ordinary Exception | Typed job/type/message diagnostic | owner fault, PBT |
| Owner raises BaseException | Same signal propagates, no diagnostic | process-control pairs |
| Callback or reporter not callable | Reject wrapper construction | boundary ports |
| Diagnostic sink fails | Infrastructure error propagates | sink failure |
| Isolated one-shot fails | Consumed once; other owner continues | shared dispatcher integration |
| Interval owner fails/cancels/replaces | Prior lifecycle semantics preserved | existing lifecycle suite |

## Boundary Value Analysis

No report versus exactly one report; zero/one repeated stale callback deliveries;
ordinary exceptions versus BaseException; missing callback/reporter; empty and
arbitrary Unicode fault messages. Existing interval tests retain reentrant
cancel/replacement boundaries and frozen diagnostic behavior after relocation.

## MC/DC

No compound Boolean decision introduced. Callability gates and optional-fault
checks are single conditions; exception matching is separate control flow.
MC/DC compound independence is inapplicable here, not certified by branch coverage.

## Property-Based Testing

Hypothesis seed 3145: arbitrary Unicode owner messages and return/failure choice.
Exactly one owner invocation occurs; the report is either absent or exactly the
original job, exception type and original message. This asserts transported fault
semantics without mirroring implementation control flow.

## Verification

479 V3 tests pass, 10 new, seed3145; Ruff lint/format, mypy and diff pass. Fresh
mutmut on job_callbacks.py and interval_recurrences.py: 144 generated, 124 killed,
20 equivalent generic-validation-prose survivors, no timeout/error/skipped.
Exact diffs in JOB_CALLBACK_MUTANT_REVIEW.md. Updated supplementary lifecycle
runner independently restores both source files between mutations; all three public
frozen-record removals remain killed with a passing baseline. Default scope eleven
modules. No live HA, ARM benchmark, weekly identity policy or timezone listener
verification claimed. The approved Claude clarification remains the next dependency.
