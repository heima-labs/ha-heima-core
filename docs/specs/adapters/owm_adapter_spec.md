# Heima OWM Adapter — Spec v1

**Status:** Reference spec for implementation  
**Repo target:** `heima-labs/ha-heima-owm-adapter`  
**Contract implemented:** External Context Contract v1.0  
**Last Updated:** 2026-04-27

---

## Purpose

Normalize the data exposed by Home Assistant's native **OpenWeatherMap**
integration into entities of the [Heima External Context Contract v1](./external_context_contract.md).

The adapter does not call the OpenWeatherMap APIs directly. It reads the HA
entities already created by the native OWM integration and transforms them.

---

## Prerequisites

| Requirement                      | Notes                                                      |
|----------------------------------|-----------------------------------------------------------|
| HA with the native OWM integration    | Configurable from Settings → Integrations              |
| OWM API key                      | Required by the native integration, not by the adapter    |
| Heima installed                  | Optional for the adapter to function, required to consume it |

The adapter does not require HACS. It's distributed as a standard custom integration.

---

## OWM source entities → Heima contract entities

### Direct mapping

| Native OWM entity (HA)                         | Heima contract entity                          | Transformation                    |
|------------------------------------------------|-------------------------------------------------|-----------------------------------|
| `sensor.openweathermap_temperature`            | `sensor.heima_ext_outdoor_temp`                 | None (already °C)                  |
| `sensor.openweathermap_humidity`               | `sensor.heima_ext_outdoor_humidity`             | None (already %)                   |
| `sensor.openweathermap_wind_speed`             | `sensor.heima_ext_wind_speed`                   | km/h → m/s conversion (÷ 3.6)   |
| `sensor.openweathermap_rain`                   | `sensor.heima_ext_rain_last_1h`                 | None (already mm)                  |
| `sensor.openweathermap_forecast_precipitation` | `sensor.heima_ext_rain_forecast_next_6h`        | Sum of 6h forecast (see §Forecast)|
| `weather.openweathermap`                       | `sensor.heima_ext_weather_condition`            | Enum mapping (see §Condition)    |

### Computed entities

| Heima contract entity              | Source                                                      |
|-------------------------------------|--------------------------------------------------------------|
| `sensor.heima_ext_outdoor_lux`      | Estimated from cloud coverage + UV index + solar time (see §Lux) |

> **Note:** the adapter does not expose `weather_alert_level` or
> `weather_alert_phenomena`. Those signals are the responsibility of adapters
> dedicated to alert sources (e.g. ha-heima-pc-adapter). OWM is not an
> authoritative source of civil alerts.

---

## Normalization logic

### Condition mapping

OWM exposes the condition code as the state of the `weather.openweathermap`
entity. The mapping to the Heima contract is:

| OWM state                                  | Heima `weather_condition` |
|--------------------------------------------|---------------------------|
| `sunny`, `clear-night`                     | `clear`                   |
| `partlycloudy`                             | `partly_cloudy`           |
| `cloudy`                                   | `cloudy`                  |
| `fog`, `haze`                              | `fog`                     |
| `rainy`, `showers-day`, `showers-night`    | `rain`                    |
| `pouring`                                  | `heavy_rain`              |
| `lightning-rainy`, `lightning`             | `storm`                   |
| `snowy`, `snowy-rainy`                     | `snow`                    |
| `windy`, `windy-variant`, `exceptional`    | `overcast`                |
| any other                                  | `unknown`                 |

### Lux estimation

OWM does not provide illuminance in lux. The adapter estimates `outdoor_lux` from:

1. **Cloud coverage** (`sensor.openweathermap_cloud_coverage`, %)
2. **UV index** (`sensor.openweathermap_uv_index`) as a proxy for irradiance
3. **Solar time** computed from the HA system's geographic location

Algorithm:

```python
def estimate_lux(cloud_pct: float, uv_index: float, solar_elevation_deg: float) -> float:
    if solar_elevation_deg <= 0:
        return 0.0  # night

    # max lux expected under a clear sky at that solar elevation
    max_lux = 120_000 * math.sin(math.radians(solar_elevation_deg))

    # cloud attenuation (approximated linear relationship)
    cloud_factor = 1.0 - (cloud_pct / 100.0) * 0.85

    # UV attenuation (UV 0 = heavy overcast, UV 11+ = full tropical sun)
    uv_factor = min(uv_index / 11.0, 1.0) if uv_index is not None else 0.5

    estimated = max_lux * cloud_factor * uv_factor
    return round(max(estimated, 0.0), 1)
```

