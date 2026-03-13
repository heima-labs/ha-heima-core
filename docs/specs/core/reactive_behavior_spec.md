# Heima — Reactive Behavior Engine SPEC v1
## Phase 7: Behavior-as-Reaction

**Status**: R0–R5 implemented on `main`. Options Flow integration for reactions/proposals available.
**Last Verified Against Code:** 2026-03-11
**Supersedes**: The `apply_filter` use case described in SPEC v1.1 (which was found redundant; see decisions).
**Complements**: `HeimaBehavior` framework (SPEC v1.1) which remains valid for passive observability.

---

## 1. Vision

Heima observes behavioral patterns over time — from people, sensors, and house state transitions — and reacts autonomously by injecting additional `ApplyStep` instances into each evaluation cycle.

A **Reaction** does not replace domain logic. It enriches the apply plan with context the domain pipeline cannot compute on its own (temporal patterns, learned habits, anticipatory pre-conditioning).

Core principle: **observe a sliding window of snapshots → detect pattern → produce ApplyStep**.

---

## 2. Architecture Overview

```
async_evaluate()
    │
    ├── _compute_snapshot()             → DecisionSnapshot
    ├── _snapshot_buffer.push(snapshot) → SnapshotBuffer (max 20)
    │
    ├── _build_apply_plan(snapshot)
    │     ├── lighting_steps (domain pipeline)
    │     ├── heating_steps  (domain pipeline)
    │     ├── _dispatch_reactions(history)
    │     │     └── for each HeimaReaction (skip if muted):
    │     │           steps = reaction.evaluate(history)
    │     │           tag each step: source = "reaction:{id}"
    │     │           if steps produced: queue reaction.fired event
    │     └── _apply_filter(all_steps, constraints)  ← constraint layer
    │           (domain + reaction steps treated equally)
    │
    ├── _sync_reactions_sensor()        → heima_reactions_active (JSON)
    └── _execute_apply_plan(plan)
```

**Key invariant**: Reaction steps pass through the same constraint layer as domain steps. A reaction cannot bypass security constraints.

---

## 3. SnapshotBuffer

**File**: `runtime/snapshot_buffer.py`

A bounded ring buffer (default capacity: 20) that stores `DecisionSnapshot` objects in chronological order. Oldest entry is evicted when full.

```python
class SnapshotBuffer:
    def push(snapshot: DecisionSnapshot) -> None
    def history() -> list[DecisionSnapshot]  # oldest first, newest last
    def latest() -> DecisionSnapshot | None
    def clear() -> None
```

Exposed as `engine.snapshot_history: list[DecisionSnapshot]`.

---

## 4. HeimaReaction Base Class

**File**: `runtime/reactions/base.py`

```python
class HeimaReaction:
    @property
    def reaction_id(self) -> str: ...          # default: class name

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        """Return steps to inject into the current plan. Default: []."""
        return []

    def on_options_reloaded(self, options: dict) -> None: ...   # no-op
    def diagnostics(self) -> dict: ...                          # {}
```

The engine:
1. Calls `reaction.evaluate(history)` for each registered reaction.
2. Tags each returned step with `source = "reaction:{reaction_id}"`.
3. Exception-isolates each reaction (exceptions are logged, never propagated).
4. Merges reaction steps into the plan before the constraint layer.

### 4.1 ApplyStep.source Field

`source: str = ""` added to `ApplyStep`. Non-empty for reaction-generated steps (`"reaction:{id}"`). Domain pipeline steps remain `""`.

---

## 5. Pattern Detection Plugin

**File**: `runtime/reactions/patterns.py`

```python
class IPatternDetector(Protocol):
    def matches(self, history: list[DecisionSnapshot]) -> bool: ...
```

Built-in: **`ConsecutiveMatchDetector`**

```python
ConsecutiveMatchDetector(
    predicate: Callable[[DecisionSnapshot], bool],
    consecutive_n: int,  # >= 1
)
```

Returns `True` if the last `consecutive_n` snapshots all satisfy `predicate`. Stateless: same history → same result.

---

## 6. Built-in Reactions

### 6.1 ConsecutiveStateReaction

**File**: `runtime/reactions/builtin.py`

Level-triggered reaction: fires on every evaluation cycle where the last N snapshots match a predicate.

```python
ConsecutiveStateReaction(
    predicate: Callable[[DecisionSnapshot], bool],
    consecutive_n: int,
    steps: list[ApplyStep],
    reaction_id: str | None = None,
    learning_backend: ILearningBackend | None = None,
    confidence_threshold: float = 0.5,
)
```

**Semantics**:
- `evaluate(history)` → `steps` if `ConsecutiveMatchDetector.matches(history)` else `[]`
- If `learning_backend` is set and `confidence < confidence_threshold` → suppress (return `[]`)
- Fires repeatedly while condition holds; stops immediately when condition breaks

