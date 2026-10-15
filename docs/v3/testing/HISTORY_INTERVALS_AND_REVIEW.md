# Historical interval geometry and critical review — 2026-10-15

Sources: clean read-only planning 0b82d61, Layer 0 §4.4 endpoint/coverage rules and
§13 acceptance; timing review also §3.1/§3.5 and CA4-98/99/100/101. No spec edits.

## Bounded historical geometry

HistoryInterval(start,end,include_start,include_end) requires canonical UTC endpoints
and explicit boolean inclusion flags. Reversed endpoints reject; equal endpoints
can describe a point or empty interval. Empty follows the microsecond grid: both-open
adjacent microseconds have no admitted instant; both-open endpoints 2 µs apart have
one. No default historical endpoint convention is imposed.

intersect_history_intervals revalidates inputs and returns the exact clipped
interval, preserving endpoint flags, or None when no canonical instant is shared.
This is bounded geometry only: it does not choose gap endpoint semantics, represent
open/pending durable gaps, assign scopes, select required streams, assess trust,
certify writes or fill ObservationCoverage.first_incomplete_at. Actual gap/read
assessment and SQLite ownership remain subsequent work. Native datetime arithmetic
is temporary; public endpoints remain EvidenceInstant.

## Decision Tables and Boundary Value Analysis

Touching ranges intersect only if both touching endpoints include that instant.
Equal starts/ends preserve the conjunction of their inclusion flags; unequal bounds
take the narrower endpoint's flag. Literal disjoint/contained/overlapping examples,
all four inclusion pairs, widths 0/1/2 µs, excluded-point requests, canonical calendar
minimum/maximum and malformed/reconstructed inputs cover these rules. Bounds do not
need a successor outside the supported calendar.

## MC/DC

New compound decisions: equal-start inclusion A AND B and equal-end inclusion
C AND D. Each table enumerates FF/FT/TF/TT. TT->FT independently changes the first
condition; TT->TF changes the second while the other stays true. Touching-boundary
cases independently check their observable intersection outcome. Other new decisions
are single predicates. This is a condition-pair argument, not branch-coverage proof.

## Property-Based Testing

Seed3145 generates intervals on a 21-point microsecond grid with arbitrary flags.
An independently enumerated membership-set oracle checks intersection, commutativity,
self-intersection and emptiness. It does not reproduce the bound-selection algorithm.

## Critical review fixes — evidence

Reviewed 0cc0929, 6a60bd5, f182a37, f92639a and scheduler/calendar dependencies.
Detailed findings in CRITICAL_REVIEW_20261015.md.

1. Countdown float transport previously rounded below the exact canonical difference.
   _countdown now computes integer microseconds and chooses the least float at/above
   them using as_integer_ratio and nextafter only when required. Both admission and
   civil re-arm share it; overdue remains zero; due and Window are untouched. No
   tolerance/grace or minimum duration introduced. The adapter still protects the
   subsequent addition to monotonic origin separately.
2. A past local candidate whose UTC form fell below year 1 aborted a weekly search
   despite a valid next-week occurrence. A civil prefilter skips past/equal candidates
   before conversion; the UTC future check remains necessary across folds.

Focused pre-fix run: 8 regression instances failed, 4 passed. Both corrections now
pass. Fraction-based countdown properties assert exact <= actual float and previous
float < exact, including 1 µs and 2**35 seconds +1 µs, both bases and re-arm. Four
old test assertions expecting nominal binary delay were strengthened to minimal
conservative float semantics; no approximate tolerance substituted. Year-1 case runs
under both host timezones. Existing DST/Apia tests remain green.

## Mutation / final scope

587 V3 tests pass: 33 new interval cases and 13 review regression/property instances
above prior 541. Ruff lint/format, mypy and diff pass. Fresh mutmut across new
history_intervals.py and fixed timing.py/recurrence.py: 364 generated, 291 killed,
5 known civil-search nontermination timeouts, 68 equivalents. Exact assessment in
HISTORY_INTERVAL_REVIEW_MUTANTS.md. No non-equivalent survivor found.

Mutmut does not mutate the @property empty body. Supplement
mutation_history_intervals.py kills four meaningful property mutations (threshold,
exclusion sum and each ignored flag) plus frozen-record removal, clean baseline.
The final harness expects the first touching-boundary test that actually fails;
an initial overly specific expected test name was rejected, not counted as a kill.
Existing mutation_weekly_occurrence.py also kills 2 result/date mutants after fix.
Default scope fifteen modules, no new dependency or score threshold.

A third reproduced finding is awaiting a normative decision: periodic forward gap
while an earlier backward floor holds. See the developer-authorized Claude prompt
PERIODIC_FORWARD_GAP_DURING_FREEZE.md. That clock behavior was not silently changed.
No live HA/ARM/SQLite/durable gap acknowledgement or deployment claimed.
