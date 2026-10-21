# Audit triage status

Operational handoff for the triage step (unit T). A new session resumes from this file, the index
`findings.md` and the verification files; it needs no earlier chat.

## How triage works

- Confirmed, non-duplicate findings are resolved as CA4 issues: P1 one at a time, P2 by thematic
  group, P3 in bulk per layer (wording only, cumulative approval after the developer sees the list).
- For each issue: impact record first (existing decisions, gap, overlap check "does this construct
  overlap something existing?", owners, scenarios), then explicit developer approval ("procedi")
  before any specification edit. One product question at a time, with options and a recommendation.
- Before recommending an option, verify it against how other layers already solved the same
  problem and say so; weigh Heima's responsiveness requirement (hot-path latency, fast event
  response) for every choice.
- Each resolved issue: owning spec edits, backlog entry (`docs/v3_backlog.md`, CA4 format, newest
  first under the CA4-126 area), review record `docs/specs/v3/reviews/CA4-<n>.md`, a
  `reviewed_slices` entry in `contract_registry.json`, the findings marked `resolved in CA4-<n>` in
  `findings.md`, `python3 scripts/check_v3_specs.py` green, one commit with trailer
  `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`. No push without request.
- Respond to the developer in Italian; write specs, backlog, reviews and commits in English.
- Codex works only in the implementation worktree and must not edit this worktree; F-L0-06 was
  nevertheless fixed in `e92234c` and kept by the developer.

## Done

| Issue | Findings resolved | Commit |
|---|---|---|
| (external) | F-L0-06 | `e92234c` |
| CA4-133 | F-L3a-01, F-L3b-03, F-L3b-04 | `0193748` |
| CA4-134 | F-L5b-03, F-L6-01 | `3b07379` |
| CA4-135 | F-X9-01, F-X3-05 | `ef28253` |
| CA4-136 | F-L5a-03, F-L8-01 | `4c6ba3f` |
| CA4-137 (G1) | F-L7-01–06, F-L8-02, F-X8-01–04, F-X8-08 | `88886c0` |

All four P1 are resolved. Next CA4 id: **CA4-138**.

## P2 groups

| Group | Theme | Findings | Status |
|---|---|---|---|
| G1 | Layer 7 integration | (see CA4-137) | done |
| G2 | Layer-0 contracts toward upper layers | F-L0-01, F-L0-02, F-X1-01, F-X1-03, F-X2-01, F-X2-02, F-X2-03, F-X2-04, F-X3-02 | in progress |
| G3 | Generations and dependency index | F-X3-01, F-X5-03, F-L3a-03, F-X7-01 | todo |
| G4 | People and presence | F-L2-01, F-L2-02, F-L3a-02, F-X9-04, F-L8-07 | todo |
| G5 | Learning ↔ Reaction contracts | F-L3b-02, F-X6-01, F-X5-01, F-X5-02, F-L3a-08, F-L4-01 | todo |
| G6 | Layer-5 descriptor rules | F-L5a-01, F-L5a-02, F-L5a-04, F-L5b-01, F-L5b-02 | todo |
| G7 | Notifications | F-L0-03, F-L6-02, F-L6-03, F-L6-04, F-L6-06 | todo |
| G8 | Layer-8 governance surface | F-X9-02, F-X9-03, F-X9-05 | todo |

After the P2 groups: the P3 findings in bulk per layer (`findings.md`, severity P3, verification
`confirmed`, not a duplicate, not resolved). The verification files also list a few unverified "New
candidates" (A, C) to consider at the end.

## G2 state (2026-10-21)

**Proposed mechanical corrections, presented, awaiting explicit approval:**
- F-L0-01: restrict "durable history never seeds this view" (Layer 0 §4.1) to unclean or mismatched
  restarts and to new or impacted keys; clean restart stays pre-hydrated (§4.1, §13, 2026-09-09).
- F-L0-02: "every class creates a hold" (Layer 0 §5, §13) becomes "every class can open a hold when
  the edge qualifies under §6.2".
- F-X1-01: follow the existing outbox/hold precedent: the record (outbox record, recovery-target
  snapshot) is a bounded typed storage envelope; only the producer payload is a
  `PersistedProjection`; nested values are canonical JSON text (`facet -> canonical JSON text`, as
  `observed_facets` and `proposed_facets`), keeping depth 2.
- F-X1-03: `entity_id` is part of the Actuator execution semantic fingerprint (Layer 2), so an entity
  change discards the recovery snapshot by the existing mismatch rule; Layer 0 §7.4 also discards the
  snapshot of a channel absent from the active generation; drop the undefined "entity delta".
- F-X2-03: add `correlation_id` to the `InferenceSignal` common fields and the closed
  `IndirectSemanticAssistSignal` payload (Layer 3), as Layer 0 §5.2 requires.
- F-X2-04: add Heima process CPU time and the engine CPU share to `RuntimeHealthSnapshot`
  (Layer 0 §9), since Layer 3 consumes only that snapshot.

**Decided:**
- F-X2-01 (developer-approved 2026-10-21, option 1): only Layer 5 reads recovery state, through
  `FrozenRecoveryView`; Layer 0 §11 states that semantic resolvers receive cycle identity and time
  only (Layer 4 §5.1). The `CLAUDE.md` invariant ("available") stays true: available to the layer
  that declares it. Rejected: a recovery input in Layer 4 with no consumer.

**Open, to ask one at a time:**
1. F-X2-02: a live Layer-3 `indirect.semantic_assist.v1` emitter computes `runtime_resolvable`
   features from a "declared bounded buffer", but Layer 0's only frozen in-cycle history read
   (`FrozenHistoryView`, §4.1) is declared and read by Layer 5. Planned recommendation: let the
   Layer-3 emitter declare `HistoryViewRequirement`s frozen at the same `CycleInputBarrier` (reuse,
   bounded, already designed for the hot path); alternative: restrict those features to current and
   previous-cycle values. Verify Layer 0 §4.1 and Layer 3 §3/§6.3 wording before asking.
2. F-X3-02: Layer 0 §7.4.1 says Layer 5 supplies the recovery-confirmation proposal (subject,
   `proposed_facets`, `proposal_fingerprint`) and that an approval re-enters Layer-5 admission, but
   Layer 5 §6.0 defines no such hand-off. Draft a short Layer-5 §6.0 subsection from the fields Layer 0
   already fixes (§7.4.1 `RecoveryConfirmationRequest`, `proposed_facets` codec) and present it.

Then apply G2 as one issue (CA4-138) after "procedi".
