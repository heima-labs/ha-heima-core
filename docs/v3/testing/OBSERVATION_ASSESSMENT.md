# Observation coverage assessment — 2026-10-15

## Owning contract and boundaries

Source: feat/v3-planning, initially base 0b82d61 plus pending CA4-102; final check
clean at 37986ea after Claude committed CA4-102. Spec/registry/backlog/review hashes
are identical to the reviewed inputs;
Layer 0 §4.4 value/first-incomplete/metadata rules and §13 endpoint/unknown-metadata
acceptance. §4.0/§4.3 state reconstruction and retention and §4.6 baseline validity
remain separate responsibilities. No planning edits, new product policy or schema.

contracts/observation_gaps.py now provides assess_observation_coverage(request,gaps,
metadata_trustworthy=...). Trust is an explicit mandatory boolean; the future owner
must certify complete evidence for the selected scope and perform durable-boundary
checks. False adds continuity_metadata_unknown; an intersecting explicitly unknown
metadata interval also adds that reason. Unknown coverage uses the request start
as §4.4 requires, and preserves all other applicable known reasons.

The function derives ObservationCoverage, with distinct ASCII-sorted reasons and
the first missing canonical instant, by reusing the existing geometry/validators.
For a known gap opening before the request, §4.4/§13 explicitly require the request
start as conservative limit, including an excluded request start. Otherwise, the
first missing instant must lie inside the intersection: an included lower bound is
used directly, an excluded bound advances by exactly 1 microsecond, EvidenceInstant's
specified resolution. Nonempty geometry guarantees that successor is representable;
no rounding, grace or duration policy is introduced.

Original gap extents must be supplied, not pre-clipped evidence: clipping alone loses
whether a gap opened before the request, which affects the conservative limit. A
private shared generator retains the original validated gap and intersection; both
public clipping and assessment consume it fully. The 58 existing clipping tests still
pass. Inputs are revalidated even if trust is already false; invalid evidence cannot
be hidden by an early unknown result.

The assessor uses one linear pass with a bounded reason set and one first instant;
there is no I/O or sorted gap list. This is a pure calculation for one caller-selected scope. Process and each required
stream can be assessed separately and combined through combine_observation_coverage.
An unrelated unavailable stream is not included by the calculator. No state-history
scan, age gate, retained-value fallback, scope selection, actual trust attestation,
open/pending gap extent inference, write acknowledgement, SQLite writer or
HistoricalReadResult assembly is implemented here. No HA contract changes.

## Decision table

| Metadata trusted | Known gap intersects | Result | First limit |
| --- | --- | --- | --- |
| True | False | complete, no reasons | None |
| True | True | incomplete, applicable reasons | first missing instant or explicit conservative request start |
| False | False | incomplete, continuity_metadata_unknown | request start |
| False | True | incomplete, unknown plus applicable reasons | request start |

An intersecting gap with reason continuity_metadata_unknown uses the same unknown
rule even when the general trust flag is True. Unknown evidence outside the request
cannot contaminate it. The trust flag has no optimistic default and rejects bool-like
numbers/text. Empty geometry has no intersecting known gap but cannot establish trust:
with trust False it still reports unknown from request start. This does not define
which empty requests a future public history API will admit.

## Five-method evidence

54 new assessment instances, plus 58 unchanged clipping instances; Hypothesis seed3145.

- Decision tables: trust × intersection, all known reasons × disjoint/overlapping/open
  starts, unknown metadata reason × trust/intersection, independent process/valve/light
  composition, order-independent reason union and earliest bound.
- BVA: lower gap opening before/at/after request (-1/0/+1us); touching endpoint flags;
  empty geometry versus point; open first missing instant; maximum calendar successor
  and empty maximum point without overflow; required boolean/no default; malformed
  evidence even for already unknown trust.
- MC/DC: no new compound Boolean source predicate; guards test one condition each.
  For the logical completeness condition, trust and absence of intersecting gaps each
  independently change outcome (T/no-gap vs F/no-gap; T/no-gap vs T/gap). Reused endpoint
  conjunction is exercised by TT/FT/TF/FF inclusion pairs. These are explicit pairs,
  not a claim that ordinary branch coverage certifies MC/DC.
- PBT: generated missing microsecond points have an independent union/minimum oracle;
  metadata False overrides the first limit to request start. Reordering or duplicating
  gaps cannot change assessment. Seed3145 with shrinking; no bound-selection code is
  reproduced in the oracle. Literal tests cover the already-open conservative exception.
- Mutation: fresh observation_gaps.py-only mutmut, all V3 tests: 110 generated,
  94 killed, 16 generic TypeError-message equivalents, no timeout/error/untested.
  Exact diffs in OBSERVATION_ASSESSMENT_MUTANTS.md. Existing frozen-gap supplement
  passes a clean baseline then kills decorator removal in the named behavioral test.

## Validation and reproduction

745 V3 tests passed (54 above committed 691), seed3145. Focused assessment+clipping:
112 passed. Ruff lint/format (51 files), mypy (22 sources), diff hygiene pass.
Parent commit d965470 contains the previous clipping slice; this assessment slice
remains uncommitted. No new dependency, policy, HA/ARM benchmark or deployment.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/contracts/test_observation_assessment.py tests/v3/contracts/test_observation_gaps.py --hypothesis-seed=3145 -q
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145 -q
.venv-v3/bin/python tests/v3/mutation_observation_gaps.py
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```
