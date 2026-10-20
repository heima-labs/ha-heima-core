# L3a — `layer3_learning_spec.md` §1–§4

## Coverage

Read `layer3_learning_spec.md` lines 1–2854 (header, §1 Purpose, §2 Principles, §3 Scope, §4.1–§4.10
including every §4.4.x model and §4.8.x environmental subsection), plus the cited sections needed
to check them: Layer 0 §3.2 (`LearnedWindow`), §3.5 (cycle instant), §4.3 (14-day default
retention), §4.4 (`ObservationCoverage`, reasons, `first_incomplete_at`), §4.7 (composed generation),
§5 (`ControlActor`); Layer 1 §5 (`ScopeKind`/`Location`), §6.1/§7 (thermal envelope,
`opening_faces_exterior`), §3.1 (reserved `actuator.correction` event); Layer 2 §2.8.1, §2.9, §3.6,
§5.3 environmental formula configurations and destination rules; Layer 4 §9.1–§9.3; Layer 5 §3.1
(`RelationProfileRef`, `environmental_response.v1`, `routine_actuation_bundle`), §4.1
(`ReactionArtifactAdoptionProposal`), §6.0 bounded learned-delay selection, §6.1 correction and
target-lifecycle records, §7.3 catalog matrix; Layer 7 §4–§6.

Checked and found clean: cross-layer section citations to Layer 0 §3.5/§4.4/§4.6/§4.7/§5/§5.1.1.1,
Layer 1 §7, Layer 2 §2.9/§3.2/§3.6/§5.3, Layer 4 §9.1/§9.2, Layer 5 §3.1/§3.2/§4.1/§6.0/§6.0.1/§6.1/§7,
Layer 7 §4/§5; `ScopeKind` values vs §4.1.1 legal scopes; `RelationProfileRef.version` as string
`"1"`; the `return_delay` horizon/incidence formula vs Layer 5's room-return selector; the
`FutureStateFractionOutcome` horizon rule vs Layer 5's state-fraction selector; correction-record
fields and lifecycle phases vs Layer 5 §6.1; `ObservationGapReason` values used in §4.4.2;
`occupied_without_residents` and `occupancy.*`/`presence.*` episode names vs Layer 4; objective/action
pairs vs the Layer 5 §7.3 matrix; `serving_semantics` withdrawal rules between §4.1.2, §4.8 and §4.9;
tier-selection, requiredness scope and global-gate rules within §4.2–§4.3; registered finding
schemas and the `("reaction.artifact_adoption", 1)` kind vs Layer 5. Remaining findings below.

## Findings

### F-L3a-01 — `RoomOccupancySurvivalModel` declares no `shadow_requirement` despite an action-serving egress

- **Category / severity:** O / P1
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:1813` — "Passing offline validation makes an artifact eligible only for the next state permitted by its frozen core `shadow_requirement`; it is not operational by default. The requirement belongs to the reviewed learning-type/version (or its reviewed relation profile), never to a per-home definition"; `docs/specs/v3/layer3_learning_spec.md:1821` — "| `not_applicable` | The type has no operational egress. It remains diagnostic-only; no shadow state exists. |"; `docs/specs/v3/layer3_learning_spec.md:1045` — "`return_delay` may also publish a validated, reviewable action-serving artifact for the exact registered Layer-5 `routine.actuation_bundle` vacancy-delay path."; `docs/specs/v3/layer3_learning_spec.md:1051` — "The existing Layer-3 validation/shadow and CA4-14 adoption lifecycle governs this artifact"
- **Owner:** Layer 3 §4.4.1 — every other concrete type in §4.4 (`CorrectionCountHurdleModel-v1` l.1196, `ActuationRoutinePatternModel-v1` l.1477, `ContextRegimeNoveltyModel` l.1553, `IndirectAssistanceContract` l.1590, environmental profiles l.1915) states its frozen value; §4.4.1 does not.
- **Defect:** §4.7 makes the type's frozen `shadow_requirement` the sole gate from offline validation to an operational state, and the only value for a type without a proposal/live-signal path (`not_applicable`) is defined as "no operational egress". `return_delay` has an operational (action-serving timing) egress, yet no value is declared, so the shadow gate that "governs this artifact" is undefined and staging cannot apply the "exactly one closed `shadow_requirement`" rule to this type.
- **Proposed direction:** Declare the frozen `shadow_requirement` of `RoomOccupancySurvivalModel` per profile (diagnostic `stay_duration`, action-serving `return_delay`) and, if none of the five values fits artifact adoption into an existing Reaction, say which state it reaches.
- **Confidence:** medium
- **Verification:** pending

### F-L3a-02 — Person-related fact list omits Layer 2's `presence.evidence.person.<id>`

- **Category / severity:** O / P2
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:338` — "It is **behavior** learning when any feature, outcome or learner-specific episode member reads a person-related fact: `occupancy` (room or casa) and its `occupancy.physical`/`occupancy.evidence.*` inputs, `presence`, `presence.household`, `occupied_without_residents`, `activity.*`, `actuator.manual_control`, `actuator.correction`, `reaction.advisory_feedback`, or any `household.*` fact. Otherwise it is **physical** learning." and l.345 — "The person-related list is core-owned; a new person-related fact type joins it in the same reviewed change."; `docs/specs/v3/layer2_registries_spec.md:394` — "For each `Person` with `household_role="resident"` whose HA person has at least one device tracker, one Sensor `presence.evidence.person.<ha_person_id>` at casa reads the HA person's state with the same mapping."
- **Owner:** Layer 3 §4.2 — it owns the list and commits to add every new person-related fact type; CA4-120 added `presence.evidence.person.*` without it joining the list.
- **Defect:** A learner instance whose feature binds `presence.evidence.person.<id>` (a per-person fact, the input of `presence.household`) is classified **physical**, so it is not censored with `censored_by_household_context` during guest stays or occupied-without-residents periods, while the same learner binding `presence.household` would be.
- **Proposed direction:** Add `presence.evidence.*` to the core person-related list (or state the namespace rule that covers it).
- **Confidence:** high
- **Verification:** pending

