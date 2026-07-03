# Heima

Heima is an intent-driven home intelligence engine for Home Assistant.

It observes the home, learns its patterns, proposes behavior in plain language, and automates
approved routines while continuing to verify that they still match reality. The success metric is
invisibility: if the people living in the home rarely need to think about the system, it is working
correctly.

## Who is Heima for?

Heima is a **B2B product** designed around two roles:

**Installer** — a professional who deploys and maintains the integration remotely. The installer
configures entity bindings, activity detectors, and house logic on behalf of the client, monitors
system health over time, and evolves the installation as the home changes (new sensors, new
actuators). The installer is not necessarily a resident of the home.

**Resident** — the person who lives in the home. Receives proposals from Heima in plain language,
approves or rejects them, and applies temporary house state overrides. Never touches configuration.

This separation is intentional. Most home automation systems conflate all roles and force everyone
into the developer seat. Heima makes that unnecessary.

## What Heima does

Home Assistant provides infrastructure: UI, storage, device services, event bus.  
Heima provides reasoning: **what should the home be doing right now, given everything it knows?**

Every evaluation cycle, Heima runs a pipeline of domain models — presence, occupancy, activity,
house state, lighting, heating, calendar, security — and produces a coherent set of actions. It
observes behavioral patterns from real usage, generates proposals in plain language, routes them to
the resident for approval, and tracks whether its actions produced the expected outcomes.

The aim is not to remove configuration entirely. Installers still bind entities, define domain
policies, and review diagnostics. The aim is to replace brittle, manually maintained automation
chains with learned, reviewable, lifecycle-aware behavior.

## Architecture

The v2 pipeline runs a fixed core domain sequence with support for declarative built-in domain
plugins:

```
People → Occupancy → Activity → HouseState → [Lighting, Heating, Calendar, Security, ...]
```

Key subsystems:

| Subsystem | Role |
|---|---|
| Domain DAG | Declarative `depends_on` ordering for built-in runtime domain plugins |
| ActivityDomain | Primitive activity detection (stove, shower, TV, …) with hysteresis state machine |
| InferenceEngine | Per-cycle `ILearningModule` execution; `SnapshotStore` for pattern history |
| Behavior analyzers | Offline pattern, anomaly, lifecycle, composite, and cross-domain analysis producing typed findings and proposals |
| AnomalyAnalyzer | Statistical behavioral drift detection; emits remediation proposals on model staleness |
| IInvariantCheck | Per-cycle structural constraint checks with debounce and resolution events |
| OutcomeTracker | Act→verify loop; degradation proposals after consecutive negative outcomes |
| ProposalEngine | Approval-gated routing of learning signals; lifecycle, grouping, replacement, retirement, and temporal review bundles |
| ManualHold | Shared override framework for deferring automation when a user manually changes an actuator |
| Admin-authored policies | Domain-specific policy templates such as camera privacy policies for alarm/house-state driven privacy control |
| SignalDiscoveryAudit | Runtime classification of HA entities into room-level signal candidates |
| Event-driven trigger | `state_changed`-driven evaluation with per-class debounce; 300 s fallback |

See `docs/specs/heima_v2_spec.md` for the full specification.

## Install

1. Add this repository as a custom repository in HACS (Integration).
2. Install **Heima**.
3. Restart Home Assistant.
4. Add the integration: Settings → Devices & services → Add integration → **Heima**.

## Configuration

Initial configuration is performed by the installer through the Options Flow:
Settings → Integrations → Heima → Configure.

See `docs/guides/heima_v2_admin_guide.md`.

## Project icon

![Heima icon](docs/assets/heima-icon.svg)

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

Active v2 integration happens on branch `feat/v2`; focused work usually lands first on feature
branches. Current phase status: `docs/v2_dev_plan.md`.

## Test House

This repository includes a maintained fake-house lab for live validation and end-to-end testing.
Used to verify v2 behavior with real HA entities before each phase is closed.

- `docs/examples/ha_test_instance/README.md` — setup and usage
- `docs/specs/core/heima_test_house_spec.md` — test house specification

## Research foundations

Heima's inference and learning design draws on the following body of research:

**Contextual activity recognition and temporal reasoning**

- Shi et al. 2026. [*TRACE: Temporal Reasoning over Context and Evidence for Activity Recognition in Smart Homes.*](https://arxiv.org/abs/2605.02841) Georgia Tech / Northeastern. arXiv:2605.02841.
  → basis for Heima's tiered inference, day-type contextual priors, and multi-scale temporal conditioning.

**System lifecycle — bootstrap, lifespan, and maintenance**

- Hiremath, Nishimura, Chernova & Plötz. 2022. [*Bootstrapping Human Activity Recognition Systems for Smart Homes from Scratch.*](https://dl.acm.org/doi/10.1145/3550294) IMWUT 6(3).
  → basis for Phase Z cold-start mode (relaxed thresholds when training data is sparse).

- Hiremath & Plötz. 2023. [*The Lifespan of Human Activity Recognition Systems for Smart Homes.*](https://www.mdpi.com/1424-8220/23/18/7729) Sensors 23(18).
  → basis for Phase AA global drift detection (behavioral model staleness over time).

- Hiremath & Plötz. 2024. [*Maintenance Required: Updating and Extending Bootstrapped Human Activity Recognition Systems for Smart Homes.*](https://arxiv.org/abs/2406.14446) ABC 2024 / IEEE.
  → basis for Phase X/Y model evolution strategy (tiered snapshot conditioning, configured-entity mapping).

**Behavioral routine theory**

- Schank & Abelson. 1977/2013. [*Scripts, Plans, Goals, and Understanding.*](https://www.routledge.com/Scripts-Plans-Goals-and-Understanding-An-Inquiry-Into-Human-Knowledge-Structures/Schank-Abelson/p/book/9780898591385) Psychology Press.
  → basis for day-type prior design: calendar categories (office, wfh, holiday, day_off, vacation) as script selectors; hour buckets as scene headers within each script.

## Specs and docs

- `docs/specs/heima_v2_spec.md` — active specification (v2.1.0-draft)
- `docs/specs/INDEX.md` — full spec index
- `docs/v2_dev_plan.md` — development plan and current phase status
- `docs/guides/heima_v2_admin_guide.md` — complete administrator guide for config flow and options flow
- `docs/guides/house_state_behavior_guide.md` — practical guide to house-state behavior and expectations
- `docs/guides/plugin_authoring.md` — how to write learning and reaction plugins
- `docs/guides/heima_operations_guide.md` — monitoring and operations guide
