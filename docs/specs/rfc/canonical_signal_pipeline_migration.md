# Migration: Canonical Signal Pipeline

**Status**: Draft
**Date**: 2026-04-13
**Depends on**: `canonical_signal_pipeline_spec.md`
**Target branch**: `refactor/canonical-signal-pipeline`

---

## Goal

Replace `SignalRecorderBehavior` (raw `state_change` events) with
`EventCanonicalizer` + periodic sync function (semantic `room_signal_threshold`
and `room_signal_burst` events). Extend `async_query`. Update `cross_domain.py`
analyzers. Add signal configuration to room config. Replace `primary_threshold`
with `primary_bucket` in bucket-based reactions. Replace `primary_rise_threshold`
with room-level `burst_threshold` in burst-pattern reactions.

---

## Production data — what happens

### EventStore
Contains ~3624 `state_change` events. Not touched by this migration.
Natural eviction: once `state_change` production stops, the FIFO cap expels old
events as new `room_signal_threshold` and `room_signal_burst` events arrive.
Estimated full eviction: 2–3 weeks under normal use.

During the transition period, `cross_domain.py` analyzers find no new `state_change`
events but still find the old ones until eviction. This is acceptable: learning
signal on `state_change` degrades gradually to zero while canonical signal grows.
No complete blackout window.

### Options / config_entry
Room config gains a `signals` array. Bucket-based reaction config loses
`primary_threshold`, gains `primary_bucket`. Burst-based reaction config loses
`primary_rise_threshold`, `primary_threshold_mode`, `corroboration_rise_threshold`,
`corroboration_threshold_mode`; the numeric thresholds move to the room's signal
config. All changes require a one-shot migration at first load (see Step 6).

---

## Intervention order

### Step 1 — Extend `async_query`
**File**: `custom_components/heima/runtime/event_store.py`

Add optional `room_id: str | None` and `subject_id: str | None` parameters.
Filter in the existing loop alongside `event_type` and `since`.

No breaking change: existing call sites omit the new parameters → identical behavior.

### Step 2 — Add signal config to room options
**Files**: `custom_components/heima/config_flow/_steps_rooms.py` (or equivalent),
options schema, translations.

Each room gains a `signals` list. The config flow step for rooms must allow
adding/editing signals with:
- `entity_id`: entity picker, filtered to sensor domain
- `signal_name`: free text, pre-filled with a suggestion based on `device_class`
- `buckets`: list of `{label, upper_bound}`, pre-filled with defaults for the detected `device_class`
- `burst_threshold` (optional): numeric delta threshold for burst detection
- `burst_window_s` (optional, default 600): not used as a sliding window — see spec
- `burst_direction` (optional, default `"up"`): `"up"`, `"down"`, or `"both"`

Default buckets are pre-populated at setup time based on the entity's `device_class`
read from HA. The user can override them. Burst fields are opt-in: left empty unless
the signal is used by a burst-pattern reaction.

### Step 3 — Implement `EventCanonicalizer`
**New file**: `custom_components/heima/runtime/behaviors/event_canonicalizer.py`

Implements `HeimaBehavior`. Replaces `SignalRecorderBehavior`.

Owns all internal state:
- `_bucket_state: dict[tuple[str, str], str]`
- `_burst_baseline: dict[tuple[str, str], tuple[float, datetime]]`
- `_last_burst_ts: dict[tuple[str, str], datetime]`

Responsibilities at setup:
- Read tracked entities from room signal config
- Auto-detect `device_class` for each entity from HA state
- Populate `_bucket_state` baseline silently (no events emitted)
- Initialize `_burst_baseline` with current values for signals with burst config
- Subscribe to `EVENT_STATE_CHANGED`

On each state change: run the bucket-diff algorithm from the spec.
Burst detection runs only in the periodic sync path, not here.

On `on_options_reloaded`: recompute tracked entities and signal config,
re-run silent baseline for both bucket and burst state.
Unsubscribe/resubscribe listener if tracked set changed.

Exposes:
- `signal_bucket(room_id, signal_name) -> str | None`
- `signal_burst_recent(room_id, signal_name, *, window_s: int) -> bool`

