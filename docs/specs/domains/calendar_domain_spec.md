# CalendarDomain — Mini Spec v0.1

**Status:** Active v1.x calendar domain contract (implemented/partial)
**Last Verified Against Code:** 2026-04-03

## Goal
Integrate events from HA calendar entities into Heima to enable proactive
schedule-based behavior (vacation, WFH) and provide lookahead for future domains.

## Position in the runtime
```
InputNormalizer → People → Occupancy → Calendar → HouseState → Lighting → Heating → Security → Apply
```

Note:
- `CalendarDomain` is already present in the runtime and is evaluated before `HouseStateDomain`
- the most important implemented integration today is `calendar -> house_state`
- `HeatingDomain` can already consume the resulting context, but product-level heating usage remains limited

## Configuration

```yaml
calendar_entities: [calendar.personal, calendar.work]  # list
lookahead_days: 7          # default 7, configurable
cache_ttl_hours: 2         # default 2, configurable
calendar_keywords:
  vacation: ["vacanza", "ferie", "viaggio", "vacation"]
  holiday: ["festivo", "festa nazionale", "bank holiday", "national holiday", "public holiday", "giorno festivo", "holiday"]
  day_off: ["giorno libero", "day off", "permesso", "recupero", "riposo"]
  wfh:      ["wfh", "smart working", "lavoro da casa", "remote"]
  office:   ["ufficio", "office", "in sede"]
  visitor:  ["ospiti", "visitor", "amici", "guests"]
```

*(The keyword lists above are Heima's intentional Italian/English calendar
keyword matching data — not documentation prose — and are preserved as-is;
see CLAUDE.md non-goals.)*

Keywords are pre-filled but editable by the user in the config flow.
Matching is **case-insensitive, substring**.

## Data model

```python
@dataclass
class CalendarEvent:
    summary: str
    start: datetime
    end: datetime
    all_day: bool
    category: Literal["vacation", "holiday", "day_off", "wfh", "office", "visitor", "unknown"]
    calendar_entity: str

@dataclass
class CalendarResult:
    current_events: list[CalendarEvent]    # active now
    upcoming_events: list[CalendarEvent]   # within lookahead_days
    is_vacation_active: bool               # vacation active now or all-day today
    is_holiday_today: bool                 # holiday active now or all-day today
    is_day_off_today: bool                 # day_off active now or all-day today
    is_wfh_today: bool                     # wfh today AND no office today
    is_office_today: bool                  # explicit office today
    next_vacation: CalendarEvent | None    # first future vacation
    cache_ts: datetime                     # timestamp of the last fetch
    cache_hit: bool                        # true if data comes from cache
```

## WFH classification logic

Priority is resolved entirely inside CalendarDomain:

```
is_office_today = at least one "office" category event active/all-day today
is_wfh_today    = at least one "wfh" category event today AND NOT is_office_today
```

`office` takes precedence over `wfh` if both are present on the same day.

`holiday` and `day_off` are at-home rest categories: they disable the `working` candidate, but
do not activate `vacation_mode`.

## Fetch behavior

- **Current event**: read directly from `calendar.<entity>` state + attributes
  (already in the normal cycle, no service call)
- **Lookahead**: `calendar.get_events` call with range `[now, now + lookahead_days]`
- The lookahead call happens **only if the cache has expired**
  (`now - cache_ts > cache_ttl_hours`)
- If the call fails: keeps the previous cache, logs a warning, `cache_hit=True`
- If there's no cache and the call fails: empty `CalendarResult`,
  downstream domains degrade gracefully

## Integration with existing domains

**HouseStateDomain — work_window:**

| Signal                        | Result         |
|-------------------------------|-------------------|
| `is_office_today=True`        | `work_window=False` (away from home) |
| `is_day_off_today=True`       | `work_candidate=False` (day off) |
| `is_holiday_today=True`       | `work_candidate=False` (holiday) |
| `is_wfh_today=True`           | `work_window=True` (working from home) |
| no WFH/office calendar event | fallback to `work_window_entity` (if configured) |

The calendar takes precedence over `work_window_entity`; the external sensor is used only if no
`office`, `day_off`, `holiday`, or `wfh` calendar event is present today.

**HeatingDomain:**
- `CalendarResult` is already available in the runtime shared state
- today the most important bridge for heating goes through `house_state` first
- a richer heating use of the calendar remains a future refinement

**Future domains** (e.g. Watering):
- Read `CalendarResult` from `CanonicalState` — zero coupling with CalendarDomain

## Runtime shared state
`CalendarResult` is written to the runtime shared state at the end of every cycle.
The cache TTL survives across cycles: the domain compares `cache_ts` with `now`
on every cycle to decide whether to refetch.

## Diagnostics

The domain exposes diagnostics with:
- `cache_ts`
- `cached_events_count`
- `cached_events`

The engine payload also includes the `calendar` fragment in the runtime diagnostics.

For v1.x operability, the surface SHOULD also expose a compact, readable summary without having
to inspect the full event list.

The summary SHOULD include at least:
- `configured_entities`
- `current_events_count`
- `upcoming_events_count`
- `is_vacation_active`
- `is_day_off_today`
- `is_holiday_today`
- `is_wfh_today`
- `is_office_today`
- `next_vacation`

This summary can live:
- in the config-entry diagnostics
- in support CLIs
- in any bounded summary menus of the config/options flow

## Graceful degradation
- No `calendar_entities` configured → domain disabled, no effect on downstream domains
- Entity unavailable → silently skipped, the others are processed
- All failures → empty `CalendarResult`, Heima's behavior unchanged

## Out of scope (v1.x)
- Proactive notifications based on future events (e.g. "system OK before vacation")
  — requires a ProposalEngine extension
- Modifying/creating events from Heima
- Structured event parsing (keyword matching only)