**Acceptable approximation:** the adapter does not claim photometric
precision. Its use in Heima (lighting compensation, gloomy detection)
tolerates a ±30% error. If `cloud_coverage` or `uv_index` are `unavailable`,
the adapter writes `unavailable` for `outdoor_lux` too, instead of using a
silent fallback.

### Precipitation forecast (next 6h)

The native OWM integration exposes hourly forecasts as attributes of
`weather.openweathermap`. The adapter reads the `forecast` attribute (a list
of dicts) and sums the precipitation of the first 6 records with a
`datetime` in the future:

```python
def sum_rain_next_6h(forecast: list[dict], now: datetime) -> float:
    total = 0.0
    count = 0
    for entry in sorted(forecast, key=lambda x: x["datetime"]):
        if entry["datetime"] <= now:
            continue
        total += entry.get("precipitation", 0.0) or 0.0
        count += 1
        if count >= 6:
            break
    return round(total, 1)
```

If `forecast` is absent or empty, the entity is `unavailable`.

---

## Configuration

The adapter is configurable via the HA Config Flow. Parameters:

| Parameter              | Type    | Default                          | Description                                       |
|------------------------|---------|-----------------------------------|---------------------------------------------------|
| `owm_entity_prefix`    | string  | `openweathermap`                 | Prefix of the native OWM entities (for multiple installations) |
| `weather_entity`       | string  | `weather.openweathermap`         | Entity ID of the main weather entity              |
| `ha_latitude`          | float   | (from HA config)                   | Latitude for solar elevation calculation          |
| `ha_longitude`         | float   | (from HA config)                   | Longitude for solar elevation calculation         |
| `update_interval_min`  | int     | `10`                             | Weather entity update frequency (minutes)     |
| `forecast_interval_min`| int     | `30`                             | Forecast update frequency (minutes)         |

Latitude and longitude are pre-filled from the HA configuration and
editable by the user.

---

## Update frequency

| Signal                        | Frequency    | Notes                                         |
|--------------------------------|--------------|------------------------------------------------|
| temp, humidity, wind, rain     | 10 min       | Bound to native OWM polling                  |
| weather_condition              | 10 min       | Same source                                 |
| outdoor_lux                    | 5 min        | Local recomputation (does not depend on OWM polling)|
| rain_forecast_next_6h          | 30 min       | HA forecasts updated less frequently   |

---

## Error handling

| Condition                                  | Adapter behavior                           |
|---------------------------------------------|-------------------------------------------------|
| Source OWM entity `unavailable`           | Corresponding heima entity → `unavailable`     |
| Source OWM entity absent (not installed)| Corresponding heima entity → `unavailable`     |
| Out-of-domain value (e.g. humidity > 100)   | Log warning, entity → `unavailable`             |
| Error computing lux                      | `outdoor_lux` → `unavailable`, log warning      |
| Malformed forecast                         | `rain_forecast_next_6h` → `unavailable`         |

The adapter **does not raise exceptions propagated to HA** for normalization
errors. All errors are handled internally and result in `unavailable`.

---

## Attributes per entity

Every entity exposes:

```python
{
    "heima_contract_version": "1.0",
    "adapter_id": "owm",
    "source_entity": "<source_OWM_entity_id>",   # or a list for lux
    "last_updated": "2026-04-27T14:32:00+02:00",
}
```

---

## Repo structure

```
ha-heima-owm-adapter/
├── custom_components/
│   └── heima_owm_adapter/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── sensor.py          # heima_ext_* entities
│       ├── coordinator.py     # DataUpdateCoordinator
│       ├── lux_estimator.py   # lux estimation logic
│       └── const.py
├── tests/
├── hacs.json
└── README.md
```

---

## Signals not covered by this adapter

| Signal                        | Reason for absence                                         | Recommended adapter              |
|--------------------------------|--------------------------------------------------------|-----------------------------------|
| `weather_alert_level`          | OWM is not an authoritative source of civil alerts         | ha-heima-pc-adapter (Italy)      |
| `weather_alert_phenomena`      | Same                                                   | ha-heima-pc-adapter (Italy)      |
