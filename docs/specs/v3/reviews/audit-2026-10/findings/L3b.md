# L3b — `layer3_learning_spec.md` §5 to end

## Coverage

Read `layer3_learning_spec.md` lines 2855–4774 at baseline: §5.1 (refresh scheduling, training
watermark, `TrainingSpan`, single-flight/no-catch-up, global queue), §5.2 (run lifecycle), §5.3,
§5.3.1, §5.3.2 (resource governance, slow-path classes, baseline/calibration constants), §6.1,
§6.1.1, §6.1.2 (live signal, `DiagnosticFinding`, `ShadowProposalPreview`), §6.2, §6.3 including
`indirect.semantic_assist.v1`, §6.3.1 (availability suppression), §6.4, §6.4.1, §6.5, §6.6, §7, §8,
§9 and the related-documents note. Also read the sections they explicitly cite where needed to check
a reference or obligation: Layer 3 §4.1.1, §4.4.1 (return-delay paragraph), §4.4.3 (member
projection), §4.7 (shadow lifecycle), §4.9 (adoption table); Layer 0 §3.1 (`AtJob` fields), §3.5,
§4.5, §4.7 (authority transitions are not configuration mutations), §9 (`RuntimeHealthSnapshot`);
Layer 1 §3.1, §7 (`opening_faces_exterior`); Layer 2 §2.9, §3.6; Layer 5 §3 (wire encodings),
§3.1 (relation profiles), §3.2 (`advisory_intents`, member delivery, action-intent translation),
§4.1 (`ProposalSupportingArtifact`, evidence source), §4.2 (`ReactionTimingModelBinding`), §6.0
(`ProposalReviewOccurrence`), §7 (routine and solar dwell); Layer 6 §9.2 (`BindingEnablementChange`);
Layer 7 §3 blueprint fields, §5, §7.2, §8, §11.

Checked and found clean: every cross-layer section reference above resolves to the cited content;
the four CA4-130 constants and their Layer-7 counterparts (`max_result_age >= cadence +
CALIBRATION_WINDOW`, 60-second minimum interval) agree; §5.3.1/§5.3.2 agree with the CA4-130
acceptance bullet; the four indirect-assistance contracts are listed identically in §6.1, §6.3 and §9;
the 5 + 7 split of `AutomationSuppressionReason` matches its prose; the candidate deduplication
fingerprint restated in §6.4 and §6.6 matches; the §6.3 signal timing/expiry rule matches its §9
bullet; the §6.5 envelope rules match their §9 bullets; the `DiagnosticFinding` schema names match
§4.4.2, §4.4.4 and §4.8.7; the Layer-7 analyzer read path matches Layer 7 §5. No invariant violation
was found in the sections read.

## Findings

### F-L3b-01 — `ContextHypothesisCandidate` cited at §6.4, defined in §6.3

- **Category / severity:** R / P3
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:4224-4225` — "The future
  `ContextHypothesisCandidate` remains unpublishable until a closed uncertainty schema is registered
  (§6.4)."; `docs/specs/v3/layer3_learning_spec.md:3363` — "### 6.3 Typed egress contracts" and
  `:3635-3636` — "`ContextHypothesisCandidate` is the separate non-action-bearing diagnostic hand-off
  described in §4.4.7. It has no V3 instance; its future closed payload is:"; `:3671` — "### 6.4
  ReactionDescriptorCandidate"
- **Owner:** Layer 3 §9, whose reference is wrong.
- **Defect:** the uncertainty-schema rule (`:3655-3657`) and the candidate are in §6.3; §6.4 covers
  only `ReactionDescriptorCandidate`.
- **Proposed direction:** cite §6.3 (and §4.4.7) instead of §6.4.
- **Confidence:** high
- **Verification:** pending

### F-L3b-02 — Initial member-intent list omits the routine descriptor's `light_state`

- **Category / severity:** D / P2
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:3720-3722` — "Initial intents are
  `increase_shading`, `decrease_shading`, `open_for_exchange`, `close_to_retain`,
  `activate_extraction`, `adjust_extraction`, `stop_extraction` and `follow_comfort_trajectory`.";
  `docs/specs/v3/layer5_action_reactions_spec.md:3537-3539` — "trigger
  `state_transition(projector.power@living, off -> on)`, three `light_state` members setting three
  living-room lights to low brightness"; `layer5_action_reactions_spec.md:2964-2968` — "The core
  translation table is indexed by `(action_intent, channel_kind, actuation_adapter_id)`. ... For
  example, `light_state` may target power, normalized brightness, ..."
- **Owner:** Layer 3 §6.4, which restates the Layer-5 `ReactionDescriptorRegistry` intent set
  incompletely; Layer 5 owns the registry.
