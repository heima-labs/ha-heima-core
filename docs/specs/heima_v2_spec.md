# Heima v2 — Formal Specification

**Status:** RFC — implementation planned on `main`
**Date:** 2026-03-12
**Version:** 2.0.0-draft
**Supersedes:** Previous v2 draft (2026-03-11). Incorporates architectural decisions A, B, C, IBehaviorAnalyzer unification, IInvariantCheck separation.

---

## §1 Vision

Heima is an intent-driven home intelligence engine distributed as a Home Assistant custom integration. Its purpose is **invisible intelligence**: the home adapts transparently, with minimum configuration, and without requiring inhabitants to think about it. Heima is an autonomous policy engine — it ingests canonical signals from all configured HA entities, evaluates structured domain rules, extrapolates behavioral patterns, detects cross-domain anomalies, and makes Home Assistant act intelligently and unobtrusively. The success metric is invisibility: if inhabitants never notice the system, it is working correctly.

---

## §2 v1 Baseline Summary

v1 delivers a complete deterministic control plane: a fixed DAG evaluation pipeline (InputNormalizer → PeopleDomain → OccupancyDomain → HouseStateDomain → LightingDomain → HeatingDomain → SecurityDomain → Apply + Execute), persistent inter-cycle memory via `CanonicalState`, a durable `EventStore` recording presence/heating/house_state transitions, a learning pipeline (`PresencePatternAnalyzer`, `HeatingPatternAnalyzer`, `ProposalEngine`, user-approval flow), a `HeimaReaction` framework with `PresencePatternReaction` and `ConsecutiveStateReaction`, and a full notification routing layer. All implemented phases have 263 passing tests. The DAG is hardcoded: domain order is fixed in `engine.py`, with no plugin registration mechanism. v2 replaces the hardcoded DAG with a declarative plugin framework, migrates the three control domains (Lighting, Heating, Security) to built-in plugins, unifies the behavior analysis interface, and introduces a structural constraint layer.

---

## §3 Goals and Non-Goals

| # | Goal |
|---|---|
| G1 | Replace hardcoded DAG ordering with declarative `depends_on` and topological sort |
| G2 | Migrate LightingDomain, HeatingDomain, SecurityDomain to built-in plugins; keep core minimal and stable |
| G3 | Unify behavior analysis under `IBehaviorAnalyzer` / `BehaviorFinding` with routed kind dispatch |
| G4 | Introduce `IInvariantCheck`: synchronous per-cycle structural constraint checks, decoupled from domain logic |
| G5 | Detect cross-domain structural inconsistencies every cycle and surface them as typed events |
| G6 | Detect statistical deviations from learned patterns offline and surface them as typed events |
| G7 | Enable multi-signal contextual reasoning: learned `P(state | context)` influences domain resolution when hard inputs are ambiguous |
| G8 | Close the act→verify loop: confirm that reactions produced their expected outcome, degrade unreliable reactions |
| G9 | Allow plugins to extend the options flow with their own `vol.Schema` via `IOptionsSchemaProvider` |

| # | Non-Goal |
|---|---|
| NG1 | Modify core domain logic (PeopleDomain, OccupancyDomain, HouseStateDomain) in a behavior-changing way |
| NG2 | Introduce external ML libraries (all inference uses pure Python + `statistics` stdlib) |
| NG3 | Apply anomaly detections as automated actions (anomalies are surfaced only; actuation remains in reaction/domain layer) |
| NG4 | Implement cross-home or cloud learning (all data stays in HA local storage) |
| NG5 | Deliver a UI for signal inspection in v2 (diagnostics endpoint and sensor attributes are sufficient) |

---

## §4 Architecture Overview

The following diagram shows the complete v2 pipeline. Components present in v1 are unlabeled; components new in v2 are marked `[v2]`.

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│  engine.async_evaluate()  —  HOT PATH (every cycle)                                       │
│                                                                                           │
│  ┌─────────────────────────────┐                                                          │
│  │  IInputNormalizerPlugin × N │  raw HA state → NormalizedObservation                   │
│  └──────────────┬──────────────┘                                                          │
│                 │                                                                         │
│  ┌──────────────▼──────────────────────────────────────────────────────────────┐          │
│  │  [v2]  _collect_signals()                                                   │          │
│  │        ILearningModule.infer(InferenceContext) × N                          │          │
│  │        → list[InferenceSignal]  →  SignalRouter  →  per-domain buckets     │          │
│  └──────────────┬──────────────────────────────────────────────────────────────┘          │
│                 │                                                                         │
│  ┌──────────────▼──────────────────────────────────────────────────────────────┐          │
│  │  [v2]  DAG evaluation  (topological order, resolved at registration)        │          │
│  │                                                                             │          │
│  │   ┌──────────────────────────────────────────────────┐                     │          │
│  │   │  CORE DOMAINS (non-plugin, always first in DAG)  │                     │          │
│  │   │   PeopleDomain    → PeopleResult                 │                     │          │
│  │   │   OccupancyDomain → OccupancyResult              │                     │          │
│  │   │   HouseStateDomain→ HouseStateResult             │                     │          │
│  │   └──────────────────────────────────────────────────┘                     │          │
│  │                                                                             │          │
│  │   ┌──────────────────────────────────────────────────┐                     │          │
│  │   │  BUILT-IN DOMAIN PLUGINS  [v2 — IDomainPlugin]   │                     │          │
│  │   │   LightingPlugin  → LightingResult               │                     │          │
│  │   │   HeatingPlugin   → HeatingResult                │                     │          │
│  │   │   SecurityPlugin  → SecurityResult               │                     │          │
│  │   └──────────────────────────────────────────────────┘                     │          │
│  │                                                                             │          │
│  │   Third-party IDomainPlugin instances (ordered by topological sort)        │          │
│  └──────────────┬──────────────────────────────────────────────────────────────┘          │
│                 │                                                                         │
│  ┌──────────────▼──────────────────────────────────────────────────────────────┐          │
│  │  [v2]  IInvariantCheck layer                                                │          │
│  │        check(snapshot, domain_results) → InvariantViolation | None × N     │          │
│  │        → HeimaEvent(type="anomaly.*")  →  EventStore + notification        │          │
│  └──────────────┬──────────────────────────────────────────────────────────────┘          │
│                 │                                                                         │
│  ┌──────────────▼──────────────────────────────────────────────────────────────┐          │
│  │  Apply + Execute  (IApplyExecutor per domain)                               │          │
│  └──────────────┬──────────────────────────────────────────────────────────────┘          │
│                 │                                                                         │
│  ┌──────────────▼──────────────────────────────────────────────────────────────┐          │
│  │  HeimaReaction pipeline                                                     │          │
│  │     [v2]  OutcomeTracker.on_reaction_fired(reaction_id, ...)                │          │
│  └──────────────┬──────────────────────────────────────────────────────────────┘          │
│                 │                                                                         │
│  ┌──────────────▼──────────────────────────────────────────────────────────────┐          │
│  │  [v2]  OutcomeTracker.check_pending(snapshot)                               │          │
│  │        → positive / negative outcomes  →  ILearningBackend                 │          │
│  └──────────────┬──────────────────────────────────────────────────────────────┘          │
│                 │                                                                         │
│  ┌──────────────▼──────────────────────────────────────────────────────────────┐          │
│  │  CanonicalState update  (key/value, string-namespaced by plugin_id.key)     │          │
│  │     [v2]  SnapshotStore.async_append(HouseSnapshot) on-change              │          │
│  └─────────────────────────────────────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────────────────────────────────────┘

