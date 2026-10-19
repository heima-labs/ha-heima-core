# Heima v3 - Architecture Overview of Defined Layers

**Status:** Explanatory reconciliation document. It does not replace the authoritative layer
specifications and introduces no new implementation requirement.

**Maintenance:** Manually synchronized when a confirmed decision is promoted to an authoritative
specification. **Reviewed through:** 2026-10-14 for every CA4 correction closed in
`docs/v3_backlog.md`, including the CA4-64 (CA5) and CA4-86–96 (CA6 and follow-ups) corrections; no
CA4 item is open. Where it differs from an authoritative specification, that specification wins.

**Scope:** Layers 0 to 6 and Layer 8 are defined in detail today; Layer 6 (notification) and
Layer 8 (administration) were approved on 2026-10-13. Layer 7 is outside this document except for
its interface obligations.

For bounded change work, start with the [contract registry](contract_registry.json) and
[specification workflow](spec_workflow.md). They record ownership and review evidence without
adding normative behavior.

## 1. Purpose and Reading Order

This document is the architectural map of the V3 work completed so far. It answers four practical
questions:

1. Which layer owns each kind of data, decision, and side effect?
2. Which paths are synchronous engine work, and which are slow/background work?
3. Which cross-layer communications are allowed, and which are deliberately forbidden?
4. Which decisions are already fixed before Layer 7 is specified?

The authoritative sources remain:

- [Layer 0 - Cross-Cutting Runtime Facilities](layer0_runtime_spec.md)
- [Layer 1 - Substrate Primitive](layer1_substrate_spec.md)
- [Layer 2 - Registries](layer2_registries_spec.md)
- [Layer 3 - Learning / Pattern Recognition](layer3_learning_spec.md)
- [Layer 4 - Semantic Resolution](layer4_domain_spec.md)
- [Layer 5 - Action and Reaction Generation](layer5_action_reactions_spec.md)
- [Layer 6 - Notification and Communication](layer6_notification_spec.md)
- [Layer 8 - Administration and Resident Surface](layer8_administration_spec.md)

Where this overview and an authoritative specification differ, the authoritative specification wins.

## 2. Architectural Picture

One dense graph made runtime, immutable contracts, staging, learning, and delivery look like one
message pipeline. The architecture is clearer as two PlantUML component diagrams with a shared
legend:

1. [Runtime and authority](architecture_runtime_authority.puml): the synchronous current-cycle path,
   its side-effect boundary, and the fact that Layer 1 is a contract rather than an intermediate
   runtime process.
2. [Support and governance](architecture_support_governance.puml): persistence/history, staged
   generations, learning outputs, review, and availability delivery.

In both diagrams, green components are layers defined so far; the legend keeps orange for a future
layer with already-fixed interfaces, and Layer 7 is not drawn yet. A solid arrow is an owned operational hand-off; a blue dashed arrow is
an immutable contract or staging dependency, never runtime message delivery.

## 3. Responsibility Map

| Layer | Owns | Main outputs | Does not own |
|---|---|---|---|
| 0 | Runtime facilities: time, persistence, provenance source vocabulary, channel divergence holds, recovery, runtime-health measurement | Durable/short-term history, timers, checkpoints, runtime-health snapshot | Fact meaning, registry semantics, learning policy, semantic resolution, actuator commands |
| 1 | Immutable semantic contracts: `HouseFact`, `Provenance`, `Location`, `Zone`, `Topology` | Typed values used by all other layers | Storage mechanics, HA reads, fusion, learning, commands, workflow records |
| 2 | Composition-time registry generation; HA read bindings; interpretations; fact fusion; formula registry; actuator inventory | Typed sensor/fused `HouseFact`s and logical Actuator descriptions | Durable storage, historical learning, semantic resolution, policy evaluation, action execution |
| 3 | Historical analysis; shared statistical lifecycle; optional ML governance; artifacts; findings; typed signals and learned candidates | `DiagnosticFinding`, `InferenceSignal`, `LearningProposalCandidate`, typed availability suppression occurrences | Fact persistence, HA access, semantic-claim resolution, policy approval, commands, notification rendering |
| 4 | Core semantic-resolver registry; staged semantic DAG; authorized signal gateway; current semantic-claim resolution | Resolved semantic `HouseFact`s, completed immutable `DecisionSnapshot`, typed availability suppression occurrences | HA reads, historical learning/model lifecycle, policy/guard/envelope evaluation, Actuator commands, notification delivery |
| 5 | Candidate validation/review; configured-Reaction staging; Reaction evaluation; action admissibility; `ApplyStep` generation | `ReactionProposal`, `ConfiguredReaction`, ordered one-endpoint `ApplyStep`s, per-Reaction decision state, typed suppression, follow-up and notice occurrences | HA read bindings, raw state interpretation, historical learning, notification delivery |
| 6 | Notification kind registry and adapters; recipients and audiences; families, quiet hours, digests; delivery, rendering, retries, fallback; availability episode tracker | The seven Layer-6 event facts with their outbox records; HA `notify.*` deliveries and `heima_notification` events | Response decisions, governance, occurrence meaning, configuration and history surfaces |
| 8 | The Heima panel by role; session change set, preview and apply; history and restore; explanations; house map; published HA entities; translations | Typed commands to owning layers; read-only HA entities; rendered views | Any configuration meaning, validation, authority, decision or fact; evaluation-cycle work |

