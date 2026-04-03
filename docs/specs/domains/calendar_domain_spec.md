# CalendarDomain — Mini Spec v0.1

**Status:** Active v1.x calendar domain contract (implemented/partial)
**Last Verified Against Code:** 2026-04-03

## Obiettivo
Integrare eventi da calendar entities HA in Heima per abilitare comportamenti
proattivi basati su agenda (vacation, WFH) e fornire lookahead a domini futuri.

## Posizione nel runtime
```
InputNormalizer → People → Occupancy → Calendar → HouseState → Lighting → Heating → Security → Apply
```

Note:
- `CalendarDomain` is already present in the runtime and is evaluated before `HouseStateDomain`
- the most important implemented integration today is `calendar -> house_state`
- `HeatingDomain` can already consume the resulting context, but product-level heating usage remains limited

## Configurazione

```yaml
calendar_entities: [calendar.personal, calendar.work]  # lista
lookahead_days: 7          # default 7, configurabile
cache_ttl_hours: 2         # default 2, configurabile
calendar_keywords:
  vacation: ["vacanza", "holiday", "ferie", "viaggio", "vacation"]
  wfh:      ["wfh", "smart working", "lavoro da casa", "remote"]
  office:   ["ufficio", "office", "in sede"]
  visitor:  ["ospiti", "visitor", "amici", "guests"]
```

Le keyword sono precompilate ma editabili dall'utente nel config flow.
Il matching è **case-insensitive, substring**.

## Modello dati

```python
@dataclass
class CalendarEvent:
    summary: str
    start: datetime
    end: datetime
    all_day: bool
    category: Literal["vacation", "wfh", "office", "visitor", "unknown"]
    calendar_entity: str

@dataclass
class CalendarResult:
    current_events: list[CalendarEvent]    # attivi ora
    upcoming_events: list[CalendarEvent]   # entro lookahead_days
    is_vacation_active: bool               # vacation attiva ora o tutto-giorno oggi
    is_wfh_today: bool                     # wfh oggi E nessun office oggi
    is_office_today: bool                  # office esplicito oggi
    next_vacation: CalendarEvent | None    # prima vacation futura
    cache_ts: datetime                     # timestamp ultimo fetch
    cache_hit: bool                        # true se dati da cache
```

## Logica di classificazione WFH

La priorità si risolve interamente dentro CalendarDomain:

```
is_office_today = almeno un evento categoria "office" attivo/tutto-giorno oggi
is_wfh_today    = almeno un evento categoria "wfh" oggi AND NOT is_office_today
```

`office` prevale su `wfh` se entrambi presenti nello stesso giorno.

## Comportamento del fetch

- **Evento corrente**: lettura diretta da `calendar.<entity>` state + attributi
  (già nel ciclo normale, no service call)
- **Lookahead**: chiamata `calendar.get_events` con range `[now, now + lookahead_days]`
- La chiamata lookahead avviene **solo se cache scaduta**
  (`now - cache_ts > cache_ttl_hours`)
- Se la chiamata fallisce: mantiene cache precedente, logga warning, `cache_hit=True`
- Se non c'è cache e la chiamata fallisce: `CalendarResult` vuoto,
  domini downstream degradano gracefully

## Integrazione con domini esistenti

**HouseStateDomain — work_window:**

| Segnale                        | Risultato         |
|-------------------------------|-------------------|
| `is_office_today=True`        | `work_window=False` (fuori casa) |
| `is_wfh_today=True`           | `work_window=True` (lavoro da casa) |
| nessun evento calendario WFH/office | fallback a `work_window_entity` (se configurato) |

Calendario prevale su `work_window_entity`; il sensore esterno è usato solo
se nessun evento calendario WFH/office è presente oggi.

**HeatingDomain:**
- `CalendarResult` è già disponibile nel runtime shared state
- il ponte più importante per heating oggi passa prima da `house_state`
- un uso heating più ricco del calendario resta un refinement futuro

**Domini futuri** (es. Watering):
- Leggono `CalendarResult` da `CanonicalState` — zero accoppiamento con CalendarDomain

## Runtime shared state
`CalendarResult` viene scritto nel runtime shared state al termine di ogni ciclo.
Il TTL della cache sopravvive ai cicli: il dominio confronta `cache_ts` con `now`
ad ogni ciclo per decidere se rifetchare.

## Diagnostics

Il dominio espone diagnostics con:
- `cache_ts`
- `cached_events_count`
- `cached_events`

Il payload engine include anche il frammento `calendar` nelle diagnostics runtime.

## Degradazione graceful
- Nessuna `calendar_entities` configurata → dominio disabled, nessun effetto sui downstream
- Entity non disponibile → saltata silenziosamente, le altre vengono processate
- Tutti i fallimenti → `CalendarResult` vuoto, comportamento Heima invariato

## Fuori scope (v1.x)
- Notifiche proattive basate su eventi futuri (es. "impianto OK prima delle vacanze")
  — richiede ProposalEngine extension
- Modifica/creazione eventi da Heima
- Parsing strutturato di eventi (solo keyword matching)
