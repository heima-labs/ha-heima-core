# V3 implementation working context

> Latest commit 2449ea0 fixes SQLite implicit-rollback atomicity.
> New composable SQLite clock-boundary writes/tests/evidence are uncommitted.
> Read the final checkpoint. Planning HEAD37986ea; Layer8 CA4-103 edits in progress.

> **Current state — 2026-10-15, CA4-101:** CronEntry is interval-only. Use
> next_weekly_occurrence(pattern,now,zone) for civil occurrences, not plan_weekly_job.
> Weekly identity is resolved at the L5 activation; do not build a generic weekly
> lifecycle. The last checkpoint below supersedes historical state/next-action notes.

Update this file at the end of every bounded task and before yielding on an unfinished task.
Keep verified state and distinguish user-approved decisions from proposals. Newer user
instructions override the next action below.

## Verified state — 2026-10-14

- Implementation workspace: `ha-heima-component-v3-implementation`, branch
  `feat/v3-implementation`, branched from planning `0063da4`; the previous instruction commit is `6fe67b8`.
  The current environment/tooling files are included in the developer-requested commit;
  use `git log -1` and status for the latest revision each session.
  Payload/codec, temporal contracts and review fix are committed as `e3e4314`.
  AtJob dispatcher/delayed-callback tests are committed as `be83856`.
  Guarded asyncio adapter/tests are committed as `beaac58`.
  Cycle-clock/classification code and tests are local, not committed.
  No HouseFact assembly, HA runtime adapter, storage or deployment exists here.
  The dedicated native Python/test-tool environment is ready; its probes ran in /private/tmp.
- Authoritative specs: sibling `../ha-heima-component-v3-planning`, branch
  `feat/v3-planning`, CA4-70 progressive recovery committed as `f84d4e7`; latest planning HEAD
  checked for this task is `d58431c` (clean), including CA4-98/99. Its Layer 0–6 specs supersede this checkout's older copies.
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

## AtJob dispatcher — 2026-10-14

User requested commit then continuation. Created signed commit e3e4314 for payload,
temporal contracts, reviewed nested-duration fix, test evidence and handoff. Worktree
was clean after commit. Planning remains 9cd077e (clean), read-only.

Implemented runtime/timing.py: explicit monotonic timer port, register/cancel keyed
by (owner, job_id), once-only handoff, stale-arm suppression, selective wall_clock
re-arm against unchanged due, cancellation of all pending arms. Admission revalidates
AtJob; failed validation or timer scheduling preserves existing registrations.
Timer calls/dispatch must be serialized and callbacks deferred. This small port/API
is an implementation choice respecting §§3.1/3.5, with no new dependency or policy.
Layer 5 retains generation/activation/arm-revision checks after handoff.

Tests: 25 new, 241 total passing, seed 3145; 59 scheduler statements/18 branches
covered. Ruff/type/format/patch checks pass. Five-method evidence in
 testing/ATJOB_DISPATCH.md; no compound Boolean gates in new module, so MC/DC has no
new compound decision. Fresh mutmut: 95 total, 87 killed, 8 survivors (only generic
TypeError prose), all exact diffs reviewed in testing/ATJOB_MUTANT_REVIEW.md.
Updated default mutation scope to include this module and tests/v3.

New dispatcher/tests/docs/config changes remain uncommitted. No concrete timer/HA
adapter, diagnostic emission, clock discontinuity detection/gaps, recurrence next-due,
DST execution, persistence or live verification was implemented. This internal API
raises admission errors for the future runtime boundary to diagnose; it does not
claim completion of all §3.1 service requirements. No specs/push/deploy changed.

## Hardware portability steering — 2026-10-14

The user requires AtJob correctness on Raspberry Pi through desktop hardware.
Reviewed dispatcher under this constraint and official HA/Python documentation.
Added four tests/properties for delayed dispatch, overdue invalidation/replacement,
and a reversed-order burst of 1000 equal-deadline jobs. Complete suite 245 passes
(seed 3145); lint/format pass. This is simulated semantic verification, not hardware
performance evidence. Production source unchanged, prior mutation scope still valid;
no additional mutation/benchmark claim. Test/docs changes remain uncommitted alongside
the preceding dispatcher block; e3e4314 remains last implementation commit.

Found a concrete adapter requirement: asyncio call_later/call_at may wake one clock
resolution early. The unimplemented concrete adapter must preserve minimum elapsed
deadlines with a monotonic due check and account for clock resolution without busy
waiting. Representational microseconds do not imply timer precision or latency.
Brief owner handoff/no blocking work follows existing code rules. Do not silently
add hardware-specific rounding, grace periods, lateness discard or queue limits.
See testing/ATJOB_DISPATCH.md for sources and remaining verification.

## Concrete monotonic adapter — 2026-10-14

At user's request, committed dispatcher + hardware-lateness tests as signed be83856;
worktree was clean. Planning remains 9cd077e (clean), read-only. Implemented
adapters/ha/monotonic_timer.py: inject existing asyncio loop, compute monotonic due
once, guard early callbacks, asynchronously re-arm beyond the clock-resolution
horizon, deliver once and release owner references on cancel/delivery. No polling,
worker/task per timer, wall-clock read or new dependency. Exact representable sums
remain unchanged; TwoSum/nextafter preserve minimum waits when float addition rounds
down, verified with an independent Fraction oracle. Standard loop clock metadata
is read once; alternative loops supply matching resolution explicitly.

Tests: 41 new, 286 total pass (seed 3145), including two actual Python asyncio-loop
cases and a scheduler/adapter early-wakeup replacement case. All 64 adapter statements/
18 branches covered; Ruff/type/format/patch checks pass. Five-method evidence in
 testing/MONOTONIC_ADAPTER.md. Fresh mutmut: 117 generated, 92 killed, 25 survivors
(24 generic-error prose, one erased cast annotation); exact diffs reviewed in
 testing/MONOTONIC_ADAPTER_MUTANT_REVIEW.md. Default scope includes all six modules.

Adapter/tests/docs/config changes remain uncommitted. This is actual stdlib asyncio
evidence on local native Python, not HA lifecycle integration or an ARM workload
benchmark. No latency/CPU/memory guarantee, lateness policy, capacity threshold or
supported hardware matrix was chosen. Diagnostic emission, cycle clock/gaps,
recurrence next-due/DST, HA bootstrap/unload wiring and storage remain pending.
No specs, push or deployment changed.

## Cycle clock/classification — 2026-10-14

User requested commit and next step. Signed beaac58 commits the guarded asyncio
adapter/tests; worktree was clean. Planning remains 9cd077e (clean), read-only.
Implemented runtime/clock.py with explicit canonical wall/int monotonic-nanosecond
inputs: strict cycle progression, shared cycle/periodic comparison baseline,
exact >1 s classification and bootstrap durable-floor/downtime separation. Invalid
readings/overflow preserve state. No ambient clock/I/O, dependency or tolerance added.
Outcomes describe re-arm requirement and floor comparison; they do not emit runtime
diagnostics or certify observation continuity.

Tests: 33 new, 319 total pass with seed 3145; 68 statements/18 branches covered.
Ruff/type/format/patch pass. Five-method evidence in testing/CYCLE_CLOCK.md; no new
compound Boolean decision, single-predicate gates tested. Fresh second mutmut run:
125 total, 112 killed, 13 contract-equivalent survivors reviewed in
 testing/CYCLE_CLOCK_MUTANT_REVIEW.md. First run found two missing result assertions;
added them and reran without cache. Three supplementary constant/decorator mutations
killed. Default mutation scope now includes all seven implemented modules.