**Use cases**:
- `house_state == "away"` for 3+ cycles → eco heating step
- `anyone_home == False` for 5+ cycles → turn-off unoccupied lighting zones

### 6.2 PresencePatternReaction

**File**: `runtime/reactions/presence.py`

Learns typical daily arrival times per weekday and fires pre-conditioning steps when the current time approaches the expected arrival window.

```python
PresencePatternReaction(
    steps: list[ApplyStep],
    min_arrivals: int = 5,        # arrivals needed before pattern activates
    window_half_min: int = 15,    # ±minutes around median arrival time
    pre_condition_min: int = 20,  # lead time before arrival to fire
    max_arrivals: int = 100,      # oldest evicted when full
    reaction_id: str | None = None,
    learning_backend: ILearningBackend | None = None,
    confidence_threshold: float = 0.5,
)
```

**Learning mechanism**:
1. Detects `anyone_home: False → True` transition in consecutive snapshots.
2. Records (weekday, minute-of-day) in local time from the snapshot timestamp.
3. Computes expected arrival window as `[median ± window_half_min]` for each weekday.
4. Fires `steps` when `current_time + pre_condition_min` falls in the window and nobody is home.
5. Midnight wrap-around: if target crosses 00:00, the next weekday's window is checked.

**In-memory only**: arrival history is not persisted across restarts in v1.

**Known limitation**: arrival time accuracy depends on the evaluation cycle interval.

---

## 7. Learning Backend Plugin

**File**: `runtime/reactions/learning.py`

### 7.1 Interface

```python
class ILearningBackend(Protocol):
    def observe(self, reaction_id: str, fired: bool, steps: list[ApplyStep]) -> None: ...
    def record_override(self, reaction_id: str) -> None: ...
    def confidence(self, reaction_id: str) -> float: ...    # 0.0–1.0
    def diagnostics(self, reaction_id: str) -> dict: ...
```

### 7.2 NaiveLearningBackend

Counter-based implementation.

```python
NaiveLearningBackend(
    override_threshold: int = 3,   # consecutive overrides before penalty
    reset_cycles: int = 20,        # override-free firing cycles to restore confidence
)
```

**Confidence lifecycle**:
- Starts at `1.0` per reaction.
- `record_override()` increments `consecutive_overrides`. When `>= override_threshold`, applies penalty `1/override_threshold` (floored at 0.0) and resets the counter.
- `observe(fired=True)` increments `cycles_since_last_override`. When `>= reset_cycles`, confidence is restored to `1.0`.
- State is independent per `reaction_id`.

**Override detection responsibility**: The caller (engine or reaction) is responsible for detecting when the user negated the reaction's output. The backend only tracks what it's told. Future engine integration will detect overrides automatically (e.g., comparing last reaction steps with subsequent HA state).

### 7.3 Pluggability

`ILearningBackend` is a `Protocol`. Future backends (`StatisticalBackend`, `MLBackend`) implement the same interface without changes to `HeimaReaction`.

---

## 8. Observability and Runtime Commands (R5)

### 8.1 heima_reactions_active Sensor

Always-present canonical sensor. Updated after every evaluation cycle and after mute/unmute operations. Value: JSON string.

```json
{
  "PresencePatternReaction": {
    "muted": false,
    "fire_count": 12,
    "suppressed_count": 0,
    "last_fired_ts": 1234567.8
  }
}
```

### 8.2 reaction.fired Event

Queued in the notification pipeline whenever a reaction produces at least one step. Emitted before constraints are applied. Rate-limiting and dedup rules from the Event Catalog apply.

```json
{
  "type": "reaction.fired",
  "key": "reaction.fired.{reaction_id}",
  "severity": "info",
  "context": {
    "reaction_id": "PresencePatternReaction",
    "step_count": 1
  }
}
```

### 8.3 mute_reaction / unmute_reaction Commands

Via `heima.command`:

```yaml
service: heima.command
data:
  command: mute_reaction          # or unmute_reaction
  params:
    reaction_id: "PresencePatternReaction"
```

- Muted reactions are **skipped entirely** in `_dispatch_reactions` (no evaluate, no event, no steps).
- Mute state is runtime-only: cleared on reload/restart.
- `heima_reactions_active` is updated immediately on mute/unmute.
- Service raises `ServiceValidationError` if the `reaction_id` is not registered.

### 8.4 Diagnostics (updated)

`engine.diagnostics()` includes:

```json
{
  "reactions": {
    "PresencePatternReaction": {
      "arrivals_count": 14,
      "fire_count": 3,
      "suppressed_count": 0,
      "last_fired_ts": 1234567.8,
      "min_arrivals": 5,
      "window_half_min": 15,
      "pre_condition_min": 20
    }
  },
  "muted_reactions": ["SomeOtherReaction"]
}
```

---

## 9. Registration and Lifecycle

```python
engine.register_reaction(reaction: HeimaReaction) -> None
```

Call before `async_initialize()`. Reactions are dispatched on every `async_evaluate()`.

`on_options_reloaded(options)` is called for all registered reactions when config entry options change. Exceptions are isolated.

### 9.1 Full Configuration Example

Reactions are defined in Python code (e.g. in `custom_components/heima/__init__.py`) and registered before `async_initialize()`:

```python
from custom_components.heima.runtime.reactions.builtin import ConsecutiveStateReaction
from custom_components.heima.runtime.reactions.presence import PresencePatternReaction
from custom_components.heima.runtime.contracts import ApplyStep

# Example 1: set eco temperature after 3 consecutive "away" cycles
eco_heating = ConsecutiveStateReaction(
    reaction_id="eco_heating_away",
    predicate=lambda s: s.house_state == "away",
    consecutive_n=3,
    steps=[
        ApplyStep(
            domain="heating",
            target="climate.termostato",
            action="climate.set_temperature",
            params={"temperature": 17.0},
        )
    ],
)

# Example 2: pre-condition home before typical arrival time
preheat = PresencePatternReaction(
    reaction_id="arrival_preheat",
    steps=[
        ApplyStep(
            domain="heating",
            target="climate.termostato",
            action="climate.set_temperature",
            params={"temperature": 21.0},
        )
    ],
    min_arrivals=5,
    pre_condition_min=20,
)

engine.register_reaction(eco_heating)
engine.register_reaction(preheat)
# engine.async_initialize() called by coordinator afterwards
```

### 9.2 Mute Management

**Runtime (cleared on restart)** — via `heima.command` service:

```yaml
service: heima.command
data:
  command: mute_reaction       # or unmute_reaction
  params:
    reaction_id: "eco_heating_away"
```

**Persisted (survives restarts)** — via Options Flow → Reactions, or by editing `options["reactions"]["muted"]` directly.

On every `on_options_reloaded`, the engine restores `_muted_reactions` from `options["reactions"]["muted"]`, intersected with currently registered reaction IDs. Unknown IDs are silently dropped.

```json
{ "reactions": { "muted": ["eco_heating_away"] } }
```

### 9.3 Observability

After each evaluation cycle, `heima_reactions_active` is updated with the live state of all registered reactions:

```json
{
  "eco_heating_away": { "muted": false, "fire_count": 12, "suppressed_count": 0, "last_fired_ts": 1234567.8 },
  "arrival_preheat":  { "muted": true,  "fire_count": 3,  "suppressed_count": 0, "last_fired_ts": null }
}
```

---

## 10. Relationship with HeimaBehavior (SPEC v1.1)

| Concept | `HeimaBehavior` | `HeimaReaction` |
|---|---|---|
| Role | Passive observer | Active contributor |
| Hook | `on_snapshot(snapshot)` | `evaluate(history)` |
| Output | None (side effects only) | `list[ApplyStep]` |
| Memory | None (stateless hook) | `list[DecisionSnapshot]` (history) |
| Constraint layer | n/a | Applied to all reaction steps |
| Use case | Diagnostics, snapshot history logging | Adaptive automations, pre-conditioning |

`apply_filter` on `HeimaBehavior` is available as an advanced extension point but **not used for concrete built-in behaviors** because it cannot safely block individual steps without a `tags` field on `ApplyStep` (context needed to distinguish auto-generated vs user-intent steps).

---

## 11. Design Principles

- **Stability first**: each step is autonomous and does not break existing domain logic.
- **Plugin-first**: `IPatternDetector` and `ILearningBackend` are swappable without touching reactions.
- **Constraint layer invariant**: all steps (domain + reaction) pass through `_apply_filter`. No bypass.
- **Learning is opt-in**: `ILearningBackend` is only active when explicitly provided.
- **Reversibility**: reactions are silenceable at runtime via `mute_reaction` / `unmute_reaction` commands (runtime-only, cleared on restart). Confidence suppression via `ILearningBackend` provides soft suppression.
- **No heavy refactor**: uses existing `ApplyStep` with one new field (`source`). Domain handlers unchanged.

---

## 12. Non-Goals (v1)

- Persistent arrival history (in-memory only; cleared on restart).
- Automatic override detection from HA state (future engine integration).
- User-configurable reactions via Options Flow (deferred; mute/unmute via service command is available).
- DSL-based or YAML-based reaction definitions.
- ML/statistical learning backends (interface is ready; implementation is future work).
