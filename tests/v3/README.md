# V3 behavioral tests

Run `.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3 --hypothesis-seed=3145`.
Install runtime/development locks first; tests import real packages and the mutated
copy under mutmut, without HA/V2 import shims. Default mutation scope: nineteen modules.

## Current contracts

CronEntry accepts IntervalRecurrence only (CA4-101). WeeklyRecurrence remains a value
for descriptor windows/bucketing. next_weekly_occurrence returns requested civil date
and canonical physical start. Layer-5 activation owns served dates, equal-start merge,
remaining-time admission and timezone re-arm; those session tests await L5 code.

## Evidence index under docs/v3/testing

- PAYLOAD_CONTRACT.md / PAYLOAD_MUTANT_REVIEW.md: shared canonical payloads.
- TIMING_CONTRACT.md: temporal foundation history; CA4101_OCCURRENCES.md is current.
- ATJOB_DISPATCH.md: shared monotonic admission, replacement and stale deliveries.
- MONOTONIC_ADAPTER.md: early-wakeup/coarse-clock and real stdlib-loop cases.
- CYCLE_CLOCK.md / CA499_EXECUTION_REFERENCES.md: cycle floor and paired basis clocks.
- CA4100_DEADLINES.md: exact canonical-decimal deadline construction/overflow.
- CA4101_OCCURRENCES.md / CA4101_MUTANT_REVIEW.md: interval-only CronEntry and
  requested-date-preserving weekly occurrences, DST and calendar boundaries.
- INTERVAL_LIFECYCLE.md: process-local standing interval rules, faults and re-arm.
- JOB_CALLBACK_BOUNDARY.md: shared owner fault isolation and wrapped one-shot tests.

Supplemental mutation runners: mutation_constants.py, mutation_timing.py,
mutation_clock.py, mutation_deadlines.py, mutation_interval_recurrences.py,
mutation_weekly_occurrence.py. The new weekly runner checks immutable metadata and
replacement of requested date with shifted start date. Actual HA/persistence wiring,
calendar staging, durable gap acknowledgement and ARM benchmarks remain separate.

Timing clock integration: `docs/v3/testing/TIMING_CLOCK_BRIDGE.md` and its mutant
review. `mutation_timing_clock.py` covers three public frozen clock/failure records.
Host capture and 60-second component composition are tested; actual HA lifecycle,
diagnostic publishers and durable continuity watermark/gap implementation remain future.

Observation coverage foundation: `docs/v3/testing/OBSERVATION_COVERAGE.md` and its
mutant review. Supplement: `mutation_observation.py`. Covers value invariants and
composition of already request-clipped process/required-stream results; actual gap
timeline assessment, SQLite durability and historical record assembly remain future.

History intervals and latest critical review: `docs/v3/testing/HISTORY_INTERVALS_AND_REVIEW.md`,
`CRITICAL_REVIEW_20261015.md` and `HISTORY_INTERVAL_REVIEW_MUTANTS.md`. Supplemental
`mutation_history_intervals.py` covers empty-property logic outside mutmut scope.
Fraction countdown regressions and year-1 weekly regression are now in the gate.
Periodic forward-gap behavior during an earlier freeze is resolved by CA4-102;
see CYCLE_CLOCK.md and CYCLE_CLOCK_CA4102_MUTANT_REVIEW.md.


Known observation gap clipping: `docs/v3/testing/OBSERVATION_GAP_CLIPPING.md` and
`OBSERVATION_GAP_CLIPPING_MUTANTS.md`. Supplement: `mutation_observation_gaps.py`.
Explicit bounded intervals/reasons are request-clipped without merging independent
gaps or inferring completeness from absent intersections. Required-stream selection,
metadata trust, pending boundaries and full history assembly remain future work.


