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

**Inference Engine v2 not implemented.** The learning system spec (`docs/specs/learning/inference_engine_spec.md`) describes a second-generation inference engine with richer pattern extraction. In v1, all analyzers use pure Python + stdlib statistics (median, IQR, ISO-week grouping). The spec is RFC/on-hold; no implementation work is scheduled until an explicit decision is made.

**Plugin registry is built-in only.** There is no dynamic third-party plugin loading in v1. Learning plugins and reaction plugins are registered at import time inside `registry.py`. Adding a new plugin requires modifying the source. A stable third-party plugin API with dynamic loading is planned for v2.

**Burst trigger mode is limited to `room_signal_assist` reactions.** The burst pipeline (rapid-change detection via `burst_threshold` / `burst_window_s`) is only exposed as a trigger mode for `room_signal_assist`. Other reaction types such as `room_darkness_lighting_assist` always operate on steady-state bucket values. Extending burst to other reaction types is deferred to v2.

**`burst_window_s` in room signal config has no runtime effect.** When configuring a signal with burst detection, the `burst_window_s` field is accepted, stored, and emitted in event payloads as metadata — but it does not throttle burst detection or influence when a reaction fires. The effective "recency window" for burst-triggered reactions is the reaction's own `followup_window_s` (default 900 s). In v2, `burst_window_s` should either be wired into the detection logic or removed from the config surface to avoid confusion.

**Corroboration signal supports bucket mode only.** In `room_signal_assist` reactions, the primary signal supports both `bucket` (fire while signal is in a given range) and `burst` (fire when signal changes rapidly) trigger modes. The corroboration signal — when present — is always evaluated in bucket mode. Dual-burst reactions (e.g., fire when both humidity and CO₂ rise rapidly at the same time) are not supported in v1. The main reasons: (1) two independent burst windows are unlikely to overlap precisely without explicit synchronization, increasing the risk of false negatives; (2) the use case is narrow enough not to justify the added config surface and runtime complexity. If a real production case emerges, this is a natural v2 extension.

**Context-conditioned lighting uses global abstract context signals at runtime.** Learned `context_conditioned_lighting_scene` proposals use abstract `context_conditions` such as `projector_context=active`, but the current runtime snapshot flattens all configured context entities into one global map. If two rooms expose the same abstract context signal name, the runtime cannot yet distinguish which room's context is active when evaluating the reaction. The learning model is valid, but room-scoped context disambiguation is not implemented in v1.

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
