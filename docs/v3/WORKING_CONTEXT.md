# V3 implementation working context

Update this file at the end of every bounded task and before yielding on an unfinished task.
Keep verified state and distinguish user-approved decisions from proposals. Newer user
instructions override the next action below.

## Verified state — 2026-10-14

- Implementation workspace: `ha-heima-component-v3-implementation`, branch
  `feat/v3-implementation`, branched from planning `0063da4`; the previous instruction commit is `6fe67b8`.
  The current environment/tooling files are included in the developer-requested commit;
  use `git log -1` and status for the latest revision each session.
  The first pure V3 payload/codec slice and behavioral tests are implemented locally.
  No HouseFact assembly, HA runtime adapter, storage or deployment exists here.
  The dedicated native Python/test-tool environment is ready; its probes ran in /private/tmp.
- Authoritative specs: sibling `../ha-heima-component-v3-planning`, branch
  `feat/v3-planning`, CA4-70 progressive recovery committed as `f84d4e7`; latest planning HEAD
  checked for this task is `9cd077e` (clean). Its Layer 0–6 specs supersede this checkout's older copies.
  Layer 8 is now authoritative too (`5f4cf1b`, registered in contract_registry); Layer 7 remains separate. Recheck HEAD,
  status and current contracts each session because another session is developing specs.
- Planning structural check rerun on 2026-10-14: 8 authoritative layers, 128 mapped
  contracts, 96 CA4 issues, 0 open, 72 reviewed slices. This is structural evidence,
  not runtime validation. Older checkpoints below are historical; the latest Layer 0/1
  synchronization supersedes their reaction.decision event model.
- The inherited V2 component, tests, operational scripts, workflows and obsolete tool configs have been removed from this worktree; V2 remains in its original workspace/history. V3 is a clean
  start with no V2 migration; protect V3 public contracts once introduced.
- CT-4 still has an implementation release gate for frozen numerical calibration and
  reproducible evidence before automatic comfort-trajectory action.
- Previously pending instructions/readiness were committed as `6fe67b8`. The requested
  subsequent environment commit establishes `.venv-v3`/`.python-v3` ignores, the pinned tooling
  requirements, dedicated V3 configs and `TEST_ENVIRONMENT.md`, plus handoff updates.
  Runtime directories are local artifacts, not Git content.

## Current task and approved decisions

The developer requested the three readiness points in order, one at a time. Point 1
is complete: Python 3.14.5 aligned with HA's minimum and running natively arm64 on the
Apple M1; tooling dependencies are pinned with hashes and verified by local probes.
The initial Intel/Rosetta venv was retired to /private/tmp after the user's correction.
The native runtime is workspace-local (uv 0.13.0/CPython standalone), avoiding a global
Homebrew update. Point 2 is now approved and prepared: build the V3 integration
from scratch in this worktree, keeping V2 in its own workspace/history as reference.
Small pure V2 functions may be assessed individually; no V2 runtime dependency.
The approved package groups are empty packages with an inert parent initializer,
so real qualified imports need no test-only namespace shim. The first pure payload/codec
behavior is now implemented and verified below; no HA lifecycle adapter exists.

- Package boundary approved: `custom_components/heima/v3/` with `contracts/`, `runtime/`,
  `storage/`, `adapters/ha/`. Domain contracts contain no Home Assistant imports. Individual
  classes, filenames and future-layer scaffolding remain undecided.
- SQLite approved, in one local V3 database separate from V2, with one serialized writer
  outside the HA event loop. Approved transaction units: end-of-cycle facts plus
  `CycleCommitMarker`; notification `ready` plus its audit fact; composed configuration
  generation. Qualified `reaction.follow_up` preparation waits for its durable result.
- WAL with `synchronous=FULL` and SQLite's backup API are the agreed starting design,
  subject to performance/crash verification. Schema, checkpoint cadence, queue data
  structures and worker implementation are not yet fixed. Verify the deployment's linked
  SQLite version against SQLite's documented WAL-reset fixes before relying on WAL.
- CA4-38/70: hard queue budget, ordinary superseded-state/event loss order, nonblocking
  admission and one exceptional global `queue_overflow` gap when protected items alone
  cannot fit. Global invalidation does not alter the live current index or short-term buffer.
- Recovery approved on 2026-10-13: fresh valid producer assertions re-seed durable state
  baselines over successive bounded cycle batches. Admission is not acknowledgement.
  The global gap can close at an acknowledged fresh intake/full-cycle accounting boundary
  before all keys recover. Reads requiring unseeded keys stay unknown and incomplete;
  global closure never revives an old invalidated record. Failed/discarded seeds retry on
  a later fresh assertion; further irreducible losses advance baseline invalidation.
