# Heima v3 - Layer 5: Action and reaction generation

**Status:** Defined V3 action-and-reaction contract. Not implemented.
**Open corrections:** none; CA4-12 closed in Layer 5 §7.3.
**Layer:** 5 of 8. Consumes Layer-2 facts and Actuators plus the current-cycle outputs of the completed
Layer-4 semantic DAG. It consumes Layer-3 `LearningProposalCandidate` only as a reviewable proposal
input. It never feeds configuration, policy state, or action results back into Layer 4.

## 1. Purpose

Layer 5 owns the conversion of resolved current semantic claims into a permitted action. It validates
and persists reviewable `ReactionProposal`s, stages configured Reactions, evaluates them through one
common plan, applies action admissibility, and emits one-endpoint `ApplyStep`s. It is the only layer
that may turn a learned proposal into a configured action path.

Layer 5 is downstream of Layer 4, not part of its DAG. The engine runs Layer 5 only after Layer 4 has
resolved the current cycle. It receives the immutable `DecisionSnapshot`: its Layer-2 intake group,
current facts, resolved semantic claims and semantic episodes, generation fingerprints, and Layer-0
`FrozenHistoryView`/`FrozenCalendarView` are all fenced by the same `CycleInputBarrier`. Layer 5
never rereads HA, a mutable buffer, durable history, a live calendar cache, or a later cycle while
processing that snapshot.

## 2. Scope and boundaries

Layer 5 owns:

- the core-owned `ReactionDescriptorRegistry` and configured-Reaction staging;
- validation, deduplication, persistence and review transitions of `ReactionProposal`;
- policy evaluation against `DecisionSnapshot` and bounded Layer-0 windows;
- action admissibility, `ApplyStep` generation and operational audit events.

Layer 5 does not own:

- HA bindings, state interpretation, fact persistence, retention or Topology ownership (Layers 0-2);
- semantic-claim resolution (Layer 4);
- historical learning, model promotion or candidate construction (Layer 3);
- resident-notification rendering/delivery (Layer 6).

Layer-7 code has no action authority: a plugin cannot create an `ApplyStep`, invoke an Actuator,
register a candidate kind or `ReactionDescriptor`, or stage a custom action path. It may provide
ordinary registered fact producers and diagnostics. It may submit a `LearningProposalCandidate` only
under the exact already-registered core candidate kind and `ReactionDescriptor`; that candidate is
only an input to the normal Layer-5 validation, review and staging workflow. `ApplyStepSource` may
record plugin-related configuration or evidence provenance, but never grants a plugin authority to
apply a command.

`InferenceSignal` remains the separately specified, strictly bounded Layer-3 -> Layer-4 input. It is
not a policy mechanism. The ordinary learned-policy path is unidirectional:

`Layer 3 candidate -> Layer 5 validation/review -> ConfiguredReaction -> Layer 5 evaluation/action`

## 3. One Reaction-descriptor mechanism

`ReactionDescriptorRegistry` is core-owned, bootstrap-frozen, versioned and O(1). It is not
administrator-configurable or plugin-extensible. There is one evaluator, one configured-Reaction
persistence path, one action-admissibility phase and one `ApplyStep` protocol. Namespaces such as
`environment.*`, `lighting.*`, `security.*` and `safety.*` identify descriptors of this mechanism, never a
separate rule engine or action protocol.

A `ReactionDescriptor` is the sole core contract from which a runtime `ConfiguredReaction` may be
staged. Its `authoring_modes` are a non-empty subset of `admin_direct` and `learner_proposal`.
`admin_direct` accepts authenticated typed ECA configuration without a learner candidate or proposal;
`learner_proposal` permits the separate Layer-3 candidate -> `ReactionProposal` -> review path. Both
origins pass the same descriptor validators, compile the same `ReactionEvaluationPlan`, read the same
`DecisionSnapshot`, pass the same action-admissibility phase, and emit the same ordered `ApplyStep`s.
The origin is immutable audit/provenance metadata, never a selector for another evaluator or action
protocol. A descriptor may expose either mode or both, but a learner can never construct a direct
configuration and an administrator cannot bypass the common staging contract.

A new descriptor is justified only when the common contract cannot express its physical scope,
relation profile, guard set, action capability, effect contract or safety limits without weakening
meaning, safety or hot-path performance. Otherwise it extends the existing typed vocabulary.

Before a Reaction-descriptor-specific payload is considered, the frozen core `ProposalCandidateKindRegistry`
validates the outer candidate contract. It is the sole owner of a candidate kind and its semantic
schema version; it is bootstrap-frozen, not administrator-configurable or plugin-extensible, and is
exposed to Layer 3 only through the existing read-only proposal facet. The Initial-V3 registry contains
`("reaction.descriptor", 1)` and `("reaction.artifact_adoption", 1)`.
A later core kind/version requires reviewed code and registry
registration; matching text, a Reaction-descriptor version, or payload shape never implies compatibility.

```python
@dataclass(frozen=True)
class RegisteredProposalCandidateKind:
    candidate_kind: str
    candidate_kind_version: int
    payload_validator: PureValidator
```

The registry validates the candidate kind/version before dispatching
`reaction.descriptor` payloads to the selected `RegisteredReactionDescriptor`
or `reaction.artifact_adoption` payloads to the current Reaction's declared
serving-artifact role. Its version covers the candidate envelope and payload semantics;
the Reaction-descriptor `version` remains the independent descriptor version
for relation profiles, intents, parameters, guards, registered-output
compatibility, envelope and translation. Both identities are required and neither
may substitute for the other. Registry lookup and validation remain O(1), pure and free of I/O,
dynamic import, HA access or plugin calls.

On the canonical JSON wire, `candidate_kind_version` is a positive integer JSON number with no
fraction or exponent; a string, boolean or numeric coercion is invalid. The initial value is the
number `1`. The exact `(candidate_kind, candidate_kind_version)` pair must be registered before
payload dispatch; neither a profile nor a descriptor version can stand in for it.

### 3.1 Versioned relation profiles

`RelationProfileRegistry` is core-owned, bootstrap-frozen, versioned and exposed to Layer 3 only
through the same read-only proposal facet as the `ReactionDescriptorRegistry`. A
`RelationProfileRef` is the shared semantic contract of a `learner_proposal` path and its policy;
there is no separate learner profile and policy profile that can drift apart. It is not a placeholder
for an `admin_direct` Reaction with no learned relation.

```python
@dataclass(frozen=True)
class RelationProfileRef:
    profile_id: str
    version: str

@dataclass(frozen=True)
class RelationEvidenceFacet:
    transition_contract_id: str           # resolves to finite disjoint observed-transition classes
    observation_slot_contracts: tuple[str, ...]
    outcome_contract_id: str              # shape, canonical unit and bounded horizons
    confounder_contract_id: str
    evidence_qualification_contract_id: str  # support, diversity and uncertainty gates
    shadow_requirement: str

@dataclass(frozen=True)
class ReactionGuardContractRef:
    guard_contract_id: str
    version: str

@dataclass(frozen=True)
class RelationPolicyFacet:
    permitted_descriptor_refs: frozenset[tuple[str, str]]
    runtime_slot_contracts: tuple[str, ...]
    permitted_envelope_axes: tuple[EnvelopeAxis, ...]  # subset of each permitted descriptor's axes
    objective_intent_contract_id: str
    guard_contract: ReactionGuardContractRef

@dataclass(frozen=True)
class RegisteredRelationProfile:
    ref: RelationProfileRef
    evidence: RelationEvidenceFacet
    policy: RelationPolicyFacet
    policy_output_schema_id: str
    policy_output_schema_version: str
    policy_output_validator: PureValidator
```

The canonical JSON wire for `RelationProfileRef` is an object with exactly `profile_id` and
`version`, both nonempty strings. `version` is the exact registered token, not a numeric field;
Initial V3 registers token `"1"` for its named profiles. Layer 3 and Layer 5 validate the
complete pair against the same frozen registry. A JSON number `1`, an `@1`-suffixed
`profile_id`, a coerced string, or an unregistered spelling is rejected rather than normalized.
The human-readable `profile_id@version` notation in prose is never the wire form.

The evidence facet is consumed by Layer 3 only: it fixes the physical relation that may be observed,
its typed input slots, outcome shape/horizons and canonical units, exclusions/confounders, evidence
qualification gates, and shadow requirement. The policy facet is consumed by Layer 5 only: it fixes
which descriptor versions may use the relation, the runtime slots the plan may read, compatible
objective/intent pairs, permitted versioned envelope axes and one exact guard
contract. The registered policy-output schema and validator below own the
measured-effect shape, dimension, unit and horizon. A descriptor contributes
its own member vocabulary and eventual semantic-intent translation; a `ReactionGuardProfile`
supplies administrator-configured bindings only through that guard contract. Neither is embedded in a
relation profile.

The versioned `transition_contract_id` resolves to a finite, closed set of
observed-transition classes. Each class has a stable `transition_class_id`,
an exact typed pre/post physical-state matcher, a comparable stable
pre-state reference matcher and, where it corresponds to a descriptor
program, one declared role `start`, `modify` or `terminate`. A modifier's
class also distinguishes direction and bounded pre/post target-change range
for a quantitative modification; the role alone is not a response key.
A complete observed edge matches at most one class; an ambiguous edge is
excluded from learning. Class ids are unique within that exact profile's
transition contract. Existing single-transition profiles declare their one
class as `primary`; there is no implicit missing-class fallback. A profile
with multiple classes uses the same learner and output
contract; no class is inferred from an HA service, last command, actor
identity or device-domain name.

The same frozen `RegisteredRelationProfile` also owns exactly one versioned
policy-output schema and pure validator. Layer 3 publishes only a typed output
validated by this registration, with its exact schema id/version in the artifact
referenced by a candidate; Layer 5 checks the same registration before a descriptor
interprets it. The common hand-off selects the schema by exact
`RelationProfileRef`, never by testing for a thermal, lighting, opening or other
device type. The thermal validator is bound to the core-frozen
`ThermalEvidenceGateCalibration` for the same exact profile version; that
calibration is release metadata, not a learner-produced artifact payload.
Changing schema id/version or validator semantics creates a new profile version
and invalidates incompatible artifacts/candidates rather than silently coercing
them. Initial `thermal_shading`, `solar_shading`, `thermal_exchange`, `air_quality_exchange`,
`hygrometric_exchange` and `humidity_extraction` use the registered `environmental_response.v1` output
shape for bounded response-artifact cells in Layer 3 §4.8.2. This
policy-consumable artifact schema is distinct from Layer 3's per-inference
`ResultEnvelope` and its closed `ResultPayload` union. The schema's exact
cell key includes the registered `transition_class_id` together with profile,
context and outcome horizon. The validator rejects unknown or duplicate
class/context/horizon cells, a transition or reference cohort from another
class, and an eligible estimate without complete class-specific support and
validation. A descriptor consuming an estimate for a program step may use
only that step's declared transition class; it cannot borrow a start estimate
for modification or termination. This completes the Initial-V3 output shape
before runtime artifacts exist; once frozen, changing its class-key meaning
requires a new version. The
`hvac_thermal_response` profile uses `hvac_thermal_response.policy_output.v1`:
its typed parameter remains `ThermalResponseParameter` and its mandatory
core release gate remains `ThermalEvidenceGateCalibration`, with their existing
fields and bounds. The routine relation profile
`RelationProfileRef(profile_id="routine_actuation_bundle", version="1")` registers
`routine.bundle_frequency.v1` for Layer 3 §4.4.3's single
`RoutineBundleFrequencyCell` per bundle/context cell. Its validator matches
the candidate's complete canonical bundle fingerprint, assembly window and
profile/descriptor pair. Each `CoverageCell` in the candidate's supported
envelope must match exactly one eligible output record with the same exact
context key; diagnostic records outside that envelope remain diagnostic and
cannot be promoted by proximity or fallback. The validator checks the keyed
`RoutineValidationReport` against the profile's `RoutineEvidenceGateCalibration` (Layer 3 §4.4.3);
it never accepts a member-frequency substitute. Its evidence facet declares the routine trigger as
one `primary` transition class, the routine confounders of Layer 3 §4.4.3 and
`shadow_requirement="optional_before_proposal"`; its policy facet permits only
`routine.actuation_bundle` and the single objective `reproduce_resident_routine`.
The output-schema version field is `"1"` for these initial
registrations. No administrator, learner instance or plugin may register an
alternate schema or validator.

Profiles contain no Actuator identity, adapter mapping, HA service, raw HA payload, resident setting,
or free expression. They are not administrator-configurable or plugin-extensible. A profile version is
immutable: every candidate, `ReactionProposal`, and learner-origin `ConfiguredReaction` retains the
exact `RelationProfileRef`. A changed evidence facet creates a new learner-definition fingerprint and
cannot reuse the prior artifact or shadow result. A changed policy facet creates a new candidate/review
path; it never rewrites a pending proposal or configured Reaction. A missing or incompatible stored ref
follows the composed-generation impact rule (Layer 0 §4.7, §4.2) and is never substituted by a similarly named
profile.

### 3.2 Reaction guard capabilities and profiles

`ReactionGuard*` is the sole common guard mechanism for every Reaction descriptor,
including environmental, security and routine descriptors. A capability describes
a typed policy input and pure snapshot check; its name does not grant a device or
domain its own guard pipeline. Descriptor versions choose the permitted and required
capabilities through the same staged contract.

`ReactionGuardCapabilityRegistry` is core-owned, assembled at bootstrap from core capability
implementations, versioned and frozen before a Layer-5 generation is active. This is a closed active
registry, not a hard-coded global enum: a reviewed core capability registers its id/version, typed
binding schema, pure snapshot evaluator and redaction contract once. An administrator, learner or plugin
cannot register a capability, supply an evaluator, or attach an expression under a new id.

```python
@dataclass(frozen=True)
class ReactionGuardCapabilityRef:
    capability_id: str
    version: str

@dataclass(frozen=True)
class RegisteredReactionGuardCapability:
    ref: ReactionGuardCapabilityRef
    legal_subject_scopes: frozenset[str]
    binding_validator: PureValidator
    snapshot_evaluator: PureFunction
    redaction_contract_id: str

@dataclass(frozen=True)
class RegisteredReactionGuardContract:
    ref: ReactionGuardContractRef
    permitted_capabilities: frozenset[ReactionGuardCapabilityRef]
    required_capabilities_by_action_variant: Mapping[tuple[str, str], frozenset[ReactionGuardCapabilityRef]]
    # key = (action_intent, descriptor-validated semantic_variant_id)

@dataclass(frozen=True)
class ReactionGuardBinding:
    capability: ReactionGuardCapabilityRef
    canonical_binding: CanonicalJsonObject

@dataclass(frozen=True)
class ReactionGuardProfile:
    guard_profile_id: str
    subject: Location
    initial_generation_id: str

@dataclass(frozen=True)
class ReactionGuardProfileGeneration:
    guard_profile_generation_id: str
    guard_profile_id: str
    generation_index: int                # contiguous per profile, beginning at 0
    subject: Location
    bindings: tuple[ReactionGuardBinding, ...]  # one binding per capability, canonical order
    definition_fingerprint: str
    staged_by: str
    staged_when: EvidenceInstant
```

The initial core registry assembles the following capability ids, each at version `1`:
`opening_security`, `precipitation`, `wind`, `thermal_bounds`, `co2_bounds`, `humidity_bounds`,
`outdoor_air_quality`, `presence`, `privacy`, and `quiet_hours.v1`. The list is a bootstrap registry inventory,
not a `Literal`: a future core entry is added in one reviewed registry registration with a new
contract/version, while existing configurations retain their exact references. `manual_hold`
and `confirmed_physical_state` are not guard capabilities or profile bindings: Layer 5 checks
hold admission and physical confirmation for every affected Actuator channel under §6.0,
independently of the descriptor. Guard entries may expose only their own typed current
`FactRef`/semantic-slot, canonical unit/value and bounded limit fields. No binding may contain
a raw HA object, free predicate, callable, prior value, or fallback.

The core `ReactionGuardCapabilityRef(capability_id="quiet_hours.v1", version="1")`
has one exact, casa-scoped current input: the registered Layer-2 boolean state
`FactRef(fact_type="quiet_hours.active", where=Location(scope="casa"),
previous_cycle=False)`. Its binding contains only that canonical `FactRef`; staging
requires its exact Layer-2 state producer, boolean output contract and current
generation, rejecting a raw HA entity, an arbitrary boolean fact or an unbound
reference. One supported producer is an administrator-selected HA `schedule.*`
helper read through Layer 2's existing `StateReadBinding` and
`MappingInterpretation`: active maps to exact `True`, inactive to exact `False`,
and unavailable/uninterpretable to `available=False`. The helper owns its civil
schedule and DST behavior; Heima adds no recurrence engine for this input.
The pure evaluator reads the frozen current `DecisionSnapshot`: `False` passes,
`True` vetoes, and an unavailable, stale or non-boolean value also vetoes as
`action_guard_active`. It neither checks Layer-6 delivery policy nor reads a
room-scoped `activity.sleeping` claim as a house-wide quiet-hours assertion.
Only a descriptor version whose exact guard contract requires this capability
for an action variant applies the veto; no global action block or administrator-added
ad hoc condition is created. The Initial-V3 descriptors retain their existing
required-capability sets unless their own versioned contract explicitly names it.

The Initial-V3 direct descriptor guard contract is
`ReactionGuardContractRef(guard_contract_id="security.presence_simulation.interior_lighting.v1",
version="1")`. It permits only `ReactionGuardCapabilityRef(capability_id="presence",
version="1")` and requires that same capability for its sole
`(light_state, default)` action variant. It introduces no new capability or
evaluator.

`environment.solar_shading` uses one guard contract for its direct path and for both of its learned
relation profiles: `ReactionGuardContractRef(guard_contract_id="environment.solar_shading.guards.v1",
version="1")`. It permits `wind`, `precipitation`, `thermal_bounds`, `privacy` and
`quiet_hours.v1`, each at version `1`. Its action variants and required sets are:

| Variant `(action_intent, semantic_variant_id)` | Required capabilities |
|---|---|
| `(increase_shading, default)` | `thermal_bounds` |
| `(increase_shading, exterior_deployable)` | `thermal_bounds`, `wind`, `precipitation` |
| `(decrease_shading, default)` | `thermal_bounds` |

The descriptor derives `exterior_deployable` exactly for `increase_shading` on a cover whose staged
Actuator is `weather_exposed` (Layer 2 §6); every other member is `default`. Retracting an exterior
cover is never blocked by wind or rain. `privacy` and `quiet_hours.v1` are optional bindings an
administrator may add; they introduce no new capability or evaluator.

A `wind` or `precipitation` binding is either a typed numeric reading with a bounded limit or an
exact Layer-2 boolean hazard state, where `True` vetoes. When a channel is covered by a
`safety.weather_protection` Reaction for that hazard, every staged opposing action variant on the
channel must bind the capability to exactly that Reaction's hazard state (§7.4), so the hazard has
one threshold owner and the opposing action is vetoed for exactly as long as the hazard lasts.

`environment.external_exchange` likewise uses one contract for its direct path and its three
learned profiles: `ReactionGuardContractRef(guard_contract_id="environment.external_exchange.guards.v1",
version="1")`. It permits `opening_security`, `precipitation`, `wind`, `thermal_bounds`,
`outdoor_air_quality`, `co2_bounds`, `humidity_bounds`, `privacy` and `quiet_hours.v1`. The
`semantic_variant_id` is the staged purpose:

| Variant | Required capabilities |
|---|---|
| `(open_for_exchange, thermal)` | `opening_security`, `precipitation`, `wind`, `thermal_bounds` |
| `(open_for_exchange, hygrometric)` | `opening_security`, `precipitation`, `wind`, `thermal_bounds` |
| `(open_for_exchange, air_quality)` | `opening_security`, `precipitation`, `wind`, `thermal_bounds`, `outdoor_air_quality` |
| `(close_to_retain, thermal)`, `(close_to_retain, air_quality)`, `(close_to_retain, hygrometric)` | none; `close_to_retain` is in the descriptor's `safe_direction_intents` |

`environment.air_extraction` uses `ReactionGuardContractRef(guard_contract_id=
"environment.air_extraction.guards.v1", version="1")` for its direct path and its learned profile.
It permits `quiet_hours.v1`, `presence` and `privacy`, each optional. Its variants
`(activate_extraction, default)`, `(adjust_extraction, default)` and `(stop_extraction, default)`
require none: `activate_extraction` and `adjust_extraction` are `low_risk_intents` (rationale: a room
extraction fan moves air out of the room it serves and creates no exterior, security or thermal
hazard; requiring presence would wrongly block extraction after the resident leaves), and
`stop_extraction` is a `safe_direction_intents` entry.

`safety.weather_protection` uses `ReactionGuardContractRef(guard_contract_id=
"safety.weather_protection.guards.v1", version="1")`. It permits no capability and its sole variant
`(secure_for_weather, default)` requires none: `secure_for_weather` is in the descriptor's
`safe_direction_intents`, and a protective action must not depend on an optional binding.

`routine.actuation_bundle` uses `ReactionGuardContractRef(guard_contract_id=
"routine.actuation_bundle.guards.v1", version="1")` for its direct path and its learned profile. It
permits `presence`, `privacy`, `quiet_hours.v1`, `opening_security`, `precipitation` and `wind`. Every
member variant requires `presence`, whose binding references the casa `presence` claim (Layer 4
§9.2) even for a room-scoped Reaction: a routine never acts while the house is away. A member also
requires the safety capabilities that an environmental descriptor requires for the same physical
action, so a routine cannot bypass them: `open_for_exchange` adds `opening_security`,
`precipitation` and `wind`; `increase_shading` on a `weather_exposed` cover (variant
`exterior_deployable`) adds `wind` and `precipitation`. These apply only where the routine descriptor version admits
that intent. A bundle requires the union of its members' sets (above).

Every relation profile names one exact `ReactionGuardContractRef`. An `admin_direct` descriptor
with no relation profile instead names one exact descriptor-level guard contract. In either case the
frozen contract defines the capabilities the configuration may use and the subset required
for each action variant. That subset is non-empty, except for a variant whose `action_intent` the
descriptor declares in `safe_direction_intents`, such as closing an exterior opening, or in
`low_risk_intents`, such as starting a room extraction fan, with a registered rationale: neither
moving toward the safe physical state nor an intrinsically low-risk action needs a descriptor veto,
while hold, physical confirmation, ownership and channel arbitration still apply under §6.0. A
low-risk declaration is a reviewed descriptor-version fact, never an administrator setting. The variant key is a frozen pair of the existing
`action_intent` and a finite descriptor-version-owned `semantic_variant_id`.
The descriptor's existing parameter/member validators derive exactly one
variant from staged typed parameters; a descriptor with no variation uses
`default`. For `environment.external_exchange`, the variant is its staged
`thermal`, `air_quality` or `hygrometric` purpose, so the same
`open_for_exchange` intent can have purpose-appropriate guards. No raw
parameter value, arbitrary administrator label or runtime heuristic can
create a variant. Registration rejects a missing, extra or duplicate key,
and requires the descriptor and selected guard contract to agree on the
required set for every variant permitted by that selected policy source. For a bundle, the required
capabilities are the union of its validated member-variant sets; every
member still passes its own current guard and whole-bundle admission. A
descriptor may require only entries permitted by its applicable contract; a
learner candidate may carry only that exact required set, never a threshold or a new capability. A
profile generation is valid only when it has exactly one validator-approved binding for every capability
required by a Reaction configuration; an extra binding is permitted only when its capability is also
permitted by that configuration's contract.

The root and its generations are immutable and append-only. Profile creation atomically persists one
root and generation index `0`, or neither; a retry returns that complete aggregate. A reaction
configuration and its evaluation plan retain the exact `(guard_profile_generation_id,
definition_fingerprint)` and the canonical required capability refs. Changing a binding creates a new
guard-profile generation; it cannot silently change an active reaction. A configuration that adopts it
is a new `ReactionConfigurationGeneration` under §4.2, starts `notification_only`, cancels predecessor
jobs and requires ordinary revalidation/promotion.

At evaluation every required capability reads only the immutable `DecisionSnapshot` through its registered
pure evaluator. `pass` is required from all of them. A missing, stale, invalid, out-of-limit or
unconfirmed required guard input, and every failed guard, prevents automatic application and
contributes only `action_guard_active`. A hold instead contributes `manual_hold_active`;
unverifiable physical state contributes `actuator_state_unconfirmed`. These common gates never
become descriptor guard failures or add `action_guard_active` solely for the same condition. A
capability may produce bounded redacted diagnostic detail under its contract, but cannot bypass a manual
hold or the shared command-ownership arbitration in §6. Safety/security guards are independent
vetoes; they are not an implicit right to preempt another writer.

#### Registered output and bundle contracts

```python
DelayGapSemantics = Literal[
    "continuous_observed",      # any observation break invalidates elapsed dwell
    "accumulated_observed",     # suspend during a break; retain verified elapsed dwell
    "elapsed_if_requalified",   # credit elapsed gap only after a fresh compatible state
]

ActuationBundle = tuple[CanonicalJsonObject, ...]

@dataclass(frozen=True)
class RegisteredReactionDescriptor:
    reaction_descriptor_id: str
    version: str
    requires_household_consent: bool
    supported_profile_refs: frozenset[RelationProfileRef]
    direct_guard_contract: ReactionGuardContractRef | None
    authoring_modes: frozenset[Literal["admin_direct", "learner_proposal"]]
    permitted_envelope_axes: tuple[EnvelopeAxis, ...]  # bounded, ordered, versioned slot/partition refs
    permitted_direct_envelope: CanonicalEnvelope | None
    # None iff no profile-free admin-direct path; otherwise exact bounded direct axes/cells
    legal_action_intents: frozenset[str]
    delay_timer_paths: Mapping[str, frozenset[DelayGapSemantics]]
    max_actuation_members: int
    subject_validator: PureValidator
    relation_profile_validator: PureValidator
    objective_validator: PureValidator
    actuation_bundle_validator: PureValidator
    member_validator: PureValidator
    minimum_practical_delta_validator: PureValidator  # validates optional member requirement against exact descriptor/profile
    parameters_validator: PureValidator
    envelope_validator: PureValidator
    evaluation_plan_compiler: PureFunction
    program_evaluator: PureFunction | None  # registered evaluate_program implementation for step-programmed versions
    normal_exit_contract: PureFunction | None
    managed_episode_resumption: bool  # versioned; requires an ongoing program
    program_family: ProgramFamilyRef | None  # shared activation/exit rules (§3.2 Program families)
    hold_release_mode: Literal["fixed_duration", "next_reaction_step"]
    safe_direction_intents: frozenset[str]  # intents moving toward the safe physical state (§3.2)
    low_risk_intents: Mapping[str, str]     # intent -> registered rationale for no required guard (§3.2)
    advisory_intents: frozenset[str]        # intents a member may deliver as resident advice (§3.2)
    resident_action_notice: bool            # notify residents of completed commands (§6.0)
    execution_audit_codes: frozenset[ReactionExecutionAuditCode]  # §4.0; subset this version may emit
    required_guards_for_action_variant: Mapping[tuple[str, str], frozenset[ReactionGuardCapabilityRef]]
    admission_reason_applicability: Mapping[str, str]
    reaction_translation_contract: PureValidator
    canonicalize_for_dedup: PureFunction
```

For a learned candidate, the exact `RelationProfileRef` selects its sole
`policy_output_schema_id/version` and validator (§3.1). The validator checks
the profile's declared outcome shape, dimension, canonical unit, horizon and
bounded measured values; the profile's objective/intent contract and the
descriptor's member/threshold validators separately check policy meaning.
Layer 5 invokes that registered validator without interpreting the
Layer-3-only evidence facet or projecting another effect-summary type.
The environmental output preserves its numeric point estimate, conservative
interval and positive horizon in the profile's outcome unit (Layer 3 §4.8.2).
The thermal output preserves ordered minimum, conservative and maximum
recovery durations as Layer-0 `Window` values (Layer 3 §4.8.1). The routine
output preserves one whole-bundle/context record with conditional and
baseline probabilities in dimensionless unit `1` and a `Window` assembly
duration (Layer 3 §4.4.3). No measured value is copied onto a routine member.
Its separate support, lift and temporal validation gates remain required;
zero baseline is diagnostic and cannot support a proposal-eligible routine.
Staging rejects a candidate whose primary artifact has the wrong schema,
variant, unit, ordering, horizon, bundle/context identity or intent mapping.
A compatible evidence refresh may
change measured values without changing the immutable candidate payload or
its fingerprint. The profile's practical-effect and uncertainty gates remain
separate from shape validation.

`ActuationBundle` is the finite ordered tuple of descriptor-validated
canonical member objects in a compiled Reaction plan. Each member's closed
schema names one logical `(actuator_id, controlled_channel)`, one registered
semantic intent and its typed parameters; the descriptor caps count and
rejects duplicate channels before execution. The Layer-3 proposal uses
`ActuationMemberCandidate` for the reviewable form and compiles it to this
same bundle contract after review. Both forms retain order and use the one
`ApplyStep` path; neither is a raw HA call list.

`supported_profile_refs` is non-empty for every descriptor that permits `learner_proposal`; an
`admin_direct`-only descriptor may have an empty set. `direct_guard_contract` is required precisely
when a descriptor permits an `admin_direct` configuration without a relation profile, and otherwise is
absent. A descriptor supporting both origins declares both its supported learner-profile set and its
direct guard contract. The descriptor compiler selects exactly one of these immutable policy sources
from the configuration origin in addition to the descriptor's base grammar;
it never synthesizes a fake relation profile or a second evaluator.
The descriptor version's existing pure validators and `evaluation_plan_compiler`
are the common, frozen source of its legal runtime slot bindings, slot
types/units, temporal-plan shape, comparisons, parameter bounds, bundle
grammar and `permitted_envelope_axes`. Each named axis resolves a staged
current `FactRef` or semantic slot and one core-owned, pure versioned
partition with a finite bucket vocabulary; registration rejects an unknown
slot/partition, wrong input type/unit, duplicate axis, unbounded bucket or
cell count, or a partition whose declared output is not total over its valid
input domain. The descriptor's `permitted_direct_envelope` is non-null
exactly when it supports a profile-free `admin_direct` path. It is one
finite `CanonicalEnvelope` with direct evidence fields exactly `None`;
its axes are a fixed ordered subset of that descriptor version's
`permitted_envelope_axes`, and its nonempty cells conform to those exact
axes and bucket vocabularies. A zero-axis direct envelope has exactly the
one empty-key cell `{()}` even when the descriptor permits nonempty axes
for learned profiles. The descriptor compiler may register that form only
when its closed typed trigger, conditions and required guards already
delimit action without an extra context partition; the empty key never
means that missing trigger or guard evidence passes. Runtime evaluates the
envelope's own frozen axes, not every axis the descriptor permits in other
origins. Administrators cannot add an
axis, partition, comparison or runtime slot through configuration. For a
`learner_proposal`, the selected relation profile's policy facet further
restricts the descriptor's slots, objective/intent pairing, guard contract
and envelope axes; neither source may widen the other. For an `admin_direct`
generation with no relation profile, the descriptor supplies the whole
non-guard plan grammar and its exact `direct_guard_contract` supplies guard
capabilities. The same compiler and evaluator validate both origins.

For a step-programmed descriptor, `program_evaluator` is required and is the
developer-implemented, core-registered pure `evaluate_program` specialization
for that exact descriptor version. Its `evaluation_plan_compiler` persists
only canonical parameters and typed bindings in `ReactionEvaluationPlan`;
the plan contains no callable. Layer 5 resolves the implementation from the
frozen descriptor/version registry and calls it once per evaluation attempt
with that plan, the current `DecisionSnapshot`, the current activation state
(or no activation before start), and any validated current boundary token
from §6.0. Its closed decision is one of `not_started`,
`ongoing`, `normal_exit`, or `abstained`, and carries at most one selected
current step per affected channel, at most one next timed boundary for the
activation, and the existing `ReactionNormalExitResult` only for
`normal_exit`. If a descriptor declares a final target at normal exit, that
same decision carries either its one selected terminal step with a complete
target per affected channel or the declared terminal step identity and a
typed reason why its target is currently unavailable. The latter is a
`terminal_action_skipped` result, not an `ended_without_final_target`
policy. Layer 5 does not compute a second target from the exit result. A selected
step has a stable `planned_step_id`, a complete
typed canonical target and parameters, and `boundary_kind="timed"|"event"`;
an event step names
only a staged typed current-snapshot event or state transition. An event
does not create a second Reaction trigger. The compiled rule evaluates
start, changes of target during an activation and end from the same frozen
inputs. The descriptor specialization decides which step and target to
propose; Layer 5 validates its closed output and alone performs common
authority, guard, hold, ownership, translation and `ApplyStep` admission.
For each finite programmed step kind, the frozen descriptor/plan declares
whether target selection needs no learned response estimate or an eligible
`environmental_response.v1` cell for one exact registered profile,
`transition_class_id`, context and horizon. A missing, invalid, unsupported
or out-of-context required cell suppresses that step; another class,
neighboring context or remembered target cannot fill the gap. The same
`evaluate_program` may still select an independently declared deterministic
step from fresh current inputs, including a normal-exit terminal step, but
cannot invent a fallback target at runtime. Verified normal exit remains
valid if its estimate-dependent terminal target is unavailable: that command
is skipped and reported by the existing terminal follow-up path (§6.2).
Suppressing an ongoing step does not implicitly close the activation. Every
selected step still passes current authority, guards, hold, physical-state
and whole-channel admission. For a learned multi-step proposal, staging
must validate how its reviewed objective and intent bind to each
estimate-dependent step; the Initial-V3 `humidity_extraction` mapping binds
`reduce_moisture` to its `start` and `modify_up` classes and treats `terminate` as diagnostic (§7).
For an estimate-dependent target modification, the specialization must also
find a currently qualifying need under its staged typed conditions and an
eligible response for the exact proposed physical transition whose
profile-declared direction and conservative bound meet the reviewed
objective and `minimum_practical_delta`. Historic response alone never
selects a step. The developer declares the legal target range, conditions
and step-to-class mapping, not a fixed amount of physical improvement or a
list of later targets presumed necessary. Current adequacy or a failed
estimate gate suppresses that modification; it does not rewrite the
descriptor's independently declared normal-exit rule. The same requirement
applies to any actuator kind; Layer 5 has no speed, position or valve-specific
decision branch. A class estimate establishes neither causal effect nor the
result of the complete multi-step program.
Descriptor-specific parameters and comparisons are staged data, never an
administrator-supplied callable or HA script. A one-shot descriptor declares
`program_evaluator=None` and follows its existing single-trigger path.

