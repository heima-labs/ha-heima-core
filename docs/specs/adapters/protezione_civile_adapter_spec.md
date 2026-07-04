# Heima Protezione Civile Adapter — Spec v1

**Status:** Reference spec for implementation  
**Repo target:** `heima-labs/ha-heima-pc-adapter`  
**Contract implemented:** External Context Contract v1.0  
**Last Updated:** 2026-04-27

---

## Purpose

Normalize weather alert data from the **Italian Protezione Civile** into
entities of the [Heima External Context Contract v1](./external_context_contract.md),
reading the entities exposed by the HACS integration
[`caronc/protezione_civile`](https://github.com/caronc/ha-protezione-civile).

The adapter does not query Protezione Civile services directly. It sits as a
normalizer on top of the `caronc/protezione_civile` integration.

---

## Prerequisites

| Requirement                                  | Notes                                                        |
|--------------------------------------------|-------------------------------------------------------------|
| HACS installed in HA                      | To install `caronc/protezione_civile`                   |
| `caronc/protezione_civile` configured     | With the reference comune/zone                              |
| Heima installed                           | Optional for the adapter to function, required to consume it   |

---

## Data source: `caronc/protezione_civile`

The caronc integration exposes one or more `sensor` entities for each
configured zone. Each entity has:

- **State**: current maximum alert level for the zone
  (`Verde` / `Giallo` / `Arancione` / `Rosso` / `unknown`)
- **Attributes**: level for each phenomenon (`idrogeologico`, `temporali`,
  `vento`, `neve_e_gelate`, `mare`, `valanghe`, `incendi_boschivi`, ...)

Each attribute contains the level as a string: `"Verde"`, `"Giallo"`,
`"Arancione"`, `"Rosso"`, `"Non Disponibile"`.

*(Note: state/attribute values and phenomenon IDs above are the literal
Italian strings produced by the upstream `caronc/protezione_civile`
integration and Italy's civil protection service; they are external data
contracts, not adapter documentation, and must not be translated.)*

---

## Entities produced by the adapter

| Heima contract entity                   | Type   | Description                                           |
|------------------------------------------|--------|-------------------------------------------------------|
| `sensor.heima_ext_weather_alert_level`   | int    | Maximum level (0–3) among the selected phenomena      |
| `sensor.heima_ext_weather_alert_phenomena` | string | Phenomena active at the current maximum level (CSV)   |

The adapter does **not** expose continuous weather signals (temp, lux, etc.).
Those are the responsibility of adapters like ha-heima-owm-adapter.

---

## Aggregation logic

### Phenomena configuration (subset)

The user configures which phenomena to consider. The default is **all
available phenomena**. Unconfigured phenomena are ignored in the aggregation.

Supported phenomena (corresponding to the caronc attributes):

| Phenomenon ID             | Display label                |
|-------------------------|------------------------------|
| `idrogeologico`         | Rischio idrogeologico        |
| `temporali`             | Temporali                    |
| `vento`                 | Vento forte                  |
| `neve_e_gelate`         | Neve e gelate                |
| `mare`                  | Mare agitato                 |
| `valanghe`              | Valanghe                     |
| `incendi_boschivi`      | Incendi boschivi             |

*(Display labels are kept in Italian: this adapter is specific to the
Italian civil protection service, and these are the labels the Italian
integration and its users expect.)*

### Level mapping

| caronc value        | Heima `alert_level` |
|----------------------|---------------------|
| `Verde`              | `0`                 |
| `Giallo`             | `1`                 |
| `Arancione`          | `2`                 |
| `Rosso`              | `3`                 |
| `Non Disponibile`    | `unavailable`       |
| absent / error     | `unavailable`       |

### Aggregation

```python
def aggregate_alert_level(
    sensor_entity: str,
    phenomena_subset: list[str],
    hass_states: dict[str, State],
) -> tuple[int | None, list[str]]:
    """
    Returns (max_level, active_phenomena_at_max_level).
    Returns (None, []) if all values are unavailable.
    """
    LEVEL_MAP = {"Verde": 0, "Giallo": 1, "Arancione": 2, "Rosso": 3}

    state = hass_states.get(sensor_entity)
    if state is None or state.state in ("unknown", "unavailable"):
        return None, []

    attributes = state.attributes
    levels: dict[str, int] = {}

    for phenomenon in phenomena_subset:
        raw = attributes.get(phenomenon)
        if raw is None or raw == "Non Disponibile":
            continue
        level = LEVEL_MAP.get(raw)
        if level is not None:
            levels[phenomenon] = level

    if not levels:
        return None, []

    max_level = max(levels.values())
    active = [p for p, l in levels.items() if l == max_level]
    return max_level, active
```

### `weather_alert_phenomena`

The entity contains the phenomena active at the current maximum level, as a
CSV string of phenomenon IDs:

```
"temporali,vento"
```

If `alert_level` is `0` (Verde), `phenomena` is the empty string `""`.
If `alert_level` is `unavailable`, `phenomena` is `unavailable`.

---

## Configuration

The adapter is configurable via the HA Config Flow. Parameters:

| Parameter                | Type          | Default             | Description                                                        |
|--------------------------|---------------|---------------------|--------------------------------------------------------------------|
| `pc_sensor_entity`       | string        | (required)      | Entity ID of the `caronc/protezione_civile` sensor to use as the source |
| `phenomena_subset`       | list[string]  | all phenomena    | Subset of phenomena to consider in the aggregation          |
| `update_interval_min`    | int           | `15`                | Polling frequency of the source entity (minutes)                    |

**`pc_sensor_entity`** is the only required parameter. The user selects it
from a dropdown listing the `protezione_civile` sensors available in HA
(detected via `platform: protezione_civile`).

**`phenomena_subset`** is configurable as a multi-select with all supported
phenomena preselected. The user can deselect the ones that aren't relevant
(e.g. `valanghe` and `mare` for those living in a lowland town).

---

## Update frequency

| Signal              | Frequency | Notes                                                       |
|----------------------|-----------|------------------------------------------------------------|
| `alert_level`        | 15 min    | PC alerts are typically updated hourly           |
| `alert_phenomena`    | 15 min    | Computed together with `alert_level`                         |

The adapter uses a `DataUpdateCoordinator` with a configurable interval.
Polling does not happen via a service call: the adapter reads the HA state
of the caronc entity already in memory (zero overhead on HA).

---

## Error handling

| Condition                                         | Adapter behavior                                  |
|----------------------------------------------------|--------------------------------------------------------|
| caronc entity `unavailable` or `unknown`            | `alert_level` → `unavailable`, `phenomena` → `unavailable` |
| caronc entity not found in HA                    | Same, log warning at startup                            |
| Configured phenomenon absent from attributes       | Phenomenon silently ignored (debug log)          |
| All phenomena in the subset are `Non Disponibile` | `alert_level` → `unavailable`                          |
| Unmappable attribute value                     | Phenomenon ignored, log warning                         |

---

## Attributes per entity

```python
{
    "heima_contract_version": "1.0",
    "adapter_id": "protezione_civile",
    "source_entity": "<pc_sensor_entity>",
    "phenomena_subset": ["idrogeologico", "temporali", ...],   # configured
    "last_updated": "2026-04-27T14:32:00+02:00",
}
```

---

## Expected behavior in Heima

With `alert_level` available, Heima can:

| `alert_level` | Heima behavior (v1)                                                  |
|---------------|---------------------------------------------------------------------------|
| `0`           | No special action                                                   |
| `1` (Giallo)  | Informational notification (optional, user-configurable)               |
| `2` (Arancione)| Notification + apply filter: skip irrigation, postpone outdoor routines    |
| `3` (Rosso)   | Urgent notification + extended apply filter: blocks outdoor routines, suggests closing shutters/curtains |

The `phenomena` enable contextual notifications (e.g. "Wind alert: retract
outdoor awnings") instead of generic messages.

> Heima's exact behavior in response to alerts is defined in the
> Apply/Notifications domain spec, not in this adapter spec.

---

## Repo structure

```
ha-heima-pc-adapter/
├── custom_components/
│   └── heima_pc_adapter/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── sensor.py          # heima_ext_weather_alert_* entities
│       ├── coordinator.py     # DataUpdateCoordinator
│       └── const.py
├── tests/
├── hacs.json
└── README.md
```

---

## v1 limitations

- **One zone per adapter instance.** Those with multiple zones configured in
  caronc must install multiple instances of the adapter, each with its own
  `pc_sensor_entity`. In that case, Heima reads the "main" instance (the
  first one found for the standard entity ID
  `sensor.heima_ext_weather_alert_level`).
- **Italy only.** This adapter is specific to the Italian Protezione Civile.
  For other countries, dedicated adapters exist or will exist (DWD for
  Germany, Meteoalarm for Europe, etc.).
- **Current alert only.** The adapter does not expose future alert
  forecasts. PC alerts are typically issued for the current day or the
  following day; temporal interpretation is left to Heima.

---

## Signals not covered by this adapter

| Signal                      | Reason for absence                              | Recommended adapter    |
|------------------------------|---------------------------------------------|-------------------------|
| `outdoor_temp`               | Not an authoritative source for continuous weather   | ha-heima-owm-adapter    |
| `outdoor_lux`                | Same                                        | ha-heima-owm-adapter    |
| `rain_forecast_next_6h`      | PC does not expose forecast quantities         | ha-heima-owm-adapter    |
| `weather_condition`          | PC does not classify weather conditions         | ha-heima-owm-adapter    |