- A new HA intake is a current read of HA state, not a forced new device measurement.
  Layer 2's existing `unknown`/`unavailable`/`max_source_age` rules remain authoritative.
  An unavailable producer assertion can establish a durable baseline while that stream
  remains unavailable. Missing durable proof alone does not make the live device unavailable.
- No generic old-state fallback was selected. Desired-target Recovery checkpoints retain
  their existing separate contract. Managed-episode facts require owner proof; a fresh HA
  active reading cannot reconstruct an invalidated opening. Recovery-only unchanged seeds
  do not create live-buffer transitions, physical edges, holds or §4.8 observer deliveries.
- Testing approved: real behavioral verification using Decision Tables, Boundary Value
  Analysis, MC/DC, Property-Based Testing and Mutation Testing. The initial pytest,
  Hypothesis, mutmut, Ruff and mypy toolchain is installed/verified; numerical thresholds
  remain open. `CODE_RULES.md` contains the approved permanent code principles; no V2
  compatibility/migration requirement is implied.
- Git and deployment sections of `DEVELOPMENT_POLICY.md` remain proposals pending review.
  The bootstrap commit does not approve them. No commit, merge, push or deploy is implied.

## Work completed and evidence

- Clean-start preparation: removed 428 tracked V2 files (including the
  replaced parent initializer), added seven inert package initializers and the V3 test
  directory guide; replaced root README and marked inherited CLAUDE instructions historical.
  Kept V3 tooling, instruction files and historical documentation. No CI/deploy replacement
  or manifest was invented. Clean-start preparation was committed as `1eaba51` at the user's request. Verification: seven real qualified imports resolve inside this worktree without HA/V2
  modules in `sys.modules`; Ruff lint and format pass; mypy passes on all seven files;
  `git diff --check` passes. No application tests ran. The five behavioral techniques
  have no applicable rule, boundary, compound decision, property or executable function
  to mutate in these docstring-only packages; apply them to the first behavioral slice.

- Workspace/bootstrap, permanent code rules, testing-policy correction and approved module,
  SQLite and transaction decisions are recorded here and in the instruction/decision files.
- Researched bounded queues in Telegraf, OpenTelemetry, Vector and Prometheus and recovery
  patterns in Kubernetes/etcd. Rationale is in `QUEUE_OVERFLOW_DECISION.md`; authoritative
  behavior is owned by planning Layer 0 §§4.0/4.2/4.4/4.6 and the CA4-70 review.
- Updated planning Layer 0, Layer 3 historical consumers, Layer 5 managed-episode validity,
  CA4-70 review, registry/dependencies, backlog, overview and recap. Added scenarios for a
  seed volume above budget, unavailable sources, unchanged seeds, ordered updates,
  repeated overflow, closure with pending keys and crashes before/during/after closure.
- Reviewed §4.8 and Layer 6: notifications observe live committed state, independently of
  durable storage. Their semantics require no modification for this correction.
- `python3 scripts/check_v3_specs.py --issue CA4-70`, `--open` and `git diff --check`
  pass in planning. No V3 runtime, behavioral, crash, performance, CI or live test ran;
  this task changes specifications and instructions only.
- Committed only our eight CA4-70 planning files as `f84d4e7` with DCO sign-off. The
  implementation instruction/audit files are included in the requested separate commit.
  Existing Git/deploy proposals stay unapproved. CA4-69 belongs to the parallel
  specification work and was not edited. Use contextual patches against the latest worktree, avoid whole-file
  overwrites from stale copies, and recheck concurrent changes before writing.

- Environment verification: hash-checked wheel installation and `pip check` passed;
  Python/executable architecture is arm64, version 3.14.5. A temporary probe passed
  9 pytest cases including generated properties and asyncio; Ruff/mypy passed and
  mutmut killed 3/3 mutants. This is tool evidence, not Heima behavior validation.
  Commands, versions and limitations are in `TEST_ENVIRONMENT.md`.

## Earlier EvidenceInstant-first proposal — superseded by the payload slice

The clean-start commit is complete (`1eaba51`). The user requested discussion of the complete fact data model before agreeing on the first behavioral contract.
Proposed first slice: `L1-EVIDENCE-INSTANT`, Layer 1 §4 and its §10 acceptance case,
registry dependencies empty, checked at planning `761294d`. No application code yet.
Proposed files: `custom_components/heima/v3/contracts/instants.py`,
`tests/v3/contracts/test_instants.py`, `docs/v3/testing/EVIDENCE_INSTANT.md`.
Proposed API: semantic string type `EvidenceInstant`, strict validation/parsing of
`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`, and explicit formatting from an aware datetime
(normalize its represented instant to UTC; reject a naive datetime). Contract-field
validation accepts only the exact canonical string and never silently repairs input.
Test evidence: validity decision table, date/fraction/offset boundaries, independent
validation-condition pairs where compound decisions exist, generated round trips and
normalization invariants, mutation scope on this module. Exact API names/error types
remain a proposal. This does not implement the cycle clock, scheduler or persistence.

