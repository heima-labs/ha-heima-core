# Heima Test House Specification

**Status:** Active
**Last Updated:** 2026-05-04
**Version:** 2.0

## Purpose

The Heima Test House is the official internal live-validation environment for the Heima
integration. It provides a deterministic fake home for:

- end-to-end feature validation before phases are closed
- runtime and learning behavior reproduction
- product debugging without a production HA instance
- installer and resident UX testing

It is **not** a generic smart-home simulator. It is a bounded, purposeful environment that models
exactly what Heima needs to be validated — nothing more.

---

## 1. Repository layout

```
lab/heima_test_house/
  infra/               ← Docker stack, HA base config, MQTT broker
  house/               ← Fake entity definitions, scenes, calendars
  validation/          ← Reset scripts, fixture restore, scenario runners
  surfaces/            ← Dashboards and operator panels
```

Current material lives under `docs/examples/ha_test_instance/` and `scripts/live_tests/`.
Migration to `lab/heima_test_house/` is tracked separately.

---

## 2. Canonical commands

| Command | Action |
|---|---|
| `up` | Start the lab stack (Docker Compose + HA boot) |
| `down` | Stop the lab stack |
| `reset` | Restore entities and storage to known baseline |
| `run_smoke` | Run the full smoke check suite |
| `run_feature <name>` | Apply a named scenario and run its validation entrypoint |

---

## 3. House model

One canonical fake home. Bounded complexity — enough variety for cross-domain testing, not
physical realism.

### Rooms

| Room | Key sensors | Actuators |
|---|---|---|
| Living room | motion, door, TV media player, TV power, PC power | lights, thermostat |
| Kitchen | motion, stove power, oven power, dishwasher power | lights |
| Bathroom | motion, humidity sensor | lights |
| Bedroom | motion | lights, thermostat |
| Laundry | washing machine power | — |
| Entrance | door contact, motion | — |

### People

Two residents with independently controllable `device_tracker` and `person` entities.

---

## 4. Entity requirements

### 4.1 Presence and occupancy

| Entity | Type | Used by |
|---|---|---|
| `person.resident_1`, `person.resident_2` | `person` | PeopleDomain |
| `device_tracker.resident_1_phone`, `device_tracker.resident_2_phone` | `device_tracker` | PeopleDomain |
| `binary_sensor.living_room_motion`, `binary_sensor.kitchen_motion`, `binary_sensor.bedroom_motion`, `binary_sensor.entrance_motion` | `binary_sensor` (motion) | OccupancyDomain |

### 4.2 Activity detectors

| Entity | Device class / type | Detector |
|---|---|---|
| `sensor.stove_power` | `power` (W) | `StoveOnDetector` (≥ 200 W) |
| `sensor.oven_power` | `power` (W) | `OvenOnDetector` (≥ 500 W) |
| `media_player.living_room_tv` | `media_player` | `TvActiveDetector` |
| `sensor.tv_power` | `power` (W) | `TvActiveDetector` (corroboration) |
| `sensor.pc_power` | `power` (W) | `PcActiveDetector` (≥ 50 W) |
| `sensor.bathroom_humidity` | `humidity` (%) | `ShowerRunningDetector` |
| `sensor.washing_machine_power` | `power` (W) | `WashingMachineDetector` (≥ 200 W) |
| `sensor.dishwasher_power` | `power` (W) | `DishwasherDetector` (≥ 200 W) |

### 4.3 Climate and lighting

| Entity | Type | Used by |
|---|---|---|
| `climate.living_room`, `climate.bedroom` | `climate` | HeatingDomain |
| `light.living_room`, `light.kitchen`, `light.bedroom`, `light.bathroom` | `light` | LightingDomain |

### 4.4 Security

| Entity | Type | Used by |
|---|---|---|
| `binary_sensor.entrance_door`, `binary_sensor.living_room_window` | `binary_sensor` (door/window) | SecurityDomain |
| `alarm_control_panel.home` | `alarm_control_panel` | SecurityDomain |

### 4.5 Invariant check entities

| Entity | Used to trigger |
|---|---|
| Any motion sensor held at `off` while `person.*` is `home` | `PresenceWithoutOccupancy` |
| `alarm_control_panel.home` disarmed while all persons absent | `SecurityPresenceMismatch` |
| `climate.*` active while home empty for > 30 min | `HeatingHomeEmpty` |
| Any sensor held at a fixed value for > 24 h | `SensorStuck` |

