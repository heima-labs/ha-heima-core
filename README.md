# Heima

Heima is an intent-driven home intelligence engine for Home Assistant.

It observes the home, learns its patterns, and automates it — without requiring inhabitants to
think about it. The success metric is invisibility: if the people living in the home never notice
the system, it is working correctly.

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
house state, lighting, heating, security — and produces a coherent set of actions. It observes
behavioral patterns from real usage, generates proposals in plain language, routes them to the
resident for approval, and tracks whether its actions produced the expected outcomes.

No YAML. No fragile script chains. No configuration drift.

## Architecture

The v2 pipeline runs a fixed core domain sequence followed by a declarative plugin DAG:

```
People → Occupancy → Activity → HouseState → [Lighting, Heating, Security, ...]
```

Key subsystems:

| Subsystem | Role |
|---|---|
| Plugin DAG | Declarative `depends_on` ordering; built-in and third-party domain plugins |
| ActivityDomain | Primitive activity detection (stove, shower, TV, …) with hysteresis state machine |
| InferenceEngine | Per-cycle `ILearningModule` execution; `SnapshotStore` for pattern history |
| IBehaviorAnalyzer | Offline pattern analysis producing `BehaviorFinding` proposals |
| IInvariantCheck | Per-cycle structural constraint checks with debounce and resolution events |
| OutcomeTracker | Act→verify loop; degradation proposals after consecutive negative outcomes |
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

See `docs/guides/options_flow_configuration_guide.md`.

## Project icon

![Heima icon](docs/assets/heima-icon.svg)

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q
```

Active development is on branch `feat/v2`. Current phase status: `docs/v2_dev_plan.md`.

## Test House

This repository includes a maintained fake-house lab for live validation and end-to-end testing.
Used to verify v2 behavior with real HA entities before each phase is closed.

- `docs/examples/ha_test_instance/README.md` — setup and usage
- `docs/specs/core/heima_test_house_spec.md` — test house specification

## Specs and docs

- `docs/specs/heima_v2_spec.md` — active specification (v2.1.0-draft)
- `docs/specs/INDEX.md` — full spec index
- `docs/v2_dev_plan.md` — development plan and current phase status
- `docs/guides/options_flow_configuration_guide.md` — Options Flow configuration guide
- `docs/guides/plugin_authoring.md` — how to write learning and reaction plugins
- `docs/guides/heima_operations_guide.md` — monitoring and operations guide