## 4. Foundation: Layers 0 and 1

Layers 0 and 1 form a deliberately small foundation slice. Their relationship is reciprocal only for
immutable value contracts: Layer 0 persists Layer-1 `HouseFact` values, while Layer-1 `Provenance`
contains Layer-0 `FactSource`. Neither layer calls the other layer's behavior during an engine cycle.
This prevents a language-level import convenience from becoming an architectural behavior cycle.

### Layer 0: Runtime Facilities

Layer 0 standardizes the machinery every higher layer needs:

- **Timing:** `AtJob` is the one execution primitive; `CronEntry` is the recurrence policy above it.
  Instants are timezone-aware UTC. Local civil time exists only for explicitly local recurrences and
  presentation. Cycle instants strictly increase; jobs declare an `elapsed` or `wall_clock` basis,
  and a clock jump over 1 second re-arms wall-clock jobs and opens a `clock_discontinuity` gap
  (§3.1/§3.5).
- **Persistence:** accepted facts enter a short-term in-memory history and an ordered durable batch.
  State facts use write-on-change and a `FactIdentityKey`; event facts remain append-only. Durable
  pruning is time-based with a 14-day baseline, per-type retention declarations, a 50,000-record
  per-type ceiling, and a 512 MiB global watermark. The durable retry queue is bounded by
  `max(32 MiB, 5% of effective memory)` and declares overflow loss as `queue_overflow` coverage
  (§4.6), with an exceptional global gap when protected items alone exceed the budget.
  Durable baselines recover progressively within that budget; global closure can precede
  all keys, and reads requiring an unseeded key remain incomplete.
- **Committed-state observers:** a core component outside the DAG (for example Layer 6 waiting for
  quiet hours to end) subscribes to exact state keys, declared at bootstrap or derived from the
  active generation and re-declared at each swap, and is notified asynchronously
  after the cycle commit, coalesced to the latest value; no polling and no mirrored events (§4.8).
- **Honest history:** retention coverage is stream-scoped. A noisy stream in one room can make its
  own historical interval truncated without falsely degrading the same fact type in another room.
  Separate durable process-continuity metadata marks restart/outage intervals; a 60-second
  all-queue-acknowledged watermark bounds uncertainty after a crash. A typed
  `ObservationCoverage` accompanies declared durable history reads independently of
  retention. The process gap closes at the first durable `CycleInputBarrier` built
  from a fresh complete HA intake with explicit binding availability; an unreadable
  channel makes only its dependent windows incomplete. Windows crossing a process
  interruption or unavailable required channel are never zero-event evidence.
  Readable channels may resume current-policy automation while another is unreadable.
  An unchanged state keeps its last-change `HouseFact.when`; source-report age
  and durable stream-gap boundaries, not that old timestamp, determine whether
  a later historical interval was observed. Only changes and interruptions
  produce durable records, never every identical read.
  Each staged Actuator channel also publishes one bounded normalized
  `actuator.channel_state.<digest>` state stream on physical/availability
  changes and one fresh post-restart boundary. Its edge id joins the
  existing three-field verified `actuator.resident_control` event; Layer 5
  appends `actuator.target_lifecycle` phases only for admitted target
  decisions, complete observations and closure. Layer 3 uses these
  declared streams with correction facts and coverage to build routine
  outcomes and zero-correction denominators, never raw HA history.
- **Provenance and causality:** Layer 0 owns the non-forgeable `FactSource`/`ApplyStepSource`
  vocabulary and correlation-id propagation rules.
- **Manual control and recovery:** Layer 0 §6 owns one internal divergence hold per Actuator
  channel, with a shared release boundary, attributed facet expectations and bounded lifecycle
  audit. Layer 5 §6 chooses a descriptor's fixed-duration or next-step release and handles
  normal exit and resident follow-up. A restart restores no hold; Layer 0 §7 exposes only a
  read-only per-channel, per-facet recovery baseline with trusted source anchors for
  a fresh current-policy decision. Revoked Reaction facets are filtered. A recovery target
  requiring resident confirmation has one bounded request per channel; relevant
  changes invalidate it, and a restart requires a new proposal from fresh reads.
