# Canonical Signal Pipeline Spec

**Status**: Active v1.x canonical signal pipeline contract
**Last Verified Against Code**: 2026-04-18
**Related**: `../core/reaction_identity_spec.md`

---

## Problem

The current `SignalRecorderBehavior` listens directly to HA's `EVENT_STATE_CHANGED`
and writes raw events into the EventStore. Semantic classification happens at
query-time inside analyzers (`_is_room_lux_event`, `_is_humidity_event`, …).

Effects:
- 72% of the EventStore (3624/5000 events) is occupied by raw `state_change` events
- Every reading of an analog sensor (lux, CO2) generates one event
- Semantic logic is duplicated and scattered across analyzers
- The `MAX_RECORDS = 5000` cap is already saturated in production

This violates the architectural invariant: the InputNormalizer exists to produce
canonical signals from raw HA — raw values must never enter the EventStore.

---

## Principle

> Heima learns from canonical signals, not raw values.
> Raw HA state changes are canonicalized before entering the EventStore.
> Analyzers work on semantic events, not sensor readings.

---

## Signal taxonomy

### Discrete signals
The transition is the information. Immediate propagation required.

| Signal | EventStore event type | Status |
|---|---|---|
| Room occupancy | `room_occupancy` | existing |
| House state | `house_state` | existing |
| Household presence | `presence` | existing |
| Calendar (vacation, wfh) | `house_state` or dedicated | existing |

### Contextual media signals
These are contextual strong signals captured in canonicalized form for learning and proposal
scoping. They are not threshold or burst signals and do not require analog bucketing.

| Signal | EventStore event type | Status |
|---|---|---|
| Room TV / projector / media player context | via canonicalized context signal state | existing substrate, explicit v1 clarification |

### Threshold signals
Only the semantic bucket crossing matters, not the continuous value.

| Signal | EventStore event type | Status |
|---|---|---|
| Room lux | `room_signal_threshold` | **new** |
| Room CO2 | `room_signal_threshold` | **new** |
| Room humidity | `room_signal_threshold` | **new** |

### Burst signals
Only a significant rate of change matters, not the absolute value.

| Signal | EventStore event type | Status |
|---|---|---|
| Room humidity rapid rise/drop | `room_signal_burst` | **new** |
| Room temperature rapid rise/drop | `room_signal_burst` | **new** |
| Room CO2 rapid rise/drop | `room_signal_burst` | **new** |

**Outdoor temperature is excluded**: it is already available as `outdoor_temp`
in `EventContext` (house-level snapshot). No dedicated event is needed.

### User intent signals
Discrete event on explicit user action.

| Signal | EventStore event type | Status |
|---|---|---|
| Light on/off | `lighting` | existing |
| Heating setpoint | `heating` | existing |

---

## Signal configuration (per room)

Each tracked signal is configured inside the room config (`rooms[]` in options).
This keeps all room-related data in one place.

```json
{
  "room_id": "studio",
  "signals": [
    {
      "signal_name": "room_lux",
      "entity_id": "sensor.lux_studio",
      "device_class": "illuminance",
      "buckets": [
        {"label": "dark", "upper_bound": 30},
        {"label": "dim",  "upper_bound": 100},
        {"label": "ok",   "upper_bound": 300},
        {"label": "bright","upper_bound": null}
      ]
    },
    {
      "signal_name": "room_humidity",
      "entity_id": "sensor.humidity_bagno",
      "device_class": "humidity",
      "buckets": [
        {"label": "low", "upper_bound": 40},
        {"label": "ok",  "upper_bound": 70},
        {"label": "high","upper_bound": null}
      ],
      "burst_threshold": 8.0,
      "burst_window_s": 600,
      "burst_direction": "up"
    }
  ]
}
```

`device_class` is auto-detected from HA at setup time and stored for reference.
`buckets` are ordered by `upper_bound` ascending; the last entry has `upper_bound: null`
meaning "everything above the previous boundary".

