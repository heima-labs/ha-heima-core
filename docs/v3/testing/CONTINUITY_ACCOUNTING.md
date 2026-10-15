# Continuity prefix accounting gate — 2026-10-15

## Source and chosen implementation boundary

Planning clean/read-only 37986ea: Layer 0 §4.4 requires every accepted fact, independently
queued audit and continuity item through a chosen observation barrier to be durably
written or have its loss durably declared. Producer audit-construction failure is a
blocker from its known instant. §4.1/§4.2 require atomic cycle facts+CycleCommitMarker;
§4.6 requires the full completed-cycle boundary, not only intake max_append_ordinal.
No planning edits, new product policy, SQL schema, dependency or HA contract.

storage/continuity_accounting.py introduces pure internal calculation inputs:

- ContinuityAccountingBarrier(through_sequence,observed_at).
- DurabilityRange(first_sequence,last_sequence,outcome), inclusive positions, one of
  pending, written, loss_pending, loss_declared.
- continuity_barrier_accounted(...), with explicit previously_accounted_through,
  inventory_complete and producer_blocked_at inputs.

These positions belong to a single process-local coordinator namespace and cover all
accepted kinds uniformly. They do not replace AppendOrder or choose a persisted key.
The owner must assign a position to every acceptance and supply verified outcomes,
including independent audits and continuity boundaries. written means all payloads
in that exact range committed; loss_declared means all losses have durable boundaries,
never that payloads were written. Sparse acknowledgements cannot justify one range
from their minimum to maximum. The prior prefix needs verified accounting in the same
namespace; it is not the largest receipt and cannot be restored from a timestamp.

Ranges were chosen over a second per-item payload/receipt queue. The pure gate scans
ordered disjoint ranges once with constant extra memory; it does not sort, retain the
input, enumerate tickets or read storage. The future assembler must produce those
ranges from matched writer results and existing bounded queue/loss-marker inventory.
This slice does not implement that assembler or solve its compaction/lifetime.

## Gate behavior

Only the still-needed interval (previously_accounted_through,through_sequence] is
accounted. Every position must be covered by contiguous resolved evidence. Holes,
pending writes, pending loss declarations, unknown inventory and producer failure at
or before observed_at return False. Later receipts cannot heal an earlier hole.
Old/future ranges cannot block this interval but are still validated. Overlap, duplicate
positions, unordered ranges, malformed nested values and impossible bounds reject.

A fully accounted empty acceptance period can pass without inventing a fact. A True
result is only the accounting prerequisite for a future watermark transaction; it does
not advance or acknowledge a watermark, validate a fresh HA intake, close a global
overflow epoch or erase a per-key unseeded baseline. Durable loss can resolve accounting
while observation coverage of the lost interval stays queue_overflow incomplete.

The owner must choose the complete evaluation-cycle boundary for global closure:
the gate can prove only the supplied target and cannot infer a missing later-DAG target
from an intake boundary. Cross-run correlation, exact writer receipts, atomic watermark
writes, process/stream continuity and history assembly remain future integration work.

## Five-method evidence

66 focused instances, Hypothesis seed3145:

- Decision tables: all four outcomes × inventory completeness; old/within/future range
  placement; holes versus pending audit versus durably declared loss; intake versus full
  cycle target; failed producer timing; empty acceptance periods. A later written fact
  never hides missing audit position 2 between written positions 1 and 3.
- BVA: covered-end and prior-prefix positions -1/0/+1; leading/internal/trailing holes;
  sequence 0 versus positive obligations; bool/float/negative positions; exact producer
  failure instant at barrier±1us; overlapping/duplicate/reversed snapshots; huge batched
  range 1..2**63+1 without enumeration; empty (previous,target] despite a straddling range.
- MC/DC on the final ready AND cursor==target: all-written complete inventory => TT,
  same coverage with unknown inventory => FT, and empty proof with a nonempty target
  => TF. Each condition independently changes the result. Other new source predicates
  are single conditions; enum membership is one outcome predicate, not a hidden MC/DC
  claim. Producer blockers, range resolution and continuity holes independently keep
  ready False even when a later range reaches the target.
- PBT: arbitrary per-item outcomes are grouped into contiguous uniform ranges. A separate
  per-item slice oracle checks the chosen prefix, then one required item's proof is
  removed while later acknowledgements remain; the gate must reject the resulting hole.
  Generated target/prefix positions include equality/empty ranges. Shrinking found a
  new-code bug for pending [1,2], previous=target=1; two literal regressions failed before
  the empty-clipped-range fix. This was not a bug attributed to the prior commit.
- Mutation: fresh scope continuity_accounting.py, all tests/v3:138 generated,97 killed,
  41 reviewed equivalents (40 generic error prose, one redundant fast-path equality),
  no timeout/error/untested. A first run exposed continue->break skipping later invalid
  entries after an empty clipped range. Added that input-validation test and reran from
  a fresh directory. Exact diffs/proof in CONTINUITY_ACCOUNTING_MUTANTS.md. Supplement
  mutation_continuity_accounting.py kills removal of both frozen declarations after a
  clean 66-test baseline, with the expected named behavioral failure.

## Validation and limits

867 V3 tests pass (66 above committed 801), seed3145. Ruff lint/format (57 files),
mypy (24 sources) and diff hygiene pass. Default mutation scope eighteen modules.
No new dependency, policy, real SQLite write, HA/ARM benchmark or deploy occurred.
Parent 956039d commits clock-gap durability projection; this accounting slice remains
uncommitted. Actual sequence/range ownership, verified outcome issuance, writer
transactions/retries, watermark publication and full historical read assembly remain
future work. Typed input construction by itself does not prove a real durable commit.

```bash
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/storage/test_continuity_accounting.py --hypothesis-seed=3145 -q
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145 -q
.venv-v3/bin/python tests/v3/mutation_continuity_accounting.py
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
```