Observation coverage assessment: `docs/v3/testing/OBSERVATION_ASSESSMENT.md` and
`OBSERVATION_ASSESSMENT_MUTANTS.md`. Uses original bounded gap extents and explicit
metadata trust to derive sorted reasons/first limit, then composes process and only
required streams. Unknown metadata is conservative. Durable proof, open/pending
boundary extents and full historical record assembly remain owner responsibilities.


Clock-gap durability projection: `docs/v3/testing/CLOCK_GAP_DURABILITY.md` and
`CLOCK_GAP_DURABILITY_MUTANTS.md`. Supplement: `mutation_clock_gap_durability.py`.
Exact receipt correlation prevents cross-gap/stale-boundary proof; pending ends stay
incomplete. This is a per-gap coverage contribution, not overall process proof or
actual SQLite receipt issuance. CA4-102 independent-gap integration is exercised.


Continuity prefix accounting: `docs/v3/testing/CONTINUITY_ACCOUNTING.md` and
`CONTINUITY_ACCOUNTING_MUTANTS.md`. Supplement: `mutation_continuity_accounting.py`.
Contiguous resolved ranges must cover every still-needed acceptance through the full
chosen barrier; later acknowledgements cannot hide audit holes or pending losses.
This pure gate does not issue receipts, own the queue/ranges or write a watermark.


SQLite transaction boundary: `docs/v3/testing/SQLITE_TRANSACTIONS.md` and
`SQLITE_TRANSACTIONS_MUTANTS.md`. Supplement: `mutation_sqlite_transactions.py`.
Real temporary on-disk WAL/FULL transactions, post-COMMIT results, rollback/uncertain
commit, SQL-control guard and worker/event-loop ownership. No application SQL schema,
queue/worker host or actual watermark/receipt issuer is implemented by this primitive.


SQLite clock-boundary operations: `storage/test_sqlite_clock_gaps.py` uses real
on-disk batch/replay/uncertainty cases; `mutation_sqlite_clock_gaps.py` supplements
SQL semantics and frozen-value checks. Evidence: `docs/v3/testing/SQLITE_CLOCK_BOUNDARIES.md`
and `SQLITE_CLOCK_BOUNDARIES_MUTANTS.md`. Receipts from inner callbacks are candidates
until the enclosing SQLiteTransactionWriter.run successfully returns.


Location prerequisite: `contracts/test_location.py` covers the exhaustive shape
matrix, canonical identity/Unicode ordering, strict key-text recovery and properties;
`mutation_location.py` supplements immutable shape and identity/order mutations.
See `docs/v3/testing/LOCATION.md` and `LOCATION_MUTANTS.md`. This slice does not
implement full HouseFact assembly or fact/marker SQL.


Source values/fingerprints: `contracts/test_fact_sources.py` verifies exact closed
vocabularies, production/test/archive shape modes, stable source axes, UUID safety
net, explicit causal propagation and forged/subclass validation. The validator grants
no authorization. `mutation_fact_sources.py` supplements module vocabularies,
dataclass defaults and frozen/slots outside ordinary function scope. Evidence:
`docs/v3/testing/FACT_SOURCE.md` and `FACT_SOURCE_MUTANTS.md`.


HouseFact/Provenance builder: `contracts/test_house_facts.py` verifies universal
record assembly, hard/soft failures, immutable snapshots, metadata, canonical
encoding/equality/hash and source mode propagation; `mutation_house_facts.py`
supplements envelope flags, omission semantics and policy/equality changes.
See `docs/v3/testing/HOUSE_FACT_BUILDER.md` and `HOUSE_FACT_BUILDER_MUTANTS.md`.
This is construction; runtime authority, diagnostics delivery and fact SQL are pending.


### State identity and change fingerprint

`contracts/test_fact_state.py` exercises L0 §4.0 identity, stable-source changes,
canonical value equality and unavailable-value exclusion. Five-method evidence:
[FACT_STATE](../../docs/v3/testing/FACT_STATE.md); generated mutant review:
[FACT_STATE_MUTANTS](../../docs/v3/testing/FACT_STATE_MUTANTS.md). Run
`.venv-v3/bin/python tests/v3/mutation_fact_state.py` for semantic supplements.
These are comparison primitives, not coordinator/admission/storage integration.


