# L5a — `layer5_action_reactions_spec.md` §1–§4

## Coverage

Read in full: Layer 5 header, §1, §2, §3 (including §3.1 relation profiles, §3.2 guard capabilities
and profiles, registered output and bundle contracts, occupied-without-residents, normal exit,
managed-episode resumption, admission-reason applicability, member delivery, program families), §4
preamble, §4.0 (diagnostic registry, governance command results, execution audit), §4.1 and §4.2
(including the common Layer-8 command surface). Read for cited cross-checks only: Layer 5 §6.0
resident advisory occurrence / on-site delivery / resident action notice (lines 2455–2520), the
`terminal_action_skipped` passage (2425–2445), §7.1 `ComfortTrajectoryGuardProfile` and §7.1.1,
§7.3 catalog matrix, §7.5; Layer 0 §4.6, §5.1, §6.1–§6.2 headers and the hold transition literal;
Layer 1 §7 (`opening_faces_exterior`); Layer 2 §2.8.1 (`Stability.to_true`), §6/§6.1
(`weather_exposed`, `hold_duration`); Layer 3 §4.1.2, §4.4.3, §4.8 (intro, §4.8.1, §4.8.2 headers
and content), §5.1–§5.2, §6.2, §6.3.1 (`AutomationSuppressionReason`, `ArtifactAdoptionCandidate`),
§6.4; Layer 4 §5.1, §9.2; Layer 6 §9.2; Layer 8 §6.4, §7, §10.2–§10.3.

Checked and found clean: candidate-kind and relation-profile wire encodings (§3, §3.1); guard
variant tables against `safe_direction_intents`/`low_risk_intents` declarations for solar shading,
external exchange, air extraction, weather protection and routine; the eight-descriptor consent
count and `when_occupied_without_residents` table against §7.5 and the program-family rules;
`planned_absence_program` rules against Layer 2 §2.8.1 and Layer 4 §9.2; `AutomationSuppressionReason`
rows and `fallback_served_without_artifact` against Layer 3 §6.3.1 (includes `artifact_stale`,
`artifact_incompatible`, `active_channel_unmanaged_after_restart`); §4.0 code sets against their uses
in §4.1/§4.2 (transition reasons, readiness codes incl. `evidence_source_unavailable`, governance
rejection codes, execution-audit `cause_ref` rule); proposal aggregate atomicity/append-only rules;
adoption-transition kinds against commands 2–3; authority-transition consent field against
`requires_household_consent`; catalog/display-name rules against Layer 2 §2.7; removal effects against
Layer 0/Layer 8 citations; `BindingEnablementChange` (Layer 6 §9.2) and the automation-state
projection (Layer 8 §10.3).

Line numbers are those of the working-tree files read in this pass (the pass did not run git, so
they were not re-verified against baseline `84f5263`).

## Findings

### F-L5a-01 — `safety.posture_check` has no guard contract although §3.2 requires one for every profile-free direct descriptor

- **Category / severity:** C / P2
- **Locations:** `layer5_action_reactions_spec.md:399-402` — "Every relation profile names one exact `ReactionGuardContractRef`. An `admin_direct` descriptor with no relation profile instead names one exact descriptor-level guard contract. In either case the frozen contract defines the capabilities the configuration may use and the subset required for each action variant. That subset is non-empty, except for a variant whose `action_intent` the descriptor declares in `safe_direction_intents` [...] or in `low_risk_intents`"; `layer5_action_reactions_spec.md:547-549` — "`direct_guard_contract` is required precisely when a descriptor permits an `admin_direct` configuration without a relation profile, and otherwise is absent."; `layer5_action_reactions_spec.md:4404` — "It is `admin_direct` only, casa-scoped, with no relation profile or learner"; `layer5_action_reactions_spec.md:4310` (§7.3 matrix row `safety.posture_check`) — "| none | trigger-driven, one activation per check instance |" in the Guard contract column.
- **Owner:** Layer 5 — either §7.5 must name a `direct_guard_contract` (and §3.2 list it with its variant table, declaring `check_alarm`, `lock_entry`, `close_opening` safe or low-risk with rationale), or §3.2 must state an exception for advice-only descriptors.
- **Defect:** `safety.posture_check` is a profile-free `admin_direct` descriptor, so §3.2 requires a non-null `direct_guard_contract` whose required set is non-empty for its variants unless they are declared safe-direction or low-risk; §7.3/§7.5 give it no contract and declare none of its intents safe or low-risk. Registration of this descriptor cannot satisfy both texts.
- **Proposed direction:** Register an explicit (possibly empty-permit) direct guard contract for `safety.posture_check` with a declared rationale, or add an advice-only exception to §3.2.
- **Confidence:** high
- **Verification:** pending