Found an unresolved §3.5 backward-gap case: between checks 60 s apart, -2 s clock
correction advances wall by 58 s. Detector must classify backward, but no cycle
freezes and the specified gap-start condition never occurs. Prepared exact note in
clarifications/CLOCK_GAP_BOUNDARIES.md for user/Claude review. The user explicitly approved preparing the note for Claude;
it is ready to hand off. No message sent, issue opened
or spec edited. Gap bounds/diagnostic policy were deliberately not chosen in code.

New code/tests/evidence/config/handoff are uncommitted. Real paired-clock reads,
engine barrier/ingress time normalization, periodic service, diagnostic emission,
scheduler re-arm integration and durable gap/floor paths remain pending. Pure
classifier accepts the clarified independent facts, including slow-loop pause without
clock drift. No HA/ARM benchmark, push or deploy.

## CA4-98 synchronization and implementation — 2026-10-14

User supplied planning handoff dd89383. Verified actual clean HEAD, normative Layer
0 §§3.5/10/13, review and registry. The backward-gap clarification is resolved; updated
clarifications/CLOCK_GAP_BOUNDARIES.md with the definitive mapping, retaining original
counterexample as history. Planning was not edited.

Updated runtime/clock.py: floor position means previous cycle+1us (fixed equality
regression); comparison returns detection point, exact bootstrap offset, regression/
re-arm requirements and immutable ClockGap boundary intent. Adjacent-cycle bounds
cover non-frozen detection. Periodic output opens with end pending and updates the
shared baseline; finish(tick) computes a later end, waiting under the frozen-floor
rule. Caller retains and consumes independent intents. No merging, durable schema,
acknowledgement or emission mechanism invented; closed intent is not a durable gap.

336 tests pass with seed 3145 (17 new); lint/format/mypy/patch pass. Five-method
mapping in testing/CYCLE_CLOCK.md. Floor equality regression demonstrated failing
before fix. Fresh mutmut: 198 total, 185 killed, 13 reviewed equivalent survivors in
 testing/CYCLE_CLOCK_CA498_MUTANT_REVIEW.md. Strengthened periodic-floor metadata
assertions after first run exposed three behavioral survivors, reran fresh. Four
supplementary threshold/frozen-decorator mutants killed.

All clock implementation and synchronization changes remain uncommitted; latest
commit remains beaac58. Actual HA clock/periodic service, coordinator diagnostics,
immediate scheduler re-arm orchestration, durable gap acknowledgements and historical
read completeness remain unimplemented. No HA/ARM benchmark, push or deploy.

## Critical clock review — 2026-10-14

Reviewed clock boundary/classification code and its scheduler/asyncio consumers
against clean planning dd89383. Confirmed/fixed one code error: a forward correction
while still below the floor wrongly opened a frozen backward-style gap. next_cycle
now requires backward AND behind to use frozen bounds; forward bounds are always
adjacent detecting-cycle instants. Older backward gaps remain independently open.
Regression + property demonstrated two failures before fix. 338 total tests pass;
Ruff/type/format/patch pass. Five-method evidence appended to CYCLE_CLOCK.md.
Fresh mutmut: 202 generated, 189 killed, 13 same reviewed equivalent survivors;
four supplementary mutations still killed. No other confirmed implementation defect
found in this scoped review. All clock/review changes remain uncommitted.

Found a concrete unresolved spec contradiction: §3.1 requires due-current_cycle
for wall_clock arm/re-arm, but §3.5 keeps that instant ahead of corrected wall during
freeze. Reproducer with real helper APIs and fake timer: wall=100, due=110; at mono=1
wall=98, cycle=100.000001; cycle-based re-arm waits 9.999999 s vs 12 s to actual due.
Prepared exact Claude prompt in clarifications/CLOCK_SCHEDULING_REFERENCE.md. This
blocks the combined clock/scheduler reference choice; did not change either spec or
scheduler silently. CA4-98's resolved gap rule remains valid. No message sent to Claude.
No HA/ARM/live/persistence test or deployment was claimed.

## CA4-99 execution references applied — 2026-10-14

User supplied handoff d58431c. Verified clean planning HEAD and normative §§3.1/3.5/13,
review/registry. The execution-reference contradiction is resolved; updated
clarifications/CLOCK_SCHEDULING_REFERENCE.md, retaining original prompt as history.
No planning edits or new policy/dependency/tolerance.

Added immutable validated ExecutionClockReading(wall,cycle_instant) in runtime/clock.py.
CycleClock.read_execution applies the floor without consuming a cycle/comparison;
cycle and periodic outcomes expose the pair from their captured wall reading.
AtJobScheduler.register/rearm_wall_clock now require the pair, choosing wall for
wall_clock and cycle_instant for elapsed. Single-instant API intentionally rejected;
all repository consumers (tests only) migrated. No public HA or durable schema exists
for this internal API. Fresh/current reading belongs to the future runtime boundary.
Calendar exhaustion fails before consuming a sample when no successor is representable.

Regression demonstrated first on prior API: 9.999999s versus required 12s. After the
paired-API migration, cycle/periodic/bootstrap cases wait 12s, deliver at wall110 once,
keep due/id unchanged; elapsed hold remains 30s. A firing-cycle test keeps its floored
when distinct from due. 355 tests pass (17 new), seed3145; lint/format/mypy/patch pass.
Five-method evidence in testing/CA499_EXECUTION_REFERENCES.md. Fresh mutmut on both
changed modules: 330 generated, 301 killed, 29 equivalent survivors (28 prose, one
unread sentinel), exact diffs in CA499_MUTANT_REVIEW.md. Five supplement mutants killed.
Default broader mutation scope remains seven modules.

All clock/CA4-98/review/CA4-99 changes remain uncommitted; last commit beaac58.
No actual HA clock-reader/periodic service, automatic diagnostic/re-arm lifecycle
wiring, durable gap acknowledgement, recurring next-due/DST or ARM benchmark exists.
Pure component integration and prior stdlib loop tests are not HA/live evidence.

## Next action

Continue internal recurrence next-due/DST calculation in Layer 0 §3.1, using the
paired execution reference per pattern/basis. Read current contract/dependencies
before coding. Clock execution-reference and CA4-98 gap-boundary ambiguities are
resolved. Future coordinator/HA/persistence wiring must consume current snapshots,
respect re-arm requirements and keep durable acknowledgement separate from gap intent.
Git/deploy policy proposals remain pending review.


## Latest checkpoint — weekly calculator, 2026-10-14

Committed the previously verified clock/CA4-98/review/CA4-99 changes as signed
commit 551caa7 (feat: add V3 cycle clock and basis-specific execution references).
This supersedes the preceding uncommitted-state notes; clean before this slice.
Planning rechecked clean at d58431c, read-only, including §§3.1/3.2 and Layer 1 §4.

Added runtime/recurrence.py::plan_weekly_job: pure weekly next-future-due calculation
using injected ZoneInfo and raw wall, preserving AtJob identity and wall_clock basis.
First fold only; missing local minutes map to first valid instant, with bounded binary
search rather than scanning seconds. Tests cover Rome spring/fall, 167/169-hour weeks,
Lord Howe half-hour gap, Apia skipped day, configured-vs-host civil dates, exact due
boundaries, invalid shapes, calendar exhaustion, and generated matching/future/floor
independence properties. Host timezone varied and restored in weekly tests.

407 total tests pass, 52 weekly cases including PBT, seed3145. Ruff check/format,
mypy and diff checks pass. Five-method evidence in testing/WEEKLY_RECURRENCE.md;
fresh mutmut 129 generated: 91 killed, 5 nontermination timeouts, 33 reviewed
equivalent survivors, exact diffs in WEEKLY_MUTANT_REVIEW.md. Default scope now
eight modules. No new test threshold or development/Git/deploy policy.

