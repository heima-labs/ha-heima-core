# Heima Inference Engine — Specification v2

**Status:** Draft/RFC — v2 target contract
**Date:** 2026-03-11
**Last Verified Against Code:** 2026-03-11
**Scope:** v2 — predict when/how known behaviors will occur, from all domain inputs/outputs

> v3 (discover unnamed patterns, propose new states) is architecturally enabled by this spec
> but not implemented. The extension points are called out explicitly.

---

## Normative precedence

This document defines the intended v2 inference architecture and contracts.

Interpretation rule:
- if implementation and spec diverge, the divergence must be resolved explicitly
- code is a reference implementation, not the source of truth

## Scope and non-goals

In scope:
- predictive inference over known behaviors
- persistent snapshot substrate for offline learning
- inference signal contracts and routing semantics
- domain consumption of optional inference hints

Not a goal of this document:
- replacing the v1 learning proposal system described in `learning_system_spec.md`
- describing every future v3 discovery capability in detail
- prescribing one exact internal package/module layout

## 1. Motivation

As of v0.4.0, Heima's DAG is purely reactive: it computes the current house state from current
inputs, with no memory beyond one cycle (CanonicalState) and no prediction capability.

The Inference Engine adds a parallel learning pipeline that:

1. Records domain outputs as a durable stream of `HouseSnapshot` records
2. Runs offline `ILearningModule` analyzers that build lightweight statistical models
3. Each cycle, modules emit typed `InferenceSignal` objects routed to the relevant domain
4. Each domain applies a domain-specific policy to consume signals when its own hard inputs
   are ambiguous or absent

Nothing in the existing eval cycle changes contract: signals are additive inputs, never
substitutes for real sensor data.

Normative rule:
- inference may refine or bias domain decisions when inputs are ambiguous
- inference must never fabricate hard sensor truth or override explicit observed facts

---

## 2. Architecture

```
                        ┌─────────────────────────────────────┐
                        │   engine.async_evaluate() — hot path │
                        │                                      │
  HA entity state ──→   │  1. collect_signals()               │
                        │     ILearningModule.infer(ctx)  ×N  │
                        │     → list[InferenceSignal]          │
                        │                                      │
                        │  2. SignalRouter                     │
                        │     → per-domain signal lists        │
                        │                                      │
                        │  3. DAG evaluation (unchanged order) │
                        │     each Domain.evaluate(           │
                        │       obs, signals=[...])            │
                        │                                      │
                        │  4. apply + CanonicalState update    │
                        │                                      │
  SnapshotStore ←───────│  5. record_snapshot() on-change     │
                        └─────────────────────────────────────┘
                                        │ on-change
                                        ▼
                              SnapshotStore (durable)
                              max 10 000 records, TTL 90d
                                        │ read
                              ┌─────────┴──────────┐
                              │  Offline task (6h)  │
                              │  ILearningModule    │
                              │  .analyze(store) ×N │
                              │  → updates module's │
                              │    internal model   │
                              └─────────────────────┘
```

**Key invariants:**
- `infer()` is synchronous and O(1): reads pre-computed model, no I/O
- `analyze()` runs off-cycle via `async_add_executor_job` or plain async task
- `SnapshotStore` writes from the hot path are fire-and-forget tasks
- Domains are never modified to depend on inference: signals are optional hints

---

## 3. Data Models

### 3.1 HouseSnapshot

The unit of observation. Derived from `DecisionSnapshot` (domain outputs only — not raw HA
entity values, which are noisy and voluminous).

```python
# runtime/inference/snapshot_store.py

@dataclass(frozen=True)
class HouseSnapshot:
    ts: str                              # ISO-8601 UTC
    weekday: int                         # 0=Monday … 6=Sunday
    minute_of_day: int                   # 0–1439 local time

    # PeopleDomain output
    anyone_home: bool
    named_present: tuple[str, ...]       # sorted person slugs

    # OccupancyDomain output
    room_occupancy: dict[str, bool]      # room_id → occupied

    # HouseStateDomain output
    house_state: str

    # HeatingDomain output
    heating_setpoint: float | None       # None if heating not configured

    # LightingDomain output
    lighting_scenes: dict[str, str]      # room_id → scene name applied

    # SecurityDomain output
    security_armed: bool
```

Recorded **on-change**: a snapshot is written only when at least one field differs from the
previous snapshot. In a typical household this produces 50–150 records/day.