- **Defect:** a learned `routine.actuation_bundle` candidate from `ActuationRoutinePatternModel-v1`
  (which §6.4 and §4.4.3 say emits `ReactionDescriptorCandidate` members) carries intents such as
  `light_state`; under the Layer-3 list it is not an initial intent, so a Layer-3 shape check written
  from §6.4 rejects a valid Layer-5 candidate.
- **Proposed direction:** replace the enumeration with a reference to the Layer-5 registry, or
  complete it with the routine/presence-simulation intents.
- **Confidence:** high
- **Verification:** pending

### F-L3b-03 — `RoomOccupancySurvivalModel` declares no `shadow_requirement`

- **Category / severity:** O / P1
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:4636-4638` — "Every reviewed learning
  type/version or relation profile declares exactly one closed `shadow_requirement`; staging rejects a
  missing/unknown value"; `:1813-1814` — "Passing offline validation makes an artifact eligible only
  for the next state permitted by its frozen core `shadow_requirement`"; `:1045-1052` (§4.4.1) —
  "`return_delay` may also publish a validated, reviewable action-serving artifact for the exact
  registered Layer-5 `routine.actuation_bundle` vacancy-delay path. ... The existing Layer-3
  validation/shadow and CA4-14 adoption lifecycle governs this artifact"
- **Owner:** Layer 3 §4.4.1, which must declare the value as the other initial types do (§4.4.2
  `:1196`, §4.4.3 `:1477`, §4.4.4 `:1553`, §4.4.5 `:1590`, §4.8 `:1915`).
- **Defect:** §4.4.1 names no `shadow_requirement` value for the type or for its `return_delay`
  action-serving path, and no Layer-5 relation profile for that path declares one (Layer 5 registers
  `shadow_requirement` only on `RelationEvidenceFacet`, set for `routine_actuation_bundle`). Under §9
  staging must reject the type; under §4.7 its next lifecycle state after validation is undefined, so
  the Initial-V3 vacancy-delay timing evidence (§9 `:4490-4495`) cannot be staged or promoted
  consistently.
- **Proposed direction:** declare the closed `shadow_requirement` of `RoomOccupancySurvivalModel`
  (and, if different, of its `return_delay` action-serving output) in §4.4.1.
- **Confidence:** medium
- **Verification:** pending

### F-L3b-04 — Adoption-producing type has no `ShadowPreviewBinding`, yet every proposal producer must have one

- **Category / severity:** C / P2
- **Locations:** `docs/specs/v3/layer3_learning_spec.md:4360` — "Every proposal-producing core
  type/version has one frozen `ShadowPreviewBinding`."; `:4368-4371` — "The initial bindings are
  exactly `environmental_episode` version `1` to ... and `actuation_routine_pattern` version `1` to
  ..., both through `reaction.descriptor` candidate version `1`."; `:3299` — "The initial frozen
  registry contains the following concrete bindings."; `:2821-2826` (§4.9) — "For an existing
  action-bearing Reaction, an eligible first artifact, or an eligible new revision while the role is in
  `pinned` mode, yields a `LearningProposalCandidate` with the closed
  `("reaction.artifact_adoption", 1)` kind"; `:1045-1052` — "`return_delay` may also publish a
  validated, reviewable action-serving artifact ... The existing Layer-3 validation/shadow and CA4-14
  adoption lifecycle governs this artifact"
- **Owner:** Layer 3 §6.1.2 (binding registry) together with §9; one of them must change.
- **Defect:** `RoomOccupancySurvivalModel` (`return_delay`) produces `LearningProposalCandidate`s of
  kind `reaction.artifact_adoption` for a Reaction's timing role, so it is a proposal-producing core
  type; the "exactly" two initial bindings exclude it and cover only `reaction.descriptor`. Either the
  §9 rule rejects that type at staging or the type has no shadow-preview path, contrary to §4.7
  (`:1835-1837`, "for a proposal family, a `ShadowProposalPreview`").
- **Proposed direction:** restrict the §9 rule to `reaction.descriptor` producers, or register a
  binding (or an explicit no-preview rule) for `reaction.artifact_adoption` producers.
- **Confidence:** medium
- **Verification:** pending

## Observations

- §5.3.1 says "An admitted learning run is never killed; it is only paused at its cooperative
  boundary" (`:3144`) and, two bullets later, that the runtime "stops a run that exceeds [its
  envelope]; the run is discarded as failed" (`:3152-3154`). Read together with §5.3 (`:3068-3069`,
  "completes or stops only at the ordinary cooperative checkpoint/budget boundary") these are
  compatible (stop at a boundary is not a kill), but the wording invites misreading.
- §5.3 says an incident "immediately closes new admission" (`:3044-3045`), while the §9 bullet says
  health failure "blocks new admission at the next boundary" (`:4621`). Likely the same rule phrased
  from the scheduler's view; not classified as drift.
- §6.3.1 cites "Layer 0's unified notification outbox (§4.5)" (`:3537-3538`); the bare §4.5 resolves
  correctly only through the preceding "Layer 0's".
