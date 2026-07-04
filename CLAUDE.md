# Heima — Claude Code Instructions

## Project
Intent-driven home intelligence engine as Home Assistant custom integration.
GitHub org: Heima Labs. Repo: `ha-heima-core`.

## Language
Respond in Italian in chat.
Write code, documentation, comments, specs, changelog entries, commit messages, branch names,
test names, and any persistent project artifact in English.

## Communication style
- Terse replies. Details only if explicitly requested.
- For architectural choices: brief discussion before touching code.
- **Spec-first, always.** Before writing code (or delegating to Codex), the phase's spec must be
  complete and **explicitly approved by the developer**. "Discussed" does not equal "approved".
  The gate is explicit confirmation: "ok, proceed".
- Every new contract (type, field, enum, interface) introduced in the spec must be validated
  against existing constructs before confirmation. Mandatory question:
  "does this construct overlap with something that already exists?"

## Commit style
- Short messages: imperative title + 2-3 lines of context max.
- Do not commit to `main` without the user's explicit request.
- On dedicated development branches, intermediate commits at the end of a stable slice are
  allowed, if they help continuity across sessions/compactions. Before committing: targeted tests
  green, or test status documented in `docs/v2_dev_plan.md`.
- Do not push, merge, or make release commits without the user's explicit request.
- Always add `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`.

## Branch model
- `main` is the production branch. Merge only when the feature/fix is complete.
- Work happens on dedicated branches (e.g. `feat/...`, `fix/...`).
- Do not commit directly to `main` unless it's a trivial fix or documentation.

### Mandatory procedure before every merge to main

1. Bump minor version: `python3 scripts/bump_minor.py`
2. Update `CHANGELOG.md` with an entry for the new version.
3. Run the full local CI: `bash scripts/ci_local.sh`
   - All jobs must pass (test + lint + format). mypy is informational.
4. Commit manifest.json + CHANGELOG.md together with the code.
5. Pushing to main automatically triggers `.github/workflows/ci.yml`.

Do not merge if `ci_local.sh` fails.

## Code rules
- No backward compatibility: sole user of the project.
- No ML libraries in built-ins. Pure Python + statistics stdlib. The core stays dependency-free.
- All tests must be green after every change.
- Current test count: 1594. Do not break existing tests without an explicit reason.
- Before modifying a file: read it.

## Architecture invariants

Fixed core DAG: `People → Occupancy → Activity → HouseState`, then plugins ordered by dependency
(`Lighting`, `Heating`, `Security`, `Calendar`, ...). ActivityDomain is the 4th core domain,
inserted between Occupancy and HouseState.

**Historical note:** v1 (fixed DAG `InputNormalizer → People → Occupancy → Calendar → HouseState →
Lighting → Heating → Security → Apply`, no declarative plugins) was replaced by this architecture
at the merge of `feat/v2` into `main`. It is no longer active code; it remains only as historical
reference in `docs/specs/rfc/heima_spec_v1.md`.

**Architectural invariants:**
- Domains read CanonicalState (previous cycle), NOT the outputs of other domains in the current cycle.
- No circular dependency between domains.
- Apply plan is the only output channel for actions on HA.

## Architectural decisions made

### Multi-person
The current architecture learns patterns at the household level, not per person. This is a known,
documented limitation, not a bug. Per-person learning is not yet planned/scheduled.

### Inference Engine v2
Incorporated in `docs/specs/heima_v2_spec.md` §10. Implemented in Phase D (`DONE`,
see `docs/v2_dev_plan.md`). The file `docs/specs/learning/inference_engine_spec.md` is superseded
by the v2.1.0-draft spec.

### Plugin API
Registries remain built-in. Dynamic loading of third-party plugins is not supported even in the
current architecture: it's an explicit non-goal (`heima_v2_spec.md`, note on `monitored_entities`).
Anyone who wants to add a built-in domain/plugin modifies the code directly, following the
declarative DAG contract (Phase A). Reopening to third-party plugins remains, by design, not
planned.

## v2 development

The v2 architecture has been merged into `main`. Remaining open v2 phases (e.g. Phase AB) continue
on dedicated branches following `docs/v2_dev_plan.md`, which remains the operational source of
truth. **Every session working on v2 phases must start by reading `docs/v2_dev_plan.md`.**
The document tracks the current phase, status, next action, and acceptance criteria for each
phase. Do not make architectural decisions not already present in the spec or the plan.

### Continuity across sessions and compactions

`docs/v2_dev_plan.md` is also the operational log for resuming work after new chats or prompt
compactions. During an active phase, maintain a `Current Working Notes` section with:
- current slice and status;
- files changed;
- tests run and result;
- concrete next step;
- open blockers or decisions.

Update the notes before risky pauses, at the end of a significant slice, and before intermediate
commits. If an architectural choice is not already covered by a spec or the plan, stop and ask the
developer.

## Key specs
- Current architecture: `docs/specs/heima_v2_spec.md` (v2.1.0-draft — spec active on `main`)
- v2 dev plan: `docs/v2_dev_plan.md` (current operational status)
- Learning system: `docs/specs/learning/learning_system_spec.md`
- Spec index: `docs/specs/INDEX.md`
- v1 (historical, superseded): `docs/specs/rfc/heima_spec_v1.md`

## Auditing and debugging
- For runtime diagnostics: `python3 scripts/diagnostics.py --section <engine|plugins|event_store>`
- For learning audit: `python3 scripts/learning_audit.py --ha-url $HA_URL --ha-token $HA_TOKEN`
- For longitudinal review: `ops_audit.py --snapshot-out` + `--compare-to`
- Bring the output JSON to Claude; don't ask it to infer state from the code.