OFFLINE PATH — coordinator-owned, every 6h:
┌──────────────────────────────────────────────────────────────────────────────┐
│  [v2]  IBehaviorAnalyzer.analyze(event_store, snapshot_store) × N           │
│        → list[BehaviorFinding]                                               │
│        → FindingRouter:                                                      │
│            kind="pattern"     → ProposalEngine  (ReactionProposal)          │
│            kind="anomaly"     → AnomalyEngine   (AnomalySignal → HeimaEvent)│
│            kind="correlation" → InferenceEngine (InferenceSignal)           │
└──────────────────────────────────────────────────────────────────────────────┘

INFERENCE PATH — every cycle, before domain evaluation:
┌──────────────────────────────────────────────────────────────────────────────┐
│  [v2]  ILearningModule.infer(InferenceContext) × N                           │
│        → SignalRouter → domain signal buckets                                │
└──────────────────────────────────────────────────────────────────────────────┘

FEEDBACK PATH — after every resolved outcome verification:
┌──────────────────────────────────────────────────────────────────────────────┐
│  [v2]  OutcomeTracker.check_pending()  →  ILearningBackend.observe()         │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key invariants (inherited from v1, extended for v2):**
- No v2 component may block the hot-path eval cycle with I/O.
- All v2 writes from the hot path are scheduled as fire-and-forget tasks.
- Signals and invariant violations are additive inputs; they never silently replace hard sensor data.
- Core domains (People, Occupancy, HouseState) are not plugins: they are always evaluated first, in fixed order.
- Plugin domains are evaluated in topological order after core domains.
- `CanonicalState` is unchanged: generic key/value, string-namespaced by convention (`plugin_id.key`). No typed isolation.

---

## §5 Plugin Framework

### §5.1 Plugin Interface Catalog

All plugin interfaces are Protocols defined in `runtime/plugin_contracts.py`.

| Interface | Kind | Sync/Async | Description | Example |
|---|---|---|---|---|
| `IInputNormalizerPlugin` | Normalizer | Sync | Maps raw HA entity states → canonical observations | `DeviceTrackerNormalizer` |
| `IDomainPlugin` | Domain | `compute()` sync | Domain node in the DAG; declares `domain_id`, `depends_on`, `compute()`, `reset()`, `diagnostics()` | `LightingPlugin`, `HeatingPlugin` |
| `IApplyExecutor` | Executor | Async | Executes a specific action type (e.g. lighting, heating) | `LightingExecutor` |
| `IHeimaBehavior` | Behavior | Async | Side effect post-cycle (already exists in v1) | `LightingBehavior` |
| `IHeimaReaction` | Reaction | Async | Reactive behavior triggered on snapshot history (already exists in v1) | `PresencePatternReaction` |
| `IBehaviorAnalyzer` | Analyzer | Async | Offline analysis of EventStore + SnapshotStore; produces `BehaviorFinding` objects | `PresencePatternAnalyzer` |
| `ILearningModule` | Learning | `analyze()` async, `infer()` sync | Offline model training + per-cycle synchronous inference | `WeekdayStateModule` |
| `IInvariantCheck` | Constraint | Sync | Per-cycle structural constraint check on current snapshot + domain results | `PresenceWithoutOccupancy` |
| `IOutcomeVerifier` | Verifier | Sync | Verifies reaction outcomes against expected post-condition | `OutcomeTracker` |
| `IOptionsSchemaProvider` | Config | Sync | Plugin extends the options flow with its own `vol.Schema` | `HeatingPlugin` |

### §5.2 IDomainPlugin in Detail

```python
# runtime/plugin_contracts.py

class IDomainPlugin(Protocol):
    @property
    def domain_id(self) -> str:
        """Unique domain identifier. Used as the key in DomainResultBag."""
        ...

    @property
    def depends_on(self) -> list[str]:
        """
        List of domain_ids whose results this domain requires in compute().
        The engine resolves evaluation order by topological sort at registration time.
        Core domain IDs ("people", "occupancy", "house_state") are valid dependency targets.
        """
        ...

    def compute(
        self,
        canonical_state: CanonicalState,
        domain_results: DomainResultBag,
        signals: list[InferenceSignal] | None = None,
    ) -> DomainResult:
        """
        Compute this domain's result for the current cycle.
        Must be synchronous and I/O-free.
        canonical_state: read-only snapshot of previous cycle's persisted state.
        domain_results: results of all already-computed dependencies (guaranteed by DAG order).
        signals: optional inference signals for this domain_id (may be None or empty).
        """
        ...

    def reset(self) -> None:
        """Reset all in-memory state (called on config change or manual reset)."""
        ...

    def diagnostics(self) -> dict[str, Any]:
        """Return a diagnostics dict for engine.diagnostics()["plugins"][domain_id]."""
        ...
```

`compute()` must never read from sibling domain results outside `domain_results` (i.e. must not call engine state directly). This preserves DAG purity.

### §5.3 DAG Resolution

DAG order is resolved once at registration time, not at every cycle.

**Algorithm:**
1. Collect all registered `IDomainPlugin` instances.
2. Build a directed graph: edge `(A → B)` means "A depends on B" (B must run before A).
3. Run Kahn's topological sort.
4. If a cycle is detected → raise `HeimaDomainCycleError` at startup; integration fails to load.
5. If a declared dependency `domain_id` is not registered → raise `HeimaMissingDependencyError` at startup.
6. Core domains (`people`, `occupancy`, `house_state`) are always prepended to the sorted list, in fixed order.

