# Audit coverage

Status: `todo`, `in progress (<date>)`, `done (<date>)`. One pass takes one unit.

## Mechanical

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| M | `scripts/audit_v3_mechanical.py` over all authoritative layers, overview and recap | done (2026-10-20) | candidates only | 9 unresolved section references, 82 identifiers without a formal definition, 0 conflicting duplicate types; see `mechanical.md`. Classified in the verification step. |

## Internal coherence, one layer or half-layer per unit

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| L0 | `layer0_runtime_spec.md` | done (2026-10-20) | 7 (P1 1, P2 3, P3 3) | §1–§13 against cited passages and §13 criteria; previous-cycle hydration and hold-opening contradictions. |
| L1 | `layer1_substrate_spec.md` | done (2026-10-20) | 6 (P3 6) | Whole layer plus cited sections in L0, L2, L3, L5, L6; drift and dangling references only. |
| L2 | `layer2_registries_spec.md` | done (2026-10-20) | 8 (P2 3, P3 5) | §1–§9 rules against acceptance criteria and every cited cross-layer section. |
| L3a | `layer3_learning_spec.md` §1–§4 | done (2026-10-20) | 8 (P1 1, P2 3, P3 4) | §1–§4 against cited L0, L1, L2, L4, L5, L7; shadow requirement, person-related list. |
| L3b | `layer3_learning_spec.md` §5–end | done (2026-10-20) | 4 (P1 1, P2 2, P3 1) | §5–end, cross-references, CA4-130 constants, closed lists, obligations on L0–L7. |
| L4 | `layer4_domain_spec.md` | done (2026-10-20) | 3 (P2 2, P3 1) | §1–§10 against cited L0, L1, L2, L3, L5; activity slots, evaluator key, restart wording. |
| L5a | `layer5_action_reactions_spec.md` §1–§4 | done (2026-10-20) | 10 (P2 4, P3 6) | §1–§4 registries, guard contracts, lifecycles, commands against L0–L4, L6, L8 and L5 §6–§7. |
| L5b | `layer5_action_reactions_spec.md` §5–end | done (2026-10-20) | 9 (P2 3, P3 6) | §5–§8 against cited L0, L2, L3, L4, L6, L8 and L5 §3.2/§4.0/§4.2. |
| L6 | `layer6_notification_spec.md` | done (2026-10-20) | 8 (P1 1, P2 5, P3 2) | §1–§14 kind table, families, digests, tags, generation types against L0, L1, L3, L5, L8. |
| L7 | `layer7_extensions_spec.md` | done (2026-10-20) | 8 (P2 6, P3 2) | §1–§13 and registry contracts against cited L0, L1, L2, L3, L5, L8. |
| L8 | `layer8_administration_spec.md` | done (2026-10-20) | 7 (P1 1, P2 2, P3 4) | §1–§16 internally and against cited L0–L7; mechanical §8.2 candidate is a false positive. |

## Interfaces, each side's obligations checked on the other side

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| X1 | Layer 0 ↔ Layers 1, 2 | done (2026-10-20) | 6 (P2 3, P3 3) | L0 obligations on L1/L2 and back; overlaps cited, not repeated. |
| X2 | Layer 0 ↔ Layers 3, 4 | done (2026-10-20) | 11 (P2 4, P3 7) | L0 obligations on L3/L4 and back; overlaps cited, not repeated. |
| X3 | Layer 0 ↔ Layers 5, 6 | done (2026-10-20) | 6 (P2 2, P3 4) | L0 obligations on L5/L6 and back; overlaps cited, not repeated. |
| X4 | Layer 1 ↔ Layer 2 | done (2026-10-20) | 3 (P3 3) | L1↔L2 obligations; overlaps cited, not repeated. |
| X5 | Layer 2 ↔ Layers 3, 4 | done (2026-10-20) | 6 (P2 3, P3 3) | L2↔L3/L4 obligations; overlaps cited, not repeated. |
| X6 | Layer 3 ↔ Layers 4, 5 | done (2026-10-20) | 1 (P2 1) | L3↔L4/L5 obligations; overlaps cited, not repeated. |
| X7 | Layer 5 ↔ Layer 6 | done (2026-10-20) | 3 (P2 1, P3 2) | L5↔L6 obligations; overlaps cited, not repeated. |
| X8 | Layer 7 ↔ Layers 0, 2, 3, 5 | done (2026-10-20) | 8 (P2 5, P3 3) | L7↔L0/L2/L3/L5 obligations; overlaps cited, not repeated. |
| X9 | Layer 8 ↔ Layers 0–7 (what Layer 8 presents and edits exists in its owner) | done (2026-10-20) | 7 (P1 1, P2 4, P3 2) | L8 commands, kinds, addresses, projections vs owners; overlaps cited, not repeated. |

## Orientation documents against the authoritative layers

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| O1 | `architecture_overview_defined_layers.md` | done (2026-10-20) | 7 (P3 7) | every overview summary vs owning section; overlaps cited, not repeated. |
| O2 | `docs/v3_architecture_recap.md` | done (2026-10-20) | 4 (P3 4) | every recap summary vs owning section; overlaps cited, not repeated. |

## After the passes

| Unit | Scope | Status | Note |
|---|---|---|---|
| V | Verify every finding and classify `mechanical.md` | todo | |
| T | Triage with the developer into CA4 issues | todo | |
