# Heima — External Context Contract v1

**Status:** Normative reference for adapter implementors  
**Last Verified Against Code:** 2026-04-28

---

## Scopo

Heima è agnostico rispetto alle fonti di dati meteorologici e di allerta. Per
consumare contesto esterno, dipende da **adapter**: custom integration HA
indipendenti che normalizzano una fonte specifica (OpenWeatherMap, DWD,
Protezione Civile, stazione meteo casalinga, ecc.) verso un insieme di entità
con naming e semantica stabili.

Questo documento definisce:
- il naming convention degli entity ID prodotti dagli adapter
- la semantica e i vincoli di ogni segnale
- come Heima mappa gli slot canonici alle entità degli adapter via config
- le regole di degradazione se un segnale è assente o non disponibile
- le responsabilità dell'adapter vs. quelle di Heima

---

## Principi

**Naming specifico per fonte.** Ogni adapter scrive entità con entity ID che
includono l'`adapter_id` della fonte: `sensor.heima_ext_<adapter_id>_<slot>`.
Questo permette a più adapter di coesistere senza conflitti (es. OWM e una
stazione casalinga espongono entrambi `outdoor_temp` su entity ID distinti).

**Mapping esplicito in Heima.** L'utente configura in Heima quali entità
mappare su quali slot canonici. Slot non configurati → feature disabilitata,
nessun errore.

**Graceful degradation.** Ogni slot è opzionale. Se l'entità mappata è assente,
`unavailable` o `unknown`, Heima disabilita le feature che ne dipendono senza
errori. Non è un fault.

