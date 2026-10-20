# L5b — `layer5_action_reactions_spec.md` §5 to end

**Coverage.** Read `layer5_action_reactions_spec.md` lines 1901–5206 in full: §5.1 (closed relational
vocabulary, `state_transition`, declared household plan), §5.2 (snapshot semantics, outcome
validation, decision record), §6.0 (hold and command-ownership admission, next-step slot, delayed
action slot, learned-delay selection, hold release at a future step, advisory / on-site / action
notice / proposal review / consent / advisory feedback / follow-up occurrences, arbitration,
`ApplyStep`, translation delay permissions), §6.0.1, §6.1, §7 (all eight Initial-V3 descriptors,
§7.1–§7.5 including the matrix), §8. Cited sections read to check: Layer 5 §3.2 descriptor fields,
consent list, member delivery and program families (L5 440–520, 650–680, 850–952) and §4.0
registry (954–1030), §4.2 commands 5–7; Layer 0 §4 reserved claims (640–665), §4.5/§4.5.1, §6
headings and invalidation reasons; Layer 2 §2.9, §5.3 formula names, `weather_exposed`; Layer 3
§4.8 objective/intent pairs and `humidity_extraction` classes/outcome, §6.3.1 helper names, §6.4.1,
§4.8.3; Layer 4 §9.2–§9.3; Layer 6 §4.2, §5.2, §6.1–§6.4, §7.4, §9.3, §11; Layer 8 §4.1, §10.3.
Checked clean: every cited Layer 0/1/2/3/4/6/8 section number resolves to the intended content;
Layer 0 reserved fact claims match L5 producers (`actuator.correction`, `actuator.target_lifecycle`,
`reaction.decision.*`, `reaction.follow_up`); follow-up prepared-intent contract matches Layer 0
§4.5.1; consent audience, item tags and reissue match Layer 6 §5.2/§7.4/§9.3; `house` delivery set
matches Layer 6 §4.2; seven consent-gated descriptors match §3.2; `when_occupied_without_residents`
values match; objective/intent pairs and units in §7/§7.3 match Layer 3 §4.8; selector arithmetic
examples in §8 are correct; casa episode names match Layer 4 §9.3.

## Findings

### F-L5b-01 — Evaluation reason codes that no outcome may carry

