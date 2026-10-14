# First V3 behavioral slice: payloads and canonical JSON

Status: implemented locally, 2026-10-14. Owning specification: planning `9cd077e`,
Layer 1 §3 (`L1-DEEP-IMMUTABILITY`, `L1-NUMERIC-DOMAIN`), §4 and §4.3
(`L1-EVIDENCE-FAILURE`), §10. CA4-28/96/97 are incorporated. No spec changed.

## API and boundaries

- `canonical_json_bytes(value) -> bytes`: shared JCS codec adapter. Frozen mappings,
  tuples and frozen dataclass fields project to ordinary JSON. It rejects Enum
  objects, unsupported objects, invalid Unicode, non-string keys and cycles. It
  has no fact-specific depth/size cap because configuration has different limits.
- `freeze_house_fact_value(value) -> PreparedPayload`: validates the payload, freezes
  it and retains its canonical bytes. Maximum collection depth 2, inclusive safe
  integer bounds and 8192-byte cap. Tuples are admitted as input only within a
  qualifying frozen dataclass; lists freeze to tuples. Ordinary map/list payloads
  cannot hide dataclass objects. Frozen dataclass type and declared fields survive;
  copying does not invoke construction callbacks or retain undeclared attributes.
- `validate_house_fact_value(value) -> None`: staging entry point for the same rules.
- `freeze_persisted_projection(value) -> PreparedPayload`: mapping-only entry point,
  without the dataclass exception. Evidence uses this same mapping shape.
- `prepare_evidence(value) -> EvidencePreparation`: invalid evidence produces an
  empty frozen mapping and one typed diagnostic code; valid evidence has none.
  This function emits no event; the future runtime consumes the result.
- Prepared payload equality/hash use canonical bytes (not Python bool/int equality).
  Local `hash()` is not a durable fingerprint. The result is construction metadata,
  not an extra HouseFact field or persisted envelope. Callers use preparation
  functions, not unchecked hand-built PreparedPayload objects.

Each mapping owns a new private dict behind MappingProxyType; recursive copies
prevent mutation of the producer input from changing the result. Primitive input
uses built-in JSON types; Enum objects must be projected to their primitive value.
No HA dependency, HouseFact assembly, timestamp, database, scheduler or deployment.
No JSON text decoder is included: a future decoder must reject duplicate keys
before building a dict. JCS output is unambiguous; input dictionaries cannot retain
already-lost duplicates. MappingProxyType is an internal representation, not an
additional admitted raw EvidenceValue type.

The runtime codec is rfc8785 0.1.4, pure Python, pinned separately in
requirements-v3-runtime.in/txt with the universal wheel SHA-256. Our validator
controls domain shape: the dependency's acceptance of tuples alone does not widen
raw fact input. Its code is not mutated by our suite; standard vectors verify
selected required boundary behavior, not exhaustive verification of all floats.

## Decision table

Tests: tests/v3/contracts/test_payloads.py and test_canonical_json.py.

| Rule | Input | Value result | Evidence result | Test family |
|---|---|---|---|---|
| D01 | Valid primitive / safe finite number | Retained | Retained in root mapping | scalar_decisions, valid_evidence |
| D02 | Bool | Boolean retained | Boolean retained | scalar_decisions, equality |
| D03 | Integer outside safe domain | Reject | Empty + integer code | invalid_value_and_evidence, outside_safe_domain |
| D04 | NaN/infinity | Reject | Empty + nonfinite code | invalid_value_and_evidence |
| D05 | Unsupported object, enum, tuple outside record | Reject | Empty + type code | invalid_value_and_evidence |
| D06 | Invalid Unicode / non-string key | Reject | Empty + Unicode/type code | invalid_value_and_evidence |
| D07 | Collection depth 0/1/2 | Retain | Retain mapping at depth <=2 | allowed_depth |
| D08 | Collection depth 3 | Reject | Empty + depth code | invalid_value_and_evidence, record_tuple_and_depth |
| D09 | Canonical byte size <=8192 | Retain | Retain | ascii_size_boundary, collection_size |
| D10 | Canonical byte size >8192 | Reject | Empty + size code | size tests |
| D11 | Qualifying frozen record | Retain type, freeze fields | Not admitted as evidence root/nested object | record tests, projection tests |
| D12 | Valid mapping projection | Detached immutable mapping | No diagnostic | immutability, valid_evidence |
| D13 | Non-mapping projection root | Reject | Empty + mapping code | projection_is_a_mapping |

Other classification combinations are intentionally impossible: e.g. exact bool
and exact int simultaneously, or the same object being an exact list and tuple.
A record's normalized field mapping adds depth 1; a collection field adds depth 2.

## Boundary Value Analysis

- Integers: both safe bounds, the adjacent inside values and the first outside
  values; generated further out-of-domain integers must never be coerced.
- Size: 8191/8192/8193 canonical bytes, including quotes; multibyte UTF-8,
  escapes and the complete root mapping contribute to the limit.
- Depth: scalars and empty/nonempty collections at depths 1/2/3; frozen records
  count their normalized field object as a collection, including tuple fields.