Burst fields are **opt-in**: a signal without `burst_threshold` does not track burst
patterns. The migration auto-populates burst fields only for signals already used
by cooling or ventilation reactions.

### Default buckets by device_class

Used when the user has not customized the bucket configuration.

| device_class | Buckets (label: upper_bound) |
|---|---|
| `illuminance` | dark: 30, dim: 100, ok: 300, bright: null |
| `carbon_dioxide` | ok: 800, elevated: 1200, high: null |
| `humidity` | low: 40, ok: 70, high: null |

There are no default burst thresholds. Burst tracking is always opt-in.

### Burst configuration fields

| Field | Type | Description |
|---|---|---|
| `burst_threshold` | `float` | Minimum absolute delta to qualify as a burst |
| `burst_window_s` | `int` | Not a sliding window — see BurstTracker algorithm |
| `burst_direction` | `"up" \| "down" \| "both"` | Which direction of change qualifies |

### Boundary convention

Boundaries are **upper-exclusive** for the lower bucket:

| Range | Bucket (illuminance example) |
|---|---|
| `[0, 30)` | `dark` |
| `[30, 100)` | `dim` |
| `[100, 300)` | `ok` |
| `[300, ∞)` | `bright` |

In code: `value < upper_bound → bucket`. A reading of exactly 30 lux is `dim`, not `dark`.

### v1 constraint: one entity per signal per room

A room can have at most one entity per `signal_name`. Two reactions in the same
room cannot use different entities for the same signal (e.g. two different lux
sensors both named `room_lux`).

**Reason**: signal configuration lives at room level, not at reaction level. This
eliminates ambiguity about which entity to canonicalize and keeps configuration
simple. Per-reaction entity override is a known limitation of v1, planned for v2
if multi-sensor rooms become a requirement.

### Media-player context clarification

Room-scoped learning/context signals MAY include `media_player.*` entities when they are meaningful
context indicators for the room.

Unlike threshold signals, these entities are not bucketized. They are canonicalized into a bounded
context vocabulary before analyzers use them.

Initial v1 guidance:
- preserve `playing`
- preserve `paused`
- preserve `idle` when useful
- preserve `off`
- degrade ambiguous or unavailable-like states such as `unknown`, empty, or integration-specific
  non-informative placeholders to `off` or, at most, `idle`

Rationale:
- room assists often need to know whether media is active in the room
- the learning system should not depend on unstable vendor-specific raw `media_player` state
  vocabularies
- this keeps media context aligned with the principle that Heima learns from canonical signals, not
  raw HA state labels

---

## Reactions — primary_bucket replaces primary_threshold

With semantic bucket labels available, reactions match on bucket name rather than
a numeric threshold:

```json
{
  "reaction_type": "room_darkness_lighting_assist",
  "room_id": "studio",
  "primary_signal_name": "room_lux",
  "primary_bucket": "dark"
}
```

The reaction engine checks: `current_bucket == primary_bucket → execute`.
No numeric comparison happens outside the canonicalizer.

The numeric `primary_threshold` field is removed from reaction config.
The canonicalizer and the reaction engine are fully decoupled on thresholds:
the canonicalizer uses the room's bucket config, the reaction uses the bucket label.

## Reactions — burst-pattern reactions

Reactions that trigger on rapid signal change (cooling assist, ventilation assist)
use a burst accessor instead of a numeric comparison:

```json
{
  "reaction_type": "room_cooling_assist",
  "room_id": "studio",
  "primary_signal_name": "room_temperature",
  "corroboration_signal_name": "room_humidity",
  "followup_window_s": 900,
  "steps": [...]
}
```

The reaction engine checks:
`signal_burst_recent(room_id, primary_signal_name, window_s=followup_window_s) → execute`

