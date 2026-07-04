# Scripts Reference

This folder contains deploy/patch tooling plus multiple Home Assistant-facing test tiers for Heima.

## Layout

- `lib/`
  - `ha_client.py`: shared HA REST client used by Python scripts.
- `live_tests/`
  - Home Assistant-facing scripts, grouped by tier in `check_all_live.sh`
  - naming convention: `NNN_<description>.py` (or `.sh`)
  - `NNN` is a legacy stable test ID, not the canonical execution order
  - canonical order and grouping are defined only by the explicit tier manifests in `check_all_live.sh`
  - tiers:
    - `setup`
      - `recover_test_lab_config.py`
      - `006_restore_learning_fixtures.sh`
    - `live_e2e`
      - `000_live_smoke.py`
      - `010_config_flow.py`
      - `011_room_source_learning_signals.py`
      - `012_house_state_general_config.py`
      - `014_house_state_workday_working.py`
      - `016_admin_only_options_flow.py`
      - `025_lighting_learning_live.py`
      - `026_room_signal_assist_live.py`
      - `027_room_cooling_assist_live.py`
      - `029_presence_live.py`
      - `040_security_mismatch_runtime.py`
      - `050_calendar_domain.py`
    - `seeded_integration`
      - `015_learning_reset.sh`
      - `020_learning_pipeline.py`
      - `060_lighting_schedule.py`
    - `diagnostic`
    - `030_learning_proposals_diag.py`
    - `031_learning_summary_diag.py`
    - `062_anomaly_rules_live.py`
    - `063_semantic_policy_live.py`
    - `064_snapshot_alignment_live.py`
    - `065_learning_modules_p_live.py`
    - targeted manual admin-authored checks
      - `032_admin_authored_lighting_flow.py`
      - `033_admin_authored_reaction_origin_diag.py`
      - `034_admin_authored_room_signal_assist_flow.py`
      - `035_admin_authored_room_darkness_lighting_flow.py`
      - `036_lighting_tuning_followup_flow.py`
      - `037_admin_authored_room_signal_binary_modes.py`
      - `048_admin_authored_room_contextual_lighting_flow.py`
- Diagnostics:
  - `diagnostics.py`: prints Heima's runtime diagnostics (event_store, proposals, calendar, engine, house_state, events, scheduler, plugins, learning, reactions, lighting). For `learning`, `reactions`, and `lighting` it also shows a readable summary before the JSON, including enabled/disabled families, implemented vs. declared-only templates, per-slot lighting collisions, and pending lighting tuning.
  - `reaction_live_debug.py`: live polling of a single reaction with a unified view of `heima_reactions_active`, `engine diagnostics`, `apply_plan`, the last event, and the state of the observed entities.
  - `learning_audit.py`: readable learning summary per family/plugin, with a pending/accepted/rejected/stale breakdown, implemented vs. declared-only templates, per-slot lighting collisions, and a lighting-specific overview of configured/pending/tuning.
  - `ops_audit.py`: compact operational summary for continuous monitoring (health, house state, learning backlog, reactions, security, camera evidence, security presence).
    Can also export a stable JSON snapshot with `--snapshot-out <path>` for longitudinal reviews.
  - `prod_daily_check.py`: quick daily summary for a Heima instance in production (health, event store, tracked learning signals, proposals).
- Deploy / patch:
  - `deploy_heima.sh`: deploy custom component to prod/dev hosts.
  - `patch_heima_dev_options.sh`: patch Heima options in HA-dev `.storage`.
- Live orchestration:
- `check_all_live.sh`: runs an explicit ordered manifest by tier (`setup`, `live_e2e`, `seeded_integration`, `diagnostic`, `all`).
  Numeric prefixes are treated as legacy IDs only.
  - `test_heima_live_runner.sh`: deploy + patch + smoke orchestrator.
  - `test_heima_learning_live_runner.sh`: baseline reset + seeded learning path.

## Usage notes

- Always provide `HA_TOKEN` via environment variable (no hardcoded tokens).
- For admin-boundary live checks, you can optionally provide `HA_NON_ADMIN_TOKEN`.
- Prefer Python scripts as canonical test logic; shell scripts are orchestration wrappers.
- To run the canonical true E2E lane:

```bash
HA_TOKEN='<token>' PERSON_SLUG='stefano' \
./scripts/check_all_live.sh --tier live_e2e --ha-url http://ha-host:8123
```

- To provision the lab first:

```bash
HA_TOKEN='<token>' \
./scripts/check_all_live.sh --tier setup --ha-url http://ha-host:8123
```

- To run the full mixed suite explicitly:

```bash
HA_TOKEN='<token>' PERSON_SLUG='stefano' \
./scripts/check_all_live.sh --tier all --ha-url http://ha-host:8123
```

- To view the runtime diagnostics:

```bash
source scripts/.env
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"

# Only one section: event_store | proposals | calendar | house_state | events | engine | scheduler | plugins | learning
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section event_store

# Only the house_state resolver
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section house_state

# Only the latest events and pipeline counters
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section events

# Only the plugin-centric learning summary
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section learning
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section lighting
python3 scripts/learning_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
python3 scripts/ops_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --snapshot-out /tmp/heima_ops_snapshot.json

# Live debug of a specific reaction by label
python3 scripts/reaction_live_debug.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --label-contains "Luce studio"

# Or by reaction_id, explicitly adding entities to monitor
python3 scripts/reaction_live_debug.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" \
  --reaction-id "<reaction_id>" \
  --entity sensor.study_illuminance \
  --entity binary_sensor.study_presence \
  --entity light.study_main
```