---

## 5. Scenario coverage

Each scenario maps to one or more v2 phases. A scenario is a named fixture + state sequence
that drives the fake house into a specific condition and asserts expected Heima behavior.

| Scenario | Phase | What it validates |
|---|---|---|
| `activity_stove_on` | F | `StoveOnDetector`: power rises ≥ 200 W → CANDIDATE → ACTIVE |
| `activity_stove_interrupted` | F | CANDIDATE → ABSENT when power drops before candidate window expires |
| `activity_shower_running` | F | `ShowerRunningDetector`: humidity rises + rate-of-change threshold |
| `activity_shower_grace` | F | ACTIVE → GRACE → ABSENT after humidity drops and grace period expires |
| `activity_tv_on` | F | `TvActiveDetector`: media_player active + power corroboration |
| `invariant_security_mismatch` | C | Alarm disarmed, all persons absent → `SecurityPresenceMismatch` event |
| `invariant_sensor_stuck` | C | Sensor value unchanged > 24 h → `SensorStuck` event + `anomaly.resolved` after change |
| `invariant_heating_empty` | C | Climate active, home empty > 30 min → `HeatingHomeEmpty` event |
| `learning_weekday_snapshot` | D | Inject consistent weekday snapshots → `WeekdayStateModule` emits `HouseStateSignal` |
| `outcome_positive` | E | Reaction fires → matching `HeimaEvent` arrives → positive outcome recorded |
| `outcome_negative_streak` | E | Reaction fires 5× → no matching event → degradation `ReactionProposal` emitted |
| `event_driven_presence` | J | `person.*` state change → evaluation triggered within 5 s debounce |
| `event_driven_power_threshold` | J | `sensor.*_power` crosses threshold → evaluation triggered within 5 s debounce |
| `installer_override_proposal` | G | `heima.override_approval` with `installer_override=True` → approval recorded with `approved_by="installer"` |
| `resident_approve_proposal` | G/H | HA notification action → approval recorded with `approved_by="resident"` |

---

## 6. Fixture reset contract

`reset` must:

1. Restore all helper-backed fake entities to their canonical baseline values.
2. Clear `custom_components/heima/.storage/heima_*` keys that persist learned state.
3. Re-seed the `EventStore` with a minimal baseline (at least 14 days of presence events).
4. Re-seed `SnapshotStore` (`heima_snapshots`) with enough weekday snapshots for
   `WeekdayStateModule` to have ≥ 10 samples per weekday (required for SUGGEST importance).
5. Leave HA itself running — no restart required after reset.

---

## 7. v2 phase coverage matrix

| v2 Phase | Covered by test house | Scenario(s) |
|---|---|---|
| A — Plugin Framework | Via existing runtime smoke | any |
| B — IBehaviorAnalyzer | Via learning cycle smoke | `learning_weekday_snapshot` |
| C — IInvariantCheck | Yes | `invariant_*` |
| D — InferenceEngine | Yes | `learning_weekday_snapshot` |
| E — OutcomeTracker | Yes | `outcome_positive`, `outcome_negative_streak` |
| F — ActivityDomain | Yes | `activity_*` |
| G — Role model | Yes | `installer_override_proposal`, `resident_approve_proposal` |
| H — House State Learning | Partial (needs approval UX) | `learning_weekday_snapshot` + approval |
| I — Activity Inference | Partial (needs composite scenarios) | TBD |
| J — Event-Driven Trigger | Yes | `event_driven_*` |
| K — Installer alert channel | TBD | TBD |
| L — Auto-discovery | TBD — requires HA entity registry | TBD |
| M — Installation validation | TBD | TBD |

---

## 8. Surfaces

- **Resident dashboard** — Lovelace view using `heima_*_view` entities. Used to validate resident
  UX: house state display, active activities, quick overrides.
- **Debug dashboard** — Full diagnostic view: CanonicalState, EventStore tail, active proposals,
  OutcomeTracker pending, InvariantCheck active.
- **Installer view** — `sensor.heima_health` state, anomaly feed, proposal status.

---

## 9. Constraints

- One canonical house — no parallel topologies.
- Fake entities must use HA `input_*` helpers or MQTT-backed templates (no real hardware).
- Fixture reset must be deterministic and idempotent.
- Scenarios must not depend on wall-clock time — use injectable `now` or explicit state sequences.
- Test house coverage must grow to match each new v2 phase before that phase is marked `DONE`.