No numeric threshold in the reaction config. The threshold lives in the room's
signal config (`burst_threshold`). Corroboration is optional: if
`corroboration_signal_name` is present, the reaction also checks
`signal_burst_recent` for the corroborating signal.

---

## EventCanonicalizer

### Responsibilities
- Listen to `EVENT_STATE_CHANGED` on tracked entities (threshold signals only)
- Maintain in memory the current bucket for each `(room_id, signal_name)` → `_bucket_state`
- Emit `room_signal_threshold` **only when the bucket changes**
- Filter all intra-bucket noise (lux 45→44→43, all "dark" → no event)
- Expose `signal_bucket(room_id, signal_name) -> str | None` accessor
- Expose `signal_burst_recent(room_id, signal_name, *, window_s: int) -> bool` accessor

### Not responsible for
- Discrete signals (occupancy, house state) — handled by other behaviors
- Drift from offline sensors — handled by the periodic sync function
- Periodic sampling — the event-driven path is purely reactive
- Burst detection — handled by the BurstTracker (periodic sync path)

### Internal state — bucket
```python
_bucket_state: dict[tuple[str, str], str]
# key:   (room_id, signal_name)
# value: current bucket label ("dark", "ok", "high", …)
```

### Algorithm for each received state_change
```
1. entity_id tracked? no → ignore
2. new state is "unavailable" or "unknown"? → ignore silently, do not update _bucket_state
3. compute current bucket from numeric value + room bucket config
4. bucket == _bucket_state[(room_id, signal_name)]? yes → ignore (noise)
5. update _bucket_state
6. emit room_signal_threshold into EventStore
```

### Multi-bucket crossing
If a value jumps across multiple buckets in one reading (e.g. lux 200→20,
skipping `dim`), emit **one event** with the actual transition:
`from_bucket: "ok"`, `to_bucket: "dark"`. Intermediate buckets are not emitted
because no real state existed in them.

### Initialization
At setup, for each tracked entity, read the current HA state and populate
`_bucket_state` silently (no events emitted). This establishes the baseline.

On `on_options_reloaded`: recompute tracked entities and bucket config, then
re-run the silent baseline population. No spurious events are emitted.

---

## BurstTracker

### Responsibilities
- Detect rapid changes in signal values over time
- Emit `room_signal_burst` when the delta from a baseline exceeds `burst_threshold`
- Reset the baseline after each burst emitted
- Expose `signal_burst_recent(room_id, signal_name, *, window_s: int) -> bool`

### Not responsible for
- Bucket state — owned by EventCanonicalizer
- Event-driven detection — BurstTracker runs only in the periodic sync path
- Continuous tracking of absolute values for threshold crossings

### Internal state
```python
_burst_baseline: dict[tuple[str, str], tuple[float, datetime]]
# key:   (room_id, signal_name)
# value: (baseline_value, baseline_ts) — reference point for delta computation

_last_burst_ts: dict[tuple[str, str], datetime]
# key:   (room_id, signal_name)
# value: timestamp of last emitted burst — used by signal_burst_recent
```

BurstTracker is not a separate class. Its state is owned by `EventCanonicalizer`
and its algorithm runs inside the periodic sync function.

### Algorithm (called by periodic sync on every engine cycle)
```
for each (room_id, signal_name) with burst_threshold configured:
  1. read current value from HA entity
  2. entity unavailable/unknown? → skip
  3. no baseline in _burst_baseline? → set baseline = (current_value, now), skip
  4. delta = current_value - baseline_value  (signed)
  5. direction check:
       "up"   → delta >= burst_threshold?
       "down" → delta <= -burst_threshold?
       "both" → abs(delta) >= burst_threshold?
     condition not met? → skip
  6. update _burst_baseline[(room_id, signal_name)] = (current_value, now)
  7. update _last_burst_ts[(room_id, signal_name)] = now
  8. emit room_signal_burst into EventStore
```

