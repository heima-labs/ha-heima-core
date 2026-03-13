# Heima Learning System — Specification v1

**Status:** Partial — core slices implemented on `main`
**Date:** 2026-03-10
**Last Verified Against Code:** 2026-03-11

---

## 1. Context and Motivation

Heima runs a DAG evaluation cycle producing `DecisionSnapshot` objects. As of v0.4.0:

- `SnapshotBuffer` holds 20 in-memory snapshots (lost on restart)
- `PresencePatternReaction` learns arrival times in-memory only (lost on restart)
- `NaiveLearningBackend` exists but is wired to no reaction by default
- No pattern data survives restart
- No mechanism exists to propose new reactions to the user

The goal is a phased, persistent, async-safe learning pipeline that:
1. Captures lightweight domain transition events to durable storage
2. Runs offline pattern analyzers (not on the hot eval cycle)
3. Surfaces detected patterns as user-reviewable proposals
4. Converts accepted proposals into persisted, managed reactions

## 1.1 Implementation Matrix (as of 2026-03-11)

| Phase | Status | Notes |
|---|---|---|
| P1 EventStore | Implemented | `runtime/event_store.py` with persistence, TTL, cap, query |
| P1b EventRecorderBehavior | Implemented | `runtime/behaviors/event_recorder.py` |
| P2 PresencePatternAnalyzer | Implemented | `runtime/analyzers/presence.py` |
| P3 HeatingPatternAnalyzer | Implemented | `runtime/analyzers/heating.py` + `heating_recorder.py` |
| P4 ProposalEngine | Implemented | `runtime/proposal_engine.py`, periodic coordinator run |
| P5 Approval Flow | Implemented | Config flow step `proposals` accepts/rejects proposals |
| P6 Generalization | Partial | `IPatternAnalyzer` exists; ecosystem/process still RFC |

---

## 2. Architecture Overview

```
HA Event Loop (hot path — eval cycle)
┌──────────────────────────────────────────────────────────┐
│  engine.async_evaluate()                                 │
│    ↓ on_snapshot()                                       │
│    EventRecorderBehavior  ──── append() ──→ EventStore   │
│    (detects transitions, writes PresenceEvent /          │
│     HeatingEvent / HouseStateEvent)                      │
└──────────────────────────────────────────────────────────┘
                                │  (async, non-blocking)
                                ↓
                          EventStore (HA Storage)
                    "heima_pattern_events" key
                    max 5000 records, 60-day TTL

Periodic async task (off hot path — every 6h + startup)
┌──────────────────────────────────────────────────────────┐
│  ProposalEngine.async_run()                              │
│    → PresencePatternAnalyzer.analyze(event_store)        │
│    → HeatingPatternAnalyzer.analyze(event_store)         │
│    → aggregate proposals                                 │
│    → persist to ProposalStore                            │
│    → write "heima_reaction_proposals" sensor             │
└──────────────────────────────────────────────────────────┘

Options Flow (user-driven)
┌──────────────────────────────────────────────────────────┐
│  "proposals" step: list pending proposals                │
│  Accept → write to options["reactions"]["configured"]    │
│  Reject → mark proposal as rejected in store             │
│  On engine reload: register configured reactions         │
└──────────────────────────────────────────────────────────┘
```

**Key design rules:**
- EventStore writes are fire-and-forget: `hass.async_create_task(event_store.async_append(event))`
- Analyzers run off-cycle: `async_add_executor_job()` or plain async tasks, never inline in `async_evaluate()`
- ProposalEngine is owned by the coordinator, not the engine
- EventStore is passed by reference to behaviors and ProposalEngine

---

## 3. Data Models

### 3.1 Pattern Events

```python
# runtime/event_store.py

@dataclass(frozen=True)
class PresenceEvent:
    ts: str                           # ISO-8601 UTC
    event_type: Literal["presence"]   # discriminator
    transition: Literal["arrive", "depart"]
    weekday: int                      # 0=Monday … 6=Sunday
    minute_of_day: int                # 0–1439 (local time)

@dataclass(frozen=True)
class HeatingEvent:
    ts: str
    event_type: Literal["heating"]
    house_state: str
    temperature_set: float
    source: Literal["user", "heima"]

@dataclass(frozen=True)
class HouseStateEvent:
    ts: str
    event_type: Literal["house_state"]
    from_state: str
    to_state: str

PatternEvent = PresenceEvent | HeatingEvent | HouseStateEvent
```

