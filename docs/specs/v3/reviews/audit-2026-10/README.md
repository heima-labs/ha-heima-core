# V3 specification coherence audit (2026-10)

A layer-by-layer and interface-by-interface reread of the V3 specifications, to find objective
defects after the Layer-7 work (CA4-127–132). It is split into small, independent passes so that no
session has to hold the whole specification set in context: the state of the audit lives in this
folder, not in any chat.

**Audited baseline:** commit `84f5263` on `feat/v3-planning`. No specification file is edited until
the triage step; line numbers in findings refer to this baseline.

## Files

- `README.md` — this method; every pass reads it first.
- `coverage.md` — one row per audit unit, with its status. A pass takes exactly one unit.
- `findings/<unit>.md` — the findings and coverage note of one pass, written only by that pass.
- `findings.md` — index of all findings with their verification status, maintained by the
  coordinator.
- `mechanical.md` — output of `python3 scripts/audit_v3_mechanical.py` (candidate list, unverified).

## Scope

In scope: the nine authoritative layer specifications listed in `contract_registry.json`, and the
overview and recap checked against them. Read the backlog (`docs/v3_backlog.md`) only to learn
whether an apparent defect is an approved decision. Out of scope: historical drafts, review records,
V2 or V3 code, external sources.

## What counts as a finding

Only objective defects, each provable by quoting the text:

| Code | Category | Test |
|---|---|---|
| C | Contradiction | Two rules, in one layer or across layers, cannot both hold for some concrete case. |
| R | Dangling reference | A section, type, field, code or registry is cited but defined nowhere, or cited with the wrong section. |
| O | Unhonored obligation | Layer A states that layer B does, owns or guarantees X; B does not. |
| D | Copy drift | The same rule is restated in two places and the restatements now differ in meaning. |
| V | Invariant violation | A rule breaks an architecture invariant: one action path (`ApplyStep` only through Layer 5), acyclic same-cycle DAG, previous-cycle reads across domains, no I/O or dynamic lookup on the hot path, non-forgeable provenance, closed core registries, no person identity in operational records. |

Ambiguities, missing lifecycle cases and improvement ideas are **not** findings. Record them, if
useful, under "Observations" in `findings.md`, without severity.

An approved backlog decision is not a defect unless it concretely contradicts another approved rule;
then the finding quotes both.

## Severity

As in the backlog: `P0` contradictory authorization or safety rules; `P1` possibly incorrect action
or data behavior, or a missing contract needed to implement an Initial-V3 capability consistently;
`P2` an ambiguous algorithm, lifecycle, schema or validation requirement caused by the defect;
`P3` documentation maintenance (wording, stale reference, orientation drift).

## Finding format

```markdown
### F-<unit>-<nn> — <one-line title>

- **Category / severity:** C | R | O | D | V / P0–P3
- **Locations:** `path:line` — "exact quote"; `path:line` — "exact quote"
- **Owner:** the layer whose text should change, and why
- **Defect:** the concrete case in which the texts conflict or the reference fails
- **Proposed direction:** one sentence; no edit is made
- **Confidence:** high | medium | low
- **Verification:** pending
```

The verification step later sets `confirmed`, `false positive (reason)` or `approved decision
(backlog reference)`.

## Roles

Passes run as parallel subagents, each on one unit. A pass writes **only** its own file
`findings/<unit>.md`; it never edits `coverage.md`, `findings.md`, any specification, or any other
file, and never runs git. The coordinator session alone updates `coverage.md` and `findings.md`,
and commits.

## Pass protocol

1. Read this README and the row of your unit in `coverage.md`.
   Read the index `findings.md` too: do not repeat a finding already recorded there. If you meet
   it again, cite its id in your Coverage paragraph instead of creating a new finding.
2. Read only the unit's files and sections, plus the sections they explicitly cite; use
   `python3 scripts/check_v3_specs.py --issue <CA4-n>` or the registry `depends_on` to find
   dependencies instead of reading whole layers.
3. For an interface unit, list every obligation each side states about the other, then check each
   one on the other side.
4. Write `findings/<unit>.md`: a heading with the unit, a **Coverage** paragraph listing the
   sections read and what was checked and found clean, then the findings with ids `F-<unit>-<nn>`
   in the format above, then optional observations. Every finding quotes both sides. "No finding"
   means none was found in what was read, not that none exists.
5. Reply to the coordinator with the unit, the number of findings by severity, and one line on what
   was checked.

The coordinator then sets the unit to `done` in `coverage.md`, adds the findings to the index in
`findings.md`, and commits `docs: audit <units> (V3 coherence audit)`. No push without the
developer's request.

## Fixed prompt for one pass

> Work in `/Users/StefanoIOD/MyProjects/heima-labs/ha-heima-component-v3-planning`, branch
> `feat/v3-planning`. Read `docs/specs/v3/reviews/audit-2026-10/README.md` and follow its pass
> protocol for unit `<UNIT>` exactly. Report only objective findings in the README's categories,
> each with exact quotes from both sides. Write only
> `docs/specs/v3/reviews/audit-2026-10/findings/<UNIT>.md`; do not edit any other file and do not
> run git. When done, reply with the unit, the number of findings by severity, and one line on what
> was checked.

## Verification protocol

A verifier covers one area and writes only `verification/<area>.md`; it edits no other file and
runs no git. For every finding of its units, in index order, it re-reads each quoted location at
the baseline and the relevant backlog decisions, then records one row:

| Id | Verdict | Duplicate of | Severity | Note |
|---|---|---|---|---|

- **Verdict:** `confirmed`, `false positive (<reason>)` or `approved decision (<backlog reference>)`.
- **Duplicate of:** the lowest id describing the same defect, in any area, or empty. A duplicate keeps
  its own verdict.
- **Severity:** the README severity the verifier assigns; it may differ from the pass's.
- **Note:** one line; for `confirmed`, the owning layer and a one-sentence correction direction.

A verifier does not search for new defects; if it meets one, it lists it under "New candidates" with
quotes, unverified.

## Steps after the passes

1. **Verification:** a separate pass reads only `findings.md` and the quoted lines, checks each
   finding against the text and the backlog, and sets its verification field; it also classifies
   every `mechanical.md` candidate.
2. **Triage:** confirmed findings are discussed with the developer one at a time and become CA4
   issues or are dropped.