Developer authorized preparing the Claude prompt for the interval precision gap:
clarifications/INTERVAL_PRECISION.md. Valid Window(0.0000001) is lost by microsecond
deadline arithmetic; 1.5 µs is also inexact. Normative rejection/rounding/minimum and
numeric interpretation remain unresolved. No interval-next-due implementation or
shared-validator change. Do not silently choose a policy. No message sent to Claude.

This weekly slice and its docs remain uncommitted. It is a calculator, not the full
CronEntry service: automatic recurring re-arm, served-occurrence replay protection,
timezone-change coordination, HA wiring, durable configuration/gaps remain future
work. No HA/live/ARM benchmark or deployment claimed.

### Exact next action

Obtain Claude's normative interval representability handoff before implementing
interval due generation. Then build the bounded CronEntry lifecycle using the existing
paired clock API and monotonic dispatcher; explicitly protect weekly occurrence
identity during clock/timezone changes. Re-read current planning contracts first.
Git/deploy proposals still await review.


## Latest checkpoint — CA4-100 applied, 2026-10-14

Verified clean read-only planning HEAD 34ce913, normative owning/dependent sections
and registry/review. It resolves INTERVAL_PRECISION.md; note updated while retaining
historical prompt. contracts/deadlines.py adds derive_instant(anchor,Window,
strictly_after=False): canonical decimal, exact integer ratio, inclusive/strict
microsecond selection and overflow preflight. Immutable Unrepresentable carries
inputs for diagnostics. Window unchanged. runtime/recurrence.py adds plan_interval_job
(cycle_instant/elapsed) and register_interval_job for one guarded admission;
overflow returns diagnostic input without changing timers. Caller must publish it.
Weekly calculation unchanged; no existing float-seconds timedelta producer to migrate.

445 V3 tests pass, 38 new, seed3145; lint/format/mypy/diff pass. Five-method evidence
in testing/CA4100_DEADLINES.md. Fresh mutation: 239 generated, 180 killed, 5 unchanged
weekly timeouts, 54 equivalents (21 new prose/ASCII aliases, 33 reviewed weekly),
exact diffs in CA4100_MUTANT_REVIEW.md. Supplement frozen diagnostic mutant killed.
Default scope nine modules. No new dependency/policy. Weekly and CA4-100 changes
remain uncommitted; last signed commit 551caa7.

Full CronEntry automatic lifecycle, served-occurrence protection, HA timezone wiring,
diagnostic publication, CalendarViewRequirement staging and persistence remain
unimplemented. Their acceptance gates have not run; no HA/live/ARM/deploy claim.
Future owner deadlines/horizons must use derive_instant; L2 strict and L5 whole-ms
rules remain valid.

### Exact next action

Proceed to bounded CronEntry lifecycle above existing single-arm planners and
AtJobScheduler: recurring re-arm, callback failure isolation and served-weekly
occurrence protection during clock/timezone changes. Re-read current Layer 0
§3.1/§3.5/§9/§13 first and surface any missing policy. Static calendar horizon
staging and diagnostic publication belong to future coordinators/adapters.
Git/deploy proposals remain pending review.


## Latest checkpoint — standing interval lifecycle, 2026-10-14

Committed all verified weekly and CA4-100 changes at user request: signed b2bff62,
feat: add V3 recurrence planning and exact deadline construction. Clean before this
slice. Earlier uncommitted notes are superseded. Planning rechecked clean 34ce913,
read-only; Layer 0 §3.1/§3.5/§9/§10/§13 apply.

Added runtime/interval_recurrences.py::IntervalRecurrences for standing interval
rules. It uses the existing planners and shared monotonic dispatcher, explicit fresh
clock capture and non-raising diagnostic sink. Callback failures are diagnosed and
finally re-arm the current rule; reentrant cancel/stop/replacement cannot resurrect
an older rule. Replacement admission failure preserves accepted state. Overflow
is reported before changing timers. Re-arm infrastructure failure/overflow retains
the standing definition with no pending timer and an explicit diagnostic; no retry
policy invented. Stop cancels only owned registrations; restart from supplied rules
arms fresh from now, without recovering countdowns.

469 tests pass, 24 new, seed3145; Ruff lint/format, mypy and diff pass. Five-method
matrix in testing/INTERVAL_LIFECYCLE.md. Fresh mutmut: 119 generated, 107 killed,
12 generic-prose equivalents, no timeout/error/skipped; exact diffs in
INTERVAL_LIFECYCLE_MUTANT_REVIEW.md. Three public diagnostic frozen-record mutants
killed by mutation_interval_recurrences.py with a passing baseline. Default scope
now ten modules. No new dependency, policy or timing threshold.

New lifecycle slice remains uncommitted; last signed commit b2bff62. Not yet a full
CronEntry service: weekly served-occurrence protection and timezone updates are
pending. Persistence of standing rules and automatic HA restart restoration,
HA diagnostic logging/publication, one-shot callback fault-boundary integration,
calendar staging and clock coordinator remain future work. No live HA/ARM/deploy
claim. Diagnostic sink must log/publish promptly without raising; this service does
not silently swallow infrastructure sink failures.

### Exact next action

Review the interval lifecycle before committing its slice, then implement weekly
lifecycle and served-occurrence identity/timezone re-arm against current Layer 0
§3.1/§3.5/§9/§13. Keep basis-specific references and CA4-100 deadline rule. Clarify
any missing occurrence policy through the existing Claude workflow rather than
choosing silently. Git/deploy proposals remain pending developer review.


## Latest checkpoint — shared callback boundary / weekly clarification, 2026-10-14

Committed verified interval lifecycle at user request as signed f92639a,
feat: add V3 standing interval recurrence lifecycle. Clean before this slice;
earlier uncommitted-state notes superseded. Planning checked clean/read-only at
34ce913, Layer 0 §3.1/§3.5/§9/§10/§13.

Found missing weekly occurrence identity rules for timezone changes and replacement.
Example: Monday 07:00 Rome served at 05:00 UTC; switch to UTC at 05:01 makes that
Monday 07:00 future again. Spec says no replay without defining identity/memory.
Requested civil date also differs from delivered date for skipped-day gaps; a backward
clock correction can revisit a served request. User authorized the Claude prompt:
clarifications/WEEKLY_OCCURRENCE_IDENTITY.md. No planning edit/message sent, no new
identity/reset/retention policy chosen. Full weekly lifecycle remains dependent.

Completed independent shared callback isolation: runtime/job_callbacks.py with
JobCallbackFault, invoke_job_callback and isolate_job_callback. Intervals reuse it
within existing finally re-arm; existing interval-module import remains valid.
One-shot wrapper integration proves a failed job is consumed once and other owners
continue. Diagnostic infrastructure errors and BaseException control signals propagate.
Actual coordinator must use the wrapper; low-level dispatcher behavior unchanged.
Updated supplementary lifecycle mutation runner for diagnostic-class relocation.

479 V3 tests pass, 10 new, seed3145; lint/format/mypy/diff pass. Five-method evidence
in testing/JOB_CALLBACK_BOUNDARY.md. Fresh mutmut on both changed modules: 144 generated,
124 killed, 20 generic-prose equivalents, no timeout/error/skipped; exact diffs in
JOB_CALLBACK_MUTANT_REVIEW.md. Three frozen public-record supplement mutants killed.
Default scope eleven modules. No new dependency/policy, live HA/ARM/deploy claim.
This new callback slice and clarification remain uncommitted; last signed commit f92639a.