### 3.2 InferenceContext

Read-only view of the current cycle state, passed to `ILearningModule.infer()`:

```python
@dataclass(frozen=True)
class InferenceContext:
    now_local: datetime
    weekday: int
    minute_of_day: int
    anyone_home: bool
    named_present: tuple[str, ...]
    room_occupancy: dict[str, bool]
    previous_house_state: str
    previous_heating_setpoint: float | None
    previous_lighting_scenes: dict[str, str]
```

Constructed by the engine at the start of each cycle from `CanonicalState` and the current
normalized observation. Modules receive it as an immutable snapshot — they cannot modify it.

### 3.3 InferenceSignal hierarchy

Base class plus one subclass per domain that can consume signals. New domains can add their
own subclass without touching the base.

```python
# runtime/inference/signals.py

from enum import IntEnum

class Importance(IntEnum):
    OBSERVE = 0   # logged only, never used in resolution
    SUGGEST = 1   # used only when no hard signal is active
    ASSERT  = 2   # treated as soft override; domain still decides

@dataclass(frozen=True)
class InferenceSignal:
    source_id: str          # module_id that emitted this
    confidence: float       # 0.0–1.0
    importance: Importance
    ttl_s: int              # seconds before signal expires
    label: str              # human-readable reason (diagnostics)

@dataclass(frozen=True)
class HouseStateSignal(InferenceSignal):
    predicted_state: str

@dataclass(frozen=True)
class OccupancySignal(InferenceSignal):
    room_id: str
    predicted_occupied: bool

@dataclass(frozen=True)
class HeatingSignal(InferenceSignal):
    predicted_setpoint: float
    house_state_context: str    # the house_state this prediction applies to

@dataclass(frozen=True)
class LightingSignal(InferenceSignal):
    room_id: str
    predicted_scene: str
```

A module may emit signals for multiple domains in a single `infer()` call.

---

## 4. ILearningModule Protocol

```python
# runtime/inference/base.py

class ILearningModule(Protocol):
    @property
    def module_id(self) -> str: ...

    async def analyze(self, store: "SnapshotStore") -> None:
        """
        Offline phase. Read snapshot history, update internal model.
        Called every 6h by the coordinator (off hot path).
        May use async I/O freely. Must not emit signals here.
        """

    def infer(self, context: InferenceContext) -> list[InferenceSignal]:
        """
        Online phase. Read internal model + context, emit signals.
        Synchronous. Must be O(1) — no I/O, no heavy compute.
        Called once per eval cycle, before domain evaluation.
        """

    def diagnostics(self) -> dict[str, Any]:
        """Return current model summary for the diagnostics payload."""
```

### Optional convenience base class

```python
class HeimaLearningModule:
    @property
    def module_id(self) -> str:
        return type(self).__name__

    async def analyze(self, store: SnapshotStore) -> None:
        pass

    def infer(self, context: InferenceContext) -> list[InferenceSignal]:
        return []

    def diagnostics(self) -> dict[str, Any]:
        return {}
```

---

## 5. SnapshotStore

```python
# runtime/inference/snapshot_store.py

class SnapshotStore:
    STORAGE_KEY    = "heima_snapshots"
    STORAGE_VERSION = 1
    MAX_RECORDS    = 10_000
    TTL_DAYS       = 90

    async def async_load(self) -> None:
        """Load persisted snapshots. Call once at coordinator startup."""

    async def async_append(self, snapshot: HouseSnapshot) -> None:
        """
        Append snapshot if it differs from the last recorded one.
        Evicts oldest if at MAX_RECORDS. Evicts TTL-expired on load and append.
        Uses async_delay_save(fn, delay=30) for batched writes.
        """

    async def async_query(
        self,
        *,
        since: str | None = None,          # ISO-8601 UTC lower bound
        until: str | None = None,
        weekdays: set[int] | None = None,
        house_state: str | None = None,
        limit: int | None = None,
    ) -> list[HouseSnapshot]: ...

    async def async_flush(self) -> None:
        """Force save. Called on coordinator shutdown."""

    async def async_clear(self) -> None: ...

    @property
    def record_count(self) -> int: ...
```

Storage format: HA `Store` → `.storage/heima_snapshots` (same pattern as `EventStore`).

---

## 6. Built-in Learning Modules (v2)

