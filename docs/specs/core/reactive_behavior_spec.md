# Heima — Reactive Behavior Engine SPEC v1
## Phase 7: Behavior-as-Reaction

**Status**: Active v1 reaction contract
**Last Verified Against Code:** 2026-03-19
**Supersedes**: The `apply_filter` use case described in SPEC v1.1 (which was found redundant; see decisions).
**Complements**: `HeimaBehavior` framework (SPEC v1.1) which remains valid for passive observability.

Normative precedence:
- this document defines the intended reaction contract
- implementation details may evolve, but they must preserve the externally visible semantics defined here
- if code and this spec diverge, the divergence must be resolved explicitly rather than inferred from code alone

---

## 1. Vision

Heima observes behavioral patterns over time — from people, sensors, and house state transitions — and reacts autonomously by injecting additional `ApplyStep` instances into each evaluation cycle.

A **Reaction** does not replace domain logic. It enriches the apply plan with context the domain pipeline cannot compute on its own (temporal patterns, learned habits, anticipatory pre-conditioning).

Core principle: **observe a sliding window of snapshots → detect pattern → produce ApplyStep**.

### 1.1 Core terms

This spec uses the following terms normatively:

- **DecisionSnapshot**: the normalized system view for one evaluation cycle. It is the input surface
  used by reactions to decide whether to fire.
- **ApplyStep**: one concrete actuation request that can later be filtered, constrained, and
  executed by the runtime.
- **Reaction**: a component that observes snapshot history and may add `ApplyStep` instances to the
  current plan.
- **Domain logic**: the base deterministic logic of a domain such as lighting or heating, evaluated
  even when no reaction exists.
- **Constraint layer**: the common policy/filter layer that can block, modify, or suppress any
  apply step before execution.

Normative rule:
- a reaction is an enrichment layer, never an authority that bypasses domain constraints or direct
  runtime safety rules

### 1.2 Design goals

The reaction system exists to satisfy four goals:

1. express temporal or learned behavior that the domain pipeline cannot derive from one snapshot
2. keep learned behavior explainable as explicit conditions plus explicit actions
3. route reaction actions through the same execution and safety path as all other actions
4. allow reactions to be muted, observed, reset, and rebuilt from persisted configuration

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

### 2.1 Normative lifecycle

Each evaluation cycle MUST follow this conceptual order:

1. compute the current normalized snapshot
2. append it to bounded history
3. let domain pipelines build their base apply steps
4. let registered reactions inspect history and contribute additional steps
5. pass the merged step set through the shared constraint layer
6. execute the resulting plan
7. update observability surfaces

The runtime MAY optimize internals, but it MUST preserve these semantics.

---

## 3. SnapshotBuffer

A bounded ring buffer (default capacity: 20) that stores `DecisionSnapshot` objects in chronological order. Oldest entry is evicted when full.

```python
class SnapshotBuffer:
    def push(snapshot: DecisionSnapshot) -> None
    def history() -> list[DecisionSnapshot]  # oldest first, newest last
    def latest() -> DecisionSnapshot | None
    def clear() -> None
```

Normative requirements:
- history ordering must be chronological
- the newest snapshot must be directly accessible
- clearing history must remove all prior reaction-learning context that depends only on the buffer

---

## 4. HeimaReaction Base Class

```python
class HeimaReaction:
    @property
    def reaction_id(self) -> str: ...          # default: class name

    def evaluate(self, history: list[DecisionSnapshot]) -> list[ApplyStep]:
        """Return steps to inject into the current plan. Default: []."""
        return []

    def on_options_reloaded(self, options: dict) -> None: ...   # no-op
    def reset_learning_state(self) -> None: ...                 # no-op
    def diagnostics(self) -> dict: ...                          # {}
```

The engine:
1. Calls `reaction.evaluate(history)` for each registered reaction.
2. Tags each returned step with `source = "reaction:{reaction_id}"`.
3. Exception-isolates each reaction (exceptions are logged, never propagated).
4. Merges reaction steps into the plan before the constraint layer.

### 4.1 Behavioral contract

Every reaction implementation MUST obey these rules:

- `evaluate(history)` must be a pure decision step with respect to external side effects
- the returned steps must be fully executable by the normal runtime, not by private reaction code
- an exception inside one reaction must not stop evaluation of other reactions or domains
- if a reaction keeps internal learning state, that state must be resettable through
  `reset_learning_state()`
- if a reaction depends on persisted configuration, it must be rebuildable from options alone

### 4.2 ApplyStep.source Field

`source: str = ""` added to `ApplyStep`. Non-empty for reaction-generated steps (`"reaction:{id}"`). Domain pipeline steps remain `""`.

---

## 5. Pattern Detection Plugin

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

This section describes the semantic contract of the built-in reactions. The code may vary, but the
observable behavior described here is normative.

### 6.1 ConsecutiveStateReaction

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

**In-memory only**: arrival history is not persisted across restarts in v1. It is also cleared by
`learning_reset`.

**Known limitation**: arrival time accuracy depends on the evaluation cycle interval.

