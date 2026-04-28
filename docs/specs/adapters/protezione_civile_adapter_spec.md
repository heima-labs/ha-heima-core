# Heima Protezione Civile Adapter — Spec v1

**Status:** Reference spec per implementazione  
**Repo target:** `heima-labs/ha-heima-pc-adapter`  
**Contratto implementato:** External Context Contract v1.0  
**Last Updated:** 2026-04-27

---

## Scopo

Normalizzare i dati di allerta meteo della **Protezione Civile Italiana** verso
le entità del [Heima External Context Contract v1](./external_context_contract.md),
leggendo le entità esposte dall'integrazione HACS
[`caronc/protezione_civile`](https://github.com/caronc/ha-protezione-civile).

L'adapter non interroga direttamente i servizi della Protezione Civile.
Si posiziona come normalizzatore sopra l'integrazione `caronc/protezione_civile`.

---

## Prerequisiti

| Requisito                                  | Note                                                        |
|--------------------------------------------|-------------------------------------------------------------|
| HACS installato in HA                      | Per installare `caronc/protezione_civile`                   |
| `caronc/protezione_civile` configurato     | Con comune/zona di riferimento                              |
| Heima installato                           | Opzionale per il funzionamento, necessario per il consumo   |

---

## Fonte dati: `caronc/protezione_civile`

L'integrazione caronc espone una o più entità di tipo `sensor` per ogni zona
configurata. Ogni entità ha:

- **State**: livello allerta massimo corrente per la zona
  (`Verde` / `Giallo` / `Arancione` / `Rosso` / `unknown`)
- **Attributi**: livello per ogni fenomeno (`idrogeologico`, `temporali`,
  `vento`, `neve_e_gelate`, `mare`, `valanghe`, `incendi_boschivi`, ...)

Ogni attributo contiene il livello come stringa: `"Verde"`, `"Giallo"`,
`"Arancione"`, `"Rosso"`, `"Non Disponibile"`.

---

## Entità prodotte dall'adapter

| Entità contratto Heima                   | Tipo   | Descrizione                                           |
|------------------------------------------|--------|-------------------------------------------------------|
| `sensor.heima_ext_weather_alert_level`   | int    | Livello massimo (0–3) tra i fenomeni selezionati      |
| `sensor.heima_ext_weather_alert_phenomena` | string | Fenomeni attivi al livello massimo corrente (CSV)   |

L'adapter **non** espone segnali meteo continui (temp, lux, ecc.).
Questi sono di competenza di adapter come ha-heima-owm-adapter.

---

## Logica di aggregazione

### Configurazione fenomeni (sottoinsieme)

L'utente configura quali fenomeni considerare. Il default è **tutti i fenomeni
disponibili**. Fenomeni non configurati vengono ignorati nell'aggregazione.

Fenomeni supportati (corrispondenti agli attributi caronc):

| ID fenomeno             | Label display                |
|-------------------------|------------------------------|
| `idrogeologico`         | Rischio idrogeologico        |
| `temporali`             | Temporali                    |
| `vento`                 | Vento forte                  |
| `neve_e_gelate`         | Neve e gelate                |
| `mare`                  | Mare agitato                 |
| `valanghe`              | Valanghe                     |
| `incendi_boschivi`      | Incendi boschivi             |

### Mapping livelli

| Valore caronc        | `alert_level` Heima |
|----------------------|---------------------|
| `Verde`              | `0`                 |
| `Giallo`             | `1`                 |
| `Arancione`          | `2`                 |
| `Rosso`              | `3`                 |
| `Non Disponibile`    | `unavailable`       |
| assente / errore     | `unavailable`       |

### Aggregazione

```python
def aggregate_alert_level(
    sensor_entity: str,
    phenomena_subset: list[str],
    hass_states: dict[str, State],
) -> tuple[int | None, list[str]]:
    """
    Returns (max_level, active_phenomena_at_max_level).
    Returns (None, []) se tutti i valori sono unavailable.
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

L'entità contiene i fenomeni attivi al livello massimo corrente, come stringa
CSV con gli ID fenomeno:

```
"temporali,vento"
```

Se `alert_level` è `0` (Verde), `phenomena` è stringa vuota `""`.
Se `alert_level` è `unavailable`, `phenomena` è `unavailable`.

---

## Configurazione

L'adapter è configurabile tramite Config Flow HA. Parametri:

| Parametro                | Tipo          | Default             | Descrizione                                                        |
|--------------------------|---------------|---------------------|--------------------------------------------------------------------|
| `pc_sensor_entity`       | string        | (obbligatorio)      | Entity ID del sensore `caronc/protezione_civile` da usare come fonte |
| `phenomena_subset`       | list[string]  | tutti i fenomeni    | Sottoinsieme di fenomeni da considerare nell'aggregazione          |
| `update_interval_min`    | int           | `15`                | Frequenza polling dell'entità sorgente (minuti)                    |

**`pc_sensor_entity`** è l'unico parametro obbligatorio. L'utente lo seleziona
da una dropdown che elenca i sensori `protezione_civile` disponibili in HA
(rilevati per `platform: protezione_civile`).

**`phenomena_subset`** è configurabile come multi-select con tutti i fenomeni
supportati preselezionati. L'utente può deselezionare quelli non rilevanti
(es. `valanghe` e `mare` per chi è in città di pianura).

---

## Frequenza di aggiornamento

| Segnale              | Frequenza | Note                                                       |
|----------------------|-----------|------------------------------------------------------------|
| `alert_level`        | 15 min    | Le allerte PC si aggiornano tipicamente ogni ora           |
| `alert_phenomena`    | 15 min    | Calcolato insieme ad `alert_level`                         |

L'adapter usa un `DataUpdateCoordinator` con intervallo configurabile.
Il polling non avviene tramite service call: l'adapter legge lo stato HA
dell'entità caronc già presente in memoria (zero overhead su HA).

---

## Gestione errori

| Condizione                                         | Comportamento adapter                                  |
|----------------------------------------------------|--------------------------------------------------------|
| Entità caronc `unavailable` o `unknown`            | `alert_level` → `unavailable`, `phenomena` → `unavailable` |
| Entità caronc non trovata in HA                    | Idem, log warning a startup                            |
| Fenomeno configurato assente negli attributi       | Fenomeno ignorato silenziosamente (log debug)          |
| Tutti i fenomeni del subset sono `Non Disponibile` | `alert_level` → `unavailable`                          |
| Valore attributo non mappabile                     | Fenomeno ignorato, log warning                         |

---

## Attributi per entità

```python
{
    "heima_contract_version": "1.0",
    "adapter_id": "protezione_civile",
    "source_entity": "<pc_sensor_entity>",
    "phenomena_subset": ["idrogeologico", "temporali", ...],   # configurati
    "last_updated": "2026-04-27T14:32:00+02:00",
}
```

---

## Comportamento atteso in Heima

Con `alert_level` disponibile, Heima può:

| `alert_level` | Comportamento Heima (v1)                                                  |
|---------------|---------------------------------------------------------------------------|
| `0`           | Nessuna azione speciale                                                   |
| `1` (Giallo)  | Notifica informativa (opzionale, configurabile dall'utente)               |
| `2` (Arancione)| Notifica + apply filter: evita irrigazione, posticipa routine esterne    |
| `3` (Rosso)   | Notifica urgente + apply filter esteso: blocca routine outdoor, suggerisce chiusura tapparelle/tende |

I `phenomena` permettono notifiche contestuali (es. "Allerta vento: ritira
tende esterne") invece di messaggi generici.

> Il comportamento esatto di Heima in risposta agli alert è definito nella spec
> del dominio Apply/Notifications, non in questa spec adapter.

---

## Struttura repo

```
ha-heima-pc-adapter/
├── custom_components/
│   └── heima_pc_adapter/
│       ├── __init__.py
│       ├── manifest.json
│       ├── config_flow.py
│       ├── sensor.py          # entità heima_ext_weather_alert_*
│       ├── coordinator.py     # DataUpdateCoordinator
│       └── const.py
├── tests/
├── hacs.json
└── README.md
```

---

## Limitazioni v1

- **Una sola zona per istanza adapter.** Chi ha più zone configurate in caronc
  deve installare più istanze dell'adapter, ognuna con il proprio `pc_sensor_entity`.
  In quel caso, Heima legge l'istanza "principale" (la prima trovata per entity ID
  standard `sensor.heima_ext_weather_alert_level`).
- **Solo Italia.** Questo adapter è specifico per la Protezione Civile italiana.
  Per altri paesi esistono o esisteranno adapter dedicati (DWD per Germania,
  Meteoalarm per Europa, ecc.).
- **Solo allerta in corso.** L'adapter non espone previsioni di allerta futura.
  Le allerte PC vengono emesse tipicamente per il giorno corrente o il giorno
  successivo; l'interpretazione temporale è lasciata a Heima.

---

## Segnali non coperti da questo adapter

| Segnale                      | Motivo assenza                              | Adapter raccomandato    |
|------------------------------|---------------------------------------------|-------------------------|
| `outdoor_temp`               | Fonte non autoritativa per meteo continuo   | ha-heima-owm-adapter    |
| `outdoor_lux`                | Idem                                        | ha-heima-owm-adapter    |
| `rain_forecast_next_6h`      | PC non espone quantitativi previsti         | ha-heima-owm-adapter    |
| `weather_condition`          | PC non classifica condizioni meteo          | ha-heima-owm-adapter    |