Default bucket table (used when room config has no explicit buckets for an entity):
```python
_DEFAULT_BUCKETS: dict[str, list[tuple[float | None, str]]] = {
    "illuminance": [(30, "dark"), (100, "dim"), (300, "ok"), (None, "bright")],
    "carbon_dioxide": [(800, "ok"), (1200, "elevated"), (None, "high")],
    "humidity": [(40, "low"), (70, "ok"), (None, "high")],
}
```
`None` as upper bound means "everything above the previous boundary".
Boundary convention: upper-exclusive (`value < upper_bound → bucket`).

There are no default burst thresholds — burst config is always opt-in.

### Step 4 — Add periodic sync to scheduler
**File**: `custom_components/heima/runtime/engine.py` (scheduler cycle)

Add a call to the periodic sync function on every engine cycle.
The function receives `_bucket_state`, `_burst_baseline`, and `_last_burst_ts`
by reference from `EventCanonicalizer` and the current HA state snapshot.
No new timer, no new class.

The sync function runs two independent algorithms per engine cycle:
1. Bucket sync: detect and correct `_bucket_state` discrepancies
2. Burst detection: compute deltas from `_burst_baseline`, emit `room_signal_burst`
   and reset baseline when threshold is exceeded

### Step 5 — Register EventCanonicalizer, remove SignalRecorderBehavior
**File**: `custom_components/heima/runtime/engine.py` (or coordinator)

Replace `SignalRecorderBehavior` instantiation with `EventCanonicalizer`.
Remove all imports and references to `SignalRecorderBehavior`.

### Step 6 — One-shot options migration
**File**: `custom_components/heima/runtime/engine.py` or a dedicated migration helper
called from `async_reload_options`.

Four transformations on first load after deploy:

**6a — Room signal config (bucket)**: for rooms that have no `signals` key,
auto-populate it by scanning `learning.context_signal_entities` and room learning
source entities. For each entity, detect `device_class` from HA and apply default
buckets. Emit a log info entry for each auto-populated signal.

**6b — Room signal config (burst)**: for entities already used in burst-pattern
reactions (`room_cooling_assist`, ventilation reactions), add `burst_threshold`,
`burst_window_s`, and `burst_direction` to the corresponding signal entry, taking
values from the reaction's `primary_rise_threshold` / `corroboration_rise_threshold`
and `correlation_window_s`. This applies to both primary and corroboration signals.
Emit a log info entry for each auto-populated burst config.

**6c — Bucket-based reaction config**: for reactions in `configured` that have
`primary_threshold` (numeric) but no `primary_bucket` (string), compute the bucket
label by evaluating `primary_threshold` against the room's bucket config for the
matching signal. Replace `primary_threshold` with `primary_bucket` in the stored
config. If the room signal config is not yet available, leave the reaction unchanged
and retry at next reload.

**6d — Burst-based reaction config**: for reactions in `configured` of type
`room_cooling_assist` or similar, remove `primary_rise_threshold`,
`primary_threshold_mode`, `corroboration_rise_threshold`,
`corroboration_threshold_mode` from the persisted config. These values have been
moved to the room's signal config in step 6b. Retain `primary_signal_name`,
`corroboration_signal_name`, `followup_window_s`, and `steps`.

Migration is idempotent: if `signals` already exists, `primary_bucket` is already
present, or burst fields are already absent from the reaction config, no action
is taken.

### Step 7 — Update cross_domain.py
**File**: `custom_components/heima/runtime/analyzers/cross_domain.py`

Replace all `state_change` queries with `room_signal_threshold` or
`room_signal_burst` queries using the extended
`async_query(event_type=..., room_id=..., subject_id=...)`.

- Bucket-based patterns (`room_darkness_lighting_assist`, `room_air_quality_assist`,
  `room_signal_assist`): query `room_signal_threshold`
- Burst-based patterns (`room_cooling_assist`, ventilation): query `room_signal_burst`

Remove dead code:
- `_is_room_lux_event`
- `_is_humidity_event`
- `_is_temperature_event`
- `_is_activation_event`
- `_is_co2_event`

Update matcher logic:
- Threshold reactions: work on `event.data["to_bucket"]` and `event.data["direction"]`
- Burst reactions: work on event presence within a time window
  (`event.data["delta"]` available for diagnostics only — analyzers must not gate
  on it)

Update `_build_cooling_assist_config` to produce `primary_signal_name` and
`corroboration_signal_name` without numeric thresholds.

### Step 8 — Update reaction engine
**File**: `custom_components/heima/runtime/` (reaction execution path)