**Implementation:**

```python
# runtime/dag.py

def resolve_dag(plugins: list[IDomainPlugin]) -> list[IDomainPlugin]:
    """
    Returns plugins in evaluation order (dependencies first).
    Raises HeimaDomainCycleError on circular dependency.
    Raises HeimaMissingDependencyError if a declared dependency is not registered.
    """
```

This function is called in `engine.register_plugin(plugin)` and after all plugins are registered, a final `engine.finalize_dag()` call produces the ordered list stored as `_eval_order`.

### §5.4 DomainResultBag

`DomainResultBag` is a typed container passed to each domain's `compute()`. It contains the results of all already-evaluated domains in the current cycle.

```python
# runtime/domain_result_bag.py

class DomainResultBag:
    """
    Immutable view of domain results computed so far in this cycle.
    Populated incrementally as the engine walks the topological order.
    """

    def get(self, domain_id: str) -> DomainResult | None:
        """Return the result for the given domain_id, or None if not yet computed."""
        ...

    def require(self, domain_id: str) -> DomainResult:
        """Return the result or raise KeyError if not present (programming error)."""
        ...

    def __contains__(self, domain_id: str) -> bool: ...
```

Domains access dependencies via `domain_results.require("house_state")` etc. Type-narrowing (casting to a concrete result type) is the plugin's responsibility.

**CanonicalState vs DomainResultBag coherence rule:**

A domain plugin may read from both `canonical_state` (previous cycle) and `domain_results` (current cycle). When the two diverge:

- `canonical_state` is the authoritative view **during evaluation** — it reflects the last committed state and is stable across the entire cycle.
- `domain_results` contains the current-cycle output of upstream domains, which has not yet been committed to `CanonicalState`.
- If a plugin needs the "stable last known state", it MUST read from `canonical_state`.
- If a plugin needs the "freshest current-cycle output of an upstream domain", it reads from `domain_results.require(...)`.
- **Never merge or average the two views** — treat them as distinct temporal snapshots.

### §5.5 Core vs Built-in Plugins vs Third-Party Plugins

| Category | Examples | Characteristics |
|---|---|---|
| **Core domains** | `PeopleDomain`, `OccupancyDomain`, `HouseStateDomain` | Not plugins. Implemented as concrete classes in `runtime/domains/`. Always evaluated first, in fixed order. Cannot be replaced or removed. Minimal and stable. |
| **Built-in plugins** | `LightingPlugin`, `HeatingPlugin`, `SecurityPlugin` | `IDomainPlugin` implementations shipped with Heima. Fully privileged (access all HA APIs). Architecturally equivalent to third-party plugins: they declare `depends_on`, are registered by the coordinator, and are evaluated in topological order after core domains. Can be disabled or replaced by third-party plugins. |
| **Third-party plugins** | Any user/developer plugin | `IDomainPlugin` implementations loaded from external packages or the HA custom_components directory. Subject to the same rules as built-in plugins. Isolated from core. |

The core is intentionally minimal and stable: adding new home control areas never requires modifying core domains.

### §5.6 IOptionsSchemaProvider

Plugins that require configuration can extend the options flow by implementing `IOptionsSchemaProvider`:

```python
class IOptionsSchemaProvider(Protocol):
    @property
    def options_schema(self) -> vol.Schema:
        """
        Returns a voluptuous schema for this plugin's configuration section.
        The engine merges this schema into the options flow under the key plugin_id.
        Called at options flow initialization; must be synchronous and side-effect-free.
        """
        ...

    def options_defaults(self) -> dict[str, Any]:
        """Default values for this plugin's options keys."""
        ...
```

The options flow step for domain plugins iterates all registered `IOptionsSchemaProvider` instances and renders each plugin's config section in sequence. Plugin config is stored under `options["plugins"][plugin_id]`.

### §5.7 Plugin Lifecycle

```
register(plugin)
  → validate: domain_id unique, depends_on resolvable
  → store in _registered_plugins

finalize_dag()
  → topological sort → _eval_order
  → startup validation complete (errors raised here)

per cycle:
  for plugin in _eval_order:
      result = plugin.compute(canonical_state, domain_results, signals.get(plugin.domain_id))
      domain_results[plugin.domain_id] = result

on config change:
  for plugin in _registered_plugins:
      plugin.reset()

on shutdown:
  (no explicit shutdown hook in v2; plugins are garbage-collected)
```

---

## §6 Home Control Taxonomy

The table below lists all home control areas and their implementation status under the v2 plugin framework.

| Area | Sub-aspects | Status |
|---|---|---|
| **Presence** | Named persons, anonymous, quorum, away/home detection | Core (PeopleDomain) |
| **Occupancy** | Room occupancy, dwell state machine | Core (OccupancyDomain) |
| **House state** | Signals, override, policy resolution, vacation | Core (HouseStateDomain) |
| **Lighting** | Intent resolution, scene apply, hold, manual override | Built-in plugin (LightingPlugin) |
| **Heating** | Branch selection, vacation curve, setpoint apply, hvac_mode | Built-in plugin (HeatingPlugin) |
| **Security** | Normalization, arm/disarm, mismatch detection | Built-in plugin (SecurityPlugin) |
| **Events** | Queue, dedup, rate-limit, routing | Core service (EventsDomain, not a plugin) |
| **Watering** | Schedule, soil moisture, rain skip | Plugin (planned, not in v2) |
| **Energy** | Load shifting, tariff-aware scheduling | Plugin (not planned) |
| **Audio/AV** | Scene-linked audio, presence-triggered TV | Plugin (not planned) |
| **Ventilation** | CO₂/humidity-driven fan control | Plugin (not planned) |

**Explicit statement:** core domains are stable and immutable between major versions. Built-in plugins are the reference implementations for their area. Third-party plugins can replace any built-in plugin (by registering with the same `domain_id`) or add entirely new domains.

---

## §7 IBehaviorAnalyzer and FindingRouter

### §7.1 BehaviorFinding

`IBehaviorAnalyzer` replaces `IPatternAnalyzer` (v1). It produces `BehaviorFinding` objects with a `kind` field that determines routing.

