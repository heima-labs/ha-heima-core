# Verification — area D (L7, L8, X8, X9, O1, O2, mechanical candidates)

Verifier pass following the README "Verification protocol". Every quoted location was re-read in
the current working tree of `feat/v3-planning` (no specification file has been edited since the
baseline `84f5263`, per the README rule) and checked against `docs/v3_backlog.md` (in particular
CA4-127–132, the Layer 6 and Layer 8 approved decisions, and CA4-59/60).

## Findings

| Id | Verdict | Duplicate of | Severity | Note |
|---|---|---|---|---|
| F-L7-01 | confirmed |  | P2 | CA4-129 decision 4 approves the timeline snapshot as an input, but `ExtensionProducerRole` has no field to declare it and Layer 0 §3.4.1 admits `CalendarViewRequirement` only from Layer-5 plans and Layer-2 declared-context producers. Owner Layer 7: add a typed calendar requirement (and admit it in Layer 0) or drop the bullet. |
| F-L7-02 | confirmed |  | P2 | The approved input (CA4-129 d.4) concretely contradicts Layer 0's approved rule that raw `CalendarWindow.summary` reaches only the Layer-2 `KeywordClassifier` (L0:889-891). Owner Layer 7: expose classified/redacted windows if calendar input is kept. |
| F-L7-03 | confirmed |  | P2 | Bound approved in CA4-130 d.5, but its stated guarantee does not follow: fixed-delay start at cadence end, blocked by the window, plus run duration and barrier latency exceeds `cadence + CALIBRATION_WINDOW`. Owner Layer 7 (Layer 3 restates): add a margin for run deadline and scheduling delay, or weaken "never expires". |
| F-L7-04 | confirmed |  | P2 | CA4-130 d.5 approves "re-arms from the last persisted result", but write-on-change (L0:1016-1017) persists only changes and instance state is runtime-only, so no record carries the last successful run. Owner Layer 7: define a persisted last-success instant or base restart expiry on the restart instant. |
| F-L7-05 | confirmed |  | P2 | `ExtensionInputSlot.fact_type` admits any exact fact type; an event key has no current value (L0:598-599) and cannot be a committed-state subscription (L0:1682, 1692). Owner Layer 7: restrict slots to state facts or define event-slot semantics. |
| F-L7-06 | confirmed |  | P2 | `ProposalEvidenceSource.serving_generation_fingerprint` points to Layer 3 §4.1.2, which derives it only for `ResolvedLearningDefinition`; no layer defines it for an extension analyzer instance, so L5 readiness (b) has no input. Owner Layer 7: define the analyzer instance's serving fingerprint and what changes it. |
| F-L7-07 | confirmed |  | P3 | §13 rejects the whole run on a returned source field, §8's normative failure list omits it, and Layer 0 §5.1 describes sanitization. Owner Layer 7: add the case to §8 and align Layer 0 §5.1 wording. |
| F-L7-08 | confirmed |  | P3 | Layer 0 §4.7's consumer-reference enumeration and code-upgrade trigger list name no extension slot binding, analyzer learner binding or `implementation_version`. Owner Layer 0: add them to both enumerations. |
| F-X8-01 | confirmed |  | P2 | L0:629 "Layer 2 registrations contribute only `state` claims" predates the extension producer kind that Layer 2 §2.1 and Layer 7 §3/§4 stage in the Layer-2 generation with optional event claims. Owner Layer 0: limit the sentence to `Sensor`/`FusionRule` and admit extension claims of either kind. |
| F-X8-02 | confirmed |  | P2 | Layer 7 §6 says "`configuration_fingerprint` of the active generation"; L0:1733 and L2:248-249 make it a per-producer execution-semantic fingerprint, and no layer lists its fields for an extension producer. Owner Layer 7: define the extension producer's semantic fingerprint and its inputs. |
| F-X8-03 | confirmed |  | P2 | Layer 0 §4.3 accepts retention declarations only from learner registrations (L0:1089-1092); Layer 7 history slots register none, so windows above 14 days are truncated with no stated run outcome. Owner Layer 7 (with Layer 0 admitting the declarant): register slot retention needs and define behavior on incomplete coverage. |
| F-X8-04 | confirmed |  | P2 | Reservation subtracts the largest envelope from learning only; nothing makes `M_slow` cover it, so `rejected_resource_budget` (L3:2982-2983) remains possible against "a due extension always fits" (L3:3147, L7:218-219). Owner Layer 3: condition the guarantee or check the envelope at enablement. |
| F-X8-05 | confirmed |  | P3 | Layer 7 §8 arms an `AtJob` without a `basis`; L0:145 makes an unclassified job invalid, and Layer 2's analogous job states `wall_clock` (L2:772-773). Owner Layer 7: declare the basis. |
| F-X8-06 | confirmed |  | P3 | L0 §5.2's origin-point list (L0:2108-2124) has no off-cycle extension run, and Layer 7 §6 omits `correlation_id` from runtime-assigned fields. Owner Layer 0: add the extension run as an origin point or state inheritance from the applying cycle. |
| F-X8-07 | confirmed |  | P3 | L5 §4.1 readiness (a) covers any source instance, but the §4.2 commit obligation (L5:1728-1731) names only learning instances, while Layer 7 §6/§13 require the same commit for analyzers. Owner Layer 5: extend the §4.2 sentence to extension analyzer instances. |
| F-X8-08 | confirmed |  | P2 | Layer 2 §2.5 defines impact cutover actions but no invalidated state for a consumer whose binding breaks, and its validation rejects the whole candidate on failed binding validation (L2:230-231); Layer 7 §13 expects a committed "breaking" Fusion consumer. Owner Layer 2: define the breaking-consumer outcome in §2.5 or make Layer 7 removal require editing consumers first. |
| F-L8-01 | confirmed | F-L5a-03 | P2 | Same defect as F-L5a-03: L5 §7.1.1 / L2:2352-2353 require the authority change in the Person change set, while L5:1805 and L8 §6.1 make it an immediate action with no `layer5` change-set kind. Downgraded from P1: a two-step path (immediate authority change first, then the Person edit, which no longer references an authorized Person) exists, so the rule is unsatisfiable as worded but the capability is not blocked. Owner Layer 5 (with Layer 8 §6.1/§6.2/§13): choose one classification. |
| F-L8-02 | confirmed |  | P2 | `suggestions/list` is computed only over the active generation (L8:365-367, 962), but an instance with an unproduced slot key fails validation (L7:132-134) and never reaches it, so the CA4-131 suggestion cannot appear for creation. Owner Layer 8 §6.5: derive `extension_requirement` also from the change set's staging errors. |
| F-L8-03 | confirmed |  | P3 | L8:379-380 calls finding acknowledgement installation-wide; L3:3274-3276 limits it to "that administrator's presentation". Owner Layer 8 §6.5 (or Layer 3 §6.1.1): align the scope. |
| F-L8-04 | confirmed |  | P3 | §7 timeline includes Layer-3 signal-artifact adoption transitions (L8:395); the `history/list` owner path (L8:947) lists only Layer 0 records and Layer 5 transitions. Owner Layer 8 §13: add Layer 3 transitions. |
| F-L8-05 | confirmed |  | P3 | §7 specifies what a non-admin resident sees in history (L8:399-402), but System and `history/list` are admin-only (L8:128, 947). Owner Layer 8: drop the resident-viewer rule or name a resident history surface. |
| F-L8-06 | confirmed |  | P3 | §9.4 clears "the floor placements" because every opening changes side under an installation-wide up direction (L8:476, 563-565); §16 tests "that floor's placements" only (L8:1082-1083). Owner Layer 8: state all-floor clearing in §9.4 and §16. |
| F-L8-07 | confirmed |  | P2 | Redaction keeps Heima ids (L8:1000-1003), yet `recipient_id` is administrator-chosen with example "stefano" (L6:154), so a person's name survives in the diagnostics file. Owner Layer 8 §14.1: pseudonymize administrator-chosen ids that may carry personal data (or constrain them in Layer 6). |
| F-X9-01 | confirmed |  | P1 | `Layer6Generation.house_endpoints` (L6:572, 579) are administrator-chosen generation records required by CA4-124's `house` audience, but Layer 8's closed `layer6` kinds are `recipient`, `family_options` only (L8:298) and Layer 8 never mentions `HouseEndpoint`. Owner Layer 8 §6.2/§5: add a `house_endpoint` kind (Layer 0 §4.7's Layer-6 list overlaps F-X3-05). |
| F-X9-02 | confirmed |  | P2 | Layer 3 requires administrative transitions into `shadow`, to `proposal_eligible`, rollback and disablement (L3:1822, 1844-1845); Layer 8's catalog has only live-signal promotion/adoption commands (L8:957). Owner Layer 8 §5/§13: add the commands or change-set path once F-L3a-03 settles the classification. |
| F-X9-03 | confirmed |  | P2 | The map-card house banner (L8:782-786) needs open `house` items and their closing; the §10.3 projections (L8:859-863) take no Layer-6 `house` items, and Layer 6 states no hand-off to Layer 8 for them. Owner Layer 6 (hand-off) and Layer 8 §10.3 (projection). |
| F-X9-04 | confirmed |  | P2 | L8:76 makes any HA administrator an `administrator`, L8:82-83 gives a guest no role; Layer 0 reads configuration from the admin flag only (L0:1838-1840) and admits a guest admin as `admin` (L0:2086-2087). Owner Layer 8 §4: limit the no-role sentence to non-administrators. |
| F-X9-05 | confirmed |  | P2 | L5:1800-1801 says Layer 8 sends "only these" seven commands, while removal, rename and restore (L5:1745, 1757-1761) are separate staging contributions, and Layer 8's `reaction` kind (L8:297) omits restore of a learner-origin Reaction. Owner Layer 5 §4.2 (name catalog-entry edits) with Layer 8 §6.2 (list restore). |
| F-X9-06 | confirmed |  | P3 | Layer 6 places the "every recipient off" warning in Layer 8's Notifications section (L6:627-629); Layer 8's Notifications row (L8:127) lists no such warning. Owner Layer 8 §5: add it. |
| F-X9-07 | confirmed |  | P3 | Layer 2 has the panel suggest `ha_user_id` (L2:366-367); Layer 8 §6.5's closed source list and `SuggestionSource` have no Person source. Owner Layer 8 §6.5: add it as a source or as a stated form default. |
| F-O1-01 | confirmed |  | P3 | Overview counts seven Layer-6 event facts (overview:68, 492; cited as 490 at baseline, +2 lines in the working tree) while Layer 6 §4.2 registers eight including `system.health`, and the overview itself says eight (overview:557). Owner overview: count eight and add `RuntimeHealthOccurrence` to the 5/0 -> 6 row. |
| F-O1-02 | confirmed |  | P3 | Overview:377-378 lists only `("reaction.descriptor", 1)`; L5:77-78 registers `("reaction.artifact_adoption", 1)` too. Owner overview: list both. |
| F-O1-03 | confirmed |  | P3 | Overview:574 says "no access for guests and device accounts"; L8:83-86 gives every HA user the map in public text. Owner overview: say no role, map only. |
| F-O1-04 | confirmed |  | P3 | Overview:239 "ending only on a household return" vs Layer 5 rule 4 (L5:924-928) normal cancellation by plan removal and natural completion; Layer 5 rule 9 (L5:942) carries the same absolute wording. Owner overview, plus Layer 5 rule 9 qualification. |
| F-O1-05 | confirmed |  | P3 | Overview:546 "common calendar/presence guards"; the descriptor's guard contract permits only stabilized casa `occupancy` (L5:4105) and policies read no calendar (L5:1973). Owner overview: activation from the planned-absence family, sole guard occupancy. |
| F-O1-06 | confirmed |  | P3 | Overview:276 "reads only Layer-0 fact history and immutable staged contracts" omits the frozen intake and previous-cycle values (L3:3380) and the runtime-health snapshot (L3:2988). Owner overview: list those inputs. |
| F-O1-07 | confirmed |  | P3 | Overview:515-516 calls global storage ceilings "hard"; L0:1109-1111 defines 512 MiB as a non-blocking watermark (overview:90 agrees). Owner overview: call it a watermark. |
| F-O2-01 | confirmed | F-O1-01 | P3 | Same drift as F-O1-01 in the other orientation document: recap:663 "the seven closed kinds" and recap:674 "Three further typed occurrences complete the inputs" omit `system.health` (L6:107). Owner recap: eight kinds. |
| F-O2-02 | confirmed |  | P3 | Recap:9 names Layers 0–6 and 8 as authoritative; `contract_registry.json` lists Layer 7 among the nine authoritative layers. Owner recap: "Layer 0–8". |
| F-O2-03 | confirmed |  | P3 | Recap:460 lists initial claims without `occupied_without_residents`, which Layer 4 §9 registers as claim 4 (L4:339). Owner recap: add it. |
| F-O2-04 | confirmed |  | P3 | Recap:158-159 merges fact and action kinds with `extension` and a "resident response" kind; L0:1747-1749 excludes `extension` from `ApplyStepSourceKind` and the kind is `user_response` (L0:1794, 1863). Owner recap: separate the vocabularies and drop the "extension-related `ApplyStepSource`" sentence. |

Line references for the overview and recap in the notes above are to the current working tree; at
several places they are one or two lines below the pass's baseline citation, with identical text.

## Mechanical candidates

Classification of every `mechanical.md` candidate. "Defined in prose" points to the place that
introduces the name with its meaning when no `class`/alias definition exists.

### M1 — section references

| Candidate | Classification | Note |
|---|---|---|
| `layer5:622` → §6.2 | already covered by F-L5a-05 | Layer 5 has no §6.2; the terminal follow-up path is §6.0. |
| `layer5:2169` → §6.2 | already covered by F-L5b-07 | Same stale §6.2 (also listed in F-L5a-05). |
| `layer5:2450` → §6.2 | already covered by F-L5b-07 | Same stale §6.2. |
| `layer5:2755` → §4.5 | already covered by F-L5b-08 | Means Layer 0 §4.5.1. |
| `layer5:4808` → §6.5 | defined in prose at `docs/specs/v3/layer3_learning_spec.md:3845` | Not dangling: the text reads "§6.5 of Layer 3", which exists (`CanonicalEnvelope`, L3:3845); the script misses the trailing "of Layer N" form. |
| `layer5:5033` → §6.2 | already covered by F-L5a-05 | Stale §6.2 (lines listed in F-L5a-05). |
| `layer5:5041` → §6.2 | already covered by F-L5a-05 | Stale §6.2. |
| `layer5:5069` → §6.2 | already covered by F-L5a-05 | Stale §6.2. |
| `layer8:905` → §8.2 | defined in prose at `docs/specs/v3/layer6_notification_spec.md:466` | Not dangling: "§8.2 of Layer 6" exists; trailing "of Layer N" form, as the L8 pass noted. |

### M2 — identifiers without a formal definition

Paths are abbreviated: `L0`–`L8` = `docs/specs/v3/layer<N>_*_spec.md`.

| Identifier | Classification | Note |
|---|---|---|
| `ActuationRoutineEpisode` | defined in prose at `L3:1237` | Episode contents defined in the routine-learning paragraph. |
| `ActuatorRequirement` | historical mention | L1:1004 names it as belonging to the retired template-matching model (CA4-132). |
| `AppendOrder` | defined in prose at `L0:728` | `AppendOrder(cycle_id, ordinal)` assigned by Persistence. |
| `ApplicabilityEnvelope` | defined in prose at `L3:2615` | Contents enumerated in place. |
| `AvailabilityEpisodeTracker` | defined in prose at `L6:537` | Layer 6 §9.2 owns the tracker and its episode rules. |
| `AvailabilityPublicationIndex` | already covered by F-L6-08 | Cited by L3, L5 and the overview but not defined by Layer 6. |
| `BooleanInterpretation` | historical mention | L2:1079 records its removal (resolved 2026-09-05). |
| `BooleanSetStrategy` | historical mention | Removed strategy (L2:1166, 2711; recap:287). |
| `ComfortSetpointPreferenceModel` | defined in prose at `L3:4011` | Future proposal-only estimator, described in place. |
| `ComfortTrajectoryGuardProfile` | defined in prose at `L5:3764` | An indented `class` inside a list item, which the script's anchored regex misses. |
| `ComfortTrajectoryPrerequisiteGeneration` | defined in prose at `L5:3781` | Indented `class`, as above. |
| `Connection` | historical mention | L1:966 says V3 has no authored `Connection`; L1:1209 names V2's internal type. |
| `ContextBucketKey` | defined in prose at `L3:641` | Tier identity plus ordered canonical dimension values. |
| `ContextTransformRegistry` | defined in prose at `L3:538` | Core-owned, bootstrap-frozen registry. |
| `CountModel` | defined in prose at `L3:1061` | Model category; first concrete type at L3:1094. |
| `DerivedObservation` | historical mention | L1:1072 lists current V2 codebase names. |
| `DetectedSlowPathCapacity` | defined in prose at `L3:2994` | Diagnostic view of snapshot and baseline. |
| `DiagnosticFindingRegistry` | defined in prose at `L3:3230` | Frozen core registry of finding schemas. |
| `EngineHealthBaseline` | defined in prose at `L3:2989` | Contents stated in the following sentence. |
| `EnvironmentalEpisode` | defined in prose at `L3:2277` | Section 4.8.1 is its contract. |
| `EnvironmentalEpisodeLearner` | defined in prose at `L3:1870` | Common environmental learner family. |
| `EnvironmentalReferenceWindow` | defined in prose at `L3:2095` | Bounded historical window, described in place. |
| `EnvironmentalResidualAnalyzer` | defined in prose at `L3:2674` | Section 4.8.7 describes it. |
| `ExtensionInputSnapshot` | defined in prose at `L7:156` | Contents listed in §5. |
| `ExtensionRegistry` | defined in prose at `L7:60` | §3 defines it; blueprint types follow. |
| `ExternalContext` | historical mention | V2 entity-list pattern replaced by Layer 2 Sensors (L2:38, 657). |
| `Freshness` | historical mention | L1:431 records a rejected tri-state draft. |
| `FusionRuleRuntimeState` | defined in prose at `L2:1364` | Layer-2-owned control state keyed per rule. |
| `HeimaEvent` | defined in prose at `L1:264` | Operational delivery envelope; field mapping table at L1:279. |
| `HouseholdConsentAuthority` | defined in prose at `L5:3962` | Layer 5 §7.1.1 governance record. |
| `IfcSpace` | external or Python name | IFC standard entity. |
| `IfcZone` | external or Python name | IFC standard entity. |
| `InferenceSignal` | defined in prose at `L3:3365` | Generic contract in §6.3; concrete payload `IndirectSemanticAssistSignal` follows. |
| `IsExternal` | external or Python name | IFC property. |
| `LearnedPattern` | already covered by F-X2-06 | L0:2116 cites a Layer-3 output type that Layer 3 does not define. |
| `LearningExecutionRequest` | defined in prose at `L3:3096` | Contents enumerated in place. |
| `LearningProposalCandidate` | defined in prose at `L3:3591` | §6.3 lists its contents. |
| `MediaActivityInterpretation` | historical mention | Removed interpretation (L2:1079, 1088). |
| `NormalizationFusionRegistry` | historical mention | V2 codebase pattern (L2:1756; recap:302). |
| `NormalizedObservation` | historical mention | V2 codebase name (L1:1072). |
| `ObservedMemberProjection` | defined in prose at `L5:3545` | Pure projection, inputs and result stated in place. |
| `PatternLearnerConfig` | already covered by F-L1-03 | L1:592; the L2:1753 occurrence is F-X5-05. |
| `PendingApply` | defined in prose at `L5:3046` | §6.0.1 defines it. |
| `PresenceInterpretation` | historical mention | Removed interpretation (L2:1079). |
| `PreviousCycleSnapshot` | defined in prose at `L0:841` | Sealed by Persistence after each evaluation. |
| `ProgramFamilyRegistry` | defined in prose at `L5:902` | Bootstrap-frozen registry. |
| `ProposalCandidateKindRegistry` | defined in prose at `L5:74` | Frozen core registry with its Initial-V3 entries (L5:77-78). |
| `PureSemanticEvaluator` | defined in prose at `L4:273` | Field type of `RegisteredSemanticResolver` (L4:108); return contract at L4:273. |
| `ReactionDescriptor` | defined in prose at `L5:60` | Sole core contract for a `ConfiguredReaction`. |
| `ReactionDescriptorRegistry` | defined in prose at `L5:54` | Core-owned, bootstrap-frozen registry. |
| `ReactionGuardCapability` | defined in prose at `L5:247` | Entries of `ReactionGuardCapabilityRegistry` (id/version, binding schema, evaluator, redaction). |
| `ReactionGuardCapabilityRegistry` | defined in prose at `L5:247` | As above. |
| `RegistryGeneration` | defined in prose at `L2:224` | Layer 2 §2.5. |
| `RelationProfileRegistry` | defined in prose at `L5:107` | Layer 5 §3.1. |
| `ResidentPresentationPreferenceModel` | defined in prose at `L3:2442` | Optional model described in place. |
| `ResolvedLearningDefinition` | defined in prose at `L3:159` | Staging result of blueprint plus instance. |
| `ResourceEnvelope` | defined in prose at `L3:2976` | Contents enumerated in place. |
| `ResponseOwnerRegistry` | defined in prose at `L0:2074` | Frozen registry with Initial-V3 owners. |
| `RuntimeHealthSnapshot` | defined in prose at `L0:2876` | Contents enumerated in Layer 0 §9. |
| `RuntimeResourceProbe` | defined in prose at `L0:2886` | Probe sources described in place. |
| `Season` | historical mention | V2 Heating derivation (L2:1265; recap:300); L3:2690 says it is not implemented. |
| `SemanticInputSchema` | defined in prose at `L4:130` | Finite ordered set of typed slots. |
| `SemanticInputSnapshot` | defined in prose at `L4:195` | Built by the engine at the barrier. |
| `SemanticOutputClaim` | defined in prose at `L4:128` | Materialized from the template. |
| `SemanticOutputTemplate` | defined in prose at `L4:124` | Field type at L4:101; contents at L4:124. |
| `SemanticResolutionGeneration` | defined in prose at `L4:185` | Activated by Layer-4 staging. |
| `SemanticResolver` | defined in prose at `L4:12` | Generic name for a Layer-4 semantic resolver; the types are `RegisteredSemanticResolver` (L4:97) and `SemanticResolverDefinition`. |
| `SemanticResolverRegistry` | defined in prose at `L4:84` | Core-owned, bootstrap-frozen registry. |
| `SensorRequirement` | historical mention | Retired template-matching model (L1:1004, CA4-132). |
| `SignalRoutingSchema` | defined in prose at `L4:150` | Pure core-owned projection. |
| `SlowPathCapacityPlan` | defined in prose at `L3:3008` | Derived plan with `lower`/`target`/`upper`. |
| `StateTransitionEpisodeAdapter` | defined in prose at `L4:143` | Attached to a state output template. |
| `StratifiedResponseModel` | defined in prose at `L3:2092` | Core baseline estimator for environmental profiles. |
| `SurvivalModel` | defined in prose at `L3:953` | Model category; first concrete type at L3:979. |
| `TemporalActuationProfileModel` | defined in prose at `L3:4107` | Future proposal-only learner. |
| `TierSelectionTrace` | defined in prose at `L3:709` | Contents enumerated in place. |
| `TimeSeriesSplit` | external or Python name | scikit-learn class, cited as a reference. |
| `Timing` | defined in prose at `L0:92` | Layer 0 §3 facility name. |
| `TopologyRequirement` | historical mention | Retired template-matching model (L1:1004, CA4-132). |
| `TrainingSpan` | defined in prose at `L3:2897` | `(eligible_through - training_window, eligible_through]`. |
| `UnsupervisedModel` | defined in prose at `L3:1500` | Model category; first concrete type at L3:1510. |
| `ZoneKey` | defined in prose at `L1:789` | Exactly `zone_id`. |

## Summary

- **Findings (41):** 41 confirmed, 0 false positive, 0 approved decision. Two duplicates:
  F-L8-01 of F-L5a-03, F-O2-01 of F-O1-01. Several confirmed findings sit on approved decisions
  (CA4-129 d.4 for F-L7-01/02, CA4-130 d.5 for F-L7-03/04, CA4-131 for F-L8-02) but concretely
  contradict another approved rule or fail their own stated guarantee, so they stay findings.
- **Severity as assigned:** P1 1 (F-X9-01); P2 18; P3 22. F-L8-01 downgraded from P1 to P2.
- **Mechanical candidates (91):** 63 defined in prose (including 2 section references that
  resolve with the "§x of Layer N" form), 14 historical mentions, 4 external names, 10 already
  covered by findings (F-L5a-05, F-L5b-07, F-L5b-08, F-L6-08, F-X2-06, F-L1-03), 0 new real
  dangling references.

## New candidates

None recorded; the verifier did not search for new defects.
