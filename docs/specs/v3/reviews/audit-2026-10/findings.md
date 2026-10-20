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
| F-L0-06 | L0 | D | P3 | Hold-audit restatements require durable acknowledgement before the watermark advances, while §4.4/§4.6 also accept a declared overflow loss | confirmed |
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
| F-X1-01 | X1 | C | P2 | Recovery-target snapshots and outbox records are declared `PersistedProjection`s but cannot satisfy its depth and no-dataclass rule | pending |
| F-X1-02 | X1 | C | P2 | A calendar Sensor reads Layer 0's `active_now` directly, which Layer 0 neither registers nor permits | pending |
| F-X1-03 | X1 | O | P2 | Layer 2 hands Layer 0 an "entity delta" that deletes recovery snapshots; Layer 0 §7.4 has no such input or rule | pending |
| F-X1-04 | X1 | R | P3 | Producer diagnostics are routed to "Layer 0 §10", which defines no producer diagnostic event | pending |
| F-X1-05 | X1 | D | P3 | Layer 1 restates when `actuator.channel_state.*` changes more narrowly than Layer 0 | pending |
| F-X1-06 | X1 | D | P3 | `FactSource.source_id` example "an entity id" conflicts with Layer 2's Sensor `source_id` | pending |
| F-X2-01 | X2 | C | P2 | Recovery classification is promised to every semantic resolver, but no Layer-4 input carries it | pending |
| F-X2-02 | X2 | O | P2 | Live Layer-3 feature evaluation needs a frozen buffer read that Layer 0 offers only to Layer 5 | pending |
| F-X2-03 | X2 | O | P2 | `InferenceSignal` must carry the cycle `correlation_id`, but its closed payload has no such field | pending |
| F-X2-04 | X2 | O | P2 | Layer 3's CPU-credit planner needs process CPU measurements that `RuntimeHealthSnapshot` does not contain | pending |
| F-X2-05 | X2 | C | P3 | `FactSourceKind="analyzer"` names the Layer-3 `PatternLearner` as a fact producer, which Layer 3 excludes | pending |
| F-X2-06 | X2 | R | P3 | `LearnedPattern` is cited as a Layer-3 output but Layer 3 defines no such type | pending |
| F-X2-07 | X2 | R | P3 | Retention rationale cites a learner `history_window` that Layer 3 does not define | pending |
| F-X2-08 | X2 | D | P3 | §13 criterion expects a departure from a `present` → `away` presence, which no Layer-4 adapter emits | pending |
| F-X2-09 | X2 | D | P3 | A missing predecessor is `available=False` in Layer 0 but `previous=None` in Layer 4 | pending |
| F-X2-10 | X2 | D | P3 | `LearnedWindow` calibration is assigned to a `SemanticResolver`, which cannot read history | pending |
| F-X2-11 | X2 | C | P3 | Changing the learning installation profile is a configuration mutation outside the composed generation | pending |
| F-X3-01 | X3 | O | P2 | Layer 5 classifies a timing-model binding as breaking, but Layer 0's dependency index has no Layer-3 learning-definition producer or Layer-5 timing-model consumer | pending |
| F-X3-02 | X3 | O | P2 | Layer 0 says Layer 5 supplies the recovery-confirmation proposal, subject and proposed facets; Layer 5's body defines no such hand-off | pending |
| F-X3-03 | X3 | O | P3 | `ResponseRequestDeclaration.expires_at` is mandatory, but Layer 5's consent and feedback requests have no expiry instant | pending |
| F-X3-04 | X3 | O | P3 | Layer 0 says a Layer-5 calendar consumer declares a `KeywordClassifier`; Layer 5 has no such binding and routes calendar meaning through Layer 2 | pending |
| F-X3-05 | X3 | D | P3 | Layer 0 §4.7 lists the Layer-6 generation without house endpoints, which Layer 6 adds with no dependents | pending |
| F-X3-06 | X3 | R | P3 | Layer 6 builds on a "Layer-0 Runtime Scheduler" that Layer 0 does not define | pending |
| F-X4-01 | X4 | D | P3 | Layer 1 limits the registry-id-suffixed evidence shape to room occupancy; Layer 2 also uses it at casa and for presence, with an HA person id suffix | pending |
| F-X4-02 | X4 | C | P3 | Layer 1 says unavailability is recorded at once and an all-unavailable fusion is unavailable; Layer 2's `unavailable_grace` keeps the last available output | pending |
| F-X4-03 | X4 | D | P3 | Layer 1 puts `opening_id` on an Actuator channel; Layer 2 defines it on the Actuator only | pending |
| F-X5-01 | X5 | C | P2 | `opening.open` is reserved to Layer-5 readers, so a window contact cannot also feed Layer-3 opening evidence | pending |
| F-X5-02 | X5 | C | P2 | `occupancy.physical` is "the sole" ground truth a learner may bind, but the survival model binds resolved Layer-4 occupancy | pending |
| F-X5-03 | X5 | C | P2 | Layer 3 resolves learner bindings against the active Layer-2 generation, not the candidate | pending |
| F-X5-04 | X5 | O | P3 | Layer 2 says Layer 3 binds a `FutureStateFractionOutcome` for solar shading; Layer 3 registers none | pending |
| F-X5-05 | X5 | R | P3 | Layer 2 §5.3 quotes a Layer-3 sentence and `PatternLearnerConfig` that Layer 3 does not contain | pending |
| F-X5-06 | X5 | D | P3 | An impacted producer's predecessor is `available=False` in Layer 2 but `previous=None` in Layer 4 | pending |
| F-X6-01 | X6 | C | P2 | Learned-timing binding must match a `FutureStateFractionOutcome`, but the routine's only timing path is a survival model that Layer 5 forbids coercing to one | pending |
| F-X7-01 | X7 | C | P2 | The "automatic authorization requires an enabled user-visible binding" check is placed at publication staging, where no binding can be enabled | pending |
| F-X7-02 | X7 | D | P3 | U4 says `HouseholdConsentAuthority` references are HA user ids; Layer 5 and Layer 6 §5.2 make them `ha_person_id`s | pending |
| F-X7-03 | X7 | C | P3 | Layer 6 acceptance tests an action notice of an `environment.*` Reaction, which Layer 5 forbids | pending |
| F-X8-01 | X8 | C | P2 | Layer 0 says Layer-2 registrations contribute only `state` claims, but the Layer-2 extension producer may declare event claims | pending |
| F-X8-02 | X8 | D | P2 | Extension `configuration_fingerprint` is "of the active generation", while Layer 0 and Layer 2 make it a per-producer execution-semantic fingerprint no layer defines for extensions | pending |
| F-X8-03 | X8 | O | P2 | Extension history slots declare a read window, but Layer 0 extends durable retention only for registered learners | pending |
| F-X8-04 | X8 | C | P2 | "A due extension always fits" is contradicted by a slow-path memory budget smaller than the largest extension envelope | pending |
| F-X8-05 | X8 | O | P3 | The extension expiry `AtJob` declares no `basis`, which Layer 0 requires of every owner | pending |
| F-X8-06 | X8 | O | P3 | Layer 0's closed list of `correlation_id` origin points has no extension run | pending |
| F-X8-07 | X8 | O | P3 | Layer 5's commit-time `evidence_source_unavailable` rule names only learning instances, but Layer 7 requires the same commit for analyzer instances | pending |
| F-X8-08 | X8 | O | P2 | Layer 0 delegates breaking-consumer invalidation to Layer 2 §2.5, which defines none, while Layer 7 relies on it for Layer-2 consumers | pending |
| F-X9-01 | X9 | O | P1 | Layer-6 `HouseEndpoint`s are administrator-configured generation records, but Layer 8 has no editable kind for them | pending |
| F-X9-02 | X9 | O | P2 | Layer-3 artifact lifecycle transitions (shadow, `proposal_eligible`, rollback, disablement) have no Layer-8 command | pending |
| F-X9-03 | X9 | O | P2 | The map-card house banner has no owner hand-off: Layer 6 does not give Layer 8 the open `house` items | pending |
| F-X9-04 | X9 | C | P2 | Layer 8 gives a guest no role, but a guest who is an HA administrator is an administrator for Layer 0 and for Layer 8's own role rule | pending |
| F-X9-05 | X9 | C | P2 | Layer 5 says Layer 8 sends "only these" seven commands, but Layer 8 also submits rename, removal and restore of Reactions, including learner-origin ones | pending |
| F-X9-06 | X9 | O | P3 | Layer 6 places an "every recipient off" warning in Layer 8's Notifications section, which Layer 8 does not list | pending |
| F-X9-07 | X9 | O | P3 | Layer 2 has the panel suggest a Person's `ha_user_id`, a source missing from Layer 8's closed suggestion list | pending |
| F-O1-01 | O1 | D | P3 | Overview says Layer 6 produces seven event fact types; Layer 6 registers eight | pending |
| F-O1-02 | O1 | D | P3 | Overview lists one Initial-V3 candidate kind; Layer 5 registers two | pending |
| F-O1-03 | O1 | D | P3 | Overview gives guests and device accounts no panel access; Layer 8 gives them the map | pending |
| F-O1-04 | O1 | D | P3 | "Ending only on a household return" omits the family's other normal exits | pending |
| F-O1-05 | O1 | D | P3 | Presence simulation is said to use "calendar/presence guards"; its guard contract has only occupancy | pending |
| F-O1-06 | O1 | D | P3 | "Layer 3 reads only Layer-0 fact history and staged contracts" omits its other declared inputs | pending |
| F-O1-07 | O1 | D | P3 | "Global storage ceilings are hard", but the 512 MiB limit is a non-blocking watermark | pending |
| F-O2-01 | O2 | D | P3 | Recap lists seven Layer-6 kinds; Layer 6 §4.2 registers eight | pending |
| F-O2-02 | O2 | D | P3 | Recap authority statement omits Layer 7 | pending |
| F-O2-03 | O2 | D | P3 | Recap's initial semantic-claim list omits `occupied_without_residents` | pending |
| F-O2-04 | O2 | D | P3 | Recap provenance summary names a "resident response" kind and an extension-related `ApplyStepSource` | pending |