### Exact next action

Obtain Claude's normative handoff defining weekly occurrence identity, consumption,
replacement scope, clock/timezone behavior and bounded transient memory before
implementing that dependent lifecycle. Keep existing first-fold/gap calculator,
CA4-98/99 basis rules and CA4-100 duration construction. Future HA diagnostic wiring,
calendar staging and durable configuration remain unimplemented. Git/deploy proposals
still await developer review.


## Latest checkpoint — CA4-101 applied, 2026-10-15

Verified clean read-only planning HEAD 0b82d61, normative L0 §3.1/restart/§13,
L5 §7.2/§7.2.1 and CA4-101 registry/review. Weekly CronEntry is OUT of Initial V3,
not a blocked feature. Clarification WEEKLY_OCCURRENCE_IDENTITY.md marked resolved.

contracts/timing.py now types/validates CronEntry.pattern as IntervalRecurrence only;
RecurrencePattern removed. Runtime interval gates reject reconstructed legacy weekly
entries. Existing interval lifecycle and shared callback isolation unchanged.
Removed internal plan_weekly_job (only test consumers); replaced with pure
next_weekly_occurrence(pattern,canonical_now,ZoneInfo) -> frozen WeeklyOccurrence
(requested_date: civil date, start: EvidenceInstant). No job metadata or paired-clock
parameter; consumers use the raw wall reference and build wall_clock AtJob boundaries.
Requested civil date survives missing-time resolution, including Apia's skipped day;
merged physical starts retain distinct requested dates for L5 to consume. No native
datetime instant crosses the output boundary; civil date is an in-process value.

486 V3 tests pass, seed3145; Ruff lint/format, mypy and diff pass. New rejection
regression failed on prior code as expected. Evidence in CA4101_OCCURRENCES.md.
Fresh mutmut timing+recurrence: 305 generated, 210 killed, 5 known search timeouts,
90 equivalents (80 generic prose, 1 cast, 9 search variants), exact diffs in
CA4101_MUTANT_REVIEW.md. Supplements: 10 timing mutants and 2 weekly occurrence
mutants killed, clean baselines. Default scope stays eleven modules, no dependency
or policy change. Newer two merged-date test instances added after mutation/source
freeze. No live HA/ARM/deploy claim.

CA4-101 and prior shared-callback changes remain uncommitted; last signed f92639a.
No L5 activation/session implementation exists: served-date RAM, equal-start merge,
late session remaining-time admission, timezone re-arm and restart activation rules
are now specified and must be implemented THERE. No generic weekly lifecycle next.

### Exact next action

Review/commit shared callback and CA4-101 slices when requested; continue Layer 0
integration with actual clock/coordinator/HA diagnostic ports and periodic interval
wiring, or the next agreed bounded foundation contract. Calendar staging, persistence
of standing configuration and durable gaps remain future work. Do not schedule a
weekly CronEntry or implement a Timing-level served-date ledger. L5 session fixtures
belong to the future presence-simulation activation. Git/deploy proposals still pending.


## Latest checkpoint — timing clock bridge, 2026-10-15

Committed shared callback and CA4-101 changes at user request as signed f182a37,
feat: align V3 recurrence contracts and share callback fault isolation. Clean before
this slice. Planning clean/read-only at 0b82d61, Layer 0 §3.1/§3.5/§4.4/§13 and
fault/diagnostic sections checked. Interval-only CronEntry scope is unchanged.

Added adapters/ha/clock_source.py SystemClockSource for sequential raw UTC/monotonic
host capture; runtime/timing_clock.py TimingClock uses explicit source, CycleClock,
scheduler, observation and re-arm-fault ports. Each comparison samples once and
re-arms civil jobs from its exact raw wall; execution reads change no baseline.
Observer receives classification/gap intents before scheduler effects. Tests compose
the periodic entry point with an ordinary 60-second IntervalRecurrence, outside a
cycle, without duplicate jump detection. Actual continuity writer is not created.

Found/fixed an actual scheduler safety defect: failed re-arm used to retain a stale
pre-correction timer that could execute before corrected wall due. Reproducer failed
before fix. rearm_wall_clock now returns per-job immutable failures, cancels failed
old arms, continues other civil jobs, and leaves elapsed untouched; bridge reports
each failure with comparison/job context. Normal registration failure still preserves
its valid old arm. No retry/fallback policy invented. All runtime callers inspected.

502 V3 tests pass, 16 new, seed3145; Ruff lint/format, mypy/diff pass. Evidence in
TIMING_CLOCK_BRIDGE.md. Fresh mutmut on three affected modules: 168 generated,
156 killed, 12 equivalent generic-error-prose survivors, no timeout/error/skipped;
exact diffs in TIMING_CLOCK_MUTANT_REVIEW.md. Three frozen-result supplement mutants
killed by mutation_timing_clock.py, clean baseline. Default scope thirteen modules.
No new dependency, timing threshold or policy; no HA/live/ARM/deploy claim.

New bridge/fix remains uncommitted; last signed f182a37. Observe/report ports require
prompt non-raising in-memory effects/logging/queuing, not waiting for storage. Their
actual runtime/HA implementations, durable gap state/acknowledgement, continuity
watermark worker, standing configuration persistence and calendar staging remain
future work. Sequential host capture is not an atomic clock pair. A gap completion
intent never certifies durable acknowledgement.

### Exact next action

Review/commit this bridge slice when requested. Continue with concrete Layer-0
continuity metadata ownership and persistence contract before wiring real durable
gap/periodic watermark effects; alternatively the next agreed foundation contract.
Actual HA bootstrap/shutdown and fault publication need their own bounded integration
slice. Preserve shared 60-second CronEntry ownership, CA4-98/99 references and CA4-101
interval-only scope. Git/deploy proposals remain pending developer review.


## Latest checkpoint — observation coverage foundation, 2026-10-15

Committed verified clock/scheduler bridge and safe failure handling at user request
as signed 6a60bd5, feat: connect V3 clock observations to safe scheduler rearming.
Clean before this slice. Planning clean/read-only 0b82d61, L0 §4.4 continuity value,
required-stream composition and dependency registry checked. Older bridge-uncommitted
notes are superseded.

Added contracts/observation.py with closed ObservationCoverageStatus/ObservationGapReason,
validated frozen ObservationCoverage, and combine_observation_coverage(process,
required_streams=()). Complete/incomplete field invariants, exact closed reason shape,
ASCII order/distinctness and canonical missing instant validated. Composition unions
reasons and keeps earliest missing instant, revalidating reconstructed inputs.
Process result is mandatory even for zero required streams; known gaps cannot be
healed by complete streams. No clipping, endpoint or retention policy is invented.

541 V3 tests pass, 39 new, seed3145; Ruff lint/format, mypy and diff pass. Five-method
evidence in OBSERVATION_COVERAGE.md. Fresh mutmut: 115 generated, 67 killed, 48 generic
error-prose equivalents, no timeout/error/skipped; exact diffs in
OBSERVATION_MUTANT_REVIEW.md. Three supplemental observation mutations killed with
clean baseline (frozen result, dropped declared reason, accepted unknown reason).
A rejected collection-error probe was not counted as a behavioral kill. Default
scope fourteen modules. No new dependency, policy or SQLite schema; no live/HA/ARM/
durable gap acknowledgement/deploy claim.

New coverage slice remains uncommitted; last signed 6a60bd5. Its inputs must already
cover the same request and be clipped to it, with only required streams selected.
This algebra does not certify trusted metadata, store gaps, select interval endpoints,
resolve latest state availability, evaluate retention or acknowledge writes. Those
belong to the future timeline/read implementation. HistoricalReadResult and HouseFact
assembly remain unimplemented.

