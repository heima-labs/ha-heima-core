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
    - targeted manual admin-authored checks
      - `032_admin_authored_lighting_flow.py`
      - `033_admin_authored_reaction_origin_diag.py`
      - `034_admin_authored_room_signal_assist_flow.py`
      - `035_admin_authored_room_darkness_lighting_flow.py`
      - `036_lighting_tuning_followup_flow.py`
      - `037_admin_authored_room_signal_binary_modes.py`
- Diagnostics:
  - `diagnostics.py`: stampa i diagnostics runtime di Heima (event_store, proposals, calendar, engine, house_state, events, scheduler, plugins, learning, reactions, lighting). Per `learning`, `reactions` e `lighting` mostra anche un summary leggibile prima del JSON, inclusi family abilitate/disabilitate, template implementati/solo dichiarati, collisioni lighting per slot e pending tuning lighting.
  - `learning_audit.py`: summary leggibile del learning per family/plugin, con breakdown di pending/accepted/rejected/stale, template implementati/solo dichiarati, collisioni lighting per slot e overview lighting-specifica su configured/pending/tuning.
  - `prod_daily_check.py`: summary rapido giornaliero per una istanza Heima in produzione (health, event store, tracked learning signals, proposals).
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

- Per visualizzare i diagnostics runtime:

```bash
source scripts/.env
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"

# Solo una sezione: event_store | proposals | calendar | house_state | events | engine | scheduler | plugins | learning
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section event_store

# Solo il resolver house_state
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section house_state

# Solo gli ultimi eventi e i contatori della pipeline
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section events

# Solo il summary learning plugin-centric
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section learning
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section lighting
python3 scripts/learning_audit.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
```

- Per un check rapido giornaliero su produzione:

```bash
source scripts/.env
python3 scripts/prod_daily_check.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN"
```

- Per run della learning seeded-integration path da baseline pulita:

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
- `seeded_integration`
  - allowed to accelerate historical data / proposals deterministically
  - not labeled as true E2E
  - current examples:
    - `020_learning_pipeline.py`: uses `heima.set_override` for presence transitions
    - `060_lighting_schedule.py`: relies on `seed_lighting_events` for proposal generation
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
- `042_room_signal_assist_tuning_followup_flow.py`
- `043_room_darkness_lighting_tuning_followup_flow.py`