**Baseline reset** (step 6): after a burst is emitted, the baseline resets to the
current value. A subsequent burst requires a new delta ≥ threshold from this new
reference point. This correctly captures multiple distinct burst episodes
(e.g. humidity 55→64→73 produces two separate bursts).

**No cooldown timer**: the reaction engine's `followup_window_s` provides the
effective cooldown. The burst tracker itself does not suppress consecutive bursts
beyond the baseline reset.

### `signal_burst_recent` accessor
```python
def signal_burst_recent(
    self,
    room_id: str,
    signal_name: str,
    *,
    window_s: int,
) -> bool:
    last = self._last_burst_ts.get((room_id, signal_name))
    if last is None:
        return False
    return (now() - last).total_seconds() <= window_s
```

The `window_s` parameter is provided by the reaction (typically its
`followup_window_s`). The room config does not define recency — only the threshold
and direction.

---

## Periodic sync function

### Responsibilities
Two independent safety nets, both called on every engine cycle:

1. **Bucket sync**: detect discrepancies between current HA state and `_bucket_state`
   (handles HA restarts and offline sensor recovery).
2. **Burst detection**: compute deltas from `_burst_baseline` and emit
   `room_signal_burst` when threshold is exceeded.

### Not responsible for
- Continuous tracking of analog values
- Producing periodic learning events for stable sensors
- Replacing the EventCanonicalizer

### Bucket sync algorithm
```
for each (room_id, signal_name) in tracked signals:
  1. read current value from HA entity
  2. entity unavailable/unknown? → skip
  3. compute current bucket from room bucket config
  4. bucket == _bucket_state[(room_id, signal_name)]? → skip
  5. update _bucket_state
  6. emit room_signal_threshold with source = "periodic_sync"
```

### Burst detection algorithm
See BurstTracker section above.

Since `_bucket_state`, `_burst_baseline`, and `_last_burst_ts` are shared by
reference, the EventCanonicalizer always sees the corrected state after sync.
No duplicate events can occur.

---

## Emitted event formats

### `room_signal_threshold`

```json
{
  "ts": "2026-04-13T14:32:00+00:00",
  "event_type": "room_signal_threshold",
  "room_id": "studio",
  "domain": "sensor",
  "subject_type": "signal",
  "subject_id": "room_lux",
  "source": null,
  "context": { "...EventContext standard fields..." },
  "data": {
    "signal_name": "room_lux",
    "entity_id": "sensor.lux_studio",
    "from_bucket": "ok",
    "to_bucket": "dark",
    "direction": "down",
    "value": 43.2,
    "device_class": "illuminance"
  }
}
```

Field notes:
- `subject_id`: the `signal_name` configured for this entity in the room config.
- `source`: `null` for EventCanonicalizer (event-driven path); `"periodic_sync"` for the sync path.
- `direction`: `"up"` if `to_bucket` has a higher index than `from_bucket`, `"down"` otherwise.
- `value`: raw numeric reading at the time of crossing, for debugging only. Analyzers must use `to_bucket`.

### `room_signal_burst`

```json
{
  "ts": "2026-04-13T14:32:00+00:00",
  "event_type": "room_signal_burst",
  "room_id": "bagno",
  "domain": "sensor",
  "subject_type": "signal",
  "subject_id": "room_humidity",
  "source": "periodic_sync",
  "context": { "...EventContext standard fields..." },
  "data": {
    "signal_name": "room_humidity",
    "entity_id": "sensor.humidity_bagno",
    "delta": 9.2,
    "direction": "up",
    "from_value": 58.0,
    "to_value": 67.2,
    "burst_threshold": 8.0,
    "burst_window_s": 600,
    "device_class": "humidity"
  }
}
```

Field notes:
- `source`: always `"periodic_sync"` — burst detection runs only in the periodic sync path.
- `delta`: signed value (positive for "up", negative for "down").
- `from_value`: baseline value at the time of the previous burst (or initial baseline).
- `burst_threshold` and `burst_window_s`: copied from room config for traceability.
- Analyzers must not use `delta` for logic — use the event's presence within a time window.

