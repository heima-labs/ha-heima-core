# Observation coverage value and composition — 2026-10-15

Sources: clean read-only planning 0b82d61, Layer 0 §4.4 ObservationCoverage and
multi-stream completeness; registry owner/dependencies. No spec changes.

## API / scope

contracts/observation.py defines closed status/reason aliases and frozen
ObservationCoverage(status,reasons,first_incomplete_at). Complete requires empty
reasons and no missing instant; incomplete requires distinct ASCII-sorted closed
reasons and a canonical instant. Invalid status, enum impostors, mutable reason
collections, duplicate/unsorted/unknown reasons and contradictory fields reject.
No silent sorting, normalization or inference of completeness occurs at construction.

combine_observation_coverage requires explicit process coverage and an immutable
tuple of coverage for required streams. Inputs are revalidated, including reconstructed
objects. Output unions/sorts reasons and chooses the earliest missing instant;
complete is possible only if all supplied inputs are complete. Zero required streams
does not remove process coverage or hide unknown continuity metadata.

Preconditions: callers select the required streams, assess trustworthy metadata and
clip all inputs to the same requested interval. Endpoint semantics, clipping,
latest-state availability resolution and pending-boundary conservatism belong to
that future assessment. This algebra cannot independently certify the truth of an
input coverage record. No retention result, HistoricalReadResult, HouseFact assembly,
gap timeline, SQLite I/O or durable acknowledgement is implemented in this slice.
An unknown process timeline must arrive as explicit incomplete metadata, not a
default optimistic process result. Existing retention coverage remains independent.

## Decision Tables

| Process | Required streams | Output |
| --- | --- | --- |
| Complete | Empty / all complete | Complete, no reasons/instant |
| Incomplete | All complete | Process limits retained |
| Complete | Any incomplete | Required-stream limits retained |
| Incomplete | Incomplete | Union of reasons and earliest instant |
| Unknown metadata | Empty / complete | Still incomplete, metadata reason retained |
| Duplicate reasons across inputs | Valid individually | One canonical copy |
| Malformed/reconstructed contradictory input | Any | Reject rather than optimistic coverage |

Eight literal composition table rows and construction rejection table exercise
status/reason/instant combinations separately. Every declared reason has an explicit
valid immutable example; enum/string coercion and missing process input are tested.

## Boundary Value Analysis

Empty/one/multiple required streams, none/one/all reason combinations, duplicate and
reversed reasons; earliest instant before/equal/after another missing instant; empty
metadata versus missing process argument; canonical instant versus Z alias/non-text.
Current result includes no interval endpoints: no endpoint convention is invented
or tested as if it belonged to this composition function.

## MC/DC

No compound Boolean decision is introduced. The validator uses separate gates with
different error categories for shape, reason closure, canonical order and status
invariants; composition uses single optional-instant decisions. Compound-condition
independence is inapplicable to this source slice. Decision outcomes are tested,
not represented as MC/DC certification from branch coverage.

## Property-Based Testing

Hypothesis seed 3145 generates valid complete/incomplete values, all closed reason
subsets and up to ten required streams. Output is complete iff every input is;
otherwise reasons equal the union and first_incomplete_at equals the earliest input
limit. Composition is idempotent, stream-order independent, and adding complete
coverage cannot heal a known gap. Literal cases independently assert expected values.

## Verification

541 V3 tests pass, 39 new, seed3145; Ruff lint/format, mypy and diff pass. Fresh
mutmut on observation.py: 115 generated, 67 killed, 48 equivalent generic-validation
prose survivors; no timeout/error/skipped. Exact diffs in OBSERVATION_MUTANT_REVIEW.md.
Supplement mutation_observation.py clean baseline passes; frozen-record removal,
removal of a declared reason and acceptance of an undeclared reason are killed by
behavioral assertions. Its missing-reason target deliberately avoids eager fixture
construction; a collection error is not counted as a semantic test kill.
Default mutation scope fourteen modules. No new dependency/policy, SQLite schema,
live HA, durable gap acknowledgement or ARM benchmark claimed.
