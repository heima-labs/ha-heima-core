# Heima — External Context Contract v1

**Status:** Normative reference for adapter implementors  
**Last Verified Against Code:** 2026-04-28

---

## Purpose

Heima is agnostic to weather and alert data sources. To consume external
context, it depends on **adapters**: independent HA custom integrations that
normalize a specific source (OpenWeatherMap, DWD, Protezione Civile, a home
weather station, etc.) into a set of entities with stable naming and
semantics.

This document defines:
- the naming convention for entity IDs produced by adapters
- the semantics and constraints of each signal
- how Heima maps canonical slots to adapter entities via config
- degradation rules when a signal is absent or unavailable
- the adapter's responsibilities vs. Heima's

---

## Principles

**Source-specific naming.** Every adapter writes entities with entity IDs that
include the source's `adapter_id`: `sensor.heima_ext_<adapter_id>_<slot>`.
This lets multiple adapters coexist without conflicts (e.g. OWM and a home
station both expose `outdoor_temp` on distinct entity IDs).

**Explicit mapping in Heima.** The user configures in Heima which entities to
map to which canonical slots. Unconfigured slots → feature disabled, no
error.

**Graceful degradation.** Every slot is optional. If the mapped entity is
absent, `unavailable`, or `unknown`, Heima disables the features that depend
on it without errors. This is not a fault.

**Independent adapters.** An adapter does not need to know about Heima
internally. It only has to expose entities with the correct naming and
semantics. Multiple adapters can coexist on the same slots (e.g. OWM for
weather + DPC for alerts) or on the same slot with different sources (e.g.
OWM and a home station both for `outdoor_temp` — the user chooses which to
use in the Heima config).

**Stable contract.** This spec is versioned. Breaking changes to the contract
(naming convention changes, unit changes, value domain changes) require a new
major version. Adapters must declare the contract version they implement.

---

## Entity ID naming convention

```
sensor.heima_ext_<adapter_id>_<slot>
```

| Part          | Description                                            | Examples                    |
|---------------|---------------------------------------------------------|---------------------------|
| `heima_ext_`  | Fixed prefix — identifies entities of the Heima contract| —                         |
| `<adapter_id>`| Short identifier for the source, defined by the adapter | `owm`, `dpc`, `station` |
| `<slot>`      | Name of the canonical signal (see §Canonical slots)     | `outdoor_temp`, `wind_speed` |

### Examples

| Adapter              | `adapter_id` | Entities produced                                                   |
|----------------------|--------------|-------------------------------------------------------------------|
| OWM Adapter          | `owm`        | `sensor.heima_ext_owm_outdoor_temp`, `sensor.heima_ext_owm_wind_speed`, … |
| DPC Adapter          | `dpc`        | `sensor.heima_ext_dpc_weather_alert_level`, `sensor.heima_ext_dpc_weather_alert_phenomena` |
| Home station   | `station`    | `sensor.heima_ext_station_outdoor_temp`, `sensor.heima_ext_station_outdoor_humidity`, … |

---

## Canonical slots

Slots are the signals that Heima knows about and can consume. Each adapter
implements the subset of slots its source is able to produce.

| Slot                        | Type    | Unit | Description                                          |
|-----------------------------|---------|-------|------------------------------------------------------|
| `outdoor_temp`              | float   | °C    | Current outdoor temperature                          |
| `outdoor_humidity`          | float   | %     | Outdoor relative humidity (0–100)                    |
| `outdoor_lux`               | float   | lx    | Outdoor illuminance (measured or estimated)          |
| `wind_speed`                | float   | m/s   | Current wind speed                                   |
| `rain_last_1h`              | float   | mm    | Precipitation in the last hour                       |
| `rain_forecast_next_6h`     | float   | mm    | Forecast precipitation for the next 6 hours          |
| `weather_condition`         | string  | —     | Current weather condition (enum, see §Enumerations)  |
| `weather_alert_level`       | int     | —     | Highest active alert level (0–3)                     |
| `weather_alert_phenomena`   | string  | —     | Phenomena active at the current alert level (CSV)    |

---

## Mapping configuration in Heima

The user declares in Heima's config flow which entity to use for each slot:

```yaml
# example — external_context section in Heima options
external_context:
  outdoor_temp: sensor.heima_ext_station_outdoor_temp     # preferred home station
  outdoor_humidity: sensor.heima_ext_owm_outdoor_humidity # OWM as fallback
  outdoor_lux: sensor.heima_ext_owm_outdoor_lux
  wind_speed: sensor.heima_ext_owm_wind_speed
  rain_last_1h: sensor.heima_ext_owm_rain_last_1h
  rain_forecast_next_6h: sensor.heima_ext_owm_rain_forecast_next_6h
  weather_condition: sensor.heima_ext_owm_weather_condition
  weather_alert_level: sensor.heima_ext_dpc_weather_alert_level
  weather_alert_phenomena: sensor.heima_ext_dpc_weather_alert_phenomena
```

