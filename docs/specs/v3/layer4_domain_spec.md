# Heima v3 - Layer 4: Semantic Resolution

**Status:** Defined V3 semantic-resolution contract. Not implemented.
**Open corrections:** none.

**Layer:** 4 of 8. Builds on Layer 0's cycle/timing/persistence facilities, Layer 1's immutable `HouseFact`/`Location`/`Provenance` contracts, Layer 2's current typed facts and staged registry generation, and Layer 3's closed transient `InferenceSignal` contracts. It completes the semantic-resolution DAG before Layer 5 evaluates policy. It never reads Home Assistant objects or payloads.

## 1. Purpose

Layer 4 resolves named **semantic claims**: a current `SemanticState` such as room or casa occupancy or household presence, or a `SemanticEpisode` whose bounded occurrence has meaning of its own. It is the only layer between raw/fused facts and action policy that may combine typed facts, upstream semantic claims, and one authorized learning hint into a current conclusion.

Layer 2 says what observations mean; Layer 3 analyzes history and may emit bounded evidence; Layer 4 resolves semantic claims; Layer 5 decides whether a `ConfiguredReaction` may act. Learning is evidence, not authority; a semantic resolver is not a reaction engine.

## 2. Scope and Boundaries

Layer 4 owns:

- the frozen core `SemanticResolverRegistry` and administrator-instantiated `SemanticResolverDefinition`s;
- staging, dependency validation, fingerprinting, topological ordering and atomic swap of a semantic generation;
- immutable per-cycle input snapshots and resolution of the semantic DAG;
- typed state/occurrence `HouseFact`s emitted by declared semantic output claims;
- narrow, registered acceptance of an `InferenceSignal` by its one authorized semantic resolver;
- its own availability-suppression occurrence and staged owner-key declaration to Layer 6.

Layer 4 does not own Home Assistant reads, entity interpretation, fusion, formula registration, or
logical Actuators (Layer 2); `Topology` and the immutable location contracts (Layer 1); historical
learning/artifacts/signals/candidates (Layer 3); ReactionDescriptors, ConfiguredReactions, review,
guards, envelopes, action results or `ApplyStep`s (Layer 5); or notification
delivery/publication-generation composition (Layer 6).

It has no runtime dependency on policy configuration or action results. A policy being enabled, disabled, held, suppressed, accepted, or previously executed cannot change a semantic conclusion.

## 3. Core Principles

- **Current-cycle semantics only.** A semantic resolver reads only its frozen snapshot, never durable history, later facts, mutable HA state, or a future cycle.
- **One durable representation.** A public semantic claim is a declared Layer-1 `HouseFact` submitted through Layer-0 Persistence. Evaluator results are local, never a parallel state store.
- **Declared meaning.** A resolver kind fixes claim kind, vocabulary, inputs, priority, availability, scope, and pure evaluator. The administrator configures only exposed typed bindings/parameters.
- **Closed learning ingress.** An `InferenceSignal` is admissible only when its core signal type and frozen contract authorize this resolver kind, claim-parameter tuple and subject scope. Each contract has one resolver kind; distinct contracts may share a signal type. Absence or expiry is absence of optional evidence, never a negative assertion.
- **No policy leakage.** A semantic resolver never inspects templates, guards, envelopes, Actuators, command outcomes, manual holds, or review state.
- **No hot-path I/O.** Lookup, input resolution, signal resolution, DAG traversal, and evaluators are in-memory, pure, and bounded.

### 3.1 `SemanticState` and `SemanticEpisode`

A `SemanticState` is one current, independently meaningful assertion at one explicit scope. Its value is
readable only while `available=True`; `available=False` means the resolver cannot form a conclusion.
Examples are `occupancy` for one room or for `casa`, and `presence` (the household) for `casa`.

A `SemanticEpisode` is not an automatic event mirror for a state transition. It is permitted only when
its occurrence has an independently declared identity, boundary, evidence contract, and consumer use
that would be lost by reading ordinary state history. An episode resolver emits only its declared event
occurrences; it has no latest-value slot. Initial V3 registers exactly two core
`StateTransitionEpisodeAdapter`s, on the casa `occupancy` state and on the casa `presence` state. They
emit only the reviewed `occupancy.departure`/`occupancy.return` and
`presence.departure`/`presence.return` occurrences of §9.3; no other initial state transition
is mirrored automatically, and another episode producer needs its own approved lifecycle contract.

```python
@dataclass(frozen=True)
class SemanticEpisodeOccurrence:
    episode_type: str                 # closed by the core output template
    phase: Literal["started", "ended", "observed"]
    episode_key: str                  # deterministic resolver-defined identity, never a random UUID
    value: SemanticValue
    confidence: float | None
    evidence: Mapping[str, EvidenceValue]
```

An episode template fixes its closed `episode_type`, permitted phases, deterministic `episode_key`
derivation, event value shape, and whether a `started` occurrence requires one later matching `ended`
occurrence. A resolver may emit only one declared occurrence per `(episode_type, phase, episode_key,
when)`; the coordinator validates this before appending the Layer-1 event `HouseFact`. There is no
persisted `available=False` episode: no emission means no new occurrence. A state required to express
“currently active” is a separate declared `SemanticState`, never a reconstruction from an episode.

An output claim declares whether its values form one **exclusive axis** (for example one room is
`present` or `absent`) or independent claims (for example `activity.working` and `activity.relax` may
both be active at different explicit scopes). A resolver must not use an exclusive enum to merge
presence, activities, operational intent, plans, or social context into a synthetic global state.

## 4. Semantic Resolver Registry and Staging

### 4.1 Frozen Core Resolver Kinds

The core-owned `SemanticResolverRegistry` is built at bootstrap and frozen before any generation runs. It is not administrator-configurable or plugin-extensible. The persisted generation stores no callable; the active in-memory generation resolves the pure evaluator by `(resolver_kind_id, implementation_version)`.

