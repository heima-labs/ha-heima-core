# Heima — Mistral Vibe Instructions

## Project
Intent-driven home intelligence engine as Home Assistant custom integration.
GitHub org: Heima Labs. Repo: `ha-heima-component`.

## Language
- **Chat responses**: Always respond in **Italian** unless explicitly asked otherwise.
- **Code, documentation, comments, specs, changelog entries, commit messages, branch names, test names**: **Always in English**.
- Persistent project artifacts must be in English.

## Communication Style
- **Be concise**: Short answers. Details only if explicitly requested.
- **Architecture discussions**: Brief discussion before touching code.
- **Spec-first, always**: Before writing code (or delegating), the spec for the phase must be **complete and explicitly approved** by the developer. "Discussed" ≠ "approved". The gate is explicit confirmation: "ok, procedi".
- **Mandatory validation**: For any new contract (type, field, enum, interface) introduced in the spec, ask: *"does this construct overlap with something that already exists?"*

## Commit Style
- **Messages**: Short. Imperative title + 2-3 lines of context max.
- **Do NOT commit to `main`** without explicit user request.
- **On `feat/v2` branch**: Intermediate commits allowed for stable slices if they help continuity between sessions/prompt compactions.
- **Before commit**: Run targeted tests and document test status in `docs/v2_dev_plan.md`.
- **Do NOT push, merge, or release** without explicit user request.
- Always add: `Co-Authored-By: Mistral Vibe <vibe@mistral.ai>`

## Branch Model
- `main`: Production branch. Merge only when feature/fix is complete.
- Feature work: Dedicated branches (`feat/...`, `fix/...`).
- **Do NOT commit directly to `main`** unless it's a trivial fix or documentation.

### Mandatory Procedure Before Merging to main
1. Bump minor version: `python3 scripts/bump_minor.py`
2. Update `CHANGELOG.md` with entry for new version
3. Run full local CI: `bash scripts/ci_local.sh`
   - All jobs must pass (test + lint + format). mypy is informational only.
4. Commit `manifest.json` + `CHANGELOG.md` together with the code
5. Push to `main` triggers `.github/workflows/ci.yml` automatically

**Do NOT merge if `ci_local.sh` fails.**

## Code Rules
- **No backward compatibility**: Single user project.
- **No ML libraries** in built-ins: Pure Python + statistics stdlib. Core must remain dependency-free.
- **All tests must pass** after every modification.
- **Current test count: 660**. Do NOT break existing tests without explicit reason.
- **Before modifying a file: read it.**

## Architecture Invariants

### v1 (branch `main`, active code)
Fixed DAG: `InputNormalizer → People → Occupancy → Calendar → HouseState → Lighting → Heating → Security → Apply`

### v2 (branch `feat/v2`, under development)
Core fixed DAG: `People → Occupancy → Activity → HouseState`, then ordered plugins DAG (`Lighting`, `Heating`, `Security`, ...)
- **ActivityDomain** is the 4th core domain, inserted between Occupancy and HouseState

### Common Invariants (v1 & v2)
- Domains read **CanonicalState** (previous cycle), **NOT** outputs from other domains in the current cycle.
- **No circular dependencies** between domains.
- **Apply plan** is the only output channel for actions on Home Assistant.

## Architectural Decisions (Finalized)

### Multi-persona
v1 learns patterns at household level, not per person. This is a known and documented limitation, not a bug. Per-person learning is planned for v2, not scheduled.

### Inference Engine v2
Incorporated in `docs/specs/heima_v2_spec.md` §10. Planned for Phase D of `feat/v2`.
The file `docs/specs/learning/inference_engine_spec.md` is superseded by v2.1.0-draft spec.

### Plugin API
In v1, registries are built-in. Dynamic loading of third-party plugins is **not supported**. To add a plugin, modify `registry.py`. This is by design until v2.

## v2 Development

Active development is on `feat/v2` branch. Development plan is in `docs/v2_dev_plan.md`.

**Every session working on v2 MUST start by reading `docs/v2_dev_plan.md`.**

This document tracks:
- Current phase and status
- Acceptance criteria for each phase

**Do NOT make architectural decisions** not already present in spec or plan.

### Continuity Between Sessions and Compactions