### F-L3a-03 — Promotion/disablement called "generation transitions" contrary to Layer 0 §4.7

- **Category / severity:** C / P2
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:1844` — "Promotion, continued shadowing, rollback and disablement are explicit administrative generation transitions."; `docs/specs/v3/layer0_runtime_spec.md:1590` — "Runtime authority transitions (promotion, consent, disablement) and artifact-adoption transitions are not configuration mutations and do not use this path."; `docs/specs/v3/layer3_learning_spec.md:2666` — "Promotion is the existing authenticated artifact-adoption decision of its consumer (Layer 5 §4.1–4.2 for a Reaction, §4.9 for a live signal), never a configuration-generation change (Layer 0 §4.7)."
- **Owner:** Layer 3 §4.7 — Layer 0 §4.7 and Layer 3 §4.8.6/§4.9 (adoption transition chain, l.2763–2783) agree that promotion is not a generation change.
- **Defect:** Read with Layer 3's own contrast at l.1845–1848 ("Entry to or exit from `bounded_adaptive` instead appends an authenticated adoption-mode transition … without changing the analysis definition or a configured Reaction generation"), §4.7 says promotion and disablement do create a generation transition, i.e. use the composed-generation path that Layer 0 §4.7 and §4.8.6 exclude for them.
- **Proposed direction:** Reword §4.7 to call promotion/rollback/disablement authenticated administrative (adoption/authority) transitions, not generation transitions.
- **Confidence:** medium
- **Verification:** pending

### F-L3a-04 — `environmental_response.v1` cells cited to §4.8.2, which defines input bindings

- **Category / severity:** R / P3
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:1895` — "The six non-HVAC Initial-V3 profiles use the common `environmental_response.v1` schema for the bounded response-artifact cells defined in §4.8.2"; `docs/specs/v3/layer5_action_reactions_spec.md:196` — "use the registered `environmental_response.v1` output shape for bounded response-artifact cells in Layer 3 §4.8.2."; `docs/specs/v3/layer3_learning_spec.md:2354` — "#### 4.8.2 Environmental input bindings" (no cell content in l.2354–2430); the cell content is at `docs/specs/v3/layer3_learning_spec.md:2102` — "For each supported class/context cell and declared outcome horizon the artifact persists the bounded empirical response distributions, their declared descriptive quantiles, support of both cohorts, uncertainty interval, and coverage/eligibility status."
- **Owner:** Layer 3 §4.8 (and the matching Layer 5 §3.1 citation) — the reference target is wrong.
- **Defect:** A reader following §4.8.2 finds slot/binding rules only; the cell fields (quantiles, support, delta, bootstrap interval, `transition_class_id`) are specified in the §4.8 body (l.2102–2147) and §4.8.1 (l.2294–2305).
- **Proposed direction:** Point both citations to §4.8 (StratifiedResponseModel cells) and §4.8.1 for `transition_class_id`.
- **Confidence:** high
- **Verification:** pending

### F-L3a-05 — Envelope abstention code spelled `out_of_operating_envelope` vs closed `outside_operating_envelope`