```python
ClaimParameterSchema = Mapping[str, frozenset[str]]
CanonicalClaimParameters = tuple[tuple[str, str], ...]

@dataclass(frozen=True)
class SemanticAvailabilityContract:
    output_fact_type_pattern: str
    suppression_scope_id: str
    allowed_reasons: frozenset[AutomationSuppressionReason]

@dataclass(frozen=True)
class RegisteredSemanticResolver:
    resolver_kind_id: str
    implementation_version: int
    legal_scopes: frozenset[ScopeKind]
    output_template: SemanticOutputTemplate
    claim_parameter_schema: ClaimParameterSchema
    input_schema: SemanticInputSchema
    accepted_signal_types: frozenset[str]
    signal_routing_schema: SignalRoutingSchema | None
    parameter_schema: ParameterSchema
    validate_definition: PureValidator
    evaluate: PureSemanticEvaluator
    availability_contract: SemanticAvailabilityContract | None
```

`ClaimParameterSchema` is a finite, closed mapping of parameter names to
nonempty core-owned value vocabularies. `CanonicalClaimParameters` contains
exactly one value per declared name, sorted by name for fingerprinting;
unknown, missing, duplicate or out-of-vocabulary values fail staging.
`SemanticAvailabilityContract=None` means the resolver owns no suppression
episode. A present contract names the resolver's one output fact-type
template, one stable semantic
suppression scope and a nonempty subset of Layer-3
`AutomationSuppressionReason`; staging rejects a mismatched output, duplicate
scope ownership or an unregistered reason. Runtime reasons must be a subset of
that frozen set, and the subject is the resolver's staged `Location`.

`SemanticOutputTemplate` fixes claim kind (`state` or `episode`), matching emission kind, core-owned
fact-type template, value vocabulary/unit, axis cardinality, legal `Location` scope, and output
availability behavior. An episode additionally fixes the `SemanticEpisodeOccurrence` contract above.
The template is either fixed or has a finite named set of core-declared claim parameters. Staging
validates `claim_parameters`, materializes one exact `SemanticOutputClaim`, and contributes its ordinary
Layer-0 `FactTypeClaim` plus, for a state, its exact state-producer claim. An episode contributes only
its event claim and rejects `previous_cycle`. `SemanticInputSchema` is a finite ordered set of typed lower-fact,
upstream-semantic-claim, and optional authorized-signal slots. It fixes requiredness, scope
compatibility, value/unit, availability/freshness, and whether an input can establish, refine, or only
constrain a conclusion.

The `activity` resolver kind additionally selects one member of its finite, core-owned
`ActivityProfile` table through `claim_parameters.activity_id`. This is profile data within the frozen
resolver kind, not an administrator-authored formula language or a second runtime registry. A profile
fixes its legal scopes, output mode, exact typed slots and their evidence roles, accepted signal use,
and pure priority/closure behavior. Adding an activity is a core specification/code change that adds a
profile and its tests; an administrator may instantiate only a profile already frozen into the active
core version.

A core `StateTransitionEpisodeAdapter` may be attached to a state output template. It is not a second
resolver or a general event-history query: staging gives it a finite table of permitted
`(from_value, to_value, episode_type)` transitions, materializes its exact event `FactTypeClaim`s, and
declares its O(1) per-output state. The adapter observes only the freshly resolved state output and its
own last available observation; it never exposes `previous_cycle` to an episode evaluator. This is the
generic mechanism for an event whose meaning is a declared transition of a semantic state.

`SignalRoutingSchema` is a pure core-owned projection from a closed signal payload to the resolver's
claim-parameter tuple. At staging it compiles one immutable O(1) index keyed by
`(resolver_kind_id, claim_parameter_tuple, exact scope)`. No runtime signal performs a wildcard,
registry scan, or configuration query. A signal with no exact staged resolver is absent to evaluation
and produces only its bounded diagnostic reason.

### 4.2 Definitions and Atomic Generation

```python
ExplicitScope = Location  # exact Layer-1 value contract; resolver kind restricts legal scopes

@dataclass(frozen=True)
class SemanticResolverDefinition:
    resolver_id: str
    resolver_kind_id: str
    implementation_version: int
    scope: ExplicitScope
    claim_parameters: CanonicalClaimParameters
    input_bindings: tuple[SemanticInputBinding, ...]
    parameters: CanonicalParameters
    enabled: bool
```

`ExplicitScope` is exactly one Layer-1 `Location` with a `scope` value
permitted by the resolver kind: `room`, `zone`, `rooms`, or `casa`. A zone id
resolves to its declared membership during staging; a set of at least two
rooms uses `Location(scope="rooms")`, while a singleton uses `room`.
The canonical `LocationKey` and resolved ordered membership enter the
definition fingerprint. Wildcards and live queries are forbidden because
they could silently change input population, meaning, output claims, and
downstream policy behavior.

Staging resolves all bindings against the candidate Layer-2 and upstream semantic generations; validates
claim parameters and materializes each exact output claim; validates signal authorization and routing
against Layer 3's read-only signal registry; computes fingerprints, the routing index, and the DAG;
then atomically activates one immutable `SemanticResolutionGeneration`. It rejects
unknown/incompatible kinds, illegal scope, unresolved or duplicate bindings, invalid claim parameters,
signal consumer/routing/scope/value/TTL mismatch, duplicate state claims, same-cycle cycles, unknown
parameters, raw HA selectors, callables, Actuators, policies, or dynamic fact expressions.

## 5. Cycle Model and Semantic DAG

### 5.1 Snapshot Boundary