## Complete fact data model — discussion, no new implementation approval

At planning `c8a68a8`, reread Layer 1 §§3/4/5 and Layer 0 §§4.0/5.
Specified envelope: immutable `HouseFact(fact_type, value, where, when, how)`, with
`Location`, canonical `EvidenceInstant`, and `Provenance(confidence, source, available,
evidence)`; structured `FactSource` vocabulary belongs to Layer 0. Value/evidence
allow depth 2 and at most 8 KiB canonical UTF-8 each; value additionally admits
qualifying frozen dataclasses. Deep freezing and RFC-8785 serialization are required.
Invalid value fails construction; invalid evidence becomes empty with a diagnostic,
without discarding the fact. Unavailable implies confidence None and unusable value.
State identity is WHAT+WHERE; change fingerprint includes availability, confidence,
normalized value and stable source, excluding when/correlation/evidence. Events have
no current-state identity; append ordering and state/event registration are runtime
metadata, not extra HouseFact fields. State when records the accepted change, not
last observation; observation coverage/source-report age remain separate mechanisms.
Proposed modules: instants, locations, sources, payloads, provenance, facts; pure
canonical serializer/freeze must exist before full fact construction. Concrete JSON
library and diagnostic delivery API (prefer pure construction results plus runtime
delivery over logging/I/O in value objects) remain to discuss. No code implemented.

## Claude Layer 0/1 sync — verified at planning `c8a68a8`

Read the supplied handoff and current owning sections; planning is clean and was not
edited. This is specification alignment, not approval to implement the proposed APIs.
The five HouseFact fields, identity, write-on-change, payload limits, deep immutability
and existing queue/recovery contract remain unchanged. Map the supplied eight items:

1. CA4-72, Layer 1 §3.1: `OperationalEventValue` has exactly notification_key, severity,
   context_version (integer >=1), context. No title/message; context holds closed fields
   and stable identifiers, never names/text/HA entity ids/person identities. Adapter
   checks the version registered for fact_type and its closed context schema; Layer 6
   renders delivery text. This restriction is for notification context, not a global
   ban on every FactSource.source_id. Typed value remains inside HouseFact.value.
2. CA4-74, Layer 5 §6.0: add reaction_descriptor_id to follow-up intent/occurrence and
   action notice occurrence. Intent projection retains it; notification context includes
   it. Keep subject as HouseFact.where, occurred_at as when; flatten follow-up facet
   maps into canonical JSON-text scalar expected.<facet>/observed.<facet> context keys.
   Read serialization examples: intent bytes 763/694/747; event bytes 891/786/856,
   all depth 2. These are documented fixtures, not freshly executed serialization tests.
3. CA4-79, Layer 0 §4 / Layer 1 §3.1 / Layer 5 §5.2 Decision record: reserve event
   claim reaction.decision owned by layer5.reaction_decision. ReactionDecisionValue is
   distinct from OperationalEventValue: ids, mode, outcome, reason tuples, flat tuple
   of failed capability_id strings, admission and admission suppression codes. Append
   once per evaluation identity when outcome != not_triggered; default retention.
   Existing notification claims remain; Layer 5 §6.0 typed occurrences have closing
   phases/response_request_id and consent reissued. Do not flatten typed occurrences
   into arbitrary generic messages or treat every event as a notification.
4. CA4-71, Layer 0 §4.5: no extra NotificationDeliveryRecord field. Permit ready->retired
   without delivery while preserving its audit fact; one digest attempt may acknowledge
   multiple ready records, each with its own delivered transition. Atomic audit+ready
   and operation uniqueness remain. Delivery transition policy belongs to Layer 6.
5. CA4-73 U3, Layer 0 §4.7: Layer-6 generation includes recipients/family options. Changes
   solely to them have no dependents, empty impact and no impact confirmation. These
   are configuration records, not new HouseFact/Provenance fields.
6. CA4-75/80, Layer 0 §4.8: add CommittedStateSubscription(subscriber_id, fact_key) and
   CommittedStateChange(fact_key, fact|None, cycle_when) to future runtime contracts.
   Core-only exact state keys; bootstrap declaration or atomic generation-swap
   redeclaration; initial delivery for added keys, stop removed keys. Post-in-memory
   commit async delivery, coalescing in cycle order, per-run initial value and isolated
   failures. No durable record, event fact, DAG dependency or durable-ack wait.