- For a quick daily check on production:

```bash
source scripts/.env
python3 scripts/prod_daily_check.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
```

- To run the learning seeded-integration path from a clean baseline:

```bash
HA_TOKEN='<token>' PERSON_SLUG='stefano' \
./scripts/test_heima_learning_live_runner.sh --ha-url http://ha-host:8123
```

## Tier semantics

- `setup`
  - provisioning / recovery only
  - not counted as runtime functional proof
  - canonical lab bootstrap entrypoint is `recover_test_lab_config.py`
  - `005_setup_lab.py` remains only as a compatibility wrapper for older commands
- `live_e2e`
  - should traverse real HA entity/service paths into Heima runtime behavior
  - should not depend on synthetic history injection as the primary assertion path
  - `check_all_live.sh --tier live_e2e` runs setup prerequisites first so the
    Docker lab has the expected baseline fixtures and room/entity wiring
  - current learning examples:
    - `011_room_source_learning_signals.py`: options-flow room edit -> config-entry diagnostics confirm persisted `occupancy_sources` / `learning_sources`, then runtime diagnostics prove the learning signals enter the signal recorder pool
    - `012_house_state_general_config.py`: options-flow general edit -> config-entry diagnostics confirm persisted `house_state_config`, then runtime diagnostics prove the HouseStateDomain sees the same config and timer values
    - `014_house_state_workday_working.py`: options-flow general edit -> configured `workday_entity` and `work_window_entity` drive `house_state: home -> working -> home` in the live lab, while temporarily neutralizing live calendar inputs that would otherwise force `vacation`/`office`
    - `016_admin_only_options_flow.py`: verifies that an admin token can open Heima options flow and, when `HA_NON_ADMIN_TOKEN` is provided, that a non-admin token is denied either by HA API (`401/403`) or by Heima flow abort (`admin_required`)
    - `025_lighting_learning_live.py`: fixture history + real living scene activation -> proposal
    - `026_room_signal_assist_live.py`: fixture history + real bathroom humidity/temperature/fan sequence -> proposal
    - `027_room_cooling_assist_live.py`: fixture history + real studio temperature/humidity/fan sequence -> proposal
    - `028_room_air_quality_assist_live.py`: fixture history + real studio CO2/fan sequence -> proposal
    - `028b_room_darkness_lighting_assist_live.py`: fixture history + real studio lux/light sequence -> proposal
    - `029_presence_live.py`: real presence source -> Heima person -> proposal
- `diagnostic`
  - `030_learning_proposals_diag.py`: read-only check for proposal sensor payloads, including lifecycle fields such as `identity_key`, `last_observed_at`, and `is_stale`
  - `031_learning_summary_diag.py`: read-only check for plugin-centric `learning_summary` diagnostics payloads
  - `062_anomaly_rules_live.py`: live service/config check for `heima.configure_anomaly_rule` and implemented `AnomalyAnalyzer` rule ids
  - `063_semantic_policy_live.py`: live reload check for Phase N semantic policy proposals and `admin_authored` provenance
  - `064_snapshot_alignment_live.py`: live runtime/storage check for Phase O snapshot fields (`security_state`, `heating_current_temperature`) and legacy `security_armed` removal
  - `065_learning_modules_p_live.py`: live diagnostics check for Phase P learning module registration/readiness and sensorless room sync
  - `070_proposal_review_grouping_live.py`: read-only check for query-time proposal review grouping, temporal bundle diagnostics, review-row count, and proposal sensor count
  - `071_learning_plugin_execution_modes_live.py`: read-only check for analyzer, lifecycle-only, and admin-authored-only plugin execution buckets
  - `072_proposal_lifecycle_diag.py`: read-only check for Phase AD proposal/reaction lifecycle monitoring diagnostics and lifecycle suggestion rows
  - `074_camera_privacy_manual_hold_live.py`: live AE camera privacy check for semantic proposal generation, Heima-owned switch apply provenance, explicit hold blocking, and external switch manual hold
- `seeded_integration`
  - allowed to accelerate historical data / proposals deterministically
  - not labeled as true E2E
  - current examples:
    - `020_learning_pipeline.py`: uses `heima.set_override` for presence transitions
    - `060_lighting_schedule.py`: relies on `seed_lighting_events` for proposal generation
    - `073_house_state_lifecycle_suggestion.py`: uses seeded house-state snapshots/events to verify a replacement lifecycle suggestion path
  - `diagnostic`
  - read-only assertions on sensors / diagnostics / counters

## Targeted manual live checks

These are useful focused regressions for proposal/reaction UX and admin-authored flows, but are not
currently part of the canonical `check_all_live.sh --tier all` lane:

- `032_admin_authored_lighting_flow.py`
- `033_admin_authored_reaction_origin_diag.py`
- `034_admin_authored_room_signal_assist_flow.py`
- `035_admin_authored_room_darkness_lighting_flow.py`
- `036_lighting_tuning_followup_flow.py`
- `037_admin_authored_room_signal_binary_modes.py`
- `048_admin_authored_room_contextual_lighting_flow.py`
- `042_room_signal_assist_tuning_followup_flow.py`
- `043_room_darkness_lighting_tuning_followup_flow.py`