### 6.1 WeekdayStateModule

**What it learns:** `P(house_state | weekday, hour_bucket)`

Hour bucket = `minute_of_day // 60` (24 buckets/day).

**Model (internal):**
```python
# counts[(weekday, hour_bucket, house_state)] = int
# total[(weekday, hour_bucket)] = int
# → probability = counts[...] / total[...]
```

**analyze():**
```
For each snapshot in store:
  key = (snapshot.weekday, snapshot.minute_of_day // 60, snapshot.house_state)
  counts[key] += 1
  total[(weekday, hour_bucket)] += 1
```
Full recompute from store each run (store is small, O(n) is fine).

**infer():**
```
key = (context.weekday, context.minute_of_day // 60, state)
for each known house_state:
  p = counts[key] / total[(weekday, hour_bucket)]   # 0 if unseen
  if p >= MIN_CONFIDENCE (0.5) and support >= MIN_SUPPORT (10):
    emit HouseStateSignal(
      predicted_state=state,
      confidence=p,
      importance=SUGGEST if p < 0.8 else ASSERT,
      ttl_s=3600,   # valid for 1h (coarse signal)
    )
```

Emits at most one signal (the highest-probability state for the current slot).

---

### 6.2 RoomStateCorrelationModule

**What it learns:** `P(house_state | room_occupancy_pattern)`

Room occupancy pattern = frozenset of occupied room_ids (ignores which rooms are empty).

**Model:**
```python
# counts[(room_pattern, house_state)] = int
# total[room_pattern] = int
```

**analyze():** same frequency-table approach, keyed by `frozenset(occupied rooms)`.

**infer():**
```
current_pattern = frozenset(r for r, occ in context.room_occupancy.items() if occ)
for each house_state:
  p = counts[(current_pattern, state)] / total[current_pattern]
  if p >= 0.6 and support >= 15:
    emit HouseStateSignal(predicted_state=state, confidence=p, importance=SUGGEST, ttl_s=900)
```

This module does NOT emit `OccupancySignal` — it only infers house_state from occupancy,
not occupancy from time. Occupancy inference would require a different input (e.g., time-of-day
→ expected occupancy) and is deferred to v3.

---

### 6.3 HeatingPreferenceModule

**What it learns:** `preferred_setpoint[house_state]` from historically observed setpoints.

**Model:**
```python
# setpoints[house_state] = list[float]
# preferred[house_state] = (median, confidence)
```

**analyze():**
```
For each snapshot where heating_setpoint is not None:
  setpoints[snapshot.house_state].append(snapshot.heating_setpoint)

For each house_state with len(setpoints) >= 10:
  s = sorted(setpoints[hs])
  median = s[len(s) // 2]
  spread = max(s) - min(s)
  confidence = max(0.3, 1.0 - spread / 5.0)
  preferred[hs] = (median, confidence)
```

**infer():**
```
hs = context.previous_house_state
if hs in preferred and preferred[hs].confidence >= 0.5:
  emit HeatingSignal(
    predicted_setpoint=preferred[hs].median,
    house_state_context=hs,
    confidence=preferred[hs].confidence,
    importance=SUGGEST,
    ttl_s=1800,
  )
```

HeatingDomain uses this only if `apply_mode` is not forcing an explicit setpoint and no
manual override is active (domain-specific policy, §7.3).

---

### 6.4 LightingPatternModule

**What it learns:** `P(scene | room_id, house_state, hour_bucket)`

**Model:**
```python
# counts[(room_id, house_state, hour_bucket, scene)] = int
# total[(room_id, house_state, hour_bucket)] = int
```

**infer():**
```
For each room_id:
  key = (room_id, context.previous_house_state, context.minute_of_day // 60)
  best_scene, p = argmax over known scenes
  if p >= 0.65 and support >= 8:
    emit LightingSignal(room_id=room_id, predicted_scene=best_scene,
                        confidence=p, importance=SUGGEST, ttl_s=1800)
```

---

## 7. Domain Integration

Each domain receives its signal list as an optional parameter to `evaluate()`. The signal
list is pre-filtered by type and sorted by confidence descending.

Signal consumption is **domain-specific** (policy option C): each domain decides independently
when and how to use inference signals. Hard inputs always take precedence.

### 7.1 HouseStateDomain

