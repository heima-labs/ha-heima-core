# Producer claim composition — impact recorded before implementation

Parentf5f2369, planningaa4455a clean/read-only. L0 §4/§4.0/§5.1/§13,
L2 §2.3, L1 §5 own reservations, global state uniqueness and reference resolution.
Reuse FactTypeClaim/glob validation and canonical Location; no competing registry.

Bounded pure runtime/producer_staging.py: immutable static claims, all15 fixed
core reservations always included, compose claims, validate global static identity,
resolve declared owner/state-event semantics into immutable concrete type bindings.
Explicit immutable room/zone ID snapshots are inputs from future candidate registries;
no unknown room/zone may pass. They do not implement Room/Zone definitions or certify
registry completeness. Core reservations are metadata, not instantiated producers.

Composition and resolution run only at staging. Bindings are metadata, not bearer
capabilities/source trust or a lifecycle admission service. Dynamic namespace
producers remain covered by their type claim; actual invocation requires future
owner-specific ports and active-generation checks. Exact static duplicate claims
reject even for the same owner; equivalent type-pattern claims may coexist.

No index/coordinator/order/SQL/worker/HA adapter added. Domain structs immutable;
factory-only composition/binding output. Failed candidate leaves existing output
unchanged. No partial publication or global mutable table. Inputs copied to owned
concrete Locations; validate exact source shapes to avoid subclass hooks.

Decision matrix: core exact/broad reservation conflicts; declared/undeclared/wrong
owner/event static claims; duplicate key versus distinct place/type; each scope's
known/unknown inventory references. BVA empty composition/inventories, duplicate
same owner, room set minimum cardinality, opaque Unicode/case and ID differences.
MC/DC independent owner/kind conditions and multi-room membership conditions.
PBT permutation-invariant semantics and static duplicate detection across Locations.
Mutation: fresh scoped module plus15 reservation-omission and output decorator seeds.
## Results and five-method evidence

63 focused cases; full V3 **1567 passed**, Hypothesis seed3145. Ruff lint/format
82files,mypy32sources and diff check pass. Default mutation scope26modules.
No dependency or public HA/persisted schema change.

Decision tables cover all15 core reservations with wrong owner and wrong kind,
matching equivalent declarations, broad wildcard conflicts, undeclared/wrong-owner/
event static claims, duplicate same-owner static keys and distinct type/place keys.
Location rows include casa, room, zone, and multi-room with neither/first/second/
both IDs missing. A failed candidate cannot change an earlier immutable result.
Bindings resolve to the fixed owner and kind, including event metadata; these are
not running producer ports. Concrete type validation remains the shared helper.

BVA: empty composition with mandatory reserves and empty inventories; zero versus
one declared static producer; duplicate identical claim; minimum two-room set;
empty/bad inventory IDs and independent room/zone surrogate inputs without static
claims (avoids masking by later missing-reference checks). Location subclass key
hooks cannot evade identity, because owned fields reconstruct a concrete Location.
Canonical set ordering and opaque Unicode IDs retain existing Location semantics.

MC/DC: this module introduces no compound Boolean decision (no and/or predicate).
Each rejection guard is independently exercised. Owner validation and state-kind
validation are separate sequential decisions; they are not mislabeled as MC/DC.
Multi-room all-members semantics are isolated by complete, first-missing,
second-missing and both-missing fixtures. Reused Location/glob compounds retain
previous five-method evidence; their source is unchanged.

PBT: permutation of candidate claims/static rooms preserves resolved semantics;
generated opaque room identities always reject a duplicate; permuting multi-room
set inputs cannot evade duplicate detection. Seed3145 used for each.

Fresh mutmut213generated,149killed,64individually reviewed generic-error-prose
equivalents, zero errors/timeouts/skipped/untested/interrupted. An initial surviving
inventory-encoding mutant exposed masking in a test, fixed by using no static
producers for malformed-input cases. Restarted from fresh mutants directory;
production source unchanged and the semantic mutant is now killed. All23 semantic
supplements killed with clean63-test baseline:15 reserve omissions,2 owner/kind
changes,6 frozen/slots mutations. Exact diffs in PRODUCER_STAGING_MUTANTS.md.
No collection/no-selection counted as a kill. No production bug fix was needed.

Commands: pytest -p no:cacheprovider -c pytest-v3.ini tests/v3 --hypothesis-seed=3145;
Ruff with ruff-v3.toml; mypy with mypy-v3.ini; mutmut run --max-children 4 in a fresh
copy scoped to producer_staging.py; python tests/v3/mutation_producer_staging.py.
Caches and mutation artifacts isolated under /private/tmp.

## Remaining integration boundary

Inventory snapshots must come from the same staged Room/Zone candidate; this module
does not validate their definitions/membership constraints, legal scopes of a
specific Sensor/Formula, or Sensor/Fusion registry-ID uniqueness. It does enforce
that every static Location reference exists in the supplied snapshot. Core claims
reserve names even before their actual producers are implemented. Dynamic future
Layer7 invocation/lifecycle is not implemented. resolve_type is staging only;
future concrete producer ports must receive resolved metadata, assign sources
at verified boundaries and check active generation. No strings supplied in a
FactTypeBinding prove runtime actor/owner authority. Runtime facts have no new fields.
Actual index, acceptance, AppendOrder, queue/SQL, HA wiring and ARM throughput
validation remain future work. Planning remains read-only, no deploy.