### Exact next action

Review/commit this value/composition slice when requested. Continue the bounded
Layer-0 observation timeline/read path: derive request-clipped process/stream coverage
from specified gap and durability state before connecting SQLite writer/acknowledgement.
Read current §4.1/§4.4/§4.6 and dependencies; surface ambiguous endpoint cases instead
of choosing silently. HA lifecycle/diagnostics, watermark writer and standing config
persistence remain future work. Preserve interval-only CronEntry and current clock
rules. Git/deploy proposals remain pending developer review.


## Latest checkpoint — historical intervals and critical review, 2026-10-15

Committed observation coverage at user request as signed 0cc0929, feat: add V3
observation coverage contracts and conservative composition. Clean before this slice.
Planning checked clean/read-only 0b82d61, L0 §4.4/§13 and timing §3.1/§3.5.

Added contracts/history_intervals.py: explicit bounded canonical endpoints and inclusion
flags; point/empty intervals on microsecond grid; exact intersection or None. Inputs
revalidated, endpoint convention never chosen implicitly. This is geometry for later
request-clipped gap evaluation, not durable-gap/metadata assessment or a complete
historical read. No open-gap closure or write acknowledgement is inferred.

Then performed requested critical review of 0cc0929,6a60bd5,f182a37,f92639a and timing
consumers/dependencies. Two confirmed defects fixed after 8 regression instances
failed: (1) timedelta.total_seconds float transport could shorten canonical duration;
new shared _countdown uses integer µs + least non-early float, no due/Window change;
(2) past year-1 local candidate could overflow UTC and hide a valid next-week start;
civil past-candidate prefilter avoids conversion and retains physical UTC fold check.
Updated four old tests to exact Fraction transport bounds rather than binary nominal
float equality; no approximate tolerance. Full report CRITICAL_REVIEW_20261015.md.

Third reproduced case needs spec decision: forward correction while old backward
floor holds has different new-gap completion for cycle vs periodic detection.
Developer approved prompt clarifications/PERIODIC_FORWARD_GAP_DURING_FREEZE.md.
ClockGap/CycleClock unchanged pending handoff; no hidden xfail or product policy.

587 V3 tests pass, seed3145; lint/format/mypy/diff pass. Five-method evidence in
HISTORY_INTERVALS_AND_REVIEW.md. Fresh mutmut on three affected modules: 364 generated,
291 killed, 5 known civil-search timeouts, 68 reviewed equivalents, exact diffs in
HISTORY_INTERVAL_REVIEW_MUTANTS.md. Supplements: 5 interval (including property logic
excluded by mutmut) and 2 weekly occurrence mutants killed, clean baselines. Default
scope fifteen modules. No new dependency/policy/live HA/ARM/SQLite/deployment claim.

New interval geometry/review fixes/prompt remain uncommitted; last signed 0cc0929.
HA lifecycle/diagnostic ports, SQLite writer, durable metadata/acknowledgement and
full history assessment remain future work. Review is scoped local evidence, not
proof of full engine integration or performance.

### Exact next action

Deliver approved prompt to Claude via developer; obtain normative forward-periodic-
under-freeze rule before changing that gap path. Review/commit current geometry and
review fixes when requested. Continue request-scoped observation assessment only
from explicit endpoint/trust/durability inputs; do not infer empty history or continuity
from missing metadata. Preserve interval-only CronEntry and no generic weekly lifecycle.
Git/deploy proposals remain pending developer review.


## Latest checkpoint — CA4-102 per-correction clock gap end rule, 2026-10-15

User-approved CA4-102 implemented from the planning working copy on feat/v3-planning,
base 0b82d61 with uncommitted spec/registry/backlog/review changes. Read Layer 0
§3.5 (Corrections while the floor holds and periodic detection), §10, §13, review
CA4-102 and backlog entry. No planning edits; do not describe this as a committed
CA4-102 spec revision. Clarification PERIODIC_FORWARD_GAP_DURING_FREEZE.md is resolved.

CycleClock.compare now selects frozen-floor waiting only for backward AND behind,
matching next_cycle. ClockGap.finish retains the end rule fixed at opening: a
non-frozen-mode gap ends at the first later cycle even when frozen; frozen-mode gaps
wait until wall strictly exceeds that cycle's floor. Later corrections do not change
an earlier gap's mode or boundaries. Boundary intents remain immutable and do not
acknowledge persistence. No changes to threshold, due/basis, re-arm or elapsed waits.
Call-site search found no runtime consumer of the removed promotion outside clock.py;
updated the old test expecting promotion. TimingClock exposes intents without storing
or closing gaps; actual gap ownership/persistence/diagnostic delivery remain pending.

Before the fix: 5 new regression/property instances failed, 40 passed. With the fix:
633 V3 tests pass, seed3145; focused clock suite 101 passed. Decision table, BVA,
MC/DC and generated sequence evidence: testing/CYCLE_CLOCK.md. Fresh scoped clock.py
mutmut: 216 generated, 199 killed, 17 reviewed equivalents; no timeout/error/untested.
Five supplemental threshold/frozen-decorator mutations killed with a clean baseline.
Exact survivor diffs and reproduction: testing/CYCLE_CLOCK_CA4102_MUTANT_REVIEW.md.
Ruff lint/format, mypy and diff hygiene pass. No dependency/schema/policy/deploy change.

Last signed commit remains 0cc0929. CA4-102 changes AND preceding interval geometry/
critical-review work remain uncommitted; user explicitly requested no commit here.
See Git status for the complete existing dirty set; preserve the earlier work.

### Exact next action

Review the CA4-102 patch and commit only when requested. Resume the bounded Layer-0
request-scoped observation assessment using explicit endpoint/trust/durability inputs,
reading current §4.1/§4.4/§4.6 and dependencies first. The periodic-forward gap question
is closed by CA4-102; do not seek another product decision for it. SQLite writer,
durable acknowledgement, runtime gap manager and HA lifecycle remain future work.
No generic weekly lifecycle; Git/deploy proposals still await developer review.


## Active slice — request-clipped known observation gaps

Committed the preceding work as signed 6cf839b at developer request; clean after commit.
Implement contracts/observation_gaps.py and behavioral tests using L0 §4.4/§13 and
explicit HistoryInterval geometry. Scope: immutable known gap interval/reason plus exact
request clipping, preserving independent records. This does not select required streams,
certify metadata trust/acknowledgement, assign first_incomplete_at or produce a full
HistoricalReadResult. Planning stays read-only at 0b82d61 plus working-copy CA4-102.


## Latest checkpoint — known observation gap clipping, 2026-10-15

At developer request committed all previously verified work as signed 6cf839b,
feat: add V3 history intervals and correct timing boundary semantics. Included interval
geometry, countdown precision/year-1 weekly review fixes and CA4-102, with evidence and
handoff files. Clean after commit; 633 tests rerun before it.

Continued with contracts/observation_gaps.py: frozen ObservationGap(interval,reason)
and clip_observation_gaps(request,gaps). Reuses HistoryInterval intersection and closed
reason validation; clips bounded known gap evidence to an explicit request. Preserves
order/multiplicity/reasons, rejects malformed/reconstructed inputs even when outside or
empty, and never turns no intersections into a completeness claim. No scope selection,
open-gap extent inference, trust/acknowledgement or first_incomplete_at assignment.
No new persisted record/API schema, dependencies or product policy introduced.

