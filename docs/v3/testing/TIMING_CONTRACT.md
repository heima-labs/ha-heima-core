# Layer-0 temporal foundation

> Superseded scope notes: see CA4101_OCCURRENCES.md. Initial V3 CronEntry is
> interval-only; weekly calculation returns an occurrence for descriptor consumers.
> Generic weekly lifecycle is outside Initial V3, not pending clarification.

Implemented 2026-10-14 against planning `9cd077e`: Layer 0 §§3.1, 3.2,
3.4/3.4.1; Layer 1 §4 EvidenceInstant. This slice provides validated immutable
contracts and pure comparisons, not the scheduler or calendar cache.

## API

instants.py: EvidenceInstant is a semantic string type; parse_instant accepts
only canonical UTC text with six fractional digits and +00:00 and returns a
temporary datetime. validate_instant returns the validated text. format_instant
explicitly normalizes an aware producer datetime to UTC. Contract strings are
never repaired, and naive producer datetimes are rejected.

Python 3.14's parser normalizes 24:00:00 to next-day midnight. A regression case
failed before the fix (1 failed/90 passed); strict parse round-trip equality now
rejects that noncanonical input. Minimum/maximum supported four-digit years and
leap dates are covered. No datetime is retained in a contract object.

timing.py: shared validate_duration normalizes positive finite non-boolean int/
float to float. Window owns seconds and its {"seconds":number} canonical form.
AtJob validates due/basis/text shape. WeeklyRecurrence validates immutable nonempty
weekdays, hour/minute and classifies against an explicit installation ZoneInfo.
IntervalRecurrence wraps Window; CronEntry accepts the two closed patterns.
CalendarWindow preserves exact summary/source text, validates canonical bounds
with end>start, and contains uses [start,end).

No extra labels/ids are normalized; string-shape validation is separate from the
future owner/registry admission. Weekly classification accepts either physical
occurrence in an ambiguous civil minute, as specified; it does not implement the
single-firing policy or spring-gap next-due calculation. Summary is the declared
raw calendar scalar, not an operational notification's rendered text.

## Decision Tables

| Rule | Input | Expected | Tests |
|---|---|---|---|
| T1 | Positive finite number | Float duration retained | duration_valid_and_canonical |
| T2 | Bool/string/native timedelta/None | Type rejection | invalid_duration_never_corrected |
| T3 | Zero/negative/NaN/infinity/overflow integer | Value rejection | invalid_duration_never_corrected |
| I1 | Exact canonical and valid calendar date | Validated UTC text | instant_valid_calendar_and_exact_precision |
| I2 | Alias, alternate offset/precision, whitespace, Unicode digit | Reject, no repair | instant_invalid_no_alias_or_silent_repair |
| I3 | Malformed calendar, 24:00 normalization | Reject | instant_invalid_no_alias_or_silent_repair |
| I4 | Aware producer datetime | Explicit UTC normalization | producer_timezone_normalization_and_naive_rejection |
| I5 | Naive/non-datetime/UTC conversion beyond calendar | Reject | same family |
| J1 | AtJob two declared bases + valid due | Immutable definition | job_and_cron_definitions_immutable |
| J2 | Invalid basis or due/nontext fields | Reject | invalid_job_basis/due/text_fields |
| R1 | Nonempty frozenset, integer civil fields in bounds | Immutable pattern | weekly_bounds_valid |
| R2 | Empty/mutable weekdays, bool, wrong types/bounds | Reject | weekly_bounds_invalid |
| R3 | Weekday AND hour AND minute match in given zone | True only when all match | weekly_matches_mcdc |
| C1 | Calendar start<=now<end | True | calendar_half_open_boundaries |
| C2 | Before start or at/after end | False | same family |
| C3 | end<=start or malformed/nontext fields | Reject | calendar_invalid families |

An object cannot simultaneously be an exact bool and exact int. An exact plain
basis string cannot simultaneously fail type validation and equal a valid literal;
the MC/DC type pair therefore uses a StrEnum that compares equal to the literal
but is not the admitted primitive type.

## Boundary Value Analysis

- Duration: negative smallest subnormal, signed zero, positive smallest subnormal,
  ordinary integer/fraction, maximum finite, infinity and overflow. Large finite
  integer normalization is permitted by the explicit duration contract (configuration
  is not restricted by the generic payload integer cap).
- Civil fields: day -1/0/1/5/6/7, hour -1/0/1/22/23/24,
  minute -1/0/1/58/59/60 and bool/noninteger alternatives.
- Instants: years 0001/9999, year 0000 invalid, leap/non-leap February 29,
  hour 24, second 60, six digits versus five/seven, UTC offset and Z aliases.
- Calendar containment: 1 microsecond before/at start, 1 microsecond before/at/
  after end; equal and reversed end rejected.