```python
def evaluate(self, obs, signals: list[HouseStateSignal] = []):
    # 1. Resolve as today: presence, override, vacation, sleep → hard result
    hard_result = self._resolve_hard(obs)

    if hard_result.is_definitive:
        return hard_result   # signals ignored

    # 2. No definitive hard result → consult signals
    best = max(signals, key=lambda s: s.confidence, default=None)
    if best and best.importance >= Importance.SUGGEST and best.confidence >= 0.6:
        return HouseStateResult(
            house_state=best.predicted_state,
            source="inference",
            confidence=best.confidence,
        )

    return hard_result   # fallback to whatever hard resolved (may be "unknown")
```

`is_definitive` is True when: explicit override is active, vacation is on, presence is
unambiguous, or sleep window is active.

### 7.2 OccupancyDomain

OccupancySignal is not emitted by any v2 module (deferred to v3). Domain interface accepts
`signals: list[OccupancySignal] = []` for forward compatibility; it is unused in v2.

### 7.3 HeatingDomain

```python
def evaluate(self, obs, signals: list[HeatingSignal] = []):
    result = self._resolve_branch(obs)   # existing logic

    if result.apply_allowed and result.target_temperature is None:
        # no explicit setpoint from branch config → consult inference
        relevant = [s for s in signals if s.house_state_context == obs.house_state]
        if relevant:
            best = max(relevant, key=lambda s: s.confidence)
            if best.confidence >= 0.55:
                result = result.with_setpoint(best.predicted_setpoint, source="inference")

    return result
```

If `manual_override_guard` is active, signals are ignored entirely (existing guard path).

### 7.4 LightingDomain

```python
def evaluate(self, obs, signals: list[LightingSignal] = []):
    room_results = self._resolve_rooms(obs)   # existing scene resolution

    for room_id, result in room_results.items():
        if result.scene is None and result.manual_hold is False:
            room_signals = [s for s in signals if s.room_id == room_id]
            if room_signals:
                best = max(room_signals, key=lambda s: s.confidence)
                if best.confidence >= 0.65:
                    result.scene = best.predicted_scene
                    result.source = "inference"

    return room_results
```

LightingSignal is only applied when: no explicit scene is configured for the current
house_state, and manual hold is not active.

---

## 8. SignalRouter

```python
# runtime/inference/router.py

class SignalRouter:
    def route(self, signals: list[InferenceSignal]) -> dict[type, list[InferenceSignal]]:
        """Group signals by subclass type. Expired signals are filtered out."""
        now = time.monotonic()
        result: dict[type, list] = defaultdict(list)
        for sig in signals:
            if not self._is_expired(sig):
                result[type(sig)].append(sig)
        # sort each bucket by confidence desc
        for bucket in result.values():
            bucket.sort(key=lambda s: s.confidence, reverse=True)
        return result
```

TTL is enforced by comparing `signal.ttl_s` against elapsed time since the signal was
created. Signals created in the same cycle are always fresh. Signals from a previous cycle
that were cached (see §9 on caching) are checked on each use.

---

## 9. Engine Integration

### 9.1 collect_signals()

```python
# called once per eval cycle, before domain evaluation

def _collect_signals(self) -> dict[type, list[InferenceSignal]]:
    ctx = self._build_inference_context()
    raw: list[InferenceSignal] = []
    for module in self._learning_modules:
        try:
            raw.extend(module.infer(ctx))
        except Exception:
            _LOGGER.exception("Module %s infer() failed", module.module_id)
    return self._signal_router.route(raw)
```

Exceptions in any module do not affect the eval cycle.

### 9.2 record_snapshot()

```python
# called at end of each eval cycle

def _record_snapshot_if_changed(self, snapshot: DecisionSnapshot) -> None:
    hs = HouseSnapshot.from_decision_snapshot(snapshot)
    if hs != self._last_recorded_snapshot:
        self._last_recorded_snapshot = hs
        self._hass.async_create_task(self._snapshot_store.async_append(hs))
```

### 9.3 Module registration

```python
# in coordinator.py, after engine init:

engine.register_learning_module(WeekdayStateModule())
engine.register_learning_module(RoomStateCorrelationModule())
engine.register_learning_module(HeatingPreferenceModule())
engine.register_learning_module(LightingPatternModule())
```

Future domains register their own modules without modifying existing code.

### 9.4 Offline scheduling

