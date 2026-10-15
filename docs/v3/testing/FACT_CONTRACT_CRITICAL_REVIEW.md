# Critical review — fact construction and state comparison, 2026-10-15

## Scope and result

Reviewed 50b9cc8 (state identity/change comparison), d921fd6 (HouseFact builder)
and their Source/Location dependencies c9b6c62,0207174,cdea575. No confirmed
correctness defect or new specification contradiction found within these
implemented contracts. This is scoped review evidence, not proof that Layer0/1
is fully implemented.

Planning aa4455a was clean and read-only. Read planning AGENTS/workflow/registry,
L0 §4.0/§4.2/§5/§13, L1 §3/§4/§5; inspected production modules, callers, tests,
mutation reports and existing source/location review. The new primitives have
only test callers; there is no running persistence coordinator using them yet.

## Paths checked critically

- Identity excludes content, provenance and time. Canonical Location equality/hash
  agree, including code-point-sorted room sets and opaque room/zone identifiers.
  Stable source changes never partition the current-state identity.
- Fingerprints include every stable source field, availability and confidence.
  Time/correlation/evidence changes affect full HouseFact equality but not change
  comparison. Unavailable value is excluded before projection. Canonical equality
  avoids True==1 while respecting1/1.0 and signed-zero equivalence.
- Dataclass normalization uses declared fields, freezes nested mappings and tuple
  contents and preserves primitive numbers. It does not decode canonical decimal
  text into potentially out-of-domain integers (for example finite float1e20).
- Builder validates/freeze-copies both payloads, keeps unavailable raw values
  storage-safe without making them usable, returns bounded evidence diagnostics,
  and rejects essential invalid metadata. Confidence endpoints/nonfinite/bools,
  omitted versus explicit invalid evidence, and source mode propagation inspected.
- Source shape checks reject extended source schemas, test data in production and
  legacy runtime data. They do not confer authority. Builder copies all source
  fields, preserves correlation and owns concrete Location fields.
- No implicit clock, storage I/O, HA calls, additional persisted fact fields,
  current-index mutation, queue coalescing or durable acknowledgements introduced.
  Public HA contracts/configuration and V2 runtime are unaffected.

## Executable evidence

Re-ran full V3 suite: **1413 passed**, Hypothesis seed3145. Ruff check and format
pass (76 files); mypy pass (30 source modules); git diff --check pass.
Commands used the existing pytest-v3.ini,ruff-v3.toml,mypy-v3.ini and isolated
Hypothesis/mypy cache directories under /private/tmp.

Additional isolated review probe:144 scenarios =4 Location forms ×18 admitted
values ×2 availability states. Each compares an original fact to one changing
only time/correlation/evidence; checks distinct full records, equal identity/hash,
equal change fingerprint/hash and exact five-field JSON envelope. Values include
None,bools,signed zero,int/float1,safe-int endpoints,smallest positive subnormal,
finite float1e20,max finite float,composed/decomposed Unicode,empty containers,
a depth2 mapping/list and a two-level frozen dataclass. Explicitly verified nested
frozen-record versus JSON equivalence and nested mapping immutability.
Probe ran as /private/tmp/heima-v3-fact-review-probes.py; no failing case found.

Existing five-method tests/mutation evidence inspected in HOUSE_FACT_BUILDER.md,
HOUSE_FACT_BUILDER_MUTANTS.md,FACT_STATE.md,FACT_STATE_MUTANTS.md and the prior
SOURCE_LOCATION_CRITICAL_REVIEW.md. No production behavior changed in this review;
no new mutation campaign was needed or claimed. No failing-before-fix evidence,
because no fix was made. Review-only cross-product probes are not a substitute
for the existing property/mutation tests.

## Known incomplete scope, not defects in this slice

Producer authority/generation checks, redaction, emission-kind routing and ownership
composition must precede actual runtime admission. Events bypass these state
comparison primitives. FactIdentityKey currently has a fact-extraction factory;
validated read-query key construction is not implemented. Current index,
AppendOrder coordinator, ordered retry queue, forced durable baselines and atomic
facts+CycleCommitMarker SQL remain future work. The on/off/on test proves
fingerprint distinctions, not actual append delivery. HA integration/live tests,
Raspberry Pi throughput and deployment were not exercised. No new policy proposed.