Planning remains read-only at 0b82d61 with uncommitted CA4-102 spec changes. Read owning
§4.4 and §13 plus §4.0/§4.3/§4.6 separation and independent clock-gap rules. Added
58 tests: decisions, boundary/point/empty/calendar extremes, delegated MC/DC endpoint
pairs, frozen/malformed inputs and generated finite-set oracle/idempotence. Full V3
691 passed, seed3145; Ruff lint/format, mypy22 and diff hygiene pass. Fresh scoped
mutmut:52 generated,40 killed,12 generic-message equivalents, no other outcomes;
individual diffs in testing/OBSERVATION_GAP_CLIPPING_MUTANTS.md. Supplemental frozen
record mutation killed after clean baseline. Default scope sixteen modules. Evidence
and reproduction: testing/OBSERVATION_GAP_CLIPPING.md. No HA/ARM/SQLite/deploy claim.

Clipping source/tests/supplement runner, mutation config, README/evidence/handoff changes
remain uncommitted; parent is 6cf839b. Prior CA4-102/geometry/review work is committed.

### Exact next action

Review/commit this clipping slice when requested. Continue request-scoped observation
assessment from explicit metadata-trust, durable boundary and required-stream inputs.
Use clipping as geometry only; an empty clipped tuple cannot certify continuity.
Read current §4.4/§4.6 and endpoint contracts before assigning first_incomplete_at or
building HistoricalReadResult; surface any unresolved case rather than choosing a rule.
SQLite writer/acknowledgements, process/stream timeline ownership, baseline validity,
HA lifecycle and complete historical read assembly remain future work. CA4-102 is
resolved; no generic weekly lifecycle. Git/deploy proposals remain pending review.


## Active slice — observation coverage assessment

Committed clipping as signed d965470 at developer request; clean after commit.
Implement pure coverage assessment from explicit bounded gap evidence and a mandatory
metadata-trust input, reusing clipping and existing ObservationCoverage composition.
Read planning L0 §4.4/§13 and dependency separation; no planning edits.


## Latest checkpoint — observation coverage assessment, 2026-10-15

Committed the previous clipping slice at developer request as signed d965470,
feat: clip known V3 observation gaps to historical requests. Clean after commit;
691 tests rerun before it. No planning edits. Initially read 0b82d61 plus pending
CA4-102; final planning check clean at 37986ea (CA4-102 committed concurrently by
Claude). SHA-256 of spec/registry/backlog/review unchanged from the reviewed inputs.

Extended contracts/observation_gaps.py with assess_observation_coverage(request,gaps,
metadata_trustworthy=...). Required trust is an explicit non-defaulted boolean from
the future timeline owner. Known original extents are request-clipped; reasons are
unioned/sorted, earliest missing canonical instant retained. §4.4's already-open-gap
exception uses request start; otherwise excluded lower bound advances exactly 1us
inside the nonempty intersection. Unknown metadata (flag False or intersecting
unknown reason) uses request start and preserves other known reasons. Original extents
must be passed, not pre-clipped gaps, to preserve the already-open distinction.

A private shared generator retains original gap and intersection for both clipping
and assessment; all inputs are still validated even if trust is already unknown.
One linear pass and a bounded reason set/one first instant; no sorted gap list, I/O
or storage access. Process/required-stream calculations compose through the existing
combine_observation_coverage. No producer availability, scope selection, durable proof
or gap end acknowledgement is inferred; the owner must supply exhaustive evidence.
No HouseFact/history record assembly, SQLite schema or HA contract changes.

54 new assessment instances + 58 unchanged clipping instances pass. Full V3:745 passed,
seed3145; Ruff lint/format51files, mypy22sources, diff hygiene pass. Fresh scoped mutmut
on observation_gaps.py:110 generated,94 killed,16 reviewed TypeError-prose equivalents,
no timeout/error/skipped/untested. Existing frozen-gap supplement killed after clean
58-test baseline. Evidence: testing/OBSERVATION_ASSESSMENT.md; exact surviving diffs:
testing/OBSERVATION_ASSESSMENT_MUTANTS.md. Default scope remains sixteen modules.
No dependencies/policies changed; no HA/ARM/SQLite/live/deploy claim.

Assessment source/test/evidence/README/handoff remain uncommitted; parent d965470.
Earlier clipping/CA4-102/interval/timing review work is committed. Git status is the
complete dirty inventory; no unrelated modifications were found.

### Exact next action

Review/commit this assessment slice when requested. Next connect explicit continuity
boundary/acknowledgement state to the bounded evidence and required trust input; read
current §3.5/§4.4/§4.6 and dependencies before defining pending/open extents. A clock
gap end intent alone cannot certify complete coverage. Keep source unavailability,
process gaps and post-overflow baseline validity separate; never restore an older
available fact over a newer unavailable one. Concrete SQLite writer/transaction
schema, watermark advancement, full HistoricalReadResult and HA lifecycle remain
future work. No generic weekly lifecycle; Git/deploy proposals still await review.


## Active slice — clock-gap durability projection

Committed assessment as signed f628736; clean after commit. Read planning 37986ea
L0 §3.5/§4.4/§4.6. Implement storage/clock_gaps.py and tests: explicit independent
opening/closing durable proof, caller-declared endpoints, conservative request coverage
while a closing intent is unconfirmed. This is a pure per-gap contribution, not a
SQLite writer or an overall process-continuity certificate. No planning edits.


## Latest checkpoint — clock-gap durability projection, 2026-10-15

Committed prior assessment at developer request as signed f628736, feat: assess V3
observation coverage from explicit continuity evidence. Clean after commit;745 tests
rerun before it. Planning checked clean/read-only 37986ea, owning §3.5/§4.4 and ordered
continuity metadata §4.6; no planning edits.

Added storage/clock_gaps.py: frozen ClockGapBoundaryReceipt and ClockGapDurability,
plus clock_gap_observation_coverage(request,durability). Receipts correlate exact
owner-assigned gap id, opening/closing side, canonical instant and inclusion flag.
Bare proof booleans rejected as insufficient against cross-gap/stale-end receipts.
This is an internal calculation interface, not a chosen SQL record or actual receipt
issuer. Future owner ensures unique ids; writer issues receipt only after durable
success. Snapshot validation rejects unmatched/malformed proof, including closing
proof for no closing instant. Out-of-order receipts remain representable.

A missing closing receipt cannot turn a pending end into historical completeness:
project potentially open extent through request end. A known open gap keeps clock
reason; absent opening proof or pending closing proof also adds unknown metadata,
using existing conservative assessment. Exact closing proof allows only this gap's
restriction to end at its declared boundary. Caller must still combine mandatory
process coverage and every other relevant gap/required stream; unrelated unknown
process metadata cannot be healed. Endpoint policy stays explicit, no state fallback.
Revalidation precedes early empty/before-gap returns. Fixed work per gap, two receipt
slots; no I/O, runtime queue, live state mutation or SQLite schema introduced.

56 new focused instances (including actual CycleClock CA4-102 independent-gap sequence)
and full V3:801 passed,seed3145. Ruff lint/format54files,mypy23sources,diff pass. Fresh
mutmut scope clock_gaps.py:205 generated,165 killed,40 reviewed generic error-prose
equivalents; no timeout/error/skipped/untested. Initial behavioral survivor prompted
malformed/reversed pending-end tests and a fresh uncached rerun. Both frozen-decorator
supplements killed after clean 56-test baseline. Default scope seventeen modules.
Evidence: testing/CLOCK_GAP_DURABILITY.md and CLOCK_GAP_DURABILITY_MUTANTS.md. No new
dependency/policy/HA/ARM/SQLite/live/deploy claim.

Current durability source/tests/supplement/config/evidence/README/handoff uncommitted;
parent f628736. Prior assessment/clipping/CA4-102 work is committed.

