# Audit findings index

Maintained by the coordinator. Each pass's full findings are in `findings/<unit>.md`; ids are
`F-<unit>-<nn>` and never reused. Verification: `pending`, `confirmed`, `false positive (reason)`,
`approved decision (backlog reference)`.

| Id | Unit | Category | Severity | Title | Verification |
|---|---|---|---|---|---|
| F-L0-01 | L0 | C | P1 | `previous_cycle` snapshot "never seeded from durable history" contradicts clean-restart pre-hydration | pending |
| F-L0-02 | L0 | C | P2 | "Every class creates a hold" contradicts the hold qualification rule | pending |
| F-L0-03 | L0 | R | P2 | `system.health` notification event fact has no reserved claim or owner | pending |
| F-L0-04 | L0 | C | P2 | Layer 0 is said to read nothing above it, yet derives `household_role` from the Layer-2 Person registry | pending |
| F-L0-05 | L0 | D | P3 | §13 checkpoint criterion says "last-write-wins per entity", while §7.4 merges per facet per channel | pending |
| F-L0-06 | L0 | D | P3 | Hold-audit restatements require durable acknowledgement before the watermark advances, while §4.4/§4.6 also accept a declared overflow loss | pending |
| F-L0-07 | L0 | R | P3 | `route_fingerprint` cites Layer 2 §5.2, but the route is defined in Layer 2 §7 | pending |
| F-L1-01 | L1 | D | P3 | `UnanimityStrategy.min_available` cited with a default of 1 that Layer 2 forbids | pending |
| F-L1-02 | L1 | R | P3 | `importance` (`OBSERVE`/`SUGGEST`/`ASSERT`) on `InferenceSignal` is defined nowhere | pending |
| F-L1-03 | L1 | R | P3 | `PatternLearnerConfig.target_shape` cited as a Layer-3 construct that Layer 3 does not define | pending |
| F-L1-04 | L1 | D | P3 | §8 attributes analysis-run correlation ids to "learned facts", which Layer 0 and Layer 3 do not produce | pending |
| F-L1-05 | L1 | R | P3 | Self-reference "under §4.5" points to a section Layer 1 does not have | pending |
| F-L1-06 | L1 | R | P3 | "(§4 intro)" cited for a statement that is not in the §4 introduction | pending |
| F-L2-01 | L2 | C | P2 | Core-generated `presence.household` FusionRule is invalid when no resident is tracked | pending |
| F-L2-02 | L2 | C | P2 | Two core-generated Sensors read the same HA person state, against "one readable signal path, one owner" | pending |
| F-L2-03 | L2 | C | P2 | Physical-evidence "recipe applies equally to presence", but its validator admits only `occupancy.physical` | pending |
| F-L2-04 | L2 | D | P3 | §5.6 rationale says FusionRules are "core-team-authored only (§2.1)"; §2.1 and the rest of Layer 2 make them administrator-configured | pending |
| F-L2-05 | L2 | D | P3 | §2.4 and §5.3 restate the "other formulas take `configuration=None`" rule differently | pending |
| F-L2-06 | L2 | R | P3 | `related_opening_id` staging rule cites §2.4, which contains no Sensor rule | pending |
| F-L2-07 | L2 | D | P3 | §7 describes `Stability` as "composed of two `Window`s"; §5.2 defines three Window fields | pending |
| F-L2-08 | L2 | D | P3 | The 14-day horizon "must exceed ceiling plus largest recovery", but Layer 5 allows the sum to equal 14 days | pending |
| F-L3a-01 | L3a | O | P1 | `RoomOccupancySurvivalModel` declares no `shadow_requirement` despite an action-serving egress | pending |
| F-L3a-02 | L3a | O | P2 | Person-related fact list omits Layer 2's `presence.evidence.person.<id>` | pending |
| F-L3a-03 | L3a | C | P2 | Promotion/disablement called "generation transitions" contrary to Layer 0 §4.7 | pending |
| F-L3a-04 | L3a | R | P3 | `environmental_response.v1` cells cited to §4.8.2, which defines input bindings | pending |
| F-L3a-05 | L3a | D | P3 | Envelope abstention code spelled `out_of_operating_envelope` vs closed `outside_operating_envelope` | pending |
| F-L3a-06 | L3a | D | P3 | Categorical tie state named `ambiguous_top_outcome` vs coded `ambiguous_top` | pending |
| F-L3a-07 | L3a | R | P3 | `ReactionArtifactAdoptionProposal` cited as bare "§4.1" inside Layer 3 | pending |
| F-L3a-08 | L3a | C | P2 | Radiation slots resolve at `casa`, but `incident_solar_exposure` is produced at the opening's room | pending |
| F-L3b-01 | L3b | R | P3 | `ContextHypothesisCandidate` cited at §6.4, defined in §6.3 | pending |
| F-L3b-02 | L3b | D | P2 | Initial member-intent list omits the routine descriptor's `light_state` | pending |
| F-L3b-03 | L3b | O | P1 | `RoomOccupancySurvivalModel` declares no `shadow_requirement` | pending |
| F-L3b-04 | L3b | C | P2 | Adoption-producing type has no `ShadowPreviewBinding`, yet every proposal producer must have one | pending |
| F-L4-01 | L4 | C | P2 | Activity profiles told to bind event/episode slots that `ActivityEvidenceSlot` rejects | pending |
| F-L4-02 | L4 | C | P3 | `occupied_without_residents` acceptance gives it a baseline it cannot have | pending |
| F-L4-03 | L4 | C | P2 | Evaluator lookup key omits the per-profile activity evaluator and version | pending |
| F-L5a-01 | L5a | C | P2 | `safety.posture_check` has no guard contract although §3.2 requires one for every profile-free direct descriptor | pending |
| F-L5a-02 | L5a | R | P2 | The guard contract of `hvac_thermal_response` / `environment.planned_comfort_trajectory` is never named, and its required set is administrator-supplied | pending |
| F-L5a-03 | L5a | C | P2 | `stage_household_consent_authority` is classified as an immediate command but §7.1.1 requires it in a change set | pending |
| F-L5a-04 | L5a | R | P2 | A "successor-generation path" for learner-origin configuration changes via proposal is cited but not defined | pending |
| F-L5a-05 | L5a | R | P3 | Dangling internal reference to Layer 5 §6.2 | pending |
| F-L5a-06 | L5a | R | P3 | `ArtifactAdoptionCandidate` cited in Layer 3 §6.2 but defined in §6.3.1 | pending |
| F-L5a-07 | L5a | R | P3 | `environmental_response.v1` cells cited to Layer 3 §4.8.2, which defines input bindings | pending |
| F-L5a-08 | L5a | R | P3 | Admitted run context cited to Layer 3 §5.1 (refresh scheduling) | pending |
| F-L5a-09 | L5a | R | P3 | Hold invalidation reason `authority_revoked` cited to Layer 0 §6.2 instead of §6.1 | pending |
| F-L5a-10 | L5a | C | P3 | "User-visible output remains exclusively" follow-up and availability occurrences, contradicting advisory and notice occurrences | pending |
| F-L5b-01 | L5b | C | P2 | Evaluation reason codes that no outcome may carry | pending |
| F-L5b-02 | L5b | C | P2 | Weather-protection example uses a `state_transition` trigger that cannot fire after restart | pending |
| F-L5b-03 | L5b | C | P2 | Posture-check advisories: `safety` family vs Layer 6 fixed `suggestion` family | pending |
| F-L5b-04 | L5b | D | P3 | §7 program-shape summary omits weather protection and posture check | pending |
| F-L5b-05 | L5b | D | P3 | Advice members restricted to two descriptors in §7.3 | pending |
| F-L5b-06 | L5b | D | P3 | Acceptance says only `eligible` reaches admissibility | pending |
| F-L5b-07 | L5b | R | P3 | References to a nonexistent Layer-5 §6.2 | pending |
| F-L5b-08 | L5b | R | P3 | Unqualified "§4.5" in the follow-up operation-id rule | pending |
| F-L5b-09 | L5b | O | P3 | Planned-absence horizon does not strictly exceed ceiling plus largest recovery | pending |
| F-L6-01 | L6 | C | P1 | `safety.posture_check` advisories are declared `safety` but `reaction.advisory` has the fixed family `suggestion` | pending |
| F-L6-02 | L6 | C | P2 | Per-proposal `closed` clearing contradicts the shared digest tag | pending |
| F-L6-03 | L6 | C | P2 | The "open request with buttons is never filtered or silenced" rule also covers advisories, emptying the `suggestion` preferences | pending |
| F-L6-04 | L6 | R | P2 | §4.3 maps `subject` and `occurred_at`, which `RuntimeHealthOccurrence` does not have | pending |
| F-L6-05 | L6 | O | P2 | `system.health` has no Layer-0 `FactTypeClaim` although the descriptor requires one | pending |
| F-L6-06 | L6 | R | P2 | Availability `episode_sequence` is attributed to Layer 3 §6.3.1, which defines no episode counter and limits tracker state | pending |
| F-L6-07 | L6 | C | P3 | §2's "reads from HA only configuration: language and `notify.*`" omits the unit system and live names used by rendering | pending |
| F-L6-08 | L6 | R | P3 | Publication-index revision number and `AvailabilityPublicationIndex` are cited but not defined by the owning layer | pending |
| F-L7-01 | L7 | R | P2 | Calendar input is promised to producers but has no blueprint field and no Layer-0 requirement path | pending |
| F-L7-02 | L7 | C | P2 | Calendar input would expose raw event text that Layer 0 restricts to the Layer-2 classifier | pending |
| F-L7-03 | L7 | C | P2 | `max_result_age >= cadence + CALIBRATION_WINDOW` does not guarantee that a forced window never expires a healthy fact | pending |
| F-L7-04 | L7 | C | P2 | Restart re-arms expiry from the last persisted result, but write-on-change persists only changes | pending |
| F-L7-05 | L7 | C | P2 | Input contract gives every bound key a "current committed value", but a slot may bind an event fact | pending |
| F-L7-06 | L7 | O | P2 | Extension analyzer evidence source needs a serving-generation fingerprint that only learners define | pending |
| F-L7-07 | L7 | D | P3 | Returned source field: whole-run rejection (§13) is absent from the §8 failure list and differs from Layer 0's sanitize rule | pending |
| F-L7-08 | L7 | O | P3 | Layer 0 §4.7 enumerations omit extension consumer references and extension code upgrades that Layer 7 relies on | pending |
| F-L8-01 | L8 | C | P1 | Consent-authority change is an immediate action, but Person removal requires it in the same change set | pending |
| F-L8-02 | L8 | C | P2 | `extension_requirement` suggestions are computed from the active generation, where an instance with a missing producer cannot exist | pending |
| F-L8-03 | L8 | D | P3 | Finding acknowledgement is called installation-wide; Layer 3 limits it to the acknowledging administrator | pending |
| F-L8-04 | L8 | D | P3 | History timeline includes Layer 3 adoption transitions; the `history/list` owner path omits them | pending |
| F-L8-05 | L8 | C | P3 | §7 defines what residents see in history, but history is administrator-only | pending |
| F-L8-06 | L8 | D | P3 | Up-direction change clears placements on every floor (§9.1, §9.4) or on one floor (§16) | pending |
| F-L8-07 | L8 | C | P2 | Redaction keeps Heima ids, but a Heima `recipient_id` is administrator-chosen and may be a person's name | pending |