- **Environmental calculations:** Layer 2's registered formulas stage closed solar-incidence
  and humidity-ratio configurations, including opening orientation and an exclusive
  pressure-source choice. The reusable `numeric.hysteresis_condition.v1`
  converts a canonical numeric state into one typed boolean condition using
  entry/exit thresholds and validated previous-cycle self-memory. Layer 3
  consumes these typed facts for environmental learning. Its common
  environmental episode anchor is a profile-declared observed transition on
  a registered Sensor state or Actuator channel; Layer-0 channel-state facts
  provide exact normalized facets without a fan-specific learner. A first
  post-gap state or requested command is not a physical-transition anchor.
  Two core-generated
  Layer-2 Sensors read one frozen `sun.sun` elevation/azimuth snapshot, enforce
  HA `last_reported` age and numeric bounds, convert degrees to canonical radians,
  and exclusively claim the casa geometry facts. Per-opening formula bindings
  then use each opening's staged orientation; no learner computes an ephemeris.
  For irradiance-triggered solar shading, Layer 5 counts one elapsed wait from
  qualifying exposure; an observation gap counts only when the last valid
  state and first fresh state are both qualifying. Initial V3 uses a staged
  fixed dwell on this path and registers no solar-fraction forecast. An
  observed exit crossing of the hysteresis condition ends the occurrence,
  while a separate cover-movement cooldown gates admission. The generic
  state-fraction outcome and bounded-delay selector remain available only to
  descriptor paths with a separately reviewed learning definition.
- **Learned timing authority:** Layer 5 stores a stable
  `ReactionTimingModelBinding` with the descriptor path, learning definition,
  typed state, closed qualifying-value set and authorized window in the
  immutable Reaction plan. The generic state-fraction path and the
  registered room-return survival path use distinct result schemas. The
  latter selects `min+(max-min)*P(return by max)` for a member whose
  versioned intent-to-target translation declares delay eligibility and a
  maximum. The staged seed applies when no eligible artifact serves.
  A typed room-occupancy path qualifies at `absent` without another boolean
  fact. This does not register a solar timing model.
  Every delayed Reaction plan declares whether a gap resets observed dwell,
  pauses verified elapsed time or counts elapsed time after fresh
  requalification. Gap time counted for action is never training evidence.
  These modes retain an anchor only within a running Heima process. Restart
  restores no delayed job; a fresh qualifying sustained state begins a new
  full wait under current policy.
  Compatible artifact revisions are evidence/adoption state, not a changed
  Reaction configuration; shadow, review, promotion and consent use the
  ordinary gates. Proposal evidence carries exact role-tagged references for
  supplemental artifacts such as a timing model. Layer 5 records an exact
  adopted revision separately from the Reaction generation. A later `pinned`
  revision uses a revision-specific proposal through `review_proposal`;
  `bounded_adaptive` may advance only within its approved compatibility
  envelope. Validated administrator-only diagnostics need no artifact
  adoption. Registered live signals use Layer-3 adoption: exact admin
  approval per `pinned` revision or a core-validated compatible
  `bounded_adaptive` transition. Layer 3 keeps analysis identity separate
  from serving-generation identity: an objective edit can reuse the
  statistical response while requiring a new proposal. An authenticated
  mode-change transition retains the current adopted artifact; entry to
  `bounded_adaptive` revalidates the approved bounds, while exit to `pinned`
  fixes the current revision.
- **Runtime health:** Layer 0 measures latency, memory, CPU and runtime capabilities. It never
  decides whether a learner may run; Layer 3 consumes the read-only snapshot on its slow path.

Layer 0 reserves the seven Layer-6 notification kinds as Layer-6-owned event fact types:
`reaction.follow_up`, `automation.availability`, `reaction.advisory`, `reaction.action_notice`,
`recovery.confirmation_request`, `reaction.consent_request` and `proposal.review_pending`. A lower
layer may not append any of them directly. `reaction.follow_up` alone has a narrow durable-intent
preparation boundary (Layer 0 §4.5); event rendering and delivery remain Layer-6 work.

### Layer 1: Semantic Substrate

Layer 1 makes every durable house assertion answerable as WHAT, WHERE, WHEN, and HOW:

- `HouseFact` is the single persistent assertion record for house state and auditable operational
  occurrences.
- `Provenance` carries source, availability, confidence, and bounded evidence. An unavailable value
  is explicitly undefined and cannot be consumed as a stale value.
- `Location`, `Zone`, and `Topology` model place, declared groups, and physical relation separately.
  A Zone is not a Topology edge; a room inventory is referenced, not reimplemented here. Topology
  stores only physical facts (room enclosure, the other side of every opening, passable doors and passages) and
  defines the derived queries every consumer shares; purpose-specific groupings are Zones with a
  closed core role (`thermal_envelope`, reserved `security_perimeter`).
- Canonical JSON follows RFC 8785 where fingerprints or persisted canonical payloads require it.
  Fact payloads share one numeric domain: non-boolean integers within `±(2**53 - 1)` and finite
  binary64 floats, with no non-generic numeric objects; stricter contracts may narrow it.
- Time has one contract representation across layers: Layer 1 `EvidenceInstant` is the exact
  UTC microsecond `+00:00` instant for facts, jobs, snapshots, model artifacts and Reaction
  records; Layer 0 `Window` is the canonical seconds object for positive elapsed durations.
  A zero interval is represented explicitly by the owning contract (for example `None` at a
  point-outcome anchor). Calendar weekday/hour/minute values remain civil coordinates.
  Arithmetic may use temporary native values, but a declared contract never publishes an
  alternate `Z` instant, integer-millisecond duration or native datetime/timedelta object.

