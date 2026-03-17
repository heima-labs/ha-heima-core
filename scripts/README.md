# Scripts Reference

This folder contains deploy/patch tooling and live E2E checks for Heima.

## Layout

- `lib/`
  - `ha_client.py`: shared HA REST client used by Python scripts.
- `live_tests/`
  - canonical live tests executed in filename order by `check_all_live.sh`
  - naming convention: `NNN_<description>.py` (or `.sh`)
  - current ordered suite:
    - `000_live_smoke.py`
    - `010_config_flow.py`
    - `015_learning_reset.sh`
    - `020_learning_pipeline.py`
    - `030_learning_proposals_diag.py`
    - `040_security_mismatch_runtime.py`
    - `050_calendar_domain.py`
- Deploy / patch:
  - `deploy_heima.sh`: deploy custom component to prod/dev hosts.
  - `patch_heima_dev_options.sh`: patch Heima options in HA-dev `.storage`.
- Live orchestration:
  - `check_all_live.sh`: dynamically discovers and runs all tests in `live_tests/` alphabetically.
  - `test_heima_live_runner.sh`: deploy + patch + smoke orchestrator.
  - `test_heima_learning_live_runner.sh`: baseline reset + learning test.

## Usage notes

- Always provide `HA_TOKEN` via environment variable (no hardcoded tokens).
- Prefer Python scripts as canonical test logic; shell scripts are orchestration wrappers.
- To run all live tests dynamically in configured order:

```bash
HA_TOKEN='<token>' PERSON_SLUG='stefano' \
./scripts/check_all_live.sh --ha-url http://ha-host:8123
```

- To run learning E2E from clean baseline:

```bash
HA_TOKEN='<token>' PERSON_SLUG='stefano' \
./scripts/test_heima_learning_live_runner.sh --ha-url http://ha-host:8123
```