7. CA4-78, Layer 0 §4.7: retain every committed manifest and referenced layer generation
   indefinitely, read by id on slow path. Outside fact retention, no pruning job; only
   latest manifest active. This constrains future storage, not HouseFact shape.
8. CA4-70: global overflow invalidation and progressive recovery unchanged.

No contradiction found between these changes and the generic model reviewed so far.
The previous six-module proposal covered the generic fact primitives, not a complete
inventory of event, configuration and runtime-observer contracts. Need to account for
OperationalEventValue and versioned adapter schemas in that roadmap, with module
placement still a proposal. Keep Layer-5 typed values owned by Layer 5.
Updated WORKING_CONTEXT and RESUME_PROMPT only; no app code, runtime tests, spec edits
or additional commit. `git diff --check` passed for the handoff patch. Continue discussing
the complete model/API before approving the first implementation slice.

## Fact construction API — approved by the user

The user resumed fact definition; no request to implement yet. Layer 1 §3 rechecked
at clean planning `3525c1b`. User approved immutable dataclasses and one public fact-building
entry point taking explicit fact_type/value/location/instant plus source/confidence/
availability/evidence, assembling Provenance and HouseFact internally. Return a typed
construction result containing the valid HouseFact and bounded diagnostic descriptors
(not raw offending payloads). Essential invalid fields/value reject construction;
invalid optional evidence becomes empty and produces a diagnostic descriptor. Runtime
admission must consume/emit those diagnostics; no logging, HA event, I/O or implicit
clock in the pure builder. Result is local construction metadata, never an extra
HouseFact field or persisted envelope. Constructor/internal API details and precise
error types remain open; enforce validation across all supported construction paths.
Source authority and concrete value semantics remain owning-boundary checks, distinct
from universal shape checks. The construction approach and FactBuildResult are approved; implementing code, exact types/module details and first slice still require the ongoing discussion.

## Frozen payload / canonical serialization — proposal, unresolved library limit

User requested discussion; no implementation yet. Layer 1 §3 rechecked at planning
`299c9ff` (clean). Proposed stdlib representation: mapping proxies over new private
dicts, tuples for input lists, and preservation of qualifying frozen dataclass types
with frozen fields. Input tuple restrictions remain as specified; internal tuple
representation does not widen admissible input. No sorting of generic list contents;
Location room_ids has its own code-point set order, distinct from JCS key UTF-16 order.
Proposed single internal canonical-JSON wrapper for fact validation/size/equality/hash
and later fingerprints. Python hash is local, not a durable identifier; SHA-256 of
canonical bytes for contracts explicitly requiring stable digests. No new type tag
or rendered notification text added to the wire shape.
Candidate library `rfc8785` (Trail of Bits), pure Python/no dependencies, UTF-8 bytes
output; not installed or approved. Read README and source, compared to RFC 8785 §3.1
and Appendix B Note 1. Its int range ±(2**53-1) is intentionally stricter than exact
binary64 representability: it rejects 2**53 although that value is exactly representable.
Layer 1 §§3/4 admit int with JCS serialization and give no explicit such safe-int cap.
Report this contract/library mismatch before selection; do not silently reject extra
values, round big integers or convert them to strings. Need developer/spec-owner
clarification of intended integer domain or selection of a compatible serializer.
References: github.com/trailofbits/rfc8785.py/blob/main/README.md and
raw.githubusercontent.com/trailofbits/rfc8785.py/main/src/rfc8785/_impl.py,
www.rfc-editor.org/rfc/rfc8785.html, Python 3.14 types.MappingProxyType docs.
Only context updated; no planning edits, runtime tests or dependency changes.

## RFC 8785 versus other codecs — evaluation requested, no change approved

User requested evaluation of JCS alternatives including Protobuf. Primary references
reviewed: protobuf.dev/programming-guides/serialization-not-canonical/, proto3 guide,
Python generated-code guide and google.protobuf well-known types; RFC 8785 and RFC
8949 §4.2 deterministic CBOR. Protobuf deterministic encoding is not canonical across
schema/runtime changes; stable V3 fingerprints would still require a separate explicit
semantic projection/canonical rule. Typed proto int64/uint64 retain those integer
domains, but generic google.protobuf.Value stores numbers as double, so Struct/Value
is not itself a solution to exact large integer handling. Generated Python messages
are mutable, requiring boundary conversion to the approved immutable domain objects.
CBOR with a fixed deterministic profile is the plausible binary alternative for
generic maps/lists and exact integers; profile must specify numeric equivalence,
allowed types/tags and ordering. No performance/size measurements conducted.
Recommendation for current local Python/SQLite architecture: keep JCS as common
canonical rule, clarify numeric domain and pick a conforming implementation; no
demonstrated benefit yet from proto schema/codegen plus separate fingerprint codec.
Protobuf may be appropriate later for a concrete external typed protocol; independent
wire storage codec need not replace canonical semantics. A global canonical-rule
change would affect payload byte limits, fingerprints/config generations/operation
ids, scalar facet codecs, LocationKey projections and examples across layers.
No planning edit, library installation, code or benchmark; alternative evaluation is
not an approval to change the RFC-8785 contract.