Layer 1 deliberately excludes artifacts, signals, candidates, commands, and review workflow records
from `HouseFact`. They have different authority and lifecycle, even when they are about the house.

## 5. Layer 2: From Home Assistant to Current Facts

Layer 2 is the semantic ingress and current-cycle fusion layer.

### Main mechanisms

- A **Person** classifies one HA `person` as `resident` or `guest` and stores its HA user link.
  It decides household membership and authority: a guest is never a resident, and an HA user with
  no `Person` is a device account. The HA administrator flag is a separate actor axis (CA4-118).
- A **Sensor** has one HA `ReadBinding`, one typed `Interpretation`, one fact type, and one explicit
  `Location`. Raw HA state/attributes/calendar data do not escape this boundary as learning or policy
  inputs.
- A **FusionRule** combines typed current facts using one closed strategy. The formula strategy is
  backed by a frozen core registry: `formula_id`, implementation version, pure binding validator and
  pure `compute` callable are resolved during staging, never dynamically in the hot path.
- An **Actuator** is a logical inventory descriptor. It can expose several independently controlled
  channels of one HA entity, but it does not issue commands. Layer 5 turns one logical actuator
  member into one endpoint-specific `ApplyStep`.

### Operational guarantees

- Registry generations are staged, validated, fingerprinted, and activated only within one
  composed configuration generation across Layers 2–6 (Layer 0 §4.7): an edit that breaks a
  downstream resolver, learner or Reaction needs confirmation of its impact record, then
  invalidates those dependents in the same atomic commit.
- State producer uniqueness is checked at composition for `(fact_type, Location)`; global fact-type
  claims protect reserved or dynamic namespaces.
- The current-cycle dependency DAG rejects cycles. `previous_cycle` is explicit and receives a
  bounded Layer-0 snapshot rather than a durable read.
- Interpretations, fusion strategies, and formulas are closed core-owned registries. They are pure,
  synchronous and bounded: no I/O, network, dynamic import, or HA access in the hot path.
- Availability grace and stability transitions are layer-owned state machines that reset selectively
  when a changed generation affects them.

## 6. Layer 3: Historical Learning and Pattern Recognition

Layer 3 analysis, training and validation are off the engine hot path. Its only in-cycle step is the
bounded emission of an adopted live `InferenceSignal`, after the Layer-2 barrier and before Layer 4,
with one replaceable expiry `AtJob` per contract and subject (Layer 3 §6.3). It reads only Layer-0 fact history and immutable staged contracts;
it never reads HA runtime objects or a mutable HA payload.

### Shared learning platform

- A learner declares a typed `SampleBinding`, complete `training_window`, feature lookbacks, target
  horizons, supported scope, resource envelope, and allowed egress. Staging derives its per-stream
  retention requirements and registers them one way with Layer 0.
- A bounded `FutureStateFractionOutcome` measures the share of a future
  interval spent in one staged typed state condition, including returns after
  an exit. It reuses state-history reconstruction and the scalar result; an
  incomplete interval contributes no training label. It grants no action
  authority by itself (CA4-13).
- The registered `RoomOccupancySurvivalModel.return_delay` instead estimates
  the cumulative incidence of a return after a physically supported room
  vacancy transition. Its finite grid starts at one minute and preserves
  censoring and declared competing events. A validated, adopted artifact may
  supply timing evidence to the generic single-member vacancy path of
  `routine.actuation_bundle`; Layer 5 alone selects the bounded wait and
  performs fresh admission. Delay permission belongs to the versioned
  translation of a typed target, not the Actuator's display role; no
  universal device-kind allowlist is required. Diagnostics and model evidence never command an
  Actuator directly.
- A learner requiring complete history refuses a truncated interval. It stays warm-up/degraded rather
  than silently learning from a shorter window.
- Routine discovery keeps one measured output per canonical bundle/context
  cell. It compares trigger-window frequency with a subject baseline from
  complete sliding-window time exposure of the same assembly duration; lift is the
  finite conditional-to-baseline ratio. A zero baseline cannot qualify a
  proposal. This evidence never gives individual bundle members authority
  (Layer 3 §4.4.3; Layer 5 §3.2).
- `PatternLearner` centralizes support, warm-up, confidence, tiers, fallback, diagnostics, staleness,
  and bounded findings. Tier fallback chooses the first valid declared tier; it never averages or
  searches for a nearest context.
- ML is permitted only through the same lifecycle: typed sample binding, chronological validation,
  leakage controls, shadow policy, calibration/coverage/KPI/drift lifecycle, resource admission and
  bounded artifacts. Local execution is the initial baseline; future external training or inference
  remains an explicit extension behind the same contracts.

### Outputs and authority