### F-L5a-02 — The guard contract of `hvac_thermal_response` / `environment.planned_comfort_trajectory` is never named, and its required set is administrator-supplied

- **Category / severity:** R / P2
- **Locations:** `layer5_action_reactions_spec.md:160-163` — "The policy facet [...] fixes which descriptor versions may use the relation, the runtime slots the plan may read, compatible objective/intent pairs, permitted versioned envelope axes and one exact guard contract."; `layer5_action_reactions_spec.md:399-402` — "Every relation profile names one exact `ReactionGuardContractRef`. [...] the frozen contract defines the capabilities the configuration may use and the subset required for each action variant."; `layer5_action_reactions_spec.md:421` — "a learner candidate may carry only that exact required set, never a threshold or a new capability"; `layer5_action_reactions_spec.md:3748-3750` — "`ComfortTrajectoryGuardProfile` is a separately staged, administrator-authored Layer-5 contract. It supplies [...] one exact environmental guard-profile generation and required site-specific guard capabilities"; `layer5_action_reactions_spec.md:3772` — "required_guard_capabilities: frozenset[ReactionGuardCapabilityRef]"; `layer5_action_reactions_spec.md:3796-3797` — "supply every required capability through the descriptor's exact guard contract"; `layer5_action_reactions_spec.md:4307` (§7.3) — Guard contract column "from its prerequisite generation (§7.1)".
- **Owner:** Layer 5 §3.2 — it enumerates the guard contracts of six Initial-V3 descriptors but not the one used by `hvac_thermal_response`.
- **Defect:** §3.2 requires the `hvac_thermal_response` relation profile to name one frozen `ReactionGuardContractRef` that fixes per-variant required capabilities; no such contract id, permitted set or variant table exists anywhere, and §7.1/§7.3 instead let an administrator-authored prerequisite generation carry `required_guard_capabilities`. The "descriptor's exact guard contract" that §7.1 validates against is a dangling reference.
- **Proposed direction:** Register and tabulate the comfort-trajectory guard contract in §3.2 and make the prerequisite's `required_guard_capabilities` a checked copy of it (or remove that field).
- **Confidence:** high
- **Verification:** pending

### F-L5a-03 — `stage_household_consent_authority` is classified as an immediate command but §7.1.1 requires it in a change set

- **Category / severity:** C / P2
- **Locations:** `layer5_action_reactions_spec.md:1801-1806` — "Command 1 and the descriptor-specific preparation inputs are configuration staging: Layer 8 submits them as edits of its session change set [...]. Commands 2 to 7 are immediate actions; only an accepting `review_proposal` also commits a composed generation"; `layer5_action_reactions_spec.md:1874-1876` — "7. `stage_household_consent_authority` changes the household's complete explicit resident-authority list [...] against its expected authority generation."; `layer5_action_reactions_spec.md:3971-3973` (§7.1.1) — "Removing or reclassifying a referenced Person is an authority removal: the same change set must carry the authority change with one disposition per current consent that person granted (§4.2 command 7), or it is rejected."
- **Owner:** Layer 5 §4.2 — the command classification must match the §7.1.1 change-set requirement (or §7.1.1 must change).
- **Defect:** Removing a Person (a Layer-2 change-set edit) requires command 7 to travel in that same change set, i.e. as configuration staging; §4.2 classifies command 7 as an immediate action that does not commit a composed generation. An implementation cannot both apply it immediately and reject the Person-removal change set when it is absent from that change set.
- **Proposed direction:** Classify command 7 with command 1 as change-set staging (or define how an immediate command 7 pairs with a later Person-removal change set).
- **Confidence:** medium
- **Verification:** pending

### F-L5a-04 — A "successor-generation path" for learner-origin configuration changes via proposal is cited but not defined