### Exact next action

Review/commit this slice when requested. Continue ordered persistence accounting and
writer integration so actual committed boundary results can issue matching receipts;
read current §4.2/§4.4/§4.6 and atomic cycle marker/barrier rules before implementing
that owner. Track all accepted facts, independent audit items and durable loss
boundaries through the full barrier, not merely a largest received ordinal. Do not
mint receipts on queue admission or callbacks before commit, and do not derive gap
ids from timestamps. SQLite schema/worker, watermark advancement, process/stream
journal ownership, overflow baseline validity and full HistoricalReadResult remain
future work. Git/deploy proposals still await review; no generic weekly lifecycle.


## Active slice — continuity prefix accounting gate

Committed clock-gap durability as signed 956039d; clean after commit. Planning
37986ea read-only; owning L0 §4.4 plus atomic cycle markers §4.1/§4.2 and full
overflow closure boundary §4.6. Implement pure accounting of complete accepted-ticket
ranges: pending writes/loss declarations, holes and producer blockers cannot be
bypassed by a later acknowledgement. No receipt issuance, durable watermark write
or payload queue is introduced. Snapshot assembler/writer remain future work.


## Latest checkpoint — continuity prefix accounting gate, 2026-10-15

Committed previous clock-gap durability at developer request as signed 956039d,
feat: guard V3 clock gap coverage with matched durable receipts. Clean after commit;
801 tests rerun before it. Planning checked clean/read-only 37986ea; read owning
§4.4 and dependency atomic-cycle §4.1/§4.2 and full overflow closure §4.6. No spec edits.

Added storage/continuity_accounting.py: frozen ContinuityAccountingBarrier and
DurabilityRange plus continuity_barrier_accounted. This checks complete contiguous
accounting of all accepted positions after an already-proved prefix through the
chosen target. Outcomes pending/written/loss_pending/loss_declared remain distinct;
only durably declared loss is resolved, not claimed as written payload. A later
acknowledgement cannot heal an earlier missing audit/fact/boundary proof. Unknown
inventory and known producer audit-construction failure at/before the barrier block.

Internal positions belong to one process-local coordinator, not a new AppendOrder
or persisted schema. Future owner must assign all acceptances and derive exact
uniform ranges from matched durable results; never infer a range from sparse min/max
receipts or a prior prefix from the largest receipt/time. Sorted disjoint ranges give
one-pass constant-extra-memory checking without enumerating tickets, sorting or
retaining payloads. Old/future entries are validated but not re-accounted. The gate
does not own ranges, advance/write a watermark or certify whole observation coverage.
Queue/loss inventory and range assembly remain to implement, without a second queue.

66 focused instances, full V3:867 passed,seed3145. Ruff lint/format57files,mypy24sources,
diff pass. PBT found a development bug with a pending range straddling previous=target;
two literal tests failed before excluding its empty clipped intersection. Fresh
mutmut scope continuity_accounting.py:138 generated,97 killed,41 equivalents (40 error
prose,1 redundant equality fast path), no timeout/error/skipped/untested. Initial
continue->break survivor prompted a later-invalid-input test and fresh uncached rerun.
Both frozen declarations removed by supplements were killed after clean 66-test baseline.
Evidence: testing/CONTINUITY_ACCOUNTING.md and CONTINUITY_ACCOUNTING_MUTANTS.md.
Default mutation scope eighteen modules. No dependency/policy/SQLite/HA/ARM/deploy claim.

Accounting source/tests/supplement/config/evidence/README/handoff remain uncommitted;
parent 956039d. Previous durability, observation assessment and clipping are committed.

### Exact next action

Review/commit this accounting gate when requested. Continue the real persistence owner:
assemble ranges from matched committed writer receipts and bounded acceptance/loss
inventory, then write the continuity watermark only after its complete chosen boundary
is accounted. Read current §4.2/§4.4/§4.6 and atomic marker/HA-intake contracts first.
Include independent audits and later same-cycle DAG facts; account an accepted item as
lost only after its loss declaration is durable. Preserve process-local sequence
namespace and receipt correlation across callbacks/restarts. No SQLite schema/worker,
range assembler, actual watermark write, process/stream owner or HistoricalReadResult
assembly exists yet. Git/deploy policies remain proposals; no generic weekly lifecycle.


## Active slice — SQLite transaction boundary

Committed accounting as signed 671f3b4; clean after commit. Planning37986ea read-only.
Implement real SQLite WAL/FULL worker-owned transactions, returning results only after
COMMIT; validate event-loop/thread ownership and fail closed on transaction uncertainty.
No fact schema, retry queue or HA lifecycle is chosen. Explicit busy timeout supplied
by owner; no new retry policy. Test real on-disk atomicity and injected failure stages.


## Latest checkpoint — SQLite transaction boundary, 2026-10-15

Committed accounting at developer request as signed671f3b4, feat: require complete V3
continuity prefix accounting. Clean after commit;867 tests rerun. Planning clean/read-
only37986ea, owning L0 §4.2/§4.4/§4.6 and marker/boundary dependencies checked. No edits.

Added storage/sqlite_transactions.py: SQLiteTransactionWriter(path,busy_timeout_ms=...),
run(operation),close(). Real native connection, verified WAL/FULL/native busy_timeout;
explicit SQL BEGIN IMMEDIATE/COMMIT/ROLLBACK with Python autocommit=True. Results return
only after successful COMMIT. Required integer busy_timeout_ms uses native representable
0..2147483647; no operational default/retry cadence/new Window semantics. Worker thread
ownership and no-running-event-loop guards enforce the I/O boundary. Host must supply
one dedicated worker and the existing bounded queue; no executor/queue is added here.

Failures discard the connection after best-effort explicit rollback; all cleanup errors
are preserved with original BaseException in an appropriate exception group. Commit
error can be uncertain, including durable rows but no returned result: no automatic
retry; future owner must reconcile stable operation identities. Normal close is
idempotent; nested transaction/close rejects. SQLite authorizer denies callback
transaction/savepoint control; a failing COMMIT-then-BEGIN regression first left a
partial fixture batch durable, then passed after guard. Warmed-cache control denial
also tested. Trusted internal callbacks must not disable guard/settings or publish
before run returns/leak connections. No application schema or real receipt issuer yet.

48 new focused instances, full V3:915 passed,seed3145. Actual temporary on-disk reads
prove isolation/atomic facts+fixture marker, real constraint rollback, lock handling,
failure stages and commit uncertainty. Dedicated single-worker executor test keeps
main event-loop callback available. PBT uses fresh databases and varied statement cuts.
Ruff lint/format60files,mypy25sources,diff pass. Fresh scoped mutmut:144 generated,
73 killed,71 reviewed equivalents (55 generic prose,11 SQL case,5 overwritten/private
setup variants); zero error/timeout/skipped/untested/interrupted. Three supplemental
SQL/publication mutations killed with clean48-test baseline. Default scope19modules.
Evidence: testing/SQLITE_TRANSACTIONS.md and SQLITE_TRANSACTIONS_MUTANTS.md, including
primary Python/SQLite API references and precise mutation limits. Runtime Python3.14.5,
SQLite3.53.1. No dependency/policy/live HA/ARM throughput/power-cut/deploy claim.

SQL module/tests/supplement/config/evidence/README/handoff uncommitted; parent671f3b4.
No production database/table was created; only temporary test fixtures. Prior gate,
clock durability, observation assessment/clipping work committed.

### Exact next action

