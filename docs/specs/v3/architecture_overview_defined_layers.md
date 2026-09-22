# Heima v3 - Architecture Overview of Defined Layers

**Status:** Explanatory reconciliation document. It does not replace the authoritative layer
specifications and introduces no new implementation requirement.

**Scope:** Layers 0, 1, 2, 3, 4, and 5 are defined in detail today. Layer 6 appears only where an
already-defined layer has a deliberately narrow future interface to it. Layers 7 and 8 are outside this
document.

## 1. Purpose and Reading Order

This document is the architectural map of the V3 work completed so far. It answers four practical
questions:

1. Which layer owns each kind of data, decision, and side effect?
2. Which paths are synchronous engine work, and which are slow/background work?
3. Which cross-layer communications are allowed, and which are deliberately forbidden?
4. Which decisions are already fixed before Layer 6 and the remaining layers are specified?

The authoritative sources remain:

- [Layer 0 - Cross-Cutting Runtime Facilities](layer0_runtime_spec.md)
- [Layer 1 - Substrate Primitive](layer1_substrate_spec.md)
- [Layer 2 - Registries](layer2_registries_spec.md)
- [Layer 3 - Learning / Pattern Recognition](layer3_learning_spec.md)
- [Layer 4 - Semantic Resolution](layer4_domain_spec.md)
- [Layer 5 - Action and Reaction Generation](layer5_action_reactions_spec.md)

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

In both diagrams, green components are layers defined so far and orange components are future layers
with already-fixed interfaces. A solid arrow is an owned operational hand-off; a blue dashed arrow is
an immutable contract or staging dependency, never runtime message delivery.

## 3. Responsibility Map

| Layer | Owns | Main outputs | Does not own |
|---|---|---|---|
| 0 | Runtime facilities: time, persistence, provenance source vocabulary, manual holds, recovery, runtime-health measurement | Durable/short-term history, timers, checkpoints, runtime-health snapshot | Fact meaning, registry semantics, learning policy, semantic resolution, actuator commands |
| 1 | Immutable semantic contracts: `HouseFact`, `Provenance`, `Location`, `Zone`, `Topology` | Typed values used by all other layers | Storage mechanics, HA reads, fusion, learning, commands, workflow records |
| 2 | Composition-time registry generation; HA read bindings; interpretations; fact fusion; formula registry; actuator inventory | Typed sensor/fused `HouseFact`s and logical Actuator descriptions | Durable storage, historical learning, semantic resolution, policy evaluation, action execution |
| 3 | Historical analysis; shared statistical lifecycle; optional ML governance; artifacts; findings; typed signals and learned candidates | `DiagnosticFinding`, `InferenceSignal`, `LearningProposalCandidate`, typed availability suppression occurrences | Fact persistence, HA access, semantic-claim resolution, policy approval, commands, notification rendering |
| 4 | Core semantic-resolver registry; staged semantic DAG; authorized signal gateway; current semantic-claim resolution | Resolved semantic `HouseFact`s, completed immutable `DecisionSnapshot`, typed availability suppression occurrences | HA reads, historical learning/model lifecycle, policy/guard/envelope evaluation, Actuator commands, notification delivery |
| 5 | Candidate validation/review; configured policy staging; policy evaluation; action admissibility; `ApplyStep` generation | `ReactionProposal`, configured policy, ordered one-endpoint `ApplyStep`s, typed suppression occurrences | HA read bindings, raw state interpretation, historical learning, notification delivery |

## 4. Foundation: Layers 0 and 1

Layers 0 and 1 form a deliberately small foundation slice. Their relationship is reciprocal only for
immutable value contracts: Layer 0 persists Layer-1 `HouseFact` values, while Layer-1 `Provenance`
contains Layer-0 `FactSource`. Neither layer calls the other layer's behavior during an engine cycle.
This prevents a language-level import convenience from becoming an architectural behavior cycle.

### Layer 0: Runtime Facilities

Layer 0 standardizes the machinery every higher layer needs:

- **Timing:** `AtJob` is the one execution primitive; `CronEntry` is the recurrence policy above it.
  Instants are timezone-aware UTC. Local civil time exists only for explicitly local recurrences and
  presentation.
- **Persistence:** accepted facts enter a short-term in-memory history and an ordered durable batch.
  State facts use write-on-change and a `FactIdentityKey`; event facts remain append-only. Durable
  pruning is time-based with a 14-day baseline, per-type retention declarations, a 50,000-record
  per-type ceiling, and a 512 MiB global watermark.