- **Category / severity:** R / P2
- **Locations:** `layer5_action_reactions_spec.md:1308-1310` — "It cannot contain a new action, descriptor parameter, guard, scope or consent request. If a change to any of those is needed, the ordinary configuration proposal and successor-generation path applies."; `layer5_action_reactions_spec.md:1709-1710` — "It applies to learner-origin Reactions too, whose configuration remains editable only through a new proposal."; `layer5_action_reactions_spec.md:1361-1363` — "stages a candidate composition that adds the resulting `ConfiguredReaction` (root and generation index `0`, in `notification_only` mode)"; `layer5_action_reactions_spec.md:1830` — "A learner-origin Reaction cannot be edited through this command"; `layer3_learning_spec.md:3607-3609` — "it persists a `ReactionProposal` for a new configuration or a `ReactionArtifactAdoptionProposal` for one existing Reaction role".
- **Owner:** Layer 5 §4.1/§4.2 — the only defined acceptance of a configuration proposal creates a new root at generation 0.
- **Defect:** For a learner-origin Reaction whose semantic configuration must change, §4.1 and §4.2 point to a proposal-driven successor-generation path, but proposal acceptance is defined only as creating a new `ConfiguredReaction` root; no rule appends a successor `ReactionConfigurationGeneration` to an existing Reaction from an accepted proposal (no target `reaction_id`, precondition or `configured_reaction_id` semantics for that case), and `stage_admin_direct_reaction` excludes learner-origin Reactions.
- **Proposed direction:** Either define proposal acceptance targeting an existing learner-origin Reaction as a successor generation, or reword both passages to say the change yields a new Reaction.
- **Confidence:** medium
- **Verification:** pending

### F-L5a-05 — Dangling internal reference to Layer 5 §6.2

