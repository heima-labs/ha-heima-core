# Heima v3 - Layer 5: Action and reaction generation

**Status:** Draft - policy-template foundation approved; reaction workflow details pending.
**Layer:** 5 of 8. Consumes Layer-2 facts and Actuators plus the current-cycle outputs of the completed
Layer-4 semantic DAG. It consumes Layer-3 `LearningProposalCandidate` only as a reviewable proposal
input. It never feeds configuration, policy state, or action results back into Layer 4.

## 1. Purpose

Layer 5 owns the conversion of resolved current semantic claims into a permitted action. It validates
and persists reviewable `ReactionProposal`s, stages configured Reactions, evaluates approved policy
templates, applies action admissibility, and emits one-endpoint `ApplyStep`s. It is the only layer that
may turn a learned proposal into a configured action path.

Layer 5 is downstream of Layer 4, not part of its DAG. The engine runs Layer 5 only after Layer 4 has
resolved the current cycle. It receives the immutable `DecisionSnapshot`: its Layer-2 intake group,
current facts, resolved semantic claims and semantic episodes, generation fingerprints, and Layer-0
`FrozenHistoryView`/`FrozenCalendarView` are all fenced by the same `CycleInputBarrier`. Layer 5
never rereads HA, a mutable buffer, durable history, a live calendar cache, or a later cycle while
processing that snapshot.

## 2. Scope and boundaries

Layer 5 owns:

- the core-owned `PolicyTemplateRegistry` and configured-policy staging;
- validation, deduplication, persistence and review transitions of `ReactionProposal`;
- policy evaluation against `DecisionSnapshot` and bounded Layer-0 windows;
- action admissibility, `ApplyStep` generation and operational audit events.

Layer 5 does not own:

- HA bindings, state interpretation, fact persistence, retention or Topology ownership (Layers 0-2);
- semantic-claim resolution (Layer 4);
- historical learning, model promotion or candidate construction (Layer 3);
- resident-notification rendering/delivery (Layer 6).

`InferenceSignal` remains the separately specified, strictly bounded Layer-3 -> Layer-4 input. It is
not a policy mechanism. The ordinary learned-policy path is unidirectional:

`Layer 3 candidate -> Layer 5 validation/review -> configured policy -> Layer 5 evaluation/action`

## 3. One policy-template mechanism

`PolicyTemplateRegistry` is core-owned, bootstrap-frozen, versioned and O(1). It is not
administrator-configurable or plugin-extensible. There is one evaluator, one configured-policy
persistence path, one action-admissibility phase and one `ApplyStep` protocol. Namespaces such as
`environment.*`, `lighting.*`, and `security.*` identify descriptors of this mechanism, never a
separate rule engine or action protocol.

A new descriptor is justified only when the common contract cannot express its physical scope,
relation profile, guard set, action capability, effect contract or safety limits without weakening
meaning, safety or hot-path performance. Otherwise it extends the existing typed vocabulary.

Before a template-specific payload is considered, the frozen core `ProposalCandidateKindRegistry`
validates the outer candidate contract. It is the sole owner of a candidate kind and its semantic
schema version; it is bootstrap-frozen, not administrator-configurable or plugin-extensible, and is
exposed to Layer 3 only through the existing read-only proposal facet. The initial registry contains
only `("policy.template", 1)`. A later core kind/version requires reviewed code and registry
registration; matching text, a template version, or payload shape never implies compatibility.

```python
@dataclass(frozen=True)
class RegisteredProposalCandidateKind:
    candidate_kind: str
    candidate_kind_version: int
    payload_validator: PureValidator
```

The registry validates the candidate kind/version before dispatching `policy.template` payloads to the
selected `RegisteredPolicyTemplate`. Its version covers the candidate envelope and payload semantics;
the template `version` remains the independent descriptor version for relation profiles, intents,
parameters, guards, effect shape, envelope and translation. Both identities are required and neither
may substitute for the other. Registry lookup and validation remain O(1), pure and free of I/O,
dynamic import, HA access or plugin calls.