```python
# runtime/plugin_contracts.py

from typing import Literal
from dataclasses import dataclass

@dataclass
class BehaviorFinding:
    kind: Literal["pattern", "anomaly", "correlation"]
    analyzer_id: str
    description: str
    confidence: float                                      # 0.0–1.0
    payload: ReactionProposal | AnomalySignal | InferenceSignal
```

- `kind="pattern"` → payload is `ReactionProposal` → routed to `ProposalEngine`
- `kind="anomaly"` → payload is `AnomalySignal` → routed to `AnomalyEngine` → emitted as `HeimaEvent` + stored in `EventStore`
- `kind="correlation"` → payload is `InferenceSignal` → routed to `InferenceEngine` for model update

### §7.2 IBehaviorAnalyzer Protocol

```python
class IBehaviorAnalyzer(Protocol):
    @property
    def analyzer_id(self) -> str:
        """Unique analyzer identifier."""
        ...

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: SnapshotStore,
    ) -> list[BehaviorFinding]:
        """
        Offline analysis. Called every 6h by the coordinator scheduler.
        May use async I/O freely. Must not mutate EventStore or SnapshotStore.
        Returns an empty list if no findings; never raises.
        """
        ...
```

This replaces the v1 `IPatternAnalyzer` Protocol. Existing analyzers (`PresencePatternAnalyzer`, `HeatingPatternAnalyzer`) are migrated by adding `snapshot_store` to their signature and returning `BehaviorFinding(kind="pattern", ...)` wrapping their existing `ReactionProposal` output.

### §7.3 FindingRouter

```python
# runtime/finding_router.py

class FindingRouter:
    def __init__(
        self,
        proposal_engine: ProposalEngine,
        anomaly_engine: AnomalyEngine,
        inference_engine: InferenceEngine,
    ) -> None: ...

    def route(self, findings: list[BehaviorFinding]) -> None:
        """
        Routes each finding to the appropriate engine by kind.
        Synchronous. Called by the coordinator after IBehaviorAnalyzer.analyze() completes.
        """
        for f in findings:
            match f.kind:
                case "pattern":
                    self._proposal_engine.submit(f.payload)
                case "anomaly":
                    self._anomaly_engine.submit_statistical(f.payload)
                case "correlation":
                    self._inference_engine.submit_correlation(f.payload)
```

### §7.4 Built-in Analyzers

| Analyzer | kind emitted | What it detects | Min support | v1 / v2 |
|---|---|---|---|---|
| `PresencePatternAnalyzer` | `pattern` | Arrival/departure time patterns per weekday | 7 events/weekday | v1, migrated |
| `HeatingPatternAnalyzer` | `pattern` | Preferred setpoints per house_state | 10 events/state | v1, migrated |
| `AnomalyAnalyzer` | `anomaly` | Statistical deviations: unusual arrival time, heating setpoint outlier | 10 events | v2 new |
| `CorrelationAnalyzer` | `correlation` | Multi-signal correlations: room pattern → house_state | 15 snapshots/pattern | v2 new |

All built-in analyzers are registered by the coordinator at startup. Third-party `IBehaviorAnalyzer` implementations can be registered via `coordinator.register_analyzer(analyzer)`.

---

## §8 IInvariantCheck

### §8.1 Concept and Separation from IBehaviorAnalyzer

`IInvariantCheck` is separate from `IBehaviorAnalyzer` by design. The distinction is:

| | `IInvariantCheck` | `IBehaviorAnalyzer` |
|---|---|---|
| When | Every cycle (synchronous) | Periodic, offline (async, every 6h) |
| Input | Current `DecisionSnapshot` + `DomainResultBag` | `EventStore` + `SnapshotStore` (historical) |
| Nature | Structural inconsistency (binary: violated or not) | Statistical / behavioral finding (probabilistic) |
| Cost | O(1) | O(N) — may read thousands of records |
| Output | `InvariantViolation` (immediate) | `BehaviorFinding` (routed by kind) |

Invariant checks must never use `EventStore` or `SnapshotStore`. They operate only on the current cycle's snapshot and domain results.

### §8.2 IInvariantCheck Protocol

```python
# runtime/plugin_contracts.py

class IInvariantCheck(Protocol):
    @property
    def check_id(self) -> str:
        """Unique check identifier. Used as the key for debounce state."""
        ...

    def check(
        self,
        snapshot: DecisionSnapshot,
        domain_results: DomainResultBag,
    ) -> InvariantViolation | None:
        """
        Synchronous. Must complete in < 0.5 ms — no I/O, no heavy compute.
        Returns InvariantViolation if the constraint is violated, None otherwise.
        Called after all domains have computed, before Apply.
        """
        ...
```

### §8.3 InvariantViolation

```python
@dataclass(frozen=True)
class InvariantViolation:
    check_id: str
    severity: Literal["info", "warning", "critical"]
    anomaly_type: str           # becomes the HeimaEvent type: f"anomaly.{anomaly_type}"
    description: str
    context: dict[str, Any]     # arbitrary key/value for diagnostics and notification body
```

An `InvariantViolation` is immediately converted by the engine to a `HeimaEvent(type=f"anomaly.{anomaly_type}")` and emitted to the notification pipeline and `EventStore`. Debounce is applied per `check_id` before emission (see §8.5).

### §8.4 Built-in Invariant Checks

All four built-in checks are registered by the engine core (not by plugins). They cannot be disabled individually, but their debounce windows are configurable.

| check_id | Trigger condition | severity | Default debounce_s |
|---|---|---|---|
| `presence_without_occupancy` | `anyone_home=True` AND `len(occupied_rooms)==0` AND house has at least 1 sensorized room | `warning` | 300 |
| `security_presence_mismatch` | `security_intent="armed_away"` AND `anyone_home=True` | `critical` | 60 |
| `heating_home_empty` | Heating apply active AND `anyone_home=False` AND `house_state="away"` duration > `anomaly_heating_empty_threshold_s` (default 1800 s) | `warning` | 600 |
| `sensor_stuck` | Any configured presence/occupancy sensor has not changed state for longer than `anomaly_sensor_stuck_threshold_s` (default 86400 s) | `info` | 3600 |

Note: `security_presence_mismatch` migrates the existing mismatch detection logic from `SecurityDomain`. The domain continues to produce its result unchanged; the check merely asserts the cross-domain invariant.

### §8.5 Debounce State Machine

Each check has independent per-cycle state:

```python
@dataclass
class InvariantCheckState:
    check_id: str
    first_seen_ts: float      # monotonic; set when condition first becomes true
    last_emitted_ts: float    # monotonic; 0 = never emitted
    is_active: bool
```

Per-cycle logic:

```
condition_violated = check.check(snapshot, domain_results) is not None

if condition_violated:
    if not state.is_active:
        state.first_seen_ts = now()
        state.is_active = True
    elapsed = now() - state.first_seen_ts
    if elapsed >= debounce_s and (now() - state.last_emitted_ts) >= re_emit_interval_s:
        emit HeimaEvent(type=f"anomaly.{violation.anomaly_type}", ...)
        state.last_emitted_ts = now()
else:
    if state.is_active:
        emit HeimaEvent(type="anomaly.resolved", context={"resolved_type": check_id})
        state.is_active = False
        state.first_seen_ts = 0
```

`re_emit_interval_s` (default: 3600 s) prevents flooding when a persistent violation is never resolved.

### §8.6 Integration Point

The invariant check layer is called in `engine.async_evaluate()` after all domain plugins have computed, before `Apply + Execute`:

```python
# in engine.async_evaluate():
violations = self._run_invariant_checks(snapshot, domain_results)
for v in violations:
    self._emit_anomaly_event(v)
```

`_run_invariant_checks()` is synchronous and applies debounce before returning violations to emit.

### §8.7 Configuration

New keys in options (under `general`):

| Key | Type | Default | Description |
|---|---|---|---|
| `anomaly_enabled` | bool | `true` | Global on/off for invariant check emission |
| `anomaly_sensor_stuck_threshold_s` | int | `86400` | Sensor stuck detection window |
| `anomaly_heating_empty_threshold_s` | int | `1800` | Heating-with-empty-house grace period |
| `anomaly_notify_on_info` | bool | `false` | Whether `info`-severity violations trigger notifications |
| `anomaly_re_emit_interval_s` | int | `3600` | Re-emit interval for persistent violations |

---

## §9 InferenceEngine v2

The InferenceEngine v2 provides per-cycle learned signals to domain plugins, replacing ambiguous hard-input situations with probabilistic guidance.

### §9.1 HouseSnapshot

The unit of observation written by the hot path to `SnapshotStore`. Derived from `DecisionSnapshot` (domain outputs, not raw HA entity values).

```python
# runtime/inference/snapshot_store.py

@dataclass(frozen=True)
class HouseSnapshot:
    ts: str                              # ISO-8601 UTC
    weekday: int                         # 0=Monday … 6=Sunday
    minute_of_day: int                   # 0–1439 local time
    anyone_home: bool
    named_present: tuple[str, ...]       # sorted person slugs
    room_occupancy: dict[str, bool]      # room_id → occupied
    house_state: str
    heating_setpoint: float | None
    lighting_scenes: dict[str, str]      # room_id → scene name applied
    security_armed: bool
```

Written on-change only: appended only if at least one field differs from the previous snapshot. Typical household: 50–150 records/day. `SnapshotStore`: max 10,000 records, 90-day TTL, persisted via HA `Store`.

### §9.2 ILearningModule Contract

```python
# runtime/inference/base.py

class ILearningModule(Protocol):
    @property
    def module_id(self) -> str: ...

    async def analyze(self, store: SnapshotStore) -> None:
        """
        Offline phase. Reads snapshot history; updates internal model.
        Called every 6h off-cycle. May use async I/O freely.
        Must not emit signals; must not write to SnapshotStore.
        """

    def infer(self, context: InferenceContext) -> list[InferenceSignal]:
        """
        Online phase. Reads pre-computed model + context; emits signals.
        Synchronous. Must complete in < 1 ms — no I/O, no heavy compute.
        Called once per eval cycle, before domain evaluation.
        """

    def diagnostics(self) -> dict[str, Any]:
        """Current model summary for engine.diagnostics()["inference"]["modules"]."""
```

Exceptions in `infer()` are caught by the engine; the offending module emits no signals for that cycle. The eval cycle is unaffected.

### §9.3 InferenceSignal Hierarchy

```python
# runtime/inference/signals.py

class Importance(IntEnum):
    OBSERVE = 0   # logged only; never applied in domain resolution
    SUGGEST = 1   # applied only when no hard signal is active
    ASSERT  = 2   # soft override; domain still decides final outcome (reserved, not used in v2)

@dataclass(frozen=True)
class InferenceSignal:
    source_id: str
    confidence: float       # 0.0–1.0
    importance: Importance
    ttl_s: int
    label: str              # human-readable reason (for diagnostics)

@dataclass(frozen=True)
class HouseStateSignal(InferenceSignal):
    predicted_state: str

@dataclass(frozen=True)
class HeatingSignal(InferenceSignal):
    predicted_setpoint: float
    house_state_context: str

@dataclass(frozen=True)
class LightingSignal(InferenceSignal):
    room_id: str
    predicted_scene: str

@dataclass(frozen=True)
class OccupancySignal(InferenceSignal):
    room_id: str
    predicted_occupied: bool    # stub; not applied in v2
```

### §9.4 SignalRouter

```python
# runtime/inference/router.py

class SignalRouter:
    def route(self, signals: list[InferenceSignal]) -> dict[type, list[InferenceSignal]]:
        """
        Groups signals by concrete subclass type.
        Filters expired signals (based on ttl_s vs signal creation time).
        Sorts each bucket by confidence descending.
        Returns a dict keyed by concrete InferenceSignal subclass.
        """
```

Each domain plugin receives only the signal type matching its domain via `signals.get(domain_id)` in `compute()`. Routing is pure (no side effects, no I/O).

### §9.5 Built-in Learning Modules

| Module | What it learns | Signal emitted | Min support |
|---|---|---|---|
| `WeekdayStateModule` | `P(house_state \| weekday, hour_bucket)` | `HouseStateSignal` | 10 snapshots/slot |
| `RoomStateCorrelationModule` | `P(house_state \| occupied_room_pattern)` | `HouseStateSignal` | 15 snapshots/pattern |
| `HeatingPreferenceModule` | `preferred_setpoint[house_state]` from observed setpoints | `HeatingSignal` | 10 snapshots/state |
| `LightingPatternModule` | `P(scene \| room_id, house_state, hour_bucket)` | `LightingSignal` | 8 snapshots/slot |
| `HouseStateInferenceModule` | `P(house_state \| weekday, hour_bucket, occupied_rooms, anyone_home)` | `HouseStateSignal` | 20 snapshots/context key |