- **Honest history:** retention coverage is stream-scoped. A noisy stream in one room can make its
  own historical interval truncated without falsely degrading the same fact type in another room.
- **Provenance and causality:** Layer 0 owns the non-forgeable `FactSource`/`ApplyStepSource`
  vocabulary and correlation-id propagation rules.
- **Manual control and recovery:** manual holds have an explicit lifecycle and carefully limited
  restart restoration. Recovery restores a prior known target first, then ordinary evaluation may
  change it when current conditions require it.
- **Runtime health:** Layer 0 measures latency, memory, CPU and runtime capabilities. It never
  decides whether a learner may run; Layer 3 consumes the read-only snapshot on its slow path.

Layer 0 reserves `automation.availability` as a Layer-6-owned event fact type. A lower layer may not
append that event directly.

### Layer 1: Semantic Substrate

Layer 1 makes every durable house assertion answerable as WHAT, WHERE, WHEN, and HOW:

- `HouseFact` is the single persistent assertion record for house state and auditable operational
  occurrences.
- `Provenance` carries source, availability, confidence, and bounded evidence. An unavailable value
  is explicitly undefined and cannot be consumed as a stale value.
- `Location`, `Zone`, and `Topology` model place, declared groups, and physical relation separately.
  A Zone is not a Topology edge; a room inventory is referenced, not reimplemented here.
- Canonical JSON follows RFC 8785 where fingerprints or persisted canonical payloads require it.

Layer 1 deliberately excludes artifacts, signals, candidates, commands, and review workflow records
from `HouseFact`. They have different authority and lifecycle, even when they are about the house.

## 5. Layer 2: From Home Assistant to Current Facts

Layer 2 is the semantic ingress and current-cycle fusion layer.

### Main mechanisms

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

- Registry generations are staged, validated, fingerprinted, and atomically swapped.
- State producer uniqueness is checked at composition for `(fact_type, Location)`; global fact-type
  claims protect reserved or dynamic namespaces.
- The current-cycle dependency DAG rejects cycles. `previous_cycle` is explicit and receives a
  bounded Layer-0 snapshot rather than a durable read.
- Interpretations, fusion strategies, and formulas are closed core-owned registries. They are pure,
  synchronous and bounded: no I/O, network, dynamic import, or HA access in the hot path.
- Availability grace and stability transitions are layer-owned state machines that reset selectively
  when a changed generation affects them.

## 6. Layer 3: Historical Learning and Pattern Recognition

Layer 3 is off the engine hot path. It reads only Layer-0 fact history and immutable staged contracts;
it never reads HA runtime objects or a mutable HA payload.

### Shared learning platform

- A learner declares a typed `SampleBinding`, complete `training_window`, feature lookbacks, target
  horizons, supported scope, resource envelope, and allowed egress. Staging derives its per-stream
  retention requirements and registers them one way with Layer 0.
- A learner requiring complete history refuses a truncated interval. It stays warm-up/degraded rather
  than silently learning from a shorter window.
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
| `AvailabilitySuppressionOccurrence` | Future Layer-6 `AvailabilityEpisodeTracker` | Typed availability transition, not a notification, event fact, command, or persistence request |

The proposal path is intentionally one way: learning proposes, Layer 5 reviews, a configured policy
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

## 7. Layer 5: Review, Policy, and Action

Layer 5 is downstream of the Layer-4 semantic DAG. It is outside that DAG and sees one immutable
`DecisionSnapshot` after Layer-2 equal-`when` intake facts have been consolidated behind a cycle
barrier. Its declared short-term windows are served only through the paired Layer-0
`FrozenHistoryView`; it never rereads HA, durable history, or a later mutable state while deciding an
action.

### One policy mechanism

- The core-owned, frozen `PolicyTemplateRegistry` supplies one evaluator, one configured-policy
  persistence path, one admissibility phase, and one `ApplyStep` protocol. Namespaces such as
  `environment.*`, `lighting.*`, and `security.*` are descriptors, not separate rule engines.
- The frozen `ProposalCandidateKindRegistry` validates the outer candidate kind/version before the
  selected template validates its own independent template version and payload. Initial V3 supports
  `("policy.template", 1)`.
- A learned candidate becomes a persisted `ReactionProposal`, then an explicitly reviewed configured
  policy. Strong evidence never enables an automatic action on its own.

### Safe execution

