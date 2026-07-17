# Code Quality Audit Plan — 2026-06-08

## Purpose

Audit the current `feat/v2` codebase for:

- unnecessary duplicated code;
- suboptimal implementations or shortcuts;
- weak module boundaries and implicit contracts;
- fragile option/default handling;
- insufficient regression coverage around shared behavior.

This is an analysis-only plan. Do not change implementation code during the audit unless the user
explicitly approves a concrete fix.

## Current Resume Point

- Date: 2026-06-08
- Branch at plan creation: `feat/v2`
- Current `feat/v2` head at plan creation: `11c439c Clean up phase Y to AA learning quality`
- Local branch state at plan creation: `feat/v2` ahead of `origin/feat/v2` by 7 commits
- Latest full CI result before this plan:
  - `1455 passed`
  - `ruff check`: OK
  - `ruff format`: OK
  - mypy informational step: OK

## Non-Negotiable Constraints

- Do not choose a knowingly suboptimal solution without asking the user first.
- Do not duplicate code unless it is strictly necessary and the necessity is documented.
- Prefer shared helpers, explicit contracts, and existing repo patterns over local reimplementations.
- Keep analysis separate from remediation:
  1. audit first;
  2. report findings with severity and concrete risk;
  3. wait for user approval before code changes.
- Do not touch unrelated user changes.
- Keep `README.md` ignored unless the user explicitly asks to modify it.

## Audit Scope

### 1. Learning and Inference

Files/directories:

- `custom_components/heima/runtime/inference/`
- `custom_components/heima/runtime/inference/modules/`
- `custom_components/heima/runtime/analyzers/`

Focus:

- duplicated context-key generation;
- duplicated context matching;
- duplicated threshold parsing;
- analyzer logic that reconstructs inference-module internals;
- inference modules exposing diagnostics that are too rich, too weak, or not explicit enough.

Known recent context:

- Phase Y introduced tiered `HouseStateInferenceModule`.
- Phase Z introduced activity bootstrap support.
- Phase AA introduced `learned_model_stale`.
- Cleanup commit `11c439c` moved AA house-state matching into the inference module contract and
  deduplicated stale contexts across tier variants.

### 2. Proposal, Review, and Approval Lifecycle

Files/directories:

- `custom_components/heima/runtime/proposal_engine.py`
- `custom_components/heima/runtime/inference/approval_store.py`
- `custom_components/heima/config_flow/_steps_reaction_*.py`
- `custom_components/heima/config_flow/_reaction_*.py`

Focus:

- duplicate proposal identity logic;
- duplicated proposal-to-record and record-to-proposal mapping;
- partial metadata persistence;
- review/edit flows reconstructing runtime contracts locally.

### 3. Coordinator Wiring

Files:

- `custom_components/heima/coordinator.py`

Focus:

- excessive coordinator knowledge of module internals;
- repeated option extraction;
- repeated diagnostics shaping;
- unclear boundary between coordinator, modules, and health/audit surfaces.

### 4. Reactions and Reaction Helpers

Files/directories:

- `custom_components/heima/runtime/reactions/`
- `custom_components/heima/config_flow/_reaction_helpers.py`
- reaction-specific config flow steps

Focus:

- duplicated validation/build logic;
- duplicate labels/details formatting;
- reaction identity and matching logic scattered across runtime and config flow;
- repeated safety checks that should be central contracts.

### 5. Configuration and Defaults

Files/directories:

- `custom_components/heima/const.py`
- `custom_components/heima/config_flow/`
- `docs/CONFIGURATION_REFERENCE.md`
- relevant tests under `tests/`

Focus:

- defaults that differ between UI, docs, coordinator, modules, and tests;
- explicit user override not taking precedence;
- diagnostic names that hide whether a value is configured, inferred, or inherited.

### 6. Tests vs Architecture

Files/directories:

- `tests/`

Focus:

- tests that only verify happy path behavior;
- missing regression tests for deduplication and override precedence;
- tests that accidentally lock in a suboptimal implementation;
- repeated test fixtures that should be shared helpers.

## Suggested Read-Only Commands

Use these commands to gather evidence. Do not use them as a substitute for reading the relevant
code.

```bash
git status --short --branch
git log --oneline --decorate -12
rg -n "_safe_dict|_token|context_key|context_snapshot|matches|match|threshold|min_support|bootstrap|diagnostics" custom_components/heima tests
rg -n "duplicate|dedup|identity|proposal_id|context_conditions|metadata" custom_components/heima tests docs/specs
```

For focused file reads, prefer:

```bash
sed -n '1,220p' custom_components/heima/runtime/proposal_engine.py
sed -n '1,240p' custom_components/heima/runtime/inference/approval_store.py
sed -n '1,260p' custom_components/heima/runtime/inference/modules/house_state_inference.py
sed -n '1,240p' custom_components/heima/runtime/inference/modules/activity_inference.py
sed -n '1,340p' custom_components/heima/coordinator.py
```

## Finding Format

Report findings ordered by severity.

Each finding must include:

- severity: `critical`, `high`, `medium`, `low`;
- file and line reference;
- duplicated/suboptimal pattern;
- concrete risk;
- why the existing code is insufficient;
- recommended fix;
- test impact;
- whether user approval is required before implementation.

Use this template:

```markdown
### [severity] Short title

- Location: `path:line`
- Problem:
- Risk:
- Recommended fix:
- Tests to add/update:
- Notes:
```

## Severity Guide

- `critical`: can cause unsafe behavior, data loss, broken approvals, or wrong runtime actions.
- `high`: likely behavior bug or architectural leak that will break future phases.
- `medium`: maintainability problem with realistic regression risk.
- `low`: naming, diagnostics clarity, local cleanup, or test ergonomics.

## Expected Output

The first audit pass should produce a report, not code changes.

Recommended report sections:

1. Summary verdict.
2. Findings ordered by severity.
3. Duplicated helper/function inventory.
4. Boundary/contract risks.
5. Test gaps.
6. Proposed remediation order.
7. Explicit questions for the user before implementation.

## Continuation Notes For Context Compaction

If the conversation context is compacted, resume by reading this file first:

```bash
sed -n '1,260p' docs/audit/code_quality_audit_plan_2026-06-08.md
git status --short --branch
git log -1 --oneline --decorate
```

Then continue with the read-only audit. Do not infer approval to modify code from this plan.

The user explicitly asked for:

- this plan to be persisted in a file;
- enough information to survive context compaction;
- no unnecessary code duplication;
- no knowingly suboptimal solution without prior authorization.

