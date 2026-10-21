# Verification — area A (units L0, L1, L2, X1, X4)

Verifier pass under the README "Verification protocol". Each quoted location was re-read in the
current working tree of `feat/v3-planning` (specification text unchanged since baseline `84f5263`
except the F-L0-06 resolution in Layer 0 §6.4/§13, which shifts later Layer-0 line numbers by about
+10; quotes were located by text). Relevant `docs/v3_backlog.md` decisions were checked for each
finding.

| Id | Verdict | Duplicate of | Severity | Note |
|---|---|---|---|---|
| F-L0-01 | confirmed |  | P2 | Layer 0 §4.1 (now l. 846–848) still says "durable history never seeds this view", against §4.1 l. 946–953, §13 and the 2026-09-09 `previous_cycle` decision; restrict the sentence to unclean/mismatched restarts and newly declared or impacted keys. Lowered to P2: the detailed rule, §13 and the decision agree; only one stale sentence. |
| F-L0-02 | confirmed |  | P2 | Layer 0 §5 (l. 1835) and §13 (l. 3527–3528) say every `ControlActor` class "creates a hold", while §6.2 and the §13 criterion at l. 3238 open none without a qualifying divergence; CA4-119 only made hold origin `manual` for every class; reword as "any class can open a hold when the edge qualifies under §6.2". |
| F-L0-03 | confirmed |  | P2 | Layer 0 §4 reserves the claim of every other Layer-6 kind (l. 663–684) but none for `system.health` (Layer 6 §4.2 kind; descriptor `claim_owner_id` required); add a reserved `system.health` event claim with its Layer-6 owner id. |
| F-L0-04 | confirmed |  | P3 | CA4-118 (backlog l. 6497) approved deriving `household_role` from the Layer-2 Person, so behavior is decided; the defect is that Layer 0 §5 (l. 1842) and §5.1.3 (l. 2082) read Layer 2 with no pushed contract, against l. 1087 and l. 1918. Owner Layer 0 §5: state that the composed generation hands Layer 0 a frozen `ha_user_id -> household_role` projection. Lowered to P3. |
| F-L0-05 | confirmed |  | P3 | Layer 0 §13 (l. 3504–3505) "one last-write-wins snapshot commit" per entity vs §7.4 (l. 2632–2636) keyed by `(actuator_id, controlled_channel)` with per-facet replacement; reword the criterion. |
| F-L0-06 | confirmed |  | P3 | Already confirmed and corrected by the coordinator (resolution F-L0-06); Layer 0 §6.4/§13 now accept the declared overflow loss. Not re-verified beyond the index. |
| F-L0-07 | confirmed |  | P3 | Layer 0 §4.0 (l. 764–765) cites Layer 2 §5.2 for the route; the route contents are in Layer 2 §7 (l. 2295–2306); cite §7. |
| F-L1-01 | confirmed |  | P3 | Layer 1 §4.2 (l. 554) says `min_available=1` is the Layer-2 default; Layer 2 §5.1 (l. 1164, 1177–1181) makes it mandatory with "no default"; Layer 1 should say "explicitly configured with `min_available=1`". |
| F-L1-02 | confirmed |  | P3 | Layer 1 §4.4 (l. 680–683) attributes `importance` (`OBSERVE`/`SUGGEST`/`ASSERT`) to Layer 3's `InferenceSignal`; Layer 3 §6 (l. 3369–3371) lists its contents without it and no V3 layer defines it (only the V2-era backlog note, backlog l. 125); Layer 1 should drop or neutralize the bullet. |
| F-L1-03 | confirmed |  | P3 | Layer 1 §4.2 (l. 592) cites `PatternLearnerConfig.target_shape`, absent from Layer 3; Layer 3 §4.3 (l. 519–527) declares a categorical/continuous target and confidence mode; Layer 1 should cite those. |
| F-L1-04 | confirmed |  | P3 | Layer 1 §8 (l. 1028–1029) "one per Layer 3 analysis run for learned facts" and §3 (l. 241–242) "a new learned pattern" contradict Layer 1 §2.2 (l. 89–91) and Layer 3 §2 (l. 50–54): learning outputs are not facts; Layer 1 should restate as outputs of an analysis run, not facts. Related to, not a duplicate of, F-X2-05/F-X2-06 (Layer 0 wording). |
| F-L1-05 | confirmed |  | P3 | Layer 1 §3.1 (l. 319) "under §4.5" has no local target (Layer 1 §4 ends at §4.4); the rule is Layer 0 §4.5; qualify the reference. |
| F-L1-06 | confirmed |  | P3 | Layer 1 §4.3 (l. 655–656) cites "(§4 intro)" for "supporting detail, not essential"; the §4 intro (l. 382–414) has no such statement, which opens §4.3 (l. 632); cite §4.3. |
| F-L2-01 | confirmed |  | P2 | Layer 2 §2.8.1 (l. 399–403) generates `presence.household` from zero inputs when no resident is tracked and says it is `available=False`, while §2.4 (l. 187, 197–198) rejects empty `inputs` and `threshold=1.0` outside `(0, 0]`; CA4-120 does not settle the zero case. Owner Layer 2 §2.8.1: state how the zero-tracked case is produced or exempt the generated rule. |
| F-L2-02 | confirmed |  | P2 | Layer 2 §2.8.1 (l. 387–396) generates two Sensors on the same HA person state path, while §3 (l. 606) registers each readable path "exactly once" and §3.6 (l. 958–960) relies on it as a staging rule. Owner Layer 2: exempt §2.8.1 explicitly or derive presence evidence without a second binding. |
| F-L2-03 | confirmed |  | P3 | Layer 2 §5.3 recipe (l. 1747–1748) "applies equally to occupancy, presence, or another registered physical boolean family", but `validate_binding` (l. 1684–1686) admits only `occupancy.physical`; stale since CA4-120 moved household presence to trackers. Restrict the recipe sentence. Lowered to P3: staging behavior is unambiguous. |
| F-L2-04 | confirmed |  | P3 | Layer 2 §5.6 (l. 1874) "`FusionRule` is core-team-authored only (§2.1)"; §2.1 (l. 79–80) closes strategies/interpretations/formulas, not FusionRule records, which administrators stage; ground the static-graph argument on per-generation staging (§2.5). |
| F-L2-05 | confirmed |  | P3 | Layer 2 §2.4 (l. 205–208) requires `configuration=None` for every other Initial-V3 formula; §5.3 (l. 1669–1671) admits another compiled type "unless their own core registration explicitly declares" one; make §2.4 authoritative and have §5.3 point to it. |
| F-L2-06 | confirmed |  | P3 | Layer 2 §3 `related_opening_id` comment (l. 566–570) cites §2.4, which states the rule only for `Actuator.opening_id` (l. 184–185); the Sensor rule is in §3 (l. 662–667); cite §3. |
| F-L2-07 | confirmed |  | P3 | Layer 2 §7 (l. 2281–2282) "`Stability` composed of two `Window`s" vs §5.2 three fields incl. `unavailable_grace` (l. 1333–1335); update §7. The finding's second claim (other Window fields unspecified) is weak: "Every `Window`-typed field in this document" already covers them, the parenthetical being examples. |
| F-L2-08 | confirmed |  | P3 | Layer 2 §2.9 (l. 485–487) requires horizon > ceiling + largest recovery, but Layer 5 §7.1 (l. 3654–3666) admits recovery up to 7 days with a 7-day ceiling (sum = 14 days = horizon) and itself claims only horizon > ceiling; align on one inequality and cite Layer 5's minimum-absence rule instead of `planned_absence_program`. |
| F-X1-01 | confirmed |  | P2 | Layer 0 §4.1 (l. 823–827) and §4.5 (l. 1352) declare the recovery-target snapshot and the frozen-dataclass `NotificationDeliveryRecord` to be `PersistedProjection`s, but `RecoveryTargetSnapshot.facets` (l. 2599–2605) is depth ≥ 3 and Layer 1 §4 (l. 405–409, with the depth rule at l. 159–162; CA4-28) admits depth 2 and no dataclass. Owner Layer 0: make only the producer payloads (`intent`, facet values) `PersistedProjection`s and bound the envelopes separately. |
| F-X1-02 | false positive (Layer 0 §3.4, l. 414–416, names the calendar Sensor sharing the classifier, and §3.4.1, l. 436–449, defines `active_now` as a cycle read of the cache; the §4.1 requirement list and the §13 rejection at l. 3481–3486 apply to staged `CalendarViewRequirement` consumers, not to the Sensor's active-now read) |  | — | Residual gap (how a Sensor-only calendar entity enters the cache's entity set) is not a contradiction; recorded under New candidates for triage. |
| F-X1-03 | confirmed |  | P2 | Layer 2 §2.5 (l. 278–282) says Actuator removal or a changed `entity_id` deletes the old snapshots and that Layer 0 receives an "entity delta"; Layer 0 §7.4 (l. 2661–2663) receives only policy/fingerprint deltas, and the Actuator semantic fingerprint fields are not enumerated (Layer 2 l. 237–240). Owner Layer 0 §7.4: accept the removal/entity delta and delete those snapshots. |
| F-X1-04 | confirmed |  | P3 | Layer 1 §4.3 (l. 657), Layer 2 (l. 805, 1287, 1539) and Layer 0 itself (l. 773) send producer diagnostics to a "Layer 0 §10" diagnostic event; §10 (l. 2906–2949) lists only Layer-0 facility state. Owner Layer 0 §10: add a producer diagnostic-event entry. |
| F-X1-05 | confirmed |  | P3 | Layer 1 §3.1 (l. 340–343) "changes only on physical state/availability changes and the first valid post-restart observation" vs Layer 0 §5.1.1.1 (l. 1929–1931, source-fingerprint change; l. 1954, overflow re-seed); Layer 1 should reference Layer 0 instead of enumerating. |
| F-X1-06 | confirmed |  | P3 | Layer 0 §5 `FactSource.source_id` example "an entity id" (l. 1730) vs Layer 2 §7 `source_id` = `sensor_id`/`fusion_id` (l. 2292) and `sensor_id` "not an HA entity_id" (l. 554); change the Layer-0 example to a registry id. |
| F-X4-01 | confirmed |  | P3 | Layer 1 §3 (l. 249–252) reserves the suffixed shape for room-occupancy evidence with a `sensor_id` suffix; Layer 2 uses it at casa (l. 626–630) and in §2.8.1 for `occupancy.evidence.person.<ha_person_id>` and `presence.evidence.person.<ha_person_id>` (l. 387–396); stale since CA4-120. Layer 1 should state the shape generically and defer the uses to Layer 2. |
| F-X4-02 | confirmed |  | P3 | Layer 1 §4.2 (l. 584–587) says an all-unavailable fusion yields an `available=False` `HouseFact` that cycle, while the approved "Stability unavailable grace" decision (backlog l. 3459–3471, applied only to Layer 2 §5.2, l. 1336–1382) keeps the last committed output for the grace; Layer 1 should scope the rule to the raw candidate and point to Layer 2 §5.2. |
| F-X4-03 | false positive (Layer 1 §7, l. 911–913, "an `Actuator` channel with `opening_id` (Layer 2 §3, §6)" reads as a channel of an Actuator carrying `opening_id`, which is what Layer 2 §6, l. 2081–2083, defines; no difference in meaning) |  | — | Optional wording polish only. |