Layer 0 first consolidates the accepted equal-`when` Layer-2 intake facts behind one immutable
`CycleInputBarrier`. The engine creates an immutable `SemanticInputSnapshot` containing that completed
input group and declared current values, active Layer-2/semantic-generation fingerprints, valid
registered signals emitted by Layer 3 earlier in this same cycle (Layer 3 §6.3), cycle identity/UTC `when`, and only predeclared Layer-0 `previous_cycle` values.

Layer 4 evaluates enabled semantic resolvers in deterministic topological order. An evaluator can read only declared lower-fact slots, declared upstream semantic-claim slots, one declared optional signal slot, parameters, and declared previous-cycle values. It cannot inspect a global fact map, HA cache, policy, future resolver output, or arbitrary prior result.

After the DAG completes, the engine creates Layer 5's immutable `DecisionSnapshot`. Its input group
remains the Layer-2 group closed by the `CycleInputBarrier`; Layer-4 outputs are represented only by
the resolved semantic-claim map, never retroactively inserted into that trigger group. The coordinator
attaches Layer 0's opaque `FrozenHistoryView`, `FrozenCalendarView`, and `HoldAdmissionView`,
plus Layer 0's `FrozenRecoveryView` and Layer 5's `CommandOwnershipView` and
`FrozenReactionAuthorityView`, before Layer-5 evaluation. The history/calendar requirements
come from the active Layer-5 generation. None of these views exposes policy configuration or
calendar contents to a semantic resolver. Layer 4 does not read, classify, resolve, or otherwise interpret this calendar
view: it transports the already frozen Layer-0 input to its downstream policy consumer.

For each staged Layer-5 `state_transition` trigger naming a Layer-2 state
fact or Layer-4 `SemanticState`, staging declares its exact `FactIdentityKey`
as a Layer-0 `previous_cycle` key. After the semantic DAG completes, the
coordinator forms one typed pair from that key's sealed previous-cycle fact
and this cycle's `current_layer2_facts` or `semantic_claims` fact, according
to the staged producer claim. It never scans history or appends a generic episode.
A missing predecessor after startup, an impacted semantic generation, or a
producer-execution fingerprint mismatch is represented as `previous=None`.
An unavailable prior or current fact remains visibly unavailable; Layer 5
must abstain from calling it a transition.

```python
@dataclass(frozen=True)
class StateTransitionInput:
    claim_key: FactIdentityKey
    previous: HouseFact | None
    current: HouseFact

@dataclass(frozen=True)
class DecisionSnapshot:
    snapshot_id: str
    cycle_id: int
    when: EvidenceInstant
    input_barrier: CycleInputBarrier
    layer2_generation_fingerprint: str
    semantic_generation_fingerprint: str
    input_fact_group: tuple[HouseFact, ...]       # canonical equal-when intake group
    current_layer2_facts: Mapping[FactIdentityKey, HouseFact]
    semantic_claims: Mapping[FactIdentityKey, HouseFact]
    semantic_episodes: tuple[HouseFact, ...]      # validated Layer-4 event occurrences this cycle
    state_transition_inputs: tuple[StateTransitionInput, ...]  # declared keys only, canonical order
    history_view: FrozenHistoryView
    calendar_view: FrozenCalendarView
    hold_admission_view: HoldAdmissionView    # frozen Layer-0 §6.1.1 projection
    command_ownership_view: CommandOwnershipView  # frozen Layer-5 §6 projection
    recovery_view: FrozenRecoveryView         # frozen Layer-0 §7.4 projection
    reaction_authority_view: FrozenReactionAuthorityView  # frozen Layer-5 §4.2 projection
```

`snapshot_id` is the SHA-256 digest of the RFC-8785 canonical JSON representation of
`(cycle_id, when, input_barrier, layer2_generation_fingerprint, semantic_generation_fingerprint,
calendar_view.fingerprint, hold_admission_view.fingerprint,
command_ownership_view.fingerprint, recovery_view.fingerprint,
reaction_authority_view.fingerprint, state_transition_inputs)`.
It is deterministic for a retry of the same frozen cycle and distinct for every later cycle, whose
cycle instant is strictly later (Layer 0 §3.5). A later fact, signal, generation change, or history append cannot alter the
snapshot, its history view, trigger group, guards, or envelope result.

### 5.2 Output and Availability

```python
@dataclass(frozen=True)
class SemanticStateResult:
    available: bool
    value: SemanticValue | None
    confidence: float | None
    evidence: Mapping[str, EvidenceValue]
    availability_reasons: tuple[AutomationSuppressionReason, ...] | None
    # None when this resolver has no active availability episode; otherwise non-empty and already
    # canonical under Layer 3's canonicalize_suppression_reasons().
```

`PureSemanticEvaluator` returns `SemanticStateResult` for a state template or zero or more declared
`SemanticEpisodeOccurrence`s for an episode template; staging rejects a kind whose evaluator/result
shape disagrees with its output template. For a declared `SemanticState`, Layer 4 converts the local
result into one candidate `HouseFact` for its output `FactIdentityKey`. When `available=False`, `value`
is undefined under Layer 1: the old available value is never retained as the current conclusion. Layer 0
write-on-change suppresses durable duplicates. A declared `SemanticEpisode` appends only its validated
occurrence and has no current-value or `previous_cycle` use. The coordinator, not the evaluator,
validates and appends facts through the ordinary Layer-0/Layer-1 path. Every such fact has
`FactSource.kind="semantic_resolver"`, with the materialized resolver identity and execution
fingerprint; `semantic_resolver` is the sole closed Layer-0 provenance kind for Layer-4 outputs.
`availability_reasons` is not fact evidence or a second semantic output: it is admitted only for a
resolver with a staged `SemanticAvailabilityContract` and only from Layer 3's closed
`AutomationSuppressionReason` vocabulary.

An edge exists only for a declared same-cycle upstream semantic claim. The generation rejects cycles; independent nodes use stable `resolver_id` order. A `previous_cycle` input must be declared and reads only Layer 0's in-memory snapshot, never disk history.

