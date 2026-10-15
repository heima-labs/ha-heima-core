# State identity and change fingerprints

## Impact recorded before implementation

Parent d921fd6. Read-only planning aa4455a, L0 §4.0/§4.2/§5.1/§13,
L1 §3/§4/§5, registry L0-STATE-HISTORY (no declared dependencies).
Reuse builder outputs, canonical Location, shared RFC8785 encoder and existing
FactSourceFingerprint. No alternative fact envelope or schema is introduced.

Implement pure extraction only in contracts/fact_state.py. Two immutable records
have exactly the specified fields. Factory-only construction accepts concrete
build_house_fact outputs; validation and source authority remain their owners.
Identity uses existing Location equality. Change values are projected from already
frozen payloads to immutable JSON field shapes (including frozen dataclasses),
without reparsing numbers or revalidating a tuple as raw producer input. Equality
and hashing use canonical JSON, avoiding Python True==1. No cached byte field.
Unavailable value is never inspected and projects to None.

These primitives must only be used for registered state claims: emission kind is
not inferable from HouseFact. Event routing/admission is not implemented here.
Neither an index nor persistence is introduced; forced durable baseline writes
and transition ordering belong to future coordinator/queue work. Later read-key
construction from a validated query is separate from this fact-extraction API.

## Test design

Decision rows: unchanged, time/correlation/evidence only, each stable source field,
value, confidence, availability, unavailable stale values. WHAT/WHERE changes
change identity; all content changes preserve identity.
BVA: confidence endpoints and adjacent floats; boolean/numeric, signed zero,
int/float equivalence; depth-2 immutable values and canonical room-set ordering.
MC/DC: no compound Boolean decision is introduced. Availability is a single
condition (available values compared; unavailable values not read). Each content
component and each stable source field is varied independently against a baseline.
PBT: metadata invariance, unavailable-value invariance, typed-record/JSON equivalence.
Mutation: fresh scoped mutmut plus frozen/slots and unavailable no-read supplements.

## Results

51 focused cases; full V3 suite 1413 passed, Hypothesis seed3145.
Ruff check/format and mypy pass (30 source modules). Fresh scoped mutmut:
95 generated, 79 killed, 16 individually reviewed generic TypeError-prose
equivalents, no errors/timeouts/skips/untested/interrupted. Six semantic
supplements killed after a clean51-test baseline; see FACT_STATE_MUTANTS.md
for exact diffs and tests/v3/mutation_fact_state.py for reproduction.
Initial test fixtures used an invalid source kind and a forbidden dataclass
nested inside ordinary JSON; corrected fixtures to existing admitted shapes,
without changing source or payload validation. No bug fix or spec ambiguity.

The on/off/on fixture proves distinct consecutive fingerprints; it does not
claim a live index, append ordering, retries or persistence exists. No HA/live,
ARM throughput, SQL batch, authority or deployment gate was run for this pure slice.

Reproduction: pytest with -p no:cacheprovider -c pytest-v3.ini tests/v3
--hypothesis-seed=3145; Ruff with ruff-v3.toml and mypy with mypy-v3.ini.
Mutmut run in a fresh isolated copy with only_mutate=fact_state.py and all V3
tests. Permanent scope includes this new module (24 total).