```python
@dataclass(frozen=True)
class RegisteredPolicyTemplate:
    template_id: str
    version: str
    supported_profiles: frozenset[str]
    legal_action_intents: frozenset[str]
    max_actuation_members: int
    subject_validator: PureValidator
    relation_profile_validator: PureValidator
    objective_validator: PureValidator
    actuation_bundle_validator: PureValidator
    member_validator: PureValidator
    minimum_practical_delta_validator: PureValidator
    parameters_validator: PureValidator
    envelope_validator: PureValidator
    evaluation_plan_compiler: PureFunction
    required_guards_for_intent: Mapping[str, frozenset[str]]
    effect_contract_for_intent: Mapping[str, EffectShape]
    reaction_translation_contract: PureValidator
    canonicalize_for_dedup: PureFunction
```

The persisted policy-template generation contains only template/version references and canonical data.
Compiled callables exist only in the frozen in-memory generation. A persisted pending
`ReactionProposal` additionally retains the exact candidate kind/version that admitted its transient
input, solely for review/audit compatibility; a configured policy does not retain or consult that
input-contract identity on its hot path. Registry lookup, validation, compilation and evaluation
perform no I/O, dynamic import, HA access, or plugin call.

## 4. Candidate to configured policy

Layer 3 submits the closed `PolicyTemplateCandidate` defined in Layer 3 §6.4 with
`candidate_kind="policy.template"` and `candidate_kind_version=1`. Layer 5 first validates that exact
outer kind/version through `ProposalCandidateKindRegistry`, then validates template/version,
`relation_profile`, objective/member-intent pairing, bounded canonical actuation bundle, each member's
minimum practical delta and outcome unit, subject/opening/Actuator relation, canonical parameters,
required guards, `CanonicalEnvelope`, predicted-effect shapes and deduplication fingerprint. It then
either rejects the transient candidate with a typed diagnostic reason or creates the persisted
`ReactionProposal` for ordinary administrative review.

The persisted proposal records the accepted `(candidate_kind, candidate_kind_version)` together with
the candidate's template/version and canonical deduplication identity. On a registry-generation
change that removes or makes its candidate kind/version incompatible, Layer 5 selectively marks only
the still-pending matching proposals `proposal_incompatible`. That is a terminal non-approvable review
disposition with an audit reason; it never silently substitutes a new kind/version, mutates the
proposal payload, or creates a replacement proposal. A configured policy created before this change
remains governed only by its staged template/version, scope, topology, Actuator and guard contracts:
candidate-kind incompatibility neither disables it nor enters policy evaluation/action. The reload work
is bounded slow-path persistence/workflow reconciliation, never an engine-cycle operation.

An accepted proposal does not become automatic merely because the evidence is strong. It first becomes
a configured policy in `notification_only` mode. Enabling automatic action is a separate authenticated
transition that stages the policy again against the current registry generation, Actuator inventory,
Topology and guard profile. A missing compatible endpoint remains `notification_only` where the
descriptor permits it; a descriptor requiring an endpoint is rejected.

Layer 3 can refresh evidence for the same review item but cannot overwrite its review status, mode,
action scope or guard profile. An incompatible descriptor version requires Layer-5 selective
revalidation; a policy that cannot be revalidated is unavailable, never silently reinterpreted.

## 5. Policy evaluation

### 5.1 Closed relational vocabulary

Every template compiles to one `PolicyEvaluationPlan`: exactly one temporal trigger, a bounded
conjunction of semantic guards, one `CanonicalEnvelope`, and one finite ordered `ActuationBundle`.
Every bundle member names one logical Actuator endpoint and one closed semantic action intent. The core
temporal primitives are:

- `delta_over_window`;
- `rate_over_window`;
- `level_crossing`;
- `state_transition`;
- `occurrence`.

The relation and guards name only typed slots declared by the selected `relation_profile`; they cannot
name arbitrary facts, inspect HA payloads, execute expressions, recursively invoke policies, or create
cross-policy flow. The profile fixes input type/unit, allowed comparison, freshness, window shape and
parameter bounds. Derived physical quantities must be a typed lower-layer fact or resolved semantic
output, never an inline policy formula.