### 3.2 ReactionProposal

```python
# runtime/analyzers/base.py

@dataclass
class ReactionProposal:
    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    analyzer_id: str = ""
    reaction_type: str = ""          # e.g. "presence_preheat", "heating_eco"
    description: str = ""
    confidence: float = 0.0          # 0.0–1.0
    status: Literal["pending", "accepted", "rejected"] = "pending"
    # Partial config OK — user fills targets in Options Flow
    suggested_reaction_config: dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


class IPatternAnalyzer(Protocol):
    @property
    def analyzer_id(self) -> str: ...
    async def analyze(self, event_store: "EventStore") -> list[ReactionProposal]: ...
```

### 3.3 Statistical Algorithm Model

The v1 built-in analyzers use **pure descriptive statistics only** — no external libraries, no training phase, no model files.

#### PresencePatternAnalyzer — algorithm

```
Input: list[PresenceEvent] for one weekday, transition="arrive"
       n = len(arrivals)  (minute_of_day values)

Require: n ≥ MIN_ARRIVALS (default 5)

median = arrivals_sorted[n // 2]          # 50th percentile, O(n log n) sort
p25    = arrivals_sorted[n // 4]          # 25th percentile
p75    = arrivals_sorted[3 * n // 4]      # 75th percentile
IQR    = p75 - p25                        # interquartile range (minutes)

# Confidence: 1.0 when IQR=0 (perfectly punctual), 0.3 floor when IQR≥120 min
confidence = max(0.3, 1.0 - IQR / 120.0)

Output: ReactionProposal(
    reaction_type="presence_preheat",
    confidence=confidence,
    suggested_reaction_config={
        "median_arrival_min": median,
        "window_half_min": 15,    # fire within ±15 min of median
        ...
    }
)
```

**Rationale:** IQR (not std-dev) is used because arrival times are often bimodal (e.g., normal days vs. late days); IQR is robust to outliers and does not require the distribution to be Gaussian.

#### HeatingPatternAnalyzer — algorithm

**Pattern B (temperature preference):**

```
Input: list[HeatingEvent] for one house_state
       n = len(temps)

Require: n ≥ 10

median = temps_sorted[n // 2]
spread = max(temps) - min(temps)        # full range, not IQR

# Confidence: 1.0 when all setpoints identical, 0.3 floor when spread≥5°C
confidence = max(0.3, 1.0 - spread / 5.0)

Output: ReactionProposal(reaction_type="heating_preference", confidence=confidence)
```

**Pattern A (eco opportunity):** event-count heuristic, no statistical fit. If `away_duration > 2h` and subsequent user setpoint raise > 1°C is observed in ≥3 distinct sessions → emit proposal with fixed `confidence=0.7`.

#### Confidence interpretation

| confidence | Meaning |
|---|---|
| ≥ 0.8 | High regularity — proposal is ready to accept |
| 0.5–0.8 | Moderate regularity — worth reviewing |
| < 0.5 (floor 0.3) | Low regularity — informational only |

`ProposalEngine` may filter out proposals below a configurable `min_confidence` threshold (default 0.4).

---

## 4. Phase P1 — EventStore

**File:** `runtime/event_store.py`

### 4.1 API

```python
class EventStore:
    STORAGE_KEY = "heima_pattern_events"
    STORAGE_VERSION = 1
    MAX_RECORDS = 5000
    TTL_DAYS = 60

    async def async_load(self) -> None:
        """Load persisted events. Call once at coordinator startup."""

    async def async_append(self, event: PatternEvent) -> None:
        """Append one event. Evicts oldest if at capacity, evicts TTL-expired records."""

    async def async_query(
        self,
        *,
        event_type: str | None = None,
        since: str | None = None,    # ISO-8601 UTC lower bound
        limit: int | None = None,
    ) -> list[PatternEvent]: ...

    async def async_clear(self) -> None: ...
    async def async_flush(self) -> None:
        """Force save. Called on coordinator shutdown."""
```