Same pattern as ProposalEngine (learning_system_spec_v1 §8.5):
- `async_call_later` with recursive reschedule every 6h
- Startup run after 60s delay (allow coordinator to fully initialize)
- Cancelled on shutdown

```python
async def _run_analyze_pass(self) -> None:
    for module in self._learning_modules:
        try:
            await self._hass.async_add_executor_job(
                lambda m=module: asyncio.run_coroutine_threadsafe(
                    m.analyze(self._snapshot_store), self._hass.loop
                ).result()
            )
        except Exception:
            _LOGGER.exception("Module %s analyze() failed", module.module_id)
    self._schedule_next_analyze()
```

Actually: since `analyze()` is declared `async`, run it directly as a task — no executor needed
unless the implementation does blocking I/O. Default implementations are pure Python.

---

## 10. Diagnostics

Added to `engine.diagnostics()` under key `"inference"`:

```python
{
  "inference": {
    "snapshot_store": {
      "record_count": 1247,
      "oldest_ts": "2026-01-10T08:00:00+00:00",
      "newest_ts": "2026-03-11T22:15:00+00:00"
    },
    "modules": {
      "WeekdayStateModule": {
        "model_slots": 168,        # weekday × hour_bucket combinations with data
        "last_analyzed": "2026-03-11T18:00:00+00:00"
      },
      "RoomStateCorrelationModule": {
        "known_patterns": 12,
        "last_analyzed": "2026-03-11T18:00:00+00:00"
      },
      "HeatingPreferenceModule": {
        "preferred": {
          "home": {"setpoint": 21.5, "confidence": 0.82},
          "sleep": {"setpoint": 18.0, "confidence": 0.91}
        }
      },
      "LightingPatternModule": {
        "known_slots": 34
      }
    },
    "last_cycle_signals": {
      "HouseStateSignal": 1,
      "HeatingSignal": 1,
      "LightingSignal": 3
    }
  }
}
```

---

## 11. File Structure

```
custom_components/heima/runtime/inference/
  __init__.py              # exports public API
  base.py                  # ILearningModule, HeimaLearningModule, InferenceContext
  signals.py               # Importance, InferenceSignal, HouseStateSignal, ...
  snapshot_store.py        # HouseSnapshot, SnapshotStore
  router.py                # SignalRouter
  modules/
    __init__.py
    weekday_state.py        # WeekdayStateModule
    room_state.py           # RoomStateCorrelationModule
    heating_preference.py   # HeatingPreferenceModule
    lighting_pattern.py     # LightingPatternModule
```

### Existing files that change

| File | Change |
|---|---|
| `runtime/engine.py` | `register_learning_module()`, `_collect_signals()`, `_record_snapshot_if_changed()`, `diagnostics()["inference"]` |
| `runtime/domains/house_state.py` | `evaluate(obs, signals=[])` — optional signals param |
| `runtime/domains/heating.py` | `evaluate(obs, signals=[])` |
| `runtime/domains/lighting.py` | `evaluate(obs, signals=[])` |
| `runtime/domains/occupancy.py` | `evaluate(obs, signals=[])` — stub, unused in v2 |
| `coordinator.py` | Module registration, offline scheduling |

---

## 12. v3 Extension Points

The following are explicitly designed as extension seams, not implemented in v2:

| Seam | v3 Use |
|---|---|
| `OccupancySignal` accepted by OccupancyDomain | Time→occupancy prediction per room |
| `target_state=None` in a future `DiscoverySignal` subclass | Unknown pattern accumulation → ProposalEngine |
| `ILearningModule.analyze()` reads full snapshot (all fields) | Multi-domain correlation (e.g. occupancy × heating × lighting) |
| `Importance.ASSERT` path in HouseStateDomain | High-confidence prediction can become primary state source |
| `register_learning_module()` in coordinator | External integrations can inject custom modules |

---

## 13. Tests to Write

### SnapshotStore

| Test | Assertion |
|---|---|
| `test_snapshot_store_on_change_only` | Identical snapshot not appended twice |
| `test_snapshot_store_evicts_at_max` | 10001 snapshots → len == 10000 |
| `test_snapshot_store_ttl_eviction` | Snapshot 91d old evicted on load |
| `test_snapshot_store_query_weekday` | Filter by weekday returns only matching |
| `test_snapshot_store_query_house_state` | Filter by house_state |
| `test_snapshot_store_roundtrip` | Flush → new instance → load → equal |