Hour bucket = `minute_of_day // 60` (24 buckets/day). All models use frequency tables and index-based percentiles — no external libraries.

### §9.6 Domain Signal Consumption Policy

Signals are optional parameters to each plugin's `compute()`. Hard inputs always take precedence.

| Domain plugin | Signal type accepted | Condition for use | Min confidence |
|---|---|---|---|
| `HouseStateDomain` | `HouseStateSignal` | No definitive hard signal (no override, no unambiguous presence, no vacation) | 0.60 |
| `HeatingPlugin` | `HeatingSignal` | `apply_allowed=True` AND `target_temperature is None` from branch config AND no manual override guard | 0.55 |
| `LightingPlugin` | `LightingSignal` | No explicit scene configured for current house_state AND `manual_hold=False` for that room | 0.65 |
| `SecurityPlugin` | — | Not applicable in v2 | — |
| `OccupancyDomain` | `OccupancySignal` | Stub — accepted in signature; not applied in v2 | n/a |

Signals never override: active user overrides, explicit config values, or safety guards.

### §9.7 House State Learning and User Approval

When a `HouseStateSignal` from `HouseStateInferenceModule` would change the resolved house state, a `ReactionProposal` is generated on first application. While the proposal is pending, the signal is applied transiently. After user acceptance, it is applied silently. After rejection, the signal is computed but not consumed; no re-proposal for the same `(context_key, predicted_state)` pair (stored in `ApprovalStore`, persisted across restarts).

Confidence model:
```
confidence = probability × min(1.0, support / MIN_SUPPORT)
```

| confidence range | Behavior |
|---|---|
| < 0.40 | Signal not emitted |
| 0.40–0.60 | Emitted as `OBSERVE` (logged, not applied) |
| 0.60–0.80 | Emitted as `SUGGEST`; applied when hard inputs ambiguous |
| > 0.80 | Applied; may generate auto-apply proposal |

---

## §10 OutcomeTracker

### §10.1 Concept

The `OutcomeTracker` closes the learn→act→verify loop. When a `HeimaReaction` fires, it registers a pending verification. On each subsequent eval cycle, the tracker checks whether the predicted event materialized within the timeout window. The result feeds `ILearningBackend` and, after repeated failures, triggers a degradation proposal.

### §10.2 Data Models

```python
# runtime/outcome_tracker.py

@dataclass
class PendingVerification:
    reaction_id: str
    expected_event_type: str        # e.g. "presence.arrive", "house_state.change"
    expected_within_s: float
    fired_at_ts: float              # monotonic
    snapshot_at_fire: HouseSnapshot

@dataclass
class OutcomeRecord:
    reaction_id: str
    outcome: Literal["positive", "negative"]
    fired_at_ts: float
    resolved_at_ts: float
    expected_event_type: str
    context: dict[str, Any]
```

### §10.3 Mechanism

**Registration (hot path, synchronous):**

```
On reaction.fire():
    if reaction.outcome_spec is not None:
        tracker.register(PendingVerification(...))
```

**Verification check (hot path, synchronous, every cycle):**

```
For each pending verification:
    elapsed = monotonic() - fired_at_ts
    recent_events = event_store.query_since(fired_at_ts, event_type=expected_event_type)

    if recent_events:
        record OutcomeRecord(outcome="positive")
        remove from pending
        backend.observe(reaction_id, "positive")

    elif elapsed > expected_within_s:
        record OutcomeRecord(outcome="negative")
        remove from pending
        backend.observe(reaction_id, "negative")
        _check_degradation(reaction_id)
```

`event_store.query_since()` is a synchronous in-memory read. Safe on the hot path.

### §10.4 Timeout Policy

| Reaction type | Default `expected_within_s` | Rationale |
|---|---|---|
| `PresencePatternReaction` | 1800 | Fires 20 min before expected arrival; 30 min window is generous |
| `ConsecutiveStateReaction` | 600 | State change expected promptly after trigger |
| Custom reactions | 900 (default) | Falls back to `outcome_spec.timeout_s` |

### §10.5 Degradation Proposal

After K=5 consecutive negative outcomes for a reaction, `OutcomeTracker` submits a `ReactionProposal` to `ProposalEngine`. Submitted at most once per reaction until the user accepts or rejects. Rejection resets the streak counter.

### §10.6 Integration Points

| Integration point | Detail |
|---|---|
| `HeimaReaction.fire()` | Call `OutcomeTracker.register()` if `outcome_spec` is set |
| `engine.async_evaluate()` | Call `OutcomeTracker.check_pending(snapshot)` after Apply, before CanonicalState update |
| `ProposalEngine` | `OutcomeTracker` holds a reference; calls `submit()` on degradation |
| `engine.diagnostics()` | `"outcome_tracker"` key: pending count, per-reaction positive/negative counts |

---

## §11 House State Learning

See §9.7 for the complete specification. Summary:

- Implemented as `HouseStateInferenceModule` (an `ILearningModule`).
- Learns `P(house_state | weekday, hour_bucket, occupied_rooms, anyone_home)` from `SnapshotStore`.
- Emits `HouseStateSignal(importance=SUGGEST)` when confidence ≥ 0.60.
- `HouseStateDomain` consumes the signal only when no definitive hard input is active.
- First application triggers a `ReactionProposal`; silent after user approval.
- `ApprovalStore` persists approval/rejection decisions across restarts (`STORAGE_KEY = "heima_inference_approvals"`).
- Rejection is permanent per `(context_key_hash, predicted_state)` pair until cleared.

---

## §12 Implementation Phases

### Phase A — Plugin Framework

**Unlocks:** declarative DAG, plugin registration, built-in plugins as IDomainPlugin, IOptionsSchemaProvider.

**Dependencies:** none (refactor of existing code).

| Deliverable | File(s) |
|---|---|
| `IDomainPlugin`, `DomainResultBag`, `IOptionsSchemaProvider` protocols | `runtime/plugin_contracts.py` |
| `resolve_dag()` with cycle detection and missing-dependency detection | `runtime/dag.py` |
| Engine plugin registration API: `register_plugin()`, `finalize_dag()` | `runtime/engine.py` |
| Migrate `LightingDomain` → `LightingPlugin(IDomainPlugin)` | `runtime/domains/lighting.py` |
| Migrate `HeatingDomain` → `HeatingPlugin(IDomainPlugin)` | `runtime/domains/heating.py` |
| Migrate `SecurityDomain` → `SecurityPlugin(IDomainPlugin)` | `runtime/domains/security.py` |
| Coordinator: register all plugins, call `finalize_dag()` | `coordinator.py` |
| All existing tests green; add DAG cycle detection tests | `tests/` |