### 4.2 Storage format

HA `Store` writes JSON to `.storage/heima_pattern_events`:

```json
{
  "version": 1,
  "key": "heima_pattern_events",
  "data": {
    "events": [
      {
        "ts": "2026-03-01T07:32:00+00:00",
        "event_type": "presence",
        "transition": "arrive",
        "weekday": 5,
        "minute_of_day": 452
      }
    ]
  }
}
```

### 4.3 Implementation notes

- Use `homeassistant.helpers.storage.Store(hass, version=1, key=STORAGE_KEY)`
- In-memory `deque(maxlen=MAX_RECORDS)` + `store.async_delay_save(fn, delay=30)` for batched writes
- TTL eviction on `async_load()` and `async_append()`
- Deserialization: switch on `event_type` field to reconstruct typed dataclass

---

## 5. Phase P1b — EventRecorderBehavior

**File:** `runtime/behaviors/event_recorder.py`

`HeimaBehavior` subclass. Observes `DecisionSnapshot` transitions via `on_snapshot()` and writes events to `EventStore`. Detects:
- `anyone_home False → True` → `PresenceEvent(transition="arrive")`
- `anyone_home True → False` → `PresenceEvent(transition="depart")`
- `house_state` change → `HouseStateEvent`

`HeatingEvent` is handled by a separate `HeatingRecorderBehavior` (P3 prerequisite) that observes `CanonicalState` heating setpoint changes between cycles.

**Hook pattern:**
```python
def on_snapshot(self, snapshot: DecisionSnapshot) -> None:
    # detect transitions vs prev snapshot
    # schedule writes as tasks (never await inline)
    self._hass.async_create_task(self._store.async_append(event))
```

---

## 6. Phase P2 — PresencePatternAnalyzer

**File:** `runtime/analyzers/presence.py`

### 6.1 Algorithm

```
For each weekday 0..6:
  arrivals = [e.minute_of_day for e in presence_events
              if e.transition=="arrive" and e.weekday==weekday]
  if len(arrivals) < MIN_ARRIVALS (5): skip
  median = sorted(arrivals)[len(arrivals) // 2]
  p25 = sorted(arrivals)[len(arrivals) // 4]
  p75 = sorted(arrivals)[3 * len(arrivals) // 4]
  spread = p75 - p25
  confidence = max(0.3, 1.0 - spread / 120.0)   # tighter = higher
  → emit ReactionProposal(reaction_type="presence_preheat")
```

### 6.2 Output proposal

```python
ReactionProposal(
    analyzer_id="PresencePatternAnalyzer",
    reaction_type="presence_preheat",
    description=f"{WEEKDAY_NAMES[wd]}: typical arrival at {hhmm(median)}. "
                f"Suggest pre-conditioning {PRE_CONDITION_MIN} min before.",
    confidence=confidence,
    suggested_reaction_config={
        "reaction_class": "PresencePatternReaction",
        "weekday": wd,
        "median_arrival_min": median,
        "window_half_min": 15,
        "pre_condition_min": 20,
        "steps": [],  # user fills heating/lighting targets in Options Flow
    },
)
```

---

## 7. Phase P3 — HeatingPatternAnalyzer

**File:** `runtime/analyzers/heating.py`

Detects two patterns from `HeatingEvent` + `HouseStateEvent`:

**Pattern A — eco opportunity:**
`away` period > 2h followed by `home` where temperature was raised with `source="user"` → suggest explicit eco heating branch.

**Pattern B — consistent temperature preference:**
```
For each house_state:
  temps = [e.temperature_set for e in heating_events if e.house_state == hs]
  if len(temps) < 10: skip
  median = sorted(temps)[len(temps)//2]
  spread = max(temps) - min(temps)
  confidence = max(0.3, 1.0 - spread / 5.0)
  → emit ReactionProposal(reaction_type="heating_preference")
```