- Floats: finite maximum, minimum subnormal 5e-324, signed zero, NaN and infinities.
- JCS: exponent-format boundaries 1e-6/1e-7 and 1e20/1e21, rounding vector from
  RFC 8785 Appendix B, recursive UTF-16 object-key sorting, array order,
  preserved composed/decomposed Unicode and control-character escapes.

## MC/DC pairs

MC/DC here is explicit decision-pair evidence, not a coverage claim. Traversal
context is exercised directly in test_mcdc_traversal_context while the public
entry-point families check end-to-end results.

| Decision | Atomic condition | Independent pair (other applicable conditions held fixed) |
|---|---|---|
| scalar-type OR None, codec | scalar membership | int 1 / unsupported object (not None) |
| scalar-type OR None, codec | None | None / unsupported object (neither a scalar type) |
| None OR bool, freeze | None | None / unsupported object (not bool) |
| None OR bool, freeze | bool | True / unsupported object (not None) |
| lower <= integer <= upper | lower bound | -9007199254740991 / -9007199254740992 (upper holds) |
| lower <= integer <= upper | upper bound | 9007199254740991 / 9007199254740992 (lower holds) |
| list OR (tuple AND record_context) | list | [1] / unsupported object, context false, neither tuple |
| list OR (tuple AND record_context) | tuple | (1,) / unsupported object, context true, neither list |
| list OR (tuple AND record_context) | context | (1,) with false / true context, list false |
| allow_record AND is_dataclass AND not-class | allow_record | Record(1), allow false / true |
| allow_record AND is_dataclass AND not-class | is_dataclass | unsupported instance / Record(1), allow true, neither class |
| allow_record AND is_dataclass AND not-class | not-class | Record class / Record(1), allow true, both dataclasses |
| is_dataclass AND not-class, codec | is_dataclass | unsupported instance / frozen record instance |
| is_dataclass AND not-class, codec | not-class | frozen record class / instance |

The membership/any predicates are single classification conditions; tests include
all accepted categories and wrong key types. Single-condition size, finiteness,
frozen-record and projection-root gates have both outcomes covered.

## Property-Based Testing

Hypothesis seed 3145. Generated mapping permutations have identical canonical
content and local hash; changing original inputs leaves frozen bytes unchanged.
Generated arrays retain order and contents after source mutation. Generated
out-of-domain integers fail rather than round/coerce, including inside evidence.
Oracles are specified bytes, independent limits and relational invariants; no
copy of the production traversal is used as an oracle.

## Mutation Testing

mutmut 3.8.0: **265 generated, 231 killed, 34 survived**, no timeout/error/untested.
Source scope: the two changed modules; tests load the copy in mutants/, verified
by test_mutation_imports_resolve_to_active_source_tree. Clean baseline and forced
failure checks passed. A fresh run after strengthening tests avoided stale tool
results. The mutation run used 107 tests; two additional inside-boundary integer
cases and a codec class-rejection assertion raised the final suite to 109 tests
without changing production source or the mutant classification.

Every surviving diff is recorded in PAYLOAD_MUTANT_REVIEW.md. Survivors are
runtime equivalent casts, identical UTF-8 aliases, irrelevant key traversal
arguments, false-to-None context flag, or generic error prose changes outside
the promised contract. Typed PayloadValidationError codes are tested. No known
non-equivalent survivor remains. This is not a claim of a 100% raw mutation score.

Supplement: python tests/v3/mutation_constants.py. Six module/decorator mutations
are killed by specified failing tests: integer/depth/size cap increases and removal
of frozen metadata on prepared payload, evidence result and diagnostic. An
additional exploratory eq=False->eq=True mutation is equivalent because explicit
__eq__ and __hash__ methods are retained; it is not counted as a killed mutant.
The supplementary runner uses a temporary checkout and leaves workspace source
unchanged. Type alias/Protocol declarations have no changed domain behavior.

## Results and reproduction

Run from the implementation worktree with native .venv-v3:

```bash
.venv-v3/bin/python -m pip install --require-hashes --only-binary=:all: -r requirements-v3-runtime.txt -r requirements-v3-dev.txt
.venv-v3/bin/python -m pytest -c pytest-v3.ini tests/v3/contracts --hypothesis-seed=3145 --cov=custom_components.heima.v3.contracts --cov-branch --cov-report=term-missing
.venv-v3/bin/ruff check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/ruff format --check --config ruff-v3.toml custom_components/heima/v3 tests/v3
.venv-v3/bin/python -m mypy --config-file mypy-v3.ini custom_components/heima/v3
.venv-v3/bin/python tests/v3/mutation_constants.py
.venv-v3/bin/mutmut run --max-children 4
.venv-v3/bin/mutmut results
```

Final focused suite: **109 passed**, all 134 statements and 52 reported branches
covered. Coverage is supporting evidence, not MC/DC certification. Ruff, format
and mypy pass. No numerical quality threshold is introduced. No HA/live/crash/
performance test ran. No duplicate-key text decoding or serializer replacement
was implemented. The next domain slice remains to discuss.
