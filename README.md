# Heima (Home Assistant Integration)

Heima is an intent-driven home intelligence engine for Home Assistant.

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

See `docs/DEVELOPMENT_PLAN.md` for milestone status and `docs/specs/INDEX.md` for the full spec index.

Practical guides:
- `docs/guides/scene_and_script_usage.md` — when to use `scene.*` vs `script.*`
- `docs/guides/plugin_authoring.md` — how to add Learning Pattern Plugins and Reaction Plugins

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

## Development
- Install dev dependencies: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`
- Run the current automated suite: `.venv/bin/pytest -q`
- The HA integration-test harness (`pytest-homeassistant-custom-component`) owns the compatible `pytest` / `pytest-asyncio` versions for this repo's Home Assistant line, so we do not pin those separately in `requirements-dev.txt`.