## 6. Inference Signal Gateway

A signal is considered only when its core signal type and frozen contract authorize this resolver kind;
the contract's claim parameters and legal scope kind, and the core-declared routing projection,
must exactly match the resolver's materialized claim parameters and subject scope;
`emitted_at <= snapshot.when < expires_at`; its artifact/freshness/schema is valid; and the resolver's
declared priority permits it. Otherwise it is absent for the cycle. Because Layer 3 emits within the
cycle after the Layer-2 barrier, an admitted signal has `emitted_at == snapshot.when`; the inclusive
lower bound admits it, and the exclusive upper bound makes a signal expiring exactly at the cycle
instant absent. Retraction at expiry relies on Layer 3's expiry `AtJob`, not on unrelated input. A valid optional signal may still
lose to stronger deterministic evidence, recorded as bounded provenance without raw learner or HA
payload.

| Signal type / contract id | Authorized resolver kind | Allowed use |
|---|---|---|
| `indirect.semantic_assist.v1` / `occupancy.room_present.indirect.v1` | `room_occupancy` | Positive optional `present` evidence only; never `absent`. |
| `indirect.semantic_assist.v1` / `activity.sleeping.indirect.v1` | `activity` | Exact room scope routes only to the `sleeping` profile; positive `active` evidence only, never inactivity. |
| `indirect.semantic_assist.v1` / `activity.relax.indirect.v1` | `activity` | Exact room scope routes only to the `relax` profile; positive `active` evidence only, never inactivity. |
| `indirect.semantic_assist.v1` / `activity.working.indirect.v1` | `activity` | Exact room scope routes only to the `working` profile; positive domestic `active` evidence only, never inactivity. |

No initial signal is authorized for casa `occupancy` or `presence`: both remain deterministic. A signal-consuming semantic claim cannot become feature, reference, label, or target of its contributing Layer-3 learner; provenance identifies the signal contribution to prevent that feedback path. The monolithic `house_state.approved_context.v1` signal is retired: any future learned signal must name one approved semantic claim and cannot reintroduce a composite house-state vocabulary.

## 7. Availability and Layer 6

A semantic resolver is a suppression owner only when its `SemanticAvailabilityContract` declares a
specific semantic output and the subset of Layer 3's closed `AutomationSuppressionReason` vocabulary
it may report. The coordinator canonicalizes `SemanticStateResult.availability_reasons` with Layer 3's
single helper and constructs the typed `AvailabilitySuppressionOccurrence`; it emits it only when the
owner's episode starts, its canonical reason set changes, or it ends. It never renders, delivers,
persists, or selects notification bindings.

At staging, Layer 4 contributes only exact `(suppression_owner_id, suppression_scope_id, subject)` declarations. It contributes no `automation_scope_id`, enabled/user-visible state, or policy reference. Layer 6 alone composes the `AvailabilityPublicationGeneration` from owner declarations and Layer-5 automation bindings.

## 8. Reload, Recovery, and Performance

Every semantic generation activates only as part of one composed configuration generation (Layer 0 §4.7). A resolver whose input binding or upstream claim no longer validates after a confirmed upstream change is invalidated by that commit and does not run until a successor definition validates. A removed, disabled or invalidated state resolver emits exactly one terminal `available=False` fact for its output claim at the swap, so no earlier available conclusion remains its latest state; an episode resolver emits nothing. A semantic-only upstream change keeps the resolver and is listed in the impact record. A changed kind/version, output claim, scope membership, input binding, signal contract, semantic parameter, priority rule, or availability contract creates an impacted generation. Its old conclusion is not reused under the new meaning: the impacted resolver starts with no evaluator-local state and emits an unavailable state until a fresh snapshot supports a result. Unimpacted resolvers preserve only state their kind explicitly declares safe.

Evaluation is bounded by finite declared inputs and pure evaluator work. It performs no durable history read, HA call, remote inference, lock acquisition, dynamic import, registry scan, policy lookup, Actuator resolution, or notification work. Staging, generation diffing, availability composition, and persistence maintenance are outside the engine path.

After restart, the generation is rebuilt through staging. Evaluator-local state begins empty unless a future explicit Layer-0 recovery contract says otherwise; persisted history is not a current evaluator cache.

## 9. Initial Semantic Claims and Deferred Semantics

The following initial resolver kinds use this kernel. Their approved inputs, vocabularies,
priorities, transition stability, availability, provenance, and acceptance criteria are specified
in §9.1–§9.7; any later resolver kind requires its own review:

1. `room_occupancy`: room-scoped `SemanticState`, built from physical room evidence plus an authorized positive indirect hint.
2. `casa_occupancy`: deterministic casa `occupancy` (is anyone physically in the house), with the closed `present | absent` vocabulary.
3. `presence`: deterministic household presence at casa (is any resident home), with the closed `home | away` vocabulary.
4. `occupied_without_residents`: deterministic casa boolean derived from the two claims above (CA4-122).
5. `activity`: independently scoped `activity.<activity_id>` `SemanticState`s without forcing activities into one classifier or global enum. `cooking`, `sleeping`, `relax`, and `working` are the first fully specified profiles.

The casa `occupancy` and `presence` resolvers each additionally have one registered transition-episode
adapter in §9.3. They produce the four initial episode types; they are not further semantic-state
resolvers or a generic transition mirror.

`house_state` is deliberately not an initial claim: its V2 vocabulary mixed presence, activity, quiet/sleep context, planned absence, and guest context. Planned absence and guest stay are not Layer-4 claims either: they are declared household context,
the Layer-2 facts `household.planned_absence` and `household.guest_stay` (Layer 2 §2.9, CA4-121),
never inferred. A future quiet/sleep context, identity inference, multi-occupant counting, learned absence, HVAC control, environmental policy evaluation, and security policy each need a separate claim and authority/safety contract.