- Civil classification: both Europe/Rome autumn fold occurrences match;
  UTC/Tokyo prove configured zone use rather than the execution host's zone.

## MC/DC

| Compound decision | Baseline | Independent condition pairs |
|---|---|---|
| not finite OR nonpositive | duration 1 | inf/1 holds positive test false; 0/1 holds finite true |
| invalid basis type OR outside vocabulary | plain elapsed | StrEnum elapsed/plain elapsed hold vocabulary; wrong/plain elapsed hold primitive type |
| 0<=civil<=maximum | valid boundary | -1/0 hold upper; maximum/maximum+1 hold lower |
| weekday AND hour AND minute | Monday 07:30 Rome | Tuesday 07:30; Monday 08:30; Monday 07:31, each compared with baseline |
| start<=now<end | within window | before/at start holds upper; before/at end holds lower |

Other gates are single conditions with both outcomes tested; MC/DC evidence is not
inferred from the line/branch coverage report.

## Property-Based Testing

Hypothesis seed 3145, 50 examples per property: generated valid UTC datetimes
round-trip through canonical text unchanged and always have fixed width/offset;
generated positive finite durations preserve their value and canonical Window form.
Properties assert contract relationships, not a second copy of the implementation.

## Mutation Testing

mutmut 3.8.0 scope: instants.py and timing.py only, with all contract tests selected.
188 mutants: **110 killed, 78 survived**, no untested/error/timeout. Every survivor
reviewed in TIMING_MUTANT_REVIEW.md: generic exception prose or runtime-equivalent
typing.cast annotations. No known non-equivalent survivor remains; raw score is
not presented as 100%. A fresh run after adding UTC/Tokyo tests kills the mutant
using the host zone. Mutation imports are checked to resolve to the mutated tree.

Supplement: `python tests/v3/mutation_timing.py` independently kills frozen
metadata removal on all six dataclasses and narrowing of the module-level instant
pattern. Baseline must pass; each mutant must fail its specified test. The runner
operates in a temporary copy and does not change workspace source.

## Commands/results

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/contracts --hypothesis-seed=3145
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python tests/v3/mutation_timing.py
```

The focused temporary mutation configuration lists only instants.py/timing.py;
the workspace's default config includes all implemented contract modules. For a
repeat of this exact 188-mutant scope, make a temporary copy and narrow only_mutate
in that copy before `mutmut run --max-children 4`. No test parent shim is used.

201 tests pass (92 new plus 109 previous). New modules: all 109 statements and
36 reported branches covered. Ruff/type/format pass. No scheduling, DST execution,
clock-discontinuity, calendar I/O/cache, storage/crash or HA/live evidence exists yet.
LearnedWindow needs Location; WarmupGate and the remaining Layer-0 facilities are
subsequent slices. No spec was modified and no code was committed in this task.


## Critical review — 2026-10-14

Confirmed one missing admission check against Layer 0 §3.1: IntervalRecurrence
previously checked only isinstance(Window), trusting prior Window validation. A
Window subtype overriding post-init could carry zero, bool, NaN, infinity or an
unconverted integer. New tests on the old code: 12 failed, 3 passed; Hypothesis
shrunk the rejection failure to 0.0. No invalid value is reachable through the
normal Window constructor; the defect is the missing independent interval guard.

The interval constructor now builds its retained Window through the same duration
validator, rejecting invalid seconds and normalizing valid seconds without mutating
the supplied object. Window identity/subtype is not a specified interval contract.
No scheduler, serialization loader, product policy or spec change was introduced.

Five-method evidence for this change:

- Decision table: wrong wrapper type rejects (existing shape test); admitted wrapper
  with invalid duration rejects; admitted wrapper with valid duration retains the
  numeric value as a float. New nested-duration tests exercise the last two rows.
- Boundary analysis: -5e-324, zero, +5e-324; maximum finite/infinity; bool, string,
  NaN and overflow integer. Integer 1 demonstrates actual normalization.
- MC/DC: no new compound decision in interval admission. The shared duration
  decision remains not-finite OR nonpositive: 1/inf holds nonpositive false;
  1/0 holds finite true. These pairs now exercise the nested entry point too.
- Property: 50 generated floats, including nonfinite values, test rejection or
  exact preservation according to the specified positive finite duration domain;
  seed 3145. Input object is not modified.
- Mutation: supplementary runner kills three new behavioral mutations (skip nested
  admission, substitute constant 1, validate but retain the unnormalized input).
  All seven earlier decorator/regex mutations still die: 10 total. The earlier
  188-mutant mutmut report is historical evidence for the preceding revision;
  mutmut was not rerun during this review.

Current complete suite: 216 passed; timing/instant coverage 110 statements and
36 branches. Ruff lint/format and mypy pass. Results are pure contract evidence,
not scheduler, persistence, HA integration or live evidence. Changes uncommitted.