### Phase B — IBehaviorAnalyzer + FindingRouter

**Unlocks:** unified behavior analysis interface, AnomalyEngine routing for statistical findings, CorrelationAnalyzer.

**Dependencies:** Phase A complete (FindingRouter references InferenceEngine, which requires Phase D infrastructure — can be stubbed).

| Deliverable | File(s) |
|---|---|
| `IBehaviorAnalyzer`, `BehaviorFinding`, `AnomalySignal` | `runtime/plugin_contracts.py` |
| `FindingRouter` | `runtime/finding_router.py` |
| Migrate `PresencePatternAnalyzer` to `IBehaviorAnalyzer` | `runtime/analyzers/presence_pattern.py` |
| Migrate `HeatingPatternAnalyzer` to `IBehaviorAnalyzer` | `runtime/analyzers/heating_pattern.py` |
| New: `AnomalyAnalyzer` (statistical deviations) | `runtime/analyzers/anomaly.py` |
| New: `CorrelationAnalyzer` (multi-signal correlations) | `runtime/analyzers/correlation.py` |
| Coordinator: register analyzers, wire `FindingRouter` | `coordinator.py` |

### Phase C — IInvariantCheck

**Unlocks:** per-cycle structural constraint layer, migration of SecurityDomain mismatch detection.

**Dependencies:** Phase A complete (requires `DomainResultBag` to be available).

| Deliverable | File(s) |
|---|---|
| `IInvariantCheck`, `InvariantViolation`, `InvariantCheckState` | `runtime/plugin_contracts.py`, `runtime/invariant_check.py` |
| Engine invariant check loop: `_run_invariant_checks()` | `runtime/engine.py` |
| Built-in check: `PresenceWithoutOccupancy` | `runtime/invariants/presence.py` |
| Built-in check: `SecurityPresenceMismatch` (migrate from SecurityDomain) | `runtime/invariants/security.py` |
| Built-in check: `HeatingHomeEmpty` | `runtime/invariants/heating.py` |
| Built-in check: `SensorStuck` | `runtime/invariants/sensor.py` |
| Debounce state machine in engine | `runtime/engine.py` |
| Tests: ≥ 1 test per check, debounce behavior, resolution event | `tests/invariants/` |

### Phase D — InferenceEngine v2

**Unlocks:** per-cycle learned signals to domain plugins, SnapshotStore, HouseStateInferenceModule.

**Dependencies:** Phase A complete (plugins must expose `compute(signals=...)` signature).

| Deliverable | File(s) |
|---|---|
| `ILearningModule`, `InferenceContext`, `InferenceSignal` hierarchy | `runtime/inference/base.py`, `runtime/inference/signals.py` |
| `SnapshotStore` with persistence | `runtime/inference/snapshot_store.py` |
| `SignalRouter` | `runtime/inference/router.py` |
| `WeekdayStateModule`, `HeatingPreferenceModule` | `runtime/inference/modules/` |
| Engine: `_collect_signals()`, `_record_snapshot_if_changed()` | `runtime/engine.py` |
| Coordinator: module registration, 6h offline scheduling | `coordinator.py` |
| Domain plugins: `compute(signals=...)` signature update | `runtime/domains/*.py` |
| `RoomStateCorrelationModule`, `LightingPatternModule` | Phase D2 (deferred) |

### Phase E — OutcomeTracker + Feedback Loop

**Unlocks:** act→verify loop, degradation proposals, `StatsLearningBackend`.

**Dependencies:** Phase D complete (OutcomeTracker reads `HouseSnapshot` from SnapshotStore context).

| Deliverable | File(s) |
|---|---|
| `OutcomeTracker`, `PendingVerification`, `OutcomeRecord` | `runtime/outcome_tracker.py` |
| `HeimaReaction.outcome_spec` attribute | `runtime/reactions/base.py` |
| `PresencePatternReaction`: populate `outcome_spec` | `runtime/reactions/presence_pattern.py` |
| `StatsLearningBackend` (replaces `NaiveLearningBackend`) | `runtime/learning_backend.py` |
| Engine integration: `check_pending()` after Apply | `runtime/engine.py` |
| Degradation proposal path | `runtime/proposal_engine.py` |
| Tests: positive outcome, negative outcome, degradation trigger | `tests/outcome_tracker/` |

### Phase F — House State Learning

**Unlocks:** `HouseStateInferenceModule`, `ApprovalStore`, user-approval gate.

**Dependencies:** Phases D and E complete.

| Deliverable | File(s) |
|---|---|
| `HouseStateInferenceModule` | `runtime/inference/modules/house_state_inference.py` |
| `ApprovalStore` | `runtime/inference/approval_store.py` |
| Approval gate in `HouseStateDomain.evaluate()` | `runtime/domains/house_state.py` |
| Options Flow: `proposals` step extended for `house_state_learned_context` | `config_flow/` |
| `AnomalyAnalyzer` registered in `FindingRouter` (statistical anomalies) | `coordinator.py` |
| Tests: confidence model, approval path, rejection persistence | `tests/inference/` |

---

## §13 File Structure

### New files