### 9.1 `room_occupancy`

`room_occupancy` materializes the room-scoped state claim `occupancy` with the closed value vocabulary
`present | absent`. It has exactly one required Layer-2 input `occupancy.physical` at the same room and
one optional routed `indirect.semantic_assist.v1` signal under contract
`occupancy.room_present.indirect.v1`. The physical input is a boolean fusion
result; the resolver performs the only permitted translation across this boundary:

1. physical `True` resolves to `present`;
2. physical `False` resolves to `absent`;
3. physical `available=False` plus a valid routed indirect positive signal resolves to `present`;
4. every other case resolves to `available=False`.

The indirect signal never overrides an available physical conclusion and never produces `absent`.
`room_occupancy` adds no dwell, grace, or retained state: Layer 2's `occupancy.physical` fusion alone
owns fast-on/slow-off temporal behavior. Its provenance identifies whether the semantic state came from
physical fusion or the bounded indirect assist; the latter is never eligible as the model's own label.

### 9.2 `casa_occupancy` and `presence` (CA4-120)

Two distinct casa claims answer two distinct questions; every consumer names the one it reads.

**`casa_occupancy`** materializes the casa-scoped `occupancy` claim with the closed vocabulary
`present | absent`. It has exactly one required Layer-2 boolean input `occupancy.physical` at
`Location(scope="casa")`, fused from physical evidence only plus optional corroborating person
evidence (Layer 2 §2.8.1), and no `InferenceSignal` input. Physical `True` resolves to `present`,
`False` to `absent`, unavailable to `available=False`. A room whose enclosure is `exterior` (terrace,
garden) is part of `casa`: evidence the administrator binds from it is ordinary occupancy evidence,
and enclosure never excludes it (Layer 1 §7). It says that someone is physically inside, whoever it is.

**`presence`** materializes the casa-scoped household claim `presence` with the closed vocabulary
`home | away`. It has exactly one required Layer-2 boolean input `presence.household` at casa
(Layer 2 §2.8.1), produced only from residents' HA persons. `True` resolves to `home`, `False` to
`away`, unavailable to `available=False`. It says that at least one resident is home; a guest, a
device account or anyone else inside never makes it `home`.

**Occupied without residents.** `occupancy=present` with `presence=away` is a normal, expected
combination (a guest alone, a house sitter, a cleaner, an untracked resident). Neither claim
overrides the other. The resolver `occupied_without_residents` (CA4-122) materializes it as the
casa claim `occupied_without_residents` with a boolean value: `True` exactly when `occupancy@casa` is
`present` and `presence@casa` is `away`, `False` for any other pair of available values, and
`available=False` when either input is unavailable. It reads only those two upstream claims of the
same cycle, adds no dwell or retained state, and asks no question about who is inside. It is the one
definition that Layer 5 descriptors (`when_occupied_without_residents`) and Layer 3 behavior
learners (censoring) consume; neither recomputes it. No warning is raised for it: Heima is not a
security system, and intrusion belongs to the alarm integration.

Layer 4 adds no dwell, grace, or retained state to either claim: the Layer-2 fusions own source
quorum, explicit evidence admission/correlation, and transition stability. Layer 4 never reclassifies
a camera's generic motion or object output as a person. A future elapsed-absence, identity or
multi-occupant semantic claim must consume these states through its own reviewed resolver or
episode contract; none is a hidden timer or value inside them.

### 9.3 Casa transition episodes

The core attaches one `StateTransitionEpisodeAdapter` to each casa claim, with these finite
transition tables:

| Claim | Transition | Episode |
|---|---|---|
| `occupancy@casa` | `present -> absent` | `occupancy.departure` |
| `occupancy@casa` | `absent -> present` | `occupancy.return` |
| `presence@casa` | `home -> away` | `presence.departure` |
| `presence@casa` | `away -> home` | `presence.return` |

All are `SemanticEpisodeOccurrence(phase="observed")` values; they are observations of a semantic
change, not a claim about the exact physical instant someone crossed a threshold. Occupancy episodes
delimit periods with nobody inside (physical learning, Layer 3); presence episodes mark the household
leaving and returning (absence programs, Layer 5).

Each adapter keeps the last available value of its claim and its `when` in its declared in-memory
state. For a newly available different value it emits exactly one episode with the following closed
payload, whose `from`/`to` use that claim's vocabulary:

```python
CasaTransitionValue = {
    "from": Literal["present", "absent"] | Literal["home", "away"],   # the claim's vocabulary
    "to": Literal["present", "absent"] | Literal["home", "away"],
    "continuity": Literal["contiguous", "reconciled_after_gap"],
    "last_available_when": EvidenceInstant,
    "observed_at": EvidenceInstant,             # equal to the event HouseFact.when
}
```

`continuity="contiguous"` means no unavailable output of that claim occurred after
`last_available_when`; `continuity="reconciled_after_gap"` means one or more unavailable outputs did
occur. In both cases `last_available_when < observed_at`, which Layer 0 §3.5 guarantees by giving
every cycle a strictly later cycle instant; for a reconciled episode, the physical
transition is known only to have occurred in `(last_available_when, observed_at]`. The deterministic
`episode_key` is the RFC-8785/SHA-256 digest of `(resolver id, from, to, last_available_when,
observed_at)`.

An unavailable output never emits an episode and never discards the retained last available baseline.
If availability resumes with the same value, it clears the gap and emits nothing; if it resumes with a
different value, it emits the reconciled episode above. With no retained available baseline, including
after restart or an impacted reload, the first available value seeds the adapter and emits nothing.
Each adapter is O(1), makes no history/HA/I/O call, and its state resets under the ordinary Layer-4
reload and recovery rules. A future policy trigger may explicitly accept `contiguous`,
`reconciled_after_gap`, or both; no policy obtains either episode implicitly from a bare state change.

