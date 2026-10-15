# Clock-gap durable proof and coverage — 2026-10-15

## Source and bounded design

Planning clean/read-only 37986ea, Layer 0 §3.5 (CA4-98/102 independent gaps and
end intent versus acknowledgement), §4.4 (failed/unknown boundaries, conservative
coverage) and §4.6 (ordered continuity metadata). Caller-declared endpoint conventions
remain explicit. No planning edits, new product rule, SQL schema or HA contract.

storage/clock_gaps.py adds internal frozen calculation values:

- ClockGapBoundaryReceipt(gap_id,boundary,when,includes_boundary): an exact correlation
  key for a future writer's durable success. Construction itself acknowledges nothing.
- ClockGapDurability(gap_id,gap,include_start,include_end,opening_receipt,closing_receipt):
  one independent ClockGap intent and at most two matched receipts.
- clock_gap_observation_coverage(request,durability): the restriction contributed by
  this gap to one request, reusing assess_observation_coverage. It must be combined
  with mandatory process continuity and all other relevant gaps/required streams.

Chosen correlation uses an owner-assigned nonempty internal id plus side, canonical
instant and inclusion flag. Bare booleans were rejected because they cannot detect a
receipt for another simultaneous gap or a previous end. IDs are not derived from bounds:
independent corrections can have identical bounds. No UUID format, SQL key, persisted
receipt schema or id-allocation mechanism is chosen here. The owner must ensure unique
identity and the future writer must issue receipts only after durable transaction success,
never at queue admission, timer delivery, ClockGap.finish or failed commit.

Snapshots permit out-of-order receipt delivery. Each receipt must match its exact
boundary; a closing receipt with no closing instant is invalid. A mismatched receipt
is an explicit error, not a way to certify complete coverage. All nested evidence is
revalidated before even an empty/before-gap early return. No mutable registry, second
queue or I/O is introduced; projection has fixed work per supplied gap.

## Read projection decisions

| Intent/proof | Within or after opening | After candidate closing instant |
| --- | --- | --- |
| Open, opening receipt present | clock_discontinuity | remains open; no closing intent |
| Open, opening receipt absent | clock_discontinuity + continuity_metadata_unknown | remains open |
| Closing intent, closing receipt absent | clock_discontinuity + continuity_metadata_unknown | still incomplete |
| Closing receipt present, opening receipt present | clock_discontinuity only inside declared bounds | no restriction from this gap |
| Closing receipt present, opening receipt absent | unknown plus clock inside declared bounds | no restriction from this gap; whole-process proof still required |

Before opening or with no admitted intersection, this gap contributes no restriction.
A known open gap is projected through the request end; a pending closing intent is
also projected through that end, since its unconfirmed end cannot certify continuity
beyond it (§3.5). Only a matching closing receipt uses the declared closing instant
and its inclusion flag. The potential open extent includes the request endpoint when
the request does; it never excludes a tail merely because an unconfirmed end exists.
Missing opening proof or a pending closing proof adds the unknown-metadata reason;
assessment uses the conservative request start and retains the clock reason. No end
intent is silently promoted to a durable receipt.

This is **one gap's contribution**, not proof of a complete timeline. For example, a
fully confirmed gap outside the query cannot heal unknown process metadata; another
still-open gap continues to block completeness. Stream availability, retention,
post-overflow baseline validity and process restart closure remain separate. No
state history is loaded, replayed or restored by the projection.

## Five-method evidence

56 focused instances, Hypothesis seed3145:

- Decision table: opening/closing receipt presence × before/inside/after ranges;
  known-open versus pending end; out-of-order receipts; wrong id/side/instant/inclusion;
  queue/finish versus confirmed closing proof. Actual CycleClock CA4-102 sequence
  confirms a new forward gap without closing the older frozen backward gap.
- BVA: opening and confirmed excluded closing at -1/0/+1us, all endpoint inclusion
  pairs, empty request, supported calendar endpoints, malformed/reversed pending end
  with no closing receipt, wrong/malformed reconstructed nested fields and frozen values.
- MC/DC: unknown = A OR (B AND C), A=opening receipt absent, B=end intent present,
  C=closing receipt absent. Inside-range tests pair A with a confirmed end (B=T,C=F),
  pair B for known opening/no closing receipt (A=F,C=T), and pair C for known opening/
  closing intent (A=F,B=T). Each independently changes the unknown reason. Four receipt
  correlation fields each have a one-field mismatch case with the others held valid.
  Reused endpoint inclusion conjunction is exercised by TT/FT/TF/FF at both bounds.
- PBT: independently enumerate integer-microsecond missing points in [10,20), over
  generated request intervals; confirmed receipts must preserve every real intersecting
  gap. Confirmation cannot make a previously complete contribution incomplete; unknown
  disappears only from this gap after exact proof, and after-end reads regain no-gap
  restriction. The oracle enumerates membership rather than reproducing projection.
- Mutation: fresh clock_gaps.py run, all tests/v3:205 generated,165 killed,40 generic
  exception-prose equivalents, no timeout/error/untested. Initial run exposed missing
  pending-end validation assertions; strengthened them and reran from an empty mutant
  directory. Exact survivor diffs in CLOCK_GAP_DURABILITY_MUTANTS.md. Supplement
  mutation_clock_gap_durability.py kills both frozen declaration removals after a clean
  baseline, with the expected named behavioral failure.

## Verification and remaining integration

801 V3 tests pass (56 above committed 745), seed3145. Ruff lint/format (54 files),
mypy (23 source files), diff hygiene pass. Default mutation scope seventeen modules.
No new dependency/policy, live HA/ARM benchmark, SQLite write or deployment occurred.

The parent f628736 commits the previous observation assessment. This durability
projection, tests, evidence/config/handoff changes remain uncommitted. Actual receipt
issuance, ordered writer callbacks/retries, SQLite transactions, watermark advancement,
process/stream journal ownership and HistoricalReadResult assembly remain future work.
The calculator cannot attest that a user-constructed receipt came from a real commit.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/storage/test_clock_gaps.py --hypothesis-seed=3145 -q
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145 -q
.venv-v3/bin/python tests/v3/mutation_clock_gap_durability.py
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```