**HeatingRecorderBehavior** (prerequisite): a `HeimaBehavior` that compares the heating setpoint in `CanonicalState` between consecutive snapshots. Source detection: if `heating_trace["apply_allowed"]` was `True` → `source="heima"`, otherwise `source="user"`.

---

## 8. Phase P4 — ProposalEngine

**File:** `runtime/proposal_engine.py`

### 8.1 Storage

Separate HA `Store` with key `"heima_proposals"`. Stores `ReactionProposal` objects serialized to JSON.

### 8.2 API

```python
class ProposalEngine:
    async def async_initialize(self) -> None: ...
    async def async_run(self) -> None:
        """Run all analyzers, merge/dedup, persist, update sensor."""
    async def async_accept_proposal(self, proposal_id: str) -> bool: ...
    async def async_reject_proposal(self, proposal_id: str) -> bool: ...
    def pending_proposals(self) -> list[ReactionProposal]: ...
    async def async_shutdown(self) -> None: ...
```

### 8.3 Deduplication

When a new proposal from an analyzer matches an existing one (same `analyzer_id` + `reaction_type` + key params):
- Status `"accepted"` or `"rejected"` → skip (do not re-surface)
- Status `"pending"` → update `confidence` + `updated_at` in-place

Key params fingerprint: `reaction_type + str(weekday or house_state)`.

### 8.4 Sensor

After each `async_run()`, write to engine state:
```python
engine.state.set_sensor("heima_reaction_proposals", json.dumps({
    p.proposal_id: {
        "type": p.reaction_type,
        "description": p.description,
        "confidence": p.confidence,
        "status": p.status,
    }
    for p in self._proposals
}))
```

**Sensor format:** value = count of pending proposals (int, allows HA automations to trigger), attributes = full proposals dict.

### 8.5 Periodic scheduling

`async_call_later` with recursive reschedule every 6h, managed by the coordinator. Cancelled on shutdown.

---

## 9. Phase P5 — User Approval Flow

### 9.1 Options Flow step `"proposals"`

New step after the existing steps. Shown only if `pending_proposals()` is non-empty (skip silently otherwise).

UI: for each pending proposal, show description + confidence + boolean selector (Accept / Reject).

On submit:
- Accept → `coordinator.proposal_engine.async_accept_proposal(pid)`
- Reject → `coordinator.proposal_engine.async_reject_proposal(pid)`

### 9.2 Acceptance → Configured Reaction

```python
reactions = dict(entry.options.get("reactions", {}))
configured = dict(reactions.get("configured", {}))
configured[proposal.proposal_id] = proposal.suggested_reaction_config
reactions["configured"] = configured
# config_entries.async_update_entry(entry, options=...)
# → triggers async_reload_options() → engine registers the reaction
```

### 9.3 Reaction instantiation from config

In `engine._rebuild_configured_reactions()` (called from `async_reload_options()`):

```python
for reaction_id, cfg in options.get("reactions", {}).get("configured", {}).items():
    match cfg.get("reaction_class"):
        case "PresencePatternReaction":
            reaction = PresencePatternReaction(
                reaction_id=reaction_id,
                steps=cfg.get("steps", []),
                ...
            )
        case "ConsecutiveStateReaction":
            ...
    self.register_reaction(reaction)
```

### 9.4 Reactions management

Configured reactions from proposals appear in the existing "Reactions" step (Options Flow) for mute/delete management.

---

## 10. Phase P6 — Generalization (design now, implement later)

### 10.1 Protocols (already satisfied by P2/P3)

```python
class IPatternAnalyzer(Protocol):
    @property
    def analyzer_id(self) -> str: ...
    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]: ...
```

All P2/P3 analyzers implement this structurally — no runtime enforcement needed.

### 10.2 HeimaAnalyzer base class (optional convenience)

```python
class HeimaAnalyzer:
    @property
    def analyzer_id(self) -> str:
        return type(self).__name__

    async def analyze(self, event_store: EventStore) -> list[ReactionProposal]:
        return []

    def diagnostics(self) -> dict[str, Any]:
        return {}
```

### 10.3 Registration

```python
proposal_engine.register_analyzer(analyzer)
```