### 9.4 `activity` kernel and initial `cooking` profile

An `activity` claim is scoped, not person-identified: `activity.cooking` at one explicitly configured
kitchen scope says that a cooking activity is currently supported there, not which resident is cooking.
It is an independent semantic axis. No activity profile can set, clear, or supersede `occupancy` or `presence`,
`occupancy`, `relax`, `sleeping`, `working`, or another activity merely because they coexist.

```python
ActivityEvidenceRole = Literal["anchor", "context", "closure"]
ActivityOutputMode = Literal["positive_only", "bipolar"]

@dataclass(frozen=True)
class ActivityEvidenceSlot:
    slot_id: str
    role: ActivityEvidenceRole
    source: FactRef                # current typed Layer-2 or upstream semantic state
    qualifying_values: tuple[EvidenceValue, ...]
    required: bool

@dataclass(frozen=True)
class ActivityProfile:
    activity_id: str                         # finite core-owned id, e.g. "cooking"
    implementation_version: int
    legal_scopes: frozenset[ScopeKind]
    output_mode: ActivityOutputMode
    slots: tuple[ActivityEvidenceSlot, ...]  # exact typed/scope-compatible bindings
    accepted_signal_type: str | None
    evaluate: PureActivityEvaluator           # core code, resolved at bootstrap; never serialized
```

An `ActivityEvidenceSlot` is a finite, staged current-state binding, not a
history query. Its `source.previous_cycle` is false; staging resolves its
registered value vocabulary, exact subject-compatible `Location` and producer
generation, and rejects empty, duplicate or wrong-type `qualifying_values`.
An unavailable reading cannot satisfy any role. Freshness is the producer's: a
state's `when` is its last accepted change, so an old `when` never makes a
continuously observed state stale; source report age is Layer 2's
`max_source_age` (Layer 1 §4.1, Layer 0 §4.4). A profile that needs to know that
something changed recently binds an event or episode slot, never the age of a
state. Only an explicit available `closure` match may support
`inactive`; a missing or false `anchor` never does.

An `anchor` is an explicitly normalized fact whose positive value has direct semantics for the
activity; it may establish `active` under the profile's declared rule. `context` can qualify an
anchor or an admitted learning signal but cannot establish `active` alone. `closure` is affirmative
evidence that a bipolar profile may use to establish `inactive`; absence, expiry, unavailability, or
negative silence of an anchor/context/signal never establishes `inactive`. The profile fixes the
finite conjunction/disjunction of these roles in core code. There is no generic expression language,
unbounded aggregation, history scan, or policy lookup in an activity definition.

`positive_only` publishes `value="active"` when its positive rule is met and otherwise publishes
`available=False`; it intentionally makes no assertion that the activity is inactive. `bipolar`
profiles may additionally publish `value="inactive"`, but only from their explicit closure rule. Both
forms preserve the general Layer-4 rule that an unavailable result has no value. An admitted
`indirect.semantic_assist.v1` signal is a positive input only. A profile may require an anchor before
using it, may use its exact admitted contract as a separately confidence-bounded positive route, or may
prohibit it entirely; that choice is fixed by the core profile and visible in provenance.

The initial `cooking` profile is `positive_only`, legal only at one explicit room scope selected by the
administrator, and initially accepts no learning signal. It requires one or more same-room boolean
`anchor` bindings of the normalized Layer-2 family
`appliance.cooking_heat_source_active`; each binding represents a specifically identified cooking heat
source (for example a cooktop burner/aggregate or an oven in active heating), never a generic smart
plug. It may accept `occupancy` at the same scope and `extractor`/ventilation activity at that scope as
optional `context` inputs, solely to refine confidence and provenance. It resolves `active` when any
available anchor is `True`; with no such anchor it resolves `available=False`. A false or unavailable
anchor is not evidence that meal preparation has ended: the initial profile deliberately does not emit
`inactive`.

This narrow first profile is useful immediately for conservative policy and explanation, while being
honest about the observable fact. It does not turn humidity, a hood, kitchen occupancy, or a learned
pattern into an assertion that someone is cooking. A future version may add a bipolar cooking profile
only with a reviewed closure contract, rather than silently changing the meaning of the initial claim.

### 9.5 Initial `sleeping` profile

`activity.sleeping` means that a sleep context is supported in one room. It is not a clinical sleep
measurement, a sleep-stage classifier, a person identity claim, or a casa-wide assertion that everyone
is asleep. The profile is `positive_only` and room-scoped: it publishes only `active` or
`available=False`. A missing, expired, contradicted, or unavailable input never publishes `inactive`.
This makes a brief overnight absence from a bedroom a loss of local support, not an implicit claim that
the resident has woken or that every household policy should leave sleep context.

The profile has two explicit positive routes. A registered normalized `sleep.session_active` fact from
a dedicated wearable, bed, or other device that itself declares an active sleep session is an optional
direct `anchor`; it may establish `active`, while retaining its device-specific confidence/provenance.
Bed occupancy, room occupancy, darkness, light state, charging devices, low local activity, and time
of day are only `context`: no one of them, nor their accidental simultaneous absence, can establish
sleep by itself. A resident-declared sleep intent is a separate future semantic claim, not an anchor
for actual sleeping context.

The second route accepts only `indirect.semantic_assist.v1` under the exact
`activity.sleeping.indirect.v1` contract. Layer 4 requires both that valid, unexpired signal and the
same-room resolved `occupancy=present` claim in the frozen semantic DAG. The contract is already
responsible for its resident-approved routine reference, independent evidence-family/correlation
checks, current physical-occupancy serving precondition, shadow, drift, and `routine_affinity` gates;
the resolver neither repeats that learning work nor inspects raw features. It emits `active` with the
signal's bounded confidence and provenance `indirect_routine`, distinct from provenance `direct_anchor`.