## Codec direction and Layer-8 consumers — approved / verified

User accepted retaining RFC 8785 and explicitly requested CBOR remain a possible
alternative if measured performance problems justify it. This is an option to
evaluate, not an automatic format switch or approval to implement CBOR now. Keep
canonical encoding behind the common function; future binary persistence/transport
may be evaluated separately from canonical fingerprint semantics. The numeric domain is approved and aligned via CA4-96; concrete library selection
remains pending.

Checked clean planning `f52f86f`: Layer 0 diff since the prior Layer-8 work adds only
read-only handoff of the same RecoveryConfirmationOccurrence (§7.4.1) to Layer 8
pending-items projection, and health snapshots / degradation-diagnostic changes
(§9/§10) to Layer 8 health projection. Layer 8 §10.3 owns in-memory projections,
rebuilt from owners' current state at startup. Fact-mirroring entities retain the
existing §4.8 observers; recovery/health handoffs are owner-produced typed changes,
not new HouseFact events or additional persisted copies. Delivery is outside cycle
evaluation; no change to recovery/queue/persistence mechanisms or fact model.
Track these additional consumers when designing runtime delivery and bootstrap.
No contradiction found in those added handoffs. No planning edits, code, dependency
installation or runtime tests; context/resume updates only, diff hygiene checked.

## Numeric payload domain — approved; incorporated by CA4-96 on 2026-10-14

The user explicitly approved the numeric domain; Claude incorporated it in planning
`15ccdcd` (CA4-96), verified clean on 2026-10-14. Layer 1 §3 is now normative.
Layer 1 §§3/4 admit int and finite float with bool distinct; no explicit safe-int
range is stated. Approved domain for canonical payloads (value, evidence,
normalized frozen-dataclass fields and PersistedProjection): non-boolean int in
[-(2**53-1), 2**53-1]; finite binary64 float, including subnormals, with no generic
physical-range limit; bool only in boolean fields; no Decimal/Fraction/complex or
implicit string/int/float conversions. Quantitative field contracts retain their
stricter ranges/units and count/integer semantics. Integer-valued float is still
binary64 approximate measurement, not an exact arbitrary-size counter workaround.
JCS makes 1/1.0 and +0/-0 canonically equal; stricter contracts such as Layer 3
may reject negative zero. No generic decimal rounding; precise decimal or large
integer encodings need a separately declared schema, never silent string conversion.
Numeric violations follow value hard-fail versus evidence empty+diagnostic rules.
The approved safe-int cap is an explicit Heima restriction, not a rule required by
JCS. Layer-1 specification alignment is complete via CA4-96. See
NUMERIC_DOMAIN_HANDOFF.md for the approved decision and verification status. Candidate rfc8785 is compatible
with this proposed integer range, but no library installation or approval inferred.
Read RFC 8785 §3.1/Appendix B and candidate source; no runtime test or spec edit.

## Claude addendum — data-model mapping at `20bc9ae`

Read owning sections and CA4-84 review; planning worktree clean and read-only.
1. CA4-83, Layer 2 §2.6: add registry-owned Room(room_id, ha_area_id|None,
   display_name|None, floor:int, enclosure:interior|exterior=interior). Semantic
   fingerprint exactly (room_id,floor,enclosure); area/name are metadata. Store
   floor/enclosure, do not read live HA floor as semantics. Nonempty/unique room ids;
   unique linked areas resolved at staging; no-area room needs nonempty explicit name;
   linked area's current name is rendering fallback. Location still holds opaque ids,
   not Room objects; Zone/Topology resolve references through this Layer-2 owner.
2. CA4-84, Layer 1 §7: Opening gains optional display_name, excluded from Topology
   fingerprint. ResolvedConnection has exactly room_a,room_b,opening_id, no access_type
   or legacy connection_id; connections derive from door/door_window, never authored
   separately. Serialized access_type is an unknown-field rejection (CA4-84 review).
   Derived floor/enclosure/exposure views recomputed and checked against Room/Openings.
