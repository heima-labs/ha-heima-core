# Verification — area B (units L3a, L3b, L4, X2, X5, X6)

Verifier pass per README "Verification protocol". Quoted locations re-read in the working tree of
`feat/v3-planning` (git not run; line numbers matched the baseline quotes unless noted); backlog
`docs/v3_backlog.md` checked for approved decisions.

| Id | Verdict | Duplicate of | Severity | Note |
|---|---|---|---|---|
| F-L3a-01 | confirmed | | P1 | Layer 3 §4.4.1 declares no frozen `shadow_requirement` although `return_delay` has an action-serving egress and §9 staging rejects a missing value (l.4637); no backlog decision (CA4-13 closure is silent). Declare the per-profile value and the state an adopted timing artifact reaches. |
| F-L3a-02 | confirmed | | P2 | Layer 3 §4.2 person-related list (l.339–345) names `presence`, `presence.household` but not Layer 2's `presence.evidence.person.<id>` (L2 l.394); add `presence.evidence.*` to the list. |
| F-L3a-03 | confirmed | | P2 | Layer 3 §4.7 l.1844 "administrative generation transitions" vs Layer 0 §4.7 l.1590 and Layer 3 l.2666 "never a configuration-generation change"; reword as authenticated adoption/authority transitions. |
| F-L3a-04 | confirmed | | P3 | Layer 3 l.1895 and Layer 5 l.196 cite §4.8.2 (input bindings; no cell content in l.2354–2430) for cells defined in §4.8 body (l.2102) and §4.8.1 (l.2301); retarget both citations. |
| F-L3a-05 | confirmed | | P3 | Layer 3 §4.8.6 l.2621 `out_of_operating_envelope` is the only occurrence in the spec set; closed vocabulary uses `outside_operating_envelope` (l.1531); use the closed value. |
| F-L3a-06 | confirmed | | P3 | Layer 3 §4.3 l.729 `ambiguous_top_outcome` occurs only there; trace code and `CategoricalResult.selection` use `ambiguous_top` (l.712, l.842); rename. |
| F-L3a-07 | confirmed | | P3 | Layer 3 §4.9 l.2827 bare "(§4.1)" resolves in Layer 3 to `LearningDefinition`; write "Layer 5 §4.1". |
| F-L3a-08 | confirmed | | P2 | Layer 3 §4.8.2 l.2376 resolves "outdoor/radiation slots" at `casa`, but `incident_solar_exposure` is produced at the opening owner's room (L2 l.1633, l.1985); state its per-opening room resolution like opening/cover slots. |
| F-L3b-01 | confirmed | | P3 | Layer 3 §9 l.4225 cites §6.4 for `ContextHypothesisCandidate` and its uncertainty-schema rule, which are in §6.3 (l.3635–3657); cite §6.3/§4.4.7. |
| F-L3b-02 | confirmed | | P2 | Layer 3 §6.4 l.3720–3722 enumerates "Initial intents" without the routine's member intents (e.g. `light_state`, Layer 5 l.3538, §7.3 matrix "every admitted member intent"); replace the list with a reference to the Layer-5 registry. |
| F-L3b-03 | confirmed | F-L3a-01 | P1 | Same missing `shadow_requirement` of `RoomOccupancySurvivalModel` as F-L3a-01, argued from the §9 staging rule (l.4636–4638). |
| F-L3b-04 | confirmed | | P2 | Layer 3 §9 l.4360 requires a `ShadowPreviewBinding` for every proposal-producing type, but the "exactly" two initial bindings (l.4368–4371, §6.1.2 table l.3299ff) cover only `reaction.descriptor`, not `reaction.artifact_adoption` producers (§4.9 l.2821–2826; `return_delay` l.1045–1052); restrict the rule to descriptor producers or register an adoption binding/no-preview rule. Related to, not a duplicate of, F-L3a-01. |
| F-L4-01 | confirmed | | P2 | Layer 4 §9.4 l.488 tells a profile to "bind an event or episode slot", but `ActivityProfile` has only `ActivityEvidenceSlot` (current state, l.465, l.481) and §10 l.626 rejects an event source; admit a bounded event/episode slot kind or drop the sentence. |
| F-L4-02 | confirmed | | P3 | Layer 4 §10 l.656 gives `occupied_without_residents` a post-restart "baseline", while §9.2 l.391 says it keeps no retained state and l.656 itself says it has no adapter; move the baseline/episode-producer sentences to the casa-adapter bullet. |
| F-L4-03 | false positive (§4.1 l.135–136 states the `activity` kind selects its frozen `ActivityProfile` through `claim_parameters.activity_id` as profile data within the kind, so the `(resolver_kind_id, implementation_version)` key and the profile dispatch coexist; whether a profile-version bump alone impacts a generation is an ambiguity, not a contradiction) | | — | Possible observation for §8 wording only. |
| F-X2-01 | confirmed | | P2 | Layer 0 §11 (l.3012–3016) and its §13 criterion promise Recovery classification to every semantic resolver; Layer 4 §5.1 (l.197–206) gives evaluators no recovery input and routes `FrozenRecoveryView` only to Layer 5. Owner Layer 0: restrict the engine-computed context for resolvers to cycle identity/time and name Layer 5 as the recovery consumer. |
| F-X2-02 | confirmed | | P2 | Layer 3 l.472–474 evaluates `runtime_resolvable` features against "its declared bounded buffer", but Layer 0's only frozen hot-path history read is `FrozenHistoryView`, declared and read by Layer 5 only (l.850–875). Owner Layer 0/Layer 3: let the Layer-3 emitter declare `HistoryViewRequirement`s frozen at the barrier, or limit live features to current/previous-cycle values. |
| F-X2-03 | confirmed | | P2 | Layer 0 §5.2 l.2109–2112 propagates the cycle `correlation_id` to every `InferenceSignal`; the closed `IndirectSemanticAssistSignal` (Layer 3 l.3403–3416) has no such field and Layer 4 rejects a payload extension (l.3429). Owner Layer 3: add `correlation_id` to the signal common fields. |
| F-X2-04 | confirmed | | P2 | Layer 3 §5.3 needs process CPU time and `C_engine_baseline` (l.3003, l.3014–3015) but `RuntimeHealthSnapshot` (Layer 0 §9 l.2876–2880) has no CPU-time field and `EngineHealthBaseline` holds only RSS and latency (l.2990–2991). Owner Layer 0 §9: add process CPU time, or Layer 3 states its own measurement. |
| F-X2-05 | confirmed | | P3 | Layer 0 §5 `analyzer` comment (l.1760–1763) names the Layer-3 `PatternLearner` as a fact producer, contrary to Layer 3 §2 l.50–52 (results are not house facts). Owner Layer 0: drop the Layer-3 example. |
| F-X2-06 | confirmed | | P3 | `LearnedPattern` (Layer 0 l.2116) occurs nowhere else in the spec set. Owner Layer 0 §5.2: name the Layer-3 outputs that carry the run's `correlation_id`. |
| F-X2-07 | confirmed | | P3 | `history_window` (Layer 0 l.1084) occurs nowhere else; Layer 3 declares `training_window` (l.526, l.2867). Owner Layer 0 §4.3: replace the field name. |
| F-X2-08 | confirmed | | P3 | Layer 0 §13 (now l.3098) "A `present` then `away` presence" uses a value outside `presence`'s `home`/`away` vocabulary and no adapter row (Layer 4 l.408–413). Owner Layer 0: write `home` then `away`. |
| F-X2-09 | confirmed | | P3 | Layer 0 l.952–953 and §13 (now l.3514) make an unhydrated previous-cycle reference `available=False`; Layer 4 l.217–220/l.699–700 map a missing predecessor to `previous=None`, distinct from an unavailable prior fact. Owner Layer 0: say the reference is absent, mapped to `previous=None`. |
| F-X2-10 | confirmed | | P3 | Layer 0 §3.2 l.372–374 leaves `LearnedWindow` calibration to "whichever `SemanticResolver`/`FusionRule`", while Layer 4 l.35 forbids history reads and CA4-13 (backlog l.5592ff) routes learned timing through the Layer-3/Layer-5 path. Owner Layer 0: point to that path. |
| F-X2-11 | confirmed | | P3 | Layer 3 §5.3 l.2997/l.3064–3066 lets the admin change the installation profile at runtime outside any generation; Layer 0 §4.7 l.1586–1591 says every configuration mutation in any layer is generation-composed and its exception list omits it. Owner Layer 0 §4.7: list the profile as a non-generation runtime setting (or stage it). Medium confidence: whether the profile is "configuration" is not defined. |
| F-X5-01 | confirmed | | P2 | Layer 2 §2.10 l.513–515 reserves `opening.open` to Layer-5 readers, Layer 3 §4.8.2 l.2377–2382 requires opening evidence from an `environment.opening_state.<sensor_id>` Sensor, and Layer 2 §3 l.606 registers a readable path once; one exterior contact serving posture check and an exchange learner has no legal registration. Owner Layer 2 §2.10 (or Layer 3 §4.8.2): name one opening-state fact readable by both. Related tension on double reads: F-L2-02. |
| F-X5-02 | confirmed | | P2 | Layer 2 §3 l.624–626 makes `occupancy.physical` "the sole" physical ground truth a core learner may bind; Layer 3 §4.4.1 l.983–989 anchors/targets on resolved Layer-4 `occupancy` transitions filtered by physical provenance. Owner Layer 2 or Layer 3: name one label source (bind `occupancy.physical`, or admit physically-provenanced Layer-4 occupancy). |
| F-X5-03 | confirmed | | P2 | Layer 3 §4.1.2 l.159–161 resolves bindings "against the active Layer-2 generation", while Layer 0 §4.7 l.1612–1613 and Layer 4 l.182 validate against the candidate lower layers. Owner Layer 3: say "candidate". |
| F-X5-04 | confirmed | | P3 | Layer 2 §5.3 l.1600–1601 says Layer 3 binds a `FutureStateFractionOutcome` to the solar hysteresis stream; Layer 3 l.971–973 and backlog CA4-13 scope note (solar `q` removed, l.5618ff) register none. Owner Layer 2: reword as a future-profile constraint. |
| F-X5-05 | confirmed | | P3 | Layer 2 §5.3 l.1752–1754 quotes Layer 3 ("declared in code only…") and `PatternLearnerConfig`; neither occurs in Layer 3 (only in L1 l.592, already F-L1-03, and here). Owner Layer 2: cite Layer 3 §4.1.1's core type registry. |
| F-X5-06 | confirmed | F-X2-09 | P3 | Same `available=False` vs `previous=None` predecessor mismatch as F-X2-09, here restated by Layer 2 §2.5 l.264–266 for impacted producers against Layer 4 l.216–220; fix together. |
| F-X6-01 | confirmed | | P2 | Layer 3 §6.4 l.3767–3771 requires a learned-timing binding to match a `FutureStateFractionOutcome`, but the only Initial-V3 learned timing path is `RoomOccupancySurvivalModel.return_delay`, which Layer 5 §4.2 l.1574–1576 "is never coerced into a state-fraction outcome" and §8 l.4571 rejects as a scalar fraction. Owner Layer 3 §6.4: defer to the outcome contract of the registered Layer-5 timing path. |

## Summary

- Findings verified: 33 (L3a 8, L3b 4, L4 3, X2 11, X5 6, X6 1).
- Confirmed: 32. False positive: 1 (F-L4-03). Approved decision: 0.
- Duplicates: 2 (F-L3b-03 of F-L3a-01; F-X5-06 of F-X2-09).
- Confirmed P1: F-L3a-01 (and its duplicate F-L3b-03).
- Cross-area note: F-L5a-07 (area of L5a) describes the same Layer-5 half of F-L3a-04; by the
  lowest-id rule its duplicate target is F-L3a-04.
- Line drift: Layer 0 §13 quotes of F-X2-08/F-X2-09 are now at l.3098/l.3514 (baseline l.3092/l.3503);
  minor ±1 shifts at Layer 3 l.729 and l.2827. Text unchanged.

## New candidates

None.
