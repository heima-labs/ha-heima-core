# Verification — area C (L5a, L5b, L6, X3, X7)

Verifier pass per README "Verification protocol". Quoted locations re-read in the working tree of
`feat/v3-planning` (specification files unchanged since baseline `84f5263` per the README rule; no git
run). Backlog `docs/v3_backlog.md` checked for approved decisions.

| Id | Verdict | Duplicate of | Severity | Note |
|---|---|---|---|---|
| F-L5a-01 | confirmed | | P2 | Layer 5 §3.2 L399-402/§3.2 L547-549 require a `direct_guard_contract` for a profile-free `admin_direct` descriptor and §3.2 L862-863 says advice members pass the same guards; §7.3 L4310 gives `safety.posture_check` "none" and CA4-126 (backlog L6433) is silent on it. Layer 5 §3.2/§7.5: register a posture-check direct guard contract (its intents declared safe/low-risk or with an explicit required set) or add an advice-only exemption to §3.2. |
| F-L5a-02 | confirmed | | P2 | Every relation profile names one exact `ReactionGuardContractRef` (L399), but `hvac_thermal_response` has none in §3.2 (L332-388 enumerate the others) and §7.3 L4307 says "from its prerequisite generation"; §7.1 L3796-3797 validates against "the descriptor's exact guard contract", which does not exist. Layer 5 §3.2: register the comfort-trajectory guard contract and make `required_guard_capabilities` checked against it. |
| F-L5a-03 | confirmed | | P1 | Same defect as F-L8-01 (Layer 8 side). L5 §4.2 L1805 "Commands 2 to 7 are immediate actions" vs §7.1.1 L3971-3973 "the same change set must carry the authority change"; reclassifying/removing an authorized Person has no valid path. Raised to P1 (authorization data path unimplementable consistently). Owner Layer 5 §4.2 with Layer 8 §6.1/§6.2 and Layer 2 §2.8: pick one rule (change-set kind or immediate command) for command 7. |
| F-L5a-04 | confirmed | | P2 | L1308-1310 and L1709-1710 route learner-origin semantic changes through "a new proposal"/"successor-generation path", but acceptance (L1359-1363) only creates a new root at index 0 and command 1 excludes learner-origin Reactions (L1830); no rule appends a successor to an existing Reaction from a proposal. Layer 5 §4.1/§4.2: define proposal-driven successor targeting an existing Reaction, or reword to "a new Reaction". |
| F-L5a-05 | confirmed | | P3 | Layer 5 headings stop at §6.1 (L3143); `§6.2` at L622 (and L2169, 2450, 5033, 5041, 5069) resolves to nothing. Layer 5: retarget to the §6.0 follow-up / hold-release subsections. |
| F-L5a-06 | confirmed | | P3 | Layer 3 §6.2 (L3335-3362) does not name the type; `class ArtifactAdoptionCandidate` is at L3615 under §6.3.1. Layer 5 L1116: cite Layer 3 §6.3.1. |
| F-L5a-07 | confirmed | F-L3a-04 | P3 | F-L3a-04 already quotes the same Layer 5 L196 citation; L522 repeats it. Layer 3 §4.8.2 (L2354) is input bindings. Layer 5 (and Layer 3 L1896): cite Layer 3 §4.8 / §4.8.6. |
| F-L5a-08 | confirmed | | P3 | Layer 3 §5.1 (L2857) is refresh scheduling; run admission/captured generation are §5.2 (L2946) and §4.1.2. Layer 5 L1343: cite Layer 3 §5.2. |
| F-L5a-09 | false positive (Layer 0 §6.2 L2418-2419 states the cited rule: "Administrative disablement and consent revocation of the release owner remain immediate, invalidate the whole hold"; the literal enum lives in §6.1 but the behavioral citation resolves) | | P3 | Optional polish only: cite "Layer 0 §6.1–§6.2". |
| F-L5a-10 | confirmed | | P3 | L1099-1101 "user-visible output remains exclusively" follow-up and availability contradicts advisory (L2462), action-notice (L2515), consent and proposal-review occurrences. Layer 5 §4.0: restate as "execution-audit records are never user-visible". |
| F-L5b-01 | confirmed | | P2 | §5.2 L2035 closes outcome/reason pairs to `trigger_not_matched`/`semantic_guard_unsatisfied` only, yet §4.0 L981-985 adds three CA4-122 codes used at L503 and L3663-3665 ("abstains with `recovery_beyond_horizon`" while `abstained` has no evaluation reason); backlog CA4-122 (L6465) fixes no outcome. Layer 5 §5.2: state which outcome carries each of the three codes. |
| F-L5b-02 | confirmed | | P2 | §7.4 L4352/L4378 use a current-`True` start criterion that reopens after restart; the "valid direct example" L4389 uses `state_transition(... False -> True)`, which §5.1 L1941 makes `abstained` across a restart gap, and L1917 says step-programmed descriptors use start criteria. Layer 5 §7.4: express the example's start as the hazard boolean's start criterion. |
| F-L5b-03 | confirmed | | P1 | CA4-126 (backlog L6433) approves `safety` family for posture-check advisories, and Layer 6 §6.1 L253 agrees, but Layer 6 §4.2 L102 fixes `reaction.advisory` to `suggestion` and §6.1 L243 limits namespace families to three other kinds: a 03:00 `lock_entry` advisory is held by quiet hours under one rule and immediate under the other. Raised to P1 (safety notice delivery). Owner Layer 6 §4.2/§6.1: make `reaction.advisory` family namespace-derived. |
| F-L5b-04 | false positive (L3601 says "the three other trigger-driven descriptors above", scoped to those specified before it; §7.4 L4348-4350 and §7.5 L4404-4408 register their own fields, so no restated rule differs in meaning) | | P3 | Optional: defer the paragraph to the §7.3 matrix. |
| F-L5b-05 | confirmed | | P3 | §7.3 L4339-4340 "available only for `environment.external_exchange` and `environment.solar_shading`" vs §3.2 L864-867 adding `safety.posture_check` intents. Layer 5 §7.3: add posture check or drop the enumeration. |
| F-L5b-06 | confirmed | | P3 | §8 L4854 "Only `eligible` reaches bundle admissibility" vs §5.2 L2026-2027 admitting terminal-step `normal_exit`. Layer 5 §8: align with §5.2. |
| F-L5b-07 | confirmed | F-L5a-05 | P3 | Same nonexistent Layer-5 §6.2 at L2169, 2450, 5033, 5041, 5069. Layer 5: retarget to §6.0 / §4.2. |
| F-L5b-08 | confirmed | | P3 | L2755 "fields that §4.5 permits" — Layer 5 has no §4.5; intended Layer 0 §4.5.1 (L1356). Layer 5: qualify the reference. |
| F-L5b-09 | confirmed | F-L2-08 | P3 | Layer 2 L485 "must exceed" vs Layer 5 L3655/L3664 ceiling 7 d and abstention only when recovery "exceeds 7 days": 7 d + 7 d = 14 d. Layer 5 §7.1 or Layer 2 §2.9: make one bound strict or say "at least". |
| F-L6-01 | confirmed | F-L5b-03 | P1 | Same defect seen from Layer 6: §4.2 L102 fixes `reaction.advisory` to `suggestion`, §6.1 L243-246 limits namespace families to three kinds, §6.1 L253-255 and Layer 5 §7.5 L4408 (approved CA4-126) say posture-check advisories are `safety`. Layer 6 §4.2/§6.1: derive the advisory family from the descriptor namespace (occurrence carries the descriptor id). |
| F-L6-02 | confirmed | | P2 | §9.3 L544-546 applies §7.4 clearing on `closed` of a proposal, whose item tag is the shared digest tag (L379), while §6.3 L301-302 clears only "when no proposal remains open"; one approval would erase the digest of still-open proposals. Layer 6 §9.3: exclude proposals and defer to §6.3. |
| F-L6-03 | confirmed | | P2 | §5.4 L222-224 and §6.2 L279-282 state "a phase with answer buttons whose request is still open" is never filtered/silenced; an `opened` advisory has buttons and an open request (Layer 5 L2629-2632), so `off`/`quiet_silent` for `suggestion` (L219, L287-288) could never act. Layer 6 §5.4/§6.2: restrict the rule to the closed kinds consent request and recovery confirmation. |
| F-L6-04 | confirmed | | P2 | §4.3 L124-126 maps `where=subject`, `when=occurred_at`, with exceptions only for availability and follow-up; `RuntimeHealthOccurrence` (Layer 0 L2962-2969) has neither field. Layer 6 §4.3: add the `system.health` mapping (casa, `detected_at`). |
| F-L6-05 | confirmed | F-L0-03 | P2 | Layer 0 L670-684 reserves every other Layer-6 claim but no `system.health`; Layer 6 L84-85 requires a Layer-0 claim owner. Layer 0 §4.0: reserve the `system.health` event claim (and Layer 1 §3.1 list it). |
| F-L6-06 | confirmed | | P2 | §7.6 L415-417 cites Layer 3 §6.3.1 for `episode_sequence`; the term appears nowhere else and Layer 3 L3530-3531 says the tracker "retains only the current episode". Layer 6 §9.2/§7.6: define the counter and its key, and align Layer 3's retention list. |
| F-L6-07 | confirmed | | P3 | §2 L46-47 "reads from Home Assistant only configuration: the system language and the registered `notify.*` services" vs §8.2 L471 formatting with "HA's unit system". Layer 6 §2: add the unit system to the list. |
| F-L6-08 | confirmed | | P3 | §9.2 L517-519 "a new revision number" and "a Reaction of another generation" have no field in `AvailabilityPublicationGeneration`/`BindingEnablementChange` (L500-512); `AvailabilityPublicationIndex` is cited by Layer 3 L3508, Layer 5 L2908 and the overview but not defined in Layer 6. Layer 6 §9.2: name the index type, add the revision field and the generation match rule. |
| F-X3-01 | confirmed | | P2 | Layer 5 L1719-1721 lists a changed "timing-model" binding as breaking, but Layer 0 §4.7 L1616-1622 indexes only fact claims and Actuator channels as producers and lists no Layer-5 timing-model consumer, so a changed/removed Layer-3 learning definition cannot classify the Reaction. Layer 0 §4.7: add learning definitions as producers and timing-model bindings as consumers (or give Layer 5 an explicit dependent-invalidation rule). |
| F-X3-02 | confirmed | | P2 | Layer 0 §7.4.1 L2699-2700/L2772-2773 says "Layer 5 supplies the current admitted recovery proposal", subject and `proposed_facets`; Layer 5's body has only the anchor (L3021-3031) and an acceptance bullet (L4765-4771), with no proposal type, fingerprint inputs or approved-dispatch path. Layer 5 §6.0: add the recovery-confirmation proposal hand-off. |
| F-X3-03 | confirmed | | P3 | Layer 0 L2060 `expires_at: EvidenceInstant` is mandatory and L2081-2082 accepts only "unexpired" requests; Layer 5 L2611 ("expiring when the request closes") and L2631-2633 declare open-ended requests with no instant. Layer 0 §5.1.3: make `expires_at` optional or have Layer 5 state the value. |
| F-X3-04 | confirmed | | P3 | Layer 0 §3.4 L413-415 obliges "a Layer-5 consumer" to declare a `KeywordClassifier`; Layer 5 L1972-1974 (CA4-121) reads only `household.planned_absence` and declares no calendar binding, and `ReactionEvaluationPlan` (L1525-1527) has no classifier. Layer 0 §3.4: restate the consumer as the Layer-2 declared-context producer. |
| F-X3-05 | confirmed | | P3 | Layer 0 §4.7 L1589-1590 and L1622-1623 list recipients and family options only; Layer 6 §10 L572 and L587-588 add `house_endpoints` with no dependents (Layer 6 §13 U3 L641-642 repeats the old list). Layer 0 §4.7 (and Layer 6 U3): add house endpoints. |
| F-X3-06 | confirmed | | P3 | "Runtime Scheduler" (Layer 6 L8, L325) occurs nowhere in Layer 0; the timer facility is Timing/`AtJob` (Layer 0 §1 L25, §3.1). Layer 6: cite "Timing (`AtJob`, Layer 0 §3.1)". |
| F-X7-01 | confirmed | | P2 | Layer 5 L734-736 and Layer 6 §9.2 L535-537 place the "enabled, user-visible binding" check at publication staging, but bindings are composed disabled (L1364-1366), become enabled only after the immediate promotion commits (L1779-1782), and promotion (command 4, L1854-1861) states no such check; a resumable Reaction with `user_visible=False` can be promoted, against §8 L5113-5117. Layer 5 §4.2 command 4: check the user-visible binding at promotion; Layer 6 staging keeps existence/visibility only. |
| F-X7-02 | confirmed | | P3 | Layer 6 §13 U4 L643 "an HA user id" vs Layer 5 §7.1.1 L3964-3965 (`ha_person_id` of a resident Person) and Layer 6 §5.2 L185-186. Layer 6 §13: restate U4 with `ha_person_id`. |
| F-X7-03 | confirmed | | P3 | Layer 6 §14 L685-687 expects an `environment.*` action notice to be held, but Layer 5 L2517-2518 lets only `safety.weather_protection` emit action notices in Initial V3. Layer 6 §14: limit the held case to availability and follow-up. |