- **Category / severity:** D / P3
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:2620` — "A context outside any such bound, vocabulary, or supported partition is `out_of_operating_envelope` and produces no response estimate or candidate."; `docs/specs/v3/layer3_learning_spec.md:1531` — "continuous value outside the recorded finite operating envelope is `outside_operating_envelope`"; `docs/specs/v3/layer3_learning_spec.md:3444` — "AutomationSuppressionReason = Literal[ \"outside_operating_envelope\", …"; `docs/specs/v3/layer5_action_reactions_spec.md:849` — "`outside_operating_envelope`, `artifact_stale`, `artifact_incompatible`, … remain pre-admission evaluation/evidence causes"
- **Owner:** Layer 3 §4.8.6 — the other three places use the closed vocabulary value.
- **Defect:** The `EnvironmentalQuantileResponseModel` "coded abstention reason" (l.2642) uses an identifier absent from the closed `AutomationSuppressionReason` and from §4.4.4/Layer 5, so the same envelope abstention has two codes.
- **Proposed direction:** Use `outside_operating_envelope` in §4.8.6.
- **Confidence:** high
- **Verification:** pending

### F-L3a-06 — Categorical tie state named `ambiguous_top_outcome` vs coded `ambiguous_top`

- **Category / severity:** D / P3
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:728` — "Equal highest-support outcomes produce the explicit diagnostic state `ambiguous_top_outcome`"; `docs/specs/v3/layer3_learning_spec.md:711` — "one ordered attempt per declared tier with exactly one coded outcome: `missing_dimension`, `noncanonical_dimension`, `bucket_absent`, `retention_incomplete`, `insufficient_support`, `ambiguous_top`, `below_confidence`, or `selected`"; `docs/specs/v3/layer3_learning_spec.md:842` — "selection: Literal[\"unique_top\", \"ambiguous_top\"]"
- **Owner:** Layer 3 §4.3 — `ambiguous_top_outcome` appears nowhere else in the specification set.
- **Defect:** The "explicit diagnostic state" is named with an identifier that is not a member of either closed vocabulary that records the tie (`TierSelectionTrace` code, `CategoricalResult.selection`).
- **Proposed direction:** Rename it to `ambiguous_top` (or name the trace code explicitly).
- **Confidence:** medium
- **Verification:** pending

### F-L3a-07 — `ReactionArtifactAdoptionProposal` cited as bare "§4.1" inside Layer 3

- **Category / severity:** R / P3
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:2826` — "Layer 5 validates that target and persists a revision-specific `ReactionArtifactAdoptionProposal` (§4.1)"; `docs/specs/v3/layer3_learning_spec.md:82` — "### 4.1 `LearningDefinition` and family governance"; `docs/specs/v3/layer5_action_reactions_spec.md:1204` — "class ReactionArtifactAdoptionProposal:" (Layer 5 §4.1)
- **Owner:** Layer 3 §4.9 — Layer 3 elsewhere prefixes cross-layer citations ("Layer 5 §4.1", l.169, l.177).
- **Defect:** Within Layer 3, "§4.1" resolves to `LearningDefinition`, which does not define the proposal.
- **Proposed direction:** Write "Layer 5 §4.1".
- **Confidence:** medium
- **Verification:** pending

### F-L3a-08 — Radiation slots resolve at `casa`, but `incident_solar_exposure` is produced at the opening's room

- **Category / severity:** C / P2
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:2376` — "`room_*` slots resolve at the subject room, while outdoor/radiation slots resolve at `casa`."; `docs/specs/v3/layer3_learning_spec.md:2370` — "`room_illuminance`, `solar_irradiance`, `incident_solar_exposure`, `outdoor_air_quality`,"; `docs/specs/v3/layer2_registries_spec.md:1985` — "`environment.solar_incidence.v1` at the subject opening's owner room;"; `docs/specs/v3/layer2_registries_spec.md:1633` — "The second additionally requires typed direct-normal and diffuse irradiance inputs and produces W/m² `environment.incident_solar_exposure.<solar_binding_id>`."
- **Owner:** Layer 3 §4.8.2 — Layer 2's destination rule is explicit; Layer 3 §4.8 itself calls it "per-opening incident solar exposure" (l.1927).
- **Defect:** If `incident_solar_exposure` (W/m² per-opening irradiance) is a "radiation slot", staging resolves it at `casa`, where no producer exists (Layer 2 places it at the opening's owner room), so `solar_shading` could never bind its required observation. "Radiation slot" is not defined, so the intended scope is not determinable from the text.
- **Proposed direction:** State per slot which resolve at `casa` (outdoor and global radiation) and that `incident_solar_exposure` resolves at the opening owner's room, like opening/cover slots.
- **Confidence:** low
- **Verification:** pending

## Observations (no severity)

- §4.6 (l.1777) says an extension analyzer "may emit diagnostics", while Layer 7 §6 states "An
  extension never emits a `DiagnosticFinding`"; compatible only if "diagnostics" means Layer-0
  diagnostic events. Wording could be tightened.
- The `ThermalTopology` KPI paragraph (l.1714–1718) sits inside §4.4.7 (context hypotheses), unrelated
  to that section.
- With no tracked resident, `presence.household` and thus `occupied_without_residents` are always
  unavailable (Layer 2 §2.8.1, Layer 4 §9.2), so rule 1 of household-context censoring (l.353) censors
  every behavior sample in such a home; a design consequence, not a contradiction.
