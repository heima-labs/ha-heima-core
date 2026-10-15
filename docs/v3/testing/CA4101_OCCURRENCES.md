# CA4-101 — interval-only CronEntry and weekly occurrence value

Verified 2026-10-15 against clean read-only planning 0b82d61: Layer 0 §3.1,
restart/fault section and §13; Layer 5 §7.2/§7.2.1; CA4-101 review/registry.
No contradiction found. Weekly CronEntry lifecycle is removed from Initial V3.

## API and implementation impact

CronEntry.pattern is IntervalRecurrence; RecurrencePattern alias removed. Mandatory
construction rejects WeeklyRecurrence. Defensive interval planning/admission also
reject reconstructed legacy objects before any arm. Interval lifecycle itself and
shared owner fault isolation are unchanged.

Removed internal plan_weekly_job(entry,paired_clock,zone). Its only consumers were
tests, all migrated; no released HA, stored schema or active configuration exists.
New next_weekly_occurrence(pattern,now,ZoneInfo) returns frozen WeeklyOccurrence:
requested_date is an in-process civil date, start is canonical EvidenceInstant.
It is a transient calculation result, not a new instant wire format, persisted
record or HouseFact payload. No job id/owner/label/basis belongs to this result.
The consumer constructs its own wall_clock AtJob boundary and owns re-arm.

Calendar arithmetic/DST search is unchanged: first physical start strictly after
now, nonexistent time -> first valid instant, ambiguous time -> fold=0. The requested
date is captured before DST resolution. Apia Friday 30 can therefore have Saturday
31 as actual local start. Separate Friday/Saturday patterns can return identical
physical start while retaining distinct requested dates for the consumer to merge.

Layer-5 activation must own served-date RAM, merged-date session admission,
remaining-duration handling and timezone/clock re-arm. None is implemented or
claimed by this Layer-0 pure calculator. Restart does not restore that activation.
Generic weekly lifecycle is not future Initial-V3 work or an open blocker anymore.

## Decision Tables

| Input / condition | Expected | Tests |
| --- | --- | --- |
| CronEntry interval | Accepted immutable standing definition | timing/lifecycle suite |
| CronEntry weekly | TypeError at construction | cron_rejects_weekly_pattern |
| Reconstructed weekly entry at interval boundary | Reject before clock/timer | forged legacy boundary fixtures |
| Weekly normal future civil time | Matching physical start, requested date | UTC PBT and explicit zones |
| Missing time | Gap endpoint, original requested date | Rome, Lord Howe, Apia |
| Ambiguous time | First fold only | Rome fold boundaries/history classification |
| Two requested dates with equal start | Distinct date metadata retained | merged physical start |
| Invalid pattern/now/zone | Reject, never normalize | boundary-shape table |
| Calendar exhausted | Explicit ValueError | calendar exhaustion |

## Boundary Value Analysis

Existing ±1 µs around normal due and DST endpoints retained. CronEntry accepted
interval versus rejected weekly; rejected legacy shapes bypass construction on
purpose to verify independent runtime admission. Original civil date versus actual
date across Apia's whole-day gap; two different dates at the same physical start.
Hour/minute/weekday bounds and UTC 167/169-hour weeks remain exercised.

## MC/DC

No compound Boolean decision introduced or modified by CA4-101: CronEntry's pattern
gate is one isinstance check, as are the pure calculator input gates. Existing
compound validators retain their earlier TIMING_CONTRACT.md evidence and tests.
Single-condition decision outcomes above are not presented as MC/DC certification.

## Property-Based Testing

Hypothesis seed 3145: generated UTC readings and valid nonempty weekday/hour/minute
patterns. The physical start is strictly future, at most seven days away, matches
the pattern with zero seconds/microseconds; requested date equals the civil date in
these non-gap UTC cases. Literal Apia fixtures independently distinguish requested
and shifted date. Tests run under host zones UTC and Europe/Rome and restore TZ.

## Verification and limits

First demonstrated the new rejection test failing on prior code: DID NOT RAISE
TypeError. After changes: 486 total V3 tests pass, seed3145; lint/format/mypy/diff
pass. Migration replaces obsolete weekly-job assertions, not removal of DST cases.
Fresh mutmut on timing.py and recurrence.py: 305 generated, 210 killed, 5 pre-existing
weekly-search timeouts, 90 equivalent survivors. Exact assessment/diffs in
CA4101_MUTANT_REVIEW.md; no behavioral survivor found. The two final independent
merged-date examples were added after the mutation run without further source edits.
Supplement mutation_timing.py: 10 killed with clean baseline. New
mutation_weekly_occurrence.py: 2 killed (frozen result; substitution of actual-start
date for requested date), clean baseline. Default mutation scope remains eleven
modules. No new dependency or score threshold, no live HA/ARM/deploy evidence.
L5 session identity/merge/late-arrival fixtures await L5 implementation.