| Output | Consumer | Authority boundary |
|---|---|---|
| `DiagnosticFinding` | Administrator-facing diagnostics/review | Never a fact, command, or direct notification |
| `ShadowProposalPreview` | Diagnostic finding registry | Preview only; promotion creates a new candidate and never reuses the preview as approval |
| `InferenceSignal` | Exactly one authorized Layer-4 semantic resolver | Transient, typed, expiring input; not a policy or `HouseFact` |
| `LearningProposalCandidate` | Layer 5 | Evidence for review; Layer 5 independently validates candidate kind/version and policy payload |
| `AvailabilitySuppressionOccurrence` | Layer-6 `AvailabilityEpisodeTracker` | Typed availability transition, not a notification, event fact, command, or persistence request |

The proposal path is intentionally one way: learning proposes, Layer 5 reviews, a `ConfiguredReaction`
later evaluates under current conditions. A statistical result can refine only its pre-approved
authority; it cannot expand scope, add an Actuator, alter guards, or command HA.

### Availability and resident visibility

An owner emits an availability occurrence only when an episode starts, its canonical reason set
changes, or it ends. Reasons are a non-empty, distinct ASCII-lexicographically ordered tuple built by
the frozen pure `canonicalize_suppression_reasons()` helper. This avoids false changes caused by
different ordering of the same causes.

Layer 6 receives every occurrence through its transient `AvailabilityEpisodeTracker`, even if no
resident-visible binding currently exists. The staged `AvailabilityPublicationIndex` maps an exact
owner/scope/subject key to a canonical tuple of configured automations. At a generation swap, the
tracker reconciles active episodes: newly visible bindings receive the current issue; removed or
disabled bindings close in administrative audit without a misleading later restoration. This keeps
resident delivery correct without polling or callback dependencies between Layer 3 and Layer 5.

## 7. Layer 4: Semantic Resolution

Layer 4 turns declared Layer-2 facts and the narrow authorized Layer-3 signal input into current
semantic claims and completed semantic episodes. Its staged core resolver registry is a deterministic
DAG: every resolver can read only its declared lower-fact slots, declared upstream claims, one declared
signal slot, declared previous-cycle values, and canonical parameters. It cannot read HA, a global fact
map, policy configuration, future resolver output, or arbitrary history.

After the Layer-4 DAG completes, the engine assembles the immutable `DecisionSnapshot` for Layer 5. It carries the
resolved semantic claims and episodes plus the Layer-0 `FrozenHistoryView`, `FrozenCalendarView`
and `HoldAdmissionView`, the Layer-0 `FrozenRecoveryView`, and Layer 5's
`CommandOwnershipView` and `FrozenReactionAuthorityView`, assembled at the shared intake barrier.
For declared state-transition triggers, the coordinator adds typed
previous/current state pairs after semantic resolution; it does not insert
Layer-4 claims into the Layer-2 intake group or mirror all state changes as
episodes.
Layer 4 transports those frozen views opaquely: it never reads, classifies, resolves, or otherwise
interprets calendar windows or hold/ownership decisions, and it never evaluates a reaction,
guard, envelope, or Actuator.

## 8. Layer 5: Review, Policy, and Action

Layer 5 is downstream of the Layer-4 semantic DAG. It is outside that DAG and sees one immutable
`DecisionSnapshot` after Layer-2 equal-`when` intake facts have been consolidated behind a cycle
barrier. Its declared short-term windows are served only through the paired Layer-0
`FrozenHistoryView`; it never rereads HA, durable history, or a later mutable state while deciding an
action.

### One policy mechanism

- The core-owned, frozen `ReactionDescriptorRegistry` supplies one evaluator, one configured-Reaction
  persistence path, one admissibility phase, and one `ApplyStep` protocol. Namespaces such as
  `environment.*`, `lighting.*`, and `security.*` are descriptors, not separate rule engines.
- The frozen `ProposalCandidateKindRegistry` validates the outer candidate kind/version before the
  selected Reaction descriptor validates its own independent version and payload. Initial V3 supports
  `("reaction.descriptor", 1)`.
- A learned candidate becomes a persisted `ReactionProposal`, then an explicitly reviewed configured
  policy. Strong evidence never enables an automatic action on its own.
- A learner's measured effect has one authoritative, profile-registered
  output schema. Layer 5 validates the referenced artifact under that schema;
  descriptor intent/target checks and the proposal evidence revision remain
  separate. No second effect-summary payload is required (Layers 3 §6.4,
  5 §3.1).
- The candidate carries stable descriptor, target and applicable numeric-outcome
  requirements. Measured response, thermal reachability and whole-bundle
  routine frequency stay in the profile's typed artifact and refreshable
  proposal evidence; no routine member receives a fictitious physical delta.
- A `ConfiguredReaction` has one stable identity and immutable append-only configuration generations.
  Its compiled canonical plan is persisted without callables; administrative enablement and any
  household consent are separate authority transitions, so neither can silently rewrite policy meaning.
  All seven Initial-V3 descriptors declare resident consent as required. An awaiting or
  revoked consent blocks commands as an authority state, not as an unavailable input.
