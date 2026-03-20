# Heima Live Test HA Instance Configuration

This folder contains a ready-to-copy Home Assistant package for a dedicated live test instance.

Goal:
- provide deterministic fake entities for Heima validation
- allow mixing fake helpers/templates/MQTT entities with real integrations
- avoid polluting a production HA instance
- provide richer fake lighting entities for reactions/learning tests

## Files

- `configuration.yaml`
  - minimal snippet to enable package loading
- `packages/heima_test_lab.yaml`
  - helpers
  - template entities
  - MQTT test entities
  - utility scripts
- `heima_test_lab_dashboard.yaml`
  - full Lovelace views for:
    - fake test-lab entities
    - Heima runtime/canonical entities
- `docker-compose.yaml`
  - ready-to-run HA test stack (Home Assistant + Mosquitto)
- `docker/ha_config/*`
  - mounted HA config used by docker-compose
- `docker/mosquitto/config/mosquitto.conf`
  - minimal MQTT broker config for test stack

## Quick Start (Docker)

From `docs/examples/ha_test_instance`:

```bash
docker compose up -d
```

Endpoints:
- Home Assistant: `http://localhost:8823`
- MQTT broker: `localhost:1885`

Notes:
- `custom_components/heima` from this repo is mounted read-only into `/config/custom_components`.
- First boot requires normal HA onboarding (create user, etc.).
- Test dashboard is preconfigured in YAML mode and appears in sidebar as `Heima Test Lab`.
- Lovelace uses the forward-compatible format (`resource_mode: yaml`, no legacy top-level `mode: yaml`).
- MQTT broker connection must be added from UI:
  - `Settings -> Devices & Services -> Add Integration -> MQTT`
  - Broker: `mosquitto`
  - Port: `1883`

## Prerequisites

1. Home Assistant package loading enabled in `configuration.yaml`:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

2. MQTT integration configured and connected to a broker (for MQTT test entities).

## Install

1. Copy:
   - `packages/heima_test_lab.yaml`
   into:
   - `/config/packages/heima_test_lab.yaml`
2. Restart Home Assistant.
3. Verify entities with prefix `test_heima_` are available.
4. (Optional) Import `heima_test_lab_dashboard.yaml` as a dedicated dashboard/view.

## Automated live smoke tests

Run the live test script from this repo:

```bash
HA_URL=http://<your-ha-dev-host>:8123 \
HA_TOKEN=<long_lived_token> \
scripts/test_heima_live.sh
```

Python alternative (recommended):

```bash
scripts/test_heima_live.py \
  --ha-url http://<your-ha-dev-host>:8123 \
  --ha-token <long_lived_token>
```

Full runner (deploy + patch + live tests):

```bash
HA_TOKEN=<long_lived_token> \
scripts/test_heima_live_runner.sh --target dev --mode tar --ha-url http://<your-ha-dev-host>:8123
```

The script validates three end-to-end scenarios:
- house state transitions to `working` from work window signal
- heating vacation branch activation (`vacation_curve`)
- notification pipeline smoke (`heima.command notify_event`)

## Entity groups provided

### Helper inputs
- `input_boolean.test_heima_*`
- `input_number.test_heima_*`
- `input_datetime.test_heima_*`

### Template entities
- `binary_sensor.test_heima_*`
- `sensor.test_heima_*`
- `switch.test_heima_heater_relay` (template switch)
- `switch.test_heima_bathroom_fan` (template ventilation switch)
- `switch.test_heima_studio_fan` (template ventilation switch)

### Fake lights for reactions / learning
- living room:
  - `light.test_heima_living_main`
  - `light.test_heima_living_spot`
  - `light.test_heima_living_floor`
- studio:
  - `light.test_heima_studio_main`
  - `light.test_heima_studio_spot`
  - `light.test_heima_studio_desk`
- all fake lights are helper-backed template lights and support:
  - on/off
  - brightness
  - color temperature

### Fake climate
- `climate.test_heima_thermostat` (`generic_thermostat`)
- thermal plant simulation automation:
  - `automation.test_heima_thermal_plant_simulation`
  - updates `input_number.test_heima_room_temp` every minute

### Fake security
- `alarm_control_panel.test_heima_alarm` (`manual` alarm panel)
- default code for lab scripts: `1234`

### MQTT entities
- `binary_sensor.test_heima_mqtt_motion`
- `sensor.test_heima_mqtt_presence_score`
- `sensor.test_heima_mqtt_external_temp`

