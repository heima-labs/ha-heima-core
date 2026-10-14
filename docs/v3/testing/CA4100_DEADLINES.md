# CA4-100 deadline construction — 2026-10-14

Sources checked: clean planning 34ce913, Layer 0 §3.1, §3.4.1/§4.1 and §13;
Layer 1 §4, Layer 2 §3.2, Layer 5 §6.0, CA4-100 registry/review. No contradiction
found in this slice.

## Scope

contracts/deadlines.py::derive_instant is the single pure rule. Convert canonical
RFC-8785 scalar seconds to Decimal and then an exact integer ratio; select the
inclusive ceiling or strict successor in microseconds. No float timedelta or
ambient Decimal context is used. Integer calendar headroom prevents overflow
before constructing the result. Window keeps its canonical value.

Unrepresentable(anchor,duration) is an immutable diagnostic input returned on
overflow. Invalid contract shapes still raise. plan_interval_job derives elapsed
due from cycle_instant, preserving identity. register_interval_job admits one arm
or returns overflow without changing any timers. Existing accepted arms survive
rejected replacement. Runtime owners must publish the diagnostic result.

Weekly calculation is unchanged. No existing V3 float-seconds timedelta producer
needed migration. Future owner deadlines/horizons must use this function. No calendar
staging service, HA diagnostic publisher, L2 binding service or L5 learned-delay
staging exists yet; their integration gates remain future work. No new dependency.

## Decision Tables

| Strict | Exact whole µs | Result |
| --- | --- | --- |
| false | yes | exact sum |
| false | no | next µs |
| true | yes | exact sum + 1 µs |
| true | no | next µs |

All rows: test_strict_and_inclusive_decision_pairs. Calendar headroom: below/exact
inclusive limit succeeds; greater fails. Strict equality fails. Invalid
anchor/Window/flag rejects without normalization. Admission: success arms once;
overflow on empty scheduler arms nothing; overflow replacement preserves prior arm.

## Boundary Value Analysis

Literal CA4-100 cases 0.1/1/1.5/2 µs and 0.1 s; nextafter on either side of 1 µs;
smallest positive float; maximum instant, one remaining microsecond, remaining
whole seconds/days, one µs beyond the limit and huge finite duration. Long canonical
decimal calculation is tested with Decimal precision 2 to detect context dependence.

## MC/DC

Compound decision: strictly_after OR remainder. Pairs (false,zero)->false versus
(true,zero)->true isolate strict selection; (false,zero)->false versus
(false,nonzero)->true isolate remainder. Ordinary/strict 1 µs and ordinary 1.5 µs
exercise these pairs. Interval gates are separate single-condition decisions.

## Property-Based Testing

Hypothesis seed 3145: positive finite floats from smallest subnormal through 1e12 s,
strict/inclusive choice and generated anchor microseconds. Independent Fraction
oracle asserts exact <= actual < exact+1, or exact < actual <= exact+1 when strict;
the result is always after anchor. Overflow is allowed only beyond calendar
headroom. This asserts minimal conservative representation without duplicating
integer division as the oracle.

## Integration and verification

Manual timer port exercises five explicit owner re-arms at consecutive microsecond
anchors: delay 1 µs, stale delivery suppressed, one pending job. This is not a full
automatic CronEntry service. Late owner delivery keeps due unchanged and next arm
uses a later captured clock reading; no catch-up or real-time timing claim.

445 V3 tests pass, 38 new, seed3145; Ruff lint/format and mypy pass. Fresh mutmut
on deadlines.py and recurrence.py: 239 generated, 180 killed, 5 unchanged weekly
nontermination timeouts, 54 equivalent survivors. Remaining-headroom arithmetic
survivors prompted seconds/day boundaries; fresh final run kills them. Exact diffs
in CA4100_MUTANT_REVIEW.md. mutation_deadlines.py baseline passes and removal of
diagnostic immutability is killed by test_calendar_boundary. Default scope nine
modules. No live HA, ARM benchmark, static calendar staging or downstream owner
integration has run.