- The frozen descriptor version supplies the base typed plan grammar. A
  learner relation profile narrows it; a profile-free admin-direct Reaction
  uses the descriptor's complete non-guard grammar and its exact direct guard
  contract. Both compile into the same plan. `CanonicalEnvelope` remains
  common: direct cells have no learner support/calibration metadata, and
  presence simulation uses one zero-axis empty-key cell. A descriptor may
  register that same direct shape while its learned profile uses nonempty
  supported context axes; typed trigger and required guards still delimit
  the direct action. Guard requirements resolve from the descriptor-validated
  action intent and semantic variant, so an external-exchange purpose need
  not inherit unrelated purpose guards. Future direct axes and pure
  versioned partitions are declared by descriptor version.
- Initial-V3 `environment.air_extraction` applies to any registered room with
  a compatible extraction fan. Its single staged room-humidity trigger may be
  a level crossing, a rise over a window or a rise rate; room occupancy is
  required only when declared. A fan already active at qualifying start is
  untouched by that activation; an initially inactive fan may be controlled
  through its declared steps. Observed entry state, `level` start/increase/stop edges
  and origin remain distinct learning evidence. The common environmental
  learner keeps a separate profile-declared physical transition class,
  comparable reference cohort and response estimate for `start`, `modify_up`
  and `terminate` (a downward or multi-level edge is excluded). Each programmed
  step declares whether it needs its exact class estimate; a missing estimate
  suppresses that step, while a descriptor-declared deterministic step remains
  subject to current admission. For a learned modification the descriptor
  also requires current need and a conservative response qualifying under
  the reviewed objective; the developer declares legal bounded actions,
  not their fixed efficacy or indispensable future targets. Its registered
  start/step-up/end program, level target, `humidity_extraction` profile and
  guard contract are in Layer 5 §7 and §3.2.
  This descriptor declares managed-episode resumption; it is available only
  after a verified Heima inactive-to-active edge. Layer 5 stores one compact
  open/closed state per channel in Layer 0's ordinary cycle batch. After
  restart, a committed open state and fresh current inputs permit a new
  activation to recalculate its program. If the first fresh valid channel
  reading after a restart is active without usable proof, Layer 5 leaves that
  channel untouched and reports the typed
  `active_channel_unmanaged_after_restart` availability cause to Layer 6.
  It reports this even when the action trigger is false; Layer 6 uses a new
  process-run notification key. That issue persists until a fresh inactive
  reading or verified proof; a changed trigger alone cannot falsely report restoration. No hold, timer or
  missed step is restored, and the unobserved interval is excluded from learning.
- Reaction guards use one core capability registry assembled and frozen at bootstrap. Descriptor
  contracts reference its versioned entries, while households stage only typed guard-profile bindings;
  a new guard-profile generation cannot silently alter an active Reaction.
  Its `quiet_hours.v1` capability reads an explicit casa boolean fact only for
  descriptor intents that require it. Layer 6 reads the same fact for its notification quiet
  hours (Layer 6 §6.2), but its delivery behavior is its own and never becomes a guard.

### Safe execution

- A policy has one temporal trigger or versioned programmed-activation start
  criterion, typed guards, one `CanonicalEnvelope`, and one finite ordered
  `ActuationBundle`.
- A step-programmed descriptor's already declared start criteria are checked
  on current frozen inputs, including after restart. Semantic episodes,
  calendar updates and due jobs request re-evaluation; they do not create
  additional triggers or a second evaluator.
- Its descriptor version registers one pure `evaluate_program` specialization;
  the compiler persists only typed parameters and bindings. The specialization
  uses the frozen snapshot and activation state to select start, target
  changes, wait or normal end and supplies each selected step's typed target.
  Fresh typed events and due timers request that same evaluation; a
  simultaneous event and timer produce one effective
  target and step identity per channel. Only timed future steps occupy the
  shared `AtJob` slot. Event steps use the same admission and `ApplyStep`
  path; a next-step hold requires a fresh post-release continuation check.
- Step-programmed Reactions share one activation-stable next-`AtJob` replacement slot, separate
  from each descriptor's planned-step identity. Temporary input loss preserves the activation;
  a fresh evaluation replaces at most the next job, and stale callbacks cannot dispatch
  (Layer 5 §6.0).
- The whole bundle passes admissibility before execution. A known-invalid member prevents all steps;
  a later HA failure stops remaining steps and records a partial outcome without speculative
  compensation.
- Each `ApplyStep` addresses exactly one logical actuator endpoint and retains the exact reaction
  configuration generation that produced it. Multiple actuator changes are represented as ordered steps
  in the same bundle, not as a multi-entity HA command.
- Manual holds, command ownership, capability, confirmed physical state, dwell/cooldown, and safety
  guards are checked on the immutable decision snapshot.
- When a configured action cannot proceed, Layer 5 emits a typed availability occurrence with every
  applicable closed reason. It does not render, persist, or send resident notifications.

## 9. Cross-Layer Communication Rules