- A policy has one temporal trigger, typed guards, one `CanonicalEnvelope`, and one finite ordered
  `ActuationBundle`.
- The whole bundle passes admissibility before execution. A known-invalid member prevents all steps;
  a later HA failure stops remaining steps and records a partial outcome without speculative
  compensation.
- Each `ApplyStep` addresses exactly one logical actuator endpoint. Multiple actuator changes are
  represented as ordered steps in the same bundle, not as a multi-entity HA command.
- Manual holds, command ownership, capability, confirmed physical state, dwell/cooldown, and safety
  guards are checked on the immutable decision snapshot.
- When a configured action cannot proceed, Layer 5 emits a typed availability occurrence with every
  applicable closed reason. It does not render, persist, or send resident notifications.

## 8. Cross-Layer Communication Rules

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
| 6 -> 0/1 | Delivery audit | Sole Layer-6 `automation.availability` event producer | Any lower-layer claim of the reserved event fact type |

## 9. Performance and Technology Choices Already Fixed

These are architectural technology choices, not incidental implementation preferences:

- **Typed immutable contracts:** dataclass-like immutable records, closed vocabularies, explicit
  versions and pure validators are the default cross-layer protocol. No untyped generic event bus is
  introduced.
- **Staged immutable generations:** registries, policy templates, candidate kinds, formulas, and
  publication bindings validate before atomic activation. The active engine reads frozen O(1) indexes.
- **No blocking I/O in the hot path:** HA data are read at Layer 2's binding boundary; learning,
  persistence maintenance, resource probing, and notification delivery do not block Sensor/Fusion/
  semantic-resolution/policy evaluation.
- **Two time scales:** current facts and fusion are synchronous per cycle; historical learning,
  model rebuilds, publication reconciliation, retention pruning, and notification delivery are slow
  or background operations.
- **Canonical identity:** stable keys, explicit versions, and RFC 8785 canonical JSON make reload,
  deduplication, audit, and cache invalidation deterministic.
- **Bounded storage and work:** retention floors are declared; count and global storage ceilings are
  hard; learning and finding capacities are explicit; admission is guided by measured runtime health.
- **Clean V3 start:** no V2 configuration, state, model, approval, or history migration enters a V3
  runtime path. This removes conversion branches from bootstrap and the hot path.

The specifications intentionally do **not** select a durable database engine, ML framework, external
training protocol, or notification transport yet. Those choices must implement the contracts above;
they must not weaken ownership, typed boundaries, staged validation, or hot-path constraints.

## 10. What Is Deliberately Deferred

The following are not gaps in the defined layers; they are ownership reserved for later work:

- **Layer 4 initial semantics:** the architecture, registry, staging contract, DAG execution model,
  signal gateway, and boundaries are defined. The individual initial semantic resolvers
  (`room_occupancy`, `presence`, and independent `activity.<activity_id>` claims) still need their
  separately approved definitions: inputs, vocabulary, priority, transition stability, availability
  and provenance. The monolithic V2 `house_state` is retired.
- **Layer 6:** Full `AvailabilityEpisodeTracker` implementation, composition/publication of the
  `AvailabilityPublicationGeneration`, notification routing, rendering, deduplication/rate limiting,
  delivery/audit storage, and resident channel behavior.
- **Layer 7:** Plugin lifecycle. Existing specs permit separately staged ordinary fact producers but
  deliberately do not permit plugins to extend core hot-path semantic registries.
- **Layer 8:** Administrative configuration, review, diagnostics and cutover user experience.

These layers must consume the frozen boundaries above rather than creating parallel state stores,
specialized action engines, or direct HA access from learning/policy code.

## 11. Implementation Reading Checklist

Before implementing a component, answer these questions in order:

1. Is this a durable assertion about the house? If yes, use a Layer-1 `HouseFact` persisted by Layer 0.
2. Is it a current HA observation or a fusion of observations? It belongs to Layer 2.
3. Does it need retained history, validation, support and bounded statistical evidence? It belongs to
   Layer 3 and must run off the hot path.
4. Is it a current semantic decision? It belongs to Layer 4, not to a learner or a policy.
5. Does it create, approve, evaluate, or execute an action? It belongs to Layer 5.
6. Does it render or deliver a resident-facing message? It belongs to Layer 6.
7. Would it add a second representation, registry, scheduler, action engine, or callback path? Reuse
   the existing typed mechanism unless the shared contract cannot express the requirement without
   weakening meaning, safety, or hot-path performance.