Default analyzers registered by coordinator. Future domains (Watering, Lighting) add their own without touching the core.

### 10.4 IPatternAnalyzer as a plug-in contract

`IPatternAnalyzer` is intentionally designed as a **replacement boundary**. The v1 built-in analyzers (`PresencePatternAnalyzer`, `HeatingPatternAnalyzer`) use simple descriptive statistics (median, IQR, range) that require no external dependencies and produce deterministic results on small datasets.

This is a deliberate v1 constraint, **not** an architectural one. Any analyzer that satisfies the protocol can be dropped in without changing `ProposalEngine`, `EventStore`, or any other component:

| Analyzer tier | Examples | Drop-in viable? |
|---|---|---|
| v1 — descriptive stats | Median, IQR, range | ✅ (default) |
| v2 — robust statistics | Kernel density, DBSCAN clustering | ✅ |
| v3 — time-series | ARIMA, changepoint detection | ✅ |
| v4 — probabilistic | GMM, Bayesian online learning | ✅ |
| v5 — ML | scikit-learn, tflite, ONNX runtime | ✅ (requires HA add-on or venv with deps) |

**Rules for plug-in analyzers:**
1. Must be async-safe: no blocking I/O inside `analyze()`.
2. Must not modify `EventStore` (read-only access).
3. Must return `list[ReactionProposal]` with `confidence` in [0.0, 1.0].
4. Should emit no more than ~10 proposals per run (ProposalEngine is not a feed).
5. May maintain internal state between calls (cache last run result, etc.).

---

## 11. File Structure

```
custom_components/heima/runtime/
  event_store.py                    NEW
  proposal_engine.py                NEW
  analyzers/
    __init__.py                     NEW
    base.py                         NEW — IPatternAnalyzer + ReactionProposal
    presence.py                     NEW — PresencePatternAnalyzer
    heating.py                      NEW — HeatingPatternAnalyzer
  behaviors/
    event_recorder.py               NEW — presence + house_state events
    heating_recorder.py             NEW — heating setpoint events
```

### Existing files that change

| File | Change |
|---|---|
| `coordinator.py` | Own `EventStore` + `ProposalEngine`; register behaviors; schedule 6h task |
| `runtime/engine.py` | Add `_rebuild_configured_reactions()`; init `heima_reaction_proposals` sensor |
| `entities/registry.py` | Add `heima_reaction_proposals` sensor |
| `config_flow/_steps_reactions.py` | Add "proposals" review sub-step |
| `translations/en.json`, `it.json` | Proposals step labels |

---

## 12. Phase Dependencies

```
P1 (EventStore)
  └─→ P1b (EventRecorderBehavior)
        └─→ P2 (PresencePatternAnalyzer)
              └─→ P4 (ProposalEngine)
                    └─→ P5 (User Approval Flow)

P3 (HeatingPatternAnalyzer) → requires P1 + HeatingRecorderBehavior
  (parallel with P2 after P1)

P6 (Generalization) → interfaces designed from P1, enforcement deferred
```

**Minimum viable slice:** P1 + P1b + P2 + P4 gives end-to-end presence proposals (sensor only, no UI). P5 adds approval UI. P3 is additive.

---

## 13. Tests to Write

### P1 — EventStore

| Test | Assertion |
|---|---|
| `test_event_store_append_and_query` | Append 3 events, query returns all ordered by ts |
| `test_event_store_evicts_at_max` | Append 5001 events → len == 5000, oldest evicted |
| `test_event_store_ttl_eviction` | Event with ts 61 days ago evicted on load |
| `test_event_store_persists_across_load` | Append → flush → new instance → load → events present |
| `test_event_store_query_by_type` | Mix of events; query type="presence" returns only presence |
| `test_event_store_query_since` | Query `since=T` returns only events after T |
| `test_event_store_clear` | After clear, query returns empty |
| `test_event_store_deserialization_roundtrip` | All three event types: `as_dict()` → `from_dict()` → equal |

### P1b — EventRecorderBehavior