**Independence**: `room_signal_threshold` and `room_signal_burst` are emitted independently.
A single sensor reading can trigger both if a bucket is crossed and the delta exceeds the
burst threshold simultaneously.

---

## async_query extension

`async_query` must be extended with two optional parameters:

```python
async def async_query(
    self,
    *,
    event_type: str | None = None,
    room_id: str | None = None,
    subject_id: str | None = None,
    since: str | None = None,
    limit: int | None = None,
) -> list[HeimaEvent]: ...
```

Both `room_id` and `subject_id` are top-level fields on `HeimaEvent` (not inside
`data`), so filtering is clean and requires no introspection of the payload.
All existing call sites remain valid — omitting the new parameters preserves
current behavior.

---

## Impact on EventStore

### Removed event type
`state_change` — no longer produced by any behavior after this change.
Existing events expire through natural FIFO eviction as new events fill the cap.
No migration required.

### New event types
- `room_signal_threshold` — semantic bucket crossing
- `room_signal_burst` — rapid rate of change

### Expected volume
- `room_signal_threshold`: 2–4 events per signal per day (bucket crossings)
- `room_signal_burst`: 0–3 events per signal per day (only for signals with burst config)
- Conservative estimate with 5 rooms × 3 signals × 4 events/day: **~60 events/day**
  vs. the current ~100–200 `state_change`/day

With `MAX_RECORDS = 5000` and TTL 60 days: cap no longer saturated.
Reducing `MAX_RECORDS` to 2000 and TTL to 30 days may be evaluated post-deploy.

---

## Impact on analyzers

### cross_domain.py
Replace `state_change` queries with `room_signal_threshold` and `room_signal_burst`
queries as appropriate per reaction type.

Remove all runtime classification functions — bucket label and burst presence are
already in the event payload.

Functions to remove:
- `_is_room_lux_event`
- `_is_humidity_event`
- `_is_temperature_event`
- `_is_activation_event`
- `_is_co2_event`

New query pattern (threshold):
```python
# Before
state_changes = await event_store.async_query(event_type="state_change")
lux_events = [e for e in state_changes if _is_room_lux_event(e)]

# After
lux_events = await event_store.async_query(
    event_type="room_signal_threshold",
    room_id=room_id,
    subject_id="room_lux",
)
# lux_events[i].data["from_bucket"], ["to_bucket"], ["direction"] already available
```

New query pattern (burst):
```python
burst_events = await event_store.async_query(
    event_type="room_signal_burst",
    room_id=room_id,
    subject_id="room_humidity",
)
# burst_events[i].data["delta"], ["direction"] available — presence within window is the signal
```

---

## What does not change

- `EventContext` — unchanged, continues to capture house-level snapshot per cycle
- Event types `lighting`, `heating`, `presence`, `room_occupancy`, `house_state` — unchanged
- `InputNormalizer` and the evaluation DAG — unchanged
- Public API (HA services, HA events) — unchanged

---

## Post-implementation invariants

1. The EventStore never contains raw analog sensor readings
2. Every `room_signal_threshold` event represents a semantic bucket transition, not a measurement
3. Every `room_signal_burst` event represents a significant rate of change, not a measurement
4. Analyzers contain no sensor classification logic (`_is_*_event` functions)
5. The canonicalizer and the reaction engine are decoupled on thresholds: the canonicalizer
   uses room bucket/burst config, reactions match on bucket labels or call `signal_burst_recent`
6. `_bucket_state` is the single source of truth for the current bucket of each signal
7. `_burst_baseline` resets after each burst emitted — consecutive bursts require a new delta
   from the new reference point
8. `signal_burst_recent` is the only mechanism reactions use to check burst patterns —
   no numeric comparisons in reaction code
9. One entity per signal per room — enforced by room config structure (v1 constraint)