3. CA4-85, Layer 5 §4.2 Reaction catalog: Layer-5 generation is a reaction_id catalog
   pointing to current configuration generations with display_name metadata. A rename
   produces a new layer generation and composed commit, retaining the SAME Reaction
   configuration generation, authority, activations, consent and jobs; empty impact.
   Effective names unique after trim+NFC+case-fold comparison; composed collisions need
   explicit display_name. This normalization is for display-name collision checks,
   never Location/Room/fact_type/source stable ids. Zone definition fingerprint still
   includes its display_name per Layer 1 §6; execution-semantic fingerprint excludes
   it. Do not globally drop presentation metadata from configuration/audit records.
4. CA4-82, Layer 0 §§7.4.1/9/10: read-only recovery occurrences and health/diagnostic
   changes to Layer 8 remain as previously verified; no new persisted record/wait.
5. CA4-80, Layer 0 §4.8 / Layer 8 §10.3: generation-derived exact-key subscriptions
   re-declared atomically on swaps; supports per-room entity publishing. Not fact fields.
6. CA4-79, Layer 5 §5.2 Decision record: failed_guard_capabilities is flat capability_id
   tuple, not binding ids; one binding per capability per profile generation.

No contradiction found with the generic five-field fact draft in this scoped review.
New Room/catalog shapes belong to their owning registries; do not add them or display
names to HouseFact/Location. Layer 8 now authoritative (`5f4cf1b`), registry verified.
At the addendum checkpoint, first-slice and numeric-domain safe-int proposal were
unapproved. The user subsequently approved the numeric domain; the first slice
remains to agree. No planning edits, app code or runtime
tests; updated own context/resume only, patch hygiene checked.

## Layer 0/1 synchronization — 2026-10-14, `793b6a2`

Compared full Layer-0/1 diff from `20bc9ae`, reread changed sections plus owning
Layer-2/5 dependencies and reviews CA4-89/91/92/95. Planning clean, read-only.
- CA4-89 supersedes CA4-79: reaction.decision.<digest> is STATE, reserved pattern
  reaction.decision.*, owner layer5.reaction_decision. Digest is SHA-256 canonical
  [reaction_id]. One exact key per catalog Reaction at subject; ordinary write-on-change.
  ReactionDecisionValue removes snapshot_id and includes not_triggered/normal_exit
  via the single ReactionEvaluationOutcome. No per-cycle identity inside its value;
  failed_guard_capabilities remains flat capability_id tuple. Latest retained, default
  14-day retention for superseded records. Removal/invalidation emits available=False;
  next evaluation of a valid successor recovers current state (Layer 5 §5.2/CA4-95).
- CA4-86, Layer 0 §§5/5.1.3/7.4.1: all three Initial-V3 response owners allow resident
  and ha_admin. Non-admin response maps to resident_response/resident; verified HA
  admin response to admin_command/ha_admin. actor_ref is verified HA user id, only
  governance, not FactSource/ApplyStep operational payloads. Account category is not
  household membership; owning consent boundary still checks membership.
- CA4-87, Layer 0 §4.7: accepting learned Reaction proposal creates configuration via
  composed commit with empty impact. Atomic transaction includes its review transition,
  manifest, layer records and invalidations; catalog edits explicitly in this path.
- Layer 0 §4.2/Layer 1 §3.1: advisory_feedback dedup by
  (advisory_operation_id, action), scoped to its event family, not generic equality.
- CA4-91, Layer 2 §2.7 / Layer 1 §6: common display-name rule, explicit names nonempty
  trimmed and <=64 Unicode characters after NFC. Uniqueness per kind: Room/Zone/Reaction
  global, Sensor/Actuator per Location, Opening per owning room. Compare trim+NFC+
  case-fold; composed names across all shipped locales. Live HA fallback names exempt
  from uniqueness check. Sensor gains display_name. Names remain outside semantic
  fingerprints; Zone full definition fingerprint still includes name. Never normalize ids.
- CA4-92, Layer 1 §7: OpeningType door/window/door_window; eight CompassOrientation
  values; orientation optional unless consumer requires it. Opening.entity_id REMOVED
  and rejected in serialized input. Opening state only via Sensor.related_opening_id
  or Actuator channel.opening_id. ResolvedConnection remains derived with no access_type.

Generic HouseFact fields/identity/deep freeze/JCS/depth/8-KiB/value-vs-evidence error
policy unchanged. No contradiction found in reviewed changes; confirmed one outstanding
approved-decision/spec alignment: safe-int numeric cap still absent from Layer 1 §3.
NUMERIC_DOMAIN_HANDOFF.md remains pending for Claude; do not silently treat it as
incorporated or edit planning. Numeric/library-dependent implementation waits alignment.
Ran planning checker --open: 8 layers/127 contracts/95 issues/0 open/71 reviews,
structural only. No application code/tests or spec edits. Updated implementation
handoff/instructions, diff hygiene checked; no commit requested/made.