### WeekdayStateModule

| Test | Assertion |
|---|---|
| `test_weekday_module_no_signal_below_support` | 9 snapshots → no signal |
| `test_weekday_module_emits_suggest` | 10 Mon 9am "working" → HouseStateSignal |
| `test_weekday_module_confidence` | 10/10 same state → confidence=1.0 |
| `test_weekday_module_mixed` | 7 "home" + 3 "working" → "home" signal, confidence=0.7 |
| `test_weekday_module_no_cross_day` | Mon data does not affect Tue inference |

### RoomStateCorrelationModule

| Test | Assertion |
|---|---|
| `test_room_correlation_min_support` | 14 snapshots → no signal |
| `test_room_correlation_emits` | 15 snapshots {studio} → "working" → signal |
| `test_room_correlation_pattern_key` | {studio, kitchen} ≠ {studio} patterns |

### HeatingPreferenceModule

| Test | Assertion |
|---|---|
| `test_heating_pref_min_count` | 9 snapshots → no signal |
| `test_heating_pref_consistent` | 10× 21.5°C → signal confidence >0.9 |
| `test_heating_pref_spread` | 18–24°C spread → confidence <0.5 |
| `test_heating_pref_house_state_scoped` | "home" pref not applied when state="sleep" |

### LightingPatternModule

| Test | Assertion |
|---|---|
| `test_lighting_module_emits_per_room` | 8× living=scene_evening → LightingSignal |
| `test_lighting_module_min_support` | 7 snapshots → no signal |
| `test_lighting_module_house_state_scoped` | "home" scenes not applied when state="sleep" |

### Domain integration

| Test | Assertion |
|---|---|
| `test_house_state_uses_signal_when_ambiguous` | No hard signal + SUGGEST 0.7 → predicted state used |
| `test_house_state_ignores_signal_when_definitive` | Override active → signal ignored |
| `test_heating_uses_signal_when_no_branch_setpoint` | No branch setpoint + HeatingSignal → applied |
| `test_heating_ignores_signal_with_manual_override` | manual_override_guard=True → signal ignored |
| `test_lighting_uses_signal_when_no_scene` | No scene configured + LightingSignal → applied |
| `test_lighting_ignores_signal_with_manual_hold` | manual_hold=True → signal ignored |

### Engine

| Test | Assertion |
|---|---|
| `test_engine_collects_signals_from_all_modules` | 2 modules registered → signals merged |
| `test_engine_module_exception_doesnt_break_cycle` | Module raises → eval cycle completes |
| `test_engine_snapshot_recorded_on_change` | State change → SnapshotStore.async_append called |
| `test_engine_snapshot_not_recorded_on_stable` | No change → async_append not called |

---

## 14. Design Constraints

- **No ML libraries.** All v2 modules use frequency tables and index-based percentiles.
  `ILearningModule` is the plug-in boundary for advanced implementations (see §15).
- **No hot-path I/O.** `infer()` is sync and reads only pre-computed in-memory state.
- **Domain hard inputs always win.** Signals are consumed only when the domain's own
  resolution is ambiguous or yields no result.
- **Graceful degradation.** If a module's `analyze()` fails, the module emits no signals
  until the next successful run. The eval cycle is unaffected.
- **Signal TTL prevents stale inference.** A 1-hour TTL for coarse signals (WeekdayState),
  15–30 minutes for fine-grained signals (Room, Lighting).
- **SnapshotStore is read-only from modules.** No module may write to the store.

---

## 15. ILearningModule as a Plug-in Contract

The four built-in modules (§6) use simple descriptive statistics intentionally. Any
implementation satisfying `ILearningModule` can be registered without changing any other
component:

| Tier | Examples |
|---|---|
| v2 default — frequency tables | Conditional counts, index-based median |
| Robust statistics | Kernel density, DBSCAN clustering on room patterns |
| Time-series | ARIMA on setpoint history, changepoint detection |
| Probabilistic | HMM for house_state transitions, Bayesian updating |
| ML | scikit-learn classifiers, ONNX runtime (requires venv with deps) |

Rules for custom modules:
1. `infer()` must be synchronous and return in < 1ms
2. `analyze()` must not modify SnapshotStore
3. Must not share mutable state with domain objects
4. `confidence` must be in [0.0, 1.0]
5. Should emit ≤ 5 signals per domain per cycle