This keeps the ECA trigger-condition-action separation familiar from
[openHAB](https://www.openhab.org/docs/concepts/rules), while deliberately excluding its scripting
surface. The exact guard-operator set and structural bounds are an open Layer-5 decision in §9.

Each compiled plan also declares its finite `HistoryViewRequirement` ids. Layer-5 staging contributes
their union to Layer 0 before activation; a plan whose required short-term history cannot be retained
is rejected at staging. Evaluation reads those exact slices only through the snapshot's
`FrozenHistoryView`, never by issuing an ad hoc historical query.

#### Calendar-plan binding

A policy that needs a future resident plan declares one finite `CalendarPlanBinding`; this is the same
policy-template mechanism, not a Layer-4 state, a fact, or a second calendar interpreter. It names a
staged Layer-0 `CalendarViewRequirement`, an explicit staged Layer-2 `KeywordClassifier`, and one
descriptor-declared intent category. The initial category is `planned_absence`. Evaluation classifies
only the binding's frozen active/upcoming windows and retains only the selected interval and category
for that evaluation; it never stores or exposes an event summary in a proposal, outcome, audit record,
or learner feature.

```python
@dataclass(frozen=True)
class CalendarPlanBinding:
    calendar_requirement_id: str
    classifier_id: str
    expected_category: str            # closed by the selected descriptor version
```

The binding is opt-in per configured policy and has no source-entity or category default. A matching
calendar event says only that an explicit plan exists; it does not imply `presence=away`, authorize an
action, or supersede a manual hold. Removed, edited, expired, or failed calendar input produces no
usable plan in the next frozen snapshot. A descriptor may require a present active plan, an upcoming
plan, or both, but must declare that role at staging and its plan horizon is bounded by the matching
`CalendarViewRequirement`.

Selection is deterministic and conservative. For `planned_absence`, an active matching interval takes
precedence over upcoming intervals; otherwise the earliest matching upcoming start is considered. Exact
duplicate normalized intervals are one candidate. Two selected-rank candidates with different end
instants are `calendar_plan_ambiguous`, so the policy abstains rather than guessing a return time.
The descriptor may provide a core-defined explicit merge rule only where its semantics make that safe;
neither an administrator nor a learner may install one ad hoc.

### 5.2 Snapshot semantics and outcomes

Layer 5 evaluates the trigger against the `DecisionSnapshot.input_fact_group`, its declared
`FrozenHistoryView` slices, and (where declared) `FrozenCalendarView` results; it evaluates every
semantic guard and envelope against that same immutable snapshot. Facts produced by Layer 4 after the input barrier are visible only through
`semantic_claims` or `semantic_episodes`, not as additional Layer-2 trigger members. A plan using
the `occurrence` primitive may name only a declared semantic-episode slot from that collection. A fact
appended later cannot affect that evaluation. This prevents the trigger/condition race documented for
automations that inspect a changed current state after their triggering event in
[Home Assistant](https://www.home-assistant.io/docs/automation/condition/).

```python
PolicyEvaluationOutcome = Literal[
    "not_triggered",
    "guards_unsatisfied",
    "abstained",
    "eligible",
]

@dataclass(frozen=True)
class PolicyEvaluationResult:
    policy_id: str
    template_id: str
    template_version: str
    subject: Location
    snapshot_id: str
    trigger_when: datetime
    outcome: PolicyEvaluationOutcome
    reason_codes: tuple[str, ...]
```

`not_triggered` and `guards_unsatisfied` are ordinary non-notifiable results. `abstained` means a
required semantic input is missing, stale or invalid, or the context lies outside the envelope; it uses
Layer 3 §6.3.1's availability-occurrence contract, with Layer 5 as suppression owner. Only `eligible`
proceeds to action admissibility. It is still not a command and contains neither an `ApplyStep` nor a
raw HA target.

## 6. Action admissibility and execution

For an eligible policy, Layer 5 checks against the same policy/snapshot identity:

- administrative enablement and authorization;
- any descriptor-required resident consent, including its immediate opt-out state;
- manual hold and command ownership;
- compatible logical Actuator capability and confirmed physical state;
- dwell/cooldown and one-bundle-per-policy/snapshot idempotency;
- required safety, security, weather, privacy and quiet-hours guards.

An admissibility failure for any required member means the semantic policy applied but its bundle cannot
currently act. Layer 5 emits the transient `AvailabilitySuppressionOccurrence` defined by Layer 3
§6.3.1 with every applicable closed action-admission reason in canonical order: active manual hold,
unavailable command ownership/capability, unconfirmed physical state, active dwell/cooldown, and/or
an active required guard. It never maps one of these blocks to a learning-evidence reason or omits a
concurrent cause. It constructs that tuple only through Layer 3's frozen pure
`canonicalize_suppression_reasons()` helper; Layer 5 does not choose its own sort order. Layer 5 never
renders, persists or delivers an availability event. The immutable staged
`AvailabilityPublicationIndex` is queried only by Layer 6's `AvailabilityEpisodeTracker`. Layer 5
sends every typed occurrence to that tracker and never selects resident-visible bindings itself; Layer
6 alone owns the resident-visible `automation.availability` event/delivery path.
Before it executes any command, Layer 5 performs the complete member-by-member admissibility pass
against the same immutable snapshot. Thus a known hold, capability, physical-state, dwell or safety
failure on one member prevents the entire bundle: no known-invalid partial execution is permitted.

An admitted bundle yields one ordered `ApplyStep` per member, each addressing exactly one Layer-2
`actuator_id`; the runtime resolves that member's sole HA endpoint. The ordered steps are not a
distributed transaction: after the first service has been sent, HA can still reject or time out a later
one. On such a runtime failure Layer 5 stops the remaining members, records the completed and failed
step identities as one partial bundle outcome, and never issues speculative compensating commands.
Automatic compensation could produce a less safe physical state than the observed partial result. No
member can attach an entity selector, service target, nested policy call, or arbitrary command graph.

### 6.1 Correction attribution evidence

Layer 5 owns the attribution of a resident correction to an action it successfully applied. This is a
strictly narrow Layer-5 -> Layer-3 evidence path: Layer 5 is the only layer that has both the accepted
`ApplyStep` audit identity and the policy/Actuator channel semantics needed to make the association;
Layer 3 consumes the resulting history but may never reconstruct attribution from raw HA state changes.
It is not a feedback command path, a live signal, an action outcome usable by Layer 4, or a generic
cross-layer event bus.

Only after Layer 0's verified `actuator.resident_control` event arrives may Layer 5 consider
attribution and emit one immutable Layer-1 event fact, `actuator.correction`, with
`FactSource.kind="reaction"` and an evidence payload named `CorrectionAttributionEvent`:

```python
CorrectionAttributionEvent = {
    "correction_id": str,                 # stable, non-forgeable event identity
    "classification": Literal[
        "resident_manual_override",
        "external_or_unknown_correction",
    ],
    "actuator_id": str,                   # Layer-2 logical actuator, never an HA entity id
    "controlled_channel": str,            # registered logical capability/channel
    "policy_id": str | None,
    "anchor_apply_step_id": str | None,
    "anchor_completed_when": EvidenceInstant | None,
    "correction_when": EvidenceInstant,
    "attribution_delta_seconds": float | None,
    "deduplication_key": str,
}
```

The event carries the ordinary non-forgeable correlation/source chain separately under the Layer-1
fact envelope. It contains no HA state object, entity identifier, service payload, command target,
resident identity, or mutable runtime buffer. Layer 5 requests its normal append through Layer 1; it
does not own fact persistence, retention, or a private historical store.

The resident-control event and anchor are eligible only when their logical `actuator_id` and
`controlled_channel` match, the anchor is a completed successful `ApplyStep` within the configured
core attribution horizon, and no later successful compatible `ApplyStep` supersedes it. The association
is one-to-one at emission: the most recent unique eligible anchor wins. A raw HA state change,
unavailable transition, or any event other than `actuator.resident_control` is never an attribution
input. Zero or ambiguous eligible anchors produce no
`resident_manual_override` event and a diagnostic reason; Layer 5 must not guess. A verified external,
automation, service, or unknown-origin correction may be recorded as
`external_or_unknown_correction` for diagnostics, but it is never eligible learning evidence for a
resident-correction model. Duplicate reports of one correction share a `deduplication_key` and append
at most one event.

The core attribution horizon and deduplication rule are Layer-5 execution semantics, frozen with the
reaction/action contract rather than chosen by a learner. Layer 3 may declare a shorter analysis
window over the already attributed records, but cannot extend Layer 5's association horizon, relabel
an origin, or attach a correction to another `ApplyStep`. This prevents later learning configuration
from rewriting what occurred operationally.

Administrative enablement and resident consent are separate, conjunctive gates for an automatic
descriptor that declares a resident-consent gate. Both start disabled for a newly configured such
policy; there is no global opt-in. An administrator may enable or disable a policy; an authorized
resident may enable their consent only for an administratively enabled policy and may revoke it at any
time. A revocation prevents admission immediately, cancels the policy's future `AtJob`s, and makes any
already-started execution stop before its next `ApplyStep`; it never compensates a step already sent to
HA. Re-enablement starts a new ordinary evaluation and never replays missed calendar boundaries.

## 7. Initial descriptors

All initial descriptors use the common mechanism above and currently declare a singleton bundle; this
does not create a second execution path. A later core descriptor may declare a bounded multi-member
bundle only through the same registry, validation, review, evaluation and `ApplyStep` contracts:

- `environment.solar_shading`: one compatible cover endpoint associated with the subject opening;
  intents `increase_shading`/`decrease_shading`; objectives `limit_solar_gain`,
  `admit_solar_gain`, and `admit_daylight` only with indoor illuminance; mandatory hysteresis and
  minimum dwell.
- `environment.external_exchange`: one compatible opening endpoint; intents
  `open_for_exchange`/`close_to_retain`; purposes `thermal`, `air_quality`, or `hygrometric`;
  automatic mode requires the descriptor's applicable manual-hold, physical-state, opening-security,
  precipitation, wind and thermal guard capabilities.
- `environment.bathroom_extract`: one room-owned extraction-fan endpoint and no `opening_id`; intent
  `activate_extraction`; initial `humidity_rise_occupied` profile uses positive relative-humidity
  `delta_over_window` and current room occupancy. It predicts humidity reduction, not a synthetic
  shower fact.
- `routine.actuation_bundle`: one room-scoped, finite ordered `ActuationBundle` triggered by one
  declared typed state transition or occurrence and guarded by a closed current-context profile. Its
  template-version-fixed member bound, member capability vocabulary, canonical target schemas and
  execution order are core-owned. It accepts a learned candidate only from
  `ActuationRoutinePatternModel-v1` or an equivalently shaped deterministic configuration; it never
  accepts a raw HA event, entity, service, script, scene payload or arbitrary condition graph. Every
  member remains subject to its own current hold, capability, physical-state, dwell and applicable
  safety/privacy/security guard before the complete bundle is admitted. This descriptor is generic:
  lighting is an expected first use, not a namespace-specific execution mechanism.
- `environment.planned_comfort_trajectory`: one explicit conditioned scope and independently
  registered heating and/or cooling endpoints. It requires a `CalendarPlanBinding` with category
  `planned_absence`, a current resolved `presence=away` claim, an observed `departure` episode that
  began the effective absence, and descriptor-declared comfort/safety bounds. While the plan remains
  valid, it may use only an approved `hvac_thermal_response` parameter to schedule a bounded sequence
  of setpoint changes: in heating season, a controlled decline toward an explicitly configured minimum
  acceptable temperature followed by recovery to the configured return comfort target; in cooling
  season, the symmetric rise toward an explicitly configured maximum followed by pre-cooling to its
  return target. Heating and cooling targets, capabilities and endpoints are independent. It is not a
  fixed setback, a universal comfort default, or a direct thermostat-control implementation.

  A plan change/removal, a `return` episode, loss of `presence=away`, unavailable model/required
  environmental input, manual hold, resident opt-out, or any descriptor safety guard suppresses future
  trajectory steps. Layer 0 arms only the bounded next inflection/boundary `AtJob`; a meaningful
  environmental update may produce a new decision, but the policy never polls. The descriptor is
  unavailable until its model, comfort/safety envelope, heating/cooling capability mapping, and
  acceptance tests are activated. It has no fallback target or automatic behavior when these contracts
  are absent.
- `security.presence_simulation`: a future optional `planned_absence` consumer using the same
  `CalendarPlanBinding`, current `presence=away`, administrative enablement, resident consent, and
  ordinary bundle/hold guards. It may operate only descriptor-allowlisted interior lighting endpoints;
  it is a bounded deterrence aid, never a security guarantee. Its staged temporal profile and bounded
  variation may be core-generated initially and later supplied by the generic approved temporal model;
  it never receives a separate execution path.

These are descriptors, not specialized engines. A deterministic configured Reaction may use any one
of them without a learner; a learner may only propose values permitted by the same descriptor.

## 8. Initial acceptance criteria

- Layer 4 has no dependency on the registry, configured policies, candidates, Reaction proposals or
  action results. Layer 5 receives only its post-DAG immutable snapshot.
- A candidate cannot invoke policy evaluation, Actuator resolution or command generation; only Layer 5
  can persist a `ReactionProposal` or emit an `ApplyStep`.
- `ProposalCandidateKindRegistry` accepts only the exact registered candidate kind/version before a
  template validator runs. Tests reject an unknown kind, a kind with an incompatible version, a payload
  that resembles `policy.template` but lacks its exact `("policy.template", 1)` identity, and a
  template version used as a substitute for candidate-kind compatibility. Changing/removing the core
  kind version invalidates only candidates, Layer-3 bindings, and still-pending `ReactionProposal`s
  that reference it; each pending proposal records its accepted kind/version and moves to the terminal
  non-approvable `proposal_incompatible` disposition. Tests prove that no replacement or payload
  rewrite is created and that an already configured policy remains evaluable when its independent
  template/version, topology, Actuator and guard contracts remain valid; no lookup performs I/O,
  dynamic import, HA access or plugin dispatch.
- A fact appended after a `DecisionSnapshot` cannot change the trigger, guard or envelope result;
  every accepted Layer-2 intake fact sharing its trigger `when` is visible before evaluation, while
  Layer-4 output is visible only through the resolved semantic-claim map.
- Each evaluation has exactly one closed outcome. Only `eligible` reaches bundle admissibility; an
  admitted bundle yields its canonical ordered one-endpoint `ApplyStep`s for `(policy_id, snapshot_id)`.
  A known-invalid member blocks every step; a later HA execution failure stops the remaining steps,
  records a partial bundle outcome, and triggers no automatic compensation.
- An `abstained` evaluation or an eligibility/admissibility failure emits only Layer 3's typed
  `AvailabilitySuppressionOccurrence`, with its complete canonical closed reason set. Tests cover
  unavailable/stale semantic input, unsupported envelope, manual hold, command ownership, actuator
  capability/state, cooldown and action guards; a concurrent hold and safety guard remain two reasons,
  never a fabricated primary reason. Tests prove every permutation of the same causes produces the
  same Layer-3 canonical reason tuple. Every occurrence reaches Layer 6's transient
  `AvailabilityEpisodeTracker` regardless of the current binding set; Layer 5 cannot query the
  publication index, render, persist or deliver `automation.availability`.
- A resident correction is evidence for learning only through one deduplicated, uniquely anchored
  `actuator.correction` event from §6.1. Raw HA state changes, ambiguous anchors and non-resident
  origins cannot become a `resident_manual_override` by a Layer-3 inference or configuration choice.
- Every descriptor uses the same evaluator, persistence path and action protocol. A namespace cannot
  select a custom runtime.
- `CalendarPlanBinding` accepts only its staged calendar requirement, classifier and descriptor-closed
  category. Tests prove a matching future window never implies `presence=away`; a failed, edited or
  cancelled window makes the policy abstain or suppress future steps in the next snapshot; raw
  summaries never reach a proposal, evaluation result, audit record or learner feature. A consent-gated
  policy starts with both administrative enablement and resident consent disabled; either disablement
  prevents admission, resident revocation cancels future `AtJob`s, and re-enablement does not replay a
  missed boundary. Exact duplicate calendar intervals resolve once, while same-rank matching intervals
  with different end instants produce `calendar_plan_ambiguous` and cannot schedule a trajectory.
- `environment.planned_comfort_trajectory` accepts only a matching planned-absence binding, current
  `presence=away`, a qualifying observed `departure`, compatible mode/endpoint and an approved thermal
  response parameter. Tests reject a calendar-only absence, fixed fallback target, missing comfort or
  safety bounds, unapproved/unavailable model, and heating/cooling endpoint conflation; they prove a
  return, plan change, hold, consent revocation or safety block prevents every future step while an
  already sent command is never automatically compensated.
- Staging rejects unknown/incompatible template or relation-profile versions, invalid scope, illegal
  action/guard, unsatisfied endpoint/topology requirements, malformed canonical parameters/envelope, or
  an effect shape outside the descriptor contract.

## 9. Decisions to refine

1. Exact `relation_profile` schema: slot declaration, permitted guard operators, global/profile guard
   limits, canonical units, and the descriptor-to-existing-reason applicability table. New reason
   codes are not a Layer-5 extension point; Layer 3 owns the closed vocabulary.
2. Full `ReactionProposal` persistence/review schema and the general non-policy Reaction contract.
3. Exact `ApplyStep` capability/action mapping for each Layer-2 Actuator role, including the
   per-member execution/audit result shape for a partially completed `ActuationBundle`.