Direct anchor evidence wins over the indirect route when both are present. Contradictory direct
evidence makes the profile unavailable rather than allowing an inferred signal to override it. The
profile adds no dwell, timer, history read, or polling: Layer 2 owns physical transition stability and
Layer 3 owns temporal routine analysis. Layer 4 performs only finite snapshot-slot lookup and pure
priority resolution.

`activity.sleeping` may initially feed only conservative, reversible Layer-5 behavior explicitly
admitted for an indirect-routine provenance, such as low-intensity lighting or deferral of ordinary
notifications. It cannot by itself suppress urgent safety/security notification, command a lock,
disarm/arm an alarm, or establish a safety condition. A future casa-level quiet/sleep context must be
a separately reviewed claim with explicit multi-resident and overnight-interruption semantics; it is
not derived implicitly from this room claim.

### 9.6 Initial `relax` profile

`activity.relax` means that a resident-approved leisure/rest context is supported in one room. It is
not a synonym for media playback, reading, a sofa being occupied, a dim scene, or absence of work; it
does not identify a resident and does not imply that another activity has ended. The profile is
`positive_only`, room-scoped, and publishes only `active` or `available=False`.

The initial profile has no universal direct anchor. It accepts only `indirect.semantic_assist.v1` under
the exact `activity.relax.indirect.v1` contract, with matching room scope, `assertion="active"`,
`confidence_kind="routine_affinity"`, and same-room resolved `occupancy=present`. The contract owns
resident routine approval, the minimum two independent evidence families, shadow, drift, and source
correlation; Layer 4 performs only the bounded contract/scope/occupancy checks. A media player, sofa
sensor, low light, clock time, quiet room, or a Heima-applied cinema/relax bundle alone is never a
semantic conclusion. A manually resident-controlled media or lighting state may be a contract-approved
observational feature, but still requires the second independent family.

The profile has no hidden exit timer or inverse inference. A missing/stale signal, no current room
occupancy, contradictory required input, or an unavailable Layer-2 fact produces `available=False`,
not `inactive`. It adds no polling, history read, or action work to the cycle path.

An `activity.relax` claim may later select only explicitly approved, reversible Layer-5 policy behavior
for its indirect-routine provenance, such as non-disruptive lighting ambience or ordinary-notification
presentation. A deterministic reaction such as “resident starts a projector; set these three lights to
these targets” remains a Layer-5 trigger/guard/`ActuationBundle` contract, whether or not it also uses
`relax` as context. The resolver itself never launches a scene or bundle.

### 9.7 Initial `working` profile

`activity.working` means that domestic work context is supported at one room-scoped workstation. It
does not identify a resident, prove paid employment, imply that a computer user is productive, or make
a claim about work performed outside the home. It is `positive_only`: it emits `active` or
`available=False`, never `inactive`. An office-day plan, absent calendar, locked computer, or missing
signal is lack of domestic-work support, not a conclusion that the resident is not working.

The profile accepts only `indirect.semantic_assist.v1` under the exact
`activity.working.indirect.v1` contract, matching room scope, `assertion="active"`, and
`confidence_kind="routine_affinity"`. It requires same-room resolved `occupancy=present`. The
contract must have one workstation-operational evidence family and a second independent context family.
The operational family may use only privacy-normalized Layer-2 computer facts from Layer 2 §3.5, such as
active interaction, a classified work application, or a declared communication-session fusion; raw
application/window/content data is never visible here. The second family may be a declared work-location
calendar fact, workstation presence, communication context, or a declared learned day/time feature.

`calendar.work_location=home` is supportive context; `calendar.work_location=office` makes the
domestic-working route unavailable; `unknown` and calendar absence are neutral. Day of week and time
are learned contextual features rather than static rules. A computer being active, a calendar event, a
communication state, or a standard working hour alone is insufficient. A direct communication-session
fact can independently drive a deterministic Layer-5 interruption policy, but it never becomes a
synonym for working and the `working` resolver never waits for learning before that policy can react.

Heima-generated lighting, notifications, and actuation bundles are excluded from the contract's
evidence/reference paths. The profile adds no timer, history scan, polling, or application inspection:
Layer 2 performs source normalization, Layer 3 analyzes the approved routine, and Layer 4 performs
only the finite snapshot/contract checks. The resulting claim may support only explicitly approved,
reversible, conservative policy behavior, such as reducing ordinary interruptions in the workstation
room; it cannot suppress urgent safety/security communication or establish an access/security state.

## 10. Initial Acceptance Criteria

- `ClaimParameterSchema` rejects missing, duplicate, unknown and
  out-of-vocabulary parameter ids; the same finite parameters have one
  canonical order. A resolver without `SemanticAvailabilityContract` cannot
  report suppression reasons; a present contract permits only its own output,
  scope and registered reason subset (§4.1/§7).
- `ActivityEvidenceSlot` rejects an event or previous-cycle source, wrong
  value type/scope or empty qualifying set; it has no age field. A context
  reading cannot become an anchor, an unavailable reading satisfies no role,
  a stable state changed hours ago still qualifies while available, and only
  an available matching closure slot can establish an inactive bipolar
  activity (§9.4).
- Every enabled semantic resolver has a registered core kind/version, legal explicit scope, valid claim parameters, one materialized unique output claim, resolved typed inputs, valid parameters, and deterministic DAG position.
- Staging rejects wildcards, raw HA selectors, expressions/callables, Actuator/policy references, unknown/unauthorized signals, invalid/unroutable signal parameters, duplicate claims, and same-cycle cycles.
- A resolver evaluates only its frozen snapshot; later fact/signal/policy/action changes cannot alter that cycle's result.
- A valid signal can influence only its authorized resolver; the resolver's separate declared `HouseFact`, not the signal, enters Persistence.
- Two distinct `IndirectAssistanceContract`s may route the same signal type to occupancy and activity,
  respectively; staging rejects a single signal type/contract identity routed to two resolver kinds,
  mismatched claim parameters, or an incompatible subject scope.
