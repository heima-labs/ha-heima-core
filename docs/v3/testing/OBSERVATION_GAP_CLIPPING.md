# Request-clipped known observation gaps — 2026-10-15

## Scope and source

Planning working copy: feat/v3-planning, base 0b82d61 plus uncommitted CA4-102;
read-only. Owning contract: Layer 0 §4.4 (request interval endpoints determine gap
intersection) and §13 endpoint acceptance; dependency separation checked against
§4.0 state reconstruction, §4.3 retention, §4.6 overflow and §3.5 independent clock
gaps. No planning changes, new product policy, storage schema or dependencies.

contracts/observation_gaps.py adds frozen ObservationGap(interval,reason) and
clip_observation_gaps(request,gaps). These are internal calculation inputs/results,
not normative new persisted records. Endpoints are explicit HistoryInterval values;
closed reason validation delegates to ObservationCoverage. Existing geometry owns
intersection. Forged/reconstructed nested inputs are revalidated, including gaps
outside the request and empty requests, so malformed evidence is not silently dropped.

Clipping preserves order, reasons and multiplicity. Independent corrections are not
merged, deduplicated or sorted. No scope inference occurs: the caller must select
process/required-stream evidence. Empty intervals contribute no known missing instant.
The output is a tuple of known evidence, **not ObservationCoverage**: an empty tuple
cannot certify complete observation or trustworthy/acknowledged metadata. Unbounded
or pending boundary resolution, first_incomplete_at assignment, stream availability,
baseline invalidation, durable timeline and HistoricalReadResult assembly remain
future integration tasks. No retention assessment or state recovery is added.

## Decision tables and boundaries

58 dedicated test instances, seed3145:

- All five closed reasons crossed with disjoint-before, disjoint-after, containing,
  contained, left-overlapping and right-overlapping gaps. Exact clipped flags/reasons
  asserted; source intervals remain unchanged.
- Both request endpoints: touching is included only when both relevant inclusion flags
  are true, all four pairs. Excluded endpoints cannot contaminate the request.
- Zero-width included point versus excluded point, widths 1 and 2 microseconds with
  both-open bounds, empty gaps, empty requests, minimum/maximum calendar points.
- Several overlapping and identical gaps keep their original order and multiplicity,
  including identical bounds with different reasons. An empty input remains evidence
  absence, not a coverage certificate.
- Non-tuple collections, wrong elements, invalid reasons and reconstructed reversed/
  non-boolean nested intervals reject; frozen record assignment rejects.

## MC/DC

No compound Boolean decision is introduced in observation_gaps.py: all guards are
single predicates; it delegates endpoint decisions to existing history_intervals.py.
MC/DC for the reused intersection is nevertheless checked through the public clipping
function: for each endpoint, TT yields one point, FT removes it while gap inclusion
stays true, and TF removes it while request inclusion stays true. These independently
exercise each inclusion condition; FF completes the table. This is distinct from
claiming new compound source decisions or equating branch coverage with MC/DC.

## Property-Based Testing

An independent membership-set oracle enumerates a 21-point canonical microsecond
grid, generating arbitrary endpoint flags, requests and up to 15 gaps with all closed
reasons. The ordered list of clipped membership sets/reasons must match the original
gaps intersected with request membership. This checks omissions, extra evidence,
reason loss, sorting and deduplication without copying the bound-selection algorithm.
Clipping already clipped evidence is idempotent. Hypothesis uses seed3145 and shrinking.

## Mutation and validation

Fresh mutmut 3.8 scoped only to observation_gaps.py, all tests/v3, four children:
52 generated, 40 killed, 12 reviewed generic TypeError-message equivalents, no timeout,
error, skipped or untested. Exact individual diffs and reproduction in
OBSERVATION_GAP_CLIPPING_MUTANTS.md. Supplement mutation_observation_gaps.py has a
clean 58-test baseline and kills frozen-decorator removal in the expected behavioral
test (pytest exit1). Default mutation scope now sixteen modules; scoped evidence does
not claim a fresh mutation run for unchanged modules.

Final V3 suite: 691 passed (58 above committed 633), seed3145. Ruff lint/format,
mypy (22 source files) and diff hygiene pass. No HA, SQLite, durable acknowledgement,
ARM benchmark or deployment was performed. Parent commit 6cf839b contains earlier
interval geometry, timing review fixes and CA4-102; the current clipping slice is
uncommitted pending review.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/contracts/test_observation_gaps.py --hypothesis-seed=3145 -q
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145 -q
.venv-v3/bin/python tests/v3/mutation_observation_gaps.py
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```