Review/commit this SQLite boundary when requested. Continue concrete domain SQL schema
and operations: matched clock-boundary rows, operation-id reconciliation and verified
accounting ranges, then actual continuity-watermark transaction after full barrier
proof. Record schema/worker lifecycle rationale before costly choices. Re-read current
§4.2/§4.4/§4.6. Never auto-replay an uncertain commit without idempotence/reconciliation,
issue a receipt on queue admission, or use intake-only ordinals for full closure.
No real bounded retry owner, SQL fact/metadata schema, receipt issuer, range assembler,
watermark publication, HA lifecycle or HistoricalReadResult exists yet. SQLite backup
and checkpoint cadence remain future design. Git/deploy policies still proposals.


## Latest checkpoint — critical SQLite/continuity review, 2026-10-15

Developer requested commit then critical review. Reran all915 tests and diff check,
committed the nine SQLite slice files as 9207821, feat: add worker-owned V3
SQLite transaction boundary; clean immediately afterward. Planning37986ea clean,
read-only; re-read registry/workflow and L0 §4.1/§4.2/§4.4/§4.6 boundaries.

One confirmed P1 atomicity defect fixed: SQLite can roll back the whole transaction
without an explicit ROLLBACK statement. A callback catching that error could then
write in autocommit; the final ownership check was too late. Real native regression
first found a durable marker with no facts on baseline9207821, for both cold and
warmed SQL. The callback authorizer now denies preparation after transaction loss;
cached_statements=0 ensures reused SQL cannot bypass that compile-time check.
No new retries/schema/receipts or product policy. Cost: repeated SQL preparations
within a batch; actual Raspberry Pi throughput remains unmeasured. Trusted callback
constraints remain; this does not sandbox Python or connections deliberately leaked.

Decision table distinguishes caught ABORT (transaction remains valid) vs ROLLBACK
(transaction ended), with cold/warmed continuation. MC/DC isolates transaction loss
and explicit transaction control. New PBT varies prefix values, prior durable row,
warm state and execute/executemany/cursor paths. A first mutation run exposed cache
size1 as a real surviving defect seed; added same-SQL/new-key regression, proved it
fails on durable contents with cache1, then restarted mutation from a fresh directory.
Final full V3 suite:921 passed, seed3145; SQLite focused54. Ruff lint/format60files,
mypy25sources and diff check pass. Fresh scoped mutmut153 generated,82killed,
71 individually reviewed equivalents; zero errors/timeouts/skipped/untested/
interrupted. Five supplemental mutations killed with clean54-test baseline.
Evidence: testing/SQLITE_CRITICAL_REVIEW.md and SQLITE_CRITICAL_REVIEW_MUTANTS.md.
Prior mutation reports remain historical. Fix/tests/supplement/review evidence/
handoff and baseline-doc cross-reference are uncommitted on parent9207821.

No other confirmed defect in reviewed clock receipt correlation, continuity-prefix
proof, observation clipping/assessment. None of these pure constructors issues a
real SQLite acknowledgement. Future domain SQL owner must correlate durable receipt
identity and reconcile uncertain COMMIT outcomes; no fake queue-admission success.

### Exact next action

Review/commit this critical-review fix when requested, then continue the domain SQL
schema/operations and stable operation-id reconciliation, matched clock boundaries,
verified range assembly and continuity watermark transaction. Read current planning
first; record concrete schema/worker rationale before costly choices. Full-cycle
closure includes later DAG facts and independent audit items, not intake ordinals.
No schema, bounded queue/retry owner, real receipt issuer, watermark publication or
HA lifecycle exists yet. No deployment, V2 change or planning write was performed.
Git/deploy policies remain proposals.

## Active slice — real SQLite clock boundary writes

Review fix committed2449ea0 after921 tests; clean afterward. Planning37986ea clean,
read-only. Implement composable immutable clock-boundary SQL operations with stable
(gap_id,boundary) reconciliation and post-COMMIT publication via existing writer.
Read L0 §3.5/§4.2/§4.4/§4.6. Rationale and rejected storage choices recorded before
implementation in testing/SQLITE_CLOCK_BOUNDARIES.md. Expected files: new storage
module/tests/evidence/supplement, mutation scope, README and handoff. No generic
ledger, fact schema, watermark, queue worker, retention or HA lifecycle yet.


## Latest checkpoint — SQLite clock-boundary operations, 2026-10-15

Committed the critical-review fix at developer request as2449ea0 after921 tests
and diff check; clean immediately afterward. Planning37986ea unchanged/clean,
read-only; reviewed current L0 §3.5/§4.1/§4.2/§4.4/§4.6 and registry/workflow.

Added storage/sqlite_clock_gaps.py: prepare_clock_gap_schema SQL callback for staging,
ClockGapBoundaryWrite frozen/slots callable for composing inside writer.run with
other end-of-cycle SQL. New version-named STRICT clock_gap_boundaries_v1 table;
(gap_id,boundary) primary key, canonical UTC time and explicit inclusion. Reuse
ClockGapBoundaryReceipt validator at staging and application (including forged data).
Exact immutable replay reconciles an uncertain COMMIT; different time/inclusion
under the same identity rejects, leaving existing data unchanged. No mutable upsert,
ID allocation, automatic retries or generic operation journal. No result may be
published from inside the callback; writer.run must return successfully first.
The future owner must supply globally unique retained gap IDs and valid matched
ClockGap intents. Separate opening/closing rows allow independent/out-of-order proofs.
Rationale/rejected options recorded before coding in testing/SQLITE_CLOCK_BOUNDARIES.md.

39 focused instances, full V3:960 passed,seed3145. Real on-disk isolation and atomic
composition with fixture facts, rollback, immutable replay, explicit replacement-
writer reconciliation after COMMIT errors before/after actual commit, and downstream
coverage from genuine committed closing receipt. Boundary IDs include raw Unicode,
SQL quotes and NUL; no extra normalization/limits. BVA min/max canonical instants,
booleans, matching/1us-different time. Decision table/MC/DC and30-example dictionary
PBT. Ruff lint/format63files,mypy26sources,diff pass. Fresh scoped mutmut45generated,
33killed,12individually inspected generic-prose equivalents, zero errors/timeouts/
skipped/untested/interrupted; five SQL/frozen/slots supplements killed with clean39
baseline. Permanent scope20modules. New evidence SQLITE_CLOCK_BOUNDARIES.md and
SQLITE_CLOCK_BOUNDARIES_MUTANTS.md; prior mutation reports remain historical.

At the final check, planning HEAD was still37986ea but another session had started
uncommitted CA4-103 changes: Layer8 house map, its registry, overview/recap/backlog
and new review. Inspected the diff and review: no new L0–5 contract, no clock/SQLite
boundary impact. Planning was clean at task start, NOT clean at final check; no
planning files were edited by Codex. Re-read the live working copy on resumption.

Module/tests/supplement/evidence/pyproject/README/handoff are uncommitted on2449ea0.
No planning/V2/deploy/live HA/power-cut/ARM-throughput claim. No production DB created.

### Exact next action

Review/commit this bounded storage slice when requested. Continue domain batch
schema/operations for accepted facts and CycleCommitMarker, then verified receipt-
backed accounting ranges and the actual continuity-watermark write. Read current
planning first and record schema rationale before costly choices. Compose all cycle
facts/marker/continuity operations in one transaction rather than flushing each
boundary. Mutable operation replay needs its own stable identity/reconciliation;
this immutable boundary mechanism does not solve general replay. Future worker/queue
owner handles admission, acknowledgements and uncertainty; HA lifecycle, startup
timeline enumeration and retention/pruning remain unimplemented. No generic weekly
CronEntry lifecycle or V2 migration. Git/deploy policies remain proposals.