**Bucket-based reactions** — replace numeric comparison with bucket label match:
```python
# Before
if current_lux < reaction_cfg["primary_threshold"]: execute()

# After
if current_bucket == reaction_cfg["primary_bucket"]: execute()
```
`current_bucket` is read from `_bucket_state[(room_id, signal_name)]` via
`signal_bucket` accessor on `EventCanonicalizer`.

**Burst-based reactions** — replace `RuntimeCompositeMatcher` numeric reads with
burst accessor:
```python
# Before
result = self._matcher.observe(now=now, pending_since=..., spec=self._pattern)
should_fire = result.ready  # numeric rise threshold checked inside

# After
should_fire = engine.signal_burst_recent(
    room_id, primary_signal_name, window_s=followup_window_s
)
if corroboration_signal_name:
    should_fire = should_fire and engine.signal_burst_recent(
        room_id, corroboration_signal_name, window_s=followup_window_s
    )
```

Remove `RuntimeCompositeMatcher` usage from burst-pattern reactions.
`RuntimeCompositeMatcher` may remain for other uses if any exist.

### Step 9 — Update diagnostics
**File**: `custom_components/heima/diagnostics.py`

Add `room_signal_threshold` and `room_signal_burst` to relevant sections.
`state_change` can remain in counts until naturally evicted.
Add a section showing current `_bucket_state` per room (useful for debugging).
Add a section showing `_last_burst_ts` per room/signal (useful for debugging
burst-pattern reactions).

### Step 10 — Update tests
Files affected:
- Tests for `SignalRecorderBehavior` → rewrite for `EventCanonicalizer`
- Tests for `cross_domain.py` → fixtures with `room_signal_threshold` and
  `room_signal_burst` instead of `state_change`
- Tests for `async_query` → add cases for `room_id` and `subject_id` parameters
- Tests for bucket-based reaction engine → replace `primary_threshold` with `primary_bucket`
- Tests for burst-based reaction engine → replace `RuntimeCompositeMatcher` mocks
  with `signal_burst_recent` accessor mocks
- Tests for BurstTracker → baseline reset behavior, directional filtering,
  multi-episode detection

---

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Entity has no `device_class` → no default bucket | Log warning once per entity; skip tracking silently |
| `primary_threshold` → `primary_bucket` migration produces wrong bucket | Migration uses the same bucket config as the canonicalizer — result is consistent by construction |
| `_bucket_state` lost on HA restart | Periodic sync reconstructs it on first engine cycle post-restart |
| `_burst_baseline` lost on HA restart | Periodic sync initializes it from current HA state on first cycle; first burst after restart requires a full delta from that point |
| Analyzers receive zero `room_signal_threshold` / `room_signal_burst` events in first days | Expected and acceptable — learning resumes as new events accumulate |
| Tests mocking `state_change` break | Updated in Step 10, before merge |
| Room with no signal config after deploy | Step 6a auto-populates from existing learning entities |
| Burst-pattern reaction fires immediately after HA restart | `_last_burst_ts` is lost on restart; `signal_burst_recent` returns False until the next real burst — correct behavior |
| Corroboration threshold migrated to wrong signal | Step 6b maps `corroboration_rise_threshold` to the signal named by `corroboration_signal_name` — explicit, not inferred |

---

## Acceptance criteria

- No new `state_change` events in EventStore after deploy
- `EventCanonicalizer` emits exactly one `room_signal_threshold` event per bucket crossing
- Two consecutive readings in the same bucket → zero events emitted
- Multi-bucket jump (e.g. ok→dark skipping dim) → one event, not two
- Burst emitted when delta ≥ threshold; baseline resets; next burst requires a new delta
- Two distinct burst episodes (55→64→73 humidity) → two `room_signal_burst` events
- Burst not emitted if `burst_threshold` is not configured for the signal
- `room_signal_burst` with `burst_direction: "up"` not emitted on falling values
- Periodic sync emits `room_signal_threshold` only when bucket discrepancy detected
- `async_query(event_type="room_signal_threshold", room_id="studio")` returns only events for that room
- `signal_burst_recent(room_id, signal_name, window_s=900)` returns True within window, False after
- `cross_domain.py` contains no `_is_*_event` functions
- Bucket-based reactions in `configured` have `primary_bucket`, not `primary_threshold`
- Burst-based reactions in `configured` have no numeric thresholds — only signal names
- Room config has `signals` array with bucket config for every tracked entity
- Signals used by burst-pattern reactions have `burst_threshold` populated
- All tests green after Step 10
