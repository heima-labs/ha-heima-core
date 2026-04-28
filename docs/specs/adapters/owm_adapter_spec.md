# Heima OWM Adapter — Spec v1

**Status:** Reference spec per implementazione  
**Repo target:** `heima-labs/ha-heima-owm-adapter`  
**Contratto implementato:** External Context Contract v1.0  
**Last Updated:** 2026-04-27

---

## Scopo

Normalizzare i dati esposti dall'integrazione nativa **OpenWeatherMap** di Home
Assistant verso le entità del [Heima External Context Contract v1](./external_context_contract.md).

L'adapter non chiama direttamente le API di OpenWeatherMap. Legge le entità
HA già create dall'integrazione OWM nativa e le trasforma.

---

## Prerequisiti

| Requisito                        | Note                                                      |
|----------------------------------|-----------------------------------------------------------|
| HA con OWM integration nativa    | Configurabile da Impostazioni → Integrazioni              |
| API key OWM                      | Richiesta dall'integrazione nativa, non dall'adapter      |
| Heima installato                 | Opzionale per il funzionamento dell'adapter, necessario per il consumo |

L'adapter non richiede HACS. È distribuito come custom integration standard.

---

## Entità sorgente OWM → entità contratto Heima

### Mapping diretto

| Entità OWM nativa (HA)                         | Entità contratto Heima                          | Trasformazione                    |
|------------------------------------------------|-------------------------------------------------|-----------------------------------|
| `sensor.openweathermap_temperature`            | `sensor.heima_ext_outdoor_temp`                 | Nessuna (già °C)                  |
| `sensor.openweathermap_humidity`               | `sensor.heima_ext_outdoor_humidity`             | Nessuna (già %)                   |
| `sensor.openweathermap_wind_speed`             | `sensor.heima_ext_wind_speed`                   | Conversione km/h → m/s (÷ 3.6)   |
| `sensor.openweathermap_rain`                   | `sensor.heima_ext_rain_last_1h`                 | Nessuna (già mm)                  |
| `sensor.openweathermap_forecast_precipitation` | `sensor.heima_ext_rain_forecast_next_6h`        | Somma forecast 6h (vedi §Forecast)|
| `weather.openweathermap`                       | `sensor.heima_ext_weather_condition`            | Mapping enum (vedi §Condition)    |

### Entità calcolate

| Entità contratto Heima              | Fonte                                                      |
|-------------------------------------|------------------------------------------------------------|
| `sensor.heima_ext_outdoor_lux`      | Stimato da cloud coverage + UV index + ora solare (vedi §Lux) |

> **Nota:** L'adapter non espone `weather_alert_level` né `weather_alert_phenomena`.
> Questi segnali sono di competenza di adapter dedicati alle fonti di allerta
> (es. ha-heima-pc-adapter). OWM non è una fonte autoritativa di allerte civili.

---

## Logica di normalizzazione

### Condition mapping

OWM espone il condition code come stato dell'entità `weather.openweathermap`.
Il mapping verso il contratto Heima è:

| Stato OWM                                  | `weather_condition` Heima |
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
| qualsiasi altro                            | `unknown`                 |

### Lux estimation

OWM non fornisce illuminamento in lux. L'adapter stima `outdoor_lux` da:

1. **Cloud coverage** (`sensor.openweathermap_cloud_coverage`, %)
2. **UV index** (`sensor.openweathermap_uv_index`) come proxy dell'irraggiamento
3. **Ora solare** calcolata dalla posizione geografica del sistema HA

Algoritmo:

```python
def estimate_lux(cloud_pct: float, uv_index: float, solar_elevation_deg: float) -> float:
    if solar_elevation_deg <= 0:
        return 0.0  # notte

    # lux massimo atteso a cielo sereno a quell'elevazione solare
    max_lux = 120_000 * math.sin(math.radians(solar_elevation_deg))

    # attenuazione nuvolosità (relazione approssimata lineare)
    cloud_factor = 1.0 - (cloud_pct / 100.0) * 0.85

    # attenuazione UV (UV 0 = overcast pesante, UV 11+ = pieno sole tropicale)
    uv_factor = min(uv_index / 11.0, 1.0) if uv_index is not None else 0.5

    estimated = max_lux * cloud_factor * uv_factor
    return round(max(estimated, 0.0), 1)
```

