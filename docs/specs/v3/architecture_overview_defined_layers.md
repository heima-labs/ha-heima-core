# Heima v3 - Architecture Map

**Status:** orientation document. It introduces no requirement: every statement summarizes an
authoritative Layer 0–8 specification and names the section it comes from. Where this map and a
specification differ, the specification wins and this map is wrong.

**Reconciled through:** CA4-162 (planning `c9a4dd8a` + CA4-162).

**Maintenance:** a change that closes a CA4 issue updates this map in the same commit (or
confirms it needs no change) and raises the line above. `scripts/check_v3_specs.py` fails when
that line is behind the backlog, when a contract id below is not in the registry, or when a layer
section is missing. The map carries no history: decision trails live in `docs/v3_backlog.md`, and
the earlier narrative `docs/v3_architecture_recap.md` is historical only.

## 1. How to use this map

- **Read it whole, once per session.** It is sized to be the big picture for a person or an agent
  starting work, and to tell you which specification section to open next.
- **Then read the owning specification section in full.** Look up the contract id
  (`L<layer>-…`, shown in brackets) in [`contract_registry.json`](contract_registry.json); its
  `owner` and `heading` name the section. Read the sections of its direct `depends_on` contracts that
  your task consumes. The [workflow](spec_workflow.md) governs specification changes.
- **Do not implement from this map.** It omits bounds, edge cases and acceptance criteria on
  purpose.

Authoritative specifications: [L0 runtime](layer0_runtime_spec.md),
[L1 substrate](layer1_substrate_spec.md), [L2 registries](layer2_registries_spec.md),
[L3 learning](layer3_learning_spec.md), [L4 semantic resolution](layer4_domain_spec.md),
[L5 action/reaction](layer5_action_reactions_spec.md), [L6 notification](layer6_notification_spec.md),
[L7 extensions](layer7_extensions_spec.md), [L8 administration](layer8_administration_spec.md).

## 2. The system in one page

Heima V3 is a Home Assistant integration that turns observations of a house into typed facts,
resolves what those facts mean, and acts only through reviewed, explicitly authorized policies.
It is a clean start: no V2 configuration, history, model or approval is migrated (L2 §1.1).

```text
Layer 8  Administration       one role-based panel; atomic change sets; history; "Why?"; house map
Layer 7  Extensions           first-party, off-cycle; facts, diagnostics and candidates; no actions
Layer 6  Notification         eight closed kinds; one audited pipeline; families, quiet hours, digests
Layer 5  Action / reaction    descriptors, proposals, ConfiguredReactions, admission, ApplySteps
Layer 4  Semantic resolution  staged DAG of semantic claims (occupancy, presence, activities)
Layer 3  Learning             off-path history analysis; signals, findings, proposal candidates
Layer 2  Registries           HA ingress (Sensor), fusion (FusionRule), Actuator inventory, people
Layer 1  Substrate            immutable contracts: HouseFact, Provenance, Location, Zone, Topology
Layer 0  Runtime              time, persistence, provenance vocabulary, holds, recovery, health
```

- **L0 + L1 are one foundation slice.** L1 owns immutable value contracts; L0 owns the runtime
  mechanisms that store, time and protect them. They depend on each other only through immutable
  values, never through behavior (L0 §2.1).
- **L2–L5 are what the engine does in a cycle.** One synchronous, event-driven evaluation from HA
  reads to `ApplyStep`s. Only L3's bounded live-signal emission runs in the cycle; its learning
  runs elsewhere.
- **L6–L8 are how people see and steer it.** They run outside the evaluation cycle.

Two component diagrams show runtime authority and support/governance:
[runtime and authority](architecture_runtime_authority.puml),
[support and governance](architecture_support_governance.puml).

## 3. One evaluation cycle, end to end

