# Claude prompt — interval duration and canonical deadline precision

Status: resolved by **CA4-100 / planning 34ce913**, verified against current
normative sections on 2026-10-14. Original prompt retained below.

Window unchanged. Derived instants use canonical decimal seconds, exact addition
and the first microsecond at/after the sum; the strict L2 variant selects the first
after it. Dynamic overflow is diagnosed without arming; static horizons fail
staging. CA4-98/99 and L5 whole-ms requirements unchanged. Shared function and
interval single-arm planning/admission implemented; see testing/CA4100_DEADLINES.md.
Full recurrence lifecycle, calendar staging and HA diagnostic publication remain
future integration work, rather than unresolved product rules.

## Prompt

Work in the V3 planning worktree on `feat/v3-planning`. Read current normative
contracts first; the following reports an implementation counterexample, not a
new normative rule. Codex checked clean planning HEAD `d58431c`.

### Approved rules and precise gap

- Layer 0 §3, Time representation: every declared instant, including AtJob.due,
  uses Layer 1's EvidenceInstant.
- Layer 1 §4, EvidenceInstant: canonical UTC text with exactly six fractional
  digits, hence microsecond precision.
- Layer 0 §3.1, Temporal construction validation: Window and IntervalRecurrence
  accept every positive finite non-boolean int/float, normalized to float.
  No constructor or scheduler silently clamps, rounds or corrects invalid values.
- Layer 0 §3.1, CronEntry computation/restart: IntervalRecurrence's next deadline
  is now + interval, using the cycle-instant clock per CA4-99.
- Layer 0 §3.2, Window: shared duration validation and canonical numeric seconds.

A positive duration need not be representable as a microsecond deadline increment.
At now `2026-10-14T12:00:00.000000+00:00`, Window(0.0000001) is valid, but its
exact requested deadline cannot be expressed as EvidenceInstant. Standard Python
timedelta(seconds=0.0000001) becomes zero, so due equals now; our AtJob dispatcher
correctly dispatches immediately. Repeating this after each fire could cause an
unbounded immediate recurrence. This is a representation conflict, independently
of timer resolution or slow hardware.

Verified on native Python 3.14.5:

| Requested seconds | timedelta's represented seconds |
| --- | --- |
| 0.0000001 | 0.0 |
| 0.000001 | 0.000001 |
| 0.0000015 | 0.000002 |
| 0.000002 | 0.000002 |

The 1.5 µs case also prevents treating only durations below 1 µs as the entire gap.

### Requested specification work

1. Make the product choice explicit: which durations may generate an AtJob due,
   and how is now + interval represented when not exactly expressible? Do not
   silently introduce rejection, rounding, a minimum or a second wire instant.
2. State whether any restriction belongs to Window universally, or to consumers
   that construct deadlines. Audit dependent holds, learned durations, calendar
   horizons and other Window uses before changing the shared validator.
3. Define the numeric interpretation used for representability: float's binary
   value versus its canonical numeric decimal representation. Ordinary values
   such as 0.1 s must have an intentional, documented treatment.
4. Add acceptance cases below/at/above 1 µs, 1.5 µs, ordinary fractional seconds,
   and unrepresentable calendar overflow. Keep representation failures distinct
   from hardware execution latency. Preserve CA4-98/99's basis and clock rules.
5. Reconcile the owning sections, dependent contracts, acceptance criteria,
   registry/backlog and review evidence through the existing workflow. Return
   a handoff with exact normative sections and the chosen rule.

Codex has implemented only the independent weekly calculator while this is open.
No interval conversion policy, extra dependency or planning change was introduced.