### 6.3 Proposal-driven reactions

Currently wired proposal-driven classes:
- `PresencePatternReaction`
- `LightingScheduleReaction`
- `HeatingPreferenceReaction`
- `HeatingEcoReaction`

`HeatingPreferenceReaction` fires when the configured `house_state` is entered and the observed setpoint differs from the learned target.

`HeatingEcoReaction` fires on entry into `away` and applies the learned eco target temperature derived from observed away sessions.

Normative rebuild rule:
- if a proposal type is user-acceptible in the options flow, the runtime must either rebuild it
  into an executable reaction class or explicitly reject/defer that proposal type
- the system must not persist “accepted but non-executable” learning reactions

---

## 7. Learning Backend Plugin

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

**Override detection responsibility**: The caller (engine or reaction) is responsible for detecting when the user negated the reaction's output. The backend only tracks what it's told. Future engine integration may detect overrides automatically (e.g., comparing last reaction steps with subsequent HA state), but this is not yet wired globally.

### 7.3 Pluggability

`ILearningBackend` is a `Protocol`. Future backends (`StatisticalBackend`, `MLBackend`) implement the same interface without changes to `HeimaReaction`.

---

## 8. Observability and Runtime Commands (R5)

This section defines the minimum external observability contract. Internal counters or richer
diagnostics may evolve, but these surfaces are the compatibility baseline.

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

Current payload is intentionally minimal. Confidence / override counters are exposed only when a
reaction backend surfaces them in `diagnostics()`. The base runtime currently guarantees:
- `muted`
- `fire_count`
- `suppressed_count`
- `last_fired_ts`

The runtime MAY expose more fields, but consumers must treat these four as the compatibility floor.

### 8.2 reaction.fired Event

Queued in the notification pipeline whenever a reaction produces at least one step. Emitted before constraints are applied. Rate-limiting and dedup rules from the Event Catalog apply.

Normative meaning:
- `reaction.fired` means “this reaction produced one or more candidate steps”
- it does not guarantee that the steps were ultimately executed, because constraints may still
  suppress them later

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
- Mute state is persisted in config-entry options and restored on reload/restart.
- `heima_reactions_active` is updated immediately on mute/unmute.
- Service raises `ServiceValidationError` if the `reaction_id` is not registered.

### 8.4 Diagnostics

The reaction subsystem MUST expose diagnostics sufficient to answer at least:
- which reactions are currently registered
- which reactions are currently muted
- how many times each reaction fired
- how many times each reaction was suppressed
- the last fire timestamp for each reaction

Reaction-specific diagnostics MAY include richer fields such as learned arrival counts or
configuration thresholds, but those fields are additive and not part of the compatibility minimum.

### 8.5 learning_reset

Via `heima.command`:

```yaml
service: heima.command
data:
  command: learning_reset
```

Semantics:
- clear persisted `EventStore`
- flush event storage immediately
- clear persisted `ProposalEngine` state
- clear runtime-local learning state in reactions/behaviors
- clear `SnapshotBuffer`

This is a hard reset of the learning substrate, not only a storage wipe.

---

## 9. Registration and Lifecycle

The runtime MUST support this lifecycle:

1. reactions are registered before normal evaluation begins
2. registered reactions participate in every evaluation cycle unless muted
3. option reload propagates updated configuration to registered reactions
4. learning reset propagates reset calls to reactions and behaviors that keep local learning state

Normative rules:
- registration order may affect diagnostic ordering, but must not change the semantic meaning of
  the merged apply plan
- unknown muted reaction ids loaded from persisted config must be ignored safely
- option reload must not require process restart to refresh reaction configuration
- reset must clear in-memory learning state even when the reaction itself remains registered

### 9.1 Persisted mute state

The reaction mute list is part of persisted user configuration.

Required semantics:
- muted reaction ids survive restart
- a muted reaction does not evaluate, emit `reaction.fired`, or contribute steps
- if persisted mute state contains ids that are not currently registered, those ids are ignored
  rather than treated as errors

### 9.2 Minimum observability guarantee

After each evaluation cycle, external observability must be able to show live state for all
registered reactions, including at least:
- `muted`
- `fire_count`
- `suppressed_count`
- `last_fired_ts`

Additional diagnostic detail is allowed but optional.

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
- **Constraint layer invariant**: all steps (domain + reaction) pass through the shared constraint layer. No bypass.
- **Learning is opt-in**: `ILearningBackend` is only active when explicitly provided.
- **Reversibility**: reactions are silenceable at runtime via `mute_reaction` / `unmute_reaction` commands, and mute state can also be persisted through configuration. Confidence suppression via `ILearningBackend` provides soft suppression.
- **Compatibility-first evolution**: the externally visible reaction contract must remain stable even if the internal engine structure evolves.

---

## 12. Non-Goals (v1)

- Persistent arrival history (in-memory only; cleared on restart).
- Automatic override detection from HA state (future engine integration).
- A general-purpose reaction DSL or YAML language.
- ML/statistical learning backends (interface is ready; implementation is future work).