**Adapter indipendenti.** Un adapter non deve conoscere Heima internamente.
Deve solo esporre le entità con il naming e la semantica corretta. Più adapter
possono coesistere sugli stessi slot (es. OWM per meteo + DPC per allerte) o
sullo stesso slot con fonti diverse (es. OWM e stazione casalinga entrambi per
`outdoor_temp` — l'utente sceglie quale usare nella config Heima).

**Contratto stabile.** Questa specifica è versionata. Breaking change al
contratto (cambi di naming convention, cambi di unità, cambi di dominio valori)
richiedono una nuova versione major. Gli adapter devono dichiarare la versione
del contratto che implementano.

---

## Naming convention entity ID

```
sensor.heima_ext_<adapter_id>_<slot>
```

| Parte         | Descrizione                                           | Esempi                    |
|---------------|-------------------------------------------------------|---------------------------|
| `heima_ext_`  | Prefisso fisso — identifica entità del contratto Heima| —                         |
| `<adapter_id>`| Identificatore breve della fonte, definito dall'adapter | `owm`, `dpc`, `station` |
| `<slot>`      | Nome del segnale canonico (vedi §Slot canonici)       | `outdoor_temp`, `wind_speed` |

### Esempi

| Adapter              | `adapter_id` | Entità prodotte                                                   |
|----------------------|--------------|-------------------------------------------------------------------|
| OWM Adapter          | `owm`        | `sensor.heima_ext_owm_outdoor_temp`, `sensor.heima_ext_owm_wind_speed`, … |
| DPC Adapter          | `dpc`        | `sensor.heima_ext_dpc_weather_alert_level`, `sensor.heima_ext_dpc_weather_alert_phenomena` |
| Stazione casalinga   | `station`    | `sensor.heima_ext_station_outdoor_temp`, `sensor.heima_ext_station_outdoor_humidity`, … |

---

## Slot canonici

Gli slot sono i segnali che Heima conosce e può consumare. Ogni adapter
implementa il sottoinsieme di slot che la sua fonte è in grado di produrre.

| Slot                        | Tipo    | Unità | Descrizione                                          |
|-----------------------------|---------|-------|------------------------------------------------------|
| `outdoor_temp`              | float   | °C    | Temperatura esterna corrente                         |
| `outdoor_humidity`          | float   | %     | Umidità relativa esterna (0–100)                     |
| `outdoor_lux`               | float   | lx    | Illuminamento esterno (misurato o stimato)           |
| `wind_speed`                | float   | m/s   | Velocità vento corrente                              |
| `rain_last_1h`              | float   | mm    | Precipitazioni nell'ultima ora                       |
| `rain_forecast_next_6h`     | float   | mm    | Precipitazioni previste nelle prossime 6 ore         |
| `weather_condition`         | string  | —     | Condizione meteo corrente (enum, vedi §Enumerazioni) |
| `weather_alert_level`       | int     | —     | Livello allerta massimo attivo (0–3)                 |
| `weather_alert_phenomena`   | string  | —     | Fenomeni attivi all'alert level corrente (CSV)       |

---

## Configurazione mapping in Heima

L'utente dichiara nel config flow di Heima quale entità usare per ogni slot:

```yaml
# esempio — sezione external_context nelle opzioni Heima
external_context:
  outdoor_temp: sensor.heima_ext_station_outdoor_temp     # stazione casalinga preferita
  outdoor_humidity: sensor.heima_ext_owm_outdoor_humidity # OWM come fallback
  outdoor_lux: sensor.heima_ext_owm_outdoor_lux
  wind_speed: sensor.heima_ext_owm_wind_speed
  rain_last_1h: sensor.heima_ext_owm_rain_last_1h
  rain_forecast_next_6h: sensor.heima_ext_owm_rain_forecast_next_6h
  weather_condition: sensor.heima_ext_owm_weather_condition
  weather_alert_level: sensor.heima_ext_dpc_weather_alert_level
  weather_alert_phenomena: sensor.heima_ext_dpc_weather_alert_phenomena
```

- Slot non configurati → feature corrispondente disabilitata, nessun errore
- L'utente può mappare slot diversi su adapter diversi liberamente
- Se un'entità configurata è `unavailable`, Heima tratta il slot come assente
  (non esiste un meccanismo di fallback automatico — la selezione della fonte
  è una decisione esplicita dell'utente)

---

## Enumerazioni

### `weather_condition`

| Valore          | Significato                                 |
|-----------------|---------------------------------------------|
| `clear`         | Cielo sereno                                |
| `partly_cloudy` | Parzialmente nuvoloso (< 60% copertura)     |
| `cloudy`        | Nuvoloso (60–90% copertura)                 |
| `overcast`      | Coperto (> 90% copertura, no precipitazioni)|
| `fog`           | Nebbia o foschia                            |
| `rain`          | Pioggia (qualsiasi intensità)               |
| `heavy_rain`    | Pioggia intensa (> 7.5 mm/h)               |
| `storm`         | Temporale con fulmini                       |
| `snow`          | Neve (qualsiasi intensità)                  |
| `unknown`       | Non determinabile dalla fonte               |

### `weather_alert_level`

| Valore | Colore    | Significato                          |
|--------|-----------|--------------------------------------|
| `0`    | Verde     | Nessuna allerta attiva               |
| `1`    | Giallo    | Allerta ordinaria / attenzione       |
| `2`    | Arancione | Allerta moderata / preallarme        |
| `3`    | Rosso     | Allerta grave / allarme              |

---

## Attributi obbligatori per ogni entità

Ogni entità del contratto deve esporre i seguenti attributi HA:

```python
{
    "heima_contract_version": "1.0",   # versione del contratto implementata
    "adapter_id": str,                 # es. "owm" | "dpc" | "station"
    "source_entity": str | list[str],  # entity ID HA sorgente
    "last_updated": ISO8601 str,       # timestamp ultimo aggiornamento dalla fonte
}
```

---

## Responsabilità dell'adapter

L'adapter è responsabile di:

1. **Usare il naming convention** `sensor.heima_ext_<adapter_id>_<slot>`
2. **Normalizzare** i valori dalla fonte verso il dominio e le unità del contratto
3. **Scrivere `unavailable`** se la fonte non è raggiungibile o il dato è fuori
   dominio, invece di scrivere un valore potenzialmente errato
4. **Aggiornare le entità** con frequenza coerente con la natura del segnale
   (meteo corrente: ≤ 10 min; forecast: ≤ 30 min; allerte: ≤ 15 min)
5. **Dichiarare la versione del contratto** in ogni entità tramite attributo
6. **Non interferire** con le entità native HA: le entità `heima_ext_*` sono
   nuove entità create dall'adapter, non alias

---

## Responsabilità di Heima

Heima è responsabile di:

1. Leggere le entità tramite il mapping configurato dall'utente
2. Trattare `unavailable`, `unknown` e assenza dell'entità come equivalenti
   (segnale non disponibile → feature disabilitata)
3. Validare la versione del contratto dall'attributo `heima_contract_version`;
   loggare un warning se incompatibile, non bloccare il runtime
4. Non fare assunzioni sulla fonte: Heima non sa e non deve sapere se il dato
   viene da OWM, DWD, una stazione casalinga o un sensore custom

---

## Degradazione per slot

| Slot assente                          | Comportamento Heima                                         |
|---------------------------------------|-------------------------------------------------------------|
| `outdoor_temp`                        | Safety floor heating disabilitata; vacation curve usa solo orario |
| `outdoor_lux`                         | Lighting usa solo sensori interni                           |
| `outdoor_humidity`                    | Nessun impatto v1                                           |
| `wind_speed`                          | Nessun impatto v1                                           |
| `rain_last_1h` / `rain_forecast_next_6h` | Watering skip disabilitato (v2)                          |
| `weather_condition`                   | Lighting gloomy compensation disabilitata                   |
| `weather_alert_level`                 | Apply filter allerta disabilitato                           |
| `weather_alert_phenomena`             | Notifica fenomeni specifica disabilitata                    |

---

## Versioning del contratto

Il contratto segue semantic versioning (MAJOR.MINOR):

- **MINOR bump**: aggiunta di nuovi slot opzionali; gli adapter esistenti
  restano compatibili
- **MAJOR bump**: cambio naming convention, cambio unità, cambio dominio valori;
  richiede migrazione adapter

Gli adapter devono dichiarare quale versione MAJOR.MINOR implementano.
Heima accetta adapter con MAJOR identica e MINOR ≤ propria.

**Versione corrente del contratto: 1.0**

---

## Adapter di riferimento

| Adapter                   | Repo                                      | `adapter_id` | Slot coperti                                              |
|---------------------------|-------------------------------------------|--------------|-----------------------------------------------------------|
| OWM Adapter               | `heima-labs/ha-heima-owm-adapter`         | `owm`        | temp, humidity, lux, wind, rain, rain_forecast, condition |
| DPC Adapter               | `heima-labs/ha-heima-DPC-adapter`         | `dpc`        | alert_level, alert_phenomena                              |
