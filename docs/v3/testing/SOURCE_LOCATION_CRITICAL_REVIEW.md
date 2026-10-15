# Critical review — source values, Location and serialization, 2026-10-15

## Scope and owning contracts

Committed source slice as `0207174` after1243 tests and diff check. Review covers
that slice, Location (`cdea575`), and connections to generic RFC8785 encoding and
immutable SQLite clock-boundary operations (`0c5a637`). Planning f191d2c clean and
read-only: L1 §5/§10 canonical Location, L0 §4.0 source fingerprint, §5/§5.1 source
shape/authority/redaction, §4.2/§4.4 atomicity and acknowledgement. No spec edit.

## P2 — Location identity trusted overridable hooks (fixed)

The canonical key property called `self.__post_init__()` virtually. An inherited
Location subclass could skip that validation: `UncheckedLocation("invalid")` acquired
key `(casa,)`, compared equal to the whole house, shared its hash and encoded as
`["casa"]`. A valid room subclass overriding `key` could likewise cause encoding
and inherited equality/hash to identify a room as the house. This violates L1 §5's
single canonical identity and risks incorrect current-state keys or stored subjects.
No live state index exists yet, so this is a reproduced primitive defect, not a
claim of already corrupted production history.

Five initial regression instances failed on the committed baseline: invalid subclass
key/hash/encoding, invalid subclass equality and wrong-key room encoding. All passed
after correction. One owned `_location_key` function explicitly invokes the base
validator and derives the key from the four declared fields. The base property,
inherited equality/hash and key-text encoder all use it; they do not delegate to a
subclass key or validation hook. Normal values retain identical keys/JSON/hash.
The metamorphic property varies all four scopes, opaque IDs and arbitrary false
keys; derived and base values with identical owned fields must encode/compare/hash
identically. This is ordinary canonicalization, not a Python sandbox: arbitrary
subclasses can override their own methods, but core identity operations own the rule.

## P2 — operational sources admitted extended schemas (fixed)

Runtime shape validation accepted any `isinstance` subclass of FactSource or
ApplyStepSource. A frozen dataclass subclass with `actor_ref="fixture-person"`
passed admission; the existing generic frozen-record codec serialized that extra
field. This contradicts L0 §5's operational source shape with no actor identity,
and §5.1's redaction boundary. The demonstration uses synthetic fixture content;
there is no integrated live source-storage path or actual person-data exposure.

Two regression instances first failed because validation did not reject the extended
source. Runtime shape validation now admits the exact two concrete source classes;
fingerprint extraction requires the concrete FactSource. This keeps an open Python
subtype schema from entering this closed operational record contract. Own field
validation still runs on accepted concrete instances, including forged attributes.
A property generates extra actor_ref/raw_payload/extra fields and both modes and
source kinds; every extended record must reject, independently of its field value.

Compatibility assessment: previously accepted subclasses are now rejected by these
new boundary functions. No production caller exists (repository reference search);
all valid concrete source inputs and persisted fields retain their shape. No
stored schema, identifier, HA entity/service or V2 data changes. The generic codec's
allowed frozen-record *value* support serves other contracts; source admission must
run before encoding. Direct generic serialization is not an authorization/redaction
boundary. No arbitrary source sanitization policy or authenticated principal is
invented here. Source shape validation still grants no runtime authority.

## Five-method evidence

| Input/rule | Expected boundary behavior | Evidence |
| --- | --- | --- |
| Ordinary valid Location | Existing canonical key/hash/JSON | Existing full scope table and fixtures |
| Invalid subclass skips construction validation | Reject at core identity/encoding | Four new regression instances |
| Valid subclass reports a false key | Owned fields determine canonical identity | New fixed fixture plus property |
| Concrete source with exact fields | Validate mode/types and preserve stable fingerprint | Existing source decision tables |
| Extended source, extra field, production or test mode | TypeError before operational admission | Two new regressions plus property |
| Forged concrete source fields | Revalidate and reject wrong shapes | Existing forged-source table |

BVA: exact declared source field set versus one added field; empty/nonempty added
values; ordinary valid Location versus invalid scope; fixed room versus house key.
Existing shape/cardinality/Unicode boundaries stay required. MC/DC: existing compound
shape/mode tables remain; new exact-type guards and helper routing introduce no new
compound Boolean decision. The table isolates ordinary/extended type at fixed source
fields and mode. Two new seeded PBTs exercise identity invariance under overridden
keys and rejection under varied schema extensions. Mutation evidence is in
SOURCE_LOCATION_CRITICAL_REVIEW_MUTANTS.md; earlier per-slice reports are historical.

## Other reviewed paths and limits

No other confirmed defect found in the reviewed source vocabularies, data modes,
causal propagation, stable-field inclusion/exclusion, key-text recovery or SQLite
clock-boundary composition/reconciliation. The entire V3 suite is required for the
cross-contract regressions. This is not a full project audit or a new benchmark.
Actual source authority/redaction adapters, Provenance/full HouseFact, fact/marker
SQL and HA lifecycle remain unimplemented, as recorded before review. No deployment,
power-cut, ARM throughput or live HA verification is claimed. No planning edits.


## Final validation and planning state

Combined Location/source focused292 instances (120/172); full V3 **1252 passed**,
seed3145. Ruff lint/format70files, mypy28sources and diff check pass. Fresh scoped
mutmut339generated,253killed,86individually reviewed equivalents; no errors,
timeouts or untested/skipped/interrupted. Existing23 and new6 semantic supplements
all killed, with clean baselines. Exact diffs/proofs in companion mutation report.

Planning was clean at f191d2c on task start. At final review it has another session's
in-progress CA4-104 changes: Topology passage type and between-floor rules, Layer2
opening bindings, Layer8 map and navigation/orientation docs. Read the live L1/L2/
registry diff and CA4-104 review: Location §5 and source contracts are unchanged,
so these fixes need no adaptation. Do not describe planning as clean at task end;
Codex made no planning edits. Re-read the current working copy when resuming.
