# Scripts Reference

This folder contains deploy/patch tooling plus multiple Home Assistant-facing test tiers for Heima.

## Layout

- `lib/`
  - `ha_client.py`: shared HA REST client used by Python scripts.
- `live_tests/`
  - Home Assistant-facing scripts, grouped by tier in `check_all_live.sh`
  - naming convention: `NNN_<description>.py` (or `.sh`)
  - tiers:
    - `setup`
      - `recover_test_lab_config.py`
      - `006_restore_learning_fixtures.sh`
    - `live_e2e`
      - `000_live_smoke.py`
      - `010_config_flow.py`
      - `025_lighting_learning_live.py`
      - `026_room_signal_assist_live.py`
      - `027_room_cooling_assist_live.py`
      - `028_presence_live.py`
      - `040_security_mismatch_runtime.py`
      - `050_calendar_domain.py`
    - `seeded_integration`
      - `015_learning_reset.sh`
      - `020_learning_pipeline.py`
      - `060_lighting_schedule.py`
    - `diagnostic`
      - `030_learning_proposals_diag.py`
- Diagnostics:
  - `diagnostics.py`: stampa i diagnostics runtime di Heima (event_store, proposals, calendar, engine, scheduler). Utile per verificare quanti eventi sono stati registrati e se il learning system sta accumulando dati.
- Deploy / patch:
  - `deploy_heima.sh`: deploy custom component to prod/dev hosts.
  - `patch_heima_dev_options.sh`: patch Heima options in HA-dev `.storage`.
- Live orchestration:
  - `check_all_live.sh`: runs an explicit ordered manifest by tier (`setup`, `live_e2e`, `seeded_integration`, `diagnostic`, `all`).
  - `test_heima_live_runner.sh`: deploy + patch + smoke orchestrator.
  - `test_heima_learning_live_runner.sh`: baseline reset + seeded learning path.

## Usage notes

- Always provide `HA_TOKEN` via environment variable (no hardcoded tokens).
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

# Solo una sezione: event_store | proposals | calendar | engine | scheduler
python3 scripts/diagnostics.py --ha-url "$HA_URL" --ha-token "$HA_TOKEN" --section event_store
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
    - `025_lighting_learning_live.py`: fixture history + real living scene activation -> proposal
    - `026_room_signal_assist_live.py`: fixture history + real bathroom humidity/temperature/fan sequence -> proposal
    - `027_room_cooling_assist_live.py`: fixture history + real studio temperature/humidity/fan sequence -> proposal
    - `028_room_air_quality_assist_live.py`: fixture history + real studio CO2/fan sequence -> proposal
    - `028b_room_darkness_lighting_assist_live.py`: fixture history + real studio lux/light sequence -> proposal
    - `029_presence_live.py`: real presence source -> Heima person -> proposal
- `seeded_integration`
  - allowed to accelerate historical data / proposals deterministically
  - not labeled as true E2E
  - current examples:
    - `020_learning_pipeline.py`: uses `heima.set_override` for presence transitions
    - `060_lighting_schedule.py`: relies on `seed_lighting_events` for proposal generation
- `diagnostic`
  - read-only assertions on sensors / diagnostics / counters