**Approssimazione accettabile:** l'adapter non pretende precisione fotometrica.
L'uso in Heima (lighting compensation, gloomy detection) tollera un errore del
±30%. Se `cloud_coverage` o `uv_index` sono `unavailable`, l'adapter scrive
`unavailable` anche per `outdoor_lux` invece di usare un fallback silente.

### Forecast precipitazioni (next 6h)

OWM nativo espone forecast orari come attributi di `weather.openweathermap`.
L'adapter legge l'attributo `forecast` (lista di dict) e somma le
precipitazioni dei primi 6 record con `datetime` nel futuro:

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

Se `forecast` è assente o vuoto, l'entità è `unavailable`.

---

## Configurazione

L'adapter è configurabile tramite Config Flow HA. Parametri:

| Parametro              | Tipo    | Default                          | Descrizione                                       |
|------------------------|---------|----------------------------------|---------------------------------------------------|
| `owm_entity_prefix`    | string  | `openweathermap`                 | Prefisso delle entità OWM nativa (per installazioni multiple) |
| `weather_entity`       | string  | `weather.openweathermap`         | Entity ID dell'entità weather principale          |
| `ha_latitude`          | float   | (da HA config)                   | Latitudine per calcolo elevazione solare          |
| `ha_longitude`         | float   | (da HA config)                   | Longitudine per calcolo elevazione solare         |
| `update_interval_min`  | int     | `10`                             | Frequenza aggiornamento entità meteo (minuti)     |
| `forecast_interval_min`| int     | `30`                             | Frequenza aggiornamento forecast (minuti)         |

Latitudine e longitudine sono precompilate dalla configurazione di HA e
modificabili dall'utente.

---

## Frequenza di aggiornamento

| Segnale                        | Frequenza    | Note                                         |
|--------------------------------|--------------|----------------------------------------------|
| temp, humidity, wind, rain     | 10 min       | Bound al polling OWM nativo                  |
| weather_condition              | 10 min       | Stessa fonte                                 |
| outdoor_lux                    | 5 min        | Ricalcolo locale (non dipende da polling OWM)|
| rain_forecast_next_6h          | 30 min       | Forecast HA aggiornati meno frequentemente   |

---

## Gestione errori

| Condizione                                  | Comportamento adapter                           |
|---------------------------------------------|-------------------------------------------------|
| Entità OWM sorgente `unavailable`           | Entità heima corrispondente → `unavailable`     |
| Entità OWM sorgente assente (non installata)| Entità heima corrispondente → `unavailable`     |
| Valore fuori dominio (es. humidity > 100)   | Log warning, entità → `unavailable`             |
| Errore nel calcolo lux                      | `outdoor_lux` → `unavailable`, log warning      |
| Forecast malformato                         | `rain_forecast_next_6h` → `unavailable`         |

L'adapter **non solleva eccezioni propagate a HA** per errori di normalizzazione.
Tutti gli errori sono contenuti internamente e risultano in `unavailable`.

---

## Attributi per entità

Ogni entità espone:

```python
{
    "heima_contract_version": "1.0",
    "adapter_id": "owm",
    "source_entity": "<entity_id_sorgente_OWM>",   # o lista per lux
    "last_updated": "2026-04-27T14:32:00+02:00",
}
```

---

## Struttura repo

```
ha-heima-owm-adapter/
├── custom_components/
│   └── heima_owm_adapter/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── sensor.py          # entità heima_ext_*
│       ├── coordinator.py     # DataUpdateCoordinator
│       ├── lux_estimator.py   # logica stima lux
│       └── const.py
├── tests/
├── hacs.json
└── README.md
```

---

## Segnali non coperti da questo adapter

| Segnale                        | Motivo assenza                                         | Adapter raccomandato              |
|--------------------------------|--------------------------------------------------------|-----------------------------------|
| `weather_alert_level`          | OWM non è fonte autoritativa di allerte civili         | ha-heima-pc-adapter (Italia)      |
| `weather_alert_phenomena`      | Idem                                                   | ha-heima-pc-adapter (Italia)      |
