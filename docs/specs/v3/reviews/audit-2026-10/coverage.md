# Audit coverage

Status: `todo`, `in progress (<date>)`, `done (<date>)`. One pass takes one unit.

## Mechanical

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| M | `scripts/audit_v3_mechanical.py` over all authoritative layers, overview and recap | done (2026-10-20) | candidates only | 9 unresolved section references, 82 identifiers without a formal definition, 0 conflicting duplicate types; see `mechanical.md`. Classified in the verification step. |

## Internal coherence, one layer or half-layer per unit

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| L0 | `layer0_runtime_spec.md` | todo | | |
| L1 | `layer1_substrate_spec.md` | todo | | |
| L2 | `layer2_registries_spec.md` | todo | | |
| L3a | `layer3_learning_spec.md` §1–§4 | todo | | |
| L3b | `layer3_learning_spec.md` §5–end | todo | | |
| L4 | `layer4_domain_spec.md` | todo | | |
| L5a | `layer5_action_reactions_spec.md` §1–§4 | todo | | |
| L5b | `layer5_action_reactions_spec.md` §5–end | todo | | |
| L6 | `layer6_notification_spec.md` | todo | | |
| L7 | `layer7_extensions_spec.md` | todo | | |
| L8 | `layer8_administration_spec.md` | todo | | |

## Interfaces, each side's obligations checked on the other side

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| X1 | Layer 0 ↔ Layers 1, 2 | todo | | |
| X2 | Layer 0 ↔ Layers 3, 4 | todo | | |
| X3 | Layer 0 ↔ Layers 5, 6 | todo | | |
| X4 | Layer 1 ↔ Layer 2 | todo | | |
| X5 | Layer 2 ↔ Layers 3, 4 | todo | | |
| X6 | Layer 3 ↔ Layers 4, 5 | todo | | |
| X7 | Layer 5 ↔ Layer 6 | todo | | |
| X8 | Layer 7 ↔ Layers 0, 2, 3, 5 | todo | | |
| X9 | Layer 8 ↔ Layers 0–7 (what Layer 8 presents and edits exists in its owner) | todo | | |

## Orientation documents against the authoritative layers

| Unit | Scope | Status | Findings | Note |
|---|---|---|---|---|
| O1 | `architecture_overview_defined_layers.md` | todo | | |
| O2 | `docs/v3_architecture_recap.md` | todo | | |

## After the passes

| Unit | Scope | Status | Note |
|---|---|---|---|
| V | Verify every finding and classify `mechanical.md` | todo | |
| T | Triage with the developer into CA4 issues | todo | |