## Summary

36 findings verified: 34 confirmed, 2 false positive (F-L5a-09, F-L5b-04), 0 approved decision.
Duplicates: 5 (F-L5a-07 → F-L3a-04, F-L5b-07 → F-L5a-05, F-L5b-09 → F-L2-08, F-L6-01 → F-L5b-03,
F-L6-05 → F-L0-03). Outside this area, F-L8-01 describes the same defect as F-L5a-03 (lower id in
index order) and should be marked its duplicate by its verifier.

Confirmed P1: F-L5a-03, F-L5b-03, F-L6-01. Severity changes against the passes: F-L5a-03 P2 → P1
(aligned with F-L8-01), F-L5b-03 P2 → P1 (aligned with F-L6-01).

CA4-126 (backlog L6433) approves the `safety` family for posture-check advisories; it does not
excuse F-L5b-03/F-L6-01 because it contradicts the approved Layer 6 §4.2 kind table.

## New candidates (unverified)

- `layer7_extensions_spec.md:7` — "... `FactSource` and non-forgeability (§5, §5.1), Runtime Scheduler"
  — same undefined Layer-0 term as F-X3-06, in Layer 7.
- `layer6_notification_spec.md:88` — "default_family: NotificationFamily | None   # None: resolved from
  the descriptor namespace (§6.1)" — the descriptor field already admits namespace resolution, which
  the §4.2 table does not use for `reaction.advisory`; relevant to the F-L5b-03 correction.