| File | Purpose |
|---|---|
| `runtime/plugin_contracts.py` | All plugin interface Protocols: `IDomainPlugin`, `IBehaviorAnalyzer`, `IInvariantCheck`, `ILearningModule`, `IOptionsSchemaProvider`, `BehaviorFinding`, `InvariantViolation` |
| `runtime/dag.py` | `resolve_dag()`, `HeimaDomainCycleError`, `HeimaMissingDependencyError` |
| `runtime/domain_result_bag.py` | `DomainResultBag` |
| `runtime/finding_router.py` | `FindingRouter` |
| `runtime/invariant_check.py` | `InvariantCheckState`, engine invariant loop helpers |
| `runtime/invariants/presence.py` | `PresenceWithoutOccupancy` check |
| `runtime/invariants/security.py` | `SecurityPresenceMismatch` check |
| `runtime/invariants/heating.py` | `HeatingHomeEmpty` check |
| `runtime/invariants/sensor.py` | `SensorStuck` check |
| `runtime/analyzers/anomaly.py` | `AnomalyAnalyzer` (statistical, `IBehaviorAnalyzer`) |
| `runtime/analyzers/correlation.py` | `CorrelationAnalyzer` (multi-signal, `IBehaviorAnalyzer`) |
| `runtime/inference/__init__.py` | Public API exports |
| `runtime/inference/base.py` | `ILearningModule`, `InferenceContext` |
| `runtime/inference/signals.py` | `Importance`, `InferenceSignal` hierarchy |
| `runtime/inference/snapshot_store.py` | `HouseSnapshot`, `SnapshotStore` |
| `runtime/inference/router.py` | `SignalRouter` |
| `runtime/inference/approval_store.py` | `ApprovalStore` |
| `runtime/inference/modules/weekday_state.py` | `WeekdayStateModule` |
| `runtime/inference/modules/room_state.py` | `RoomStateCorrelationModule` |
| `runtime/inference/modules/heating_preference.py` | `HeatingPreferenceModule` |
| `runtime/inference/modules/lighting_pattern.py` | `LightingPatternModule` |
| `runtime/inference/modules/house_state_inference.py` | `HouseStateInferenceModule` |
| `runtime/outcome_tracker.py` | `OutcomeTracker`, `PendingVerification`, `OutcomeRecord` |

### Modified files

| File | Change |
|---|---|
| `runtime/engine.py` | Plugin registration API, DAG evaluation loop, `_collect_signals()`, `_record_snapshot_if_changed()`, `_run_invariant_checks()`, `OutcomeTracker.check_pending()` call, diagnostics extensions |
| `runtime/domains/lighting.py` | Implement `IDomainPlugin`; `compute(canonical_state, domain_results, signals)` |
| `runtime/domains/heating.py` | Implement `IDomainPlugin`; `compute(canonical_state, domain_results, signals)` |
| `runtime/domains/security.py` | Implement `IDomainPlugin`; `compute(canonical_state, domain_results, signals)`; remove internal mismatch detection (migrated to `SecurityPresenceMismatch` invariant check) |
| `runtime/domains/house_state.py` | Signal consumption + approval gate for `HouseStateSignal` |
| `runtime/domains/occupancy.py` | `compute(signals: list[OccupancySignal] = [])` stub |
| `runtime/analyzers/presence_pattern.py` | Migrate `IPatternAnalyzer` → `IBehaviorAnalyzer`; return `BehaviorFinding(kind="pattern", ...)` |
| `runtime/analyzers/heating_pattern.py` | Same migration |
| `runtime/reactions/base.py` | Add `outcome_spec: OutcomeSpec \| None = None` |
| `runtime/reactions/presence_pattern.py` | Populate `outcome_spec` |
| `runtime/reactions/consecutive_state.py` | Populate `outcome_spec` |
| `runtime/proposal_engine.py` | Add `submit(proposal)` for tracker-triggered proposals; accept `IBehaviorAnalyzer` registrations |
| `coordinator.py` | Register plugins, invariant checks, analyzers, learning modules; call `finalize_dag()`; schedule 6h offline pass |
| `config_flow/` | Handle `house_state_learned_context` and `reaction_degraded` proposal types; `IOptionsSchemaProvider` rendering loop |
| `translations/en.json`, `it.json` | Labels for new proposal types and anomaly notifications |

---

## §14 Design Constraints

| # | Constraint | Rationale |
|---|---|---|
| 1 | **No ML libraries in built-in implementations.** All built-in analyzers and modules use pure Python stdlib: `sorted()`, index-based percentile arithmetic, `statistics.median()`, `statistics.correlation()`, `collections.defaultdict`. Conditional probability tables (Naive Bayes with Laplace smoothing) and z-score/IQR outlier detection cover all v2 use cases. This is a deliberate fit for the domain: homes produce small datasets (tens to hundreds of observations) where simple statistics outperform complex models that overfit. Explainability is a hard requirement — every decision must be expressible in a human-readable sentence. `IBehaviorAnalyzer` and `ILearningModule` are the explicit plug-in boundaries: a third-party plugin may provide ML-backed implementations (GMM, ARIMA, a local LLM) without any change to the core. |
| 2 | **No blocking I/O on the hot path.** `infer()`, `_run_invariant_checks()`, `OutcomeTracker.check_pending()`, and `OutcomeTracker.register()` are synchronous and I/O-free. All writes to stores are scheduled as `hass.async_create_task(store.async_append(...))`. | HA's event loop is single-threaded; any blocking call degrades the entire HA instance. |
| 3 | **HA async patterns only.** `analyze()` and `async_append()` are coroutines. Batched writes use `store.async_delay_save(fn, delay=30)`. Off-cycle tasks use `async_call_later` with recursive reschedule. | Consistent with existing v1 patterns (EventStore, ProposalEngine). |
| 4 | **DAG is resolved once at startup, not per cycle.** `finalize_dag()` runs topological sort at registration time. Cycle and missing-dependency errors are fatal at integration load. | Per-cycle sort would add unnecessary overhead and mask configuration errors until runtime. |
| 5 | **CanonicalState remains generic key/value.** Plugin state is namespaced by convention (`plugin_id.key`). No typed isolation per plugin. | Avoids over-engineering; namespacing by convention is sufficient and already used in v1. |
| 6 | **Core domains are not plugins.** `PeopleDomain`, `OccupancyDomain`, `HouseStateDomain` are concrete classes evaluated in fixed order before all plugin domains. | Core must be stable and minimal. Making it pluggable would risk instability in the foundational layer. |
| 7 | **IInvariantCheck must not read EventStore or SnapshotStore.** It receives only the current `DecisionSnapshot` and `DomainResultBag`. | Invariant checks are O(1) per-cycle; allowing historical reads would break this guarantee and conflate structural checks with statistical analysis. |
| 8 | **Signals are additive, never substitutes.** A domain with fully determined hard inputs must ignore all `InferenceSignal` objects. Signals never override active user overrides, explicit config values, or safety guards. | Prevents inference from silently masking real sensor data. |
| 9 | **All persistent stores use HA `homeassistant.helpers.storage.Store`.** Keys: `heima_snapshots`, `heima_inference_approvals`. | Consistent with v1 stores; survives HA restarts; included in HA backup. |
| 10 | **Behavior-preserving refactor for Phase A.** The migration of Lighting/Heating/Security to IDomainPlugin must not change any externally observable behavior. All 263 existing tests must remain green after Phase A. | Prevents regressions during the architectural migration and validates that the plugin framework is a true structural improvement. |