- A signal emitted in the cycle with instant `t` is admitted at `snapshot.when == t`; one with `expires_at == t` is absent. With no other input, Layer 3's expiry job triggers a cycle at `expires_at`, and a signal that no longer qualifies retracts the assisted conclusion in that cycle; a restart carries no signal forward.
- An absent/expired/invalid signal never becomes a negative assertion, stale retained state, policy action, fact of its own, or direct notification.
- An unsupported state conclusion publishes `available=False` with undefined value, not the old available conclusion. Event outputs have no latest-value or `previous_cycle` use.
- A resolver may report availability only through a non-empty canonical tuple of Layer-3
  `AutomationSuppressionReason` values authorized by its staged availability contract; an unknown,
  unordered, duplicate, or unauthorized reason rejects the result before emission.
- An episode output has a closed type/phase/value contract and deterministic `episode_key`; it emits no unavailable event and cannot be reconstructed as a current state.
- A state-transition adapter accepts only its staged finite transition table, emits at most one event
  per observed value change, distinguishes `contiguous` from `reconciled_after_gap`, and resets with
  no retained baseline after restart or an impacted reload.
- Initial V3 registers exactly two casa transition adapters (CA4-120): on `occupancy@casa`,
  `present -> absent` emits one `occupancy.departure` and `absent -> present` one `occupancy.return`;
  on `presence@casa`, `home -> away` emits one `presence.departure` and `away -> home` one
  `presence.return`; an unchanged or unavailable value emits none. A guest alone at home after the
  last resident leaves yields `presence.departure` and no occupancy episode.
- `occupied_without_residents` (CA4-122) is `True` for occupancy `present` with presence `away`,
  `False` for `present`/`home`, `absent`/`away` and `absent`/`home`, and unavailable when either input
  is unavailable; it has no transition adapter and raises no notification. The first post-restart available value seeds its baseline without inventing a
  transition. Staging rejects an unregistered initial episode producer or transition table.
- An activity definition resolves only a frozen core `ActivityProfile`; staging rejects an unknown
  profile, illegal scope, an unresolved/mis-typed role binding, a context-only positive route, an
  unauthorized signal, or a requested `inactive` result for a positive-only profile. The initial
  `cooking` profile publishes `active` only from a true cooking-heat-source anchor; kitchen occupancy,
  extractor activity, humidity, a false anchor, an unavailable anchor, or signal absence cannot alone
  publish either `active` or `inactive`.
- The `sleeping` profile accepts an indirect route only from the exact
  `activity.sleeping.indirect.v1` contract with matching room scope, unexpired signal,
  `assertion="active"`, `confidence_kind="routine_affinity"`, and same-room resolved
  `occupancy=present`. A light/clock/charger/low-motion context, a routine signal without occupancy,
  an unknown contract, a stale signal, or an `inactive` assertion produces no sleep conclusion. Direct
  contradictory anchor evidence makes the result unavailable; an indirect result never overrides it.
- `room_occupancy` accepts only `occupancy.room_present.indirect.v1` with
  `assertion="present"` and `confidence_kind="calibrated_probability"`; it still cannot override an
  available `occupancy.physical` result or produce `absent`.
- The `relax` profile accepts only `activity.relax.indirect.v1` with matching room scope, unexpired
  `active` routine-affinity signal, and same-room `occupancy=present`. Tests reject media playback,
  sofa state, light level, clock time, low motion, or a Heima-originated ambience bundle as sole
  evidence; signal absence and every contradictory/unavailable required input produce no conclusion,
  never `inactive` or an action.
- The `working` profile accepts only `activity.working.indirect.v1` with matching room scope,
  unexpired active routine-affinity signal, and same-room `occupancy=present`. Tests require one
  normalized workstation-operational family plus one independent context family; they reject a raw
  desktop value, standard weekday/hour, calendar, computer-active state, communication state, or
  `work_location=office` as a sufficient route, and require no conclusion when the office plan is
  active. A communication-session fact remains independently
  usable by a deterministic policy and never implies `activity.working`.
- A signal-consuming semantic claim cannot feed its own learner's feature/reference/label/target path.
- An impacted reload does not reuse old evaluator state or a conclusion under a new fingerprint.
- A confirmed upstream change that removes `occupancy.physical` for a room invalidates that
  room's `room_occupancy` resolver in the same composed commit; it emits one terminal
  `available=False` `occupancy` fact at the swap and does not run until a successor validates.
  Removing or disabling a resolver likewise closes its state claim; an episode resolver emits
  nothing. No cycle mixes the old Layer-2 generation with the new semantic generation (§8;
  Layer 0 §4.7).
- Semantic resolution, signal resolution, and DAG lookup perform no I/O, dynamic import, HA access, policy lookup, Actuator resolution, or notification delivery.
- Layer 4 contributes only exact availability-owner declarations. Tests reject a policy binding, `automation_scope_id`, visibility state, direct availability event, or Layer-6 delivery call.
- Layer 5 receives only the completed immutable `DecisionSnapshot` and cannot cause a semantic resolver reevaluation or make a resolver inspect policy configuration.
- A staged `state_transition` on a Layer-4 semantic state receives the exact
  previous/current pair after the DAG in the same `DecisionSnapshot`; the
  current semantic fact is never inserted into the Layer-2 intake group.
  Missing previous-cycle state after restart or a changed producer fingerprint
  yields `previous=None`, not an invented transition (§5.1).
- The same barrier freezes recovery state/episode/baselines and current Reaction
  authority into separate opaque views. A retry of one barrier has one
  `snapshot_id`; a changed recovery baseline, state or consent projection
  changes the next snapshot identity. A post-barrier checkpoint commit or
  revocation cannot mutate an already frozen view (§5.1).