### Fact-type staging claims

`contracts/test_fact_types.py` covers L0 §4 dotted glob grammar, independent
language-intersection properties, ownership/emission conflicts and finite search.
See [FACT_TYPE_CLAIMS](../../docs/v3/testing/FACT_TYPE_CLAIMS.md) and
[mutant review](../../docs/v3/testing/FACT_TYPE_CLAIM_MUTANTS.md).
Run `.venv-v3/bin/python tests/v3/mutation_fact_types.py` for record and termination
supplements. HouseFact builder reuses the concrete identifier validator.
This does not yet compose reserved core claims or admit running producers.


### Composed producer staging

`runtime/test_producer_staging.py` checks mandatory core reservations, exact static
identity uniqueness, inventory references and staging-only owner/kind bindings.
Evidence: [PRODUCER_STAGING](../../docs/v3/testing/PRODUCER_STAGING.md) and
[mutants](../../docs/v3/testing/PRODUCER_STAGING_MUTANTS.md). Semantic supplements:
`.venv-v3/bin/python tests/v3/mutation_producer_staging.py`.
Bindings are metadata, not source-authority tokens or live producer admission.


### Composed generation record shapes

`contracts/test_generations.py` checks L0 §4.7 exact records, canonical five-layer
order, immutable metadata and explicit UTC effective_at. Evidence:
[COMPOSED_GENERATION](../../docs/v3/testing/COMPOSED_GENERATION.md) and
[mutants](../../docs/v3/testing/COMPOSED_GENERATION_MUTANTS.md).
Run `.venv-v3/bin/python tests/v3/mutation_generations.py` for semantic supplements.
Constructing a manifest does not prove durable commit or activate a generation.


### Generation-fenced fixed-source state builders

`runtime/test_state_producers.py` exercises staged source assignment, installed-
snapshot identity, pre/post-build fencing, explicit correlation and diagnostic
preservation. No pattern resolution is allowed during build. Evidence:
[STATE_PRODUCER_PORTS](../../docs/v3/testing/STATE_PRODUCER_PORTS.md) and
[mutants](../../docs/v3/testing/STATE_PRODUCER_PORT_MUTANTS.md). Supplements:
`.venv-v3/bin/python tests/v3/mutation_state_producers.py`.
These builders return facts; actual accepted append/index/queue remain separate.


### Live current index and append order

`runtime/test_state_acceptance.py` exercises cycle-owned time/origin, fixed-source
producer fencing, write-on-change against live current, and ordered transitions.
Evidence: [STATE_ACCEPTANCE](../../docs/v3/testing/STATE_ACCEPTANCE.md) and
[mutants](../../docs/v3/testing/STATE_ACCEPTANCE_MUTANTS.md). Supplements:
`.venv-v3/bin/python tests/v3/mutation_state_acceptance.py` and the updated
`mutation_state_producers.py`. This is the live comparison/order step: the next
owner must publish returned transitions to buffer and durable queue synchronously.
No retry journal, forced baseline, event admission or fact SQL is implemented here.


### State transition buffer retention

`runtime/test_state_buffer.py` checks per-key horizons, equal-time transitions,
sparse predecessors, explicit maintenance and immutable snapshots. Evidence:
[STATE_BUFFER](../../docs/v3/testing/STATE_BUFFER.md) and
[mutation review](../../docs/v3/testing/STATE_BUFFER_MUTANTS.md). Run
`.venv-v3/bin/python tests/v3/mutation_state_buffer.py` for semantic supplements.
The buffer consumes trusted accepted state transitions; raw records do not certify
observation completeness. Frozen views, event streams and queue publication remain
separate integrations.