When an event and a timed boundary are both relevant in one cycle, the
compiled descriptor rule returns one effective target and step identity per
channel. Its version must declare a deterministic resolution over those
inputs; registration rejects an unresolved combination and runtime
abstains on an invalid or ambiguous result. It may return no current step
while retaining a next timed boundary. Layer 5 alone mints or retains the
activation id, enforces step-id idempotency, applies common guards, hold and
ownership admission, and translates an admitted target through the one
`ApplyStep` path. It never dispatches directly from this pure result.
`requires_household_consent` is an exact, frozen descriptor-version property. The
registry rejects a missing or non-boolean value. All seven
Initial-V3 descriptor registrations declare `True`:
`environment.solar_shading`, `environment.external_exchange`,
`environment.air_extraction`, `environment.planned_comfort_trajectory`,
`security.presence_simulation`, `routine.actuation_bundle` and
`safety.weather_protection`. This records
the choice for each descriptor;
future descriptor versions must declare their own value instead of inheriting a
global default. Consent is a common authority gate, not a `ReactionGuardCapability`.
`hold_release_mode` is fixed by the core descriptor version, not configured by an administrator,
learner or observed device. `next_reaction_step` requires both a non-null `normal_exit_contract` and
a bounded future step identity contract from the descriptor's evaluation-plan compiler (§6.0),
covering every declared timed or event-driven step. An event-driven step that
can release this hold must also declare a typed current-state continuation
condition that can be checked again after the preliminary release; an
isolated event without such a condition is not a release-capable step;
staging rejects a descriptor/configuration that cannot meet these requirements. Only
`fixed_duration` requires the Actuator's positive `hold_duration` (Layer 2 §6.1).
`delay_timer_paths` is the closed per-descriptor-version list of timing paths
and allowed gap-time meanings. Its compiler must select one permitted meaning
for every delayed Reaction plan; an empty mapping permits no delayed path.
For the irradiance-triggered solar-shading path the only permitted meaning is
`elapsed_if_requalified`. The `routine.actuation_bundle` room-vacancy path
registered in §7 permits only `elapsed_if_requalified`; other paths need
their own explicit registration before staging a delayed Reaction.

```python
ReactionNormalExitOutcome = Literal[
    "not_ended", "normal_cancellation", "natural_completion"
]

@dataclass(frozen=True)
class ReactionNormalExitResult:
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str
    snapshot_id: str
    outcome: ReactionNormalExitOutcome
    evidence_fingerprint: str | None
```

`normal_exit_contract` is the versioned, core-owned terminal rule used by
the descriptor's `evaluate_program` implementation. Layer 5 never invokes it as
a second action evaluator. It examines one active Reaction activation, its
configured generation and frozen, typed inputs. An
activation is one execution episode of a configured Reaction: Layer 5 mints
one opaque `reaction_activation_id` when the descriptor's
validated start criteria first become true (or its one-shot trigger fires),
and retains it through re-evaluations and timed steps of that sequence.
The id is live only during that process activation but is collision-resistant
across process restarts as well: a new run must never deliberately reuse a
prior id under the same Reaction/generation. The durable follow-up records in Layer 0's notification outbox
therefore cannot mistake a new post-restart activation for a retry of an old
channel boundary (§6.0). No live activation is restored from that durable id.
V3 permits at most one active activation per configured Reaction generation:
repeated qualifying cycles while it is active reuse its id. A replacement
plan closes the old activation before a fresh cycle may start another and
admit its commands. A programmed activation closes under the descriptor's
verified end criteria; a one-shot execution retires after its command outcome without treating that
retirement as a normal exit or releasing its fixed-duration hold. The hold
keeps the original activation id until its own release. A later qualifying
start receives a new id under the same still-authorized configuration.
Temporary input loss or a guard veto neither ends the activation nor mints
another id. A restart
forgets live activations; a fresh current-policy start receives a new id and
restores no hold or missed step. For a one-shot trigger, the id still anchors
its confirmed target and possible fixed-duration hold; completion of its
command does not make a normal exit.

`managed_episode_resumption=True` is permitted only for a descriptor whose
version declares an ongoing program, a verifiable initial inactive-to-active
transition, current continuation/end rules and bounded step identities. Its
one-shot version cannot opt in merely because its target was reached. Layer 5
requires that descriptor's staged admission-reason applicability to include
`active_channel_unmanaged_after_restart` and an exact Layer-6 availability
publication binding for each resumable channel; a multi-channel descriptor
must provide distinct staged suppression scopes for its channels. An
automatically authorized resumable Reaction requires an enabled,
resident-visible binding for this cause; publication staging rejects a
missing binding. Layer 5
opens the Layer-0 §5.1.1.2 projection only after a fresh inactive entry and a
subsequent physical active edge linked to its own admitted `ApplyStep`.
`already_satisfied`, an HA service acknowledgement, a partial target match,
an external actor's identical target and an unavailable-to-active reading
never open it. It closes the projection at verified normal program end,
configuration-generation replacement or authority revocation. The live
activation and its jobs still end under the existing rules.

After restart, Layer 5 reads only the latest committed managed-episode
projection for the staged channel. An `open` value is usable only if its
Reaction and generation are still configured and authorized, the current
descriptor still permits resumption, a fresh current channel reading is
active and valid, and the current continuation/end rules still select an
ongoing program. Layer 5 creates a new activation id and recomputes current
steps and targets from current inputs; it does not restore a prior activation,
hold, due job, step or missed command. Every new `ApplyStep` passes normal
guards, hold and physical-state admission. If the fresh state is inactive,
the stored episode is closed using its stored opening identity and ordinary
current start evaluation applies. Any later fresh inactive-to-active Heima
start creates a new opening identity; it cannot overwrite an old open episode
without closing it first.
If the marker is absent, closed, malformed, uncommitted or fails the current
continuation checks, an active channel is not claimed or changed by this
descriptor. Under that no-proof condition, at every process restart, if the
first fresh valid channel observation is active, an automatically authorized
Reaction with `managed_episode_resumption=True` reports
`active_channel_unmanaged_after_restart` through the ordinary
`AvailabilitySuppressionOccurrence` path (Layer 3 §6.3.1), regardless of
whether its start trigger currently qualifies. This is a separate
current-state availability check in the ordinary evaluation pass; it mints
no activation id, target decision or `already_satisfied` anchor and does not
change a `not_triggered` Reaction evaluation result. Layer 6 renders the
resident notice and owns delivery; Layer 5 cannot infer who activated the
device. If authorization becomes effective later in the same process while
that initially observed active channel remains active, the check publishes
the issue then; an authority revocation closes its resident publication
through the normal administrative path. Once raised, the suppression remains
active while that channel is observed active without usable proof. It ends
on a fresh observed inactive state or verified management proof; Layer 6's
`restored` notice must not imply that Heima switched the channel off. A
configuration or authority removal closes the publication binding through
the existing administrative reconciliation, without a false physical
restoration. Initial unreadability waits for the first valid observation;
if that observation is inactive, this restart produces no unmanaged-active
notice. A later in-process active edge follows ordinary origin, target and
hold rules, not this restart warning. The process gap never supplies a
Layer-3 complete learning sample.

The rule returns one `ReactionNormalExitResult`; its identity must match the
current activation, generation and frozen snapshot being evaluated. `not_ended`
has no evidence fingerprint; a terminal outcome has a nonempty fingerprint of
the descriptor-validated canonical evidence projection, never a raw HA payload
or personal identity. `None` means the descriptor has no provable normal-exit
boundary. A normal cancellation needs an explicit
descriptor-declared cancellation signal; natural completion needs proof that
the descriptor's program has no remaining step or ongoing target. Missing or
temporarily unavailable input, a failed guard, completion of one `ApplyStep`,
and ordinary re-evaluation all return `not_ended`. Administrative disablement,
consent revocation and other immediate authority loss use the separate
revocation path, never this rule. The rule's evidence sources and terminal
conditions are fixed by the descriptor version and validated at staging; an
administrator or learner cannot supply executable exit logic. Layer 5 alone
accepts the compiled evaluator's terminal result and submits an authorized
terminal result to Layer 0; the
result closes only that activation, not the configured Reaction's future
eligibility. It is not a separate trigger, `HouseFact`, or admin command.

The persisted descriptor generation contains only descriptor/version references and canonical data.
Compiled callables exist only in the frozen in-memory generation. A persisted pending
`ReactionProposal` additionally retains the exact candidate kind/version that admitted its transient
input, solely for review/audit compatibility; a `ConfiguredReaction` does not retain or consult that
input-contract identity on its hot path. Registry lookup, validation, compilation and evaluation
perform no I/O, dynamic import, HA access, or plugin call.

`admission_reason_applicability` is a closed declaration, validated at bootstrap and staging, rather
than an extension point for Layer-5 reason strings. Its complete core mapping is:

| Admission gate | `AutomationSuppressionReason` |
|---|---|
| active manual hold | `manual_hold_active` |
| unavailable command ownership | `command_ownership_unavailable` |
| absent or incompatible registered channel, target contract, or actuation adapter | `actuator_capability_unavailable` |
| unavailable or unverifiable endpoint/channel state | `actuator_state_unconfirmed` |
| active channel lacking managed-episode proof after restart, for a descriptor that declares resumption | `active_channel_unmanaged_after_restart` |
| active dwell or cooldown | `cooldown_active` |
| any required safety, security, weather, privacy, quiet-hours or descriptor guard | `action_guard_active` |

The descriptor declares only the conditional gates its contract can require; each declared gate
must map to exactly the corresponding row above. The common hold and physical-state gates are
always applied to every affected Actuator channel, even when absent from a descriptor declaration.
A descriptor cannot rename, omit, prioritize, or introduce a suppression reason.
Missing or revoked required household consent, and administrative disablement,
are authority states rather than availability suppression: they block every
automatic `ApplyStep` and future job, but produce no
`AvailabilitySuppressionOccurrence` or `action_guard_active` solely for that
state. The current effective mode remains visible as `notification_only` or
`authorized_awaiting_household_consent` in the authority projection. A
concurrent consent revocation is checked again at the per-step execution fence.

If HA has not supplied a fresh valid state after restart, no endpoint command is admitted.
If only one registered channel is unreadable, this gate suppresses that channel while other
readable channels remain eligible. After the channel returns, its first valid read establishes
the new observation epoch rather than a hold; current Reaction, guards, and ownership are
re-evaluated. An already satisfied complete target records `already_satisfied` without a call;
otherwise the ordinary guarded plan may dispatch. No missed step is replayed merely because
the channel became readable.

`outside_operating_envelope`, `artifact_stale`, `artifact_incompatible`,
`missing_required_input`, and `stale_required_input` remain pre-admission evaluation/evidence causes;
they never describe an action that reached this phase. An invalid configuration, authorization, or
descriptor/Actuator incompatibility found at staging or proposal review is instead a typed staging or
review diagnostic, never a runtime availability occurrence.

#### Member delivery: command or advice

Every bundle member declares `delivery`: `command` (the default) produces the ordinary `ApplyStep`;
`advice` produces a resident-facing suggestion instead, through Layer 6, and never an
`ApplyStep`. An advice member is legal only for an intent in the descriptor version's
`advisory_intents`. It may name an Actuator the administrator prefers to leave to the resident, or,
for an opening without an Actuator, only an `opening_id` for which `opening_faces_exterior` holds
(Layer 1 §7); a command member always needs an Actuator. Advice members pass the same staging,
trigger, conditions, envelope and guards as command members, but no hold, command-ownership,
physical-state or arbitration gate, because they move nothing. Initial-V3 `advisory_intents` are
`open_for_exchange` and `close_to_retain` (`environment.external_exchange`) and `increase_shading`
and `decrease_shading` (`environment.solar_shading`); every other Initial-V3 descriptor declares
none.

**Delivery depends on authority, not only on the member.** In `notification_only` a Reaction
issues no command and no resident-facing notification: its evaluations feed only the
administrator's read-only preview. Advice is delivered once the Reaction is administratively
authorized; household consent gates only command members, because advice moves nothing. Each
eligible advice member produces one `ReactionAdvisoryOccurrence(opened)` per activation (§6.0), not
one per evaluation, and one `closed` occurrence when the activation ends; the closing phase is never
delivered to residents as a "no longer needed" notice.

#### Program families

A **program family** is a core-owned, versioned set of activation, continuity, exit and restart
rules that several step-programmed descriptors share. It is written, validated and tested once,
and each descriptor version that declares it inherits it instead of restating it. It is not a
second evaluator, scheduler or action path: a descriptor still registers its own pure
`program_evaluator`, which calls the family's pure component on the same frozen snapshot and then
plans only its own steps and targets.

```python
@dataclass(frozen=True)
class ProgramFamilyRef:
    family_id: str
    version: str                      # exact registered token, e.g. "1"

@dataclass(frozen=True)
class AbsenceProgramState:
    effective_absence: bool | None    # None: undecidable (calendar failed or presence unavailable)
    selected_interval_start: EvidenceInstant | None
    selected_interval_end: EvidenceInstant | None
    exit: ReactionNormalExitOutcome   # "not_ended" unless the family proves an exit
    evaluation_requested_by_departure: bool
```

`ProgramFamilyRegistry` is bootstrap-frozen and closed to administrators, learners and plugins.
A descriptor version names at most one exact `ProgramFamilyRef`; changing family behavior creates
a new family version, which each declaring descriptor adopts only through its own new version.
Staging rejects a declared family whose requirements below are not met, and a descriptor cannot
override a family rule.

**`planned_absence_program`, version `"1"`.** For every declaring descriptor:

1. **Calendar binding.** The configuration has exactly one `CalendarPlanBinding` with
   `expected_category="planned_absence"` (§5.1), selected by the binding's union rule.
2. **Effective absence.** True only when a selected planned-absence interval is *active* (never
   merely upcoming) and the current casa `presence` claim is a committed `away` (already
   stabilized by the Layer-2 fusion). Staging also requires the casa presence `FusionRule` to
   declare a non-null `Stability.to_true`: this is the return-confirmation dwell, so a brief false
   `present` reading cannot commit a `presence.return` and end the program (rule 4). A failed
   calendar read or unavailable presence makes the state undecidable, never true.
3. **Start.** The family's start criterion is effective absence. During a running process an
   observed `presence.departure` episode requests an immediate fresh evaluation; at bootstrap the
   current plan and stabilized `away` establish effective absence directly, without recovering a
   pre-restart departure.
4. **Normal exit.** A committed `presence.return`, or a fresh valid calendar result proving
   removal or replacement of the selected interval, is `normal_cancellation` of the current
   activation. The valid end of the selected interval with no later step or ongoing target of the
   descriptor's program is `natural_completion`. Calendar failure, undecidable presence, hold,
   guard veto or an unresolved descriptor input is `not_ended`: future steps are suppressed but no
   exit is invented.
5. **Next activation.** After an exit, a later eligible interval starts a new activation under the
   same configuration generation; no job, hold or step identity crosses activations.
6. **Holds.** `hold_release_mode="next_reaction_step"`; a channel staged only for declaring
   descriptors needs no `hold_duration`.
7. **Restart.** `managed_episode_resumption=False`. No activation, hold, job or missed step is
   restored; fresh current inputs may open a new activation and select only still-future steps
   through the one next-step slot (§6.0).
8. **Authority.** `requires_household_consent=True`.

The family component returns `AbsenceProgramState`; the descriptor's `normal_exit_contract` uses
its `exit` value and may only add the descriptor's own terminal-target rule. Initial V3 has two
declaring descriptors, `environment.planned_comfort_trajectory` (§7.1) and
`security.presence_simulation` (§7.2). A future program of the same kind, for example an
absence frost-protection descriptor, declares the family and specifies only its own steps,
targets, endpoints, guards and prerequisites.

## 4. Candidate to `ConfiguredReaction`

### 4.0 Layer-5 diagnostic registry

Layer 5 owns one core-owned, bootstrap-frozen, versioned `Layer5DiagnosticRegistry`. It is not
administrator-configurable or plugin-extensible. Its code sets are closed; an unknown code, a code in
the wrong namespace, or a noncanonical tuple is rejected at the persistence or audit boundary. Bounded
redacted detail may explain a code but cannot introduce new diagnostic semantics.

```python
ProposalTransitionReasonCode = Literal[
    "accepted_by_admin",
    "rejected_by_admin",
    "candidate_kind_incompatible",
]

ProposalReadinessReasonCode = Literal[
    "evidence_expired",
    "descriptor_incompatible",
    "relation_profile_incompatible",
    "topology_incompatible",
    "actuator_inventory_incompatible",
    "guard_profile_incompatible",
    "staged_prerequisite_incomplete",
    "staged_prerequisite_incompatible",
]

ReactionEvaluationReasonCode = Literal[
    "trigger_not_matched",
    "semantic_guard_unsatisfied",
]

ReactionExecutionAuditCode = Literal[
    "late_recovery",
    "late_step_skipped",
    "stale_callback_discarded",
    "future_work_cancelled",
    "alternate_bundle_selected",
    "bundle_skipped_no_admissible_alternative",
    "fallback_served_without_artifact",
    "coalesced_identical_target",
]

GovernanceCommandOutcome = Literal["applied", "idempotent_replay", "rejected"]

GovernanceCommandRejectionCode = Literal[
    "actor_unauthorized",
    "stale_precondition",
    "operation_id_conflict",
    "target_not_found",
    "authoring_mode_not_permitted",
    "validation_failed",
    "consent_disposition_incomplete",
]

@dataclass(frozen=True)
class Layer5DiagnosticRegistry:
    version: str
    proposal_transition_codes: frozenset[ProposalTransitionReasonCode]
    proposal_readiness_codes: frozenset[ProposalReadinessReasonCode]
    evaluation_codes: frozenset[ReactionEvaluationReasonCode]
    execution_audit_codes: frozenset[ReactionExecutionAuditCode]
    governance_command_codes: frozenset[GovernanceCommandRejectionCode]
    canonicalize_readiness_codes: PureFunction
```

The initial registry contains exactly the literals above. A transition code is valid only for its
corresponding disposition: `accepted_by_admin` -> `accepted`, `rejected_by_admin` -> `rejected`, and
`candidate_kind_incompatible` -> `proposal_incompatible`. Readiness codes are duplicate-free and in
registry canonical order; `approvable` readiness has an empty tuple.

#### Governance command results

Every common §4.2 command and every registered descriptor-specific preparation command, such as
`stage_comfort_trajectory_prerequisite_generation`, returns exactly one typed result to its caller:

```python
@dataclass(frozen=True)
class GovernanceCommandResult:
    operation_id: str
    command_id: str                   # registered command name
    outcome: GovernanceCommandOutcome
    rejection_codes: tuple[GovernanceCommandRejectionCode, ...]
    readiness_codes: tuple[ProposalReadinessReasonCode, ...]
    resulting_ref: str | None         # new generation/transition/proposal id when applied
```

`applied` has empty code tuples and the identity of the record it appended. `idempotent_replay`
returns the original result unchanged for the same operation id and canonical request.
`rejected` has a non-empty, duplicate-free canonical `rejection_codes` tuple, changes nothing and
has `resulting_ref=None`; `readiness_codes` is non-empty only together with `validation_failed`
when the failed check has a readiness code. `actor_unauthorized` covers a missing role or explicit
resident authority; `stale_precondition` covers any expected generation, transition, revision or
empty-current sentinel that differs from the current one; `operation_id_conflict` is reuse of an
operation id with different content; `authoring_mode_not_permitted` is, for example,
`stage_admin_direct_reaction` for a learner-proposal-only descriptor; and
`consent_disposition_incomplete` is a resident-authority removal without exactly one disposition
per affected consent. The result goes only to the Layer-8 caller; it is never a resident
notification.

#### Execution audit

```python
@dataclass(frozen=True)
class ReactionExecutionAudit:
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str | None
    snapshot_id: str | None           # None only for a callback discarded before evaluation
    code: ReactionExecutionAuditCode
    planned_step_id: str | None
    cause_ref: str | None             # required exactly for future_work_cancelled and
                                      # coalesced_identical_target
    artifact_ref: str | None          # exact ArtifactRef identity where one exists
    recorded_at: EvidenceInstant
```

The codes are descriptor-neutral; each descriptor version declares in
`RegisteredReactionDescriptor.execution_audit_codes` the subset it may emit, and staging rejects a
code outside the registry:

- `late_recovery`: a program that continues with the next safe step after its remaining supported
  ramp can no longer meet its boundary.
- `late_step_skipped`: a due job evaluated after its step's admissible time; the step is skipped,
  never caught up.
- `stale_callback_discarded`: a callback whose activation or arm revision is no longer current.
- `future_work_cancelled`: pending jobs of the activation were cancelled; `cause_ref` names the
  existing record that caused it (the `ReactionNormalExitResult`, the `ReactionAuthorityTransition`,
  or the successor configuration generation), so no second cause vocabulary exists.
- `alternate_bundle_selected` / `bundle_skipped_no_admissible_alternative`: before admission a
  freshly derived complete alternate bundle was admitted, or none was and no member was commanded.
- `coalesced_identical_target`: this Reaction's member was merged into another Reaction's identical
  safe-direction target on the same channel (§6.0 arbitration); `cause_ref` names the dispatched
  `apply_step_id`, and this member sent no call.
- `fallback_served_without_artifact`: a serving role used its descriptor-authorized fallback or
  staged seed because no usable adopted artifact exists; `artifact_ref` is `None` at first use with
  no adoption, otherwise the unusable adopted revision. A role without such a fallback abstains
  through `AutomationSuppressionReason` instead.

An execution-audit code is neither an `ApplyCallFailureReason` (a call that was attempted), an
`AutomationSuppressionReason`, nor a `ReactionFollowUpOutcome`. These records feed Layer-5 audit and
the read-only shadow view only; resident-visible output remains exclusively
`ReactionFollowUpOccurrence` and `AvailabilitySuppressionOccurrence` through Layer 6. A skipped step
that releases a hold produces its audit record and, under §6.0, its follow-up occurrence.

Layer 3 submits the closed `ReactionDescriptorCandidate` defined in Layer 3 §6.4 with
`candidate_kind="reaction.descriptor"` and `candidate_kind_version=1`. Layer 5 first validates that exact
outer kind/version through `ProposalCandidateKindRegistry`, then validates Reaction-descriptor id/version,
exact `RelationProfileRef`, objective/member-intent pairing, bounded canonical actuation bundle,
each member's applicable `NumericOutcomeRequirement` and registered outcome unit,
subject/opening/Actuator relation, root and member canonical parameters,
required guards, `CanonicalEnvelope`, exact profile-registered primary-artifact
output and deduplication fingerprint. It then
either rejects the transient candidate with a typed diagnostic reason or creates the persisted
`ReactionProposal` for ordinary administrative review.

For the closed `("reaction.artifact_adoption", 1)` kind, Layer 3 submits only
the `ArtifactAdoptionCandidate` of Layer 3 §6.2: current Reaction/generation,
declared serving-artifact role and exact immutable revision, with the
ordinary bounded evidence and validity fields. Layer 5 resolves the current
Reaction and role before creating a `ReactionArtifactAdoptionProposal`; this
candidate cannot specify a new descriptor, action, guard, endpoint,
configuration or authority. The initial kind registry remains closed to
plugins and administrator-added payloads.

The candidate root is the only owner of Reaction-descriptor and relation-profile identity.
`CanonicalEnvelope` contains only its canonical axes, partitions, and supported cells; it cannot carry
or override a second descriptor id/version or profile reference. Its schema is selected exclusively by
the root's exact `(reaction_descriptor_id, reaction_descriptor_version, RelationProfileRef)`.

For `environment.planned_comfort_trajectory`, the registered validator additionally requires the
closed Layer-3 §6.4.1 translation: exactly one scope/mode candidate, one
`follow_comfort_trajectory` member, and the exact staged prerequisite-generation id/fingerprint in
root `descriptor_parameters`. It resolves that generation independently and requires its scope,
endpoint, guards, `RelationProfileRef(profile_id="hvac_thermal_response", version="1")`, exact
parameter bucket and envelope to agree with the candidate and evidence revision. For this descriptor the evidence revision's bounded redacted
snapshot contains the selected parameter's canonical fingerprint and its scope, mode, cell and bucket
identities; Layer 5 validates those against its `artifact_ref`, candidate and current artifact. The
parameter/artifact identity, evidence span, confidence and uncertainty remain refreshable evidence
only; target/bound/calendar/adapter/consent values in learned candidate or evidence payload are
rejected because those values are not legal there. A generation-pair or mode/bucket/envelope change is a different
candidate; an otherwise compatible artifact refresh is not.
The selected thermal parameter and its calibration first pass the exact
`hvac_thermal_response.policy_output.v1` registration above; this descriptor's
remaining target and prerequisite checks specialize policy meaning, not the
Layer-3-to-Layer-5 output transport.

Layer-3 proposal-facet validation is advisory preflight, never an authorization or a reservation of a
registry/configuration generation. Layer 5 alone authoritatively validates a candidate before it
creates a `ReactionProposal`; authenticated acceptance repeats that validation against the then-current
descriptor/profile versions, canonical payload/fingerprint, Topology, Actuator inventory, guard profile
and staging configuration. A discrepancy found at either Layer-5 boundary follows the typed rejection,
pending non-approvability, or `proposal_incompatible` rule applicable to that boundary. No successful
Layer-3 preflight can be cached as permission to persist or accept a proposal.

A Layer-5 fingerprint or approved-envelope subset check cannot serialize a complete
`CoverageCell` as semantic identity: it uses Layer 3 §6.5's exact
`envelope_semantic_projection`, including axis/partition versions and cell
keys but excluding support/calibration evidence. Root `descriptor_parameters`
are part of the same candidate semantic fingerprint at both layers.

The persisted proposal records the accepted `(candidate_kind, candidate_kind_version)` together with
the candidate's Reaction-descriptor id/version, exact `RelationProfileRef`, and canonical deduplication identity. On a registry-generation
change that removes or makes its candidate kind/version incompatible, Layer 5 selectively marks only
the still-pending matching proposals `proposal_incompatible`. That is a terminal non-approvable review
disposition with an audit reason; it never silently substitutes a new kind/version, mutates the
proposal payload, or creates a replacement proposal. A `ConfiguredReaction` created before this change
remains governed only by its staged Reaction-descriptor id/version, scope, topology, Actuator and guard contracts:
candidate-kind incompatibility neither disables it nor enters policy evaluation/action. The reload work
is bounded slow-path persistence/workflow reconciliation, never an engine-cycle operation.

An accepted proposal does not become automatic merely because the evidence is strong. It first becomes
a `ConfiguredReaction` in `notification_only` mode. Enabling automatic action is a separate authenticated
transition that revalidates its current configuration generation against the current registry generation,
Actuator inventory, Topology and guard profile; it does not rewrite or restage semantic configuration.
A member without a compatible endpoint can only be an advice member where the descriptor lists
its intent in `advisory_intents` (§3.2); otherwise staging rejects it.

Layer 3 can refresh evidence for the same review item but cannot overwrite its review status, mode,
action scope, guard profile, or `RelationProfileRef`. An incompatible descriptor or profile version requires Layer-5 selective
revalidation under the composed-generation impact rule (Layer 0 §4.7); a policy that cannot be
revalidated is `configuration_invalid`, never silently reinterpreted.

### 4.1 `ReactionProposal` review lifecycle

`ReactionProposal` is the persisted governance record owned by Layer 5, never a `HouseFact`. Layer 1
defines only its ontological distinction from the fact substrate. Its review disposition is exactly one
of `pending`, `accepted`, `rejected`, or
`proposal_incompatible`. The aggregate's immutable root, and its three append-only record types, are:

```python
@dataclass(frozen=True)
class ReactionProposal:
    proposal_id: str
    candidate_kind: str
    candidate_kind_version: int
    reaction_descriptor_id: str
    reaction_descriptor_version: str
    relation_profile: RelationProfileRef
    canonical_admitted_payload: CanonicalJsonObject
    deduplication_fingerprint: str
    admitted_when: EvidenceInstant
    initial_evidence_revision_id: str

@dataclass(frozen=True)
class ReactionArtifactAdoptionProposal:
    proposal_id: str
    candidate_kind: str               # closed core artifact-adoption candidate kind
    candidate_kind_version: int
    reaction_id: str
    configuration_generation_id: str
    role_id: str                       # descriptor-declared artifact role
    artifact_ref: str                  # exact proposed Layer-3 revision
    canonical_admitted_payload: CanonicalJsonObject
    deduplication_fingerprint: str
    admitted_when: EvidenceInstant
    initial_evidence_revision_id: str

@dataclass(frozen=True)
class ProposalSupportingArtifact:
    role_id: str                       # closed role registered by the candidate/descriptor version
    artifact_ref: str                  # exact immutable Layer-3 ArtifactRef identity

@dataclass(frozen=True)
class ProposalEvidenceRevision:
    evidence_revision_id: str
    proposal_id: str
    revision_index: int
    admitted_payload_fingerprint: str
    finding_id: str
    artifact_ref: str
    supporting_artifacts: tuple[ProposalSupportingArtifact, ...]
    evidence_fact_refs: tuple[str, ...]
    evidence_start: EvidenceInstant
    evidence_end: EvidenceInstant
    confidence: float
    uncertainty: CanonicalJsonObject
    valid_until: EvidenceInstant
    bounded_redacted_snapshot: CanonicalJsonObject
    recorded_when: EvidenceInstant

@dataclass(frozen=True)
class ProposalReviewTransition:
    transition_id: str
    proposal_id: str
    from_disposition: Literal["pending"]
    to_disposition: Literal["accepted", "rejected", "proposal_incompatible"]
    actor_ref: str                       # authenticated actor or the closed `system` actor
    reason_code: ProposalTransitionReasonCode
    evidence_revision_id: str
    configured_reaction_id: str | None   # required for accepted configuration or adoption
    recorded_when: EvidenceInstant

@dataclass(frozen=True)
class ProposalReadinessAssessment:
    assessment_id: str
    proposal_id: str
    evidence_revision_id: str
    registry_generation_fingerprint: str
    readiness: Literal["approvable", "not_approvable"]
    reason_codes: tuple[ProposalReadinessReasonCode, ...]  # empty iff approvable; otherwise canonical registry order
    bounded_redacted_detail: CanonicalJsonObject
    recorded_when: EvidenceInstant
```

`ReactionProposal` stores only the identity and canonical payload that Layer 5 admitted; it never
stores a raw HA entity, service, command, or mutable review fields. The current disposition is a
projection of the sole `ProposalReviewTransition`, if any. The current evidence is the revision with
the greatest `revision_index`; its validity interval determines readiness. Every revision requires
`evidence_start <= evidence_end` and binds the same admitted payload fingerprint. An evidence revision
whose fingerprint differs is a new candidate, not a refresh.

`artifact_ref` is the primary evidence artifact. `supporting_artifacts` holds
additional immutable Layer-3 artifact identities, in canonical `role_id`
order, with at most one entry per role and only roles declared by the exact
candidate/descriptor version. Layer 5 resolves each reference and validates
its role-specific definition, schema, subject, evidence validity and required
shadow eligibility against the admitted semantic payload. A timing-model role
must match the complete stable `ReactionTimingModelBinding` in §4.2, including
its condition and horizon. Missing, extra, duplicate, incompatible or
unavailable required support makes the proposal not approvable. The typed
tuple is committed with the evidence revision; a redacted snapshot or root
parameter cannot substitute for it. It is evidence, never configuration or
adoption. A compatible evidence refresh may update its exact artifact
revision while preserving the same registered role set and admitted payload.

`ReactionArtifactAdoptionProposal` is the review item for one exact revision
of a descriptor-declared artifact role on an existing Reaction: the first
selection when none was staged, or a later `pinned` successor.
It uses the same committed initial `ProposalEvidenceRevision`, readiness
assessment, terminal dispositions, authenticated `ProposalReviewTransition`
and `review_proposal` command as a configuration proposal. Its primary
`ProposalEvidenceRevision.artifact_ref` must equal its frozen `artifact_ref`;
a freshness update may append evidence for that same revision, never replace
it with another revision. Its deduplication fingerprint includes the exact
Reaction id, current configuration generation, role and immutable artifact
identity. Thus a new revision can open a distinct review item even when the
Reaction's semantic payload is unchanged; a retry of the same revision cannot
duplicate one. A rejected or accepted adoption proposal remains terminal.
Its closed `canonical_admitted_payload` is exactly the four identity fields
above; it adds no proposed Reaction configuration. Both proposal kinds use
the same atomic root-plus-index-0-evidence invariant below.
It cannot contain a new action, descriptor parameter, guard, scope or consent
request. If a change to any of those is needed, the ordinary configuration
proposal and successor-generation path applies.

Proposal creation is one atomic, idempotent aggregate transaction: it persists the immutable root and
exactly one initial `ProposalEvidenceRevision` together, or persists neither. That first revision has
`revision_index=0`, the root's `initial_evidence_revision_id`, the root's `proposal_id`, and the
canonical fingerprint of the root's admitted payload. No proposal projection, transition, readiness
assessment, or review operation may observe or reference a root before that revision commits. A retry
of the same admitted candidate returns that complete aggregate; it cannot create a second root or a
second index-0 revision.

Within one proposal, evidence revisions are immutable and append-only with unique contiguous indexes
`0..n`; a compatible refresh atomically appends only `n + 1`. Each revision's
`admitted_payload_fingerprint` must equal the initial revision's fingerprint. A transition or readiness
assessment may reference only a committed revision of its proposal. The storage implementation may use
any crash-safe mechanism, but must preserve these observable atomicity, uniqueness, ordering, and
idempotency invariants.

`accepted`, `rejected`, and `proposal_incompatible` are terminal; only a `pending` proposal may
receive a compatible Layer-3 evidence refresh. A refresh appends a new `ProposalEvidenceRevision` and
advances the current-evidence projection; it never rewrites the root or a prior revision, nor changes
review disposition, scope, action bundle, guard profile, descriptor/version, `RelationProfileRef`, or
candidate-contract identity. Every snapshot is individually bounded and redacted; its references are
typed evidence identities, never copied fact or HA payloads.

A proposal whose evidence is no longer within its declared validity interval remains `pending`, but is
not approvable until a compatible refresh restores current evidence. This is a review-readiness result,
not a fifth disposition and not a terminal expiry: it prevents approval from stale evidence without
discarding an item that Layer 3 can still substantiate. Layer 5 records this, and every other
non-transitioning revalidation result, as a `ProposalReadinessAssessment`; it never overloads a review
transition to record a failed attempt.