| Test | Assertion |
|---|---|
| `test_recorder_presence_arrive` | `anyone_home` False→True → `PresenceEvent(transition="arrive")` |
| `test_recorder_presence_depart` | True→False → `transition="depart"` |
| `test_recorder_no_event_on_stable` | Same `anyone_home` → no event |
| `test_recorder_house_state_transition` | State change → `HouseStateEvent` |
| `test_recorder_weekday_minute_of_day` | Arrive 07:32 Mon local → weekday=0, minute=452 |

### P2 — PresencePatternAnalyzer

| Test | Assertion |
|---|---|
| `test_presence_analyzer_requires_min_arrivals` | 4 arrivals → no proposal |
| `test_presence_analyzer_emits_proposal` | 5 arrivals for Mon → proposal `reaction_type="presence_preheat"` |
| `test_presence_analyzer_confidence_tight` | Arrivals within 5 min → confidence > 0.8 |
| `test_presence_analyzer_confidence_spread` | Arrivals spread 2h → confidence < 0.5 |
| `test_presence_analyzer_per_weekday` | 5 Mon, 2 Tue → only Mon proposal |
| `test_presence_analyzer_empty_store` | No events → [] |

### P3 — HeatingPatternAnalyzer

| Test | Assertion |
|---|---|
| `test_heating_analyzer_requires_min_events` | 9 events → no proposal |
| `test_heating_analyzer_consistent_preference` | 10 events ~21°C for "home" → proposal |
| `test_heating_analyzer_high_spread_no_proposal` | 10 events 18–24°C → no proposal |
| `test_heating_analyzer_eco_pattern` | away >2h + user raises temp → eco proposal |

### P4 — ProposalEngine

| Test | Assertion |
|---|---|
| `test_proposal_engine_dedup_pending` | Two runs, same output → single proposal, confidence updated |
| `test_proposal_engine_skip_accepted` | Accepted proposal → no duplicate on re-run |
| `test_proposal_engine_skip_rejected` | Rejected → not re-surfaced |
| `test_proposal_engine_persist_and_load` | Flush → new instance → load → proposals recovered |
| `test_proposal_engine_sensor_updated` | After run, `heima_reaction_proposals` sensor has JSON |
| `test_proposal_engine_accept` | `async_accept_proposal(pid)` → status="accepted" |
| `test_proposal_engine_reject` | `async_reject_proposal(pid)` → status="rejected" |

### P5 — Approval Flow

| Test | Assertion |
|---|---|
| `test_options_flow_proposals_step_shown` | Pending proposals → step appears |
| `test_options_flow_no_step_when_empty` | No pending → step skipped |
| `test_options_flow_accept_writes_to_options` | Accept → `options["reactions"]["configured"][pid]` populated |
| `test_configured_reaction_registered_on_reload` | Accept + reload → engine has reaction registered |

---

## 14. Design Constraints

- **No ML libraries in v1.** Built-in analyzers use pure Python: `sorted()`, median/percentile via index arithmetic. Advanced analyzers can be added via the `IPatternAnalyzer` plug-in contract without touching core components (see §10.4).
- **No blocking the eval cycle.** `async_append()` is always scheduled as a task from `on_snapshot()`.
- **PresencePatternReaction stays.** Real-time in-memory firing continues. Analyzers are the offline "proposal" path — complementary, not a replacement.
- **Partial proposals are valid.** `steps: []` is acceptable; user fills targets in Options Flow.
- **Proposal acceptance persists.** Stored in `options["reactions"]["configured"]` (HA config entry options, durable).
- **EventStore writes are batched.** `async_delay_save(fn, 30)` avoids I/O on every event.

---

## 15. Open Questions

1. **HeatingRecorderBehavior access to `heating_trace`**: preferred option is `engine.heating_trace` property for testability.
2. **`heima_reaction_proposals` sensor format**: value = count of pending proposals (int, allows HA automations on count changes), attributes = full proposals dict.
3. **6h periodic scheduling**: `async_call_later` with recursive reschedule is consistent with existing scheduler pattern in `coordinator.py`.
4. **HeatingEvent source detection**: `source="heima"` when `heating_trace["apply_allowed"]` was True in same cycle; `source="user"` for all other observed setpoint changes.