Heima is event-driven: a meaningful HA state change, a due `AtJob` (for example a Fusion dwell
deadline, a signal expiry or a Reaction's next step) or the bounded periodic safety net requests a
cycle; a fixed timer never drives evaluation (L0 §2, §3.1). One cycle runs these steps in order:

1. **Cycle instant.** Layer 0 assigns `cycle_instant = max(wall clock, previous + 1 µs)` and checks
   for a clock discontinuity (L0 §3.5) [L0-CYCLE-INSTANT]. The active composed generation is fixed
   for the whole cycle; a committed change swaps all layers together only at a cycle boundary
   (L0 §4.7) [L0-COMPOSED-GENERATION].
2. **Recovery context.** Layer 0 classifies runtime state from the pushed observation set in O(1),
   before any semantic work (L0 §7.1) [L0-RECOVERY-CLASSIFICATION].
3. **Layer 2 intake.** Every active `ReadBinding` is read once (HA state, one attribute, or the
   calendar `active_now` view from Layer 0's cache), interpreted into a typed `HouseFact`, then
   `FusionRule`s run in DAG order with their stability rules (L2 §3–§5) [L2-TYPED-STATE-INGRESS,
   L2-FUSION-STABILITY]. Accepted facts go through Layer 0: write-on-change for state, append for
   events, the in-memory buffer and the ordered durable queue (L0 §4.1–§4.2) [L0-STATE-HISTORY].
4. **Input barrier.** Layer 0 closes the intake with one `CycleInputBarrier` and freezes the
   declared history and calendar views at that barrier (L0 §4.1, §3.4.1) [L0-FROZEN-HISTORY].
5. **Live signals.** An adopted Layer-3 live signal is emitted from the frozen intake and its own
   staged requirements, stamped with the cycle instant (L3 §6.1, §6.3) [L3-SIGNAL-EGRESS].
6. **Semantic DAG.** Layer 4 builds a `SemanticInputSnapshot` and runs enabled resolvers in
   topological order; outputs become `HouseFact`s through the same Layer-0 path (L4 §5)
   [L4-DECISION-SNAPSHOT].
7. **Decision snapshot.** The engine assembles the immutable `DecisionSnapshot`: intake group,
   current Layer-2 facts, semantic claims and episodes, declared state-transition pairs, and the
   frozen history, calendar, hold, command-ownership, recovery and Reaction-authority views
   (L4 §5.1).
8. **Reactions.** Layer 5 evaluates every active `ConfiguredReaction` against that snapshot only:
   trigger or program, guards, envelope, then one admissibility phase (holds, ownership, authority,
   consent, recovery). Admitted members become ordered one-endpoint `ApplyStep`s; the decision is
   recorded as per-Reaction state; typed occurrences go to Layer 6 (L5 §5–§6)
   [L5-PROGRAM-EVALUATOR, L5-DECISION-RECORD].
9. **Commit.** The cycle's accepted facts are committed durably with a `CycleCommitMarker`, never
   blocking evaluation; the `PreviousCycleSnapshot` is sealed for the next cycle; committed-state
   observers are notified after commit (L0 §4.1, §4.4, §4.8) [L0-COMMITTED-STATE-OBSERVERS].

Outside the cycle: Layer 6 adapters turn occurrences into audited event facts and deliver them
asynchronously; Layer 3 trains and analyzes on its slow path; Layer 7 instances run on their own
cadence and their results enter at a later barrier; Layer 0 prunes retention, writes checkpoints
and samples runtime health; Layer 8 change sets commit through L0 §4.7. The one bounded wait inside
the cycle path is the preparation of a qualifying `reaction.follow_up` intent (L0 §4.5.1).

## 4. Responsibility map

| Layer | Owns | Main outputs | Does not own |
|---|---|---|---|
| 0 | Time, persistence, provenance vocabulary, divergence holds, recovery, runtime-health measurement, composed generations | Durable/short-term history, timers, checkpoints, frozen views, health snapshot | Fact meaning, registry semantics, learning policy, semantic resolution, commands |
| 1 | Immutable contracts: `HouseFact`, `Provenance`, `FactValueContract`, `Location`, `Zone`, `Topology` | Typed values used by every layer | Storage, HA reads, fusion, learning, commands, workflow records |
| 2 | Registry generation; HA read bindings; interpretations; fusion; formula registry; Actuator inventory; people and declared household context | Typed sensor/fused `HouseFact`s, logical Actuator channels, recovery observation set | Durable storage, learning, semantic resolution, policy, execution |
| 3 | Historical analysis; shared statistical lifecycle; optional ML governance; artifacts | `DiagnosticFinding`, `InferenceSignal`, `LearningProposalCandidate`, availability occurrences | Persistence, HA access, semantic resolution, approval, commands, rendering |
| 4 | Core resolver registry; staged semantic DAG; signal gateway | Semantic-claim `HouseFact`s, episodes, `DecisionSnapshot` | HA reads, learning, policy, commands, delivery |
| 5 | Descriptor registry; proposal review; Reaction configuration and authority; evaluation; admissibility; `ApplyStep`s | `ReactionProposal`, `ConfiguredReaction`, `ApplyStep`s, decision state, typed occurrences | HA bindings, interpretation, learning, delivery |
| 6 | Kind registry and adapters; recipients, audiences, families, quiet hours, digests; delivery and rendering | Eight event fact kinds with outbox records; HA `notify.*` deliveries | Response decisions, governance, occurrence meaning |
| 7 | Extension blueprint registry and instances (first-party only) | `ext.*` facts, diagnostics, candidates under existing kinds | Any action, descriptor or candidate kind |
| 8 | Role-based panel; change sets, preview, apply; history/restore; explanations; house map; published entities; translations | Typed commands to owning layers; read-only HA entities | Any configuration meaning, validation, authority, decision or fact |

## 5. Cross-layer communication

| From → to | Allowed contract | Prohibited shortcut |
|---|---|---|
| 0 ↔ 1 | Immutable values only (`HouseFact`, `Location`, `FactSource` in `Provenance`) | Behavioral calls or registry lookups across the boundary |
| 2 → 0 | Accepted `HouseFact`s, fact-type claims, event producer declarations, retention/buffer needs, recovery observation set | Raw HA payloads, dynamic fact ownership |
| 3 → 0 | Declared history requirements; bounded history reads | Hot-path disk reads; training on truncated required history |
| 3 → 4 | One authorized typed `InferenceSignal` | Signal as a fact, generic event bus, direct action |
| 3 → 5 | Typed `LearningProposalCandidate` | Approval, configuration change or command by Layer 3 |
| 5 → HA | Ordered one-endpoint `ApplyStep`s | Multi-entity command graphs, arbitrary service payloads |
| 3/4/5 → 6 | Typed availability occurrences; staged publication declarations | Rendering, direct notification, `automation.availability` persistence |
| 5/0 → 6 | Typed follow-up, advisory, action-notice, review, consent, recovery and health occurrences | Pre-rendered text; lower-layer append of a Layer-6 event fact |
| 6 → 0 | Sole producer of its eight event kinds, each with its outbox record; answers forwarded to Layer 0's response ingress | Layer 6 deciding a response |
| 7 → 2/3 | Staged producer instance (`ext.*` claims) and analyzer instance (existing candidate kinds) | Actions, raw HA state, person-related facts, in-cycle execution |
| 8 → 0/3/5 | Change sets through L0 §4.7; governance commands; answers through the response ingress | Writing another layer's store, evaluating policy, running in a cycle |

Sources: L0 §2.1, §4, §5.1.3; L3 §6; L4 §6–§7; L5 §2, §6.0; L6 §3, §13; L7 §5–§7; L8 §2–§3.

## 6. Cross-cutting mechanisms

### 6.1 Staged generations and the composed manifest

Every configuration change in Layers 2–6 activates only as one **composed configuration
generation** [L0-COMPOSED-GENERATION] (L0 §4.7):

- **Staging.** Each layer validates its candidate part against candidate lower layers. Layer 0
  builds a dependency index from producer declarations and consumer references.
- **Impact.** Every consumer outside the edited objects is `breaking` (its binding no longer
  validates: missing producer, changed `FactValueContract`, changed scope…), `semantic_only` (an
  upstream execution fingerprint changed) or `unaffected`. A non-empty impact record needs the
  administrator to confirm its `impact_fingerprint` against the base generation.
- **Commit.** One atomic transaction writes the manifest, layer generation records and dependent
  invalidations; the engine swaps all layers at the next cycle boundary. No cycle sees a mix.
- **Code upgrade.** At bootstrap the latest manifest is restaged; a changed formula, learning
  type, resolver kind, descriptor or extension version is classified and invalidated under the
  system actor with diagnostics.
- **Not configuration:** runtime authority transitions (promotion, consent, disablement), artifact
  adoption and learning lifecycle transitions. Accepting a learned proposal is the one governance
  command that creates configuration (L5 §4.1).

Registries that are not administrator-editable are **core-owned and bootstrap-frozen**: formulas,
semantic resolver kinds, learning types, Reaction descriptors, proposal candidate kinds, guard
capabilities, notification kinds, extension blueprints. Their hot-path lookups are O(1).

### 6.2 Fingerprints and versions

All stable digests are SHA-256 over RFC-8785 canonical JSON (L1 §3). Each staged producer has:

- an **execution semantic fingerprint**: exactly the inputs that can change its output, including a
  core **implementation version** for core logic. It is `FactSource.configuration_fingerprint`
  and drives write-on-change, `previous_cycle` invalidation and `semantic_only` impact;
- a **definition fingerprint**: the full administrative definition, for audit and generation
  identity.

Owners: Sensor and Fusion (L2 §2.5, §5.3), core producers such as household presence and declared
context (`core_producer_id` + `implementation_version`, L2 §2.8.1, §2.9), semantic resolvers
(`resolver_kind_id` + `implementation_version`, L4 §4.1–§4.2), Layer-3 analysis vs serving
identity (L3 §4.1.2) [L3-ANALYSIS-SERVING-IDENTITY], Reaction configuration generations (L5 §4.2).
Upstream changes propagate through the dependency index, not by nesting fingerprints.

### 6.3 Fact value contracts

Every state claim has one staging-time `FactValueContract`: `boolean`, `categorical` (closed
vocabulary), `numeric` (canonical unit) or `structured` (core-registered schema id) (L1 §3).
Producers derive it (L2 §2.3; L4 output templates; L7 claims) and every consumer binding is
validated against it at staging. It is never read from a runtime value and adds no field to
`HouseFact`. A change of kind, vocabulary, unit or schema is `breaking`.

- Mappings produce `boolean` or `categorical` only; "no value" is `NO_DEFAULT` (unavailable), never
  `None` (L2 §4).
- Formulas declare their output contract from configuration and non-self input contracts before
  validation; self-memory receives the declared contract (L2 §5.3). A validator reads staged
  metadata only through its `StagedFormulaInput`s and a frozen Topology view; the resolved plan
  enters the rule's fingerprint (L2 §5.3, §2.5).
- `structured` facts (`household.guest_stay.v1`, `household.planned_absence.v1`) cannot be fused
  and are bound only by exact schema id (L2 §2.9).

### 6.4 Claims, producers and identity

- **One state producer per `(fact_type, Location)`**, checked at composition; global
  `FactTypeClaim`s reserve namespaces and owners (L2 §2.3; L0 §4) [L0-STATE-HISTORY].
- **Event producers declare exact places.** Each event-claim owner declares a finite set of
  `EventProducerDeclaration(fact_type, where, owner_id)` from its staged configuration. Event
  consumers must resolve to one; an append at an undeclared place is rejected (L0 §4)
  [L0-FACT-CLAIMS].
- **Per-source fact families** use the producer's stable Heima id as suffix, never an HA entity id:
  `occupancy.evidence.person.<ha_person_id>`, `appliance.cooking_heat_source_active.<id>`,
  `actuator.channel_state.<digest>`, `reaction.decision.<digest>` (L1 §3; L2 §2.8.1, §3;
  L0 §5.1.1.1; L5 §5.2).
- `FactIdentityKey` (WHAT + WHERE) is the state identity; events have none (L0 §4.0).

### 6.5 Availability and suppression

- `available=False` means the producer cannot form an assertion; its value is undefined and never
  replaced by a stale one (L1 §4.1; L2 §3.2).
- Absence of an optional signal is absence of evidence, never a negative assertion (L4 §3).
- When an automation cannot act, its owner (L3, L4 or L5) emits a typed
  `AvailabilitySuppressionOccurrence` only when an episode starts, its canonical reason set changes,
  or it ends. Layer 6 decides visibility and delivery (L3 §6.3.1; L6 §9.2)
  [L3-AVAILABILITY-SUPPRESSION, L6-AVAILABILITY-PUBLICATION].
- A removed, disabled or invalidated state producer emits one terminal unavailable fact so no
  stale available conclusion stays latest (L4 §8; L5 §5.2).

### 6.6 Provenance and causality

Every `HouseFact` and `ApplyStep` carries a non-forgeable `FactSource`/`ApplyStepSource`: closed
`kind` (fact-only: sensor, analyzer, extension, semantic_resolver; shared/action: reaction,
admin_command, user_response, timeout, recovery, system…), `source_id`, actor type and
`correlation_id`. Trust is derived from the runtime path, never stored; an extension never has an
action kind. Following one `correlation_id` explains "why is the house in this state" (L0 §5,
§5.1, §5.2) [L0-FACT-SOURCE]. Authenticated answers enter through one response ingress that routes
to the registered owner (L0 §5.1.3) [L0-RESPONSE-INGRESS].

### 6.7 History, coverage and continuity

- **Two tiers.** A durable store for learning/audit and an in-memory short-term buffer for the hot
  path; a tiny `PreviousCycleSnapshot` holds declared `previous_cycle` keys (L0 §4.1).
- **Frozen views.** Consumers declare `HistoryViewRequirement`s at staging; each cycle gets a
  `FrozenHistoryView` captured at the barrier, never the mutable buffer (L0 §4.1)
  [L0-FROZEN-HISTORY].
- **Honest coverage.** Every declared durable read carries retention coverage and a typed
  `ObservationCoverage`. Its closed gap reasons are `process_interruption`,
  `clock_discontinuity`, `queue_overflow`, `required_stream_unavailable` and
  `continuity_metadata_unknown`; a Layer-2 `max_source_age` expiry between cycles is recorded as a
  known break too. A window crossing a gap is incomplete, never zero-event evidence (L0 §4.3–§4.4,
  §4.6) [L0-RETENTION, L0-OBSERVATION-COVERAGE, L0-RETRY-QUEUE].
- **Bounded storage.** Retention floors per type, a 50,000-record per-type ceiling, a 512 MiB
  global pruning watermark that never drops a latest state, and a bounded retry queue
  (`max(32 MiB, 5% of memory)`) with declared loss and progressive baseline recovery (L0 §4.3,
  §4.6).

### 6.8 Time

- One instant form across all contracts: Layer 1 `EvidenceInstant`, canonical UTC with six
  fractional digits and `+00:00`. One duration form: Layer 0 `Window` in canonical seconds. Civil
  weekday/hour/minute exist only where a contract declares local time (L0 §3; L1 §4)
  [L1-EVIDENCE-INSTANT, L0-WINDOW].
- `AtJob` is the one execution primitive; `CronEntry` is interval-only in Initial V3; each job
  declares an `elapsed` or `wall_clock` basis (L0 §3.1) [L0-TIMING].
- Cycle instants strictly increase; a clock jump over 1 s re-arms `wall_clock` jobs and records a
  `clock_discontinuity` gap (L0 §3.5).

## 7. The layers

### Layer 0 — Runtime facilities

**Purpose.** Shared runtime machinery outside the semantic DAG; nothing in L2–L5 depends on a
Layer-0 facility changing mid-cycle (L0 §1).

**Owns.** Timing; two-tier persistence, continuity metadata and the notification outbox; the
`FactSource` vocabulary; the Divergence Hold Manager; Recovery/Checkpoint; runtime-health
telemetry; composed generations; committed-state observers.

**Key mechanisms.**

- *Holds.* One process-local divergence hold per Actuator channel when a valid observation
  diverges from a confirmed Reaction target; release is chosen by the descriptor (Layer 5); no hold
  survives restart (L0 §6) [L0-HOLD-ORIGIN, L0-HOLD-AUDIT].
- *Manual control.* A trusted manual-control edge joins the bounded `actuator.channel_state`
  stream and the redacted `actuator.manual_control` event with a coarse `ControlActor`
  (L0 §5.1.1–§5.1.1.1) [L0-MANUAL-CONTROL, L0-CHANNEL-STATE]. Managed-episode proof lets a
  registered program resume after restart (L0 §5.1.1.2) [L0-MANAGED-EPISODE].
- *Recovery.* Layer 2 pushes a `RecoveryObservationSet` at every generation cutover; Layer 0
  classifies `startup_recovery`, `degraded_recovery`, `power_recovery`, `recovery_settling`,
  `normal` with a fixed precedence, mints a recovery episode on power evidence, and reconciles once
  after `normal` against a read-only per-facet baseline — never a command replay. A member that
  changed during downtime is labelled `unknown_during_downtime` or `power_restore_candidate`, never
  evidence of a manual action (L0 §7.1–§7.4)
  [L0-RECOVERY-CLASSIFICATION, L0-CHECKPOINT, L0-RECOVERY-BASELINE]. A recovery target that needs
  confirmation opens one bounded request per channel (L0 §7.4.1) [L0-RECOVERY-CONFIRMATION].
- *Calendar.* Layer 0 extracts raw calendar windows into a normalized cache with
  consumer-declared upcoming horizons and serves `active_now`/upcoming reads; classifying their
  text is Layer 2's `CalendarInterpretation` (L0 §3.4–§3.4.1).
- *Warm-up.* `WarmupGate` requires both a time floor and a sample floor per learning subject
  (L0 §3.3).
- *Unavailability.* An unavailable Actuator channel is an observation break: never `off`, a manual
  edge, a resident response or a failed action. Intervals containing it are interrupted, not
  negative evidence (L0 §5.1.2).
- *Clean shutdown.* A single-use `CleanShutdownMarker` lets the next bootstrap pre-hydrate the
  declared `previous_cycle` keys; otherwise that snapshot starts empty (L0 §4.1).
- *Outbox.* One durable store for every notification: `ready` commits with its audit fact;
  delivery transitions follow (L0 §4.5) [L0-NOTIFICATION-OUTBOX].
- *Health.* Read-only capability and resource snapshot for slow-path admission; a runtime error
  condition raises `system.health` (L0 §9, §10.1) [L0-RUNTIME-ERROR]. Failure handling: L0 §8
  [L0-FAILURE].

**Invariants.** No semantic resolver depends on Layer 0 mid-cycle; Layer 0 never names a fact's
meaning (it receives declared sets); no hot-path disk read; every retained payload is a complete
fact or a bounded `PersistedProjection` (depth 2, 8 KiB) (L0 §4.1, §11).

### Layer 1 — Substrate

**Purpose.** Make every durable assertion answerable as WHAT, WHERE, WHEN and HOW (L1 §1).

**Key types.**

- `HouseFact(fact_type, value, where: Location, when: EvidenceInstant, how: Provenance)` — the only
  persistent assertion shape, for house state and auditable operational occurrences
  [L1-HOUSE-FACT-TIME]. Artifacts, signals, candidates, proposals and `ApplyStep`s keep their own
  contracts (L1 §2.2).
- `Provenance(confidence, source, available, evidence)`; per-strategy confidence is mapped in
  L2 §5.4 (L1 §4) [L1-CATEGORICAL-CONFIDENCE, L1-EVIDENCE-FAILURE].
- `FactValueContract` (§6.3 above).
- `OperationalEventValue` for notification events: closed fields and identifiers, never text
  (L1 §3.1) [L1-OPERATIONAL-EVENT].
- `Location` (`casa`, `room`, `zone`, `rooms`) [L1-LOCATION]; `Zone` (admin-declared room group,
  closed core roles such as `thermal_envelope`) [L1-ZONE-ROLES]; `Topology` (physical relations:
  enclosure, opening sides, passages, orientation, floor) [L1-TOPOLOGY]; Zone suggestions derive
  from Topology (L1 §5–§7.1).

**Invariants.** Deep immutability [L1-DEEP-IMMUTABILITY]; one numeric domain (non-boolean ints
within ±(2^53−1), finite binary64 floats) [L1-NUMERIC-DOMAIN]; value and evidence bounded to depth 2
and 8 KiB; invalid value rejects, invalid evidence is dropped with a diagnostic (L1 §3–§4).

### Layer 2 — Registries

**Purpose.** The only HA ingress and the current-cycle fusion layer (L2 §1).

**Key types and registries.**

- `Room` registry (floor, enclosure; area link is metadata) [L2-ROOM-REGISTRY]; presentation names
  outside fingerprints [L2-PRESENTATION-NAMES] (L2 §2.6–§2.7).
- `Person` (resident or guest, HA user link) [L2-PERSONS]; per-person evidence and the
  `presence.household` fusion [L2-HOUSEHOLD-PRESENCE]; declared context
  `household.guest_stay` / `household.planned_absence` from calendars and panel declarations
  [L2-DECLARED-CONTEXT]; security and opening state facts [L2-SECURITY-STATE] (L2 §2.8–§2.10).
- `Sensor` = one `ReadBinding` + one `Interpretation` + fact type + `Location` (+ recovery
  observation role) [L2-TYPED-STATE-INGRESS]. Interpretations are closed: mapping, numeric,
  bucket, calendar (with `KeywordClassifier`). Source-shape and unit drift are
  diagnosed [L2-QUANTITATIVE-UNITS]; core solar geometry uses the same path [L2-SOLAR-GEOMETRY] (L2 §3–§4).
- `FusionRule` with a closed strategy: direct, unanimity, weighted quorum, precedence, formula.
  Stability (dwell, unavailable grace) is orthogonal to strategy [L2-FUSION-STABILITY]. Formulas
  come from a frozen core registry with semantic versions: numeric hysteresis
  [L2-NUMERIC-HYSTERESIS], numeric difference [L2-NUMERIC-DIFFERENCE], environmental
  [L2-ENVIRONMENTAL-FORMULAS], `physical_evidence.weighted_evidence` for occupancy
  [L2-PHYSICAL-EVIDENCE-FORMULA]. Only a formula may read its own previous-cycle value (L2 §5).
- Fusion inputs may be other `FusionRule` outputs addressed by `(fact_type, Location)`; each
  strategy defines how unavailable inputs and source vs destination locations are handled
  (L2 §5.5–§5.7).
- `Actuator`: inventory only (entity, location, optional opening, open role string used only as a
  hint, exterior exposure, `power_recovery_policy` `reconcile | never | require_confirmation`);
  never a command. Each logical channel binds a closed core channel kind, observable-state
  contract and actuation adapter (L2 §6–§6.1) [L2-ACTUATOR-CHANNEL, L2-ACTUATOR-EXPOSURE].
- Registration-time validation rejects invalid numbers and cardinalities; nothing is clamped or
  repaired later (L2 §2.4). HA metadata may only suggest ephemeral staging candidates
  (`EnvironmentalDiscoveryCandidate`), never create a Sensor or a runtime path (L2 §3.4).
- Desktop workstations are ordinary opt-in Sensors producing bounded normalized facts
  (`computer.*`); raw window titles, documents, URLs or unclassified application names never
  become facts, and computer activity alone never proves work (L2 §3.5).

**Invariants.** No blocking I/O in the hot path (L2 §2.2); one state producer per
`(fact_type, Location)`; fusion DAG is acyclic; extensions add producers only through Layer 7
(L2 §2.1) [L2-EXTENSION-BOUNDARY].

### Layer 3 — Learning

**Purpose.** Answer bounded statistical questions from history; produce evidence and candidates,
never authority (L3 §1–§2).

**Key mechanisms.**

- `LearningDefinition` from a core learning-type registry; one admin toggle per family covers
  analyzer and live signal (L3 §4.1) [L3-LEARNER-SCOPE, L3-EXTENSION-BOUNDARY].
- `SampleBinding`: typed anchors, causal window features and outcomes over declared streams;
  requiredness and household-context censoring (behavior samples are censored while the house is
  occupied without residents and, during a guest stay, in guest rooms; physical learning continues) (L3 §4.2) [L3-SAMPLE-TIME, L3-CAUSAL-WINDOW, L3-REQUIREDNESS-SCOPE,
  L3-HOUSEHOLD-CENSORING, L3-FUTURE-STATE-FRACTION].
- Sample kinds: anchors `IntervalAnchor`, `StateTransitionAnchor`, `EventOccurrenceAnchor`;
  features `AsOfStateFeature`, `CausalAggregateFeature`, `CausalSequenceFeature`; outcomes
  `PointOutcome`, `EventWindowOutcome`, `TimeToEventOutcome`, `FutureStateFractionOutcome`,
  `NoOutcome` (L3 §4.2).
- `PatternLearner`: buckets, `min_support` gate, warm-up, standard confidence, tier fallback; a
  core, frozen `ContextTransformRegistry` canonicalizes features into tier keys (L3 §4.3). Registered models: room-return survival [L3-ROOM-RETURN-SURVIVAL], correction-count
  hurdle [L3-CORRECTION-COUNT], routine pattern [L3-ROUTINE-PATTERN, L3-ROUTINE-BASELINE,
  L3-ROUTINE-OUTPUT, L3-ROUTINE-GATES], indirect semantic assist
  [L3-INDIRECT-PHYSICAL-REFERENCE], environmental episodes [L3-ENVIRONMENTAL-ANCHOR,
  L3-ENVIRONMENTAL-OUTPUT, L3-ENVIRONMENTAL-GATES, L3-GUARD-CANDIDATE] including
  `EnvironmentalQuantileResponseModel` and the evidence-gated `hvac_thermal_response` contract;
  `ContextRegimeNoveltyModel` is an unsupervised, diagnostic-only novelty detector (L3 §4.4,
  §4.8). Result contracts: [L3-RESULT-TIME, L3-EVIDENCE-RANGE].
- Adaptation: each learner declares a `seasonality_mode` and records an `operating_envelope`;
  runtime use abstains outside it. Artifact adoption is `pinned` (each revision approved) or
  `bounded_adaptive` (within approved bounds) (L3 §4.9). Refresh is evidence-driven
  (`inspection_interval`, `min_new_eligible_evidence`, `training_window`) (L3 §5.1–§5.2).
- Retired or inactive: composite `house_state` learning is retired; `ContextHypothesisCandidate`
  has no active kind; V2 families are re-specified, never ported, and `presence_preheat` is not
  ported (L3 §4.4.6–§4.4.7, §7).
- Optional ML under the same lifecycle (validation, shadow, KPIs, drift); runtime-health-driven
  admission and slow-path work classes (L3 §4.6–§4.7, §5.3) [L3-SLOW-PATH-CLASSES,
  L3-HEALTH-BASELINE].

**Outputs and authority** (L3 §6) [L3-SIGNAL-EGRESS, L3-PROPOSAL-EFFECT, L3-REACTION-ENVELOPE,
L3-REACTION-HANDOFF, L3-EGRESS-ARTIFACT-ADOPTION]:

| Output | Consumer | Boundary |
|---|---|---|
| `DiagnosticFinding`, `ShadowProposalPreview` | Administrator diagnostics | Never a fact, command or notification |
| `InferenceSignal` (`indirect.semantic_assist.v1` only) | One authorized Layer-4 resolver | Transient, expiring, positive evidence only |
| `LearningProposalCandidate` | Layer 5 | Evidence for review; Layer 5 validates independently |
| `AvailabilitySuppressionOccurrence` | Layer 6 tracker | Typed transition only |

**Invariants.** Off the hot path except bounded signal serving; never trains on truncated or
incomplete required history; results are not `HouseFact`s; no V2 model migration.

### Layer 4 — Semantic resolution

**Purpose.** Resolve named semantic claims from current facts and one authorized learning hint;
the only place where facts become current conclusions (L4 §1).

**Key types.** `SemanticResolverRegistry` (core, frozen; one `implementation_version` per kind)
[L4-SEMANTIC-CONTRACTS]; `SemanticResolverDefinition` → staged `ResolvedSemanticResolver` with
execution and definition fingerprints [L4-RESOLVER-SCOPE]; `SemanticState` (current value at one
scope) and `SemanticEpisode` (declared occurrence, no latest value); `DecisionSnapshot`
[L4-DECISION-SNAPSHOT] (L4 §3–§5).

**Cycle rules.** Resolvers read only declared lower facts, declared upstream claims, one optional
signal slot, parameters and declared previous-cycle values; topological order with `resolver_id`
tie-break; no history, HA, policy or global fact map. Signals pass the gateway only on exact kind,
claim parameters, scope and `emitted_at <= when < expires_at` (L4 §5–§6) [L4-SIGNAL-GATEWAY].
Reload invalidates impacted resolvers and emits terminal unavailable facts (L4 §8) [L4-RELOAD].

**Initial-V3 claims** (L4 §9):

| Resolver kind | Claim | Values | Notes |
|---|---|---|---|
| `room_occupancy` | room `occupancy` | `present`/`absent` | from `occupancy.physical`; optional positive signal |
| `casa_occupancy` | casa `occupancy` | `present`/`absent` | deterministic [L4-CASA-CLAIMS] |
| `presence` | casa `presence` | `home`/`away` | household residents; deterministic |
| `occupied_without_residents` | casa boolean | — | from the two claims above |
| `activity` | room `activity.<id>` | profile-defined | profiles `cooking`, `sleeping`, `relax`, `working` [L4-ACTIVITY-SLOTS] |

Two transition-episode adapters emit `occupancy.departure/return` and `presence.departure/return`
[L4-CASA-EPISODES]. There is no global `house_state`; planned absence and guest stay are declared
Layer-2 facts, not claims.

### Layer 5 — Action and reaction

**Purpose.** Turn resolved claims into permitted action through one descriptor mechanism (L5 §1).

**Key mechanisms.**

- `ReactionDescriptorRegistry` (core, frozen, versioned). A descriptor allows `admin_direct`,
  `learner_proposal` or both; both origins compile the same `ReactionEvaluationPlan` and use the
  same evaluator and `ApplyStep` protocol (L5 §3) [L5-SCOPE-BOUNDARIES, L5-DESCRIPTOR-PLAN,
  L5-EFFECT-BUNDLE]. `ProposalCandidateKindRegistry` holds `reaction.descriptor` v1 and
  `reaction.artifact_adoption` v1 [L5-PROPOSAL-CANDIDATE-KINDS].
- Relation profiles narrow a descriptor for learned use [L5-RELATION-PROFILES]; guards use one
  frozen capability registry and household guard-profile generations [L5-REACTION-GUARDS]; program
  families (`planned_absence_program`) and managed resumption are written once
  [L5-PROGRAM-FAMILY, L5-MANAGED-RESUMPTION] (L5 §3.1–§3.2).
- `ReactionProposal`: persisted review record with evidence snapshot [L5-PROPOSAL-SUPPORTING-EVIDENCE,
  L5-PROPOSAL-EVIDENCE-SOURCE]; acceptance stages a `ConfiguredReaction` in `notification_only`
  (L5 §4.1). `ConfiguredReaction`: stable id, append-only configuration generations; authorization
  and resident consent are separate authority transitions [L5-REACTION-AUTHORITY]; timing-model and
  artifact adoption are recorded separately [L5-TIMING-MODEL-BINDING,
  L5-REACTION-ARTIFACT-ADOPTION] (L5 §4.2).
- Evaluation reads only the `DecisionSnapshot` and declared windows; closed relational vocabulary,
  state transitions and program starts [L5-HISTORY-READ, L5-STATE-TRANSITION, L5-PROGRAM-START]
  (L5 §5.1). One pure `evaluate_program` per descriptor version [L5-PROGRAM-EVALUATOR].
- Admissibility and execution: shared hold and command-ownership admission, one next-step `AtJob`
  slot per activation [L5-STEP-SLOT, L5-STEP-HOLD], trigger-driven delay slot and bounded
  learned-delay selection [L5-TRIGGER-DELAY-SLOT, L5-FRACTION-DELAY-SELECTOR, L5-ROOM-RETURN-DELAY,
  L5-DELAY-GAP-SEMANTICS, L5-TRANSLATION-DELAY-PERMISSION]; members are commands or advice
  [L5-MEMBER-DELIVERY]; correction attribution evidence [L5-TARGET-EVIDENCE] (L5 §6).
- `PendingApply` tracks each dispatched `ApplyStep`: a core, versioned confirmation window and
  matcher confirm the physical outcome; a target already satisfied at the final check sends no
  call (L5 §6.0.1).
- Typed occurrences to Layer 6: follow-up, advisory (with feedback), action notice, proposal
  review, consent request, recovery confirmation proposal (L5 §6.0). Governance commands share one
  Layer-8 command surface (L5 §4.2). A household plan is read as the Layer-2
  `household.planned_absence` fact by its exact schema; a policy never binds a calendar itself
  (L5 §5.1).
- Audit: decision state `reaction.decision.<digest>` [L5-DECISION-RECORD]; diagnostic registry,
  governance results, execution audit [L5-DIAGNOSTIC-REGISTRY, L5-GOVERNANCE-RESULT,
  L5-EXECUTION-AUDIT]; recovery confirmation proposals [L5-RECOVERY-CONFIRMATION-PROPOSAL].

**Initial-V3 catalog** (L5 §7.3) [L5-CATALOG-MATRIX]:

| Descriptor | Origins | Program |
|---|---|---|
| `environment.solar_shading` [L5-SOLAR-SHADING] | direct, learned | trigger-driven |
| `environment.external_exchange` | direct, learned | trigger-driven |
| `environment.air_extraction` [L5-AIR-EXTRACTION] | direct, learned | step-programmed |
| `routine.actuation_bundle` [L5-ROOM-VACANCY-ROUTINE] | direct, learned | trigger-driven |
| `environment.planned_comfort_trajectory` [L5-COMFORT-TRAJECTORY] | learned only, evidence-gated | step-programmed, `planned_absence_program` |
| `security.presence_simulation` [L5-PRESENCE-SIMULATION] | direct only | step-programmed, `planned_absence_program` |
| `safety.weather_protection` [L5-WEATHER-PROTECTION] | direct only | step-programmed per hazard |
| `safety.posture_check` [L5-POSTURE-CHECK] | direct only, advice only | trigger-driven |

Seven of the eight require resident consent; `safety.posture_check` does not. A protective action
is never undone by another automation: every action that would undo it uses the hazard as its
guard (L5 §7).

**Invariants.** One evaluator and one action protocol; an `ApplyStep` addresses exactly one logical
Actuator endpoint and retains its configuration generation; the whole bundle passes admissibility
before execution; a learned result never expands its approved scope; Layer 7 has no action
authority.

### Layer 6 — Notification

**Purpose.** The one path for pushed notifications, built on HA infrastructure (L6 §1, §3).

**Kinds** (closed, frozen; one audited event fact per phase, no stored text) (L6 §4.2)
[L6-NOTIFICATION-KINDS]: `reaction.follow_up`, `automation.availability`, `reaction.advisory`,
`reaction.action_notice`, `recovery.confirmation_request`, `reaction.consent_request`,
`proposal.review_pending`, `system.health`.

**Key mechanisms.** Recipients and audiences (`residents`, `administrators`,
`consent_authorities`, `house`) [L6-RECIPIENTS, L6-AUDIENCES]; per-person preferences outside the
generation [L6-RECIPIENT-PREFERENCES] (L6 §5). Families `safety`, `attention`, `suggestion`,
`governance` from closed per-namespace tables [L6-FAMILIES]; quiet hours from the casa
`quiet_hours.active` fact (safety bypasses) [L6-QUIET-HOURS]; proposal and advisory digests
[L6-DIGESTS] (L6 §6). Delivery via `notify.*`, retries, one `persistent_notification` fallback,
tags and clearing [L6-DELIVERY]; answers via mobile actions to Layer 0's ingress [L6-RESPONSES]
(L6 §7). `notification_key` is kind + operation id; there is no time-based deduplication, and
items may retire undelivered only by explicit rule (L6 §7.5–§7.6). Each delivery also fires one
`heima_notification` bus event (L6 §7.8). Text rendered at delivery in the recipient's locale
[L6-RENDERING] (L6 §8). After restart the scheduler is rebuilt from the outbox (at-least-once,
replaced on the phone by tag) (L6 §11). The Layer-6
generation holds availability publication bindings, recipients, house endpoints and family options
[L6-GENERATION, L6-AVAILABILITY-PUBLICATION] (L6 §9.2, §10).

**Invariants.** Typed inputs only; never silent by misconfiguration; delivery never blocks a cycle;
delivery preference is not authority.

### Layer 7 — Extensions

**Purpose.** A boundary for first-party, in-repository extensions; no external code is discovered
or loaded (L7 §1–§2) [L7-SCOPE].

**Key mechanisms.** Closed, bootstrap-frozen blueprint registry [L7-REGISTRY]; administrator
instances staged as a Layer-2 producer or Layer-3 analyzer [L7-INSTANCES]; inputs are declared
non-person facts and bound learners' results [L7-INPUTS]; outputs are `ext.<extension_id>.*`
claims, diagnostics and candidates under existing kinds [L7-OUTPUTS]; pull-only off the cycle, at
most once per 60 s [L7-INVOCATION]; a failed run is discarded and stale facts expire
[L7-FAILURE, L7-LIFECYCLE]. Third parties need the reopening conditions of L7 §11
[L7-REOPENING].

**Invariants.** No `ApplyStep`, Actuator call, descriptor or candidate kind; never runs in the cycle.

### Layer 8 — Administration

**Purpose.** One Heima panel for every configuration, review and diagnostic, by role (L8 §1–§3).

**Key mechanisms.** Roles resolved server-side (administrator from HA's flag, resident from the
Layer-2 `Person`) [L8-ROLES]; text registers and resident-data visibility [L8-TEXT-REGISTERS]
(L8 §4). Navigation, addresses, panel states, accessibility, Extensions section [L8-PANEL-ADDRESSES,
L8-PANEL-STATES, L8-ACCESSIBILITY, L8-EXTENSIONS] (L8 §5). Session change set → preview → atomic
apply; governance actions are immediate [L8-CHANGE-SET, L8-PREVIEW-APPLY]; configuration
suggestions [L8-SUGGESTIONS] (L8 §6). History and restore as a new change set
[L8-HISTORY-RESTORE]; "Why?" explanations from durable records [L8-EXPLANATIONS] (L8 §7–§8).
Native house map with control scope and Lovelace card [L8-HOUSE-MAP, L8-CONTROL-SCOPE,
L8-MAP-CARD] (L8 §9). Read-only published HA entities fed by observers and owner projections
[L8-PUBLISHED-ENTITIES, L8-PROJECTIONS] (L8 §10). Guided first start; `en` and `it`
[L8-LANGUAGES] (L8 §11–§12). Typed websocket backend [L8-BACKEND]; downloadable diagnostics
[L8-DIAGNOSTICS-EXPORT] (L8 §13–§14).

**Invariants.** The panel owns no configuration meaning, validation, authority or decision; it
sends typed commands to the owning layer and never runs in an evaluation cycle. Holds have no
manual clear action.

## 8. Technology choices already fixed

- **Typed immutable contracts:** immutable records, closed vocabularies, explicit versions and pure
  validators; no untyped generic event bus.
- **Staged immutable generations:** validated before atomic activation; the engine reads frozen
  O(1) indexes.
- **No blocking I/O in the hot path:** HA is read only at Layer 2's binding boundary; learning,
  persistence maintenance, probing and delivery never block evaluation.
- **Two time scales:** synchronous per-cycle work; slow or background learning, pruning,
  reconciliation and delivery.
- **Canonical identity:** stable keys, explicit versions, RFC 8785 canonical JSON.
- **Bounded storage and work:** declared retention, hard per-type ceilings, a global pruning
  watermark, explicit learning capacities, admission from measured runtime health.
- **Clean V3 start:** nothing from V2 enters a V3 runtime path.
- **HA infrastructure for notifications:** `notify.*`, mobile actions, `persistent_notification`.

The specifications do not select a database engine, ML framework or external training protocol;
implementation choices must honour the contracts above (implementation decisions are recorded in
the implementation worktree).

## 9. Gated, deferred and out of scope

- **Gated per household:** `environment.planned_comfort_trajectory` needs validated thermal
  evidence, the notification-only shadow, authenticated promotion and current consent
  (L5 §7.1). `security.presence_simulation` is a deterrence aid, never a security guarantee
  (L5 §7.2).
- **Deferred:** third-party extension loading and a public extension API (L7 §11); further
  semantic claims (quiet/sleep context, identity inference, occupant counting, learned absence,
  HVAC control, security policy) each need their own contract (L4 §9); weekly cron (L0 §3.1).
- **Out of scope:** per-person learning (Heima learns at household level); push-model extensions;
  V2 migration.
- **Each specification's "Not yet decided" section** lists its remaining open points (L0 §12,
  L1 §9, L2 §8, L3 §8). Open CA4 issues: `python3 scripts/check_v3_specs.py --open`.

## 10. Implementation reading checklist

Before implementing a component, answer in order:

1. Is it a durable assertion about the house? Use a Layer-1 `HouseFact` persisted by Layer 0.
2. Is it a current HA observation or a fusion of observations? Layer 2.
3. Does it need history, support and bounded statistical evidence? Layer 3, off the hot path; only
   bounded serving of an adopted live signal runs in the cycle.
4. Is it a current semantic decision? Layer 4, not a learner or a policy.
5. Does it create, approve, evaluate or execute an action? Layer 5.
6. Does it render or deliver a message to people? Layer 6.
7. Does it present, edit or explain configuration, decisions or state? Layer 8, through typed
   commands to the owning layer.
8. Would it add a second representation, registry, scheduler, action engine or callback path?
   Reuse the existing typed mechanism unless the shared contract cannot express the requirement
   without weakening meaning, safety or hot-path performance.

## 11. Glossary

| Term | Meaning | Owner |
|---|---|---|
| `ApplyStep` | One ordered command to one logical Actuator endpoint | L5 §6 |
| `AtJob` / `CronEntry` | One-shot deadline / interval recurrence above it | L0 §3.1 [L0-TIMING] |
| `CanonicalEnvelope` | The context cells where a Reaction may act | L3 §6.5 [L3-REACTION-ENVELOPE] |
| `ComposedGenerationManifest` | Atomic record of one composed configuration generation | L0 §4.7 [L0-COMPOSED-GENERATION] |
| `ConfiguredReaction` | Staged policy with configuration generations and authority state | L5 §4.2 [L5-REACTION-AUTHORITY] |
| `CycleInputBarrier` | Closes one cycle's intake; frozen views are captured at it | L0 §4.1 [L0-FROZEN-HISTORY] |
| `DecisionSnapshot` | Immutable input to Layer 5 for one cycle | L4 §5.1 [L4-DECISION-SNAPSHOT] |
| `EventProducerDeclaration` | Exact `(fact_type, where, owner)` an event producer may emit | L0 §4 [L0-FACT-CLAIMS] |
| `EvidenceInstant` | The one canonical UTC instant form | L1 §4 [L1-EVIDENCE-INSTANT] |
| `FactIdentityKey` | WHAT + WHERE identity of a state fact | L0 §4.0 [L0-STATE-HISTORY] |
| `FactSource` / `ApplyStepSource` | Non-forgeable provenance of facts and actions | L0 §5 [L0-FACT-SOURCE] |
| `FactValueContract` | Staging-time type of a state claim | L1 §3 |
| `FrozenHistoryView` | Declared short-term history frozen at the barrier | L0 §4.1 [L0-FROZEN-HISTORY] |
| `FusionRule` | Combines current facts into one derived fact | L2 §5 [L2-FUSION-STABILITY] |
| `HouseFact` | The one persistent assertion shape | L1 §3 [L1-HOUSE-FACT-TIME] |
| `InferenceSignal` | Transient learned hint to one authorized resolver | L3 §6.3 [L3-SIGNAL-EGRESS] |
| `LearningProposalCandidate` | Learned evidence handed to Layer 5 for review | L3 §6.4 [L3-PROPOSAL-EFFECT] |
| `ObservationCoverage` | Typed completeness of a historical read | L0 §4.4 [L0-OBSERVATION-COVERAGE] |
| `ReactionDescriptor` | Core contract a `ConfiguredReaction` is staged from | L5 §3 [L5-DESCRIPTOR-PLAN] |
| `ReactionProposal` | Persisted review record for a learned candidate | L5 §4.1 [L5-PROPOSAL-SUPPORTING-EVIDENCE] |
| `RecoveryObservationSet` | Layer-2-declared members used for recovery classification | L0 §7.1 [L0-RECOVERY-CLASSIFICATION] |
| `SampleBinding` | Typed historical sample definition of a learner | L3 §4.2 [L3-SAMPLE-TIME] |
| `SemanticResolverDefinition` | Administrator instance of a core resolver kind | L4 §4.2 [L4-RESOLVER-SCOPE] |
| `Sensor` | One HA read binding interpreted into one typed fact | L2 §3 [L2-TYPED-STATE-INGRESS] |
| `Window` / `LearnedWindow` | Canonical duration / self-calibrating duration | L0 §3.2 [L0-WINDOW] |