## Summary

- Findings verified: 30 (L0 7, L1 6, L2 8, X1 6, X4 3).
- Confirmed: 28 (P1 0; P2 7: F-L0-01, F-L0-02, F-L0-03, F-L2-01, F-L2-02, F-X1-01, F-X1-03;
  P3 21).
- False positive: 2 (F-X1-02, F-X4-03).
- Approved decision: 0 (F-L0-04 and F-X4-02 involve approved decisions CA4-118 and the 2026-09-10
  unavailable-grace decision, but the defect is in un-updated restatements, so they stay confirmed).
- Duplicates within area A: none. Lower-id duplicates elsewhere that point here: F-L6-05 duplicates
  F-L0-03; F-L5b-09 duplicates F-L2-08 (both for the verifiers of those areas to record).
- Confirmed P1: none (F-L0-01 lowered from P1 to P2).

## New candidates (unverified)

- Calendar Sensor cache membership: Layer 0 §3.4.1 (`layer0_runtime_spec.md:460`) — "Consumers
  declare their largest upcoming horizon at registration. The cache prefetches through the maximum
  declared horizon for that entity"; §4.1 (`:883–884`) lists only "A Layer-5 plan or a core Layer-2
  declared-context producer (Layer 2 §2.9)" as `CalendarViewRequirement` declarers; Layer 2 §3.1
  (`layer2_registries_spec.md:693–694`) — "`CalendarWindowReadBinding` reads only the raw windows
  active **now** for one `calendar.*` entity through Layer 0's `active_now` view". No text says how a
  calendar entity bound only by a Sensor enters Layer 0's per-entity cache (declaration with a zero
  horizon or otherwise).