- **Category / severity:** C / P2
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:2035` — "Outcome validation is closed: `not_triggered` has exactly `(\"trigger_not_matched\",)` as its evaluation reasons; `guards_unsatisfied` has exactly `(\"semantic_guard_unsatisfied\",)`; `abstained` has no evaluation reason and a non-empty canonical Layer-3 `AutomationSuppressionReason` tuple; `eligible` and `normal_exit` have both tuples empty."; `docs/specs/v3/layer5_action_reactions_spec.md:3664` — "A shorter absence records `absence_below_minimum` and starts nothing. A parameter whose `conservative_recovery_duration` exceeds 7 days could not schedule recovery inside the horizon: the descriptor abstains with `recovery_beyond_horizon`."; `docs/specs/v3/layer5_action_reactions_spec.md:503` — "The suppression records the evaluation reason `occupied_without_residents_pause`."; `docs/specs/v3/layer5_action_reactions_spec.md:981` — "ReactionEvaluationReasonCode = Literal[ \"trigger_not_matched\", \"semantic_guard_unsatisfied\", \"occupied_without_residents_pause\", \"absence_below_minimum\", \"recovery_beyond_horizon\", ]"
- **Owner:** Layer 5 §5.2 — its closed outcome/reason table predates the CA4-122 codes added to §4.0 and used by §3.2/§7.1.
- **Defect:** A comfort trajectory facing an 8-day recovery "abstains with `recovery_beyond_horizon`", but an `abstained` result must have no evaluation reason; a below-minimum absence or a paused activation must record a §4.0 evaluation reason, yet no outcome in §5.2 admits any of the three new codes, so every such `ReactionEvaluationResult` fails validation.
- **Proposed direction:** Extend the §5.2 outcome/reason table to say which outcome carries each CA4-122 code.
- **Confidence:** high
- **Verification:** pending

### F-L5b-02 — Weather-protection example uses a `state_transition` trigger that cannot fire after restart

- **Category / severity:** C / P2
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:4352` — "Its start criterion is the `True` state of an administrator-declared Layer-2 boolean"; `docs/specs/v3/layer5_action_reactions_spec.md:4378` — "After a restart a still-active hazard opens a new activation from fresh state."; `docs/specs/v3/layer5_action_reactions_spec.md:4389` — "trigger `state_transition(environment.wind_hazard@casa, False -> True)`"; `docs/specs/v3/layer5_action_reactions_spec.md:1941` — "missing/unavailable input or a restart/semantic-generation gap is `abstained`, never an inferred edge."; `docs/specs/v3/layer5_action_reactions_spec.md:1917` — "An ordinary nonprogrammed trigger uses one of these primitives. A step-programmed descriptor instead uses its versioned start criteria"
- **Owner:** Layer 5 §7.4 — its valid example contradicts its own start-criterion and restart rules (the §7.3 matrix lists it as step-programmed).
- **Defect:** With the example's `state_transition` trigger, a restart while wind is already above the threshold yields `abstained` (no previous/current pair), so no activation opens and nothing is secured, contradicting "a restart during the hazard secures from fresh state only" (§8, line 4495); the example also uses a primitive trigger where a step-programmed descriptor must use start criteria.
- **Proposed direction:** State the example's start as the hazard boolean's current `True` state (the start criterion), not a `state_transition` edge.
- **Confidence:** medium
- **Verification:** pending

### F-L5b-03 — Posture-check advisories: `safety` family vs Layer 6 fixed `suggestion` family

- **Category / severity:** C / P2
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:4408` — "Its namespace places its advisories in the `safety` notification family (Layer 6 §6.1): they are delivered immediately, quiet hours included, to residents only."; `docs/specs/v3/layer6_notification_spec.md:102` — "| `reaction.advisory` | `ReactionAdvisoryOccurrence` (Layer 5 §6.0) | residents, house (when `house_delivery`) | suggestion | info |"; `docs/specs/v3/layer6_notification_spec.md:243` — "Families are closed and fixed per kind (§4.2). For the three kinds that report on a Reaction's action — `reaction.follow_up`, `automation.availability` and `reaction.action_notice` — the family comes from the namespace of that Reaction's descriptor"
- **Owner:** Layer 6 §4.2/§6.1 — the kind table and the namespace rule exclude `reaction.advisory`, while §6.1's own example sentence (line 253) and Layer 5 §7.5 put posture-check advisories in `safety`.
- **Defect:** An `entry_unlocked_while_empty` advisory at 03:00 is a `suggestion` under Layer 6 §4.2 (held until quiet hours end, digested) but `safety` under Layer 5 §7.5 and the §8 posture-check acceptance ("yields a `safety` `lock_entry` advisory despite quiet hours", line 5185).
- **Proposed direction:** Make `reaction.advisory` use the namespace family (or add an explicit `safety.*` exception) in Layer 6 §4.2/§6.1.
- **Confidence:** high
- **Verification:** pending

### F-L5b-04 — §7 program-shape summary omits weather protection and posture check

- **Category / severity:** D / P3
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:3601` — "The three other trigger-driven descriptors above (`environment.solar_shading`, `environment.external_exchange` and `routine.actuation_bundle`) register `normal_exit_contract=None`"; `docs/specs/v3/layer5_action_reactions_spec.md:3613` — "`environment.air_extraction` is the third required step-programmed Initial-V3 descriptor"; `docs/specs/v3/layer5_action_reactions_spec.md:4309` — "| `safety.weather_protection` | ... | step-programmed per hazard episode; safe: `secure_for_weather` |"; `docs/specs/v3/layer5_action_reactions_spec.md:4310` — "| `safety.posture_check` | ... | trigger-driven, one activation per check instance |"
- **Owner:** Layer 5 §7 — the paragraph was not updated when §7.4/§7.5 (CA4-126) were added.
- **Defect:** The matrix has four step-programmed and four trigger-driven descriptors; the §7 paragraph enumerates three and three, so weather protection (with a normal-exit contract) and posture check fall outside its stated registrations.
- **Proposed direction:** Update the paragraph to cover all eight or defer to the §7.3 matrix.
- **Confidence:** high
- **Verification:** pending

### F-L5b-05 — Advice members restricted to two descriptors in §7.3

- **Category / severity:** D / P3
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:4339` — "Advice members (§3.2) are available only for `environment.external_exchange` and `environment.solar_shading` intents"; `docs/specs/v3/layer5_action_reactions_spec.md:864` — "Initial-V3 `advisory_intents` are `open_for_exchange` and `close_to_retain` (`environment.external_exchange`), `increase_shading` and `decrease_shading` (`environment.solar_shading`), and `check_alarm`, `lock_entry` and `close_opening` (`safety.posture_check`, §7.5)"
- **Owner:** Layer 5 §7.3 — stale after CA4-126.
- **Defect:** A `safety.posture_check` advice member is legal under §3.2 and §7.5 (line 4408) but excluded by the §7.3 statement.
- **Proposed direction:** Add `safety.posture_check` to the §7.3 sentence.
- **Confidence:** high
- **Verification:** pending

### F-L5b-06 — Acceptance says only `eligible` reaches admissibility

- **Category / severity:** D / P3
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:4854` — "Each evaluation has exactly one closed outcome. Only `eligible` reaches bundle admissibility"; `docs/specs/v3/layer5_action_reactions_spec.md:2026` — "Only `eligible` and, for its declared terminal step, `normal_exit` proceed to action admissibility."
- **Owner:** Layer 5 §8 — restatement predates `normal_exit` as an outcome.
- **Defect:** A terminal-target `normal_exit` (§6.0, lines 2426–2441) must pass whole-bundle admission; the §8 criterion would fail that case.
- **Proposed direction:** Align §8 with §5.2.
- **Confidence:** high
- **Verification:** pending

### F-L5b-07 — References to a nonexistent Layer-5 §6.2

- **Category / severity:** R / P3
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:2169` — "A failed continuation produces the existing skipped step outcome, not a replayed event or an unguarded command (§6.2)."; `docs/specs/v3/layer5_action_reactions_spec.md:2450` — "administrative disablement and resident-consent revocation remain immediate as specified in §6.2."; `docs/specs/v3/layer5_action_reactions_spec.md:5033` — "(§3.2, §5.1, §6.0, §6.2)"; `docs/specs/v3/layer5_action_reactions_spec.md:5041` — "(§3.2, §6.2)"; `docs/specs/v3/layer5_action_reactions_spec.md:5069` — "(§3.2, §6.2, §7)"; heading list — §6 contains only "### 6.0", "### 6.0.1", "### 6.1" (lines 2090, 3044, 3143).
- **Owner:** Layer 5 — stale section numbers (also at line 622, in L5a scope).
- **Defect:** The skipped-step/terminal follow-up and immediate revocation rules live in §6.0 (follow-up) and §6.1/§4.2 (revocation); §6.2 does not exist.
- **Proposed direction:** Retarget each reference to §6.0 or §6.1/§4.2.
- **Confidence:** high
- **Verification:** pending

### F-L5b-08 — Unqualified "§4.5" in the follow-up operation-id rule

- **Category / severity:** R / P3
- **Locations:** `docs/specs/v3/layer5_action_reactions_spec.md:2755` — "a later observation may change only the final occurrence fields that §4.5 permits, never the prepared payload under the same id."; Layer 5 §4 contains only §4.0, §4.1, §4.2 (lines 954, 1182, 1401); `docs/specs/v3/layer0_runtime_spec.md:1310` — "### 4.5 Unified notification delivery outbox"
- **Owner:** Layer 5 §6.0 — missing "Layer 0" qualifier.
- **Defect:** Read as a Layer-5 section, the reference resolves to nothing.
- **Proposed direction:** Write "Layer 0 §4.5.1".
- **Confidence:** high
- **Verification:** pending

### F-L5b-09 — Planned-absence horizon does not strictly exceed ceiling plus largest recovery

- **Category / severity:** O / P3
- **Locations:** `docs/specs/v3/layer2_registries_spec.md:485` — "a core-fixed horizon of **14 days**, which must exceed the ceiling of the comfort-trajectory minimum absence duration plus the largest recovery duration (Layer 5 `planned_absence_program`)"; `docs/specs/v3/layer5_action_reactions_spec.md:3655` — "floor = 24 h, ceiling = 7 days)"; `docs/specs/v3/layer5_action_reactions_spec.md:3664` — "A parameter whose `conservative_recovery_duration` exceeds 7 days could not schedule recovery inside the horizon: the descriptor abstains"
- **Owner:** Layer 5 §7.1 (or Layer 2 §2.9 wording) — Layer 2 states an obligation on Layer 5's constants.
- **Defect:** Layer 5 admits a recovery of exactly 7 days with a 7-day ceiling; 7 d + 7 d = 14 d equals, and does not exceed, the 14-day horizon Layer 2 requires.
- **Proposed direction:** Make one bound strict (recovery `>= 7 days` abstains) or relax Layer 2 to "at least".
- **Confidence:** medium
- **Verification:** pending

## Observations (not findings)

- §7.4 example: with the window held, "only the awning is retracted" while §6.0 says "A blocked member blocks its entire bundle". This is consistent only if each channel is its own bundle or the §7 alternate-bundle rule applies; §7.4 says neither explicitly.
- Line 2327 cites "CA4-13 above", but no earlier Layer-5 text names CA4-13 (it is a backlog id).
- Line 2456 says "Every typed occurrence of this section" goes to Layer 8 projections; Layer 8 §10.3 lists only proposal-review, consent and advisory occurrences (not follow-up or action notice) as pending-item inputs.
