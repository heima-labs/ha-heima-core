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
| CA4-138 (G2) | F-L0-01, F-L0-02, F-X1-01, F-X1-03, F-X2-01–04, F-X3-02 | `f0f39f5` |
| CA4-139 (G3) | F-X3-01, F-X5-03, F-L3a-03, F-X7-01 | `068126e` |
| CA4-140 (G4) | F-L2-01, F-L2-02, F-L3a-02, F-X9-04, F-L8-07 | `e9f0760` |
| CA4-141 (G5) | F-L3b-02, F-X6-01, F-X5-01, F-X5-02, F-L3a-08, F-L4-01 | `d03766c` |
| CA4-142 (G6) | F-L5a-01, F-L5a-02, F-L5a-04, F-L5b-01, F-L5b-02 | `96e2b17` |
| CA4-143 (G7) | F-L0-03 (+F-L6-05), F-L6-02, F-L6-03, F-L6-04, F-L6-06 | `6418e5f` |
| CA4-144 (G8) | F-X9-02, F-X9-03, F-X9-05 | `0468f4a` |
| CA4-145 (P3, L0/L1) | 25 P3 findings owned by Layer 0 or Layer 1 | `2167544` |
| CA4-146 (P3, L2/L3) | 13 P3 findings owned by Layer 2 or Layer 3 | `3e0895e` |
| CA4-147 (P3, L4/L5) | 9 P3 findings owned by Layer 4 or Layer 5 | commit "docs: fix Layer 4 and Layer 5 P3 findings (CA4-147)" |

All four P1 are resolved. Next CA4 id: **CA4-148**.

## P2 groups

| Group | Theme | Findings | Status |
|---|---|---|---|
| G1 | Layer 7 integration | (see CA4-137) | done |
| G2 | Layer-0 contracts toward upper layers | F-L0-01, F-L0-02, F-X1-01, F-X1-03, F-X2-01, F-X2-02, F-X2-03, F-X2-04, F-X3-02 | done (CA4-138) |
| G3 | Generations and dependency index | F-X3-01, F-X5-03, F-L3a-03, F-X7-01 | done (CA4-139) |
| G4 | People and presence | F-L2-01, F-L2-02, F-L3a-02, F-X9-04, F-L8-07 | done (CA4-140) |
| G5 | Learning ↔ Reaction contracts | F-L3b-02, F-X6-01, F-X5-01, F-X5-02, F-L3a-08, F-L4-01 | done (CA4-141) |
| G6 | Layer-5 descriptor rules | F-L5a-01, F-L5a-02, F-L5a-04, F-L5b-01, F-L5b-02 | done (CA4-142) |
| G7 | Notifications | F-L0-03, F-L6-02, F-L6-03, F-L6-04, F-L6-06 | done (CA4-143) |
| G8 | Layer-8 governance surface | F-X9-02, F-X9-03, F-X9-05 | done (CA4-144) |

After the P2 groups: the P3 findings in bulk per layer (`findings.md`, severity P3, verification
`confirmed`, not a duplicate, not resolved). The verification files also list a few unverified "New
candidates" (A, C) to consider at the end.

## Next step

All P2 groups are done (CA4-137–144); Layer 0/1 P3 done (CA4-145), Layer 2/3 P3 done (CA4-146), Layer 4/5 P3 done (CA4-147). Next: the remaining P3 findings in bulk per owner layer (Layer 6 onward, then overview/recap) (`findings.md`,
severity P3, verification `confirmed`, not a duplicate, not resolved), wording only, presented per
layer for cumulative approval; then the unverified "New candidates" of the verification files.
