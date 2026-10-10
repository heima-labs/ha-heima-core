# CA4-01 — Full review record

This preserves the detailed decisions, counterexamples, construct matrix and marked historical review moved from the [CA4-01 backlog summary](v3_backlog.md#ca4-01--hold-authority-and-observed-divergence). The layer specifications remain normative.

#### CA4-01 — Hold authority and observed divergence

**Reopened 2026-10-03; DONE 2026-10-04 (Codex, specification readiness).** The independent full reread found two blocking cross-layer contradictions missed by the earlier field matrix and T1–T19: nested follow-up and hold values exceeded Layer 1's depth-two storage contract (D-A), and one activation-level follow-up operation id collided when an exit covered several Actuator channels (D-B). The oversized hold-audit detail store was replaced by a proved inline bound (D-C). The user approved A1/B1/C2 on 2026-10-03; the decisions and the renewed cross-layer closure gate are recorded below. The 2026-10-02 DONE claim remains historical; this is the new closure.

**Current refinement (2026-10-02; historical closure claim):** T10/T11 pass their activation-scoped
specification counterexamples. Presence simulation follows its programmed
steps while eligible and cancels unsent work on committed return. T18 passes
its mixed-source and oversized-audit specification counterexamples after the
approved delayed-visibility rule. The final cross-layer gate and backlog
cleanup are recorded below.

**Status:** DONE (2026-10-04; specification readiness). **Historical status:** DONE was claimed on 2026-10-02 after D1–D5, B/C, finite follow-up preparation, activation-scoped normal exit, CA4-33 and delayed oversized-audit visibility were specified. T1–T19, the expanded residue gate and the 90-field construct matrix did not test the depth-two serialization rule or per-channel operation identity. Those prior checks remain evidence for their narrower claims, not a closure gate. CA4-02, CA4-17, CA4-38 and CA4-39 remain separate. This is specification work, not runtime implementation or validation. **Type:** superseded product authority model and cross-layer contract. **References:** [Layer 0 §4.1–4.5, §5.1, §6, §13](specs/v3/layer0_runtime_spec.md), [Layer 1 §3–4, §10](specs/v3/layer1_substrate_spec.md), [Layer 2 §6, §9](specs/v3/layer2_registries_spec.md), [Layer 5 §3.2, §6, §7.2, §8](specs/v3/layer5_action_reactions_spec.md), [overview](specs/v3/architecture_overview_defined_layers.md), [recap](v3_architecture_recap.md).

**D-A — APPROVED A1 on 2026-10-03 and applied; proposal rationale retained.** Layer 1 §3–4 counts containers after normalizing a frozen dataclass to its field payload: the payload object is depth 1, a field mapping such as `context` or `expected_values` is depth 2, and a mapping/list inside that field is depth 3. Scalars add no container depth. A `reaction.follow_up` value with `context.expected_facets.power=true` is already depth 3; an intent with `expected_facets.color=[255,128,0]` and a hold audit with `expected_values.color=[255,128,0]` are also depth 3. These cannot pass the declared validators, regardless of byte size. House example: a resident changes a colour light while a presence-simulation Reaction has confirmed power, brightness and RGB colour; the hold audit and subsequent follow-up must preserve that colour without storing an invalid nested value.

- **A1, recommended:** require each target-contract facet to have a bounded canonical JSON *text scalar* projection (`true`, `0.6`, `[255,128,0]`, `"heat"` encoded as strings). Staging validates that every declared facet can be projected, decoded and bounded without information loss; runtime validates the actual copied value. Keep `expected_facets`/`observed_facets` as depth-two scalar maps in the intent and `expected_values`/`observed_values` as depth-two scalar maps in the audit. Flatten the event context into reserved scalar keys such as `expected.power`, `observed.power`, with a bounded facet-name grammar and collision rejection; `context.expected_facets` cannot remain a nested map even if its values are scalar. The serialized scalar representation retains type and composite colour through canonical JSON parsing. Empty maps are legal where the existing path permits them. Retry comparisons use identical canonical bytes. Restart reads only persisted scalar text; revocation and absent observations retain their existing semantics. This adds a staging/normalization contract and changes the follow-up event context, but no new store or fact type.
- **A2:** let each target contract declare the deepest allowed facet value and reject contracts or configuration combinations that would exceed Layer 1 depth two. This works for primitive-only actuators, but rejects ordinary composite colour targets unless they are changed or encoded; the event context still needs flattening. It therefore does not solve the illustrated light alone and has a narrow product envelope.
- **A3:** introduce a separate versioned compact follow-up/audit value schema with a flat scalar facet sequence. This can satisfy depth two, but creates more type/codec surface than A1 and still needs staging bounds and cross-layer adapters.

**Overengineering check:** A1 uses one scalar representation and the current two storage contracts; no general recursive envelope or extra runtime store. It anticipates the *shape-validation* portion of CA4-28 for these target-derived projections only; CA4-28 remains open for recursive immutability and invalid-evidence handling elsewhere. Layer 1 §3.1, Layer 2 §6.1, Layer 5 §6.0 and Layer 0 §6.1 now define the flattened key grammar, scalar codec and staging bounds.

**D-B — APPROVED B1 on 2026-10-03 and applied; proposal rationale retained.** The then-current Layer 5 §6.0 assigned an operation id to an activation boundary, while Layer 0 §4.5 stored one intent and one event per Actuator/channel under that id. At the end of presence simulation, three lights can need three notices: the second distinct intent would have been rejected as a conflicting retry and two notices lost.

- **B1, recommended:** derive one opaque, domain-separated id deterministically from `(reaction_id, configuration_generation_id, reaction_activation_id, boundary_kind, boundary_identity, actuator_id, controlled_channel)`. A planned step uses its stable `planned_step_id`; a normal exit or terminal action uses its one descriptor-verified exit-boundary identity. Each channel's exact retry keeps its id; a different canonical payload under the same id still fails. Recovery finalizes each prepared channel independently as `interrupted_before_outcome`; an unprepared channel remains best effort. `notification_key` continues to include that per-channel id, so delivery deduplication cannot merge different lights. Revocation prevents commands for all channels without suppressing already committed notices. The id is generated by core, never supplied by an administrator, and its input tuple is staged/validated to avoid collisions.
- **B2:** mint a separate random id for each channel and persist the boundary-to-channel assignment before any preparation. It can work, but adds a second durable identity map and more recovery ordering without improving the observable result.
- **B3:** make one aggregate intent and notice for the entire multi-channel exit. This avoids the collision but changes the approved channel-local intent, mixes success/failure states, and makes one failed channel preparation affect the whole handoff. It is a larger contract change.

**Overengineering check:** B1 changes only identity derivation and acceptance fixtures; the existing per-channel outbox, transaction, event and delivery path remain. T20 includes three channels with one failed preparation, exact/conflicting retries, crash recovery, and distinct notification keys.

**D-C — APPROVED C2 on 2026-10-03 and applied; historical detail-store rationale retained.** The former >8 KiB hold-audit detail store needed a queue-size exception, delayed buffer visibility, orphan cleanup, digest/length checks and a typed integrity-failure read. Its purpose was to retain a complete facet/source audit when the inline fact would exceed Layer 1 §3. A multi-facet valve, HVAC or light transition could cross that cap if ids, names or values were not bounded, but a finite staged adapter/Reaction scope could prove its worst-case canonical value size instead.

- **C1, retain current store:** preserve all valid bounded detail regardless of 8 KiB, including large future adapters. Crash between detail and fact leaves an orphan; retry and typed reads require the existing digest, length, cleanup and integrity rules. This preserves compatibility but retains the most mechanisms.
- **C2, recommended:** staging computes the worst-case *complete* `HoldLifecycleValue` for each allowed adapter/scope/Reaction combination, including all facet-source maps, bounded ids, timestamps, strings and canonical scalar facet projections from D-A. It rejects a generation unless the worst case has depth at most 2 and canonical UTF-8 length at most 8 KiB. The ordinary runtime value validator remains a backstop; a contract breach is diagnostic and cannot weaken a live hold. Every valid transition is then one ordinary inline fact and ordinary queued value. This removes the detail store and its exception. It narrows acceptance of very large future facet contracts but does not truncate an accepted audit. If any dynamic field has no enforceable maximum, staging must reject rather than assume a bound.

**Overengineering check and applied replacement:** C2 reuses the Layer-1 validator and Layer-2/5 staging, with a deterministic worst-case calculator and enforceable bounds rather than a new persistence tier. Layer 0 §1–2/§4.1–4.4/§6.1/§6.4/§8/§13, Layer 1 §3–4/§10, overview §4, recap and Graphviz now use one complete inline audit fact. The former detail reference, delayed buffer visibility, orphan cleanup, digest/length checks, queue-size exception and typed detail-read path are historical only. T18 and the matrix below use staging-bound and inline-retry checks. No audit is truncated; an unprovably bounded combination is rejected before cutover.

**Historical pre-approval serialization and trace probes (superseded by the approved examples below).** These examples use ASCII-only identifiers so canonical JSON byte count equals character count; a frozen fact dataclass is counted after normalization to its field object (depth 1). Its map fields have depth 2. The then-current light `HoldLifecycleValue` example had `expected_values={"brightness":0.7,"color":[255,128,0]}` and corresponding observed colour; its complete 28-field canonical JSON was 1,414 bytes but depth 3 and invalid inline. The then-current complete `ReactionFollowUpIntent` example had `expected_facets={"power":true,"brightness":0.7,"color":[255,128,0]}` and corresponding observed facets; its 17-field JSON was 650 bytes but depth 3 and invalid as a `PersistedProjection`. The then-current complete `OperationalEventValue` example had the same two maps under `context`; its 5-field JSON was 760 bytes and depth 4 with colour (depth 3 even for `power=true`), invalid as a `HouseFact.value`. A `HoldLifecycleDetailRef` with `operation_id`, `hold_id`, `event`, 64-hex digest and `detail_bytes=1414` was 172 bytes at depth 1 and valid as a fact value, but did not repair the other two records or the inline selection at 1,414 bytes. The size estimates count value/projection bytes only, not a surrounding `HouseFact` or outbox index.

For A1, the same complete light examples replace each facet value by canonical JSON text (for example `"true"`, `"0.7"`, `"[255,128,0]"`); the fact context replaces the two facet maps with scalar `expected.power`, `expected.brightness`, `expected.color`, `observed.power`, `observed.brightness`, `observed.color` keys. Their complete canonical sizes become approximately 1,422 bytes (hold), 662 bytes (intent) and 786 bytes (event), all depth 2 or less and below 8 KiB. These are candidate-format measurements, not a claim that the current normative schemas already pass. A valve `position` expectation/observation of `1`/`0.5` and HVAC `mode`/`setpoint`/`fan_speed` of `heat`/`21.5`/`auto` versus `heat`/`19`/`low` likewise use scalar canonical JSON text in A1; their facet maps remain depth 2 and the flattened event context remains depth 2. Complete worst-case size across every staged adapter remains to be proved, not inferred from these small examples.

The valve and HVAC shapes in the preceding historical A1 candidate paragraph
were not executable Initial-V3 descriptor fixtures. The current examples linked
above replace the HVAC facets with the admitted trajectory target and mark the
valve's future-descriptor status explicitly.

| New or repeated trace | Counterexample sought | Historical finding before approval |
|---|---|---|
| T20, three-channel normal exit | Lights A/B/C need distinct notices, B's preparation times out, then process crashes; A/C must remain separately recoverable and B best effort, with no collision or merged notification key | FAIL under one activation-boundary id; B conflicts with A's intent. B1 specifies the remedy but is not applied. |
| T21, composite colour | A confirmed light target includes power/brightness/RGB; resident changes colour; hold audit, durable intent and follow-up event all survive Layer-1 validators | FAIL: current complete records above have depth 3 or 4. A1 specifies the remedy but is not applied. |
| T10/T11, exit and follow-up | A channel has a mismatched confirmed target and produces a warning or recovery uncertainty after a prepared intent | The earlier lifecycle/path result stands, but its persisted examples fail depth validation when facet maps are populated. Re-run after D-A/B. |
| T17, durable preparation | Late/uncertain prepare, terminal retirement and final fact serialize under one operation id | Per-id ordering remains coherent for one channel; the three-channel case exposes the missing id scope. Re-run after D-B. |
| T18, mixed-source hold audit | Two Reactions source distinct facets, including composite colour, and exact retry retains one complete transition | Source attribution remains specified, but colour fails inline depth validation. If D-C changes, replace its delayed-reference branch with staging-bound and inline-retry checks. Re-run after D-A/C. |

**Renewed closure gate (2026-10-04): PASS for specification readiness.** The [complete serialized light, valve and HVAC examples](specs/v3/ca4_01_serialization_examples.md) validate nine complete payloads against the exact declared field sets, canonical facet codec, depth-two/8 KiB limits, source-map keys and B1 operation-id hash. The light and HVAC cases bind valid Initial-V3 descriptors; the valve case is an explicitly illustrative future-descriptor shape and proves only generic serialization, not Initial-V3 normal-exit eligibility. Their byte/depth results are light 1615/707/909 at depth 2, valve 1238/638/804 at depth 2, and HVAC 1246/681/862 at depth 2 (hold/intent/event order). T10/T11/T17/T18 and new T20/T21 pass the counterexample review below. The matrix has 94 complete field rows, including exactly all 90 fields of its nine named types; no required field is missing or has an empty definition, producer, consumer or acceptance cell. This is a document/serialization check, not a runtime test.

The case-insensitive PCRE2 union gate used the prior expression recorded below plus `operation_id|expected_facets|observed_facets|PersistedProjection`. Its exact scope was `docs/specs/v3/*.md`, `docs/specs/v3/*.puml`, `docs/img/v3_architecture.dot`, and `docs/v3_architecture_recap.md`. After the descriptor-example, renderer-bound and architecture-diagram corrections, the 243 matching **lines** were classified against their clauses as follows; the five historical lines are Layer 0's pre-V3 expiry analogy, the recap's explicitly superseded domain model/earlier registry wording and one line in the retired Graphviz source. No live normative detail-store path or stale activation-wide follow-up identity remained in a separate semantic search.

| File | Coherent current/example | Marked history | Residue |
|---|---:|---:|---:|
| Overview | 10 | 0 | 0 |
| CA4-01 serialization examples | 15 | 0 | 0 |
| Layer 0 | 83 | 1 | 0 |
| Layer 1 | 14 | 0 | 0 |
| Layer 2 | 5 | 0 | 0 |
| Layer 3 | 24 | 0 | 0 |
| Layer 4 | 2 | 0 | 0 |
| Layer 5 | 62 | 0 | 0 |
| Recap | 18 | 3 | 0 |
| Graphviz/PlantUML | 5 | 1 | 0 |
| **Total** | **238** | **5** | **0** |

The final dependent-section reread covered Layer 0 §1–2/§4.1–4.5/§6/§8/§13, Layer 1 §3–4/§10, Layer 5 §3.2/§4.2/§6.0–6.1/§7.2/§8, and the complete overview and recap. `git diff --check` passed after the edits. CA4-18 remains TODO with its narrower independent next-job identity/rearm residual; it was not closed through CA4-01. No CA4-51+ finding was confirmed within this scope.

**Minimal contradiction:** an automation changes a dedicated hold helper without an authenticated resident edge. The old normal-cycle rule preserves the prior hold while the old helper-reconciliation rule clears it. At restart the same helper was made authoritative despite unknown origin. This conflict is superseded at its source: the resident does not operate a hold helper at all. The resident operates the ordinary device; a hold is internal expected-versus-observed difference.

**Reviewed product decision (2026-09-28; revised 2026-10-02):** one process-local hold per registered Actuator channel, only after a physically confirmed Heima expectation and a later valid differing edge. A pending or unconfirmed Heima ApplyStep is not a hold. Unknown origin still produces a temporary hold. Origin is attributed only from verified direct resident/admin command, automation trace, or integration evidence; otherwise `unknown`. A propagated HA user id alone cannot claim direct resident action. A multi-facet edge makes one hold episode; later facet changes inherit its shared release boundary without extending it. The default blocks the channel, while an admin may select changed-facet admission only where the versioned adapter declares complete effects. A core Reaction descriptor may select fixed duration or the next planned, target-changing step of that same Reaction/channel; an ordinary re-evaluation is not that step. A programmed change on any target facet releases the whole hold, even if a different facet was manually changed; this may restore the prior facet and must be explained in the admin UI. Cancellation or natural completion defaults to leave-as-observed, with resident follow-up only for an unresolved mismatch or unavailable observation. A versioned core descriptor may define a final target: on normal cancellation, release the hold and attempt that one terminal action under current admission before closing that activation; a blocked or unconfirmed action does not delay activation closure and the resident sees the observed state. Administrative disablement and consent revocation remain immediate and never admit a later final-target call. Convergence, observation loss, authority change, or restart also releases the hold. The first reading after restart or an observation gap cannot create one; normal current-policy automation resumes, including after power-on defaults. No resident-facing hold control exists. The earlier approved lighting/heating/environment domain mapping is inapplicable to this narrower scope and remains historical. The prior helper-edge, explicit/implicit, conditional-restoration, and journal/checkpoint-identity decisions are explicitly superseded for Initial V3. The user approved an asynchronous lifecycle-audit queue on 2026-09-28: a crash before the final event is written may leave an audit gap; the in-process hold remains effective until restart and is never reconstructed from that queue.

**Earlier partial review (historical; superseded by T1–T19 and the final gate below). Changed:** Layer 0 §4/§5.1/§6/§7/§8/§10/§13, Layer 1 §3, Layer 2 §6, Layer 3 §4.4.2, Layer 5 §6/§6.0.1, architecture overview and recap. **Document-level trace checks:** (1) resident turns a confirmed light off while Heima runs: one hold on that light channel is active, with verified manual origin or unknown if proof is absent; (2) another HA automation changes it: the same scope is held with automation or unknown origin; (3) resident acts during HA/Heima restart, or two bulbs power on by default after an outage: the first returned readings create no hold and current policy may act; (4) an HA service call completes without physical confirmation: outcome is unconfirmed and no hold is inferred; (5) an edge arrives after snapshot but before a later ApplyCall: the per-call fence stops unsent work; (6) repeated differing edges update origin without extending the original hold deadline. These are contract traces, not runtime tests. **Partial review:** the old helper authority has no current consumer or control surface; the frozen channel view is the sole live hold admission source. The restart, unknown-origin, unconfirmed-command, expiry, and per-call race cases above have one outcome in the current text. A search of the current Layer 0–5 specifications and recap found no remaining normative explicit/implicit-helper or conditional hold-restoration rule. `git diff --check` passed. This is a specification trace, not a runtime test. **Closure gate:** the expanded T1–T16 review below supersedes this earlier partial trace. D2 and D5 have approved core rules, but D3 follow-up production and mixed-Reaction audit still need structural decisions. T10/T11/T15/T16 and the new traces require counterexample review before a final PASS. Historical continuity and the runtime contracts remain in their separate CA4 items. **Separate remaining findings:** CA4-02 owns multi-Reaction arbitration and safety precedence; CA4-17 owns the dispatch fence; CA4-33 owns historical gap continuity; CA4-38 owns the unresolved retry-queue bound. CA4-19 and CA4-31 are DONE; CA4-32 is NOT_APPLICABLE. None reintroduces a helper as authority.

**Cross-layer contract map (2026-09-29 audit).**

| Rule | Normative owner | Repeated by | Result |
|---|---|---|---|
| One process-local channel hold after confirmed expectation and later valid divergence; evidence-based origin | Layer 0 §6 with Layer 5 §6.0.1 for confirmation | Layer 1 §1/§3, Layer 3 §4.4.2, overview, recap, runtime diagram | Consistent after R1/R6–R9/R13 and D5; only a current admitted Reaction target anchors a hold. |
| Registered channel, scope and fixed duration | Layer 2 §6; Layer 0 §6 for lifecycle | Layer 5 §6.0, overview, recap | Selective scope is coherent; one Actuator-level duration applies to all its fixed-duration channels, with independent activation deadlines (D4 approved). |
| Frozen admission, whole-bundle arbitration and dispatch fence | Layer 0 §6.1.1; Layer 5 §6.0/§6.0.1 | Layer 4 §5.1, overview | Hold admission is coherent; R14 is resolved by the common Layer-5 gates; CA4-02 owns wider arbitration. |
| Fixed expiry, next timed target change, convergence, cancellation, invalidation | Layer 0 §6 and Layer 5 §6.0 | Layer 2 §6, recap, overview | Core hold transitions agree; R15 uses the existing operational-event and Layer-6 route. |
| Restart/observation break, async lifecycle audit | Layer 0 §4/§6.3–6.4/§7/§8 | Layer 1 §3–4, Layer 5 §6.0.1, recap | No hold restoration or synchronous journal; restart diagnostic R2 and historical continuity CA4-33 are specified; retry bound CA4-38 remains. |

**Residue classification.** R1, R3, R4, R6–R11 and R18 were corrected as alignment to recorded decisions. R12's nonexistent global-hold trigger was removed from current presence-simulation prose; the historical PS-3 text is marked superseded for that clause. R13 retained the existing lifecycle fact id and analyzer source: Layer 0 §5 defines `analyzer` for derived results, and §6.1 now explicitly says the manager compares expectation with observation, while the origin field alone attributes the actor. This adds no construct. R19 overview, recap, both PlantUML files and Graphviz were checked: the runtime diagram/overview now name channel divergence holds, the support diagram has no hold-specific claim, and the Graphviz node describes process-local holds rather than a HouseFact-backed live state. R2 and R16 were approved and applied on 2026-09-30; R14, R15 and R17 are approved and applied below. R5 is a separate runtime-confirmation finding CA4-39. R4's historical continuity obligation is specified by CA4-33 without a hold-specific journal.

**Historical mechanical gate claim (superseded; 2026-09-30).** Command: `rg -n -i -e 'explicit (manual )?hold|implicit[ -]hold|hold helper|restore_eligible|trigger_state|trigger_entity_id|implicit_hold_restore_class|manual_hold\.<domain>|manual_hold\.\*|global hold|restoration_discarded|ExplicitHoldIdentity|ManualHoldJournal|journal|restor(e|ed|ation)|after_restart|downtime-gap|gap marker|durability_pending|hold checkpoint|expiry|domain-wide|functional domain|release_policy|resident_response|runtime confirmation' docs/specs/v3/*.md docs/specs/v3/*.puml docs/img/v3_architecture.dot docs/v3_architecture_recap.md`. The earlier 85-line run omitted the expanded expressions required by the independent review and cannot establish closure. CA4-38/39 remain separate issues. The enlarged gate, matrix, and counterexample review are required before CA4-01 can be DONE; T15 also depends on CA4-33.

**Contract traces (Given/When/Then; document review, not runtime tests).** Each row gives the operative clause for its When/Then result.

| Trace | Given / When / Then | Result |
|---|---|---|
| T1 | Given a confirmed light target; when a resident turns it off; then Layer 0 §6.2 opens one channel hold with verified resident origin or unknown under §6.1. | PASS |
| T2 | Given that target; when a verified external automation changes it; then §6.1–6.2 opens or updates the same channel hold with automation or unknown origin. | PASS |
| T3 | Given restart or blackout; when the first current readings arrive; then §6.3 creates no hold, Layer 0 §10 may display a non-authoritative comparison, and Layer 5 §6 re-evaluates current policy. | PASS after D1 approval |
| T4 | Given a completed HA call without timely physical match; when the pending deadline passes; then Layer 5 §6.0.1 records unconfirmed and Layer 0 §6.2 creates no hold. | PASS |
| T5 | Given a post-snapshot edge; when it precedes another HA call; then Layer 5 §6.0's per-call fence stops unsent work. | PASS, CA4-17 separately open |
| T6 | Given an active hold; when later valid divergent edges arrive; then Layer 0 §6.2 updates origin/facets without extending its boundary. | PASS |
| T7 | Given two facets in one edge at 10:00 and a further facet at 10:29; when the 30-minute deadline arrives; then §6.2 creates one activation/operation id, one update and releases all at 10:30. | PASS |
| T8 | Given selective scope with complete adapter effects; when a call intersects divergent facets it blocks, a disjoint call passes; incomplete effects reject selective staging under Layer 2 §6 and Layer 5 §6.0. | PASS after D2; hold and physical-state checks use distinct mandatory admission reasons |
| T9 | Given next-step mode; when ordinary re-evaluation or another Reaction steps, hold stays; when the same Reaction/channel's later different target is due, Layer 5 §6.0 releases before fresh admission even if guards then block. | PASS |
| T10 | Given cancellation/completion of one activation without final target and its current-run confirmed target; a remaining mismatch or unavailable state requests one Layer-6 follow-up, while a complete observed match requests none. A previously expired hold does not itself suppress a remaining mismatch. | PASS 2026-10-04: the populated channel intent and flattened event pass Layer-1 depth/size validation; the exit uses a distinct operation id for each channel. |
| T11 | Given normal cancellation of one activation with final target; Layer 5 releases, refreshes, tries once before closing that activation, and permits pending observation but no later call from it. Skipped/unconfirmed outcomes pass through Layer 6; a computed final target may differ from preparation. | PASS 2026-10-04: the prepared identity stays frozen per channel while the fresh target is an occurrence field; revocation admits no call. |
| T12 | Given administrative disablement or consent revocation; when committed, Layer 0 §6.2 invalidates and Layer 5 §6.2 admits no terminal call. | PASS |
| T13 | Given observation loss during a hold; when first valid read returns, Layer 0 §6.2–6.3 invalidates then creates no new hold from that read. | PASS |
| T14 | Given a reload changing channel/scope/adapter; when the generation cuts over, §6.1.1 invalidates affected entries in canonical order before new admission. | PASS; CA4-27 owns global cutover |
| T15 | Given a crash before an asynchronous hold-audit write, the durable watermark starts a process gap; a fresh completed HA intake closes it. Layer 3 excludes/censors every sample window crossing that gap and restores no live hold. | PASS: crash, short-gap, first-cycle and all historical-consumer fixtures cross-checked |
| T16 | Given an admin/recovery ApplyStep physically confirmed; when a later divergent edge arrives, a standalone command has no Reaction hold anchor; a current admitted Reaction target retains its own identity regardless of the matching command source. | PASS: Layer 0 §6.2 and Layer 5 §6.0.1 acceptance cross-check |

| T17 | Given one `reaction.follow_up` operation and an uncertain preparation or event write, Layer 6 reconciles by the operation id: an exact retry retains one event and a changed payload is rejected. A crash before finalization yields only a conservative interrupted outcome; a lost delivery acknowledgement may repeat the HA notice. | PASS 2026-10-04: the operation id is per boundary/channel, the first prepared payload is frozen, and the fact/intent transaction and delivery acknowledgement have separate stated guarantees. |
| T18 | Given another Reaction confirms a second facet that joins an active selective channel hold, transition audit identifies both expectations and only the original owning Reaction step releases the shared hold. | PASS 2026-10-04: one bounded inline value records both facet sources, including canonical colour text; staging rejects any unbounded or >8 KiB composition and exact retry yields one fact. |
| T19 | Given restart with a fresh completed HA intake where light A is readable and valve B is explicitly unavailable, the process gap closes at that cycle barrier; A may act and later complete A-only windows, while B commands and B-dependent windows remain blocked/incomplete until a fresh valid B observation. | PASS: Layer 0 §4.4/§13 and Layer 3 §9 cross-check |
| T20 | Given a presence-simulation exit on lights A/B/C, when A and C prepare durably, B's prepare times out, and the process crashes before finalization, then A/C each recover one `interrupted_before_outcome` event under distinct keys; B retains only the stated best-effort guarantee. Exact retries do not duplicate either durable fact; a changed retry fails. | PASS 2026-10-04: Layer 5 §6.0/§8 derives three boundary/channel hashes; Layer 0 §4.5/§13 keeps independent rows and serialization. |
| T21 | Given a confirmed power/brightness/RGB target, when a resident changes colour and a later exit needs follow-up, then the complete hold fact, prepared intent and flattened event preserve typed colour through canonical JSON text at depth two. | PASS 2026-10-04: Layer 0 §6.1/§6.4, Layer 1 §3/§3.1 and Layer 5 §6.0 match the complete light serialization example; staging checks the worst case, not only that example. |

**Renewed T10/T11/T17/T18/T20/T21 counterexample review (2026-10-04; specification only).**

| Trace | Counterexample sought | Contract that rejects or bounds it |
|---|---|---|
| T10 | Three lights end one activation with mismatches, but one activation-wide id merges their notices; an old pre-restart target alone also causes a notice. | Layer 5 §6.0 derives a separate id per channel and requires a current-run confirmed target; Layer 0 §4.5 stores each separately. |
| T11 | A fresh snapshot changes the terminal target after preparation, or revocation lands before the final call. | Layer 5 §6.0 freezes only boundary identity in the intent, allows the final target in the occurrence, and rechecks authority before dispatch; Layer 0 §4.5 retires a disqualified intent. |
| T17 | A timed-out preparation commits after a best-effort event or after success retirement, and a retry creates a second fact. | Layer 0 §4.5 serializes prepare/final fact/retirement by the same channel operation id, rejects changed payloads and keeps one durable fact. A lost HA delivery acknowledgement may still repeat the visible notice under the documented at-least-once guarantee. |
| T18 | Reaction B's RGB facet joins A's held power facet, producing a nested value or >8 KiB audit; a crash/retry duplicates it. | Layer 0 §6.1 proves the complete mixed-source maximum at staging, stores canonical colour as scalar text and §6.4 accepts only an inline depth-two value with durable operation-id deduplication. A pre-durable crash may lose that audit and is represented by the continuity gap. |
| T20 | A/B/C share one exit id, B's failed prepare blocks A/C, or recovery merges their delivery keys. | Layer 5 §6.0 includes Actuator/channel in the hash; Layer 0 §4.5 independently prepares, finalizes and keys each row. B's missing prepared row cannot gain a crash-recoverable guarantee. |
| T21 | RGB `[255,128,0]` becomes a nested list in a fact/projection, or quoted JSON text is mistaken for an untyped colour string. | Layer 5 §6.0 requires a lossless canonical scalar codec and round-trip validation; Layer 1 §3.1 flattens event keys. The complete light payloads in the serialization examples measure 1615/707/909 bytes at depth two. |

**Historical T1–T19 counterexample pass (specification only; updated 2026-10-02, superseded for T10/T11/T17/T18 on 2026-10-03).** These cases test
whether two plausible implementations could disagree; they do not run code.

| Trace | Counterexample sought | Contract that rejects it |
|---|---|---|
| T1 | HA carries a user id inherited from an automation, so a light change looks manual. | Layer 0 §6.1 requires verified direct-command proof; otherwise origin is external automation or `unknown`, while divergence still holds. |
| T2 | An automation changes the same channel while the resident-origin hold is live. | Layer 0 §6.2 updates the single hold and origin trail; it mints no parallel hold. |
| T3 | A bulb power-on default or resident action during restart differs from the last target. | Layer 0 §6.3 treats the first returned value as an epoch baseline; current policy can resume without a hold. |
| T4 | An HA service call succeeds, its deadline expires, then a late matching read arrives. | Layer 5 §6.0.1 keeps the terminal `unconfirmed` outcome; that read may confirm a current expectation, but only a later distinct differing edge opens a hold. |
| T5 | A resident edge lands after admission but before the second call in a bundle. | Layer 5 §6.0's per-call fence rechecks before each unsent call; CA4-17 separately tracks fence implementation lifecycle. |
| T6 | A second divergent edge arrives one second before the hold deadline. | Layer 0 §6.2 updates the shared set and origin without rearming its AtJob. |
| T7 | One observation changes two facets, but a producer calls the Manager twice. | Layer 5 §6.0.1 and Layer 0 §6.2 require one atomic channel transition and one operation id. |
| T8 | A brightness call also powers on a held light, despite an apparently disjoint brightness target. | Layer 5 §6.0 checks the complete declared affected-facet set; incomplete translation fails staging. |
| T9 | B's step or A's second current-bundle member is mistaken for A's future release step. | Layer 5 §6.0 requires A's later timed step identity and changed target on that channel. |
| T10 | A hold expired earlier but a valve still differs at normal exit; alternatively only a stale pre-restart target differs. | Layer 5 §6.0 requires a current-run confirmed target and unresolved current observation; expiry neither forces nor suppresses notice. |
| T11 | The fresh post-release snapshot computes a different final target, or consent is revoked after intent preparation. | Layer 5 §6.0 allows mutable outcome target while Layer 0 §4.5 compares stable identities; revocation retires the intent and admits no call. |
| T12 | A prepared terminal intent is mistaken for permission to send after admin disablement. | Layer 5 §6.0/§6.2 makes revocation immediate; Layer 0 §4.5 outbox recovery never replays a call. |
| T13 | The first read after unavailability is still different from the old expected value. | Layer 0 §6.3 invalidates the old hold and treats that read as a new epoch baseline, not a fresh divergence edge. |
| T14 | A scope/adapter change occurs during a decision cycle. | Layer 0 §6.1.1 invalidates affected entries before publishing the new frozen view; CA4-27 tracks the wider cutover contract. |
| T15 | A two-minute restart is shorter than a freshness threshold, and both occupancy readings match. | Layer 0 §4.4 reports a process gap regardless of freshness; Layer 3 §4.2/§4.4.1–4.4.3/§4.8.1 censors or excludes crossing windows. |
| T16 | An admin sets exactly the target of a current Reaction, versus a standalone admin-only target. | Layer 0 §6.2 and Layer 5 §6.0.1 use the current admitted Reaction decision for the first case and create no anchor in the second. |
| T17 | Fact commit succeeds but the producer retries after an uncertain acknowledgement; HA delivery acknowledgement is also lost. | Layer 0 §4.5 keeps one durable fact by operation id; Layer 6 may deliver twice under its stated at-least-once guarantee. |
| T18 | One edge changes A and B facets; B's next target replaces its held facet; or a 9 KiB mixed-source audit waits five minutes for detail durability while a query, retry or crash occurs. | Layer 0 §6.2 emits one transition with both sources; B's step cannot release A's boundary, and actual B supersession removes only B's obsolete facet. Layer 0 §4.1/§6.4 keeps the typed complete value in the ordered queue and the live hold in its separate view; no generic reference is visible until the detail is verified. Layer 1 §4 permits only this typed queue-size exception, and §13 fixtures cover delayed publication, original order, retention, retry and interruption. |
| T19 | The first fresh cycle reads light A but explicitly reports valve B unavailable. | Layer 0 §4.4 closes only the global gap at the complete intake barrier; B-dependent history remains incomplete while A can resume. |

All results above are historical 2026-10-02 document-level checks. Their
detail-reference branch and T10/T11/T17/T18 storage conclusions were
superseded by D-A/B/C on 2026-10-03. The new closure gate is recorded below.

**Expanded gate, historical preliminary count before B/C and CA4-33 application (2026-10-01):** The required union regex (the earlier expression plus `manual-hold|manual_hold(?!\.lifecycle)|physical-state|confirmed_physical_state|guard capabilit|bounded retry|CA4-[0-9]+|follow_up|follow-up|observation_coverage|expectation source`, with PCRE2 and case-insensitive matching) returned 130 matching lines at that earlier revision. B/C and CA4-33 later changed the contracts; the final 2026-10-02 classification below supersedes this count. The old 85-line gate could not prove zero residues.

**Expanded gate verification (repeated 2026-10-02 after the delayed-visibility decision).**
The exact union search now returns 184 matching lines.
The exact case-insensitive PCRE2 union is the historical expression above plus
`manual-hold|manual_hold(?!\.lifecycle)|physical-state|confirmed_physical_state|guard capabilit|bounded retry|CA4-[0-9]+|follow_up|follow-up|observation_coverage|expectation source`.
Scope: `docs/specs/v3/*.md`, `docs/specs/v3/*.puml`,
`docs/img/v3_architecture.dot`, `docs/v3_architecture_recap.md`. Every matched
line was classified against its surrounding clause; an additional semantic
search covered hyphen/underscore/space variants of hold, physical state,
guard capability, functional domain and expectation source, plus first-observation
wording. Counts are matching lines, not occurrences within a line:

| File | Coherent current rule (1) | Marked history (2) | Residue (3) |
|---|---:|---:|---:|
| Layer 0 | 71 | 2 | 0 |
| Layer 1 | 7 | 0 | 0 |
| Layer 2 | 3 | 1 | 0 |
| Layer 3 | 24 | 0 | 0 |
| Layer 4 | 2 | 0 | 0 |
| Layer 5 | 50 | 0 | 0 |
| Overview | 7 | 0 | 0 |
| Recap | 15 | 2 | 0 |
| PlantUML and Graphviz | 0 | 0 | 0 |
| **Total** | **179** | **5** | **0** |

The matched historical lines are Layer 0's pre-V3 timer comparison and
retired `resident_response` source comment, Layer 2's corrected old
FusionStrategy recap, and the recap's superseded hold model and earlier
FusionStrategy account. The semantic follow-up search also found Layer 5's
explicitly retired functional-domain admission mapping; its hyphenated form
does not match this exact union. Negative current rules such as “no hold helper”
or “manual hold is not a descriptor guard” are class (1), not historical.
The gate passes as a document search; the separate field-level matrix and
affected-section reread are recorded in the final closure verification below.

**Structural decision record (historical proposal and application stages; final verification below).** The previous T10/T11 PASS labels described intended behavior before the implementable event contract and final counterexample review were completed.

**B — `reaction.follow_up` production and delivery.** Owners: Layer 5 §6.0 (outcome), Layer 1 §3.1 (event envelope), Layer 0 §4/§6.4 (claim and persistence), Layer 6 (resident rendering/delivery). Example: a resident leaves a valve at 50%; the owning Reaction's 10:30 close step is skipped by a guard, and its event write is retried after timeout. Current text permits two durable events with one `notification_key`, and either Layer 5 or Layer 6 may render different text. An earlier expired hold also leaves it unclear whether a later Reaction exit deserves a notice.

- **Option 1 (historical initial recommendation; superseded 2026-10-01):** keep `OperationalEventValue` and the existing fact type; add a bounded typed and validated `ReactionFollowUpContext` serialized into its `context`. Include a stable outcome/operation id, closed outcome, Reaction/generation, Actuator/channel, causal hold id, later-step status, and canonical observed facets or explicit unavailability. Reuse §6.4's in-flight payload check and durable `(fact_type, operation_id)` uniqueness for exact retries; distinct occurrences still append. Layer 6 owns a versioned pure renderer supplied to the production adapter at bootstrap, so the Layer-5 producer can persist the already rendered title/message required by Layer 1 without owning their wording. Define hold-related as an active hold of this Reaction/channel immediately before its release/exit boundary, carrying the hold id through a delayed terminal outcome; an expired earlier hold alone does not qualify. Proposed severity: `info` for exit without final target, `warning` for skipped/unconfirmed action; proposed delivery key: fact type plus outcome id. The prior update/clear promise is removed because events are append-only.
- **Option 2 (selected 2026-10-01):** Layer 6 produces the fact from a new typed transient Layer-5 occurrence. Rendering ownership is direct, but the fact claim moves and a new cross-layer occurrence and ordering contract are needed.
- **Option 3:** retain generic `context` and rely on delivery-key deduplication. This is superficially simplest but cannot prevent duplicate audit records, validate meaning, or settle owner and exit semantics.

Option 1 resolves the real retry and conflicting-renderer cases with one typed context and an existing dedup mechanism. It must be tested for all five outcomes, same/different-payload retries, restart after commit, exit without an active hold, skipped final target, delayed unconfirmed terminal outcome after disablement, revocation, and unrelated concurrent Reaction. It adds no second envelope or fact type; bootstrap injection must avoid a runtime dependency cycle. **Overlap check:** `OperationalEventValue`, `HeimaEvent`, `notification_key` and hold-audit operation identity already exist. The new context narrows the generic payload; the retry check reuses the hold-audit mechanism. No threshold, calibration or approval default is invented.

**B reassessment (2026-10-01; historical proposal, superseded by the approved decision below).** After rereading Layer 5 §2, Layer 1 §3.1, Layer 3's `automation.availability` precedent and the overview's Layer-5→6 boundary, Option 2 is now preferred over the former Option 1. Layer 5 is expressly excluded from resident rendering; Layer 1 requires rendered title/message *inside* the durable fact. Injecting a Layer-6 renderer into Layer 5 at bootstrap makes ownership harder to explain and still lets Layer 5 produce resident text indirectly. The simpler coherent path is one typed transient `ReactionFollowUpOccurrence` from Layer 5 to Layer 6, parallel in shape of responsibility (not semantics) to `AvailabilitySuppressionOccurrence`: Layer 5 fixes outcome, causal hold/Reaction/channel, current observed values/unavailability and stable operation id; Layer 6 validates, renders title/message, derives severity and `notification_key`, constructs/persists the existing `OperationalEventValue` fact, and delivers it. The core `FactTypeClaim` owner for `reaction.follow_up` would move to Layer 6. There is no second durable envelope, resident switch, or new fact type. Layer 0's §6.4 exact-retry operation-id check can be reused by this fact type without conflating distinct occurrences or relying on delivery-key deduplication. A crash after Layer 5 computes an occurrence but before its durable event write remains a separate delivery-reliability decision: accepting best-effort loss matches the current asynchronous event boundary but may miss a resident warning; durable outbox/replay would be stronger and costlier. No guarantee is inferred from the approved asynchronous *hold-audit* policy. **Overlap check:** the availability occurrence and `OperationalEventValue` already separate operational cause from rendering; the new occurrence is needed only to carry follow-up-specific fields and must not duplicate the delivery envelope.

**B product decisions and application (historical stage, 2026-10-01).** The user selected Option 2:
Layer 5 emits a typed outcome and Layer 6 alone renders, produces the existing fact, and
delivers it. An intent must be durably prepared before a qualifying step/normal exit
advances when storage is healthy. If preparation fails, current guarded action proceeds
with `follow_up_durability_degraded`; the recovery guarantee cannot apply to that notice.
A prepared intent left without a committed outcome by a crash yields a conservative
`interrupted_before_outcome` warning and no command replay. At normal exit without a final
target, an unresolved observed mismatch or unavailable state warrants follow-up even if
the hold expired; a verified complete match does not. Every follow-up is `warning` and
uses the stable outcome operation id in its notification key. The fact is idempotent under
that id; HA delivery is at least once and may duplicate after an uncertain acknowledgement.
These are approved structural and product decisions, applied in Layer 0 §4/§4.5/§13,
Layer 1 §3.1/§10, Layer 5 §6.0/§8, overview and recap. They do not make CA4-01 DONE:
consumer cross-checks, B counterexamples, C, and CA4-33/T15 remain. The earlier Option-1
recommendation and the D3 producer wording below are historical for ownership; reuse of
the Layer-1 event mapping and Layer-6 pipeline remains approved.

**B construct trace (partial CA4-01 matrix).** `ReactionFollowUpPath`,
`ReactionFollowUpOutcome`, `ReactionFollowUpIntent`, and
`ReactionFollowUpOccurrence` are defined in Layer 5 §6.0; Layer 5 produces the
intent/outcome, Layer 6 validates and consumes both, and Layer 5 §8 tests the six
closed outcomes plus schema rejection. The sole `reaction.follow_up` fact claim is
Layer 0 §4, with Layer 6 as producer and the existing Layer-1 §3.1
`OperationalEventValue`/`HeimaEvent` mapping as durable/delivery consumer; Layer 0
§13 tests operation-id retry, interruption, degraded preparation, and retention of
undelivered outbox payload, while Layer 1 §10 tests exact context mapping. Layer 0
§4.5 owns the outbox transaction and replay; Layer 6 owns warning text and delivery.
This is a B-specific trace, not the required complete CA4-01/CA4-33 construct matrix.

**B counterexample review (historical partial specification stage, 2026-10-01).** For T10, the
counterexample was an expired hold followed by a still-divergent valve at Reaction exit:
§6.0 now tests the current-run confirmed target and latest observation rather than
requiring an active hold. The opposite counterexample was a stale pre-restart target:
that alone cannot qualify after Recovery. For T11, a final target calculated from the
fresh snapshot can differ from the pre-release intent projection; only the immutable
boundary identities must match. Revocation retires the intent without a terminal call.
For T17, a crash after intent preparation but before an outcome yields the closed
uncertainty outcome, while an atomic event-plus-ready commit and the durable operation
key reject a second fact; delivery acknowledgement can still be lost and repeat the
external notice. A storage failure at preparation permits action and explicitly drops
the crash-recovery guarantee for that one notice. These counterexamples no longer
produce two contradictory *specified* outcomes, but a final CA4-01 PASS still requires
the full cross-layer matrix and expanded gate; no runtime behavior has been verified.

**C — mixed-Reaction expectation source in one selective channel hold (APPROVED and applied 2026-10-01; T18 PASS).** Owners: Layer 0 §6.1–6.2 (hold and audit), Layer 5 §6.0 (step identity). Example: at 10:00 Reaction A's light-power target is held after a resident switches it off. At 10:05 Reaction B confirms brightness on the same channel; the resident changes brightness at 10:06. The earlier single audit value named only A, so one implementation could falsely attribute B's expected brightness to A while another left it unattributed. B's later step could also be mistaken for A's release step.

- **Option 1 (recommended):** preserve one channel hold and A's original release boundary. Add a bounded per-facet expectation-source projection to each lifecycle transition carrying affected facets, with Reaction id/generation and confirmed target/step identity. B's step does not release A's hold; A's qualifying step releases the whole shared hold.
- **Option 2:** forbid selective scope on any channel that may have multiple Reaction owners, forcing channel-wide blocking. This avoids a mixed active hold only if staging can prove exclusivity over generations; otherwise audit ambiguity remains.
- **Option 3:** use a hold per Reaction. This contradicts the agreed single shared channel boundary and multiplies arbitration/expiry states.

Option 1 preserves current live behavior and makes the audit truthful with one bounded projection. Test a second Reaction's facet, a simultaneous mixed-facet observation, A/B step order, cancellation/revocation, restart and unavailability. **Overlap check:** `HoldLifecycleValue.reaction_id` already identifies A as release owner but cannot name B as a facet's expectation source; extending that value avoids a second hold or journal. This case is relevant now because selective scope and multi-Reaction channels are already specified.

**C application and counterexample review.** Layer 0 §6.1 extends `HoldLifecycleValue`
with five shallow maps keyed by canonical facet: Reaction id, generation,
activation id, confirmed target fingerprint, and optional confirmed scheduled
step id. Values that fit Layer 1 §3's fact-value limit remain inline; larger
valid values use the approved detail reference without a nested event schema. Layer 5
§6.0 supplies the verified source per involved facet; Layer 0 validates identical
keys in the mandatory maps and preserves the first hold's release owner and
boundary. Layer 0 §13 and Layer 5 §8 have Given/When/Then fixtures. Counterexample:
if B's brightness step is mistaken for the shared boundary, B could release A's
power hold at 10:07 and cause an unwanted power command; the explicit owner rule
blocks that release. If one edge changes power and brightness together, separate
per-facet calls could mint two holds; the atomic channel transition produces one
hold and audit operation. Release-owner revocation, observation loss and restart
invalidate rather than restore it; loss of B's expectation follows the
facet-only rule below. These are specification traces, not runtime tests.

**C construct trace (partial CA4-01 matrix).** `HoldLifecycleValue`'s
`expectation_reaction_ids`, `expectation_generation_ids`,
`expectation_activation_ids`,
`expectation_target_fingerprints` and optional `expectation_step_ids` are defined
in Layer 0 §6.1. Layer 5 §6.0 produces their verified per-facet content; Layer 0
validates, retains and emits them in `manual_hold.lifecycle`; Layer 1 §3 validates
the shallow copied value and Persistence consumes it. Layer 0 §13, Layer 1 §10
and Layer 5 §8 test a second Reaction, one mixed edge, A/B step order, invalid
map keys, size and source provenance. The shared CA4-01/33 matrix appears below;
its 90 typed fields have individually checked rows.

**C follow-on structural decision (APPROVED and applied 2026-10-01; T18 PASS).** The mixed-source
case exposes a target-lifecycle corner: A opens a selective hold on power, B's
brightness joins, A's power later physically converges, then B's planned target
is superseded or B is cancelled while brightness remains divergent. Keeping B's
old facet until A's boundary protects a target that is no longer current;
closing the whole hold on B's change gives B the release power reserved for A;
calling the terminal event `converged` falsely claims a physical match.
Layer 0 §6.1–6.2 owns the live set and lifecycle reason; Layer 5 §6.0 owns
whether B's admitted target remains current. The simplest truthful option is
to remove only B's obsolete facet, keep A's original boundary while other
facets remain, and use one closed `expectation_superseded` invalidation reason
if that removal empties the set without physical convergence. Other choices
are to invalidate the entire hold on any source loss, or keep the obsolete
facet through the shared boundary; each loses either A's release authority or
the current-target invariant. The selected option adds one enum value and
one subset update, no new hold or timer. It must be checked for a B step
blocked by the active hold, B cancellation/revocation, simultaneous A/B
changes, restart and unavailability. **Overlap check:** `converged` denotes an
observed match and `authority_revoked` denotes authority loss; neither truthfully
names ordinary replacement of B's target. The user approved facet-only removal
and `expectation_superseded` for terminal invalidation. Layer 0 §6.1–6.2/§13
and Layer 5 §6.0/§8 now define and test the distinction. A merely due or
rejected B candidate does not supersede its earlier admitted expectation.
The new `HoldLifecycleValue.invalidation_reason` member is defined in Layer 0
§6.1; Layer 5 produces the supersession signal, Layer 0 emits the terminal
fact, Layer 1/Persistence retains it, and Layer 0 §13/Layer 5 §8 cover the
one-facet-left and last-facet cases. This extends the partial C construct trace.

**Historical CA4-01 oversized-audit decision (approved 2026-10-02; superseded by C2 on 2026-10-03).** A
complete `HoldLifecycleValue` that fits Layer 1's 8 KiB fact-value limit stays
inline. When it exceeds that limit, the same `manual_hold.lifecycle` event fact
carries a bounded `HoldLifecycleDetailRef`; a separate typed store holds the
complete canonical detail. The background writer durably writes detail before
fact, so a crash between writes can leave only a collectible orphan, never a
dangling fact. The same operation id and digest prevent changed-payload retry;
retention prunes detail after its fact, and the continuity watermark waits for
both writes. The detail store counts toward the existing global storage
watermark but has no 8 KiB per-detail cap. This follows the user's preference
for a separate store only when the complete fact value exceeds 8 KiB. It
supersedes the earlier staging-size rejection and accepted healthy-storage
audit-loss options. Layer 0 §4.3–4.4/§6.1/§6.4/§13, Layer 1 §3/§10, overview
and recap carry the contract. A corrupt or missing retained detail is an
integrity failure, never a complete audit result. This is a specification
decision, not a runtime implementation.

**CA4-01 preliminary verification (historical 2026-10-02; superseded by the later T18 pass).** The expanded line-level gate
and 79-field matrix below were complete for the constructs reviewed at that point.
T10–T11 passed a descriptor-boundary and two-activation specification
counterexample pass. At that earlier point, T18's large-detail queue and size
boundary still required a fresh counterexample pass.
The older partial-review and preliminary-gate paragraphs in this item
record earlier stages and do not describe the current closure state. The
Layer 0 §4.2–4.5/§6.1–6.4/§13, Layer 1 §3/§10, Layer 5 §6/§8, overview,
recap and this backlog were reread for the approved reference path.

**CA4-01 short-term visibility and queue-shape decision (APPROVED;
T18 PASS 2026-10-02).** The approved separate store for details
over 8 KiB requires the asynchronous queue to capture the complete immutable
transition before disk I/O. Layer 0 §4.1 previously said every accepted
transition immediately enters the short-term `HouseFact` buffer and every
non-fact retained projection, including the retry queue, obeys Layer 1's 8 KiB
`PersistedProjection` contract. Layer 0 §4.2/§6.4 instead delay construction
of a large reference fact until detail durability and retain the full larger
value in the queue. Example: at 10:00 a resident changes a multi-facet valve;
the canonical audit is 9 KiB and the detail writer stalls until 10:05. One
implementation exposes the reference event in the short-term history at
10:00 with an in-memory detail; another exposes nothing until 10:05, even
though both have the same live hold. The first violates the stated queue-size
rule; the second violates the immediate-buffer rule unless this audit case is
an explicit exception.

- **Option A (selected 2026-10-02):** declare the complete typed
  `HoldLifecycleValue` a narrow exception to `PersistedProjection` only while
  queued for the separate detail writer, with copied immutable fields and
  resource accounting under CA4-38. Keep the already drafted delayed generic
  fact visibility for oversized audit. It changes no live hold behavior,
  provides no false short-term audit fact during detail failure, and needs no
  second in-memory resolver. A short-term consumer may see a large audit only
  after detail durability and must not use audit absence for live admission.
- **Option B:** put the small reference fact in the buffer immediately and
  resolve its detail from the pending queue until disk commit, then from the
  detail store. This preserves uniform event-buffer timing but adds two
  resolver states and a queue-to-read dependency; the same typed queue-size
  exception is still necessary.
- **Option C:** write the detail synchronously before buffering the fact. This
  restores the old immediate-fact shape only by blocking the evaluation path
  and contradicts the approved asynchronous hold-audit boundary.

**Applied contract:** Layer 0 §4.1/§4.2/§6.4 and Layer 1 §4 make the
oversized `HoldLifecycleValue` the sole typed exception to the ordinary
8 KiB non-fact queue projection. The background writer verifies detail
durability before constructing and exposing the small reference fact in
short-term history; durable fact append follows in its reserved original
order. A slow or failed detail write does not expose a dangling reference or
weaken the live `HoldAdmissionView`. Layer 0 §13 and Layer 1 §10 cover the
exception, delay, failure, retry and crash cases. CA4-38 still owns the
aggregate queue budget and overflow policy; this decision supplies no
unreviewed numeric limit or loss guarantee.

**Edge/overlap check:** the frozen `HoldAdmissionView` already supplies live
authority, so audit-buffer timing cannot decide a command. The ordinary
ordered queue and `durability_pending` diagnostic already exist; no new live
hold type, fact type, or resident control is needed. A crash before fact commit
still loses only the approved audit tail, while a detail write failure keeps
the live hold effective. The choice affects generic short-term audit readers
and the queue's payload-size exception. After the selected rule was propagated
and its counterexamples checked, T18 passed as a specification trace. The
final CA4-01 closure gate is recorded below.

**CA4-01 follow-up preparation deadline (APPROVED and specified; 2026-10-02).** Layer 5 §6.0
and Layer 0 §4.5 previously required a durable `prepared` acknowledgement
before a scheduled step or normal exit advanced on healthy storage, without an
upper bound for a write that neither completed nor failed. Such a write could
stall the scheduled step indefinitely. Layer 5 now has a finite, versioned core-owned
preparation deadline, shared by all descriptors and validated at bootstrap;
expiry is an uncertain acknowledgement,
reported as `follow_up_durability_degraded`, after which the step or exit
proceeds through ordinary admission. The existing stable operation id and
reconciliation path handle a late write, including a final event or a no-event
retirement; a retry must not create another intent or event. The exact technical duration belongs to the versioned core
implementation, not administrator configuration. Acceptance covers a never-returning
writer, a late successful write, a crash after the deadline, and immediate
administrative revocation.

**CA4-01 normal-exit boundary (APPROVED and specified; T10/T11 PASS, 2026-10-02).** Layer 5
§3.2/§6.0 now requires a versioned core descriptor to declare a pure
`normal_exit_contract` or `None`. Its typed result identifies the Reaction
generation, frozen snapshot, closed outcome and validated terminal evidence.
Normal cancellation requires an explicit descriptor-declared cancellation
signal; natural completion requires proof of no later step and no ongoing
target. Finishing a command or one-shot bundle, temporary input unavailability,
a guard veto and ordinary re-evaluation do not prove an exit. Immediate
authority loss uses revocation. A descriptor without a normal-exit contract
uses fixed-duration holds; `next_reaction_step` staging requires both a bounded
future-step identity and a provable normal-exit contract so a canceled program
cannot strand its hold. No administrator control or second event type is added.
The user clarified that the configured Reaction remains available while each
qualifying absence starts and ends its own activation. Layer 5 now mints one
process-local `reaction_activation_id` per start and carries it through jobs,
evaluations, calls, leases, terminal results and follow-up intents/outcomes.
Layer 0 freezes the opening activation on the channel hold and records it in
audit, including a per-facet source id when another Reaction joins. A normal
exit or future step matches Reaction, generation and activation; it closes
only that activation, leaving authorization for a later qualifying start.
Presence simulation and planned comfort trajectory distinguish a verified
return, selected-plan removal/replacement and valid interval end from source
unavailability or guard veto. The four trigger-driven Initial-V3 descriptors
use fixed-duration holds and no normal-exit rule. T10/T11 passed their
historical lifecycle counterexamples; the then-current 90 fields of nine typed audit,
coverage, follow-up and exit-result structures have exact rows below, while
other newly changed activation fields have separate rows. No runtime
implementation is claimed.

**CA4-01/33 construct matrix, updated for A1/B1/C2 (2026-10-03).** Each row names
its definition, producer, consumer and a fixture location. The matrix is a
cross-layer specification check, not evidence that runtime code implements it.

| Construct or changed rule | Definition | Producer | Consumer | Acceptance fixture |
|---|---|---|---|---|
| Restart comparison is diagnostic only (D1) | Layer 0 §6.3/§10 | Layer 0 Recovery | Admin diagnostic surface; Layer 5 evaluates current policy separately | Layer 0 §13 restart/power-on case |
| Common hold and physical-state gates, separate reasons (D2) | Layer 5 §3.2/§6.0; Layer 3 §7 | Layer 0 hold view and Layer 5 physical matcher | Layer 5 admission and Layer 3 availability occurrence | Layer 5 §8 environmental guard/hold/unreadable fixture |
| One channel hold, divergent facet set, release owner and boundary | Layer 0 §6.1–6.2 | Layer 0 Manager from Layer 5 confirmed transition | Layer 0 frozen view; Layer 5 admission | Layer 0 §13 multifacet, expiry and next-step fixtures; Layer 5 §8 |
| `HoldOrigin`, `HoldOriginProof`, `observation_context` | Layer 0 §6.1 | Verified ingress and Layer 0 Manager | Persistence audit and provenance diagnostics | Layer 0 §13 verified/unknown, break fixtures |
| `HoldAdmissionEntry` and `HoldAdmissionView` fields/fingerprints | Layer 0 §6.1.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 scope/fingerprint and Layer 5 §8 arbitration fixtures |
| `HoldLifecycleValue` identity, state, reasons, maps, fingerprints and `manual_hold.lifecycle` fact | Layer 0 §6.1/§6.4 | Layer 0 Manager | Persistence audit; Layer 5 live admission uses only the separate frozen view | Layer 0 §13 transition/retry/size fixtures; Layer 1 §10 |
| Bounded canonical facet-text codec and staging proof (A1/C2) | Layer 2 §6.1; Layer 5 §6.0; Layer 0 §6.1/§6.4; Layer 1 §3–4 | Core target contract and Layer 0/5 staging | Complete inline hold fact, intent and Layer-6 event | Layer 0 §13 8 KiB boundary; Layer 1 §10; Layer 5 §8; complete serialization examples |
| Per-boundary/channel operation identity (B1) | Layer 5 §6.0; Layer 0 §4.5 | Layer 5 core | Layer 6 outbox/recovery/delivery | Layer 0 §13 and Layer 5 §8 three-channel fixture |
| Finite follow-up intent preparation deadline and degraded advance | Layer 5 §6.0; Layer 0 §4.5 | Layer 5 boundary and Layer 6 durable-intent adapter | Layer 5 scheduled step/exit; Layer 6 recovery | Layer 5 §8 never-returning/late writer; Layer 0 §13 crash and idempotency fixtures |
| Presence-simulation planned sequence and early-return stop | Layer 5 §7.2 | Versioned core episode generator; Layer 4 committed return | Layer 5 scheduler/dispatch; Layer 0 hold lifecycle | Layer 5 §7.2.1 planned off, early return and between-call fence fixtures |
| Normal-cancellation withdrawal before unsent calls | Layer 5 §6.0 | Layer 5 descriptor evaluator and ordered coordinator | Layer 5 per-call fence; Layer 6 follow-up preparation follows | Layer 5 §7.2.1 committed return between calls with pending intent fixture |
| Five per-facet source maps and `expectation_superseded` reason (C) | Layer 0 §6.1–6.2 | Layer 5 verified expectation and supersession; Layer 0 Manager | Persistence audit; Layer 0 live set | Layer 0 §13 mixed-edge, B-step and terminal reason; Layer 1 §10; Layer 5 §8 |
| Actuator-level `hold_duration` and independent channel deadlines (D4) | Layer 2 §6; Layer 0 §6.2 | Layer 2 staged Actuator; Layer 0 AtJob | Layer 0 Manager; Layer 5 admission | Layer 0 §13 two-channel fixture; Layer 2 §9 |
| `RegisteredReactionDescriptor.normal_exit_contract` | Layer 5 §3.2 | Versioned core registry | Layer 5 staging/evaluator | Layer 5 §8 missing-contract and fixed-duration fixtures; Layer 2 §9 |
| `ReactionNormalExitResult` including activation identity | Layer 5 §3.2/§6.0 | Layer 5 evaluator using the descriptor rule | Layer 0 hold release; Layer 5 follow-up | Layer 5 §8 schema, two-activation, one-shot, exhausted stream, unavailable source, guard and revocation fixtures; Layer 0 §13 |
| Reaction-only current admitted expectation (D5) | Layer 0 §6.1–6.2; Layer 5 §6.0.1 | Layer 5 admitted decision and physical confirmation | Layer 0 Manager; Layer 3 correction anchor | Layer 0 §13 standalone admin/recovery fixture; Layer 5 §8 |
| `ReactionFollowUpPath` and `ReactionFollowUpOutcome` | Layer 5 §6.0 | Layer 5 boundary resolution | Layer 6 validator/rendering | Layer 5 §8 six outcomes and invalid combinations |
| `ReactionFollowUpIntent` fields and durable prepared state | Layer 5 §6.0; Layer 0 §4.5 | Layer 5 identity/last observation; Layer 6 outbox adapter | Layer 6 recovery/finalization | Layer 0 §13 crash, mismatch, degraded write; Layer 5 §8 |
| `ReactionFollowUpOccurrence` fields and interruption outcome | Layer 5 §6.0 | Layer 5 result; Layer 6 only for recovery interruption | Layer 6 validator, renderer and event adapter | Layer 5 §8 six outcomes; Layer 1 §10 mapping |
| `reaction.follow_up` fact claim, `OperationalEventValue` context, severity/key, retry and delivery | Layer 0 §4/§4.5; Layer 1 §3.1; Layer 5 §6.0 | Layer 6 sole fact producer | Persistence audit; Layer 6 HA delivery | Layer 0 §13 one fact/crash/delivery; Layer 1 §10 exact keys; Layer 5 §8 |
| `ObservationCoverageStatus`, `ObservationGapReason`, `ObservationCoverage.reasons/first_incomplete_at` | Layer 0 §4.4 | Layer 0 historical read | Layer 3 sample builder and model consumers | Layer 0 §13 closed reason/boundary fixture; Layer 3 §9 |
| `HistoricalReadResult.records/retention_coverage/observation_coverage` | Layer 0 §4.4 | Layer 0 Persistence | Layer 3 declared historical readers | Layer 0 §13 independent coverage fixture; Layer 3 §9 |
| Watermark, process gap and fresh-cycle closure | Layer 0 §4.4 | Layer 0 Persistence/HA intake barrier | Historical read; Layer 3 learning | Layer 0 §13 clean/crash/cached/unavailable fixtures |
| Fixed-window rejection, survival right-censor and correction/routine/environmental exclusion | Layer 3 §4.2/§4.4.1–4.4.3/§4.8.1 | Layer 3 shared builder and respective models | Layer 3 training and inference artifacts | Layer 3 §9 consumer-specific fixtures |
| Full `TrainingSpan` identity with gap-affected samples excluded | Layer 3 §5.2 | Layer 3 scheduled inspection | Layer 3 rebuild/publish gate | Layer 3 §9 full-span fixture |

**Field-level matrix expansion.** Every field below has its own row; the type rows above retain lifecycle and enum rules. A row states the normative definition, producer, consumer and validating fixture.

| Field | Definition | Producer | Consumer | Acceptance |
|---|---|---|---|---|
| `HoldAdmissionEntry.actuator_id` | Layer 0 §6.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionEntry.controlled_channel` | Layer 0 §6.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionEntry.hold_id` | Layer 0 §6.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionEntry.divergent_facets` | Layer 0 §6.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionEntry.scope` | Layer 0 §6.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionEntry.expires_at` | Layer 0 §6.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionView.entries` | Layer 0 §6.1.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionView.actuator_generation_fingerprint` | Layer 0 §6.1.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldAdmissionView.fingerprint` | Layer 0 §6.1.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission | Layer 0 §13 frozen-view fixture; Layer 5 §8 |
| `HoldLifecycleValue.operation_id` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.hold_id` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.actuator_id` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.controlled_channel` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.divergent_facets` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.event` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.release_reason` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.invalidation_reason` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.scope` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.release_mode` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.expires_at` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.reaction_id` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.reaction_generation_id` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.anchor_step_id` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.anchor_target_fingerprint` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.origin` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.origin_evidence` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.observation_context` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.expected_values` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Inline Persistence audit | Layer 0 §13; Layer 1 §10; light/valve/HVAC canonical-text examples |
| `HoldLifecycleValue.observed_values` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Inline Persistence audit | Layer 0 §13; Layer 1 §10; light/valve/HVAC canonical-text examples |
| `HoldLifecycleValue.expectation_reaction_ids` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.expectation_generation_ids` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.expectation_target_fingerprints` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.expectation_step_ids` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.expected_fingerprint` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.observed_fingerprint` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 exact lifecycle fixture; Layer 1 §10 |
| `ObservationCoverage.status` | Layer 0 §4.4 | Layer 0 historical read | Layer 3 declared history consumers | Layer 0 §13 coverage fixture; Layer 3 §9 |
| `ObservationCoverage.reasons` | Layer 0 §4.4 | Layer 0 historical read | Layer 3 declared history consumers | Layer 0 §13 coverage fixture; Layer 3 §9 |
| `ObservationCoverage.first_incomplete_at` | Layer 0 §4.4 | Layer 0 historical read | Layer 3 declared history consumers | Layer 0 §13 coverage fixture; Layer 3 §9 |
| `HistoricalReadResult.records` | Layer 0 §4.4 | Layer 0 Persistence | Layer 3 declared history consumers | Layer 0 §13 independent coverage fixture; Layer 3 §9 |
| `HistoricalReadResult.retention_coverage` | Layer 0 §4.4 | Layer 0 Persistence | Layer 3 declared history consumers | Layer 0 §13 independent coverage fixture; Layer 3 §9 |
| `HistoricalReadResult.observation_coverage` | Layer 0 §4.4 | Layer 0 Persistence | Layer 3 declared history consumers | Layer 0 §13 independent coverage fixture; Layer 3 §9 |
| `ReactionFollowUpIntent.operation_id` | Layer 5 §6.0 | Core boundary/channel SHA-256 derivation; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 and Layer 0 §13 three-channel fixture |
| `ReactionFollowUpIntent.reaction_id` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.configuration_generation_id` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.actuator_id` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.controlled_channel` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.subject` | Layer 5 §6.0 | Layer 5 typed Location; Layer 6 persists scalar LocationKey text | Layer 6 validator/outbox recovery | Layer 5 §8 and complete serialization examples, including rooms key |
| `ReactionFollowUpIntent.path` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.hold_id` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.planned_step_id` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.later_step_remains` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.expected_facets` | Layer 5 §6.0 | Layer 5 bounded scalar codec; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8; Layer 1 §10; complete serialization examples |
| `ReactionFollowUpIntent.observed_facets` | Layer 5 §6.0 | Layer 5 bounded scalar codec; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8; Layer 1 §10; complete serialization examples |
| `ReactionFollowUpIntent.observation_available` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.observed_at` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.observation_epoch_id` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpIntent.prepared_at` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema fixture; Layer 0 §13 |
| `ReactionFollowUpOccurrence.operation_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.reaction_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.configuration_generation_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.actuator_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.controlled_channel` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.subject` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.path` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.outcome` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.hold_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.planned_step_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.later_step_remains` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.expected_facets` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.observed_facets` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.observation_available` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.observed_at` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.observation_epoch_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `ReactionFollowUpOccurrence.occurred_at` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema fixture; Layer 1 §10 |
| `OperationalEventValue.notification_key` | Layer 1 §3.1; Layer 5 §6.0 | Layer 6 follow-up adapter from per-channel operation id | Layer 6 delivery deduplication; Persistence audit | Layer 1 §10 and Layer 0 §13 three-channel fixture |
| `OperationalEventValue.severity` | Layer 1 §3.1; Layer 5 §6.0 | Layer 6 follow-up adapter | Layer 6 routing; Persistence audit | Layer 1 §10 warning severity fixture |
| `OperationalEventValue.title` | Layer 1 §3.1; Layer 5 §6.0 | Layer 6 bounded renderer | Layer 6 resident delivery; Persistence audit | Layer 1 §10 and complete serialization examples |
| `OperationalEventValue.message` | Layer 1 §3.1; Layer 5 §6.0 | Layer 6 bounded renderer | Layer 6 resident delivery; Persistence audit | Layer 1 §10 and complete serialization examples |
| `OperationalEventValue.context` | Layer 1 §3.1; Layer 5 §6.0 | Layer 6 closed scalar context adapter | Layer 6 resident delivery; Persistence audit | Layer 1 §10 depth-two/facet-key fixture and complete serialization examples |
| `RegisteredReactionDescriptor.normal_exit_contract` | Layer 5 §3.2 | Versioned core descriptor registry | Layer 5 staging and activation evaluator | Layer 5 §8 fixed/next-step staging and terminal-evidence fixtures |
| `ReactionNormalExitResult.reaction_id` | Layer 5 §3.2 | Layer 5 descriptor evaluator | Layer 0 release validation; Layer 5 follow-up | Layer 5 §8 terminal schema and two-activation fixture |
| `ReactionNormalExitResult.configuration_generation_id` | Layer 5 §3.2 | Layer 5 descriptor evaluator | Layer 0 release validation; Layer 5 follow-up | Layer 5 §8 terminal schema and two-activation fixture |
| `ReactionNormalExitResult.reaction_activation_id` | Layer 5 §3.2 | Layer 5 descriptor evaluator | Layer 0 release validation; Layer 5 follow-up | Layer 5 §8 terminal schema and two-activation fixture |
| `ReactionNormalExitResult.snapshot_id` | Layer 5 §3.2 | Layer 5 descriptor evaluator | Layer 0 release validation; Layer 5 follow-up | Layer 5 §8 terminal schema fixture |
| `ReactionNormalExitResult.outcome` | Layer 5 §3.2 | Layer 5 descriptor evaluator | Layer 0 release validation; Layer 5 follow-up | Layer 5 §8 closed-outcome fixture |
| `ReactionNormalExitResult.evidence_fingerprint` | Layer 5 §3.2 | Layer 5 descriptor evaluator | Layer 0 release validation; Layer 5 follow-up | Layer 5 §8 valid/invalid terminal-evidence fixture |
| `ReactionEvaluationResult.reaction_activation_id` | Layer 5 §5.2 | Layer 5 evaluator | Layer 5 action admission/audit | Layer 5 §8 two-activation evaluation fixture |
| `CommandLease.reaction_activation_id` | Layer 5 §6.0 | Layer 5 channel coordinator | Layer 5 ownership view and dispatch fence | Layer 5 §8 stale-activation lease fixture |
| `ApplyStep.reaction_activation_id` | Layer 5 §6.0.1 | Layer 5 action compiler | Layer 5 dispatch fence and execution audit | Layer 5 §8 stale-activation call fixture |
| `HoldAdmissionEntry.release_owner_activation_id` | Layer 0 §6.1 | Layer 0 Manager | Layer 4 snapshot; Layer 5 admission/release | Layer 0 §13 two-activation frozen-view fixture |
| `HoldLifecycleValue.reaction_activation_id` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 two-activation lifecycle fixture; Layer 1 §10 |
| `HoldLifecycleValue.expectation_activation_ids` | Layer 0 §6.1 | Layer 0 Manager from Layer 5 verified transition | Persistence lifecycle audit | Layer 0 §13 per-facet source-map fixture; Layer 1 §10 |
| `ReactionFollowUpIntent.reaction_activation_id` | Layer 5 §6.0 | Layer 5 boundary; Layer 6 durable preparation | Layer 6 validator/outbox recovery | Layer 5 §8 exact schema/two-activation fixture; Layer 0 §13 |
| `ReactionFollowUpOccurrence.reaction_activation_id` | Layer 5 §6.0 | Layer 5 outcome; Layer 6 recovery interruption | Layer 6 validator/event adapter | Layer 5 §8 exact schema/two-activation fixture; Layer 1 §10 |

**Closed vocabulary and fact-rule matrix.** Each listed enum or inline literal has a producer, consumer and fixture; the field table above covers its storage position.

| Construct | Definition | Producer | Consumer | Acceptance |
|---|---|---|---|---|
| `HoldOrigin` | Layer 0 §6.1 | Verified ingress; Layer 0 Manager | Lifecycle audit | Layer 0 §13 verified/unknown origin |
| `HoldOriginProof` | Layer 0 §6.1 | Verified ingress; Layer 0 Manager | Lifecycle audit | Layer 0 §13 direct/automation/integration/unknown proof |
| `HoldLifecycleValue.event` | Layer 0 §6.1 | Layer 0 Manager | Persistence lifecycle audit | Layer 0 §13 activated/updated/converged/expired/released/invalidated |
| `HoldLifecycleValue.release_reason` | Layer 0 §6.1 | Layer 0 Manager | Persistence lifecycle audit | Layer 0 §13 next-step/cancelled/completed |
| `HoldLifecycleValue.invalidation_reason` | Layer 0 §6.1 | Layer 0 Manager | Persistence lifecycle audit | Layer 0 §13 lost/config/revoked/rebound/superseded |
| `HoldLifecycleValue.scope/release_mode` | Layer 0 §6.1; Layer 2 §6 | Layer 2 staging; Layer 0 Manager | Layer 5 admission/release | Layer 0 §13 and Layer 5 §8 |
| `ObservationCoverageStatus` | Layer 0 §4.4 | Layer 0 historical read | Layer 3 history consumers | Layer 0 §13 complete/incomplete |
| `ObservationGapReason` | Layer 0 §4.4 | Layer 0 historical read | Layer 3 history consumers | Layer 0 §13 closed reasons |
| `ReactionFollowUpPath` | Layer 5 §6.0 | Layer 5 boundary | Layer 6 validator | Layer 5 §8 compatible paths |
| `ReactionFollowUpOutcome` | Layer 5 §6.0 | Layer 5 result; Layer 6 recovery | Layer 6 validator/event adapter | Layer 5 §8 six outcomes |

The expanded line-level gate, complete matrix and touched-section reread are
recorded in this item; they are specification checks, not runtime tests.

**Structural-decision register (historical 2026-09-30 stage).** D1–D5 were approved as product decisions; at that stage D3 implementation contracts and propagation were incomplete, so approval alone was not closure evidence. The later B decision and final matrix supersede that status.

- **D1 / R2 — restart diagnostic.** Layer 0 §6.3 names `after_restart` without a destination/type while `HoldLifecycleValue.observation_context` excludes it. Recommend reuse of Layer 0 §10's non-authoritative diagnostic surface for post-break mismatches, with no hold lifecycle event; alternative is a new typed recovery event. Check overlap: §10 already provides diagnostics, whereas a lifecycle event would falsely imply a live hold. State: APPROVED and applied (2026-09-30); Layer 0 §6.3/§10 use the existing diagnostics surface and add no type or event.
- **D2 / R14 — admission ownership.** Layer 5 §3.2 registers `manual_hold` and `confirmed_physical_state` as guard capabilities, but §6.0 maps them to distinct admission reasons and §7.2 says they are not descriptor guards. The approved correction removes both from the environmental guard capability registry and keeps the existing mandatory core Layer-5 admission checks. A hold produces `manual_hold_active`, an unverifiable physical state produces `actuator_state_unconfirmed`, and neither adds `action_guard_active` solely for the same condition. Check overlap: `HoldAdmissionView` and PendingApply/physical confirmation already carry the needed state; a new guard type duplicates them. CA4-02 remains open. State: APPROVED and applied (2026-09-30): the two common gates are mandatory and removed from the descriptor guard registry; only their own admission reasons apply.
- **D3 / R15 — resident follow-up notice (historical ownership wording; superseded by B decision above).** Layer 0 §6.2 and Layer 5 §6.0 require notices without a typed path to Layer 6. Reuse the Layer-1 operational-event mapping: Layer 5 produces the approved `reaction.follow_up` event fact with `OperationalEventValue`, and Layer 6 delivers its derived `HeimaEvent`. `AvailabilitySuppressionOccurrence` describes an automation availability episode and Layer5DiagnosticRegistry is admin-facing; neither carries this follow-up outcome. A diagnostics-only option is simpler but fails the resident-notice requirement. State: APPROVED and applied (2026-09-30): reuse `OperationalEventValue`/`HeimaEvent`, one `reaction.follow_up` event type, and the existing Layer-6 delivery pipeline; no separate hold envelope.
- **D4 / R16 — duration granularity.** Layer 2 §6 stores `hold_duration` on Actuator, while holds and scopes are per channel. Simplest recommendation is to state that one configured duration applies to every fixed-duration channel of that Actuator; a per-channel field is justified only by a concrete requirement for distinct deadlines. Check overlap: current `Actuator.hold_duration` already supplies the value, so a new field duplicates it unless channel-specific durations are required. State: APPROVED and applied (2026-09-30); Layer 0 §6.2 and Layer 2 §6 make the shared value and independent channel deadlines explicit.
- **D5 / R17 — non-Reaction expectations.** Layer 0 §6.1 requires Reaction id/generation/target fingerprint, but `ApplyStepSourceKind` includes admin and recovery commands. Approved rule: a hold protects a current admitted Reaction target, regardless of whether that exact target was physically achieved by its own call, an admin action, or recovery. A standalone admin/recovery ApplyStep without a unique current Reaction decision establishes no hold anchor; its later divergence remains an ordinary observed state. If a recovery reconciliation does represent a current Reaction decision, retain that Reaction identity rather than treating its `ApplyStepSource.kind="recovery"` alone as the hold anchor. Alternative: generalize `HoldLifecycleValue` to permit non-Reaction anchors with fixed-duration release, adding optional Reaction fields and source rules. Check overlap: Layer 5's admitted decision and `already_satisfied`/PendingApply confirmation already supply the first option's anchor, while `ApplyStepSource` alone proves who sent a call but not which Reaction target it protects. The rejected broader option would add schema/state complexity and might block an unrelated future Reaction after a direct admin action. State: APPROVED and applied (2026-09-30): only a current admitted Reaction target anchors a hold; matching external physical state can confirm it, while standalone admin and recovery-only one-time commands do not create a Reaction identity.

**This pass changed:** Layer 0 §4.3/§5/§6.1/§6.2/§6.3/§10; Layer 1 §1/§3/§4/§10; Layer 2 §6/§7; Layer 5 §7.2; overview, runtime-authority diagram, recap, and this backlog. Residue cleanup aligned existing text to recorded decisions; approved D1 and D4 clarified diagnostic routing and Actuator-level duration without adding a type, field, enum, interface, or cross-layer contract. The overlap check found Layer 0 §10 and `Actuator.hold_duration` already sufficient. D2/D3/D5 reuse existing common admission, operational-event, and Reaction decision contracts. The earlier Layer 0/2/3/4/5 hold work remains uncommitted and preserved.

**D4 contract trace:** Given one Actuator with two fixed-duration channels and a shared 30-minute setting, when holds activate at 10:00 and 10:10, Layer 2 §6 supplies the same Window to both and Layer 0 §6.2 arms independent AtJobs; the first expires at 10:30 and the second at 10:40. This is a document trace, not a runtime test. D1's restart trace is T3 above.

**Historical CA4-01 closure verification (2026-10-02; superseded by the 2026-10-03 reopening).** The
expanded case-insensitive PCRE2 union and scope recorded above returned 184
matching lines: 179 coherent current rules, five explicitly historical lines,
zero residues. A separate semantic search checked hyphen, underscore and
space forms of hold, physical state, guard capability, functional domain,
expectation source and first returned observation; the retired Layer-5
functional-domain mapping is explicitly historical. The shared construct
matrix has 129 data rows with no empty definition, producer, consumer or
acceptance cell; every one of the 90 fields of its nine targeted typed
structures has an individual row. T1–T19 pass the document counterexample
review, including activation-scoped T10/T11, interruption-dependent T15,
mixed-source and delayed-detail T18, and unreadable-channel T19. The affected
Layer-0 §4.1–4.5/§6.1–6.4/§13, Layer-1 §3–4/§10, Layer-2 §6/§9,
Layer-5 §3.2/§6/§7.2/§8, overview, recap and this backlog were reread; the
previously reviewed Layer-3 historical consumers and architecture diagrams
retain their CA4-33 and hold cross-references. `git diff --check` passed.
These are specification checks, not executable tests or runtime validation.
CA4-02/17/38/39 keep the separate boundaries stated below.

**Remaining boundaries (updated 2026-10-04).** CA4-01 and CA4-33 are DONE as specifications. CA4-02 owns simultaneous Reaction arbitration and safety precedence; CA4-17 owns dispatch-fence completion; CA4-38 owns retry-queue budget/overflow; R5 remains isolated in CA4-39. No runtime implementation or validation was performed.