- **Category / severity:** R / P3
- **Locations:** `layer5_action_reactions_spec.md:621-622` — "that command is skipped and reported by the existing terminal follow-up path (§6.2)."; Layer 5 section headings — "### 6.0 Shared hold and command-ownership admission" (2090), "### 6.0.1 Pending apply and physical observation" (3044), "### 6.1 Correction attribution evidence" (3143), then "## 7. Initial V3 descriptors" (3307).
- **Owner:** Layer 5 — the terminal follow-up path lives in §6.0 ("Hold release at a future Reaction step", 2425–2445; "Resident follow-up operational event", 2641).
- **Defect:** Layer 5 has no §6.2; the same stale citation also occurs at lines 2169, 2450, 5033, 5041 and 5069 (outside this unit's range).
- **Proposed direction:** Retarget the citations to the §6.0 subsections that define terminal follow-up.
- **Confidence:** high
- **Verification:** pending

### F-L5a-06 — `ArtifactAdoptionCandidate` cited in Layer 3 §6.2 but defined in §6.3.1

- **Category / severity:** R / P3
- **Locations:** `layer5_action_reactions_spec.md:1115-1116` — "For the closed `(\"reaction.artifact_adoption\", 1)` kind, Layer 3 submits only the `ArtifactAdoptionCandidate` of Layer 3 §6.2"; `layer3_learning_spec.md:3615` — "class ArtifactAdoptionCandidate:" (inside "### 6.3.1 Observable automation abstention", 3433, before "### 6.4", 3671); Layer 3 §6.2 (3335–3362) does not mention it.
- **Owner:** Layer 5 (citation); Layer 3 may alternatively move the definition.
- **Defect:** The cited section does not define the type.
- **Proposed direction:** Cite the section that actually defines `ArtifactAdoptionCandidate`.
- **Confidence:** high
- **Verification:** pending

### F-L5a-07 — `environmental_response.v1` cells cited to Layer 3 §4.8.2, which defines input bindings

- **Category / severity:** R / P3
- **Locations:** `layer5_action_reactions_spec.md:195-197` — "use the registered `environmental_response.v1` output shape for bounded response-artifact cells in Layer 3 §4.8.2"; `layer5_action_reactions_spec.md:521-522` — "The environmental output preserves its numeric point estimate, conservative interval and positive horizon in the profile's outcome unit (Layer 3 §4.8.2)."; `layer3_learning_spec.md:2354-2357` — "#### 4.8.2 Environmental input bindings / `EnvironmentalEpisodeLearner` profiles read only complete Layer-1 `HouseFact` records through named, typed binding slots."; `layer3_learning_spec.md:4242` — "profiles use the shared response-artifact schema (§4.8; Layer 5 §3.1)".
- **Owner:** Layer 5 (citation); Layer 3 line 1896 repeats the same "defined in §4.8.2" wording.
- **Defect:** Layer 3 §4.8.2 contains no response cell, point estimate or conservative interval; the schema is described in §4.8's preamble (1893–2029) and the conservative contrast in §4.8.6.
- **Proposed direction:** Cite Layer 3 §4.8 (and §4.8.6 for the conservative bounds).
- **Confidence:** medium
- **Verification:** pending

### F-L5a-08 — Admitted run context cited to Layer 3 §5.1 (refresh scheduling)

- **Category / severity:** R / P3
- **Locations:** `layer5_action_reactions_spec.md:1342-1343` — "The core runtime assigns all three fields from the admitted run context (the learning instance and serving generation under which the run was admitted, Layer 3 §5.1)"; `layer3_learning_spec.md:2857` — "### 5.1 Evidence-driven refresh scheduling"; `layer3_learning_spec.md:2946` (§5.2 Run lifecycle) — "The inspection captures the active generation and learner definition fingerprint"; `layer3_learning_spec.md:186` (§4.1.2) — "`serving_generation_fingerprint` covers the active".
- **Owner:** Layer 5 (citation).
- **Defect:** Layer 3 §5.1 defines inspection intervals and training windows, not run admission or the captured serving generation; those are in §5.2 and §4.1.2.
- **Proposed direction:** Cite Layer 3 §5.2 / §4.1.2.
- **Confidence:** medium
- **Verification:** pending

### F-L5a-09 — Hold invalidation reason `authority_revoked` cited to Layer 0 §6.2 instead of §6.1

- **Category / severity:** R / P3
- **Locations:** `layer5_action_reactions_spec.md:1751` — "a hold it owns is invalidated with `authority_revoked` (Layer 0 §6.2)"; `layer0_runtime_spec.md:2212-2213` (§6.1 Identity, origin, and lifecycle) — "invalidation_reason: Literal[\"observation_lost\", \"configuration_changed\", \"authority_revoked\", ..."; Layer 0 §6.2 "Detection and release" (2324–2426) does not contain `authority_revoked`.
- **Owner:** Layer 5 (citation).
- **Defect:** The cited section does not define or use the invalidation reason.
- **Proposed direction:** Cite Layer 0 §6.1.
- **Confidence:** medium
- **Verification:** pending

### F-L5a-10 — "User-visible output remains exclusively" follow-up and availability occurrences, contradicting advisory and notice occurrences

- **Category / severity:** C / P3
- **Locations:** `layer5_action_reactions_spec.md:1099-1101` — "These records feed Layer-5 audit and the read-only shadow view only; user-visible output remains exclusively `ReactionFollowUpOccurrence` and `AvailabilitySuppressionOccurrence` through Layer 6."; `layer5_action_reactions_spec.md:857-859` — "`advice` produces a user-facing suggestion instead, through Layer 6"; `layer5_action_reactions_spec.md:2462-2464` — "An eligible advice member (§3.2) gives Layer 6 one typed occurrence; Layer 6 alone appends the `reaction.advisory` event fact [...] and delivers it."; `layer5_action_reactions_spec.md:2515-2516` — "A descriptor version with `resident_action_notice=True` tells residents what it did."
- **Owner:** Layer 5 §4.0 — the sentence predates advisory, action-notice, consent-request and proposal-review occurrences.
- **Defect:** Layer 5 hands Layer 6 user-visible `ReactionAdvisoryOccurrence`, resident action notices, consent requests and proposal-review notices; the "exclusively" statement is false for these.
- **Proposed direction:** Restate the sentence as "execution-audit records are never user-visible" without enumerating an exclusive set.
- **Confidence:** high
- **Verification:** pending

## Observations

- `routine.actuation_bundle` (393–397) says a member "requires the safety capabilities that an
  environmental descriptor requires for the same physical action", then lists only
  `opening_security`/`precipitation`/`wind`, omitting `thermal_bounds` (and `outdoor_air_quality`
  for air-quality exchange) that `environment.external_exchange` requires for `open_for_exchange`
  (lines 368–370, 389–397). Whether `thermal_bounds` counts as a "safety" capability is not
  stated; not recorded as a finding.
- `layer5_action_reactions_spec.md:1519` "Layer 4 transports the view opaquely (§5.1)" reads as a
  Layer 5 §5.1 citation; the transport is in Layer 4 §5.1 (lines 206, 247).
- `GovernanceCommandResult` (1032–1046): for a staging contribution, `applied` is said to carry "the
  identity of the record it appended" while `resulting_ref` "is set only once the change set
  commits"; the result shape at validation time is not stated.