## CA4-96 verification — 2026-10-14, `15ccdcd`

Planning clean and read-only. Compared the complete numeric-domain commit against
NUMERIC_DOMAIN_HANDOFF.md and reread Layer 1 §§3/4/4.3/10, Layer 0 §4.1, Layer 5
§6.0 facet codec and CA4-96 review/registry closure. All agreed numeric rules are
incorporated: inclusive safe-int domain, finite binary64/subnormals, bool distinct,
no implicit conversions or Decimal/Fraction/complex, generic canonical equalities,
stricter owning contracts preserved, value hard failure versus evidence soft failure.
PersistedProjection and facet codec reference the same owner; Layer-2 configuration
keeps its own contracts. No discrepancy found in this scoped comparison.
Ran check_v3_specs.py --issue CA4-96 and --open: 8 layers, 128 contracts, 96 issues,
0 open, 72 reviews. git diff --check passed. Structural/scenario review only, no
behavioral implementation/test or benchmark. Updated own handoff/context/resume and
policy status; no planning edit or commit. This supersedes earlier numeric-pending
checkpoints. rfc8785 library/version and frozen payload implementation remain to agree.

## Concrete codec / freeze — approved on 2026-10-14

User asked to proceed to library/frozen payload selection. No application implementation
started. Planning is now clean `9cd077e` (CA4-97): Layer 2 §2.4 explicitly applies the
Layer-1 domain to formula-result payloads, preserving configuration-specific limits.
CA4-97 leaves the agreed numeric domain unchanged.

Propose rfc8785==0.1.4, isolated behind canonical_json_bytes; private copied dicts
with MappingProxyType, list-to-tuple deep freezing, qualifying dataclass type retained
with frozen fields, explicit JSON projection for the serializer. Never pass raw HA
objects or arbitrary mappings/tuples directly into the third-party codec and treat
its wider acceptance as the input contract. Fact equality/hash must use canonical
content, not auto-generated Python collection comparisons/hash. Stable digests remain
separate from local Python hash. No codec framework or CBOR implementation now.

Fetched official PyPI 0.1.4 metadata and universal pure-Python wheel to /private/tmp.
Requires Python >=3.8, no runtime dependencies. SHA256 verified:
520d690b448ecf0703691c76e1a34a24ddcd4fc5bc41d589cb7c58ec651bcd48.
Loaded wheel via sys.path using project native Python 3.14.5 -B, without installing
it into .venv-v3 or changing requirements. 13 targeted checks passed: safe-integer
extremes/rejection of next integers, finite minimum subnormal, signed-zero canonical
form, 1.0 form, bool distinction, UTF-16 object-key order and tuple-array encoding,
NaN/infinities rejected. Separate check confirmed MappingProxyType unsupported by
raw library; explicit projection is needed. This is a library compatibility probe,
not full conformance/Heima behavioral testing or a performance benchmark.

Proposed first slice is now the shared payload validation/freezing/canonical codec
(Layer 1 §3, L1-NUMERIC-DOMAIN / L1-DEEP-IMMUTABILITY, plus §4 projection shapes),
before full HouseFact assembly. This revises the earlier EvidenceInstant-first
proposal; user has now approved this implementation scope and rfc8785 0.1.4, requested the
preceding instruction changes be committed, then this first slice implemented.
Candidate files canonical_json.py/payloads.py and focused tests/evidence; exact API
remains to agree. Apply all five behavioral testing methods to changed own code,
and standard JCS vectors to verify the dependency boundary.
Only WORKING_CONTEXT updated; existing pending handoff edits preserved. No code,
installation, spec edit or commit. Patch hygiene checked.

## First behavioral slice completed — 2026-10-14

- The user approved rfc8785 0.1.4, private mapping/tuple deep freezing and the
  shared payload/codec slice. Prior instruction/handoff changes committed first
  as `7ca1700`, as requested. Current slice changes remain uncommitted. Final checks reran successfully in the
  actual implementation worktree (not only the temporary development copy), including
  109 cases, lint/format/types/pip consistency and six supplementary mutants.
- Added canonical_json.py and payloads.py: shared JCS projection, bounded value
  validation/freezing, mapping-only projections, evidence soft failure with typed
  diagnostics, canonical-content equality/hash. No raw HA object retention.
- Added separate hashed runtime lock, focused tests, mutmut-only pyproject.toml,
  six targeted module/decorator mutations and permanent five-method evidence.
  Kept tool lock/versions unchanged. Updated README/test-environment/readiness/resume.
- Tests: 109 passed with seed 3145; all 134 statements and 52 branches reported
  covered. Explicit decision table/BVA/MC/DC/property evidence in
  testing/PAYLOAD_CONTRACT.md. Ruff lint/format and mypy pass. Runtime hashed wheel
  installed in .venv-v3; pip check/patch hygiene verified.