`docs/v2_dev_plan.md` also serves as the **operational registry** to resume work after new chats or prompt compactions. During an active phase, maintain a `Current Working Notes` section with:
- Current slice and status
- Modified files
- Tests executed and results
- Next concrete step
- Blockers or open decisions

Update the notes before risky pauses, at the end of significant slices, and before intermediate commits.

**If an architectural choice is not already covered by spec or plan: STOP and ask the developer.**

## Key Specifications
- v1: `docs/specs/rfc/heima_spec_v1.md`
- v2: `docs/specs/heima_v2_spec.md` (v2.1.0-draft — active spec)
- v2 dev plan: `docs/v2_dev_plan.md` (current operational status)
- Learning system: `docs/specs/learning/learning_system_spec.md`
- Spec index: `docs/specs/INDEX.md`

## Auditing and Debug
- Runtime diagnostics: `python3 scripts/diagnostics.py --section <engine|plugins|event_store>`
- Learning audit: `python3 scripts/learning_audit.py --ha-url $HA_URL --ha-token $HA_TOKEN`
- Longitudinal review: `ops_audit.py --snapshot-out` + `--compare-to`
- Bring JSON output to Vibe; do NOT ask to infer state from code.

## Project Overview (from README.md)

### What is Heima
Heima is an **intent-driven home intelligence engine** for Home Assistant that observes the home, learns its patterns, and automates it. The success metric is **invisibility**: if residents never notice the system, it is working correctly.

### Target Audience
Heima is a **B2B product** with two distinct roles:

| Role | Responsibilities |
|------|------------------|
| **Installer** | Professional who deploys and maintains the integration remotely. Configures entity bindings, activity detectors, and house logic on behalf of the client. Monitors system health. Evolves installation as the home changes (new sensors, actuators). Not necessarily a resident. |
| **Resident** | Person who lives in the home. Receives plain-language proposals from Heima, approves or rejects them, applies temporary house state overrides. Never touches configuration. |

### Core Value Proposition
- No YAML configuration
- No fragile script chains
- No configuration drift
- Separation of concerns: Installer configures, Resident uses

### Architecture (v2)
Pipeline: `People → Occupancy → Activity → HouseState → [Lighting, Heating, Security, ...]`

**Key Subsystems**:
| Subsystem | Role |
|-----------|------|
| Plugin DAG | Declarative `depends_on` ordering; built-in and third-party domain plugins |
| ActivityDomain | Primitive activity detection (stove, shower, TV, etc.) with hysteresis state machine |
| InferenceEngine | Per-cycle `ILearningModule` execution; `SnapshotStore` for pattern history |
| IBehaviorAnalyzer | Offline pattern analysis producing `BehaviorFinding` proposals |
| AnomalyAnalyzer | Statistical behavioral drift detection; emits remediation proposals on model staleness |
| IInvariantCheck | Per-cycle structural constraint checks with debounce and resolution events |
| OutcomeTracker | Act→verify loop; degradation proposals after consecutive negative outcomes |
| ProposalEngine | Approval-gated routing of SUGGEST-level learning signals to the resident |
| SignalDiscoveryAudit | Runtime classification of HA entities into room-level signal candidates |
| Event-driven trigger | `state_changed`-driven evaluation with per-class debounce; 300s fallback |

See `docs/specs/heima_v2_spec.md` for the full specification.

### Development Environment
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

### Test House
This repository includes a maintained fake-house lab for live validation and end-to-end testing:
- `docs/examples/ha_test_instance/README.md` — setup and usage
- `docs/specs/core/heima_test_house_spec.md` — test house specification

## Research Foundations
Heima's inference and learning design draws on research in:
- Contextual activity recognition and temporal reasoning (TRACE: Shi et al. 2026)
- System lifecycle: bootstrap, lifespan, maintenance (Hiremath et al. 2022-2024)
- Behavioral routine theory (Schank & Abelson 1977/2013)

## Important Guides
- `docs/guides/heima_v2_admin_guide.md` — complete administrator guide for config flow and options flow
- `docs/guides/house_state_behavior_guide.md` — practical guide to house-state behavior and expectations
- `docs/guides/plugin_authoring.md` — how to write learning and reaction plugins
- `docs/guides/heima_operations_guide.md` — monitoring and operations guide