- Unconfigured slots → the corresponding feature is disabled, no error
- The user can freely map different slots to different adapters
- If a configured entity is `unavailable`, Heima treats the slot as absent
  (there is no automatic fallback mechanism — source selection is an
  explicit user decision)
- For compatibility with legacy configurations, Heima can accept a
  `weather.*` entity as the source of `weather_condition` and `outdoor_temp`:
  `weather_condition` uses the entity's state, `outdoor_temp` uses the
  `temperature` attribute. The `sensor.heima_ext_*` adapters remain the
  recommended and normatively preferred source.

---

## Enumerations

### `weather_condition`

| Value           | Meaning                                      |
|-----------------|-----------------------------------------------|
| `clear`         | Clear sky                                     |
| `partly_cloudy` | Partly cloudy (< 60% cover)                   |
| `cloudy`        | Cloudy (60–90% cover)                         |
| `overcast`      | Overcast (> 90% cover, no precipitation)      |
| `fog`           | Fog or haze                                   |
| `rain`          | Rain (any intensity)                          |
| `heavy_rain`    | Heavy rain (> 7.5 mm/h)                       |
| `storm`         | Thunderstorm                                  |
| `snow`          | Snow (any intensity)                          |
| `unknown`       | Cannot be determined from the source          |

### `weather_alert_level`

| Value | Color    | Meaning                              |
|--------|-----------|--------------------------------------|
| `0`    | Green     | No active alert                      |
| `1`    | Yellow    | Ordinary alert / attention            |
| `2`    | Orange    | Moderate alert / pre-alarm            |
| `3`    | Red       | Severe alert / alarm                  |

---

## Mandatory attributes for every entity

Every entity of the contract must expose the following HA attributes:

```python
{
    "heima_contract_version": "1.0",   # contract version implemented
    "adapter_id": str,                 # e.g. "owm" | "dpc" | "station"
    "source_entity": str | list[str],  # source HA entity ID
    "last_updated": ISO8601 str,       # timestamp of the last update from the source
}
```

---

## Adapter responsibilities

The adapter is responsible for:

1. **Using the naming convention** `sensor.heima_ext_<adapter_id>_<slot>`
2. **Normalizing** values from the source into the contract's domain and units
3. **Writing `unavailable`** if the source is unreachable or the data is out
   of domain, instead of writing a potentially wrong value
4. **Updating entities** at a frequency consistent with the nature of the
   signal (current weather: ≤ 10 min; forecast: ≤ 30 min; alerts: ≤ 15 min)
5. **Declaring the contract version** on every entity via an attribute
6. **Not interfering** with native HA entities: `heima_ext_*` entities are
   new entities created by the adapter, not aliases

---

## Heima's responsibilities

Heima is responsible for:

1. Reading entities through the user-configured mapping
2. Treating `unavailable`, `unknown`, and entity absence as equivalent
   (signal unavailable → feature disabled)
3. Validating the contract version from the `heima_contract_version`
   attribute; logging a warning if incompatible, without blocking the runtime
4. Making no assumptions about the source: Heima does not know and must not
   need to know whether the data comes from OWM, DWD, a home station, or a
   custom sensor

---

## Degradation per slot

| Slot absent                          | Heima behavior                                               |
|---------------------------------------|-------------------------------------------------------------|
| `outdoor_temp`                        | Safety floor heating disabled; vacation curve uses time-of-day only |
| `outdoor_lux`                         | Lighting uses only indoor sensors                            |
| `outdoor_humidity`                    | No impact in v1                                              |
| `wind_speed`                          | No impact in v1                                              |
| `rain_last_1h` / `rain_forecast_next_6h` | Watering skip disabled (v2)                               |
| `weather_condition`                   | Lighting gloomy compensation disabled                        |
| `weather_alert_level`                 | Alert apply filter disabled                                  |
| `weather_alert_phenomena`             | Specific phenomena notification disabled                     |

---

## Contract versioning

The contract follows semantic versioning (MAJOR.MINOR):

- **MINOR bump**: addition of new optional slots; existing adapters remain
  compatible
- **MAJOR bump**: naming convention change, unit change, value domain change;
  requires adapter migration

Adapters must declare which MAJOR.MINOR version they implement.
Heima accepts adapters with an identical MAJOR and MINOR ≤ its own.

**Current contract version: 1.0**

---

## Reference adapters

| Adapter                   | Repo                                      | `adapter_id` | Slots covered                                              |
|---------------------------|-------------------------------------------|--------------|-----------------------------------------------------------|
| OWM Adapter               | `heima-labs/ha-heima-owm-adapter`         | `owm`        | temp, humidity, lux, wind, rain, rain_forecast, condition |
| DPC Adapter               | `heima-labs/ha-heima-DPC-adapter`         | `dpc`        | alert_level, alert_phenomena                              |