An authenticated acceptance is one transaction: Layer 5 revalidates the immutable admitted payload
against the current registry generation, Actuator inventory, Topology, and guard profile; creates the
resulting `ConfiguredReaction` in `notification_only` mode; and records the accepting actor, time,
decision reason, evidence revision, and resulting reaction identity in the one `accepted`
`ProposalReviewTransition`. A recoverable current staging failure leaves the proposal `pending` with a
typed non-approvability `ProposalReadinessAssessment`. A candidate-kind/version incompatibility instead
moves the still-pending proposal to the terminal
`proposal_incompatible` disposition under §4's selective reconciliation rule.

Acceptance of a `ReactionArtifactAdoptionProposal` instead revalidates the
exact current Reaction generation, role binding, artifact, quality/shadow
eligibility and, for a successor, pinned compatibility under §4.2. It atomically commits the
`accepted` review transition and one `ReactionArtifactAdoptionTransition` for
that revision. The transition names the existing Reaction in
`configured_reaction_id`; no Reaction root or configuration/authority
generation is created, and existing administrative authorization and
household consent remain as they were. A stale generation, superseded
revision or failed eligibility check leaves the proposal pending with a
typed readiness assessment; it cannot adopt by merely becoming available.

An authenticated rejection appends a typed `rejected` `ProposalReviewTransition`. A candidate with the
same canonical deduplication fingerprint cannot silently reopen that decision; a semantic configuration
change has a different fingerprint and follows the ordinary new-candidate path. There is no in-place
reopening transition. The accepted proposal remains the immutable record of the decision: later policy
artifact adoption, policy enablement, and promotion from `notification_only` to automatic action belong
to the separate configured-Reaction lifecycle and never rewrite its proposal or evidence revision.

### 4.2 `ConfiguredReaction` configuration and authority lifecycle

`ConfiguredReaction` is the persisted Layer-5 policy aggregate, never a `HouseFact` and never a
descriptor-specific runtime object. It gives both `admin_direct` and `learner_proposal` authoring one
common identity, immutable configuration history, evaluation plan and action protocol. The only
difference between those origins is durable provenance: a learner-origin reaction names the accepted
proposal that created its first configuration; an admin-direct reaction names no proposal. Neither origin
selects a different evaluator, scheduler, authorization rule or `ApplyStep` path.

```python
ReactionOrigin = Literal["admin_direct", "learner_proposal"]
ReactionExecutionMode = Literal[
    "configuration_invalid",
    "notification_only",
    "authorized_awaiting_household_consent",
    "automatic",
]

@dataclass(frozen=True)
class ReactionTimingModelBinding:
    timing_path_id: str                 # one path registered by this descriptor version
    learning_kind_id: str
    learning_kind_version: str
    learning_definition_fingerprint: str
    sample_binding_id: str
    sample_binding_version: int
    result_schema_id: str
    result_schema_version: int
    condition_ref: FactRef             # exact staged typed state, same Location
    qualifying_values: tuple[EvidenceValue, ...]  # closed nonempty subset of that state's vocabulary
    window: LearnedWindow             # authorized seed/min/max, not an artifact revision

@dataclass(frozen=True)
class ReactionDelayTimerSemantics:
    timing_path_id: str
    gap_semantics: DelayGapSemantics
    condition_ref: FactRef
    qualifying_values: tuple[EvidenceValue, ...]

@dataclass(frozen=True)
class ReactionEvaluationPlan:
    trigger: CanonicalJsonObject
    delay_timer_semantics: ReactionDelayTimerSemantics | None
    timing_model_binding: ReactionTimingModelBinding | None
    delay_permission_ids: tuple[str, ...]  # one per delayed bundle member; empty for immediate paths
    semantic_guards: tuple[CanonicalJsonObject, ...]
    canonical_envelope: CanonicalJsonObject
    canonical_actuation_bundle: ActuationBundle
    history_requirement_ids: tuple[str, ...]
    calendar_plan_binding: CalendarPlanBinding | None
    guard_profile_generation_id: str | None
    guard_profile_definition_fingerprint: str | None
    required_guard_capabilities: tuple[ReactionGuardCapabilityRef, ...]
    plan_fingerprint: str

@dataclass(frozen=True)
class ConfiguredReaction:
    reaction_id: str
    origin: ReactionOrigin
    source_proposal_id: str | None       # required iff origin="learner_proposal"
    initial_configuration_generation_id: str
    created_by: str                       # authenticated administrator or closed system actor
    created_when: EvidenceInstant

@dataclass(frozen=True)
class ReactionConfigurationGeneration:
    configuration_generation_id: str
    reaction_id: str
    generation_index: int                 # contiguous per reaction, beginning at 0
    reaction_descriptor_id: str
    reaction_descriptor_version: str
    relation_profile: RelationProfileRef | None
    subject: Location
    canonical_descriptor_configuration: CanonicalJsonObject
    evaluation_plan: ReactionEvaluationPlan
    definition_fingerprint: str
    staged_by: str                        # authenticated administrator or closed system actor
    staged_when: EvidenceInstant

@dataclass(frozen=True)
class ReactionAuthorityTransition:
    authority_transition_id: str
    reaction_id: str
    configuration_generation_id: str
    administrative_action_authorized: bool
    household_consent: bool | None        # None exactly when the descriptor has no consent gate
    actor_ref: str
    recorded_when: EvidenceInstant

@dataclass(frozen=True)
class ReactionArtifactAdoptionTransition:
    adoption_transition_id: str
    transition_kind: Literal["initial", "pinned_revision", "bounded_refresh", "mode_change"]
    reaction_id: str
    configuration_generation_id: str
    role_id: str
    previous_adoption_transition_id: str | None
    artifact_ref: str
    adoption_mode: Literal["pinned", "bounded_adaptive"]
    source_proposal_id: str | None     # absent for admin-direct or compatible automatic adoption
    source_evidence_revision_id: str | None
    actor_ref: str                     # authenticated administrator or closed system actor
    recorded_when: EvidenceInstant

@dataclass(frozen=True)
class FrozenReactionAuthorityView:
    active_modes: tuple[tuple[str, str, ReactionExecutionMode], ...]
    # canonical (reaction_id, current configuration_generation_id, mode) order
    layer5_generation_fingerprint: str
    fingerprint: str
```

Layer 5 freezes this view at the shared `CycleInputBarrier` from the current
committed configuration and authority projections. It includes one entry per
current Reaction, even when its mode is not `automatic`; an absent or stale
generation is therefore never inferred to be authorized. An entry in
`configuration_invalid` takes precedence over every authority transition and is
excluded from evaluation, shadow and scheduling. The fingerprint is
SHA-256 over RFC-8785 canonical JSON of the ordered entries and Layer-5
generation fingerprint. Layer 4 transports the view opaquely (§5.1). Layer 5
uses it to filter every Reaction-anchored recovery facet and to evaluate normal
Reaction authority for that snapshot. A later consent revocation cannot alter
the frozen decision but the dispatch fence rechecks current authority before
any physical command; an old snapshot can never outlive revocation.

`ReactionEvaluationPlan` is the persisted canonical result of the descriptor compiler: exactly one
closed temporal trigger or versioned programmed-activation start criterion, a bounded ordered set of typed semantic guards, one validated envelope, one
finite ordered semantic bundle, and only the staged history/calendar requirement identities it may read.
Its JSON members are validated and canonicalized by the exact descriptor/profile version; they cannot
contain a callable, raw HA selector, service payload, dynamic expression, live snapshot, consent value,
or scheduler state. The active frozen Layer-5 generation resolves the
descriptor/version and plan fingerprint to its registered compiler and
program evaluator. No callable is serialized, and a plan cannot be recompiled under a
different descriptor/profile version merely because its JSON resembles a compatible shape.
For a step-programmed descriptor, the existing `trigger` field retains a
canonical reference to the descriptor version's bounded start-criteria
contract and its staged input bindings (§3.2). It does not encode a new core
temporal primitive or the event that happened to request this evaluation.
The registered program evaluator checks those descriptor-version criteria against the current
snapshot, including at bootstrap; a scheduled callback and an observed
semantic episode only request another evaluation of that same plan. The
current activation id prevents repeated qualifying cycles from starting
another program.

`timing_model_binding` is present only for a descriptor-version-declared
model-backed delay path. The descriptor registry fixes each legal
`timing_path_id`, its trigger/intent applicability and one-binding limit;
an administrator or learner cannot add a timing path to another descriptor.
Every delayed path, including one using only a fixed seed, declares exactly
one `delay_timer_semantics` in the immutable plan. The descriptor version
registers its permitted `gap_semantics`, typed condition and qualifying set;
staging rejects an undeclared choice. A model binding, when present, must name
the same path, condition and qualifying set. The declaration is part of the
plan/configuration fingerprint; a different meaning requires a successor
configuration generation and ordinary authority review. An immediate or
event-only path without a declared persistent continuation state has no
delay-timer declaration. This field describes time accounting, never a
command permission or a replacement for the current-state admission gates.
Staging resolves the named core learning kind/version and staged definition,
checks its exact fingerprint, the path's registered sample binding and result
schema, typed state `condition_ref`, exact nonempty `qualifying_values`,
subject `Location`, and the path's required horizon. The state-fraction path
requires `FutureStateFractionOutcome`, a dimensionless scalar result and
`horizon=window.maximum`. The room-return path requires the registered
`RoomOccupancySurvivalModel.return_delay` time-to-event binding,
`SurvivalResult`, exact resolved `room_occupancy` at the same room,
`qualifying_values=("absent",)`, a physical-evidence-eligible
`present -> absent` anchor, an `absent -> present` target, the registered
competing-event vocabulary, and an exact curve point at
`window.maximum`. A state-transition trigger must observe entry from
outside that set into it on this same stream. An event-occurrence trigger
is eligible only when its descriptor separately declares a typed current
continuation state and a bounded rule that anchors the event to an already
qualifying value; no event is treated as a persistent state by inference.
The Reaction's continuation condition and the learner's declared typed
source/qualifying set must be identical; the survival path binds its
`return_delay` profile and is never coerced into a state-fraction outcome.
`window.calibrated_from`/`where` identify that same fact type and Location.
Staging rejects unknown, duplicate, wrong-type or non-vocabulary values,
a mismatched outcome/result schema or an event-only trigger without that declared
continuation contract. Unknown or mismatched definitions reject staging; a
disabled, degraded or unvalidated artifact cannot serve a learned delay.
The complete stable binding and window enter
the configuration and plan fingerprints. An artifact's `analysis_revision`,
current `artifact_ref`, quality metrics, evidence span and adoption status do
not: those are mutable evidence/serving state under Layer 3 §4.5/§4.9 and
CA4-14, never a semantic configuration edit by themselves. This distinction
does not authorize an unapproved artifact; §6.0 falls back to the staged seed
until the separate adoption state proves current eligibility.
Completion of Layer-3 shadow alone never populates that adoption state or
grants automatic action. Initial model-backed use follows the existing
candidate/review or admin-direct staging, notification-only, admin promotion
and descriptor-required consent gates.

For each descriptor-declared serving artifact role, the current adopted revision is the last
committed `ReactionArtifactAdoptionTransition` for the current Reaction
generation and role. It is an append-only serving decision, separate from
the configuration and authority transitions. A new configuration generation
does not inherit one. Initial learner-proposal acceptance commits the exact
eligible artifact from the accepted evidence revision for each declared
serving role, whether primary or supporting, together
with the Reaction root/generation and review transition. Admin-direct staging
may name an exact eligible artifact for a descriptor-declared role and commits
its initial adoption in the same transaction; otherwise the declared timing
path starts on its authorized seed. Staging never chooses whichever revision
happens to be newest without an explicit initial selection. The authenticated
administrator selects `pinned` or `bounded_adaptive` where the registered
model type permits both; the choice is retained in the adoption transition.
It does not change action authority or resident consent.

Transitions for one `(reaction_id, configuration_generation_id, role_id)`
form a single ordered chain through `previous_adoption_transition_id`.
An append compares the committed head, is idempotent for the exact operation
and artifact revision, and atomically records the new head; a crash reveals
the old or new complete transition. An accepted proposal requires both its
committed proposal id and exact evidence revision in the adoption transition;
admin-direct staging has neither, and a compatible automatic advance uses
the closed `system` actor with neither. A mode change has neither and retains
the authenticated administrator as actor. A later transition retains the
current adoption mode unless its `transition_kind` is `mode_change`.
`initial` has no predecessor; `pinned_revision` requires accepted
revision-specific proposal evidence; `bounded_refresh` requires the closed
system actor and the compatible-revision proof. A `mode_change` requires an
authenticated administrator, the current exact generation/role and adoption
head, and the same currently adopted artifact. It changes only the mode:
entry to `bounded_adaptive` requires the current artifact to be eligible and
binds the current generation's approved compatibility bounds before any
automatic refresh; exit to `pinned` fixes the current revision until another
exact admin review, even if that revision is presently unavailable. It
does not create a Reaction generation, revoke action authority or resident
consent, issue a command, or inherit a different artifact. A mode change
with the same effective artifact leaves an already armed delay unchanged;
only a later effective revision or availability change invokes §6.0's
recalculation from the original anchor. A mode change
with no current adoption or a stale head is rejected without mutation;
entry to `bounded_adaptive` also rejects unapproved bounds or an ineligible
current artifact. A future change to the
Reaction's semantic scope or bounds still uses a successor configuration.
Layer 5 rejects a candidate revision
older than the committed head, a mismatched definition or role, an expanded
scope/envelope, or a missing current quality/shadow/eligibility gate. A
`pinned` successor requires an accepted revision-specific
`ReactionArtifactAdoptionProposal` under §4.1. A `bounded_adaptive`
successor may be appended by the closed system actor only after the
core-owned compatibility predicate proves the same staged binding, result
schema, condition, horizon, subject, action scope, guards, mode and approved
parameter/envelope bounds. An incompatible change follows ordinary
configuration review, never this transition. Adoption refresh changes no
configuration generation, authorization or consent and sends no command.

An adoption record is evidence of permission to use one revision, not proof
that it remains usable. At each evaluation Layer 5 also requires the exact
artifact to be current, validated, nonstale, applicable to the present
context and eligible under Layer 3 §4.5/§4.9. If it is withdrawn, disabled,
degraded beyond its type's serving gate or unavailable after restart, the
declared timing path uses its staged seed; a serving role without a
descriptor-authorized fallback abstains. It never silently serves a prior
revision or auto-adopts an unrecorded newer one. A change between an adopted
forecast and the seed, or between adopted revisions, recalculates only
pending work from its original trigger anchor under §6.0; no completed step
is replayed.

For a descriptor that declares Reaction guards, the plan additionally retains one exact
guard-profile generation/fingerprint and canonical required capability refs. Both guard-profile fields
are absent only when the selected guard contract requires no environmental capability. They are resolved
and validated at configuration staging, never selected from a current snapshot or learned evidence.

The root and every configuration generation are immutable and append-only. Creation atomically persists
one root and generation index `0`, or neither; a retry returns the complete same aggregate. Every later
semantic edit revalidates the complete descriptor configuration and atomically appends exactly the next
contiguous generation. The current configuration is the greatest committed generation index. A
configuration generation's fingerprint covers its descriptor/profile identities, subject, complete
canonical descriptor configuration and plan fingerprint. It is the generation used for all evaluation,
job, execution and audit identity; no active work may be interpreted under a later generation.

`canonical_descriptor_configuration` is the descriptor-validated source of the plan: it contains only
the descriptor's declared subject, parameters, bundle/member identities and semantic parameters,
guard/profile references, envelope, and any declared prerequisite, calendar or
`ReactionTimingModelBinding`. It never copies
learned evidence, a raw HA endpoint/service, current authority, an `ApplyStep`, an `ApplyCall`, or a
prebuilt schedule. `environment.planned_comfort_trajectory` additionally requires its exact immutable
`(prerequisite_generation_id, definition_fingerprint)` pair here; its narrower contract in §7.1 remains
authoritative for that pair.

For a learner-origin Reaction, `relation_profile` is required and must be one of the descriptor's
`supported_profile_refs`; its guard contract supplies the plan's required capabilities. For an
admin-direct configuration that uses the descriptor-level contract, `relation_profile` is absent and
the descriptor's required `direct_guard_contract` supplies them. Any other origin/profile/contract
combination is rejected atomically at staging. The optional reference therefore expresses a real absence
of learned-relation semantics, never an unchecked or ungoverned policy path.

The same origin selects `CanonicalEnvelope` evidence validation (Layer 3
§6.5), never a different runtime envelope evaluator. A learner-origin
generation requires supported and calibrated cells from its accepted
candidate. A profile-free direct generation uses only descriptor-permitted
joint cells with both evidence metadata fields absent; its canonical
envelope is frozen with the plan and configuration fingerprint. Presence
simulation has zero axes and exactly one empty-key cell (§7.2). A descriptor
that permits administrator selection of direct cells stages a bounded subset
of its versioned permitted set; a later expansion is a semantic configuration
successor with ordinary authority review, not a live edit.

**Composed-generation dependency.** Every Reaction configuration, guard-profile and prerequisite
generation activates only through the composed configuration generation of Layer 0 §4.7, and is a
consumer in its dependency index. When a confirmed change elsewhere makes the current generation's
plan fail validation (**breaking**: a missing or changed trigger, guard, axis, history, calendar,
timing-model or Actuator-channel binding, or a changed derived Topology/Actuator property it uses,
such as `weather_exposed`, `opening_faces_exterior` or thermal-envelope membership), the same commit appends an authority transition with
administrative authorization and any household consent disabled, cancels the Reaction's future
jobs, and projects mode `configuration_invalid`. That mode is derived, not stored: the Reaction
neither evaluates, shadows nor schedules work until an administrator commits a successor
configuration generation that validates; that successor starts `notification_only` under the
ordinary rules and needs fresh promotion and consent. Pending proposals bound to the invalid
dependency become not approvable with the existing readiness codes. A **semantic_only** upstream
change keeps the Reaction's generation and authority unchanged; it appears in the impact record so
the administrator can decide whether to edit or disable it. The dispatch fence (§6.0) rejects any
unsent call of an invalidated generation.

Every new configuration generation starts `notification_only`, with administrative action authorization
disabled and household consent unset/disabled. Authority changes are immutable append-only
`ReactionAuthorityTransition`s whose current projection determines `ReactionExecutionMode`: no
administrative authorization is `notification_only`; authorization awaiting a required consent is
`authorized_awaiting_household_consent`; both current gates are required for `automatic`. An authority
transition never changes trigger, guards, endpoints, envelope, plan or configuration fingerprint. A
configuration successor never inherits automatic authority or consent; it cancels every future job for
its predecessor and requires ordinary fresh evaluation after separately authenticated promotion.
For a descriptor with `requires_household_consent=True`, every committed
authority transition carries a boolean `household_consent`; `False` is the
initial and revoked value, and `True` requires an authorized resident grant for
that exact generation. For a descriptor with the property `False`, the field is
always `None`, resident consent commands are inapplicable, and administrative
authorization alone can produce `automatic`. Staging and projection reject a
transition whose consent field disagrees with the frozen descriptor property.

`actor_ref`, `created_by` and `staged_by` are restricted to common Layer-5 governance or immutable
administrator-configuration records: proposal-review transitions; Reaction creation/configuration
generations; authority and artifact-adoption transitions; `ReactionGuardProfileGeneration`; and
`ComfortTrajectoryPrerequisiteGeneration`. They make an authenticated administrative or resident
decision attributable, including consent retention or revocation when resident authority is removed.
A future Layer-5 type may retain one only when it is a common governance or immutable
administrator-configuration record of this same class, never descriptor operational data. No
`ReactionEvaluationPlan`, preview, `AtJob`, `ReactionEvaluationResult`, `ApplyStep`, execution audit or
descriptor-specific diagnostic may copy an actor reference or resident identity. A descriptor's data
minimization rule may further constrain its operational records but cannot prohibit this common
governance ledger.

#### Common Layer-8 command surface

Layer 8 renders descriptor-specific forms but sends only these shared typed
Reaction governance commands to Layer 5. Every command carries an
authenticated `actor_ref`, stable `operation_id`, `correlation_id`, exact
target identity and stated optimistic-concurrency precondition. Layer 5
validates the actor and current descriptor/generation, applies the whole
mutation atomically, and returns a typed result. Retrying the same operation
id with the same canonical request returns its prior result without another
generation or authority transition; reusing it with different content is
rejected. A stale precondition, unauthorized actor, or failed validation
changes nothing. Command results and rejections use `GovernanceCommandResult`
and the closed codes of §4.0, never a descriptor-invented string.

1. `stage_admin_direct_reaction` creates a root plus generation `0`, or
   appends one complete successor generation to an existing admin-direct
   Reaction. An authenticated administrator supplies the exact descriptor
   id/version, complete typed configuration and expected current generation
   id, with an explicit empty-current sentinel for creation. The descriptor
   must permit `admin_direct`; staging compiles and validates the full plan
   and leaves the new generation `notification_only`. An exact optional
   initial artifact selection and administrator-selected adoption mode for
   each declared role are typed staging arguments and commit their adoption
   with that generation; they are never descriptor parameters. A role with
   no initial artifact serves only its declared fallback until an explicitly
   reviewed first selection; it cannot enter `bounded_adaptive` by default.
   A learner-origin Reaction cannot be edited through this command.
2. `review_proposal` is the existing common proposal dispatcher. An
   authenticated administrator names the exact proposal and expected
   evidence revision; initial acceptance also names one permitted
   administrator-selected adoption mode for each selected artifact role.
   Acceptance revalidates and creates the
   learner-origin `ConfiguredReaction` in `notification_only` mode, or,
   for a `ReactionArtifactAdoptionProposal`, appends only the reviewed
   revision's adoption transition to the existing Reaction. A rejected or
   incompatible proposal changes no Reaction or adoption. Neither acceptance
   grants action authority. The adoption branch also requires the expected
   current Reaction generation and evidence revision; a stale precondition
   changes nothing. A first adoption names an administrator-selected permitted
   mode; a `pinned` successor retains its existing mode (§4.1–4.2).
3. `set_reaction_artifact_adoption_mode` names the exact Reaction,
   configuration generation, descriptor-declared serving role, current
   adoption transition and requested mode. Only an authenticated
   administrator may invoke it. It appends the `mode_change` transition
   under §4.2 after the direction-specific checks; retrying the same
   operation id returns the same result. It neither creates a proposal nor
   changes action authority or consent.
4. `promote_reaction_automatic_action` names the exact reaction and expected
   current configuration generation plus expected current authority
   transition id (or empty-current sentinel). An authenticated administrator
   passes descriptor-specific readiness/shadow gates and the common
   capability checks, then appends only administrative authorization.
   If consent is required but absent, the projected mode is
   `authorized_awaiting_household_consent`. Promotion never sends an
   `ApplyStep`.
5. `set_reaction_household_consent` names the same exact reaction/generation
   and expected authority transition, plus one boolean. Only an explicitly
   authorized resident may grant or revoke consent for a descriptor whose
   frozen `requires_household_consent` is true. A grant requires current
   administrative authorization; it requests fresh evaluation but replays
   no missed step. Revocation blocks the next dispatch fence and cancels
   future jobs. It cannot apply to a successor generation.
6. `disable_reaction_automatic_action` uses the same exact generation and
   authority preconditions and requires an authenticated administrator. It
   appends administrative disablement, cancels future action jobs and leaves
   configuration, evidence, proposal and audit intact. Re-enablement uses
   ordinary promotion checks again.
7. `stage_household_consent_authority` changes the household's complete
   explicit resident-authority list against its expected authority
   generation. An authenticated administrator removing an actor must supply
   exactly one `retain_current_consent` or `revoke_current_consent`
   disposition for each current consent that actor granted. Missing or extra
   dispositions reject the whole request. Retention audits an admin
   decision over an existing grant, never creates a new resident grant;
   revocation cancels affected future jobs. An administrator role alone
   never substitutes for resident consent authority.

These commands apply to all seven Initial-V3 descriptors under one
`ConfiguredReaction` lifecycle. Descriptor-specific preparation, such as
`stage_comfort_trajectory_prerequisite_generation`, may create an immutable
input referenced by a later configuration, but cannot duplicate these
authority commands or bypass their generation fences.

The idempotency identity of an evaluation and its bundle is
`(reaction_id, configuration_generation_id, snapshot_id, reaction_activation_id)`;
the activation id is absent only when no activation exists or starts in that
evaluation. Every Reaction-owned `AtJob`, `ReactionEvaluationResult`,
`ApplyStep`, execution audit and correction-attribution anchor carries that
configuration generation; work belonging to an activation also carries its
activation id. A standalone direct or recovery `ApplyStep` has no fabricated
Reaction identity and uses its own stable operation id and `snapshot_id`.
This makes a stale callback, a duplicate retry, or an action trace attributable to one exact immutable
policy meaning rather than only to a long-lived reaction id.

## 5. Policy evaluation

### 5.1 Closed relational vocabulary

Every descriptor compiles to one `ReactionEvaluationPlan`: exactly one temporal trigger or
programmed-activation start criterion, a bounded
conjunction of semantic guards, one `CanonicalEnvelope`, and one finite ordered `ActuationBundle`.
Every bundle member names one logical Actuator endpoint and one closed semantic action intent. The core
temporal primitives are:

- `delta_over_window`;
- `rate_over_window`;
- `level_crossing`;
- `state_transition`;
- `occurrence`.

An ordinary nonprogrammed trigger uses one of these primitives. A
step-programmed descriptor instead uses its versioned start criteria under
§3.2, compiled into the same `ReactionEvaluationPlan.trigger` field. Its
relevant typed event/state edge, semantic episode, calendar update and
next-step `AtJob` request the same fresh `evaluate_program` call, not an
additional policy trigger or evaluator. Only timed future boundaries occupy
the shared `AtJob` slot; an event-driven current step is evaluated from the
current frozen snapshot and never stores or replays that event as a timer.
The start criteria are evaluated
from the current frozen snapshot; no previous state or synthetic episode is
required after restart. Repeated qualifying evaluations keep the existing
activation, while a new valid start after its verified end receives a new id.

`state_transition` binds exactly one staged state `FactIdentityKey` from a
Layer-2 state producer or Layer-4 `SemanticState`, plus a closed, typed
`from_value`/`to_value` pair permitted by that producer's value contract.
Staging declares its `previous_cycle` key and rejects an event claim,
unregistered state, wrong scope or mismatched value type. The evaluator
reads only the matching `DecisionSnapshot.state_transition_inputs` member:
both previous and current facts must be available, have the same producer
execution semantics and belong to adjacent completed in-process cycles.
The trigger fires once in the current cycle exactly when the canonical
previous value matches `from_value` and current value matches `to_value`,
with the values distinct. An unchanged value, including a confidence-only
or source-route update, is `not_triggered`; missing/unavailable input or a
restart/semantic-generation gap is `abstained`, never an inferred edge.
This is the net previous/current state transition across a cycle. If one
intake contains multiple changes that return to the prior value, this
primitive does not fire for an intermediate edge; a descriptor needing
each occurrence must bind a declared event/episode through `occurrence`.

The relation and guards name only typed slots permitted by the descriptor's
frozen plan grammar and, for `learner_proposal`, further restricted by the
selected relation profile's policy facet;
Reaction guards are further restricted to the exact capability registry and guard contract in §3.2.
They cannot name arbitrary facts, inspect HA payloads, execute expressions, recursively invoke policies,
or create cross-policy flow. The descriptor fixes input type/unit, allowed comparison, freshness, window
shape and parameter bounds; a selected relation profile may narrow them. Derived physical quantities must be a typed lower-layer fact or resolved
semantic output, never an inline policy formula.