- Mutation source scope: both modules; 265 generated, 231 killed, 34 survived and
  reviewed as equivalent for the runtime contract, no timeout/error/untested.
  Complete survivor diffs/rationales in testing/PAYLOAD_MUTANT_REVIEW.md. Additional
  six module/decorator mutants killed by named tests. Fresh run after adding missing
  validator/hash/context cases avoided cached mutation results. No raw 100% score claimed.
- No full HouseFact construction or actual diagnostic emission exists yet; returned
  diagnostic descriptors will be consumed by the future builder/runtime. No JSON
  text decoder: duplicate-key rejection belongs at the future decoding boundary.
  No performance/HA/live/storage/crash verification or deployment.
- Planning checked at `9cd077e` (clean): CA4-97 aligns formula payloads with the same
  numeric domain; no changed Layer-1 behavior or spec edits in this implementation.

## Layer-0 temporal foundation — 2026-10-14

The user authorized continuing Layer-0 implementation. Scoped this next block to
fully specified immutable timing definitions (Layer 0 §§3.1/3.2/3.4/3.4.1), with
Layer 1 §4 EvidenceInstant as a required dependency; planning `9cd077e` is clean.
Implemented instants.py (strict parsing/validation, explicit producer normalization)
and timing.py (Window, AtJob, WeeklyRecurrence, IntervalRecurrence, CronEntry,
CalendarWindow). Weekly matches uses an explicit ZoneInfo and classifies both
physical DST-fold occurrences; CalendarWindow uses half-open containment.
No ambient wall clock is read by these modules; objects store canonical strings.
Shared duration normalization excludes bool/zero/negative/nonfinite/overflow, and
civil fields validate their exact bounds. Window remains a comparison value.

Tests: 92 new cases, 201 total with existing payload tests, seed 3145. New modules
report 109 statements/36 branches covered. Five-method evidence and limitations in
testing/TIMING_CONTRACT.md; mutmut: 188 total, 110 killed, 78 runtime-contract
equivalent survivors reviewed in testing/TIMING_MUTANT_REVIEW.md; no errors/timeouts.
Seven supplementary module/decorator mutants killed. Regression demonstrated before
fix: Python 3.14 accepts 24:00:00 and normalizes it; added parse round-trip identity
check rejects it. Mutation found implicit host-time-zone use was not distinguished;
added explicit UTC/Tokyo tests, reran fresh mutation stats. Ruff/mypy pass.

This is the temporal contract foundation, not all Layer 0. Monotonic dispatch,
replacement/cancellation, weekly next-due DST execution policy, cycle clock/epochs,
calendar I/O/cache, LearnedWindow (needs Location), WarmupGate consumers, provenance,
persistence/queue/outbox/holds/recovery/health/observers remain unimplemented. No
HA integration, spec edits, new dependency, commit or deployment. Earlier pending
payload implementation changes are preserved, not silently committed.

## Critical code review — 2026-10-14

Reviewed all four implemented contract modules and behavioral tests against planning
9cd077e (clean), chiefly Layer 0 §§3.1/3.2/3.4 and Layer 1 §§3/4. Confirmed and fixed
one missing check: IntervalRecurrence accepted a Window subtype that bypassed
post-init even with invalid seconds. Normal Window construction was already safe;
this was missing independent interval admission required by §3.1. Retained interval
is now constructed via Window/the shared validator; valid seconds normalize to float
and the source object is unchanged. No spec or product-policy change.

Regression demonstrated first: 12 failures/3 passes, including Hypothesis shrinking
to 0.0. Added 15 cases/properties: complete suite 216 passes, seed 3145; timing/instant
coverage 110 statements/36 branches; Ruff/type/format pass. Five-method evidence in
testing/TIMING_CONTRACT.md. Three new targeted behavioral mutations killed; all seven
previous timing supplements still killed (10 total). Earlier full mutmut counts are
historical; no fresh full mutmut run claimed. No other confirmed defect in this
review. Performance, full builder/runtime diagnostics, scheduler, persistence/crash
and HA/live integration remain unverified/unimplemented as previously recorded.

All preceding local implementation changes preserved; review edits also uncommitted.

## Next action

Continue Layer 0 from these verified temporal contracts: monotonic AtJob dispatch
and replace/cancel semantics, with injected timer/clock and scheduler-specific
five-method tests. Read §§3.1/3.5 and dependencies before fixing its API; preserve
elapsed versus wall-clock semantics and DST single-firing policy. Complete required
foundation dependencies alongside runtime slices. Git/deploy proposals remain open.