| From | To | Allowed contract | Prohibited shortcut |
|---|---|---|---|
| 0 <-> 1 | Foundation peer | Immutable values only (`HouseFact`, `Location`, `FactSource` in `Provenance`) | Behavioral calls or registry/policy lookup across the boundary |
| 2 -> 0 | Persistence | Accepted `HouseFact` values, global fact claims, declared retention/buffer needs | Raw HA payload persistence or dynamic fact ownership |
| 2 -> 1 | Immutable contracts | Constructs/consumes Layer-1 `HouseFact`, `Location`, and `Provenance` values | Runtime message delivery or behavioral call into Layer 1 |
| 3 -> 0 | Persistence | Declared history/retention requirements; bounded history reads | Hot-path disk read, training from truncated required history |
| 3 -> 4 | Semantic resolution | One authorized typed `InferenceSignal` | Signal as a fact, generic event bus, or direct action |
| 3 -> 5 | Review path | Typed `LearningProposalCandidate` | Approval, configuration mutation, or command generation by Layer 3 |
| 5 -> HA | Execution | Ordered one-endpoint `ApplyStep`s | Raw multi-entity command graph or arbitrary service payload |
| 3/4/5 -> 6 | Availability | Typed runtime suppression occurrences; own immutable staged publication declarations | Rendering, direct notification, policy lookup, or `automation.availability` persistence |
| 5 -> 6 | Reaction follow-up | Typed `ReactionFollowUpOccurrence` and a durably prepared intent at the qualifying boundary; Layer 6 persists the existing `reaction.follow_up` event fact and renders text only when it delivers its derived `HeimaEvent` | Layer-5 rendering, a second delivery envelope, or replaying an Actuator command from the outbox |
| 5/0 -> 6 | Notices and requests | Typed advisory, action-notice, proposal-review and consent occurrences (Layer 5) and recovery-confirmation occurrences (Layer 0) | Pre-rendered text or any lower-layer append of a Layer-6 event fact |
| 6 -> 0/1 | Delivery audit | Sole producer of the seven Layer-6 event fact types, each committed with its outbox record (Layer 0 §4.5); answers forwarded only to Layer 0's response ingress | Any lower-layer claim of these reserved event fact types, or Layer 6 deciding a response |
| 8 -> 0/3/5 | Administration | Change sets committed through Layer 0 §4.7; governance commands of Layer 5 §4.2 and Layer 3; answers through the response ingress | Writing another layer's store, evaluating a policy, or running in an evaluation cycle |

## 10. Performance and Technology Choices Already Fixed

These are architectural technology choices, not incidental implementation preferences:

- **Typed immutable contracts:** dataclass-like immutable records, closed vocabularies, explicit
  versions and pure validators are the default cross-layer protocol. No untyped generic event bus is
  introduced.
- **Staged immutable generations:** registries, Reaction-descriptor definitions, candidate kinds, formulas, and
  publication bindings validate before atomic activation. The active engine reads frozen O(1) indexes.
- **No ordinary blocking I/O in the hot path:** HA data are read at Layer 2's binding boundary; learning, persistence maintenance, resource probing, and
  notification delivery do not block Sensor/Fusion/semantic-resolution/policy
  evaluation. The narrow Layer-0 §4.5 follow-up-intent preparation waits for a
  durable acknowledgement at a qualifying Reaction boundary only up to the
  finite, versioned Layer-5 core preparation deadline; a failed or still
  unacknowledged write degrades notice recovery without holding a scheduled step.
- **Two time scales:** current facts and fusion are synchronous per cycle; historical learning,
  model rebuilds, publication reconciliation, retention pruning, and notification delivery are slow
  or background operations.
- **Canonical identity:** stable keys, explicit versions, and RFC 8785 canonical JSON make reload,
  deduplication, audit, and cache invalidation deterministic.
- **Bounded storage and work:** retention floors are declared; count and global storage ceilings are
  hard; learning and finding capacities are explicit; admission is guided by measured runtime health.
- **Clean V3 start:** no V2 configuration, state, model, approval, or history migration enters a V3
  runtime path. This removes conversion branches from bootstrap and the hot path.

Notification transport is fixed by Layer 6: Home Assistant `notify.*`, mobile actions and
`persistent_notification`. The specifications intentionally do **not** select a durable database
engine, ML framework or external training protocol yet. Those choices must implement the contracts above;
they must not weaken ownership, typed boundaries, staged validation, or hot-path constraints.

## 11. Defined but Gated, and Deferred Ownership

The following descriptors are defined Initial-V3 contracts, but remain gated per household rather than
being unconditional behavior. Both declare the shared, versioned `planned_absence_program` family
(Layer 5 §3.2), which owns their calendar-plus-stabilized-away activation, departure and bootstrap
handling, normal exit, next-step hold release, restart and consent rules once:

- **Evidence-gated Initial-V3 descriptor:** `environment.planned_comfort_trajectory` is registered
  from the start. Its administrative HVAC/calendar/comfort prerequisites are staged as an
  immutable versioned generation. A proposal additionally requires validated thermal evidence;
  automatic action requires the separate operational shadow, authenticated promotion and
  current household consent gates.
  Its prerequisite stages one explicit desired heating/cooling mode source;
  only the matching mode Reaction can act, and opposing active equipment
  blocks the command.
  Its descriptor uses `next_reaction_step` hold release; a future target-changing HVAC step is
  evaluated through a fresh snapshot after that release.
  It applies an absence target directly and a core-generated, model-supported recovery-only ramp one
  fresh bounded step at a time; it has no fallback behavior.
- **Admin-direct Initial-V3 descriptor:** `security.presence_simulation` is registered from the
  start as a bounded planned-absence deterrence aid, never a security guarantee. Its initial
  core-generated light-activity episodes use the common calendar/presence guards, scheduler,
  `ConfiguredReaction` authority lifecycle and one-endpoint `ApplyStep` path. It is not a Layer-3
  learning family. Selected endpoints are admitted by their registered light-state channel and
  adapter, not by a free-text Actuator role. It also uses `next_reaction_step` hold release.
  Its planned light steps include switch-off after the last
  activity for each light, and run while current absence and action criteria hold. A
  committed early return cancels unsent steps without adding a terminal
  command. Preview shadow is optional rather than an evidence gate; a future learned or
  imported temporal profile needs its own contract before it can replace the core generator.

**Layer 6 (defined).** [Layer 6](layer6_notification_spec.md) is the one path for pushed
notifications. A closed registry of eight kinds turns typed occurrences into one audited event fact
per phase with no stored text, committed with its outbox record. Recipients are people, optionally
linked to a Layer-2 `Person`, with endpoints; `residents` and `consent_authorities` derive from the
Person's classification and `HouseholdConsentAuthority`, and only `administrators` is configured on
the recipient (CA4-118). Closed families drive quiet hours (`safety` bypasses; Reaction notices
take their family from the descriptor namespace), proposal and advisory digests group low-urgency
items, and item tags let later phases replace or clear a notification. Delivery uses `notify.*`,
growing retries and a single `persistent_notification` fallback; buttons go through
`mobile_app_notification_action` to Layer 0's ingress. Text is rendered at delivery per recipient
locale. The `AvailabilityPublicationGeneration`, recipients and family options form the Layer-6
generation of the composed configuration generation. Each person's own preferences (language,
level per family, own endpoints) live in a separate Layer-6 store outside the generation (CA4-116).

**Layer 8 (defined).** [Layer 8](layer8_administration_spec.md) is the single Heima panel, with
content by role resolved server-side from the HA user (administrator from HA's flag, resident from
the user's Layer-2 `Person`, or no access for guests and device accounts; CA4-118). The
config flow only creates the integration. Configuration edits accumulate in a session change set
and apply atomically after a preview of changes, effects and errors; governance actions and answers
are immediate. One history timeline with restore, a "Why?" chain on every object (built on
the per-Reaction `reaction.decision.<digest>` state, trigger history and the generation of that time), a native house map drawn from rooms and topology (device control through HA's own controls),
read-only published HA entities fed by committed-state observers and owner projections, a guided
first start, and fully translated text (English source, `en` and `it` shipped). The panel is a Lit
custom panel talking to typed websocket messages; nothing runs in an evaluation cycle.

The following ownership remains deliberately deferred beyond Layers 0--6 and 8:

- **Layer 7:** Plugin lifecycle. Existing specs permit separately staged ordinary fact producers,
  diagnostics, and candidates under exact existing core contracts, but deliberately do not permit
  plugins to extend core hot-path semantic registries or create `ApplyStep`s/invoke Actuators.
  A plugin's staged producer claims and consumer bindings must enter the composed-generation
  dependency index like core ones; adding, upgrading or removing a plugin is a configuration
  mutation with the same impact preview, confirmation and invalidation rules (Layer 0 §4.7).
These layers must consume the frozen boundaries above rather than creating parallel state stores,
specialized action engines, or direct HA access from learning/policy code.

## 12. Implementation Reading Checklist

Before implementing a component, answer these questions in order:

1. Is this a durable assertion about the house? If yes, use a Layer-1 `HouseFact` persisted by Layer 0.
2. Is it a current HA observation or a fusion of observations? It belongs to Layer 2.
3. Does it need retained history, validation, support and bounded statistical evidence? It belongs to
   Layer 3 and must run off the hot path; only bounded serving of an adopted live signal runs in the cycle.
4. Is it a current semantic decision? It belongs to Layer 4, not to a learner or a policy.
5. Does it create, approve, evaluate, or execute an action? It belongs to Layer 5.
6. Does it render or deliver a resident-facing message? It belongs to Layer 6.
7. Does it present, edit or explain configuration, decisions or state to people? It belongs to
   Layer 8, which only sends typed commands to the owning layer.
8. Would it add a second representation, registry, scheduler, action engine, or callback path? Reuse
   the existing typed mechanism unless the shared contract cannot express the requirement without
   weakening meaning, safety, or hot-path performance.