This keeps the ECA trigger-condition-action separation familiar from
[openHAB](https://www.openhab.org/docs/concepts/rules), while deliberately excluding its scripting
surface. Guard schemas and structural bounds are owned by the exact frozen capability registration,
not by a generic expression language.

Each compiled plan also declares its finite `HistoryViewRequirement` ids. Layer-5 staging contributes
their union to Layer 0 before activation; a plan whose required short-term history cannot be retained
is rejected at staging. Evaluation reads those exact slices only through the snapshot's
`FrozenHistoryView`, never by issuing an ad hoc historical query. A `None` read means the
in-memory interval is incomplete (§4.1 of Layer 0): evaluation abstains from a
history-dependent trigger or guard instead of interpreting it as an empty event slice
or a stable prior state. A complete empty event slice retains its ordinary no-event meaning.

#### Calendar-plan binding

A policy that needs a future resident plan declares one finite `CalendarPlanBinding`; this is the same
Reaction-descriptor mechanism, not a Layer-4 state, a fact, or a second calendar interpreter. It names a
non-empty bounded canonical set of staged Layer-0 `CalendarViewRequirement`s, each bound to one
`calendar.*` entity, an explicit staged Layer-2 `KeywordClassifier`, and one descriptor-declared intent
category. The initial category is `planned_absence`. Evaluation classifies each frozen active/upcoming
window individually and retains only the selected derived interval and category for that evaluation; it
never stores or exposes an event summary in a proposal, outcome, audit record, or learner feature.

```python
@dataclass(frozen=True)
class CalendarPlanBinding:
    calendar_requirement_ids: tuple[str, ...]  # non-empty, unique, canonical order; each names one source
    classifier_id: str
    expected_category: str            # closed by the selected descriptor version
```

The binding is opt-in per configured Reaction and has no source-entity or category default. Every named
requirement must be `ready`; a removed, edited, expired, or failed input produces no usable plan in the
next frozen snapshot. A matching calendar event says only that an explicit plan exists; it does not
imply `presence=away`, authorize an action, or supersede a manual hold. A descriptor may require a
present active plan, an upcoming plan, or both, but must declare that role at staging and every plan
horizon is bounded by its matching `CalendarViewRequirement`.

Selection is deterministic and conservative. For `planned_absence`, matching intervals from every
declared source are one union: exact duplicates collapse, and overlapping or directly adjacent intervals
coalesce to their earliest start and latest end. Source identity has no precedence. An active coalesced
interval takes precedence over upcoming intervals; otherwise the coalesced interval with the earliest
start is selected. A window whose own summary matches multiple categories uses the classifier's explicit
`priority_order`; a differently categorized window from another source neither cancels nor overrides a
matching `planned_absence` window. The initial descriptor permits only this core-defined union rule.
Any later category that needs a veto, source precedence, or another merge semantic requires an explicit
reviewed descriptor contract; neither an administrator nor a learner may install one ad hoc.

### 5.2 Snapshot semantics and outcomes

Layer 5 evaluates the trigger against the `DecisionSnapshot.input_fact_group`, its declared
`FrozenHistoryView` slices, and (where declared) `FrozenCalendarView` results; it evaluates every
semantic guard and envelope against that same immutable snapshot. Facts produced by Layer 4 after the input barrier are visible only through
`semantic_claims` or `semantic_episodes`, not as additional Layer-2 trigger members. A plan using
the `occurrence` primitive may name only a declared semantic-episode slot from that collection. A fact
appended later cannot affect that evaluation. This prevents the trigger/condition race documented for
automations that inspect a changed current state after their triggering event in
[Home Assistant](https://www.home-assistant.io/docs/automation/condition/).
The `state_transition` primitive uses only its staged previous/current pair
from the same `DecisionSnapshot`, including when the current claim was produced
by Layer 4 after the Layer-2 intake barrier; it does not query live HA or
the durable history store.

```python
ReactionEvaluationOutcome = Literal[
    "not_triggered",
    "guards_unsatisfied",
    "abstained",
    "eligible",
]

@dataclass(frozen=True)
class ReactionEvaluationResult:
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str | None  # None only before any activation exists or starts
    reaction_descriptor_id: str
    reaction_descriptor_version: str
    subject: Location
    snapshot_id: str
    trigger_when: EvidenceInstant
    outcome: ReactionEvaluationOutcome
    evaluation_reason_codes: tuple[ReactionEvaluationReasonCode, ...]
    suppression_reason_codes: tuple[AutomationSuppressionReason, ...]
```

`not_triggered` and `guards_unsatisfied` are ordinary non-notifiable results.
The independent §3.2 post-restart active-channel notice does not relabel a
`not_triggered` result as an action attempt. `abstained` means a
required semantic input is missing, stale or invalid, or the context lies outside the envelope; it uses
Layer 3 §6.3.1's availability-occurrence contract, with Layer 5 as suppression owner. Only `eligible`
proceeds to action admissibility. It is still not a command and contains neither an `ApplyStep` nor a
raw HA target.

An `eligible` result has the current nonempty activation id; an absent id
cannot compile an automatic bundle. A non-eligible result retains the id of
an already active sequence, if one exists, without minting a replacement on
abstention or guard failure. Outcome validation is closed: `not_triggered` has exactly `("trigger_not_matched",)` as its evaluation
reasons; `guards_unsatisfied` has exactly `("semantic_guard_unsatisfied",)`; `abstained` has no
evaluation reason and a non-empty canonical Layer-3 `AutomationSuppressionReason` tuple; `eligible`
has both tuples empty. No `ReactionEvaluationResult` may carry an arbitrary string.

## 6. Action admissibility and execution

### 6.0 Shared hold and command-ownership admission

Layer 5 owns command arbitration, including leases for work already admitted in another cycle.
Before the input barrier it freezes a `CommandOwnershipView` of unresolved in-flight channel leases:

```python
@dataclass(frozen=True)
class CommandLease:
    actuator_id: str
    controlled_channel: str
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str
    snapshot_id: str

@dataclass(frozen=True)
class CommandOwnershipView:
    leases: tuple[CommandLease, ...]  # canonical channel-key order; at most one per key
    layer2_generation_fingerprint: str
    fingerprint: str
```

Its key is the canonical `(actuator_id, controlled_channel)` in the committed Layer-2 generation;
its value identifies the owning `(reaction_id, configuration_generation_id, reaction_activation_id, snapshot_id)` bundle.
The fingerprint is SHA-256 of RFC-8785 canonical JSON over the ordered leases and Layer-2
generation fingerprint. It contains no HA endpoint or actor identity. An empty
view is an explicit empty map, never a missing authority input. Layer 4 transports the frozen view
in `DecisionSnapshot` without interpreting it. Layer 5 uses the snapshot's Layer-0
`HoldAdmissionView`; it cannot read a newer hold table while deciding that snapshot.

Hold admission matches the exact `(actuator_id, controlled_channel)` entry in Layer 0 §6.1.1.
With `scope="channel"`, every automatic bundle member addressing that channel is blocked. With
`scope="changed_facets"`, a member is blocked when any facet affected by any of its HA calls
intersects the hold's divergent-facet set; a disjoint member remains eligible. A blocked member
blocks its entire bundle, never just selected calls. Each core translation entry declares the
complete canonical affected-facet set, including predictable side effects (for example, a
brightness command that also powers on a light), and its physical matcher. `targeted_facets`
must cover that set; staging rejects an incomplete or unresolved mapping. Runtime admission
never executes a call whose effects were omitted from the checked view. The earlier
functional-domain mapping is historical and has no admission role.

#### Shared next-step scheduling slot

For every active step-programmed Reaction, the Initial-V3 contract permits one next `AtJob`.
Layer 5 owns one process-local next-step slot keyed by `(reaction_id, configuration_generation_id,
reaction_activation_id)`. Its `AtJob.job_id` is stable for that activation and the core
`next_step` purpose; it does not include a mutable plan fingerprint, mode, session, episode,
Actuator, or `planned_step_id`. A descriptor supplies the bounded next boundary's `due` and its
Layer-0 `AtJob.basis`: a boundary derived from civil or calendar time (a presence-simulation
session or episode boundary, a comfort-trajectory calendar return boundary) is `wall_clock`; a
boundary derived only from an elapsed duration after an in-process anchor (an adapter step-settle
interval) is `elapsed`. It also supplies the
canonical nonempty ordered `(actuator_id, controlled_channel, planned_step_id)` tuple and
current validation inputs; concurrent bundle members share that boundary. The job id is
the replacement key; each `planned_step_id` identifies a channel's program step, not a
second timer. Staging rejects a
step-programmed descriptor that cannot supply this bounded next-step contract.

An event-driven program step uses the same descriptor-produced
`planned_step_id`, canonical target, activation and common admission as a
timed step. It is selected only from a fresh staged event or state transition
in the current `DecisionSnapshot`; repeated evaluation of that event and
retry of its step id cannot admit it twice. It occupies no `AtJob` slot.
When the same cycle contains a due timer and a relevant event, the one
`evaluate_program` result supplies the effective step for each channel;
Layer 5 never separately dispatches the timer and event proposals. The
timed slot is replaced or retained from that same result. A stale callback
or event from a closed activation is ignored before hold release or command.
After restart, neither a missed timed step nor an event observed only before
the gap is replayed; fresh current-state continuation may select a new step
under the descriptor's declared rule and ordinary admission.
For an event step that first releases a `next_reaction_step` hold, Layer 5
retains one bounded process-local pending boundary token per selected channel,
each containing the selected
`planned_step_id`, source event identity and activation, but no frozen
command target. The next fresh snapshot passes this token to the same
`evaluate_program`; only its staged typed continuation condition can select
a current target. The token is consumed after that evaluation and is never
persisted or restored. A failed continuation produces the existing skipped
step outcome, not a replayed event or an unguarded command (§6.2). A guard
veto in that post-release attempt cannot re-arm the consumed event boundary;
only a later fresh qualifying input may select another step under the
descriptor's rule.

Layer 5 keeps the selected step-reference tuple, `due` and a process-local arm revision in that
slot. Re-evaluating an unchanged *pending* selection leaves its timer armed. A changed candidate replaces
the same `AtJob.job_id` through Layer 0 §3.1; a verified end, authority revocation or
configuration/activation replacement cancels the old slot. Cancel/replacement advances its arm
revision. A callback bound to an obsolete revision, generation, activation or selected step tuple is
discarded before any command or hold release. The accepted due callback retires that timer and
advances the arm revision before requesting a fresh `DecisionSnapshot`; another callback from
the same arm cannot execute the selection twice. Layer 5 serializes admission of the selected
boundary and records each admitted member's planned-step identity before its first HA call
or `already_satisfied` terminal result;
a second evaluation cannot admit that member again. A guard veto need not consume the
descriptor's planned-step identity: a later valid evaluation may select that identity again only with a new
current due boundary under the descriptor's program rule. The callback never applies a target
captured when the job was armed.

Missing or invalid required input and a guard veto are nonterminal: they neither mint a new
activation nor invent a future step. Layer 5 cancels action-only work it cannot currently
validate, while retaining an already identified due boundary that must evaluate an active
`next_reaction_step` hold's non-command release (§6.0). A later valid input or guard change
requests a fresh evaluation of the same activation, selecting at most one next job in the
same slot. Each descriptor's existing program contract decides which future step is then
eligible; this shared mechanism does not replay past commands, select a device-specific
target, or alter normal-exit and follow-up policy.

#### Trigger-driven delayed action slot

A descriptor-declared sustained-state trigger may use the same Layer-0
`AtJob` replacement mechanism for one delayed action decision. Layer 5
keeps one process-local slot keyed by `(reaction_id,
configuration_generation_id, reaction_activation_id, "delayed_action")`.
Its stable `job_id` contains those identities and the fixed purpose, not
the selected duration, artifact revision, Actuator, target or snapshot. The
job has Layer-0 `AtJob.basis="elapsed"`: its wait is a duration from the
in-process qualifying anchor.
The slot contains the original qualifying-state anchor, effective due,
exact timing path, one stable activation action identity and an arm
revision. A trigger-only descriptor has no concurrent programmed-step
slot for that activation. An unchanged selection does not re-arm; a changed
eligible artifact, model availability or semantic configuration replaces or
cancels the old arm under the ordinary authority and activation rules.
Only an unexecuted decision is recalculated from its original in-process
anchor. If its new due is already past, Layer 5 requests one immediate fresh
evaluation instead of replaying a missed callback.

The callback compares the current generation, activation, timing path,
action identity, selected due and arm revision. A mismatch is a no-op.
An accepted callback retires the arm before requesting a fresh
`DecisionSnapshot`; it never carries or applies a stored target. A valid
exit from the staged qualifying set, authority revocation, configuration
replacement or verified activation end cancels the slot and advances its
revision. While the source is unreadable, no due callback commands. After
fresh requalification, the declared gap semantics determine whether the
original anchor remains and whether an elapsed due requests evaluation.

At or after due, Layer 5 evaluates the current trigger/continuation state,
bundle target and every ordinary admission gate. It serializes one
admission per activation action identity, recording that identity before
the first HA call or an `already_satisfied` terminal result; a duplicate
callback, snapshot or retry cannot admit it again. A veto or unavailable
required input does not consume the action identity and does not spin an
already elapsed `AtJob`: it waits for a fresh relevant state, guard, hold,
authority or model transition before another current evaluation of the
same activation. A new effective delay may move the due into the future;
only then is a replacement job armed. The target is always recomputed,
and a passed due alone grants no command permission. The process-local
anchor and job are not restored after restart; the first fresh qualifying
sustained state begins a new full wait under the current policy (§3.2;
Layer 0 §3.1).

#### Bounded learned-delay selection

For a descriptor-declared delayed path with one staged typed state and a
closed nonempty set of qualifying values, Layer 5 may select its one
effective wait from a `LearnedWindow` and an eligible Layer-3
`FutureStateFractionOutcome` forecast for that exact state and set. Staging
requires `calibrated_from` and `where` to identify the same fact type and
Location as `condition_ref`, exact equality of the model outcome's
`qualifying_values`, and a forecast horizon equal to
`LearnedWindow.maximum`. The descriptor's
minimum action dwell is this window's `minimum`, not an additional timer.
For this path `minimum.seconds`, `maximum.seconds` and `seed.seconds` must be
representable as positive integer milliseconds within their ordinary
construction-time bounds (Layer 0 §3.2).

Let `q` be the eligible adopted model's finite scalar forecast of the fraction
of `[anchor, anchor + window.maximum]` for which the state belongs to the
qualifying set. Its result must have dimension `dimensionless`, unit `1`,
exact staged state, qualifying set, Location and horizon, and `0 <= q <= 1`;
any mismatch makes it unusable. The
selected wait in milliseconds is
`ceil(min_ms + (max_ms - min_ms) * (1 - q))`, rounded upward to the next whole
millisecond. Thus `q=1` chooses the minimum, `q=0` chooses the maximum, and
intermediate estimates choose intermediate waits without a second threshold
or weight. This is a versioned descriptor-authorized selection rule, not an
authority granted by the statistical result.

For the separately registered room-return timing path, the adopted eligible
`RoomOccupancySurvivalModel.return_delay` `SurvivalResult` supplies
`r = 1 - S(window.maximum) - sum(competing cumulative incidences at window.maximum)`.
This is the probability of room return by the staged maximum, not the
fraction of future time spent absent. The path requires a finite,
monotone, schema-valid curve with an exact point at that horizon and
`0 <= r <= 1`. Its effective delay is
`ceil(min_ms + (max_ms - min_ms) * r)` in positive integer milliseconds.
Thus zero estimated return risk selects the minimum and full risk selects
the maximum; intermediate probabilities select intermediate delays.
The core uses the existing probability tolerance to validate survival and
competing-risk mass, but requires the derived `r` itself to be within
`[0, 1]`; an invalid result falls back to the seed rather than being
clamped into a command. Its first registered horizon
is one minute; staging requires `minimum.seconds >= 60`, a maximum that is an
exact registered curve horizon, and seed/bounds representable in positive
integer milliseconds. The descriptor owns this formula and exact model role.
It is not the state-fraction selector and does not authorize another trigger
or Actuator intent.

For either selector, an unavailable, withdrawn, stale, mismatched or
unadopted artifact selects the already authorized `seed` unchanged. Layer 5
uses the selected duration from the current occurrence anchor and later
performs fresh trigger, target, hold and guard checks before any `ApplyStep`.
A valid transition between qualifying values preserves that occurrence's
anchor. A valid state outside the set ends it and cancels its pending delay.
An unavailable or invalid state suspends action and marks an observation
break; a due callback during the break cannot command. The staged
`ReactionDelayTimerSemantics` determines accounting for an in-process break:

- `continuous_observed` discards the prior dwell. A fresh qualifying state
  may start a new dwell under the descriptor's start rule.
- `accumulated_observed` retains only previously observed qualifying time
  and pauses accumulation during the break. A fresh qualifying state resumes
  the remaining duration; a fresh nonqualifying state cancels.
- `elapsed_if_requalified` retains the original anchor and due. If the last
  valid pre-break and first fresh post-break states both belong to the staged
  qualifying set, it credits elapsed wall time across the break for this
  Reaction only. If due has passed, it requests one fresh evaluation
  immediately. A nonqualifying return cancels the occurrence. Two distinct
  values are compatible only when that typed set explicitly includes both;
  an unknown pre-break value cannot establish compatibility.

None of these modes asserts that physical state was continuous during an
unobserved interval, creates a synthetic trigger edge, or supplies a Layer-3
training sample. An event-only trigger cannot use endpoint agreement to
replay an occurrence. Neither historical outcome joins observations across a
gap (Layer 3 §§4.2, 4.4.1). These gap-time modes apply only while the same
Heima process retains its live occurrence. After any process restart, Layer 5
restores neither activation, anchor nor `AtJob` (§3.2; Layer 0 §3.1). Once a
fresh completed HA intake supplies a valid qualifying state, a
descriptor-declared sustained-state delayed path starts a new full timer at
that reading under current policy, even without an observed crossing. This
runtime start is not a historical transition or a replay of an event-only
trigger. Unreadable or invalid state cannot start it; missed pre-restart due
times never command or shorten the new wait.
The trigger-job and model-specific eligibility details are those closed by CA4-13 above;
the artifact-adoption transitions are in §4.2 and Layer 3 §4.9. This
paragraph fixes the selection math and qualifying-state continuation.

#### Hold release at a future Reaction step

`next_reaction_step` is a versioned core-descriptor capability, not an inference from a changed
HA state or a generic `ReactionEvaluationResult`. A descriptor offering it must
also register a `normal_exit_contract` that distinguishes a canceled or
exhausted program from an unavailable step source. It declares a bounded,
ordered stream of future step identities for each affected logical channel;
the descriptor declares whether a boundary is timed or selected from a
fresh typed event/state transition. The
configured Reaction activation owns that sequence. At every such step the core can identify
`(reaction_id, configuration_generation_id, reaction_activation_id, planned_step_id, actuator_id,
controlled_channel, canonical_target_fingerprint)` independently of whether the step's guards
will admit a command. An `ApplyStep` is one member of the *current* admitted bundle (§6), so
the next member of that bundle, a retry, and an ordinary re-evaluation are not future steps.
The administrator cannot forge or supply a step identity or convert a non-scheduled Reaction
to this release mode. The descriptor retains an identified timed boundary
and its current planned target across evaluation cycles until terminal
handling. An event boundary exists only in the fresh snapshot containing its
qualifying event/state transition; it is never replayed from an earlier
cycle. A guard veto may suppress a command but cannot erase an identified
due boundary or a valid currently selected event step. At that qualifying
step the hold releases before fresh admission even if the guard still vetoes
the command. A verified normal exit may release it earlier; temporary
source unavailability cannot invent an exit or a step.
The first later step of the same Reaction/generation/activation/channel whose canonical target differs
from the target that anchored the hold releases its entire channel hold before that step's
ordinary command admission. Because the step target may be computed from the current immutable
snapshot, this release is a preliminary non-command result: Layer 5 submits it to Layer 0,
abstains from dispatching affected channel bundles against the old snapshot, and requests a
fresh cycle; unrelated channels may complete their ordinary admission. The next frozen
`HoldAdmissionView` no longer contains the hold; current guards, ownership, authority, and
physical state are evaluated afresh before any call. This avoids mutating a snapshot while
using it for an action. For an event-selected release, the descriptor's staged typed
continuation condition must still qualify in that fresh snapshot. The
process-local selected step identity is used only to prevent a duplicate
boundary; the old event is not replayed as action authority. If continuation
fails or is unavailable, no call is admitted and the existing skipped-step
follow-up applies. A step that repeats the old target does not release the
hold. A change to any target facet counts; a different facet's programmed change can thus
release an intervention on another facet, after which the full new target may restore the
resident-adjusted value. This is the explicit simplicity tradeoff of one shared channel
boundary. A future step of another Reaction or a later activation of the same
Reaction cannot silently release the hold. A stale job from a closed activation
fails the activation-id check before it can admit a command.
When selective admission lets a different Reaction confirm a disjoint facet on
the same channel, Layer 5 submits that facet's admitted Reaction id, generation,
activation id, confirmed target fingerprint and planned step id (if
applicable) with the normalized transition. A single observation involving facets from both Reactions
still yields one channel transition. Layer 0 §6.1 stores these sources per facet
in the lifecycle audit, while the Reaction activation that opened the hold remains its sole
release owner. The other Reaction's later step neither resets the shared deadline
nor qualifies as `next_reaction_step` for this hold.
If B's confirmed target is replaced, B's activation normally ends, or B
loses authority while its facet is
divergent, Layer 5 reports that the old admitted expectation is no longer
current. Layer 0 §6.2 removes only B's affected facets; A's hold and release
boundary remain if another divergent facet exists. If none remains, the hold
ends with `expectation_superseded`, not physical convergence. A merely due B
step or rejected candidate is insufficient evidence that its prior admitted
target ended. B's replacement target still needs ordinary admission and
physical confirmation before a later edge can create a new divergence.

The step boundary and physical outcome are separate. If guards or arbitration in that
fresh cycle skip the new command, the hold still ends; no physical-success or closed-device claim is made.
Layer 5 records the skipped planned action and emits a resident-visible warning when the
expected follow-up did not occur. An admitted but unconfirmed call uses the normal pending
apply outcome and warning path (§6.0.1). If the condition later becomes true while the new
target remains current, a fresh Reaction evaluation may attempt it; it is not a replay of the
old step. A temporarily unavailable next-step source does not prove that a Reaction was
cancelled or completed and cannot release the hold on that basis. A valid step
source reporting no later step and no ongoing target proves completion only
when the registered descriptor's `normal_exit_contract` recognizes that
evidence for this configuration generation; it then uses the same exit policy
as normal cancellation.

Only a `normal_cancellation` or `natural_completion` result from that contract
releases a hold owned by the matching Reaction activation as a normal exit
without another step. The configured Reaction remains enabled for a later
activation under its current authority.
A verified normal-cancellation signal first withdraws all unsent ordinary
steps of that activation from dispatch eligibility, including calls remaining
in an admitted bundle. The per-call fence rejects them before any wait for
follow-up intent preparation or any terminal-step admission;
calls already submitted to HA retain their recorded outcomes.
The coordinator processes a committed, descriptor-verified cancellation
before deciding the next HA call; an unsent ordinary call cannot overtake it.
A one-shot bundle finishing its calls is not such a result; a descriptor with
no normal-exit contract keeps its hold until its configured fixed-duration
boundary or another ordinary invalidation/convergence rule. Immediate authority
revocation instead invalidates the hold. The default exit policy sends no command and preserves the observed physical state.
It requests a resident follow-up only when the latest observation differs from that
Reaction's last confirmed target or is unavailable (§6.0). A later policy decision
does not alter an already emitted append-only follow-up event.
Any later resident-facing outcome requires its own approved event under the ordinary event contract.

A versioned core descriptor may instead declare a final target for normal cancellation
or natural completion. Its registered `program_evaluator` selects that typed
terminal step, or reports that the declared step's target is unavailable, in
the same `normal_exit` decision whose verified
`ReactionNormalExitResult` closes the program; Layer 5 never invokes another
target-choice evaluator. A normal cancellation request stops scheduling future
steps of that activation, but retains the configured Reaction's current
authority for this one terminal action. Layer 5 first
releases its hold as a preliminary non-command result and obtains a fresh frozen
snapshot, as for a planned-step release above.
The same descriptor specialization revalidates the terminal step's current
target in that fresh snapshot. If unavailable, Layer 5 records
`terminal_action_skipped` without offering a command. Otherwise Layer 5
offers it once through ordinary
whole-bundle admission, safety guards,
channel arbitration, `ApplyStep` execution and physical verification. The terminal action
finishes dispatching under those rules, or is skipped by them, before that
activation closes. A failed guard does not keep the activation open. The
configured Reaction retains its existing authorization for a later qualifying
activation. If a dispatched action remains physically unconfirmed, its pending
observation may resolve after the activation closes, but that activation cannot
dispatch another call. Layer 5 reports a skipped or unconfirmed final action and the actual observed
state to the resident. No final-target call is admitted after authority has been revoked;
administrative disablement and resident-consent revocation remain immediate as specified
in §6.2. Staging rejects `next_reaction_step` unless the descriptor provides
both its bounded future-step identity contract and its provable normal-exit
contract; otherwise the configured channel uses `fixed_duration`. A descriptor
with no normal-exit contract cannot infer one
from the completion of an individual command.

#### Resident advisory occurrence

An eligible advice member (§3.2) gives Layer 6 one typed occurrence; Layer 6 alone appends the
`reaction.advisory` event fact and its delivery record in the unified outbox (Layer 0
§4.5), and delivers it.

```python
@dataclass(frozen=True)
class ReactionAdvisoryOccurrence:
    operation_id: str                 # sha256 of "reaction.advisory.operation.v1:" + RFC-8785
                                      # [reaction_id, configuration_generation_id,
                                      #  reaction_activation_id, member_index, phase]
    phase: Literal["opened", "closed"]
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str
    snapshot_id: str
    subject: Location
    member_index: int
    action_intent: str
    objective_id: str | None          # the configuration's objective, when it has one
    opening_id: str | None
    actuator_id: str | None
    controlled_channel: str | None
    closed_reason: Literal["activation_ended", "authorization_disabled", "superseded"] | None
    response_request_id: str | None   # the feedback request id on "opened"; None on "closed"
    occurred_at: EvidenceInstant
```

The operation id makes each phase at most once per activation and member, across retries and
re-evaluations. `closed` is produced when the activation ends, when administrative authorization
is disabled or revoked, or when a configuration successor replaces the generation; `closed_reason`
is `None` exactly for `opened`. The occurrence carries only these closed fields; Layer 6 owns the
text, severity `info`, family and quiet-hours behavior. The closing phase is audit and delivery
state only: Layer 6 appends its `reaction.advisory` fact, retires the opening record undelivered if
it is still waiting (for example deferred by quiet hours), and never sends residents a closing
notice; an advice already delivered is not withdrawn. An activation never survives a restart, so
Layer 6 treats an `opened` advisory from before the current process start without a `closed` phase
as closed: it retires an undelivered record without delivery and appends no fact.

#### Resident action notice

A descriptor version with `resident_action_notice=True` tells residents what it did. In Initial V3
only `safety.weather_protection` declares it; every other descriptor declares `False`. When every
channel selected by an activation's step has a recorded outcome (after its confirmation window),
Layer 5 gives Layer 6 one occurrence for that activation:

```python
@dataclass(frozen=True)
class ChannelNoticeOutcome:
    actuator_id: str
    controlled_channel: str
    outcome: Literal["completed", "unconfirmed", "failed", "skipped_manual_hold"]

@dataclass(frozen=True)
class ReactionActionNoticeOccurrence:
    operation_id: str                 # sha256 of "reaction.action_notice.operation.v1:" + RFC-8785
                                      # [reaction_id, configuration_generation_id, reaction_activation_id]
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str
    snapshot_id: str
    subject: Location
    channels: tuple[ChannelNoticeOutcome, ...]  # canonical key order; bounded by staged endpoints
    occurred_at: EvidenceInstant
```

Layer 6 appends it as one `reaction.action_notice` event fact with severity `info` and renders its
text at delivery (for example "windows and awnings secured for rain; living-room window left open
by you"). It summarizes and does
not replace a channel's `manual_hold_active` availability notice or a `reaction.follow_up` warning.

#### Proposal review notice

When Layer 5 creates a `ReactionProposal` or `ReactionArtifactAdoptionProposal` (§4.1), when a
pending proposal that had become not approvable becomes approvable again, and when a proposal stops
being reviewable, it gives Layer 6:

```python
@dataclass(frozen=True)
class ProposalReviewOccurrence:
    operation_id: str                 # sha256 of "proposal.review.operation.v1:" + RFC-8785
                                      # [proposal_id, phase, cause_record_id]
    phase: Literal["created", "approvable_again", "closed"]
    cause_record_id: str              # the §4.1 record that caused the phase (below)
    proposal_id: str
    proposal_kind: Literal["reaction_configuration", "artifact_adoption"]
    reaction_descriptor_id: str
    reaction_descriptor_version: str
    subject: Location
    evidence_revision_id: str
    closed_reason: Literal["accepted", "rejected", "proposal_incompatible", "not_approvable"] | None
    occurred_at: EvidenceInstant
```

`cause_record_id` is the initial `ProposalEvidenceRevision` for `created`, the
`ProposalReadinessAssessment` that records the readiness change for `approvable_again` and for
`closed` with `not_approvable`, and the terminal `ProposalReviewTransition` for the other closed
reasons. Keying the operation on that record keeps two distinct readiness changes under one
evidence revision distinct, while a retry of the same change stays one operation. `closed` with
`not_approvable` is produced only when a pending proposal whose latest phase was `created` or
`approvable_again` receives a not-approvable assessment; a later approvable assessment produces
`approvable_again`. `closed_reason` is `None` exactly for the other two phases.

Its audience is administrators only; Layer 6 appends `proposal.review_pending` for every phase and
owns grouping into a digest. A proposal is open for review from its latest `created` or
`approvable_again` phase until a later `closed`; the closing phase is never delivered on its own.
The occurrence carries no evidence payload, learner text or approval control.

#### Household consent request notice

When a Reaction enters `authorized_awaiting_household_consent`, and when that state ends, Layer 5
gives Layer 6 one occurrence per phase:

```python
@dataclass(frozen=True)
class ConsentRequestOccurrence:
    operation_id: str                 # sha256 of "reaction.consent.operation.v1:" + RFC-8785
                                      # [reaction_id, configuration_generation_id,
                                      #  authority_transition_id, phase, response_request_id]
    phase: Literal["opened", "reissued", "closed"]
    reaction_id: str
    configuration_generation_id: str
    authority_transition_id: str      # the transition that opened the request
    response_request_id: str | None   # the ingress request id; None exactly for "closed"
    reaction_descriptor_id: str
    subject: Location
    closed_reason: Literal["granted", "declined", "authorization_disabled", "superseded"] | None
    occurred_at: EvidenceInstant
```

Its audience is the residents named by `HouseholdConsentAuthority` (§7.1.1); Layer 6 appends it as
one `reaction.consent_request` event fact per phase. The notice is actionable: on `opened` the
response owner `layer5.household_consent` declares a request to Layer 0's response ingress (Layer 0 §5.1.3) with actions `grant` and `decline` and actor category
`resident`, expiring when the request closes. A `VerifiedResponse` is applied only if its
`actor_ref` is currently in `HouseholdConsentAuthority`: `grant` appends exactly the authority
transition of `set_reaction_household_consent` against the opening authority transition as its
precondition, using the ingress id as the operation id; `decline` changes no authority and closes
the request with `declined` for the whole household, so the first answer from any authorized
resident decides and every other authority's notification is cleared. A stale precondition, a
removed resident or a closed request changes nothing.

Ingress declarations do not survive a restart, while a Reaction awaiting consent does. At each
process start, for every Reaction still in `authorized_awaiting_household_consent`, the owner
declares a fresh request and gives Layer 6 one `reissued` occurrence carrying the new
`response_request_id`; Layer 6 replaces the earlier notification of the same request through its
item tag, so no button with a withdrawn id stays usable. The same `set_reaction_household_consent` command from the Layer-8 surface remains
available; both paths share one authority rule.

#### Advisory feedback

Each `ReactionAdvisoryOccurrence(opened)` is actionable for feedback only: before giving it to
Layer 6, the owner `layer5.advisory_feedback` declares a request, whose id the occurrence carries
as `response_request_id`, with actions `done`, `dismiss` and `not_useful`, actor
category `resident`, open for as long as the activation lasts and withdrawn at its `closed` phase;
there is no separate feedback window. A `VerifiedResponse` appends one `reaction.advisory_feedback` event fact
(`advisory_operation_id`, `action`, `actor_category`, `recorded_at`), once per advisory and
action. Feedback grants no authority, sends no command, changes no Reaction state and is never a
correction of Heima. It is bounded explicit evidence for the future
`ResidentPresentationPreferenceModel` (Layer 3 §4.8.3); an unanswered advisory is censored, not a
negative answer.

#### Resident follow-up operational event

Layer 5 owns the operational cause, not resident text or event-fact persistence. At a qualifying
boundary it gives Layer 6 one typed `ReactionFollowUpOccurrence`; Layer 6 alone validates the
publication mapping, appends the existing `reaction.follow_up` operational event
(`OperationalEventValue`, Layer 1 §3.1), then delivers its derived `HeimaEvent`. There is no
hold-specific notification envelope, resident control, or second fact type. A later policy
change cannot edit or clear an append-only outcome; a later material outcome needs its own event.

```python
ReactionFollowUpPath = Literal["normal_exit", "planned_step", "terminal_action"]
ReactionFollowUpOutcome = Literal[
    "ended_without_final_target", "planned_step_skipped", "planned_step_unconfirmed",
    "terminal_action_skipped", "terminal_action_unconfirmed", "interrupted_before_outcome",
]

@dataclass(frozen=True)
class ReactionFollowUpIntent:
    operation_id: str
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str
    actuator_id: str
    controlled_channel: str
    subject: Location
    path: ReactionFollowUpPath
    hold_id: str | None
    planned_step_id: str | None
    later_step_remains: bool
    expected_facets: dict[str, str]     # facet -> canonical JSON text; possibly empty
    observed_facets: dict[str, str]     # facet -> canonical JSON text
    observation_available: bool
    observed_at: EvidenceInstant | None
    observation_epoch_id: str | None
    prepared_at: EvidenceInstant

@dataclass(frozen=True)
class ReactionFollowUpOccurrence:
    operation_id: str                    # one opaque id for this boundary and channel; stable on retry
    reaction_id: str
    configuration_generation_id: str
    reaction_activation_id: str
    actuator_id: str
    controlled_channel: str
    subject: Location
    path: ReactionFollowUpPath
    outcome: ReactionFollowUpOutcome
    hold_id: str | None                 # causal active/released hold, when one exists
    planned_step_id: str | None
    later_step_remains: bool
    expected_facets: dict[str, str]     # last confirmed or due/final target; canonical JSON text
    observed_facets: dict[str, str]     # latest bounded projection; possibly empty
    observation_available: bool
    observed_at: EvidenceInstant | None
    observation_epoch_id: str | None
    occurred_at: EvidenceInstant
```

Layer 5 owns both immutable contracts; `ReactionFollowUpIntent` is the sole durable
pre-outcome projection (Layer 0 §4.5), and `ReactionFollowUpOccurrence` is its transient
resolved result. Layer 6 validates both and requires the stable operation, Reaction/generation/activation,
Actuator/channel, subject, path, hold and planned-step identities of an occurrence
to match its prepared intent. The due/final target, later-step status and observed
projection may be resolved only after the fresh snapshot and therefore may differ
from preparation. The stored intent proves the boundary, not a future physical result.
At the `PersistedProjection` boundary, Layer 6 serializes the typed `subject`
as the scalar RFC-8785 JSON text of Layer 1's canonical `LocationKey`, rather
than retaining a nested `Location` dataclass or a `room_ids` collection.
Recovery decodes and validates that key before reconstructing the typed intent;
the event fact still uses a real `Location` as `where`. Staging bounds the
serialized key length. This keeps even a `rooms` Location within the projection's
depth-two limit without changing location identity.

For a persisted or fact-bound projection, the core takes each target-contract
facet value through one lossless scalar codec: its value is the RFC-8785
canonical JSON text of that facet's normalized JSON value. Thus a boolean is
`"true"`, a number is `"0.7"`, a colour array is `"[255,128,0]"`, and a
string mode is `"\"heat\""` in the containing JSON object. Parsing the text
must reproduce the same normalized value and canonical bytes. The codec
rejects non-finite numbers, duplicate object keys, raw HA objects and values
whose canonical JSON cannot round-trip. It is an audit/notification projection,
not a replacement for the typed `ChannelTarget` or physical matcher.
Facet keys use the staged, nonempty `[a-z][a-z0-9_]*` grammar and at most
64 UTF-8 bytes; no two facets may normalize to one key. Every target contract
declares a finite maximum canonical byte length for each possible facet value.
Staging verifies all supported values are losslessly encodable within that
bound and that the complete intent, hold audit and follow-up fact
fit Layer 1's depth-two/8 KiB validators under the relevant maximal facet
sets and bounded identities. The hold proof includes the longest source
identity for each facet across all staged Reactions that can contribute on
the same channel, even under selective admission. A contract with an unprovable maximum is
rejected. Runtime validates the copied actual projection and the final
Layer-6 event. The event stores no rendered text (Layer 1 §3.1), so staging
needs no renderer bounds; Layer 6 renders text only at delivery. Layer 6
flattens these maps to scalar `expected.<facet>` and
`observed.<facet>` context keys under Layer 1 §3.1; it never nests a facet
map inside `OperationalEventValue.context`.

For each qualifying channel boundary, core derives `operation_id` as lowercase
hex SHA-256 of the RFC-8785 array
`[reaction_id, configuration_generation_id, reaction_activation_id,
boundary_kind, boundary_identity, actuator_id, controlled_channel]` prefixed
by the fixed domain separator `reaction.follow_up.operation.v1:`.
`boundary_kind` is the exact `ReactionFollowUpPath`; `boundary_identity` is the
stable `planned_step_id` for `planned_step`, or the activation's single verified
normal-exit boundary for `normal_exit`/`terminal_action`. A normal exit occurs
at most once per activation and channel, so its identity is the fixed literal
`exit`; path distinguishes the two exit policies. Core validates all tuple
components as nonempty staged identities and rejects a collision between
distinct tuples. One exit covering several channels produces distinct ids;
the same channel/boundary retry keeps one id even if a new evaluation snapshot
arrives. The first prepared intent is frozen for exact retries; a later
observation may change only the final occurrence fields that §4.5 permits,
never the prepared payload under the same id. No administrator, learner or
adapter supplies the id or a substitute boundary identity.

The core validator rejects empty identities, a mismatched activation against
the prepared intent (and, for a live occurrence, its current boundary), an identity absent from the staged
immutable generation or prepared intent, a mismatched Actuator/channel/Location,
a non-canonical or oversized facet projection, inconsistent `observation_available`,
a missing observation instant/epoch for a claimed complete observation, an outcome
incompatible with `path`, and a planned-step id outside `planned_step`. The exact
path/outcome pairs are `normal_exit`/`ended_without_final_target`,
`planned_step`/`planned_step_skipped|planned_step_unconfirmed`, and
`terminal_action`/`terminal_action_skipped|terminal_action_unconfirmed`;
`interrupted_before_outcome` is the recovery-only alternative for any of these paths. `interrupted_before_outcome`
is legal only during recovery of a durably prepared but unfinished intent; it
uses the persisted activation id without requiring a live activation and reports uncertainty,
not a skipped command or physical success. Layer 5 records the observation instant and epoch with
the projection; a post-restart event labels it as the *last pre-interruption observation*, never
as current device state. No raw HA state or personal actor identity enters this record.

For `normal_exit` without a final target, a follow-up is due when Layer 5 has a
confirmed channel target from this activation in the current process run and the latest valid observation
still differs from it or observation is unavailable. A pre-restart target alone cannot
qualify: Recovery resumes current policy without restoring hold or pending confirmation. An expired
hold alone does not cause one, but its expiry does not suppress a still-unresolved difference.
A verified complete match suppresses this exit notice. A normal exit with no current-run
confirmed target cannot infer a mismatch and produces no follow-up solely from an old
configuration target or another activation's target. For `planned_step`, the selected target-changing
step that releases this Reaction's channel hold needs a notice if its command is skipped or
physically unconfirmed. For `terminal_action`, normal cancellation/completion with a declared final
target needs a notice if that action is skipped, including an unavailable
estimate-dependent target, or physically unconfirmed. A terminal pending
outcome may resolve after the activation closes, but that activation cannot dispatch again. Ordinary hold
activation, a fully confirmed due/final target, and administrative disablement or consent
revocation alone emit no follow-up. A verified revocation always blocks a terminal call.

Before consuming a qualifying step or completing a normal exit, Layer 5 derives the stable
per-channel `operation_id` for that activation boundary and asks Layer 6 to prepare the minimal typed follow-up intent through Layer 0
§4.5. Layer 5 waits for its durable acknowledgement only until the positive finite
`Window` fixed by the versioned Layer-5 core runtime contract. The same technical
deadline applies to every descriptor and is measured by a monotonic clock from the
preparation request; it is not an administrator, resident, or descriptor parameter.
The core must publish and validate that bound at bootstrap; a missing, zero,
non-finite, or mutable bound is invalid. The intent records
the path, Reaction/generation/activation, channel, possible hold id, target, and last observation, but no
claim that a command occurred. Layer 5 then applies the ordinary release, fresh-snapshot,
guard, arbitration, command and physical-confirmation rules. Once an outcome is known it sends
one occurrence with the same id to Layer 6. Layer 6 atomically materializes the event and
marks the intent ready; it retries both persistence and delivery. A fully confirmed
step/final target closes its prepared intent without an event; a final target
computed from the fresh post-release snapshot is validated as an outcome rather
than required to match the earlier preparation projection. A failed close can
produce a conservative interruption warning after restart, never a claim of failure. On recovery, a prepared
intent with no committed outcome produces `interrupted_before_outcome`, never a replayed
`ApplyStep`. Current-policy automation resumes through ordinary Recovery admission and may
act independently of this notification recovery.

If preparation fails, or its durable acknowledgement is still uncertain when
the preparation deadline expires (including a write that remains pending while
storage otherwise appears healthy), Layer 5 reports `follow_up_durability_degraded`
and lets the scheduled step or normal exit proceed
through ordinary current authority and guards. It sends the resulting occurrence to Layer 6 for a best-effort ordinary queued event and
resident delivery while running, but cannot promise crash recovery of that particular
notice. When storage returns, Layer 6 first reconciles this id with any prepared intent
before committing an event; it never leaves both a pending prepared intent and a
separately committed final event under the same id. It does not retain a scheduled hold
merely to protect notification durability. An uncertain write keeps the same operation id for
later reconciliation; a discovered prepared intent may be finalized from the still-live outcome
or conservatively recovered after a crash. Administrative disablement and consent revocation
remain immediate and never await this persistence path. An intent is not a live hold, command,
checkpoint, or claim about current post-restart state.

Every `reaction.follow_up` has `warning` severity because it identifies an unresolved handoff,
skipped/unconfirmed step, or interruption that may need attention. Layer 6 sets
`notification_key = "reaction.follow_up:" + operation_id`; the per-channel key never merges distinct
outcomes. Resident text names the Reaction/channel, the known outcome and whether another
step remains. It labels an observed value with its observation time; after interruption
it says that the outcome and current device state are unverified, without asserting that
an earlier value still holds. Event-fact retry is idempotent by Layer 0 §4.5, while delivery is at least once:
if HA accepted a notification just before a crash but its acknowledgement was not recorded,
Layer 6 may repeat it. No generic actuator hazard class or `critical` severity is inferred here.

Arbitration is a bounded, whole-cycle pass, independent of registration or evaluation order:

1. Evaluate every enabled Reaction against one frozen `DecisionSnapshot`. For each `eligible`
   automatic bundle, run all non-ownership checks on every member first, including hold, consent,
   physical state, safety and cooldown. A bundle failing any such check claims no channel.
2. For the remaining complete bundles, form each set of channel keys, rejecting duplicate keys
   within one bundle at staging. A key already held by an unresolved in-flight lease blocks the
   complete new bundle. If two distinct remaining bundles claim the same key, both complete
   bundles are blocked, whether their targets conflict or address disjoint facets. The one
   exception is an **identical safe target**: when every claimant's member on that key has the
   identical complete canonical target and targeted facets, and every such intent is in its
   descriptor's `safe_direction_intents`, the claims do not conflict. The key is reserved once by
   the claimant first in canonical `(reaction_id, configuration_generation_id,
   reaction_activation_id)` order, whose member dispatches the one `ApplyStep`; every other
   claimant's member on that key sends no call and records `coalesced_identical_target` (§4.0).
   Only the dispatching Reaction's confirmed target anchors a hold. The other keys of every bundle
   follow the ordinary rules. Conflict never authorizes a winner
   by iteration order. The Initial-V3 core precedence-exception table is empty: opposing actions
   are prevented by guards before arbitration (§7.4), not by precedence. A future exception
   requires a separately reviewed, versioned core descriptor rule with explicit applicability and
   safety proof; no administrator, learner, or plugin may add one implicitly.
3. Reserve all keys of every unblocked bundle atomically in canonical key order before dispatch.
   Failure to reserve any key releases that bundle's tentative reservations and blocks the entire
   bundle. Same-bundle idempotent retry uses its existing reservation and cannot acquire a second
   lease. A lease ends only after all its calls complete/fail/cancel and any uncertain physical
   outcome is reconciled under the common pending-apply contract; no fixed wall-clock expiry or
   process restart may be treated as proof that a command did or did not take effect. A restart
   admits no new command on an unconfirmed channel until a fresh observable state and current
   authority check resolve it.

An ownership block emits `command_ownership_unavailable`; a matching active channel hold
emits `manual_hold_active`. All concurrent applicable reasons are retained in the canonical
suppression tuple. These are admission results, not execution failures. The full bundle uses one
set of reservations; a service failure stops remaining members as below and releases only after
their outcomes have been recorded. Revocation, rebinding or withdrawal of the
originating activation's ordinary dispatch eligibility after admission is
checked again at the dispatch fence
(the per-call fence in §6.0),
never treated as authorized by an older frozen snapshot. The same in-memory fence
compares the current activation id, hold entries and affected-facet intersections
for exactly the bundle's targeted Actuator/channel keys, plus the committed Actuator generation, against the admitted
snapshot immediately before every HA call. A change confined to an unrelated channel or to
disjoint facets under selective scope does not cancel this bundle. The coordinator serializes
accepted observation ingress and the final dispatch decision: it processes every edge accepted before the fence, rechecks the resulting view, and submits
the next nonblocking HA call in that same order. It also rejects a newly accepted external
observation edge on a targeted facet since the preceding call, even if pending confirmation has
not yet made that edge a hold; Heima-linked observations do not trigger this abort. An
edge accepted later is a later event, not retroactive evidence against an already submitted call. A newly observed resident change or
other divergence that changes the view before submission stops all remaining calls and members,
records them as `not_attempted`, and requests a new evaluation; no old snapshot may overwrite it.
Already sent calls retain their recorded outcome
and are never compensated merely because a later hold appeared.

For an eligible policy, Layer 5 checks against the same policy/snapshot identity:

- administrative enablement and authorization;
- any descriptor-required resident consent, including its immediate opt-out state;
- manual hold and command ownership;
- a registered logical Actuator channel whose `channel_kind` and adapter binding are permitted by the
  selected semantic intent, plus confirmed physical state;
- dwell/cooldown and one-bundle-per-policy/snapshot idempotency;
- required safety, security, weather, privacy and quiet-hours guards.

An admissibility failure for any required member means the semantic policy applied but its bundle cannot
currently act. Layer 5 emits the transient `AvailabilitySuppressionOccurrence` defined by Layer 3
§6.3.1 with every applicable reason from the descriptor's closed admission-applicability declaration,
in canonical order. It never maps one of these blocks to a learning-evidence reason or omits a
concurrent cause. It constructs that tuple only through Layer 3's frozen pure
`canonicalize_suppression_reasons()` helper; Layer 5 does not choose its own sort order. Layer 5 never
renders, persists or delivers an availability event. The immutable staged
`AvailabilityPublicationIndex` is queried only by Layer 6's `AvailabilityEpisodeTracker`. Each
availability binding Layer 5 declares names the `automation_scope_id` (the configured Reaction),
its `reaction_descriptor_id`, and whether it is enabled and resident-visible; Layer 6 derives the
notification family from the descriptor (Layer 6 §6.1). Layer 5
sends every typed occurrence to that tracker and never selects resident-visible bindings itself; Layer
6 alone owns the resident-visible `automation.availability` event/delivery path.
Before it executes any command, Layer 5 performs the complete member-by-member admissibility pass
against the same immutable snapshot. Thus a known hold, capability, physical-state, dwell or safety
failure on one member prevents the entire bundle: no known-invalid partial execution is permitted.

An admitted bundle yields one ordered `ApplyStep` per member, each addressing exactly one Layer-2
`actuator_id` and registered `controlled_channel`; the runtime resolves that member's sole HA endpoint.
An `ApplyStep` is one logical requested channel state, not necessarily one HA service call:

```python
@dataclass(frozen=True)
class ChannelTarget:
    target_contract_id: str             # closed channel-kind/adapter target contract
    values: CanonicalJsonObject         # typed by that contract, never raw HA service data
    targeted_facets: tuple[str, ...]    # canonical non-empty subset; omitted facets are preserved

@dataclass(frozen=True)
class TranslationDelayPermission:
    permission_id: str                  # unique core-owned versioned id, ending in .vN
    timing_path_id: str                 # exact descriptor timing path this entry may serve
    max_delay: Window                   # positive upper bound for this translated target
    target_validator: PureValidator     # checks the complete typed target and affected facets

@dataclass(frozen=True)
class ApplyCall:
    service: str
    data: CanonicalJsonObject            # no HA target selector

@dataclass(frozen=True)
class ApplyStep:
    apply_step_id: str
    reaction_id: str | None
    configuration_generation_id: str | None
    reaction_activation_id: str | None
    snapshot_id: str
    member_index: int
    actuator_id: str
    controlled_channel: str
    target: ChannelTarget
    expected_channel_state: ChannelTarget  # partial matcher over targeted facets only
    calls: tuple[ApplyCall, ...]           # finite, non-empty, canonical order
    source: ApplyStepSource

ApplyCallOutcome = Literal["completed", "failed", "not_attempted"]
ApplyCallFailureReason = Literal[
    "service_rejected",
    "transport_failed",
    "timeout",
    "invalid_response",
]
```

The core translation table is indexed by `(action_intent, channel_kind, actuation_adapter_id)`. It
validates semantic parameters, constructs the typed `ChannelTarget`, and encodes its finite ordered
calls and partial expected-state matcher. It never accepts an HA service, target, attribute name, or
parameter from a descriptor author or learner. For example, `light_state` may target power, normalized
brightness, canonical colour temperature/colour and transition facets atomically; `valve_position` may
target a canonical fraction; `hvac_state` may target mode, setpoint, fan-speed and swing facets and
therefore compile to several calls. An omitted facet means preserve current state, never an implicit
default, and verification/correction attribution considers only `targeted_facets`.

Each frozen core translation entry may declare a finite, unique
`TranslationDelayPermission` for a descriptor timing path. This is the
developer's versioned assertion that the entry's exact typed target may
wait up to `max_delay` in every target state accepted by its validator,
regardless of the model's current probability or selected shorter wait;
absence means that target cannot use that path. A target with an immediate
safety deadline or a smaller safe maximum must be rejected or declared
under a narrower permission and maximum. The model never supplies the
safety proof or extends the permission's bound.
The pure `target_validator` checks the translated `ChannelTarget`, its
target-contract id, every supplied value and the translation's complete
affected-facet set. It cannot infer permission from `actuator_role`, an HA
domain, a raw service, a current sensor value or an administrator-supplied
urgency flag. Registration rejects duplicate permission ids or path ids,
an unknown descriptor path, a nonpositive/nonfinite maximum, a validator
that cannot decide every admitted target shape, or an entry whose declared
maximum conflicts with its target/adapter safety contract. Changing the
validator, target envelope or maximum requires a new permission id/version;
an old Reaction never silently adopts that change.

For a delayed Reaction, staging first translates every canonical member
under its exact registered intent, channel kind and adapter. It requires
one matching permission whose validator accepts the complete target and
whose `max_delay.seconds` is at least the configured
`LearnedWindow.maximum`; it retains the permission id in the immutable
plan and its fingerprint. The current Initial-V3 vacancy path has one
member, but this per-member rule does not depend on an Actuator kind or
assume every target of one intent is eligible. At due time, Layer 5
re-translates the current target and rechecks the exact permission id,
target validator and maximum before ordinary admission. A missing or
changed permission, changed adapter or newly ineligible target blocks with
`actuator_capability_unavailable`; it never falls back to immediate dispatch
or another permission. No permission waives a current guard, hold, ownership,
physical confirmation or consent gate. An administrator chooses whether to
configure the descriptor's delayed path and its staged bounds, but cannot
declare a translation eligible or extend its core maximum.

The three Reaction identity fields are present together exactly when the
step is attached to a current admitted Reaction activation. They are all
`None` for a standalone direct-admin, resident-approved or recovery-only
target without a Reaction. `source.kind="reaction"` requires the three
fields; `source.kind="recovery"` or `"resident_response"` may carry them
only when Layer 5 has separately admitted that exact Reaction identity.
The source kind never fabricates a Reaction anchor. `snapshot_id`, channel,
target and the ordinary dispatch fence remain mandatory in both variants.
Layer 5 assigns the identity; an external request cannot supply or clear it.

At accepted-target bookkeeping, Layer 5 supplies Layer 0 §7.4 with the trusted
per-facet recovery authority anchor. For a current admitted Reaction it is the
exact `reaction_id` and configuration generation, regardless of whether a later
reconciliation step carries `ApplyStepSource.kind="recovery"`. For a standalone
direct admin or verified resident command it is the direct source kind; an
external/unknown observation supplies no desired-target anchor. Recovery checks
each Reaction anchor against the current automatic authority projection and
consent before retaining its facet. A removed, edited, disabled or revoked
Reaction cannot survive as a historical fallback. Surviving direct facets still
pass current Actuator recovery policy, channel translation and ordinary safety
admission. Several authorized facet origins may coexist in one channel baseline;
Layer 5 validates their merged current target before one ordinary `ApplyStep`.

Steps and their calls are not a distributed transaction. On a failed call, Layer 5 stops the remaining
calls in that step and every later bundle member; it records each call as `completed`, `failed`, or
`not_attempted` with a bounded redacted `ApplyCallFailureReason` where applicable. These are Layer-5
execution-audit diagnostics, never `AutomationSuppressionReason`s and never availability occurrences:
the action was admitted and attempted. The step is successful only when every call
completes; no automatic compensating call is issued. A later member is `not_attempted`, never reported
as failed. Automatic compensation could produce a less safe physical state than the observed partial
result. No member or call can attach an entity selector, service target, nested policy call, or arbitrary
command graph.

### 6.0.1 Pending apply and physical observation

Layer 5 owns one `PendingApply` per dispatched `ApplyStep`, keyed by its stable `apply_step_id` and
the committed `(actuator_id, controlled_channel, configuration_generation_id)`. The core
translation entry supplies a positive, versioned `confirmation_window: Window` and a pure
per-facet matcher over canonical observed values and `expected_channel_state`; the descriptor,
learner, administrator, and HA event cannot choose that matcher or window. Staging rejects a
translation entry without either. `targeted_facets` is the closed set that may be confirmed;
omitted facets are never treated as failed, confirmed, or held by this step.

At the final pre-dispatch observation check, a fresh, available, canonical reading that matches
every targeted facet under the versioned core matcher closes the recorded, admitted target decision
as `already_satisfied`; Layer 5 sends none of its planned `ApplyCall`s. That reading establishes the
confirmed Heima expectation for later distinct edges, and the decision may anchor correction
learning under §6.1. A merely hypothetical target or a policy that was not admitted and recorded
creates no anchor. Repeated evaluations of the same still-active trigger/eligibility episode,
configuration generation, activation id, logical Actuator/channel, and canonical target reuse the first recorded
target decision and its `apply_step_id` only while the latest valid observation continues to
match the complete target. They create neither another `already_satisfied` decision nor another
correction-learning window. A new trigger occurrence, loss of trigger/guard eligibility, a target or generation change,
loss of observation, or a valid divergence closes that satisfied episode. A terminal unconfirmed pending
outcome closes its dispatch episode but retains the recorded target decision as possible later
learning evidence under §6.1. While a hold is active, ordinary admission blocks a
new command; after release, current-policy evaluation may record a new decision under fresh
guards and authority. The current `ReactionEvaluationResult` is still recorded for each snapshot;
the reuse link is audited against the first decision identity. If even one targeted facet does
not match, Layer 5 dispatches the complete core-translated call plan when current admission
permits: it never prunes individual calls or treats a pre-dispatch match as final confirmation.
It records the dispatch observation epoch and revision, expected target, matcher version,
deadline, and Heima call-context identities in process-local pending state.

A successful return from every `ApplyCall` means `service_completed` for execution audit only;
it does not mean physical confirmation or prove which actor produced a later matching state.
Failed and unattempted calls retain their existing outcomes. A failed call may still have changed
the device, so pending observation continues for the dispatched step through its confirmation
window. Layer 5 separately records the verified origin of each observation, or `unknown` when
proof is absent; matching the target never changes that origin into Heima causation.

For a dispatched step, each targeted facet is `physically_confirmed` only by a newer valid,
available, canonical observation revision in the same uninterrupted observation epoch, at or
before the monotonic deadline, matching the versioned core matcher. A pre-dispatch match alone
cannot confirm a facet after calls that may change it. Layer 5 records confirmation time and
revision separately per facet. The whole target is `fully_confirmed` only when the latest valid
state of every targeted facet forms one coherent, simultaneously matching channel state within
the confirmation window. Separate past matches do not add up to full confirmation if a facet
diverged before the others matched. The step remains `partially_confirmed` when at least one
facet was confirmed but the coherent complete target was not, or `unconfirmed` when none was.
One normalized observation containing later valid divergences from confirmed facets may activate
or update the channel hold in one atomic transition even while another facet is pending; the channel ownership lease remains unresolved until the whole step
is reconciled. A nonmatching edge on an as-yet unconfirmed facet during pending is not itself a
hold or resident correction. Verified direct resident evidence is retained, but §6.1 cannot
attribute a correction until the complete coherent target has been observed.

At deadline, an unconfirmed facet receives an explicit `unconfirmed` outcome, with reason
`observation_timeout` or `observation_unavailable`; neither is an inferred resident action or a
confirmed physical state. If all facets matched separately but never formed one coherent
complete target, the whole step remains `partially_confirmed` with reason
`target_never_coherent`. An availability break invalidates the old observation epoch, closes
pending confirmation as unavailable, and invalidates any established hold on that channel
(Layer 0 §6). A later returned value starts a new epoch, not a late confirmation of the old step.
The ordinary current-policy decision may issue a new target only after a fresh valid observation
following the terminal pending outcome and the dispatch fence's current authority check. Until then the channel lease remains unresolved
and blocks competing bundles (§6.0). A fresh valid post-terminal reading that matches a facet
of the still-authorized recorded target may establish a current expectation for that facet,
without changing the old step's terminal execution outcome. A subsequent distinct valid
divergence from that expectation may activate or update the ordinary channel hold; the matching read
itself never activates one. A later HA state edge linked to the old Heima call remains
Heima-originated for provenance purposes; it cannot be relabeled a resident action merely because
the confirmation deadline passed. Without that verified link its origin is `unknown`.

Layer 5 sends only normalized, validated expectation/observation transitions from a current,
admitted Reaction target to Layer 0 §6. A physically matching value can establish that target
even when a different actor produced the value; the observation retains its verified origin.
A standalone `admin_command` or `recovery` ApplyStep has no Reaction hold anchor merely because
Heima dispatched and confirmed it. If the recovery delta is the current admitted Reaction
target, Layer 5 retains that Reaction identity separately from `ApplyStepSource.kind`.
Before
freezing a cycle's `DecisionSnapshot`, the coordinator processes in canonical ingress order:
availability breaks; current-generation pending confirmation and expiry; qualifying later
observation edges against confirmed expectations; due hold expiry; then the frozen hold and
ownership views. For equal timestamps, ingress revision order decides among distinct observations;
a fixed hold deadline is due when `now >= due`, after all ingress edges with `observed_at < due`
and before those at `observed_at >= due`. A qualifying next scheduled Reaction step releases its hold through the preliminary
non-command result above; the old snapshot dispatches nothing for that step, and the new
snapshot performs ordinary guard and command admission. No cycle may decide against a partially updated view. A
configuration swap or revocation invalidates pending expectations and their holds before the next
admission; an older callback cannot repopulate either under a new generation. On process restart
pending confirmation is not restored: every old lease/target requires a fresh observable state and
current-policy reconciliation before a new command, while no old hold is restored (§6.0, Layer 0
§6.3). These are execution and observation outcomes, not a second `ApplyStep` success definition.

Acceptance cases include delayed full confirmation, partial facet confirmation, facet matches
that never coexist in one coherent channel state, repeated identical observations, no observation
before deadline, unavailability and return, a late Heima-linked edge, resident/manual divergence
after confirmation, revocation during pending work, and restart during an uncertain outcome. Service success alone must never create a physical-success or hold claim.
A full matching read after the execution deadline may anchor a resident correction and establish
a current expectation for a later distinct edge without changing the terminal execution outcome.

### 6.1 Correction attribution evidence

**Durable target lifecycle for historical learning.** Layer 5 emits the
reserved `actuator.target_lifecycle` event fact (Layer 0 §4) only on these
three recorded transitions of one admitted target decision:

```python
TargetLifecyclePhase = Literal["decision", "complete_observation", "closed"]
TargetCloseReason = Literal[
    "superseded_apply", "authority_revoked", "observation_break",
]
TargetLifecycleValue = {
    "event_id": str,                       # stable id for (apply_step_id, phase)
    "phase": TargetLifecyclePhase,
    "apply_step_id": str,
    "reaction_id": str | None,
    "configuration_generation_id": str | None,
    "reaction_activation_id": str | None,
    "actuator_id": str,
    "controlled_channel": str,
    "target_contract_id": str | None,      # decision phase only
    "targeted_facets": list[str],          # sorted/unique; decision phase only
    "expected_facets": dict[str, str],     # decision phase only; canonical JSON text
    "matcher_id": str | None,              # decision phase only, versioned core matcher
    "decision_kind": Literal["already_satisfied", "dispatched"] | None,
    "linked_edge_id": str | None,          # complete_observation when an edge exists
    "close_reason": TargetCloseReason | None,
}
```

`decision` is appended once after ordinary admission and before the first
call, including `already_satisfied` (which sends no call). It records the
entire targeted-facet matcher and exact Reaction/generation/activation or
standalone source identity; an inadmissible proposal creates no event.
`complete_observation` is appended once at the first valid coherent match
of the complete target, including a late match after a terminal timeout
without revising that execution outcome. For `already_satisfied`, both
phases share the admitted cycle and observation instant. Partial or
separately timed facet matches create no complete phase. `closed` is
appended once when existing §6.0.1/§6.1 eligibility ends through a newer
admitted target on the channel, authority revocation or an observation
break. Ending the `already_satisfied` *reuse* episode, a resident
correction, or service-call completion alone is not a close reason for
the historical attribution anchor; it remains bounded by §6.1's core
horizon and latest-state check. A later new target has a new
`apply_step_id`; repeated evaluations reusing the old admitted decision
append no phase. A closed decision cannot later acquire a complete phase.

The phase-specific fields above are exact: `decision` alone has non-null
target contract/matcher/decision kind and nonempty bounded targeted and
expected facets; the other phases have those fields empty/None.
`complete_observation` alone may have a `linked_edge_id` (None for an
already-satisfied current reading); `closed` alone has a non-null reason.
Every phase retains the common identity, `where` is the registered Actuator
location and `HouseFact.when` is that transition's canonical UTC instant.
The `event_id` is the lowercase SHA-256 hex of RFC-8785 canonical JSON
over `[apply_step_id, phase]`;
ordinary queue retry or callback duplication appends at most one of each.
The events use the Layer-1 depth-two/8 KiB bound and the same staged
lossless per-facet codec as §6.0; staging proves the complete decision value
fits. No HA endpoint, raw service payload, person identity or mutable
snapshot is retained. The ordinary ordered end-of-cycle batch persists
them; a crash gap or failed write cannot certify a complete historical
denominator under Layer 0 §4.4. These facts are historical evidence only:
live command/hold authority remains the process-local admission and pending
state of §6.0–§6.0.1.

Layer 5 owns the attribution of a resident correction to a recorded, admitted target decision whose
complete target was observed. This is a strictly narrow Layer-5 -> Layer-3 evidence path: Layer 5 is
the only layer that has both the accepted `ApplyStep` audit identity and the policy/Actuator channel
semantics needed to make the association; Layer 3 consumes the resulting history but may never reconstruct attribution from raw HA state changes.
It is not a feedback command path, a live signal, an action outcome usable by Layer 4, or a generic
cross-layer event bus.

Only after Layer 0's verified `actuator.resident_control` event arrives may Layer 5 emit a
`resident_manual_override` attribution. A verified external/integration or
unknown-origin normalized channel edge may separately yield an
`external_or_unknown_correction` diagnostic when it diverges from a
confirmed compatible target; it never supplies resident learning evidence
or claims a resident acted. Both cases use the one immutable Layer-1 event fact
`actuator.correction`, with
`FactSource.kind="reaction"` and an exact `value` named `CorrectionAttributionEvent`:

```python
CorrectionAttributionEvent = {
    "correction_id": str,                 # stable, non-forgeable event identity
    "classification": Literal[
        "resident_manual_override",
        "external_or_unknown_correction",
    ],
    "actuator_id": str,                   # Layer-2 logical actuator, never an HA entity id
    "controlled_channel": str,            # registered Layer-2 logical channel
    "reaction_id": str | None,
    "anchor_apply_step_id": str | None,
    "anchor_completed_when": EvidenceInstant | None,  # None for skipped or failed calls
    "anchor_target_observed_when": EvidenceInstant | None,  # full target, including a late read
    "correction_when": EvidenceInstant,
    "attribution_elapsed": Window | None,
    "deduplication_key": str,
}
```

Layer 0 §4 reserves the exclusive `event` `FactTypeClaim` for this Layer-5 producer. The value
has exactly the fields above, with no raw payload or extension keys; every id and timestamp
passes Layer-1's ordinary value and size validation before append. The fact's `where` is the
registered Actuator `Location`, and its `when` is `correction_when`.

The event carries the ordinary non-forgeable correlation/source chain separately under the Layer-1
fact envelope. It contains no HA state object, entity identifier, service payload, command target,
resident identity, or mutable runtime buffer. Layer 5 requests its normal append through Layer 1; it
does not own fact persistence, retention, or a private historical store.

The resident-control event and anchor are eligible only when their logical `actuator_id` and
`controlled_channel` match and Layer 5 recorded an admitted `ApplyStep` decision whose complete
target was observed with valid, available canonical values before that resident edge (§6.0.1).
The match covers every targeted facet under the versioned core matcher, not just the facet the
resident changed; the joined Layer-0 `actuator.channel_state.*` edge must
prove that at least one **targeted** facet changed away from its expected
value under that matcher. A change only to an omitted facet is not a
correction of this target. The latest valid state before the resident edge must still match that complete
target. `already_satisfied`, completed calls, and failed or timed-out calls may all supply an anchor
once the full target is observed. The actor that produced the matching state does not decide
eligibility: verified external origin or `unknown` remains in provenance and is never relabeled as
Heima causation. The anchor must fall within the configured core attribution horizon measured
from the first valid complete-target observation, and no later recorded decision with a different target or
authority revocation may supersede it. `attribution_elapsed` is a positive `Window` measured from
`anchor_target_observed_when`, never from HA service completion. `None` means zero elapsed time when
an anchor exists, or no measured interval when the anchor fields are absent; the anchor fields
disambiguate the two cases. A fresh valid reading after a
pending decision's terminal timeout may establish this learning anchor for that still-authorized
recorded target, even before a new policy evaluation, if no different target intervened. It does
not retroactively change the old step's `unconfirmed` execution outcome or prove Heima
caused the state. It may establish a current per-facet expectation for a later distinct edge
under §6.0.1 and Layer 0 §6. The runtime lease still requires the post-terminal fresh read and
current-authority reconciliation of §6.0.1 before another command.

An unobserved or only partially matched target, hypothetical decision, or edge with no normalized
facet/target linkage cannot be called a resident correction. The association is one-to-one at emission: the most recent
unique eligible anchor wins. A raw HA state change, unavailable transition, or any event other
than `actuator.resident_control` is never a **resident** attribution input. Zero or ambiguous eligible anchors
produce no `resident_manual_override` event and a diagnostic reason; Layer 5 must not guess. A
verified nonresident automation or integration change, or a change with unknown origin, may be
recorded as `external_or_unknown_correction` for diagnostics, but it is never eligible learning
evidence for a resident-correction model. Duplicate reports of one correction share a
`deduplication_key` and append at most one event.

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

## 7. Initial V3 descriptors

All Initial-V3 descriptors use the common mechanism above. A descriptor may declare either a singleton
bundle or a finite ordered multi-member bundle within its core-owned bound. In both cases staging,
evaluation, complete-bundle admissibility and one-endpoint `ApplyStep` execution follow the same
registry, validation, review and runtime contracts. An alternate bundle may be freshly derived only
before admission; no known-invalid original bundle is partially executed.
Every Initial-V3 descriptor declares the §4.0 execution-audit codes `stale_callback_discarded`,
`future_work_cancelled`, `alternate_bundle_selected` and `bundle_skipped_no_admissible_alternative`;
a descriptor with a declared timing path whose fallback is a staged seed also declares
`fallback_served_without_artifact`. Only `environment.planned_comfort_trajectory` declares
`late_recovery`, and only `security.presence_simulation` declares `late_step_skipped`. Every
descriptor with a `safe_direction_intents` entry (`environment.external_exchange`,
`environment.air_extraction`, `safety.weather_protection`) also declares `coalesced_identical_target`:

- `environment.solar_shading`: one compatible cover endpoint associated with the subject opening;
  intents `increase_shading`/`decrease_shading`; objectives `limit_solar_gain`,
  `admit_solar_gain`, and `admit_daylight` only with indoor illuminance; mandatory hysteresis and
  minimum dwell. For an irradiance-triggered shading intent, this dwell is the minimum
  elapsed wait under `elapsed_if_requalified`: observed `False` cancels the occurrence,
  while an observation gap counts only if valid solar exposure is `True` both before
  and on the first fresh reading after that gap. Its staged
  trigger is the boolean output of Layer 2's `numeric.hysteresis_condition.v1`, bound to measured
  or explicitly trusted `environment.incident_solar_exposure` for that opening; the Reaction
  references that output and cannot copy or override its thresholds. Hysteresis
  defines separate entry and exit thresholds in that formula; crossing the exit threshold cancels that pending
  occurrence, and a later entry starts a new occurrence and anchor. Initial V3
  uses one staged positive dwell for this path; it registers no solar
  state-fraction forecast or learned-delay binding. The dwell is one wait
  from that anchor, not a second timer after a minimum dwell.
  At the due instant Layer 5 re-evaluates current inputs, target and ordinary admission before any
  command. A separate cooldown, if declared, limits the interval between cover movements; it is
  not this solar-condition dwell. An unavailable condition blocks action but
  preserves the pending in-process occurrence until a fresh valid reading
  establishes whether it still qualifies. A fresh `False` cancels; a fresh
  `True` after a prior valid `True` keeps the original anchor and may request
  immediate current-policy evaluation if the wait elapsed during the gap.
  An unknown middle-band
  state remains unavailable until the Layer-2 formula can establish it.
  The common future learned-delay and action-bearing adoption contracts do
  not authorize a solar timing model absent a reviewed descriptor version.
  Its Initial-V3 `authoring_modes` are `admin_direct` and `learner_proposal`.
  The profile-free direct registration may use the one zero-axis empty-key
  `CanonicalEnvelope` only with this descriptor's complete typed trigger,
  staged guards and target bounds; it carries no environmental-response
  support or calibration. A learned proposal still needs an eligible exact
  relation profile and its own supported context cells.

  Its `supported_profile_refs` are exactly `thermal_shading` and `solar_shading`, version `"1"`
  (Layer 3 §4.8). Both profiles and the direct path name
  `environment.solar_shading.guards.v1` (§3.2); its `direct_guard_contract` is that ref. The legal
  objective/intent pairs are:

  | Objective | Intent | `thermal_shading` | `solar_shading` | Direct |
  |---|---|---|---|---|
  | `limit_solar_gain` | `increase_shading` | yes | yes | yes |
  | `admit_solar_gain` | `decrease_shading` | yes | yes | yes |
  | `admit_daylight` | `decrease_shading` | no | only with an indoor-illuminance binding | yes, with an indoor-illuminance trigger or guard slot |

  Valid direct example: the living-room exterior awning `cover.living_awning` (registered with
  `opening_id="living_south_window"`, `is_external=True`) and an administrator-declared Layer-2
  `FusionRule` using `numeric.hysteresis_condition.v1` over that opening's
  `environment.incident_solar_exposure`, producing the boolean state
  `environment.solar_gain_high` at the living room. The configuration has subject
  `Location(scope="room", room_id="living")`, `relation_profile=None`, trigger
  `state_transition(environment.solar_gain_high@living, False -> True)`, objective
  `limit_solar_gain`, one member `increase_shading` on that cover with a canonical
  shading target, the zero-axis empty-key envelope, and a guard-profile generation binding
  `thermal_bounds` (indoor temperature), `wind` and `precipitation`. The member derives variant
  `(increase_shading, exterior_deployable)`, so the plan's required capabilities are exactly
  `thermal_bounds`, `wind` and `precipitation`. The same configuration without the `wind` or
  `precipitation` binding is rejected at staging; for an interior blind (`is_external=False`) the
  variant is `default` and neither is required. If the awning is also protected by a
  `safety.weather_protection` Reaction, those two bindings must reference its hazard states (§7.4).
- `environment.external_exchange`: one compatible opening endpoint; intents
  `open_for_exchange`/`close_to_retain`; purposes `thermal`, `air_quality`, or `hygrometric`;
  automatic opening requires the purpose's applicable opening-security, precipitation, wind,
  thermal and, for `air_quality`, outdoor-air-quality guard capabilities, while closing requires
  none (`safe_direction_intents`); the common hold and physical-state admission gates apply
  separately to the affected Actuator channel (§3.2, §6.0). Its Initial-V3
  `authoring_modes` are `admin_direct` and `learner_proposal`. The same
  `open_for_exchange` intent resolves a distinct staged action variant for
  each of the three purposes; a direct guard contract must require only the
  applicable capabilities for that validated variant, including the
  opening-safety capabilities where applicable. It cannot require CO2 solely
  because another purpose uses it, nor omit a guard required for the
  selected purpose. A direct zero-axis empty-key envelope is permitted only
  when its typed trigger, conditions and purpose-specific guards completely
  delimit action. Learned paths retain exact profile and supported context
  cells.

  The endpoint's opening must satisfy `opening_faces_exterior` (Layer 1 §7); a window toward an
  interior garage is rejected. Each purpose uses exactly one profile at version `"1"`:
  `thermal -> thermal_exchange`, `air_quality -> air_quality_exchange`, `hygrometric ->
  hygrometric_exchange`. The guard contract is `environment.external_exchange.guards.v1` (§3.2),
  which is also its `direct_guard_contract`; `safe_direction_intents={"close_to_retain"}`. Legal
  objective/intent pairs:

  | Purpose | Objective | Intent | Learned | Direct |
  |---|---|---|---|---|
  | thermal | `cool_with_outdoor_air` | `open_for_exchange` | yes | yes |
  | thermal | `warm_with_outdoor_air` | `open_for_exchange` | yes | yes |
  | thermal | `limit_thermal_exchange` | `close_to_retain` | yes | yes |
  | air_quality | `reduce_co2` | `open_for_exchange` | yes | yes |
  | hygrometric | `reduce_moisture` | `open_for_exchange` | yes | yes |
  | air_quality, hygrometric | `close_after_ventilation` | `close_to_retain` | no | yes |

  `close_after_ventilation` is a deterministic direct rule, not a learned response claim. A direct
  trigger is a `state_transition` of an administrator-declared Layer-2 boolean produced by
  `numeric.hysteresis_condition.v1`, whose numeric source staging verifies against the purpose at
  the subject room: room CO2 for `air_quality`; a `numeric.difference.v1` of indoor minus outdoor
  temperature for `thermal`; a `numeric.difference.v1` of indoor minus outdoor humidity ratio for
  `hygrometric` (Layer 2 §5.3). A trigger on another quantity, or an inline comparison, is rejected.

  Valid direct example: the living-room motorized window, Actuator on opening
  `living_south_window` (faces `outside`), purpose `thermal`, a `numeric.difference.v1` producing
  the living-room indoor-minus-outdoor temperature difference, and a hysteresis boolean
  `environment.free_cooling_available` (`above`, entry 3.0 C, exit 1.0 C). The configuration has
  subject `Location(scope="room", room_id="living")`, `relation_profile=None`, trigger
  `state_transition(environment.free_cooling_available@living, False -> True)`, objective
  `cool_with_outdoor_air`, one member `open_for_exchange`, the zero-axis empty-key envelope, and a
  guard-profile generation binding `opening_security`, `precipitation`, `wind` and
  `thermal_bounds`. Its required capabilities are exactly those four. A companion Reaction with
  trigger `True -> False`, objective `limit_thermal_exchange` and `close_to_retain` stages with no
  required guard binding.
- `environment.air_extraction`: one room-owned extraction-fan endpoint in any registered room and no
  `opening_id`; intents `activate_extraction`, `adjust_extraction` and `stop_extraction`. Its
  `humidity_extraction` profile selects exactly one
  typed room relative-humidity trigger from `level_crossing` (upward crossing of a staged level),
  `delta_over_window` (positive rise in a bounded staged `Window`), or `rate_over_window` (positive
  rise divided by a bounded staged `Window`). The descriptor version validates the selected
  primitive, canonical input unit, comparison and finite parameter bounds at staging; the frozen
  plan carries one trigger, never an implicit OR of the three. A declared current room-occupancy
  condition is evaluated separately as a typed semantic guard; without that declaration,
  occupancy is not required. Missing or stale declared occupancy blocks the action, and an
  incomplete humidity history makes delta/rate abstain under §5.1. The profile predicts humidity
  reduction, not a synthetic shower fact. At the qualifying start of an extraction
  activation, the descriptor requires a fresh valid observed inactive fan. If
  the fan is already active, it admits no `ApplyStep` for that activation,
  including no speed change or later stop, regardless of origin or whether
  its speed matches the proposed target. This pre-target decision creates no
  `already_satisfied` target anchor and does not claim the existing operation
  as Heima's. An unavailable state cannot be assumed inactive. If the fan
  was inactive at entry, the Reaction may operate it only through its
  descriptor-declared steps and ordinary current authority, guards, hold and
  physical-state admission. The Initial-V3 registration must include a
  developer-supplied §3.2 `program_evaluator` specialization that can select
  start, target modification and terminal steps from typed current context,
  with stable step identities, bounded canonical targets and a verified
  normal exit. Fan speed (the canonical `level` below) and `off` are descriptor-specific targets of those
  generic steps, not common evaluator branches. The earlier one-shot
  `activate_extraction` draft lacks that specialization and is incomplete;
  staging cannot accept it as the full Initial-V3 extraction program. This
  descriptor's `humidity_extraction` relation profile must declare separate
  observed-transition classes for physical start, each supported direction
  and bounded range of target modification, and physical termination, with
  distinct comparable reference cohorts and class-keyed estimates. A single
  class for every speed change or a pooled on/speed/off estimate is invalid.
  Its finite step kinds must declare whether their target
  needs an eligible estimate for that step's exact physical transition class.
  Without a speed-modification estimate, that change is suppressed; an
  explicitly deterministic terminal rule may still select `off` at a
  verified normal exit, subject to fresh admission. No start estimate can
  substitute for speed or stop, and missing stop evidence does not create an
  implicit `off` rule. A speed change also requires its current modification
  condition to qualify under the staged program and the exact
  modification cell to pass the reviewed moisture-reduction objective. The
  developer need not assert that any particular speed is necessary or supply
  a static extraction rate. This ongoing descriptor declares
  `managed_episode_resumption=True` under §3.2:
  after restart it may recompute current steps only with committed proof of
  its own confirmed inactive-to-active transition and fresh current state.
  Its channel uses the approved `fixed_duration` hold release; a resident
  correction blocks later automatic target steps until that hold releases.

  **Registration (CA4-12c).** `authoring_modes` are `admin_direct` and `learner_proposal`;
  `supported_profile_refs` is exactly `humidity_extraction` version `"1"`; the guard contract (§3.2)
  is also its `direct_guard_contract`; `safe_direction_intents={"stop_extraction"}` and
  `low_risk_intents` covers `activate_extraction` and `adjust_extraction`. The canonical target is
  `level`, an integer in `[1, N]` where `N` is the channel adapter's declared level count (`N=1` for
  an on/off fan), or `off`. Its staged program parameters are `start_level`, `max_level`
  (`1 <= start_level <= max_level <= N`), `settle_window`, `end_level` (relative humidity),
  `end_dwell` and `max_runtime`, each a bounded `Window` or canonical value validated at staging. The
  registered `program_evaluator` specialization selects:

  1. **Start:** the staged humidity trigger qualifies, the fan is freshly observed `off`, and a
     declared occupancy condition holds -> `activate_extraction` to `start_level`.
  2. **Increase:** only when `max_level > start_level`. At least `settle_window` after the previous
     step, relative humidity still satisfies the start condition and is rising -> `adjust_extraction`
     to the next level up to `max_level`. On a learned path this step also needs an eligible
     `modify_up` estimate for its exact cell; without one it is suppressed. Initial V3 has no
     downward modification.
  3. **Normal end:** relative humidity at or below `end_level` for `end_dwell` -> `stop_extraction`,
     `natural_completion`. Unavailable humidity is `not_ended`.
  4. **Runtime cap:** `max_runtime` after the start step -> `stop_extraction`,
     `natural_completion`, regardless of humidity, so a stuck sensor cannot leave the fan running.
  5. **Resident switch-off:** an observed resident `off` during the activation is
     `normal_cancellation`; the fixed-duration hold applies, and a new activation requires relative
     humidity first to return to or below `end_level`, so Heima does not restart against the
     resident.

  Occupancy is never required unless declared; leaving the room does not stop the program, which
  ends only through items 3–5. Objective/intent pairs: `reduce_moisture -> activate_extraction`
  and `reduce_moisture -> adjust_extraction` (learned and direct); `end_extraction ->
  stop_extraction` (direct only: a deterministic end rule; the `terminate` class is diagnostic
  evidence). The step timers use the common next-step slot (`elapsed` basis).

  Valid direct example: bathroom subject `Location(scope="room", room_id="bathroom")`,
  `relation_profile=None`, trigger `delta_over_window` of +10 relative-humidity points in a 10-minute
  `Window`, no occupancy condition, a two-level fan, `start_level=1`, `max_level=2`,
  `settle_window=10 min`, `end_level=65 %`, `end_dwell=5 min`, `max_runtime=60 min`, the zero-axis
  empty-key envelope and an empty guard binding set. A shower raises humidity: the fan starts at
  level 1 while the resident is present, steps to level 2 after 10 minutes if humidity keeps rising,
  keeps running after the resident leaves and stops once humidity stays at or below 65 % for 5
  minutes, or after 60 minutes at the latest.
- `routine.actuation_bundle`: one room-scoped, finite ordered `ActuationBundle` triggered by one
  declared typed state transition or occurrence and guarded by a closed current-context profile. Its
  Reaction-descriptor-version-fixed member bound, member capability vocabulary, canonical target schemas and
  execution order are core-owned. It accepts a learned candidate only from
  `ActuationRoutinePatternModel-v1` or an equivalently shaped deterministic configuration; it never
  accepts a raw HA event, entity, service, script, scene payload or arbitrary condition graph. Every
  member remains subject to its own current hold, capability, physical-state, dwell and applicable
  safety/privacy/security guard before the complete bundle is admitted. This descriptor is generic:
  lighting is an expected first use, not a namespace-specific execution mechanism.

  Its Initial-V3 `authoring_modes` are `admin_direct` and `learner_proposal`. Its sole
  `supported_profile_refs` entry is `routine_actuation_bundle` version `"1"` (§3.1), with the single
  objective `reproduce_resident_routine` paired with every member intent the descriptor version
  admits and no `NumericOutcomeRequirement`. Its guard contract, also its `direct_guard_contract`,
  is `routine.actuation_bundle.guards.v1` (§3.2). Valid direct example: subject
  `Location(scope="room", room_id="living")`, `relation_profile=None`, trigger
  `state_transition(projector.power@living, off -> on)`, three `light_state` members setting
  three living-room lights to low brightness, the zero-axis empty-key envelope and a guard-profile
  generation binding `presence`; the required capabilities are exactly `presence`. The same bundle
  with an `open_for_exchange` member, where admitted, also requires `opening_security`,
  `precipitation` and `wind`.

  For historical routine discovery, the descriptor version registers a
  bounded, pure `ObservedMemberProjection` for each permitted
  `(action_intent, channel_kind, actuation_adapter_id)` translation entry.
  It accepts one complete canonical post-edge `ChannelStateValue`, its
  exact changed-facet set and the staged channel contract, and returns
  either one descriptor-valid semantic member target or `no_unique_target`.
  It cannot inspect raw HA state, infer resident intent from an unavailable
  value, or fill omitted parameters from defaults. Staging checks its
  input/output schemas, facet bounds and round trip: forwarding the
  returned member through the same versioned translation must match the
  observed post-edge state on every resulting targeted facet under that
  translation's matcher, and at least one changed facet must be targeted.
  Zero or multiple valid member targets, an unrepresentable combination,
  or a failed round trip excludes the episode rather than choosing one by
  heuristic. This is a learning projection only; it creates no second
  ApplyStep path or automatic authority (§6; Layer 3 §4.4.3).

  Its Initial-V3 descriptor version also registers one optional
  `room_vacancy_return_delay` timing path for an exact
  `room_occupancy: present -> absent` trigger and sustained `absent`
  continuation at that same room. This path accepts one Actuator-channel
  member only, so its single due boundary never silently delays a second,
  urgent member. Its frozen descriptor `member_validator` requires the exact
  versioned `TranslationDelayPermission` for this timing path on the
  selected intent/channel/adapter translation entry, accepting the complete
  staged target and `LearnedWindow.maximum` (§6.0). The descriptor does
  not enumerate Actuator kinds, duplicate translation rules or infer
  permission from a lighting namespace. Every registered translation that
  declares this permission uses the same model, timer and ApplyStep; one
  without it cannot stage the delayed path.
  Bootstrap rejects this Initial-V3 descriptor registration if the frozen
  core translation table has no eligible permission for the path; a
  nominally registered learned-delay feature with no stageable target is
  not considered available. The core implementation publishes its exact
  permission ids and accepted target envelopes as part of the versioned
  translation registry, not as a universal Actuator-kind allowlist.
  This timing role is supplemental to the deterministic admin-direct bundle
  or the ordinary `ActuationRoutinePatternModel-v1` bundle candidate; it
  never learns or substitutes the bundle target. The optional binding is
  exactly `RoomOccupancySurvivalModel.return_delay` with §6.0's selector,
  the same room and staged `LearnedWindow`; without an eligible adopted
  artifact it waits the staged seed. Its only allowed timer-gap meaning is
  `elapsed_if_requalified`. A valid `present` return cancels the pending
  occurrence; unavailable occupancy blocks action. After a process restart
  a fresh sustained `absent` state starts a new full wait, with no synthetic
  `present -> absent` training transition. Every due decision uses the
  current bundle target and the common authority, hold, guard and physical
  confirmation admission. This path does not change the descriptor's
  `normal_exit_contract=None` or `hold_release_mode="fixed_duration"`.

All seven Initial-V3 descriptors use the common §4.2 Layer-8 command surface
for configuration creation or proposal review, promotion, consent and
disablement. The presence-simulation descriptor and the other
`admin_direct`-capable descriptors use `stage_admin_direct_reaction` with
their exact complete descriptor configuration; the comfort trajectory uses
its separate prerequisite preparation followed by `review_proposal`.

The three other trigger-driven descriptors above (`environment.solar_shading`,
`environment.external_exchange` and `routine.actuation_bundle`) register
`normal_exit_contract=None`, `managed_episode_resumption=False` and
`hold_release_mode="fixed_duration"` in Initial V3. Their
individual bundle completion does not prove a scheduled program ended. A
later descriptor version may add a bounded step stream and verified activation
end without changing their current versions.
The two already specified step-programmed Initial-V3 descriptors,
`environment.planned_comfort_trajectory` and
`security.presence_simulation`, also declare
`managed_episode_resumption=False`; their existing restart rules recompute
their programs without claiming ownership from this new projection.
`environment.air_extraction` is the third required step-programmed
Initial-V3 descriptor; its specialization, target schema and normal-exit rule
are registered above. Its resumption capability and fixed-duration hold
release are fixed above, not left to inference.

### 7.1 Evidence-gated Initial-V3 descriptor

`environment.planned_comfort_trajectory` is a fixed Initial-V3 `ReactionDescriptor` registry entry,
with a stable identifier and the common descriptor/runtime mechanism. It is not a default automation:
its `learner_proposal` path remains operationally dormant until all evidence and staged prerequisites
below are present. Registration alone never makes it eligible, and it never uses a fallback target,
endpoint, model, calendar plan, or consent value.
Its descriptor version declares `program_family=("planned_absence_program", "1")` (§3.2 Program
families), which supplies its calendar binding, effective-absence start, departure and bootstrap
behavior, normal exit, next-step hold release, restart rule and consent requirement. This section
specifies only what is specific to the trajectory.

Its only authoring mode is `learner_proposal`. An administrator stages its HVAC, calendar and comfort
prerequisites, but cannot use `admin_direct` to create a comfort-trajectory `ConfiguredReaction`
without the required thermal evidence and ordinary proposal review.

- `environment.planned_comfort_trajectory`: one explicit conditioned scope and independently
  registered heating and/or cooling endpoints, active only during the family's effective absence,
  with descriptor-declared comfort/safety bounds. While the plan remains
  valid, it may use only an exact-cell, unexpired `hvac_thermal_response`
  `ThermalResponseParameter` as a bounded reachability estimate. Layer 5 combines its conservative
  recovery duration with an explicitly configured return target and the calendar return boundary to
  choose the latest start that conservatively permits recovery by that boundary; the parameter never
  supplies a target, command or schedule.
  In heating season the descriptor may permit a controlled decline toward an explicitly configured
  minimum acceptable temperature followed by recovery; in cooling season, the symmetric rise toward an
  explicitly configured maximum followed by pre-cooling. Heating and cooling targets, capabilities and
  endpoints are independent. It is not a fixed setback, a universal comfort default, or a direct
  thermostat-control implementation.

  Its staged `HvacTrajectoryBinding` names one registered Actuator/channel endpoint per declared
  mode; a binding may declare heating, cooling, or both, but never duplicates a mode. The same
  Actuator/channel may serve both only where its Layer-2 adapter admits both explicit mode bindings.

```python
@dataclass(frozen=True)
class ConditioningScope:
    conditioning_scope_id: str
    location: Location                  # exactly one `room` or `casa`; never `zone` or `rooms`;
                                        # a room must be in the thermal envelope (Layer 1 §6.1)
    temperature_fact: FactRef           # staged canonical current temperature for this scope

@dataclass(frozen=True)
class HvacTrajectoryEndpoint:
    mode: Literal["heating", "cooling"]
    actuator_id: str
    controlled_channel: str
    target_contract_id: Literal["hvac_state.trajectory_setpoint.v1"]

@dataclass(frozen=True)
class HvacTrajectoryBinding:
    conditioning_scope_id: str
    endpoints: tuple[HvacTrajectoryEndpoint, ...]  # non-empty; unique `mode`

@dataclass(frozen=True)
class DesiredConditioningMode:
    fixed_mode: Literal["heating", "cooling"] | None
    mode_fact: FactRef | None  # current typed mode at the conditioning scope
```

  The prerequisite stages exactly one desired-mode source: a fixed
  administrator-selected `fixed_mode` or a `mode_fact`, never both or neither.
  The latter resolves to one current, freshness-checked Layer-2 categorical
  fact at the `ConditioningScope.location`, with the closed values `heating`,
  `cooling`, and `off`; it is not inferred from outdoor temperature, calendar
  text, the order of endpoints, or a learned thermal parameter. A fixed mode
  must have a matching bound endpoint. A fact-driven mode may use both bound
  endpoints but must have a matching endpoint for every actionable value.
  The exact source and fact binding enter the prerequisite fingerprint.
  When the current desired value is `off`, the mode condition is unsatisfied;
  when the fact is missing, stale or invalid, evaluation abstains. One mode
  value is selected per frozen `DecisionSnapshot`.

  Layer 3 produces a distinct candidate for each exact `(conditioning_scope_id,
  mode)` parameter. Each resulting Reaction retains that one mode; it is
  eligible only when the current desired mode equals it. Thus two configured
  mode Reactions from one prerequisite cannot both claim a shared channel
  through binding order. Before commanding, Layer 5 checks the selected
  endpoint's observed mode and all other configured mode endpoints in the
  frozen physical state. The selected endpoint may be confirmed `off` or in
  the selected mode; an unselected distinct endpoint must be confirmed
  inactive. An unavailable/unconfirmed mode blocks with
  `actuator_state_unconfirmed`; a confirmed opposing active mode blocks with
  the descriptor safety guard. The ordinary hold, consent and ownership gates
  still apply. No automatic mode switch compensates an already sent call.

  A staged `ConditioningScope` is the shared scope identity for the HVAC binding, guard profile,
  Layer-3 thermal artifact and configured Reaction. A `room` scope uses its declared canonical room
  temperature fact. A `casa` scope is legal only with one explicit staged canonical casa-temperature
  fact; it never averages, selects, or infers a house temperature from several room sensors. A `zone`
  or ad-hoc `rooms` location is rejected in Initial V3 because heterogeneous room dynamics cannot be
  represented by one thermal-response artifact or one recovery ramp.
  Staging requires its temperature fact's producing quantitative unit contract
  to output canonical Celsius. A later Layer-2 unit mismatch makes that fact
  unavailable and the trajectory abstains; it never interprets a changed raw
  numeric scale as Celsius.

  The core-owned `hvac_state.trajectory_setpoint.v1` target contract is defined here for this
  descriptor: its complete canonical facet set is `("mode", "setpoint_c")`; `mode` is exactly
  `heating` or `cooling`, and `setpoint_c` is a finite canonical Celsius temperature within the
  staged administrative bounds. Every admitted trajectory `ChannelTarget` uses this contract and
  targets both facets. It cannot target `auto`, power, fan speed, swing, preset, humidity, or an
  unspecified HVAC facet; those facets remain observed current state. Layer 5 rejects the binding or
  suppresses the step when the registered channel/adapter does not admit the contract, the declared
  mode is unsupported, the typed current state is unconfirmed, or the canonical setpoint is outside
  the descriptor's administrative bounds. The translation table may compile mode/setpoint into several
  `ApplyCall`s, but it cannot introduce another target facet or target selector.

  `ComfortTrajectoryGuardProfile` is a separately staged, administrator-authored Layer-5 contract. It
  supplies the absence bound and return target for each bound mode, plus one exact environmental
  guard-profile generation and required site-specific guard capabilities; it is never learned from a
  setpoint history or chosen by a thermal artifact.

  ```python
  @dataclass(frozen=True)
  class ThermalBoundRule:
      kind: Literal["absolute", "relative_to_fact"]
      absolute_c: float | None
      reference: FactRef | None            # current staged temperature fact; never raw HA state
      offset_c: float | None
      hard_min_c: float
      hard_max_c: float

  @dataclass(frozen=True)
  class ComfortTrajectoryGuardProfile:
      conditioning_scope_id: str
      heating_absence_bound: ThermalBoundRule | None
      heating_return_target: ThermalBoundRule | None
      cooling_absence_bound: ThermalBoundRule | None
      cooling_return_target: ThermalBoundRule | None
      reaction_guard_profile_generation_id: str
      reaction_guard_profile_definition_fingerprint: str
      required_guard_capabilities: frozenset[ReactionGuardCapabilityRef]
  ```

  The three administrator-authored contracts above are not independently mutable runtime inputs. One
  atomic, immutable, append-only `ComfortTrajectoryPrerequisiteGeneration` is the only staged unit for
  this descriptor:

  ```python
  @dataclass(frozen=True)
  class ComfortTrajectoryPrerequisiteGeneration:
      prerequisite_generation_id: str
      generation_index: int                  # contiguous per conditioning scope, beginning at 0
      conditioning_scope: ConditioningScope
      hvac_binding: HvacTrajectoryBinding
      desired_mode: DesiredConditioningMode
      guard_profile: ComfortTrajectoryGuardProfile
      calendar_plan_binding: CalendarPlanBinding
      definition_fingerprint: str            # canonical complete aggregate fingerprint
      staged_by: str                         # authenticated administrator
      staged_when: EvidenceInstant
  ```

  Staging validates and persists the complete generation, or persists none of it. The binding and
  profile must name exactly the generation's `conditioning_scope_id`; the calendar binding must have
  `expected_category="planned_absence"`; every endpoint, current `FactRef`, dynamic bound, hard bound,
  adapter ramp constraint and required guard capability must validate together. The referenced
  Reaction guard-profile generation must have the same scope and supply every required capability
  through the descriptor's exact guard contract. The generation contains no learned artifact, proposal,
  resident consent or administrative action enablement. It defines what may be considered; it does not
  authorize an action.

  A comfort-trajectory candidate, its admitted `ReactionProposal`, and every resulting
  `ConfiguredReaction` retain the exact pair `(prerequisite_generation_id, definition_fingerprint)`.
  The reaction's immutable `configuration_generation`, including the generation in its `AtJob` key,
  binds that exact pair and cannot name a later prerequisite generation.
  The learner may select only a compatible exact-cell thermal artifact against that pair. It cannot
  select, alter, merge, or inherit a scope, endpoint, calendar binding, comfort/safety rule, guard or
  technical ramp constraint. Layer 3 §6.4.1 defines the canonical candidate payload carrying this
  reference; CT-3 in the backlog records its decision history.

  An administrative edit creates a new generation atomically; it never changes an earlier generation.
  Pending proposals bound to an earlier generation remain historical but become `not_approvable` with
  `staged_prerequisite_incompatible`. A currently automatic reaction bound to it cancels its future
  action jobs and is demoted to `notification_only`; it cannot reinterpret its candidate, artifact or
  target under the newer generation. Automatic operation can resume only through a new compatible
  candidate, ordinary proposal review, notification-only shadow, and authenticated promotion on the
  new generation. Existing sent HA calls are never compensated.

  An `absolute` rule supplies `absolute_c`; a `relative_to_fact` rule supplies one current,
  temperature-typed `FactRef` and `offset_c`. Its `reference.previous_cycle` **must** be `False`:
  staging rejects it when true, including a Layer-2 self-memory reference otherwise valid for a
  `FusionRule`. The resolved result is always clamped to the explicit finite
  `[hard_min_c, hard_max_c]` interval. Staging requires exactly the fields selected by `kind`,
  compatible canonical units, and a current-snapshot `FactRef` declared by the descriptor/profile's
  permitted runtime slots. On every snapshot, the resolved heating pair must satisfy
  `absence_bound <= return_target`; the cooling pair must satisfy
  `return_target <= absence_bound`. A missing, stale, invalid or non-temperature reference, or a
  resolved pair that violates its ordering, makes the current rule unresolved and prevents the step;
  there is no prior-cycle value, prior-value, default, expression, or HA fallback. Thus an administrator may declare, for
  example, an absence bound relative to outside temperature while retaining an absolute safety
  floor/ceiling.

  The profile declares no maximum setpoint jump or operator-selected ramp cadence. The absence bound
  is one direct semantic target at departure. Recovery is instead a core-generated, bounded adaptive
  ramp: in heating its setpoint steps only upward toward the return target; in cooling its steps only
  downward toward the return target. The descriptor never changes a confirmed current mode, and it
  never overshoots either resolved bound.

  The selected adapter supplies a closed recovery-ramp translation constraint: the largest permitted
  recovery setpoint step and the minimum interval before its next evaluation. These are technical
  adapter constraints, not administrator preferences. Layer 5 selects only a step whose absolute
  magnitude is admitted by both that constraint and an exact current
  `ThermalResponseParameter.recovery_setpoint_step_*` bucket. It then waits at least that parameter's
  `conservative_step_settle_duration` and the adapter minimum interval before the next knot. Thus
  Layer 3 supplies measured bounded step response; Layer 5 alone derives the direction, next target,
  and timing from the current snapshot, remaining return delta, calendar boundary, and constraints.

  The recovery ramp has no persisted curve or prebuilt command list. Departure handling is the
  family's start rule (§3.2, Program families, rule 3). A selected plan/dependency change and
  the descriptor's one next
  Layer-0 `AtJob` request a fresh re-evaluation of that same plan; neither is a second semantic trigger
  or a stored event. The job uses the common activation-stable next-step slot of §6.0; a changed
  plan, mode or due knot replaces that slot instead of leaving another pending job. The
  descriptor's bounded step stream identifies the one pending recovery knot by the normalized
  plan fingerprint, selected mode, activation-local step ordinal and selected Actuator/channel.
  Re-evaluating or replacing
  the same pending knot retains its `planned_step_id`; the ordinal advances only when that knot is
  consumed or terminally skipped, never merely because a guard vetoed an evaluation. The canonical
  target fingerprint is computed from the fresh frozen snapshot when the due step is evaluated.
  These identities name steps, not a persisted curve or a prebuilt command list. At bootstrap the
  family's effective absence (§3.2) opens a new activation, which arms only the one next-step slot
  derivable from that fresh snapshot and current configuration; otherwise it remains unarmed.

  At each recovery knot Layer 5 rereads the current snapshot, recalculates one next supported target,
  emits at most one `ApplyStep`, and arms at most one following `AtJob`. It never replays missed knots,
  sends a burst of calls, bypasses the adapter's step/interval constraints, or jumps directly to the
  return target merely to catch up. If the remaining supported ramp cannot meet the calendar boundary,
  it continues only with the next safe step and records `late_recovery`. A missing compatible artifact,
  current state, plan, presence, hold or guard cancels the next command job and
  emits no step. A previously identified due boundary for an active
  `next_reaction_step` hold remains scheduled solely for its non-command
  release evaluation under §6.0; the guard still blocks the actual call. The
  thermostat may apply its own physical ramp to every target, but Layer 5 neither assumes nor verifies
  that behavior.

  Administrative action enablement and household consent are mandatory, separate, conjunctive gates
  for automatic action and both start disabled when its `ConfiguredReaction` is created. They are
  current runtime authority, not fields of a prerequisite generation, and household consent is never a
  per-person learned profile. Neither gate blocks candidate admission, proposal review, or the
  `notification_only` shadow: that shadow may schedule evaluations but never emits an `ApplyStep`.
  Revocation of either while automatic action is enabled cancels every future action job and returns the
  reaction to `notification_only`; a manual hold, return/loss of `presence=away`, plan change/removal,
  unresolved bound/model/state, or any required safety guard suppresses the corresponding future work.
  No command already sent to HA is compensated. Layer 5 uses
  `ThermalResponseParameter.conservative_recovery_duration` and the calendar return boundary to arm the
  first future recovery-knot evaluation. At that `AtJob`, a new snapshot resolves the bounds and all
  gates again before it may generate the one actual next `ApplyStep`; it never sends a command prepared
  earlier. If the calculated recovery start is already past, the current evaluation may issue only the
  next adapter- and artifact-supported knot after the same checks and records `late_recovery`; it never
  takes a more aggressive step or overrides a guard.

  A plan change/removal, a `return` episode, loss of `presence=away`, unavailable model/required
  environmental input, manual hold, resident opt-out, or any descriptor safety guard suppresses future
  trajectory commands. A guard alone does not erase an already due boundary
  retained for an active next-step hold. Layer 0 arms only the bounded next inflection/boundary `AtJob`; a meaningful
  environmental update may produce a new decision, but the policy never polls. A learner may submit
  this descriptor's candidate only against one already staged compatible
  `ComfortTrajectoryPrerequisiteGeneration`; it may bind an eligible exact-cell
  `ThermalResponseParameter`, but cannot choose or modify any administrative prerequisite. Missing or
  incompatible evidence/configuration leaves the registered descriptor dormant and produces no proposal
  or action.

  Its normal exit is the family's (§3.2): it applies to one active trajectory, never to the
  reusable configured Reaction. An unresolved thermal model or bound is an additional
  descriptor-specific `not_ended` cause. Authority revocation or configuration replacement follows
  the common immediate invalidation path.

  **Initial-V3 lifecycle gates.** Gates 1--2 are required before Layer 5 may admit a candidate and
  create its reviewable proposal. An accepted proposal creates a `ConfiguredReaction` only in
  `notification_only` mode; gate 3 is required before its operational shadow completes, and gate 4 is
  required before automatic action is enabled:

  1. Its exact `hvac_thermal_response` artifacts have complete passive-drift and active-response
     cohorts, exact-cell applicability coverage, a complete frozen `ThermalEvidenceGateCalibration`,
     calibrated trajectory/prediction intervals and completed thermal shadow validation. No
     energy-benefit result is admitted without the declared measured energy/power outcome.
  2. Staging validates the complete administrative prerequisite generation atomically:
     `ConditioningScope`, `HvacTrajectoryBinding`, `ComfortTrajectoryGuardProfile`, dynamic fact
     bindings and hard bounds, calendar binding, required guards, technical adapter constraints, and
     independently valid heating/cooling endpoints. It contains neither artifact evidence nor current
     consent/enablement; a failure persists no partial generation.
  3. The descriptor completes a bounded operational shadow period in `notification_only` mode. For
     each qualifying plan it records the absence target and every recovery knot it would have selected,
     without emitting an `ApplyStep`; it verifies plan edits/cancellations, dynamic-bound availability,
     rescheduling and all suppression/cancellation paths. This shadow validates orchestration only and
     never claims an uncommanded thermal effect.
  4. Automatic action requires a separate authenticated administrative promotion and current household
     consent after the preceding gates. End-to-end tests cover departure, absence target, recovery
     timing, plan change/removal, early return, manual hold, safety guard, consent/administrative
     revocation, restart, `late_recovery`, and the rule that no already sent call is compensated.
     A verified return or selected-plan removal ends only the current activation;
     a later eligible absence creates a new id under unchanged authorization,
     while calendar/model unavailability cannot falsely end the old activation.

  Shadow evidence, readiness, or successful tests never auto-promote the descriptor or grant consent.

#### 7.1.1 Layer-8 staging and administration contract

`environment.planned_comfort_trajectory` is administered through the Layer-8 governance panel. It is
not a config-flow form: its immutable prerequisite generations, proposal review, artifact evidence and
shadow history are relational workflow data. Layer 8 authenticates the actor, checks the declared
capability, renders bounded redacted state, and sends a typed command; Layer 5 remains the only owner
of validation, durable mutation, job cancellation, review transition and action authority.

Its one descriptor-specific preparation command is
`stage_comfort_trajectory_prerequisite_generation`. An authenticated
administrator submits the complete `ConditioningScope`,
`HvacTrajectoryBinding`, `DesiredConditioningMode`,
`ComfortTrajectoryGuardProfile` and `CalendarPlanBinding`, plus
`expected_current_generation_id` (or the explicit empty-current sentinel),
`operation_id` and `correlation_id`. Layer 5 appends exactly one validated
`ComfortTrajectoryPrerequisiteGeneration` and returns its id/fingerprint, or
changes nothing. It never accepts a field-level patch.

Proposal review and all Reaction promotion, consent, disablement and
resident-authority changes use the common §4.2 commands, with the exact
comfort-trajectory readiness/shadow gates above. This descriptor is
learner-proposal-only, so `stage_admin_direct_reaction` rejects it. No
descriptor-specific alias of a common authority command is registered.

`HouseholdConsentAuthority` is a Layer-8 household access binding, separate from a trajectory
prerequisite generation and from the consent value itself. It contains one or more explicitly assigned
authenticated resident actor references; each reference is a Home Assistant user id (`ha_user_id`),
the identity Layer 0's response ingress verifies (Layer 0 §5.1.3) and Layer 6 matches to recipients. Only an actor carrying this explicit resident authorization
may issue `set_reaction_household_consent`; an administrator role alone is insufficient, although one person may hold both
roles through separate grants. A configuration-generation successor starts with consent disabled and
never inherits it from its predecessor. Retention at authority removal is an explicit administrative
decision about a pre-existing household consent, not an administrative consent grant.

The panel's shadow view is read-only. For each reaction it may expose the prerequisite/artifact/profile
identity, evidence freshness, current readiness, bounded duration/temperature summaries, would-be
absence target and recovery knots, suppression reasons and §4.0 execution-audit records. It
never exposes calendar title/description/attendee content, raw fact history, resident identity beyond
the acting audit reference, raw HA payload, or an unredacted artifact.

#### 7.1.2 Executable acceptance suite

The descriptor's prose requirements are release-blocking executable scenarios, not illustrative test
ideas. Every scenario is a versioned `Given / When / Then` fixture with a fake monotonic clock,
frozen-calendar snapshots, typed fact snapshots, a registered adapter/Actuator double, durable
proposal/configuration records and a Layer-0 scheduler double. It asserts only its observable trace:
persisted generation/proposal/reaction state, exact `AtJob` keys and cancellation/replacement,
`ApplyStep`/`ApplyCall` trace, and typed diagnostic/audit code. It does not assert private evaluator
objects, call ordering not guaranteed by the contract, or raw calendar/HA payload.

The Initial-V3 suite contains at least these scenarios:

1. **Candidate and governance contracts:** one exact `(scope, mode)` candidate uses only a compatible
   generation/artifact/bucket; a missing, stale or out-of-envelope artifact emits no candidate; accepted
   review creates only `notification_only`; and an edited prerequisite generation makes old pending
   proposals `not_approvable` while an old automatic reaction cancels future action jobs and never
   interprets its old evidence under the new generation.
2. **Direct absence and adaptive recovery:** an observed `departure`, valid plan and stabilized
   `presence=away` emit exactly one direct absence target and arm exactly one future job. Heating
   recovery issues only upward and
   cooling recovery only downward targets. Each knot consumes a fresh snapshot, emits at most one
   adapter/artifact-supported step, and arms at most one successor job; no scenario may observe a
   persisted curve, prebuilt call list or physical-thermostat ramp assumption.
3. **Plan and safety interruption:** a plan edit replaces or cancels the activation's existing
   next-step slot and invalidates its old planned-step selection; plan removal, early `return`, loss of `presence=away`, hold, unresolved dynamic bound,
   stale/missing artifact, unconfirmed HVAC state or required guard failure cancels future action work
   and emits no step. A late recovery records exactly `late_recovery` while selecting only the next
   safe knot: it never replays, bursts, bypasses an interval/step limit or jumps to the return target.
   A temporary unavailable bound or guard veto retains the same activation. When a valid input
   returns, one fresh evaluation replaces at most its activation-stable next-step slot with
   the next adapter- and artifact-supported knot; repeated evaluations and a stale callback
   cannot add another job or duplicate a command. An already identified due boundary for an
   active next-step hold still evaluates release without admitting a blocked HVAC command.
4. **Restart and application boundary:** after restart the descriptor reads a fresh calendar snapshot
   and re-arms only a job derivable from current configuration, an active planned-absence interval and
   current stabilized `presence=away`; it never replays a missed boundary or requires pre-restart
   presence history. Adapter tests admit exactly the descriptor-owned
   `hvac_state.trajectory_setpoint.v1` facets `mode`/`setpoint_c` with a supported explicit
   heating or cooling mode and finite bounded Celsius setpoint; they reject `auto`, missing or
   extra facets, non-finite or out-of-bound setpoints, and an incompatible registered channel/adapter.
   Once an `ApplyCall` is sent, later cancellation/failure may
   block only future calls and never emits compensating control.
5. **Shadow, promotion and consent:** notification-only shadow records each would-be target/knot but
   emits no `ApplyStep`. Administrative promotion without consent produces
   `authorized_awaiting_household_consent`; a later grant requests a fresh evaluation. Resident
   revocation or admin disablement cancels future action jobs. A successor configuration starts without
   consent. Removing a resident consent authority requires an explicit retain/revoke disposition for
   every consent they granted; retain produces the required audit, while revoke blocks future action.
6. **Desired mode selection:** with heating and cooling candidates bound to
   one channel, a fresh desired `heating` fact makes only the heating Reaction
   eligible; `cooling` makes only cooling eligible. With distinct endpoints,
   the unselected one must be confirmed inactive. A confirmed `off` selected
   endpoint may receive the selected mode/setpoint target; an opposing active
   mode, `auto`, unavailable or unconfirmed physical mode sends no call.
   Desired `off` satisfies neither Reaction, while a stale/missing desired
   fact makes both abstain. A fixed desired mode has the same one-mode
   result and never changes because endpoint tuple order changes.

The BOPTEST matrix, replay fixtures and opt-in field-pilot analysis of `ThermalEvidenceGateCalibration`
are a separate release-calibration suite. They determine the frozen profile gates; they do not replace
the deterministic regression scenarios above.

### 7.2 Initial-V3 direct descriptor: `security.presence_simulation`

```python
@dataclass(frozen=True)
class PresenceSimulationActivitySession:
    recurrence: WeeklyRecurrence
    duration: Window
```

This is descriptor configuration, not a new Layer-0 temporal abstraction or a `CronEntry`.
`WeeklyRecurrence` supplies the non-empty weekday set, local-civil hour/minute, timezone and DST
semantics; `Window` supplies the validated positive duration. During an eligible planned absence,
Layer 5 uses this pair only to determine the current/next session occurrence and derive its one next
`AtJob`; it does not install a standing recurrence or a second scheduler. It is a descriptor
time-window parameter under Layer 0 §3.1, not a standalone schedule: the calendar's planned
absence and stabilized `presence=away` activate the Reaction, and the session only limits when
it may act. The administrator therefore records only the absence in the calendar and configures
lights, density and session in this Reaction.

Session occurrences are deterministic:

- **Start:** the `WeeklyRecurrence` occurrence in local civil time; a nonexistent local start
  moves to the first valid instant after the gap and an ambiguous one uses its first occurrence
  (Layer 0 §3.1).
- **End:** start plus `duration` as elapsed time, so a session keeps its real length across a DST
  change. A session that crosses midnight ends on the following day and belongs to the weekday on
  which it started.
- **No overlap:** staging rejects a `duration` that is not strictly shorter than the minimum
  elapsed interval between two consecutive selected weekday starts, computed in civil time over
  one week (for every weekday selected, shorter than 24 hours).
- **Timezone change:** an occurrence already started keeps its computed end; later occurrences are
  recomputed in the new zone and its session-boundary job is re-armed (`wall_clock` basis).

The session boundary job uses `AtJob.basis="wall_clock"`; the end of an already started session
is also re-armed after a clock discontinuity (Layer 0 §3.5).

`security.presence_simulation` is a fixed Initial-V3 core `ReactionDescriptor`, with
`admin_direct` as its initial sole authoring mode. It is a bounded deterrence aid that may make a home
less obviously vacant during a planned absence; it is never a security guarantee or a substitute for
physical security. It uses the common `ConfiguredReaction`, scheduler, current-snapshot admission,
ordered `ApplyStep` and audit path. It neither becomes a learning family nor acquires a security-specific
runtime. Its descriptor version declares `program_family=("planned_absence_program", "1")` (§3.2
Program families), which supplies its calendar binding, effective-absence start, departure and
bootstrap behavior, normal exit, next-step hold release, restart rule and consent requirement.
This section specifies only what is specific to presence simulation.
Its `supported_profile_refs` is empty and its exact descriptor-level
`direct_guard_contract` is `security.presence_simulation.interior_lighting.v1`: for `light_state` it
permits and requires only the stabilized `presence` capability. Manual hold, command ownership and
confirmed state remain the ordinary common admission checks rather than profile capabilities.
This descriptor version declares `permitted_envelope_axes=()` and
`permitted_direct_envelope=CanonicalEnvelope(axes=(), supported_cells={CoverageCell(
axis_values=(), support=None, calibrated=None)})`. The sole empty-key cell
adds no context restriction and supplies no fabricated learning evidence;
the active planned-absence interval, stabilized presence, session, guard,
authority and physical admission checks remain mandatory. Staging rejects a
supplied axis, other cell, or non-null support/calibration field. Its activation
start criterion is the family's effective absence; the session determines the
next eligible step, not a second activation.

Its casa-scoped immutable configuration generation contains one `CalendarPlanBinding` for
`planned_absence`, the exact required `presence` guard-profile generation, a canonical non-empty set of
selected lighting endpoint/channel identities, typed `light_state` targets, one
`PresenceSimulationActivitySession`, and one closed activity density (`quiet`, `ordinary`, or `active`). At
staging, an administrator may select registered endpoints and/or rooms; each room expands once to the
then-current endpoints. The persisted set is deduplicated and canonically ordered, never a live room
group. Each endpoint must be an explicitly selected `where: room` Actuator with a registered
`light_state`-compatible channel kind, observable-state contract and core actuation adapter accepted
by this descriptor's light intent. `actuator_role` may suggest an endpoint in the Layer-8 picker but
is never an admission test. Selection is the administrator's declaration that the endpoint
is appropriate as an interior light for this deterrence use; Layer 2 has no global `simulation_safe`
field. An endpoint in a room whose enclosure is `exterior` (Layer 1 §7) enters only through explicit
selection of that endpoint or room. Unknown, duplicate, empty, incompatible or subsequently changed selections reject staging or
make the current generation unavailable rather than silently changing its membership. All unselected
or incompatible endpoints, openings, locks, alarms, HVAC, appliances, scripts and scenes are excluded
by construction. A generic switch with a compatible registered light-state channel may be selected
for an interior lamp; its role string alone neither qualifies nor disqualifies it.

The initial generator deterministically derives a day-varying finite sequence of activity episodes from
the configuration generation, local session and episode index. Its bounded core constants determine
episode count, bundle size, continuity, duration, overlap and handoff; it never replays historical
commands, accepts arbitrary jitter/frequency, HA scenes/scripts or an external scheduler. An episode
may contain a finite concurrent light bundle across rooms. Layer 5 schedules only the next future
`AtJob` in the common activation-stable next-step slot of §6.0. The descriptor keeps the
normalized calendar-plan fingerprint, local session, episode index and step kind in the
selected planned-step identity, not in the job replacement key. Each firing reads a fresh snapshot, revalidates every gate, derives at most
one still-future bundle and then its successor job. Missed or late work is skipped, never caught up,
replayed, burst or compensated; a skipped late step records `late_step_skipped` (§4.0).
For each selected channel, the bounded generator derives a stable `planned_step_id` from the
activation, normalized plan fingerprint, local session, episode index, on/off step kind and
channel; re-evaluating the same pending boundary preserves the
identity. The current frozen snapshot supplies its canonical target fingerprint. A planned switch-off
is therefore a later step, not a completion-only side effect.

The generator defines the episode's ordinary future light targets. Its
sequence includes a planned switch-off for each light it turns on, after the
last activity that still targets that light; overlap and handoff may defer
that step. The generator fits these planned steps within the selected session
and current planned-absence interval; it does not start activity that cannot
reach its planned switch-off before those existing boundaries. This switch-off is a normal step of the generated sequence, not a
separate exit action. Layer 5 admits each still-future step
only while its current session, planned-absence, presence and common action
criteria hold. It applies the same `AtJob`, fresh-snapshot admission, holds,
guards, ownership, physical confirmation and follow-up rules to every step.
Completion adds no further command: the Reaction executes its declared
sequence, including its planned switch-offs, while eligible.

An episode requires the family's effective absence (§3.2), which also defines start, departure,
bootstrap, normal cancellation, natural completion and the next activation. Layer 5 never consumes
raw camera results or adds a separate return timeout. A transient contradictory or unavailable
presence result abstains only the affected episode, allowing later fresh evaluation. A calendar
update, departure occurrence or due `AtJob` is only an evaluation request under the same plan;
none becomes a second trigger. Repeated qualifying snapshots reuse the current activation and one
next-step slot. Specific to this descriptor: the planned switch-off steps are handled before
natural completion, and a blocked or unconfirmed step does not claim that the light physically
switched off. A committed `presence.return` before the sequence finishes cancels its still-future
steps; Layer 5 sends no additional command to restore or switch off a light, and a step already
sent to HA is not compensated.
A guard alone does not erase an already identified due episode boundary for
an active next-step hold; that boundary evaluates release under §6.0 without
admitting a blocked command.
A configuration successor or authority revocation invalidates affected holds
through the common immediate path. The current activation's applicable holds
follow the endpoint-level exit rule only for its validated normal cancellation
or completion.

The descriptor uses ordinary enablement, resident consent, manual-hold, command-ownership,
confirmed-state, cooldown and idempotency checks, plus its exact stabilized-presence guard. Weather,
opening, thermal and unspecified privacy guards are not required merely because the common registry
contains them. A held or resident-controlled endpoint may be excluded only before admission: Layer 5
may freshly derive a complete plausible alternate bundle whose every member passes ordinary admission,
or else skips the episode. It never partially applies a known-invalid original bundle. A later failed
`ApplyCall` stops later work, records its partial outcome and never compensates an already completed
call.

Optional `notification_only` shadow is a read-only administrative preview, not an evidence gate for
this deterministic admin-direct configuration. It records would-be episodes, bundles, suppressions and
jobs but emits neither `ApplyStep` nor a resident-visible notification by default. An administrator may
promote a current valid generation without waiting for an absence or preview occurrence; promotion
records only administrative authorization and yields `authorized_awaiting_household_consent` until an
authorized resident grants current consent. Grant requests fresh evaluation without replaying missed
work. Resident revocation, administrative disablement or a configuration successor cancels future jobs;
a successor inherits neither authorization nor consent. The common resident-authority removal rule,
including explicit retain/revoke disposition for existing consents, applies unchanged.

No presence-simulation operational record, preview, job or execution-audit projection stores a generator
seed, whole future programme, calendar text, resident identity, historical presence, raw HA payload,
scene or script. The common Layer-5 governance ledger retains its required authenticated actor
references under §4.2, but they are never copied into these operational projections. Correlation and
execution audit use only reaction/configuration identity, a non-reconstructive plan fingerprint,
session/episode identity, logical members, `ApplyStep` outcomes, closed suppression reasons and
§4.0 execution-audit codes.

A later generic `TemporalActuationProfileModel` may supply a bounded reviewed profile/artifact only
after its independent learning, privacy, scheduling, evidence and shadow-promotion contract exists. It
may replace the core episode selector only; it cannot alter endpoint, calendar, presence, guard,
authority, scheduler or `ApplyStep` ownership.

#### 7.2.1 Executable acceptance

This descriptor's release-blocking versioned `Given / When / Then` fixtures use a fake monotonic clock,
frozen calendar/fact snapshots, registered Actuator/adapter doubles and a Layer-0 scheduler double.
They assert only durable configuration/authority state, exact job creation/cancellation/replacement,
`ApplyStep`/`ApplyCall` traces, and closed audit/diagnostic reasons:

1. Atomic staging rejects empty room expansion, duplicate/unknown/ineligible endpoint, incompatible
   light target, invalid `PresenceSimulationActivitySession`, any supplied relation profile, or
   incomplete required guard profile without persisting a partial configuration. It accepts an
   explicitly selected room lamp with a compatible `light_state` channel and adapter even when its
   `actuator_role="switch"`; it rejects `actuator_role="light"` without that compatible registered
   channel/observable-state contract. No Layer-3/5 admission decision reads the role string.
   It accepts only the descriptor's zero-axis, one-empty-cell
   `CanonicalEnvelope` with absent support/calibration; a second cell,
   undeclared axis or invented learner evidence rejects staging.
2. Optional `notification_only` preview with active planned absence and stabilized `away` derives only
   the hypothetical episode/bundle and next job, never an `ApplyStep` or resident-visible notification.
3. Departure during an open session, calendar edit/removal, committed return, transient contradictory
   presence, targeted-channel hold, unconfirmed state, late job and restart produce only the defined
   selection, abstention, cancellation or replacement behavior: never raw-camera cancellation,
   catch-up, replay, burst or compensation.
   A return closes only that activation; another qualifying absence under the
   same configured Reaction starts a distinct activation. A calendar outage
   or failed guard suppresses work without a false normal exit, and a stale
   job from the prior activation cannot dispatch into the new one.
   With activation A's next job armed, temporary unavailable presence cancels
   only action work; it neither ends A nor creates B. When current stabilized
   `away` returns after that job's due time, one fresh evaluation selects the
   descriptor's next still-future step in A's same job slot, or leaves the
   slot empty if no step remains. Repeated evaluations create no duplicate
   `AtJob` or command; an obsolete callback cannot dispatch. A known due
   boundary for an active next-step hold remains available for release even
   while presence is unavailable.
   Given a sequence whose final planned step switches off a light, no return
   allows that step to run through ordinary admission when due within the
   selected session and absence interval; a committed return before
   its dispatch cancels it and leaves the observed light state. A step
   already sent to HA is not compensated. If a committed return closes the
   activation between two calls of a closing bundle, the per-call fence
   rejects the unsent call while preserving the first call's recorded outcome,
   even when the follow-up intent write is still pending.
   A blocked or unconfirmed planned
   step uses the ordinary outcome and follow-up path, never a claimed
   physical result. No second switch-off is added solely because an episode
   or activation ends.
4. A known-invalid original bundle may be replaced only by a freshly derived complete plausible
   alternate bundle whose every member passes common admission. Otherwise no member is commanded. A
   failure after a sent `ApplyCall` records its partial outcome, stops later work and never compensates
   a completed call.
5. Staging begins disabled; promotion without consent is
   `authorized_awaiting_household_consent`; a current grant enables only fresh evaluation; resident
   revocation, administrative disablement and a configuration successor cancel future jobs and do not
   inherit authority. Resident-authority removal exercises each explicit retain/revoke disposition.
6. Audit/trace fixtures prove no generator seed, future programme, calendar text, resident identity,
   historical presence, raw HA payload or actor reference enters the descriptor's stored operational
   preview, job or execution-audit projections; the separate common governance ledger retains only its
   required actor references.
7. A session `Mon–Sun 22:00` with `duration=3 h` ends at 01:00 the following day and belongs to
   its start day; with `duration=24 h` staging rejects it as overlapping. On a spring-forward night a
   `02:30` start begins at `03:00` and still lasts its full duration; an ongoing session keeps its
   end across an HA timezone change while the next start uses the new zone. No session starts
   without the calendar absence and stabilized `away`.

These fixtures validate contract orchestration, not learned behavioral plausibility or an uncommanded
lighting effect. A future learned/imported temporal profile requires its own evidence and
shadow-promotion acceptance before it can replace the initial core generator.

Every active descriptor uses the common Reaction engine. A deterministic admin-direct
configuration may use a descriptor without a learner only when its `authoring_modes` admits
`admin_direct`; `environment.planned_comfort_trajectory` remains learner-proposal-only.
A learner may propose only values permitted by that same active descriptor.

### 7.3 Initial-V3 catalog matrix and valid examples

This matrix is the single owner summary of the seven Initial-V3 registrations; the referenced
sections stay authoritative for their details. Every Initial-V3 descriptor is registered at
version `"1"`, and every listed profile is `RelationProfileRef(profile_id=..., version="1")`.

| Descriptor | Origins | Profiles -> policy output | Objective -> intent | Guard contract | Program |
|---|---|---|---|---|---|
| `environment.solar_shading` | direct, learned | `thermal_shading`, `solar_shading` -> `environmental_response.v1` | `limit_solar_gain -> increase_shading`; `admit_solar_gain -> decrease_shading`; `admit_daylight -> decrease_shading` (`solar_shading` or direct only) | `environment.solar_shading.guards.v1` | trigger-driven |
| `environment.external_exchange` | direct, learned | `thermal_exchange`, `air_quality_exchange`, `hygrometric_exchange` (one per purpose) -> `environmental_response.v1` | thermal: `cool_with_outdoor_air`, `warm_with_outdoor_air -> open_for_exchange`, `limit_thermal_exchange -> close_to_retain`; `reduce_co2`, `reduce_moisture -> open_for_exchange`; `close_after_ventilation -> close_to_retain` (direct only) | `environment.external_exchange.guards.v1` | trigger-driven; safe: `close_to_retain` |
| `environment.air_extraction` | direct, learned | `humidity_extraction` -> `environmental_response.v1` | `reduce_moisture -> activate_extraction`, `adjust_extraction`; `end_extraction -> stop_extraction` (direct only) | `environment.air_extraction.guards.v1` | step-programmed; low-risk: activate, adjust; safe: stop |
| `routine.actuation_bundle` | direct, learned | `routine_actuation_bundle` -> `routine.bundle_frequency.v1` | `reproduce_resident_routine ->` every admitted member intent | `routine.actuation_bundle.guards.v1` | trigger-driven |
| `environment.planned_comfort_trajectory` | learned only | `hvac_thermal_response` -> `hvac_thermal_response.policy_output.v1` | `planned_comfort_reachability -> follow_comfort_trajectory` | from its prerequisite generation (§7.1) | step-programmed, `planned_absence_program` v"1" |
| `security.presence_simulation` | direct only | none | none (direct `light_state`) | `security.presence_simulation.interior_lighting.v1` | step-programmed, `planned_absence_program` v"1" |
| `safety.weather_protection` | direct only | none | none (direct `secure_for_weather`) | `safety.weather_protection.guards.v1` | step-programmed per hazard episode; safe: `secure_for_weather` |

Only environmental-response members carry a `NumericOutcomeRequirement`, in the registered outcome's
canonical unit; comfort-trajectory and routine members carry `None`, and presence simulation has no
candidate. Valid examples:

- **Direct:** solar shading, external exchange, air extraction and routine in §7; presence
  simulation in §7.2 with its §7.2.1 fixtures; weather protection in §7.4.
- **Learned comfort trajectory:** the exact candidate translation of Layer 3 §6.4.1.
- **Learned solar shading:** `reaction_descriptor_id="environment.solar_shading"`, version `"1"`,
  subject the living room, `relation_profile=solar_shading@1`, `objective_id="limit_solar_gain"`,
  `descriptor_parameters={}`, one member `increase_shading` on the awning channel with
  `opening_id="living_south_window"`, its canonical shading target and
  `NumericOutcomeRequirement(minimum_practical_delta=0.5)` (°C reduction), required guards exactly
  `thermal_bounds`, `wind` and `precipitation`, and the artifact's supported incident-solar-exposure and
  outdoor-temperature cells as envelope.
- **Learned air extraction:** `environment.air_extraction` `"1"`, the bathroom subject,
  `humidity_extraction@1`, `objective_id="reduce_moisture"`, root `descriptor_parameters` carrying the
  staged program parameters of §7 (`start_level`, `max_level`, `settle_window`, `end_level`,
  `end_dwell`, `max_runtime`), one `activate_extraction` member at `level` 1 with
  `NumericOutcomeRequirement(minimum_practical_delta=0.0005)` (kg/kg humidity-ratio reduction), an
  empty required guard set, and the supported humidity-rise and fan-state cells. Its step-up uses the
  `modify_up` class only when that cell is eligible.
- **Learned routine:** `routine.actuation_bundle` `"1"`, the living room, `routine_actuation_bundle@1`,
  `objective_id="reproduce_resident_routine"`, the observed three-light bundle with
  `numeric_outcome_requirement=None` for every member, required guard exactly `presence`, and the
  context cells of its eligible `RoutineBundleFrequencyCell`s.

No example requires a placeholder outcome unit, a fictitious measured effect, an invented relation
profile or a guard outside its registered contract. Advice members (§3.2) are available only for
`environment.external_exchange` and `environment.solar_shading` intents; for example, an
external-exchange Reaction on a manual window has one `open_for_exchange` advice member naming only
`opening_id` and produces a `reaction.advisory` instead of a command.

### 7.4 Initial-V3 direct descriptor: `safety.weather_protection`

This descriptor secures exposed endpoints when a weather hazard arrives; Reaction guards alone only
veto opening or deployment and never close anything. It is `admin_direct` only, has no relation
profile or learner, and declares `requires_household_consent=True`,
`safe_direction_intents={"secure_for_weather"}`, `normal_exit_contract` below,
`managed_episode_resumption=False` and `hold_release_mode="fixed_duration"`.

- **Hazard and trigger.** One Reaction per hazard. Its start criterion is the `True` state of an
  administrator-declared Layer-2 boolean produced by `numeric.hysteresis_condition.v1` over a
  wind-speed or precipitation fact (for example wind at or above 40 km/h to enter, at or below
  25 km/h to exit). The exit threshold also defines the end of the hazard.
- **Opposing actions are vetoed, not outranked.** Each Reaction declares its hazard
  (`wind` or `precipitation`). Staging, in the same composed generation, requires every other
  staged action variant that moves a protected channel away from its safe target (for example
  `(increase_shading, exterior_deployable)` or `open_for_exchange`) to require that hazard's guard
  capability bound to exactly this Reaction's hazard state (§3.2), and rejects the generation
  otherwise. While the hazard lasts, the opposing action fails its guard before arbitration, so
  securing never competes with it; identical safe targets from several Reactions, such as wind and
  rain closing one window, coalesce into one command (§6.0).
- **Endpoints.** The administrator selects rooms and/or endpoints; staging keeps only Actuators that
  are `weather_exposed` (Layer 2 §6: declared exterior, in an exterior room, or undeclared on an
  opening that faces an exterior side, so a window operator qualifies while an interior blind declared
  `is_external=False` does not), and only channels whose core translation registers
  `secure_for_weather`. The
  persisted set is explicit and canonically ordered, never a live group; an empty result rejects
  staging.
- **Target.** The safe target is fixed per channel kind and adapter by the core translation entry
  (closed opening, retracted awning, closed shutter), never chosen by the administrator. A channel
  already observed in its safe target receives no step.
- **Program.** The hazard boolean becoming `True` opens an activation; its evaluation selects one
  `secure_for_weather` step for every selected channel not in its safe target, each through ordinary
  admission. Later evaluations during the same hazard secure a channel that has left its safe target
  only when no hold blocks it. The boolean returning `False` is `natural_completion`; it sends no
  command and never restores a prior position. After a restart a still-active hazard opens a new
  activation from fresh state.
- **Resident hold.** A manual hold on a selected channel is respected; the descriptor never
  preempts a resident or another writer (§3.2). While the hazard is active and a held channel is not
  in its safe target, Layer 5 emits the existing `AvailabilitySuppressionOccurrence` with
  `manual_hold_active` for that channel, so Layer 6 can warn the resident (for example "living-room
  window held open by you; rain detected").
- **No confirmation.** Securing runs without a runtime confirmation; the completed or skipped steps
  are reported as ordinary execution audit and follow-up outcomes, and the descriptor's
  `resident_action_notice=True` produces one `ReactionActionNoticeOccurrence` per activation that
  Layer 6 appends as `reaction.action_notice` (§6.0).
- **Valid direct example.** Casa subject, `relation_profile=None`, trigger
  `state_transition(environment.wind_hazard@casa, False -> True)` from a hysteresis over the casa
  wind-speed fact, selected endpoints the living-room awning (`is_external=True`) and the living-room
  window actuator on `living_south_window`, the zero-axis empty-key envelope and an empty guard
  binding set. With the awning extended and the window open, both are secured; with the window held
  open by the resident, only the awning is retracted and a `manual_hold_active` occurrence is
  emitted for the window.

## 8. Initial acceptance criteria

- A consent request answered `grant` from a notification by a resident in
  `HouseholdConsentAuthority` appends the same authority transition as the command and closes the
  request `granted`; the same answer from a resident not in the authority, after the request
  closed, or with a stale opening transition changes nothing. `decline` changes no authority and
  closes the request for every authority. After a restart, a Reaction still awaiting consent
  produces one `reissued` occurrence with a new `response_request_id`; a button carrying the old
  id is rejected by the ingress. An
  advisory answered `not_useful` appends one `reaction.advisory_feedback` and nothing else; a
  second identical answer appends none; an unanswered advisory records nothing.
- A weather-protection activation that secures two channels and skips one held channel produces
  one `ReactionActionNoticeOccurrence` with three channel outcomes, once, after every confirmation
  window; a descriptor with `resident_action_notice=False` produces none. A new proposal produces
  one `ProposalReviewOccurrence(created)` for administrators, and a later evidence refresh that
  keeps it approvable produces none. Approval, rejection, incompatibility or loss of approvability
  produces one `closed` with its reason; two separate returns to approvability under the same
  evidence revision produce two distinct `approvable_again` operations. An advice activation that
  ends produces one `ReactionAdvisoryOccurrence(closed)` per advice member and no resident notice. Promotion of a consent-requiring Reaction produces one
  `ConsentRequestOccurrence(opened)`; a grant, disablement or successor generation produces one
  `closed` with its reason. None of the three carries actor identity or rendered text.
- A Reaction in `notification_only` produces no `ApplyStep` and no resident notification, only the
  administrator preview. Once authorized, an external-exchange advice member on a manual window
  (`opening_id` facing outside, no Actuator) produces exactly one `ReactionAdvisoryOccurrence` per
  activation, even across repeated evaluations, and no `ApplyStep`; household consent is not needed
  for it, while a command member in the same bundle still needs consent. An advice member for an
  intent outside `advisory_intents`, or without an Actuator and without an exterior-facing opening,
  is rejected at staging.
- Arbitration: wind and rain `safety.weather_protection` Reactions that both secure one window in
  one cycle produce one `ApplyStep` from the canonically first Reaction and one
  `coalesced_identical_target` audit for the other; a weather-protection close and an
  `external_exchange` `close_to_retain` with the identical complete target coalesce the same way.
  Different targets on one channel still block both bundles.
- With an exterior awning protected for wind and rain, staging rejects a solar-shading
  `increase_shading` Reaction whose `wind` or `precipitation` binding is not the protection
  Reaction's hazard state. While either hazard is `True` the deployment fails its guard before
  arbitration and the retraction proceeds; when the hazard ends nothing is restored, and solar
  shading may deploy again only through its own trigger and guards.
- `safety.weather_protection` stages the §7.4 example with an empty required guard set and rejects a
  selection containing no `weather_exposed` endpoint, and drops an interior blind declared
  `is_external=False`. On hazard start it secures every
  selected channel not already safe; a held channel is not commanded and yields
  `manual_hold_active`; hazard end sends no restore command; a restart during the hazard secures
  from fresh state only.

- Each §7.3 example validates against its registered descriptor, profile, objective/intent pair,
  guard contract and output schema; replacing a routine member's `None` requirement with a numeric
  one, adding a profile to presence simulation, or a learned `close_after_ventilation` or
  `end_extraction` candidate is rejected.

- `environment.air_extraction` stages the §7 direct example with an empty required guard set
  (`low_risk_intents` and `safe_direction_intents`). In its trace the fan starts at level 1 while
  the room is occupied, steps to level 2 only after `settle_window` with humidity still rising,
  is not stopped by vacancy, and stops at `end_level` held for `end_dwell` or at `max_runtime`. A fan
  already on at entry is untouched; a resident switch-off is `normal_cancellation` and no new
  activation starts until humidity first returns to `end_level`; a learned `adjust_extraction`
  without an eligible `modify_up` cell is suppressed; `start_level > max_level` is rejected.
- `routine.actuation_bundle` stages the §7 direct example with required capabilities exactly
  `presence`; it rejects a configuration without a `presence` binding, and a member whose physical
  action requires safety guards in an environmental descriptor inherits them. A learned candidate is
  proposal-eligible only under `routine_actuation_bundle` v"1" with a matching report entry that
  passes every `RoutineEvidenceGateCalibration` gate (Layer 3 §4.4.3).
- `environment.external_exchange` stages the §7 thermal direct example with required capabilities
  exactly `opening_security`, `precipitation`, `wind` and `thermal_bounds`; an `air_quality` opening
  additionally requires `outdoor_air_quality`; a `close_to_retain` variant stages with an empty
  required set because the intent is declared safe-direction, while still passing hold, physical
  confirmation and channel arbitration. It rejects a window toward an interior garage, a thermal
  trigger not derived from an indoor-minus-outdoor difference, an inline comparison, and a learned
  `close_after_ventilation` candidate.
- `environment.solar_shading` stages the §7 direct example with required capabilities exactly
  `thermal_bounds`, `wind` and `precipitation`; it rejects the same configuration without either
  weather binding, accepts an interior blind without them, never requires them for
  `decrease_shading`, rejects `admit_daylight`
  under `thermal_shading`, and treats an undeclared `is_external` on an opening facing an exterior
  side as `weather_exposed` (Layer 2 §6).
- Every governance command returns one `GovernanceCommandResult`: `applied` with its resulting
  record, `idempotent_replay` with the original result, or `rejected` with closed codes and no
  mutation; `stage_admin_direct_reaction` for comfort trajectory returns
  `authoring_mode_not_permitted`. Every acceptance outcome of §7.1.2 and §7.2.1 maps to a declared
  execution-audit code, `ReactionNormalExitOutcome`, `ApplyCallOutcome`, follow-up outcome or
  suppression reason; a code outside the descriptor's `execution_audit_codes` is rejected,
  `future_work_cancelled` always names its existing cause record, and first use with no adopted
  artifact records `fallback_served_without_artifact` with `artifact_ref=None` (§4.0).
- Every learned descriptor/profile pair resolves one exact frozen
  policy-output schema and validator through its `RelationProfileRef`.
  Tests reject an unknown variant, unit mismatch, unordered numeric interval
  or `Window` duration bounds, and a whole-bundle routine frequency record
  outside `[0, 1]`; none is copied into a candidate
  member. An ordered `ActuationBundle` admits
  two distinct registered channels, including unlike Actuator kinds, but
  rejects duplicate channels, excess members or raw HA calls before any
  `ApplyStep` (§3/§5).
- A routine output is checked once for the canonical bundle/context record;
  a zero baseline remains diagnostic and cannot be promoted by treating
  undefined lift as infinity. Duplicate records or a proposed envelope cell
  with no exact eligible record reject the proposal. Member-level effect copies are rejected
  (Layer 3 §4.4.3; §3.2).
- A Reaction trigger instant and correction occurrence use the exact Layer-1 `EvidenceInstant`
  bytes, and every positive trigger/model/attribution duration uses Layer-0 `Window` at the
  contract boundary. The millisecond arithmetic in the selector yields a `Window` before a
  scheduled job is armed; an alternate `Z` instant or integer-millisecond field is rejected
  (§6.0; Layer 0 §3; Layer 1 §4).
- A trigger-driven delayed action retains one stable activation action
  identity and one replacement `AtJob` slot. An unchanged due does not
  re-arm; an eligible revision change replaces the arm from the original
  in-process anchor; an obsolete callback cannot act. At due, the arm is
  retired before a fresh snapshot and one admission is recorded before an
  HA call or `already_satisfied`. A veto leaves that identity pending
  without a timer spin; a later relevant fresh change may re-evaluate it.
  A valid state exit or authority loss cancels it, and a process restart
  restores neither anchor nor job (§6.0).
- A room-scoped `routine.actuation_bundle` with one member whose exact
  translation has a matching versioned delay permission stages a
  `room_vacancy_return_delay` path from the
  physically supported `room_occupancy: present -> absent` transition.
  A missing permission, a target outside its accepted envelope, a staged
  maximum longer than its core maximum, an immediate-only intent, a second
  member, a
  mismatched room, or a binding to `stay_duration`, a scalar fraction, a
  different result schema or an absent maximum curve horizon rejects
  staging. Fixtures admit two different registered channel kinds with
  independently declared permissions, while a valve-position target
  without permission and a different target variant on an otherwise
  eligible entry are rejected. The member's display role and HA domain
  never decide permission. Bootstrap with no permission for the Initial-V3
  path rejects its descriptor registration (§§4.2, 6.0, 7; Layer 3 §4.4.1).
- At an exact maximum horizon, a valid return cumulative incidence of
  `0`, `0.5` or `1` selects respectively the staged minimum, midpoint
  rounded upward to a millisecond, or maximum. A declared `away`
  competing incidence is subtracted from `1-S`; it is never counted as
  a return. Invalid mass, missing one-minute calibration, withdrawn or
  unadopted evidence cannot affect the timer: the authorized seed is
  used. Layer-2 vacancy debounce is elapsed before the Layer-5 anchor;
  the end-to-end delay is their sum (§6.0; Layer 3 §4.4.1).
- A valid return to `present` before the due boundary cancels the vacancy
  action. A gap never supplies a return or a complete learning sample;
  compatible `absent` endpoints retain elapsed in-process timer time and
  require one fresh due evaluation. A current hold, conflicting owner,
  invalid physical state, guard veto, revoked authority or unavailable
  occupancy prevents the command. An already satisfied target records
  that outcome without an HA call. After restart the first fresh `absent`
  begins a full new wait, with no historical edge or replay (§§6.0, 7).
- A changed adapter, withdrawn permission or current target outside the
  staged permission envelope at due emits
  `actuator_capability_unavailable` and sends no immediate substitute
  command. A changed permission implementation requires a new versioned
  id and successor Reaction review; a valid target with current permission
  still passes every hold, guard, ownership and physical-state gate (§6.0).
- A generic contract fixture with a test descriptor for a state-fraction
  delay on `room_occupancy` and `qualifying_values=("absent",)` binds the same
  typed state and set in the Reaction and Layer-3
  `FutureStateFractionOutcome`. A second test-only boolean condition with
  `qualifying_values=(True,)` exercises the generic type contract; neither
  fixture claims an Initial-V3 solar timing model. Entry from outside the
  set starts an occurrence; a transition within the set keeps its anchor;
  exit cancels pending work; unavailability blocks action and follows the
  declared timer semantics when a fresh state returns. A later valid re-entry
  after an observed exit gets a new anchor only under the descriptor's
  trigger semantics. Staging
  rejects a different model source, Location,
  qualifying set or horizon, a value outside the staged vocabulary, and an
  event-only trigger without a descriptor-owned continuation contract.
  Neither typed case needs a second boolean projection merely to represent
  membership in the qualifying set (§4.2, §6.0).
- Every delayed Reaction plan declares its typed timer semantics and the
  descriptor version admits that choice; a model binding must use the same
  path, condition and qualifying values. A gap with qualifying values on
  both sides resets `continuous_observed`, pauses `accumulated_observed`, and
  counts elapsed time for `elapsed_if_requalified`. A return outside the
  staged set cancels all three. A due callback during unreadability commands
  nothing; a late return under `elapsed_if_requalified` requests one fresh
  evaluation, with current authority, guard, hold, target and state checks.
  Changing timer meaning requires a new configuration generation (§4.2, §6.0).
- After a process restart no delayed activation, anchor or pending `AtJob`
  survives. With the first valid qualifying condition in a fresh completed
  HA intake, a sustained-state delayed path starts its full current wait;
  an unreadable condition waits, and an event-only path does not synthesize
  a trigger. Three in-process source gaps may retain one elapsed anchor under
  `elapsed_if_requalified`, but a process restart always begins a new one.
  Neither path contributes a gap-crossing Layer-3 label (§3.2, §6.0).
- Candidate-kind staging admits only the two frozen Initial-V3 outer pairs
  `("reaction.descriptor", 1)` and `("reaction.artifact_adoption", 1)`.
  The latter requires a current Reaction/generation, registered serving role,
  exact eligible artifact and matching immutable validation/shadow
  assessment; it cannot carry descriptor parameters, members, commands or
  new authority. A wrong kind/version or assessment for another revision is
  rejected before a proposal root is persisted (§3, §4.1).
- An administrator switches an adopted Reaction role from `pinned` to
  `bounded_adaptive` against its exact current adoption head: the same
  artifact remains selected, the current configuration's compatibility
  bounds are revalidated, and neither the Reaction generation nor its
  administrative authorization or resident consent changes. Switching
  back fixes that exact current revision, even if temporarily unavailable.
  An automatic compatible refresh racing with either switch serializes on
  the head: only the winner's precondition commits, and retrying the loser
  cannot silently advance. An absent head, stale head, unsupported mode or
  unapproved entry bounds rejects without mutation. Changing semantic
  Reaction bounds still requires a successor configuration (§4.2).
- A Reaction created with a selected eligible timing artifact commits its
  initial adoption with the notification-only generation and exact evidence;
  one staged without an artifact uses its seed. Two compatible `pinned`
  revisions with the same semantic Reaction payload produce distinct
  revision-specific adoption proposals. Accepting one through
  `review_proposal` appends exactly one adoption transition to the existing
  generation, leaves admin authorization and resident consent intact, and
  issues no command. Rejecting it leaves the old head. An older revision,
  changed generation, invalid artifact or concurrent head change cannot
  overwrite a newer adoption (§4.1–4.2).
- A compatible `bounded_adaptive` refresh appends one system transition only
  within the staged binding and approved bounds. An expanded envelope,
  changed trigger or action, or missing quality/shadow gate cannot auto-adopt.
  A crash exposes the old or new complete transition; a retry duplicates
  neither. A withdrawn or stale adopted artifact uses the staged seed while
  retaining audit, and a pending timer is recalculated from its original
  anchor without replaying a completed step (§4.2, §6.0).
- A learner proposal with a declared timing-model role records the exact
  supporting artifact revision beside its primary artifact in the same
  initial evidence transaction. A compatible revision refreshes evidence
  without changing the semantic proposal fingerprint; missing, duplicate,
  undeclared, stale or binding-incompatible support is not approvable.
  Neither a redacted snapshot nor a root parameter can replace the typed
  supporting reference (§4.1–4.2).
- For an irradiance-triggered solar-shading occurrence, an entry crossing starts
  one dwell anchor. A transient exit before the effective deadline cancels the
  pending command; re-entry starts a new occurrence. A staged fixed dwell
  of three minutes reaches one fresh evaluation three minutes after the
  original entry; it does not add a second minimum-dwell timer. A separate cover-movement
  cooldown still gates admission. Staging rejects a geometry-only proxy, a
  different opening's condition fact, a non-boolean condition for this
  particular solar descriptor, a learned solar-fraction binding, or copied
  thresholds in the Reaction. Loss of the Layer-2 condition output suspends action. If its last
  valid value was `True` and the first fresh value is also `True`, elapsed
  gap time counts toward this Reaction's wait and a passed due is evaluated
  once against fresh state; `False` cancels. The gap remains incomplete for
  Layer-3 learning and cannot be an inferred solar transition (§6.0, §7).
- A pure state-fraction selector fixture with `min=1 min`, `max=10 min` and a matching
  ten-minute forecast chooses 1 minute at `q=1`, 10 minutes at `q=0`, 2 minutes
  48 seconds at `q=0.8`, and 8 minutes 12 seconds at `q=0.2` (§6.0).
  Fraction values outside `[0, 1]`, wrong dimension/unit, condition, Location,
  horizon or artifact identity cannot influence timing; an unavailable model
  uses the staged seed. A changed maximum is a changed binding horizon, not a
  reuse of a forecast trained for an older maximum. A non-millisecond-representable
  bound or seed fails staging; no constructor or scheduler silently rounds it.
- A `ReactionTimingModelBinding` enters one immutable configuration and plan
  fingerprint with its exact learning definition, sample/result schemas,
  condition and window. Changing the trigger, definition, horizon or bounds
  creates a semantic successor generation and loses prior action authority;
  refreshing only a compatible artifact revision leaves that fingerprint
  unchanged and follows CA4-14 adoption. A mismatched or unregistered binding
  fails staging, while a valid binding with a temporarily unusable artifact
  selects its seed and cannot treat that artifact as automatically authorized
  (§4.2, §6.0).
- Removing a Sensor that an automatic extraction Reaction uses as a declared
  occupancy guard is a breaking impact. Without the administrator's
  confirmation of the current `impact_fingerprint` nothing commits; with it,
  one composed commit records the new Layer-2 generation, an authority
  transition disabling authorization and consent, cancelled future jobs and
  the derived `configuration_invalid` mode. The Reaction neither evaluates nor
  shadows; an unsent call of its old generation fails the dispatch fence. A
  successor configuration that validates starts `notification_only` and needs
  fresh promotion and consent. Changing only that Sensor's reliability is
  `semantic_only`: generation and authority stay unchanged and the Reaction
  appears in the impact record (§4.2; Layer 0 §4.7).
- Each of the seven Initial-V3 descriptors can reach its permitted
  `notification_only` creation path through `stage_admin_direct_reaction`
  or `review_proposal`, and uses the same `promote_reaction_automatic_action`,
  `set_reaction_household_consent` when its consent property is true,
  `disable_reaction_automatic_action`, and household authority commands.
  A stale configuration or authority precondition, unauthorized actor,
  changed request under one operation id, or invalid descriptor configuration
  causes no partial mutation. A retry with the same operation id returns the
  prior result. Promotion and consent never issue an `ApplyStep` themselves;
  revocation/disablement stop future dispatch. A comfort prerequisite edit
  uses only its descriptor-specific preparation command and cannot bypass
  the common authority lifecycle.
- Every Initial-V3 `RelationProfileRef` resolves one registered policy-output
  schema id/version and validator. Layer 3 rejects an output missing that
  identity or failing its validator; Layer 5 rejects a candidate whose output
  identity or parameter disagrees with the artifact, its profile's frozen
  release-gate calibration or current profile registration. A new profile uses the same hand-off without a
  new cross-layer pipeline. The thermal registration accepts only its existing
  `ThermalResponseParameter` under a complete frozen `ThermalEvidenceGateCalibration`;
  the common environmental response schema rejects a thermal-only payload.
- A `require_confirmation` recovery proposal uses Layer 0 §7.4.1 for one request per
  channel and recovery episode. Layer 5 recomputes its final target and ordinary
  guards from fresh cycle inputs before a response may dispatch through the common
  `ApplyStep` path. A changed target, unreadable channel, revoked consent, failed
  guard or changed configuration invalidates the old request; an unrelated fact
  update does not. An already satisfied target sends no command, and a response to
  a pre-restart request id is rejected.
- Recovery decisions use only the `DecisionSnapshot.recovery_view` and
  `reaction_authority_view` frozen at the same intake barrier. A revoked
  Reaction facet is filtered by that authority view, and a later revocation
  also blocks an already prepared command at the dispatch fence. A
  post-barrier checkpoint update cannot change this cycle's target; an
  unreadable channel cannot be treated as a verified match.
- A `state_transition` on a Layer-4 semantic state fires once for a complete
  typed previous/current change in the completed snapshot. Equal values,
  including provenance-only changes, do not trigger; unavailable, first-cycle,
  post-restart or producer-changed pairs abstain. A same-cycle change that
  returns to the previous value is no net transition; declared episodes
  remain the route for individual occurrences (§5.1–5.2).

- Every Initial-V3 descriptor, whether environmental, security or routine, resolves its
  declared guard references through the one core `ReactionGuardCapabilityRegistry`
  and `ReactionGuardContractRef` mechanism of §3.2. Staging rejects a descriptor
  that invents a separate guard evaluator or uses an unregistered capability.
- A profile-free `admin_direct` presence simulation compiles through the
  descriptor's frozen slot/temporal/parameter grammar and exact direct guard
  contract into the ordinary `ReactionEvaluationPlan`. Staging rejects an
  undeclared slot, comparison, partition, axis or cell. The plan retains the
  descriptor's programmed start-criteria reference; departure, calendar
  refresh and next-step callback request fresh evaluation rather than
  installing a second trigger. A fresh bootstrap `away` plus active plan may
  start one new activation without a synthetic departure or missed-step
  replay; repeated qualifying cycles reuse it (§§3.2, 4.2, 5.1, 7.2).
- A direct solar-shading or external-exchange generation has the one
  descriptor-registered zero-axis empty-key envelope only when its complete
  typed trigger, conditions, targets and variant-required guards validate.
  An absent/stale trigger or guard blocks despite the matching empty cell;
  the same descriptor's learned proposal still requires exact supported,
  calibrated context cells. A thermal `open_for_exchange` variant is not
  forced to bind an air-quality-only capability, while the air-quality
  variant cannot omit its registered capability or opening-safety guards.
  An unknown purpose, a mismatched guard contract, a direct cell with
  fabricated support or an administrator-added axis rejects staging (§3.2,
  §6.5 of Layer 3, §7).
- `quiet_hours.v1` stages only against the exact casa `quiet_hours.active` boolean
  Layer-2 state claim, including an HA `schedule.*` binding using the ordinary
  Layer-2 mapping. A descriptor that requires it blocks on `True`, unavailable,
  stale or invalid input and passes on `False`, with `action_guard_active` as
  its suppression reason. A descriptor without that required capability acts
  under its other gates even when quiet hours are active. Layer-6 notification
  quiet hours do not change this action result (§3.2, §6.0).

- Layer 4 has no dependency on the registry, configured policies, candidates, Reaction proposals or
  action results. Layer 5 receives only its post-DAG immutable snapshot.
- A candidate cannot invoke policy evaluation, Actuator resolution or command generation; only Layer 5
  can persist a `ReactionProposal` or emit an `ApplyStep`.
- Every staged Initial-V3 step-programmed descriptor uses one activation-stable `AtJob.job_id` as its
  next-step replacement slot, distinct from each selected channel's `planned_step_id`.
  Concurrent members at one due boundary occupy one slot with a bounded canonical step tuple.
  An unchanged
  selection does not re-arm; a changed selection replaces that same slot; a callback carrying
  an old arm revision, generation, activation or step is a no-op. A temporary unavailable
  required input or guard veto preserves the activation, admits no command and cannot create
  a second slot. On recovery, a fresh snapshot selects at most one descriptor-valid next job;
  a verified exit or authority loss cancels the old slot. A previously identified due boundary
  needed for a next-step hold still evaluates non-command release while its guard blocks action.
  Two concurrent evaluations cannot admit one planned member twice; `already_satisfied` also
  consumes that member's scheduled decision without an HA call.
- The outer candidate kind version is admitted only as the exact registered JSON integer `1`;
  an Initial-V3 `RelationProfileRef.version` is admitted only as the exact registered JSON string
  `"1"` in its two-field object. Staging rejects `1.0`, `1e0`, `"1"` for the outer version,
  numeric `1` for the profile version, or a combined `profile_id@1` substituted for that object.
- `ProposalCandidateKindRegistry` accepts only the exact registered candidate kind/version before a
  Reaction-descriptor validator runs. Tests reject an unknown kind, a kind with an incompatible version, a payload
  that resembles `reaction.descriptor` but lacks its exact `("reaction.descriptor", 1)` identity, and a
  Reaction-descriptor version used as a substitute for candidate-kind compatibility. Changing/removing the core
  kind version invalidates only candidates, Layer-3 bindings, and still-pending `ReactionProposal`s
  that reference it; each pending proposal records its accepted kind/version and moves to the terminal
  non-approvable `proposal_incompatible` disposition. Tests prove that no replacement or payload
  rewrite is created and that an already configured Reaction remains evaluable when its independent
  Reaction-descriptor id/version, topology, Actuator and guard contracts remain valid; no lookup performs I/O,
  dynamic import, HA access or plugin dispatch.
- A fact appended after a `DecisionSnapshot` cannot change the trigger, guard or envelope result;
  every accepted Layer-2 intake fact sharing its trigger `when` is visible before evaluation, while
  Layer-4 output is visible only through the resolved semantic-claim map.
- A calendar refresh after `CycleInputBarrier` cannot change the active or upcoming windows seen by
  a Layer-5 policy in that cycle. A predictive plan reads only its staged requirement id in the
  `FrozenCalendarView`; an attempted direct `upcoming_starts_within` call or widened horizon during
  evaluation is rejected. Layer 4 transports but never classifies the calendar view.
- Each evaluation has exactly one closed outcome. Only `eligible` reaches bundle admissibility; an
  admitted bundle yields its canonical ordered one-endpoint `ApplyStep`s for
  `(reaction_id, configuration_generation_id, reaction_activation_id, snapshot_id)`.
  An active or unresolved intersecting
  hold blocks the whole bundle through the frozen hold view. Two eligible bundles claiming one
  channel block both regardless of target or iteration order; a non-ownership-blocked bundle makes
  no ownership claim. Atomic multi-member reservation and lease release preserve single-writer
  ownership, including a retry, partial execution, and a fresh state check after restart.
  A known-invalid member blocks every step; a later HA execution failure stops the remaining steps,
  records a partial bundle outcome, and triggers no automatic compensation.
- An ordinary `abstained` evaluation or eligibility/admissibility failure emits Layer 3's typed
  `AvailabilitySuppressionOccurrence`, with its complete canonical closed reason set.
  A due hold-releasing step or terminal action that is skipped also follows the distinct
  `reaction.follow_up` outcome path in §6.0; availability and follow-up facts retain
  separate purposes and producer identities. Tests cover
  unavailable/stale semantic input, unsupported envelope, manual hold, command ownership, actuator
  capability/state, cooldown and action guards; a concurrent hold and safety guard remain two reasons,
  never a fabricated primary reason. Tests prove every permutation of the same causes produces the
  same Layer-3 canonical reason tuple. Every occurrence reaches Layer 6's transient
  `AvailabilityEpisodeTracker` regardless of the current binding set; Layer 5 cannot query the
  publication index, render, persist or deliver `automation.availability`.
- All seven Initial-V3 descriptor registrations named in §3.2 each declare
  `requires_household_consent=True`. After admin promotion without a resident
  grant, each projects `authorized_awaiting_household_consent` and sends no
  `ApplyStep`; revocation blocks subsequent dispatch, including the next call
  of a partly executed step. These authority states emit no
  `AvailabilitySuppressionOccurrence` and no `action_guard_active` solely for
  missing consent. A hypothetical registered descriptor declaring `False`
  rejects a non-`None` consent field and can become `automatic` through admin
  authorization alone; one declaring `True` rejects `None` and requires a
  current grant for its exact generation.
- A rejected, timed-out, transport-failed or invalid-response `ApplyCall` is recorded solely as a
  bounded Layer-5 execution-audit diagnostic. It never extends `AutomationSuppressionReason` or emits
  an availability occurrence; tests distinguish it from a pre-command admissibility failure.
- Given one admitted `ApplyStep` compiled to two HA calls, if resident consent is revoked,
  administrative action is disabled, its activation is cancelled, or its Actuator is rebound to a
  new endpoint after the first call, the per-call dispatch fence records the first call's actual
  outcome and marks the second `not_attempted`. It sends neither an old-authority call nor a call
  to the new endpoint under the old admitted generation. An accepted external targeted-facet edge
  between calls has the same stop effect; an unrelated channel or genuinely disjoint facet does not.
  A timed-out first call is not blindly retried: its physical outcome follows §6.0.1 and another
  command requires a fresh valid read and current authority. This tests the common dispatch fence
  independently of the cross-layer composition commit of Layer 0 §4.7.
- Given an environmental descriptor whose profile requires opening security and wind, staging
  requires only those descriptor guard bindings. When a readable channel has an active hold,
  action admission reports `manual_hold_active`; when a separate channel is unreadable, it
  reports `actuator_state_unconfirmed`. Neither cause alone becomes `action_guard_active`
  (§3.2, §6.0).
- Given a physically confirmed standalone admin or recovery `ApplyStep` without an admitted
  Reaction target, a later divergent edge creates no Reaction-anchored hold. Given a current
  admitted Reaction target matching that physical state, only a later distinct edge may open
  its hold, regardless of which actor established the matching state (§6.0.1).
- Two channels on one endpoint retain distinct recovery targets; partial targets on
  one channel update only their addressed facets. Revoking one facet's Reaction
  removes that facet from the baseline without relabeling it as a direct command
  or deleting a still-authorized sibling facet. An incompatible merged target
  abstains, while a surviving direct-admin target still passes current safety
  admission before reconciliation or a confirmation proposal (§6.0, Layer 0 §7.4).
- Given a selective hold opened by Reaction A and a disjoint facet confirmed by
  Reaction B, a later mixed-facet observation produces one transition with both
  confirmed expectation sources. B's planned step does not release A's hold;
  A's qualifying step releases it before fresh admission. No source is invented
  for an unconfirmed facet (§6.0, Layer 0 §6.1–6.2).
- When B's previously confirmed target is actually superseded while its facet
  is held, only that facet is removed. A still-divergent facet retains A's
  boundary; if B was last, `invalidated/expectation_superseded` closes the
  hold without a false convergence claim. A due but rejected B candidate
  leaves the earlier current expectation intact; a replacement target can
  anchor only after current admission and physical confirmation (§6.0).
- Given a hold that expires before normal Reaction completion, an observed mismatch with the
  last confirmed target still yields one `ended_without_final_target` follow-up; a later verified
  complete match yields none. A due target-changing step that releases an active hold and is
  skipped, and a normal-cancellation final target that is skipped, each yield one typed occurrence
  with its own compatible closed outcome. Pending terminal observation may resolve as
  `terminal_action_unconfirmed` after activation closure without another call. A fresh
  post-release snapshot may compute a different final target than the prepared
  intent; the occurrence records the actual target and cannot be rejected solely
  for that difference. Ordinary hold activation,
  administrative revocation and full physical confirmation produce no follow-up. The validator
  rejects a path/outcome mismatch, wrong generation/activation/channel/Location, raw HA state, excessive
  projection, or a forged `interrupted_before_outcome` outside recovery (§6.0).
- Fixtures cover every closed `ReactionFollowUpOutcome`: normal exit leaves a
  divergent observed channel without a final target; an active-hold next step is
  skipped by a guard; an admitted next step passes its deadline without physical
  confirmation; a terminal target is skipped by current admission; a terminal
  target remains unconfirmed after activation closure; and a crash leaves only a prepared
  intent. Each fixture checks the compatible path, observed/unavailable projection,
  single Layer-6 warning fact, and no false physical-success claim. A complete match,
  an expired but reconciled hold, and a stale pre-restart target each create no
  `ended_without_final_target` fact (§6.0).
- A schema fixture checks every declared field of `ReactionFollowUpIntent` and
  `ReactionFollowUpOccurrence`: nonempty stable identities, subject/location,
  path/outcome compatibility, matching activation, hold and planned-step applicability, later-step
  status, bounded expected/observed facet maps, observation availability/time/
  epoch consistency, and preparation/occurrence instants. Layer 6 rejects an
  omitted, extra or mismatched immutable field; it permits the outcome target
  and observation to differ from preparation after a fresh snapshot (§6.0).
- A light target with power, brightness and RGB colour yields canonical JSON
  text facet values in the complete hold audit and durable intent; Layer 6
  emits only scalar `expected.<facet>`/`observed.<facet>` context entries.
  An illustrative future-descriptor valve position and Initial-V3 HVAC
  `mode`/`setpoint_c` take the same codec; the valve normal-exit payload
  is not an Initial-V3 executable outcome.
  The Layer-1 depth-two and 8 KiB validators accept the complete facts and
  projections; a nested facet map in event context, noncanonical text, raw
  HA object or unbounded target contract is rejected before publication.
  Staging proves worst-case sizes, not only these representative samples
  (§6.0; Layer 0 §6.1/§6.4; Layer 1 §3–4;
  [complete serialized examples](ca4_01_serialization_examples.md)).
- Given a qualifying follow-up boundary and a preparation acknowledgement before the
  finite core deadline, Layer 5 advances only after the typed intent is durable;
  Layer 6 alone persists one warning event with
  a key derived from `reaction.follow_up` and its operation id. A crash after preparation
  but before a committed outcome yields one uncertainty warning on recovery and no replayed
  command. A crash after event commit does not create a second fact. A conflicting payload
  under the same id fails; a distinct outcome id appends independently. A delivery accepted
  by HA just before a crash may be attempted twice if its acknowledgement was lost.
  With failed intent preparation or a write still pending at the monotonic core deadline,
  the scheduled step proceeds through current guards, exposes
  `follow_up_durability_degraded`, and does not promise recovery of that notice.
  A late successful prepare and either a final event or a confirmed no-event
  retirement under the same id serialize to one terminal outcome; a
  never-returning write cannot stall the step. A crash after
  the deadline reports interruption only if a prepared intent actually committed;
  revocation never waits for storage (§6.0; Layer 0 §4.5).
- One normal exit on three different lighting channels derives three
  different operation ids from one activation. With B's preparation failing
  at the deadline, A/C advance only after their own acknowledged prepares;
  B proceeds in diagnosed best-effort mode. A crash recovers uncertainty
  notices only for committed prepared rows, never a replayed light command.
  Exact retry preserves each channel id and frozen intent; a changed retry
  fails; per-channel notification keys do not merge A/B/C. A second
  activation or another planned step gets different ids. A new activation
  after restart also has a distinct collision-resistant activation id under
  the same Reaction/generation, so an old outbox row cannot consume its
  channel boundary. Revocation stops
  unsent calls without waiting for any channel's outbox (§6.0; Layer 0 §4.5).
- A resident correction is evidence for learning only through one deduplicated, uniquely anchored
  `actuator.correction` event from §6.1. Raw HA state changes, ambiguous anchors and non-resident
  origins cannot become a `resident_manual_override` by a Layer-3 inference or configuration choice.
- An admitted `already_satisfied` target produces exactly one decision and
  one complete-observation `actuator.target_lifecycle` event with one
  `apply_step_id`, and no HA call. A dispatched target with only partial
  matches produces no complete phase; a late coherent full match may
  produce it without revising a terminal `unconfirmed` call outcome.
  Reused evaluations and callback retries duplicate no phase. A newer
  admitted target, authority revocation or channel observation break
  closes the earlier anchor with one typed reason; a resident correction
  alone does not. All phases fit the bounded Layer-1 event value, and
  service completion alone never creates a learning anchor (§6.0.1/§6.1).
- A verified resident edge joined to an available channel-state record
  that changes only an omitted facet is not a target correction. An
  external/unknown normalized edge may produce only the diagnostic
  `external_or_unknown_correction` classification; an unavailable edge,
  raw HA change or propagated user context cannot be relabelled resident
  (§6.1; Layer 0 §5.1.1).
- A one-shot routine's calls complete and a later resident edge diverges from its
  confirmed target: with no registered normal-exit contract, the fixed-duration
  hold remains until its own deadline or another ordinary release/invalidation.
  A valid configured step source proves both no later step and no ongoing target:
  its descriptor emits `natural_completion` with matching generation, snapshot
  and evidence fingerprint, and the normal exit policy runs. An unavailable
  step source, guard veto, ordinary re-evaluation or completed `ApplyStep`
  yields `not_ended`; administrator disablement uses immediate revocation.
  Staging rejects `next_reaction_step` without both bounded future step
  identity and a descriptor-owned normal-exit contract (§3.2, §6.0).
- One compiled `evaluate_program` call on a frozen snapshot selects a start,
  an ongoing target change, a verified normal exit, or abstention for a
  step-programmed Reaction. A staged event and a due timer in the same cycle
  produce at most one effective target and `planned_step_id` per channel;
  ambiguous output abstains. An event step occupies no `AtJob` slot and is
  admitted once through the ordinary guards, hold, ownership, `ApplyStep`
  and follow-up paths. Re-evaluation of the same event, a stale callback,
  restart and a closed activation do not duplicate or replay the step.
  The normal-exit rule is consumed only inside that evaluator (§3.2, §5.1,
  §6.0, §6.2).
- A descriptor with a declared final target returns it as the terminal step,
  or returns that step's identity with a typed unavailable-target reason, of
  its `normal_exit` program decision. The mandatory fresh post-release
  snapshot revalidates that step through the same registered specialization;
  an invalid or unavailable current target is skipped and reported under
  the existing terminal follow-up path, while the verified exit still closes
  the activation. No independently chosen second target or duplicate
  terminal `ApplyStep` is admitted (§3.2, §6.2).
- A step-programmed descriptor registration without its versioned pure
  `program_evaluator` is rejected. The persisted plan contains only validated
  data and resolves the exact registered specialization after restart. That
  specialization receives the frozen snapshot and activation state, returns
  one closed step decision with a typed target or a wait/end/abstain result,
  and cannot dispatch an HA call. Layer 5 rejects an undeclared target,
  invalid step identity or out-of-bounds parameter before common admission.
  The same interface stages and executes a cover-position change and a
  fan-target change without a kind-specific Layer-5 branch (§3.2, §4.1).
- A multi-transition relation profile registers finite disjoint
  `transition_class_id`s with exact physical and comparable stable-reference
  matchers. Its `environmental_response.v1` validator rejects an unknown or
  duplicated class/context/horizon output, a class-mismatched cohort and a
  program step trying to consume another class's estimate. An extraction
  profile cannot pool physical start, modification and termination effects;
  the same rule applies to bounded valve or cover target changes (§3.1, §7).
- A step requiring an exact-class estimate suppresses only that step when
  its class/context/horizon cell is ineligible. An independently declared
  deterministic step remains evaluable through the same `evaluate_program`
  and current admission. If verified normal exit has an unavailable
  estimate-dependent terminal target, the activation closes and the
  terminal follow-up reports the skipped command; no generic actuator-off
  default is inserted (§3.2, §6.2, §7).
- A managed fan, cover or valve has an eligible modification cell but its
  current staged condition no longer calls for a change: `evaluate_program`
  selects no modification. If current need persists but the exact class cell
  fails the conservative objective threshold, the same step is suppressed;
  another class or a developer-stated fixed efficacy cannot substitute.
  A separately declared normal exit is still evaluated from fresh inputs.
- An `environment.air_extraction` Reaction can stage in a registered laundry
  room or kitchen with a compatible extraction fan; no bathroom label is
  required. It selects exactly one of an upward relative-humidity
  `level_crossing`, a positive `delta_over_window`, or a positive
  `rate_over_window`; staging rejects a missing/invalid unit, comparison,
  threshold or required positive bounded window and never compiles an
  implicit OR. A fast rise may qualify at a low absolute level when its
  selected rate criterion passes. Without a declared occupancy condition,
  an unoccupied room is eligible; with one, false blocks and missing/stale
  input abstains. Incomplete humidity history or an unavailable fan never
  becomes a qualifying rapid rise or an assumed fan-off state. A fresh active fan at
  qualifying start is left untouched even when its speed differs from the
  proposed target, with no `already_satisfied` target anchor. A fresh inactive
  fan may receive the declared activation step; the registered modification
  and terminal steps for that activation still need current admission and cannot bypass a
  resident correction hold. A first post-gap reading is a current baseline,
  not proof of what happened during the gap. The old one-shot draft cannot
  pass Initial-V3 staging as the complete extraction program; acceptance
  requires the registered start/change/end specialization and valid examples
  for all three decisions (§3.2, §5.1, §7).
- A step-programmed extraction registration with managed-episode resumption
  observes an initially inactive fan and a verified Heima off-to-on edge:
  one `open` projection joins that cycle's ordinary batch. A later speed step
  writes no new projection. After a committed opening and restart, a fresh
  active reading permits only current-policy continuation with new activation
  and ordinary guards. A crash before opening commit, an external matching
  activation, revoked consent, ended program or fresh inactive reading grants
  no continuation. At every restart, a fresh active channel lacking usable
  proof remains untouched and publishes
  `active_channel_unmanaged_after_restart` through the existing availability
  tracker even when the humidity trigger does not qualify. The ordinary
  `not_triggered` result remains distinct from that current-state warning.
  The issue stays open if humidity later falls while the fan remains
  active; a fresh off reading restores only this suppression, without claiming
  that Heima switched the fan off. An already-active fan at an ordinary
  in-process start is left untouched without this restart-specific reason. No
  historical training interval crosses the process gap (§3.2; Layer 0 §5.1.1.2).
- Staging a resumable descriptor without
  `active_channel_unmanaged_after_restart` in its closed applicability map,
  or authorizing it automatically without an exact enabled resident-visible
  availability binding per resumable channel, fails. A multi-channel
  descriptor cannot collapse two distinct channels into one suppression
  scope. The availability occurrence contains neither rendered text nor an
  Actuator/HA id and does not use `reaction.follow_up`'s prepared-intent
  write (§3.2; Layer 3 §6.3.1).
- Both Initial-V3 planned-absence descriptors declare
  `program_family=("planned_absence_program", "1")`, and staging rejects either one if its
  configuration lacks the `planned_absence` calendar binding, its casa presence fusion has a null
  `Stability.to_true`, or its descriptor version contradicts a family rule (hold release, restart,
  consent). Given the same calendar and presence trace — departure, bootstrap during an active
  absence, early return, calendar removal, calendar outage, interval end — the family component
  returns the same `AbsenceProgramState` for both descriptors; only their steps and targets differ.
  A family change is a new family version adopted through each descriptor's new version, never an
  in-place edit (§3.2 Program families).
- The Initial-V3 presence-simulation and comfort-trajectory descriptor entries both declare
  `hold_release_mode="next_reaction_step"`; their staged channels need no `hold_duration` unless
  another fixed-duration descriptor uses that Actuator. A confirmed scheduled target followed by
  a resident change opens one channel hold with a non-null anchor step and no expiry timestamp.
  Re-evaluating the pending future step keeps its identity; its first different target releases
  the hold before fresh admission, while a repeated target does not. A guard veto at the due
  different-target step suppresses the call without retaining the old hold. A verified normal exit
  uses the descriptor exit policy; an unavailable step source cannot fabricate a release (§6.0).
- Given one configured presence-simulation Reaction, a first qualifying
  absence creates activation A; its committed return ends A, releases only
  A-owned holds under the declared exit policy and leaves the Reaction
  authorized. A later qualifying absence creates activation B under the same
  generation. An A job, A terminal result or A follow-up intent cannot
  dispatch, release B's hold or be validated as B's outcome. A fresh restart
  during either absence creates a new activation without restoring the old
  hold; a calendar outage or guard veto creates no terminal result (§3.2,
  §6.0, §7.2).
- A `ReactionNormalExitResult` with an unknown outcome, wrong Reaction,
  generation, activation or snapshot, a fingerprint on `not_ended`, or no validated
  fingerprint on a terminal outcome is rejected. A terminal fingerprint
  derived from unavailable or non-declared evidence is rejected. The same
  configured generation and frozen inputs yield the same result; a terminal
  result never follows merely from command completion or an unavailable
  calendar/step source (§3.2, §6.0).
- Every descriptor uses the same evaluator, persistence path and action protocol. A namespace cannot
  select a custom runtime.
- A future direct descriptor registration with one or more envelope axes
  resolves each exact typed slot and pure versioned partition and bounds its
  permitted joint cells. Direct cells carry no learner support/calibration;
  learner candidate cells require both. Runtime uses the same exact-cell
  lookup and abstains on an unavailable, stale or unpartitionable input.
  An axis/partition change cannot silently mutate an authorized generation
  (Layer 3 §6.5; §3.2).
- Staging rejects unknown/incompatible Reaction-descriptor or relation-profile versions, invalid scope, illegal
  action/guard, unsatisfied endpoint/topology requirements, malformed canonical parameters/envelope, or
  a primary artifact incompatible with the exact profile-output schema,
  validator or descriptor/intent pairing. It requires a
  positive per-member `NumericOutcomeRequirement` only for a registered
  numeric-response member, rejects it for routine and comfort members, and
  validates their whole-bundle or thermal effect from exact typed evidence.
- A `planned_absence` calendar binding rejects an empty, duplicate, undeclared, non-ready, or
  source/horizon-incompatible requirement set. Tests prove that matching intervals from multiple
  declared calendars deduplicate and coalesce across overlap or adjacency, that the active union wins
  over an upcoming union, and that source order cannot alter the selected interval. A second category
  cannot cancel a matching absence interval; only a summary with multiple category matches uses the
  registered classifier `priority_order`.
