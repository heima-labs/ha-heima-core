# Heima (Home Assistant Integration)

Heima is an intent-driven home intelligence engine for Home Assistant.

## Who is Heima for?

Heima is designed around three distinct roles:

**Developer** — writes new learning plugins and reaction plugins. Defines what patterns the home can detect and what behaviors it can propose. Does not interact with the running instance.

**Admin** — configures the integration, reviews learning proposals in plain language, and decides which behaviors to activate. The admin may be the same person who lives in the home, or an external consultant who sets things up once and steps back. Either way, the admin is the only person who needs to understand Heima's configuration surface.

**Inhabitant** — lives in the home. Interacts with lights, heating, and presence as usual. Never touches configuration. The home adapts to them, not the other way around.

This separation is intentional. Most home automation systems conflate all three roles and force everyone into the developer seat. Heima's goal is to make that unnecessary.

## What Heima is (and is not)

Heima's goal is to make the home **truly smart**: invisible to those who live in it, yet functional and aware.

This is different from building a configurable automation platform — Home Assistant already does that.
Heima adds a **context interpretation layer** on top: it reads presence, occupancy, time, and house state, and translates them into coherent actions — without inhabitants having to think about it.

The success metric is invisibility. If the people living in the home never notice the system, never have to fight it or configure it constantly, and things simply happen at the right moment in the right way — Heima is working correctly.

Home Assistant provides the infrastructure (UI, storage, device services, event bus).
Heima provides the reasoning: **what should the home be doing right now, given everything it knows?**

See `docs/specs/rfc/heima_spec_v1.md` § 0 for the full design intent.

### The blueprint problem

Most home automation users end up with dozens of blueprints, scripts, and automations they barely understand. Each one was correct when created, but over time they drift, conflict, and go stale. The person who set them up no longer remembers what half of them do. Non-technical household members can't touch them. Debugging why the lights behaved unexpectedly on Tuesday at 21:47 requires reading YAML.

Heima's answer is: instead of more blueprints, build one engine that observes the home and proposes coherent automations based on what actually happens there. The user reviews proposals in plain language and accepts or rejects them — no YAML, no fragile script chains.

### Philosophy and roadmap

**v1 — statistical baseline (current)**
The learning system uses pure Python + the standard library: median, IQR, ISO-week grouping. No external ML dependencies. This keeps the integration installable on any Home Assistant instance without additional packages. The system must observe a pattern across at least 2 distinct calendar weeks before it generates a proposal — this threshold is configurable per analyzer.

**v2 — ML-optional plugin system (planned)**
v1's plugin architecture is designed to be replaced and extended. The v2 DAG introduces a declarative `depends_on` system and a stable third-party plugin API. This will allow community plugins to bring in ML-based analyzers (sklearn, lightweight models, etc.) as opt-in extensions — the core integration stays dependency-free. See `docs/specs/heima_v2_spec.md` and `docs/specs/learning/inference_engine_spec.md`.

### Known limitations in v1

**Household-level learning only.** Heima v1 observes the home as a unit. Presence patterns, lighting preferences, and schedules are learned at the household level — not per person. In households where two people have substantially different routines (different work schedules, different sleeping times), the learned patterns may reflect an average that is optimal for neither. Per-person learning with device-tracked identity is a planned v2 capability.

## Project Icon
![Heima icon](docs/assets/heima-icon.svg)

## Development status

Active development is tracked on `main`, with feature work landing on short-lived topic branches before merge.

Implemented modules:
- Runtime engine with full domain DAG (people, occupancy, house state, lighting, heating, security)
- Config Flow and Options Flow
- Event pipeline with notification routing (recipients, groups, legacy routes)
- Reactive Behavior Engine (Phase 7 R0–R5): SnapshotBuffer, HeimaReaction, ConsecutiveStateReaction, PresencePatternReaction, ILearningBackend / NaiveLearningBackend, mute/unmute commands, `heima_reactions_active` sensor
- Security-owned capabilities such as:
  - `security_presence_simulation`
  - `security_camera_evidence`
- Monitoring and operability surfaces:
  - daily operations
  - investigation/debug
  - weekly learning review
  - CLI audit / snapshot / compare tooling

See `docs/DEVELOPMENT_PLAN.md` for milestone status and `docs/specs/INDEX.md` for the full spec index.

Practical guides:
- `docs/guides/scene_and_script_usage.md` — when to use `scene.*` vs `script.*`
- `docs/guides/plugin_authoring.md` — how to add Learning Pattern Plugins and Reaction Plugins
- `docs/guides/options_flow_configuration_guide.md` — how to configure Heima through the Options Flow
- `docs/guides/heima_operations_guide.md` — how to monitor Heima over time and review health / learning progress

Practical reference surfaces:
- `docs/examples/heima_dashboard_production.yaml` — generic low-noise daily operations dashboard
- `docs/examples/heima_dashboard_debug.yaml` — generic debug/investigation dashboard
- `docs/examples/ha_test_instance/docker/ha_config/dashboards/heima_test_lab_dashboard.yaml` — validated fake-house dashboard for live testing and operator review

## Install (HACS custom repo)
- Add this repository as a custom repository in HACS (Integration)
- Install **Heima**
- Restart Home Assistant
- Add integration: Settings → Devices & services → Add integration → Heima

## Specs
See `docs/specs/INDEX.md` and the versioned spec files.

## Guides
- `docs/guides/scene_and_script_usage.md`
- `docs/guides/plugin_authoring.md`
- `docs/guides/options_flow_configuration_guide.md`
- `docs/guides/heima_operations_guide.md`

## Monitoring And Operations

For day-to-day operations and periodic review, the main CLI tools are:

```bash
source scripts/.env
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
python3 scripts/learning_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
```

For longitudinal review:

```bash
source scripts/.env
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --snapshot-out tmp/heima_ops_snapshot.json
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --review --compare-to tmp/heima_ops_snapshot.json
```

See:
- `docs/guides/heima_operations_guide.md`
- `scripts/README.md`

## Test House

This repository includes a maintained fake-house lab for live validation and product debugging.

Key entry points:
- `docs/examples/ha_test_instance/README.md`
- `scripts/live_tests/006_restore_learning_fixtures.sh`
- `docs/examples/ha_test_instance/docker/ha_config/dashboards/heima_test_lab_dashboard.yaml`

## Development
- Install dev dependencies: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`
- Run the current automated suite: `.venv/bin/pytest -q`
- The HA integration-test harness (`pytest-homeassistant-custom-component`) owns the compatible `pytest` / `pytest-asyncio` versions for this repo's Home Assistant line, so we do not pin those separately in `requirements-dev.txt`.