### Utility scripts
- `script.test_heima_reset`
- `script.test_heima_set_vacation_curve_short`
- `script.test_heima_mqtt_publish_demo`
- `script.test_heima_set_cold_house`
- `script.test_heima_set_living_evening_scene`
- `script.test_heima_set_studio_focus_scene`
- `script.test_heima_run_bathroom_shower_pattern`
- `script.test_heima_run_studio_cooling_pattern`
- `script.test_heima_alarm_arm_away`
- `script.test_heima_alarm_arm_home`
- `script.test_heima_alarm_disarm`

## Suggested Heima bindings for this lab

### General -> house signals
- `vacation_mode_entity` -> `input_boolean.test_heima_vacation_mode`
- `guest_mode_entity` -> `input_boolean.test_heima_guest_mode`
- `sleep_window_entity` -> `binary_sensor.test_heima_sleep_window`
- `relax_mode_entity` -> `binary_sensor.test_heima_relax_mode`
- `work_window_entity` -> `binary_sensor.test_heima_work_window`

### People / anonymous examples
- Use:
  - `binary_sensor.test_heima_room_studio_motion`
  - `binary_sensor.test_heima_room_living_motion`
  - `sensor.test_heima_people_score`
  - `sensor.test_heima_mqtt_presence_score`

### Lighting learning examples
- living room lights:
  - `light.test_heima_living_main`
  - `light.test_heima_living_spot`
  - `light.test_heima_living_floor`
- studio lights:
  - `light.test_heima_studio_main`
  - `light.test_heima_studio_spot`
  - `light.test_heima_studio_desk`
- helper scripts for repeatable lighting patterns:
  - `script.test_heima_set_living_evening_scene`
  - `script.test_heima_set_studio_focus_scene`

### Cross-domain learning example
- bathroom occupancy source:
  - `binary_sensor.test_heima_room_bathroom_motion`
- bathroom signal entities:
  - `sensor.test_heima_bathroom_humidity`
  - `sensor.test_heima_bathroom_temperature`
  - `switch.test_heima_bathroom_fan`
- helper script for repeatable shower-like pattern:
  - `script.test_heima_run_bathroom_shower_pattern`
- suggested `Learning -> context_signal_entities` bindings:
  - `sensor.test_heima_bathroom_humidity`
  - `sensor.test_heima_bathroom_temperature`
  - `switch.test_heima_bathroom_fan`
  - `sensor.test_heima_studio_humidity`
  - `sensor.test_heima_studio_temperature`
  - `switch.test_heima_studio_fan`
- studio cooling example:
  - occupancy source:
    - `binary_sensor.test_heima_room_studio_motion`
  - signal entities:
    - `sensor.test_heima_studio_temperature`
    - `sensor.test_heima_studio_humidity`
    - `switch.test_heima_studio_fan`
  - helper script:
    - `script.test_heima_run_studio_cooling_pattern`

### Heating vacation bindings
- `thermostat_entity` -> `climate.test_heima_thermostat`
- `outdoor_temperature_entity` -> `sensor.test_heima_outdoor_temp`
- `vacation_hours_from_start_entity` -> `sensor.test_heima_vacation_hours_from_start`
- `vacation_hours_to_end_entity` -> `sensor.test_heima_vacation_hours_to_end`
- `vacation_total_hours_entity` -> `sensor.test_heima_vacation_total_hours`
- `vacation_is_long_entity` -> `binary_sensor.test_heima_vacation_is_long`

### Security bindings
- `security_state_entity` -> `alarm_control_panel.test_heima_alarm`
- `armed_away_value` -> `armed_away`
- `armed_home_value` -> `armed_home`

## Notes

- This package includes a fake thermostat for Heating policy tests:
  - `climate.test_heima_thermostat`
- The thermal model is intentionally simple and deterministic:
  - when heater is `on`, room temperature rises
  - when heater is `off`, room temperature drifts toward outdoor temperature
- Calendar note:
  - the Docker lab ships a preconfigured Local Calendar fixture: `calendar.principale`
  - the mounted HA storage already contains:
    - the `local_calendar` config entry
    - the `calendar.principale` entity
    - a baseline ICS store under `.storage/local_calendar.principale.ics`
  - `scripts/live_tests/050_calendar_domain.py` now uses this fixture and creates a deterministic all-day test event through `calendar.create_event`
