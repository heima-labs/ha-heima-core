# Heima v2 — Formal Specification

**Status:** RFC — implementation planned on `main`
**Date:** 2026-04-30
**Version:** 2.1.0-draft
**Supersedes:** 2.0.0-draft (2026-03-12). Incorporates Activity Layer (§7), Event-Driven Trigger
(§11), enriched `InferenceContext` / `HouseSnapshot`, updated DAG and phase plan.

---

## §1 Vision

Heima is an intent-driven home intelligence engine distributed as a Home Assistant custom
integration. Its purpose is **invisible intelligence**: the home adapts transparently, with minimum
configuration, and without requiring inhabitants to think about it. Heima is an autonomous policy
engine — it ingests canonical signals from all configured HA entities, evaluates structured domain
rules, extrapolates behavioral patterns, detects cross-domain anomalies, and makes Home Assistant
act intelligently and unobtrusively. The success metric is invisibility: if inhabitants never
notice the system, it is working correctly.

The v2 model is **event-driven**: evaluation is triggered by meaningful state changes in the home,
not by a fixed timer. Time is a contextual dimension used to interpret events, not a trigger.
The system does not learn "at 22:00 dim the lights" — it learns "when the `movie_night` activity
is active, dim the lights in the living room". Clock time surfaces only as a feature in
pattern recognition.

---

## §2 v1 Baseline Summary

v1 delivers a complete deterministic control plane: a fixed DAG evaluation pipeline
(`InputNormalizer → PeopleDomain → OccupancyDomain → HouseStateDomain → LightingDomain →
HeatingDomain → SecurityDomain → Apply + Execute`), persistent inter-cycle memory via
`CanonicalState`, a durable `EventStore` recording presence/heating/house_state transitions,
a learning pipeline (`PresencePatternAnalyzer`, `HeatingPatternAnalyzer`, `ProposalEngine`,
user-approval flow), a `HeimaReaction` framework with `PresencePatternReaction` and
`ConsecutiveStateReaction`, and a full notification routing layer. All implemented phases have
660 passing tests. The DAG is hardcoded: domain order is fixed in `engine.py`, with no plugin
registration mechanism.

v2 replaces the hardcoded DAG with a declarative plugin framework, adds `ActivityDomain` as a
fourth core domain between `OccupancyDomain` and `HouseStateDomain`, introduces an event-driven
evaluation trigger, migrates the three control domains to built-in plugins, unifies behavior
analysis under `IBehaviorAnalyzer`, introduces `IInvariantCheck`, and adds a full inference
pipeline with `ILearningModule` and `ActivityInferenceModule`.

---

## §3 Goals and Non-Goals

| # | Goal |
|---|---|
| G1 | Replace hardcoded DAG ordering with declarative `depends_on` and topological sort |
| G2 | Migrate LightingDomain, HeatingDomain, SecurityDomain to built-in plugins |
| G3 | Unify behavior analysis under `IBehaviorAnalyzer` / `BehaviorFinding` with routed kind dispatch |
| G4 | Introduce `IInvariantCheck`: synchronous per-cycle structural constraint checks |
| G5 | Detect cross-domain structural inconsistencies every cycle and surface them as typed events |
| G6 | Detect statistical deviations from learned patterns offline and surface them as typed events |
| G7 | Enable multi-signal contextual reasoning: learned `P(state \| context)` influences domain resolution when hard inputs are ambiguous |
| G8 | Close the act→verify loop: confirm that reactions produced their expected outcome |
| G9 | Allow plugins to extend the options flow via `IOptionsSchemaProvider` |
| G10 | Introduce `ActivityDomain` as fourth core domain: detect primitive home activities from normalized sensor observations with candidate/grace hysteresis |
| G11 | Replace the periodic-only eval trigger with a hybrid event-driven model: subscribe to HA `state_changed` on registered signal entities, batch with per-class debounce, periodic fallback every 5 minutes |
| G12 | Discover composite activity patterns offline via `ActivityAnalyzer`; surface as `ActivityProposal` for user approval |

| # | Non-Goal |
|---|---|
| NG1 | Modify core PeopleDomain or OccupancyDomain behavior |
| NG2 | Introduce external ML libraries (all inference uses pure Python + `statistics` stdlib) |
| NG3 | Apply anomaly detections as automated actions (anomalies are surfaced only) |
| NG4 | Implement cross-home or cloud learning (all data stays in HA local storage) |
| NG5 | Deliver a UI for signal inspection in v2 |
| NG6 | Per-person activity tracking (contract is forward-compatible via `Activity.context`; implementation deferred) |

---

## §4 Architecture Overview

### §4.1 Hot Path

```
┌────────────────────────────────────────────────────────────────────────────────────────────┐
│  engine.async_evaluate()  —  HOT PATH (triggered by event or periodic fallback)            │
│                                                                                             │
│  ┌──────────────────────────────────┐                                                       │
│  │  IInputNormalizerPlugin × N      │  raw HA state → NormalizedObservation                │
│  └───────────────┬──────────────────┘                                                       │
│                  │                                                                          │
│  ┌───────────────▼──────────────────────────────────────────────────────────────┐           │
│  │  [v2]  _collect_signals()                                                    │           │
│  │        ILearningModule.infer(InferenceContext) × N                           │           │
│  │        → list[InferenceSignal]  →  SignalRouter  →  per-type buckets        │           │
│  │        (InferenceContext includes previous_activity_names from CanonicalState)│           │
│  └───────────────┬──────────────────────────────────────────────────────────────┘           │
│                  │                                                                          │
│  ┌───────────────▼──────────────────────────────────────────────────────────────┐           │
│  │  [v2]  DAG evaluation  (topological order, resolved at registration)         │           │
│  │                                                                              │           │
│  │   ┌────────────────────────────────────────────────────────┐                │           │
│  │   │  CORE DOMAINS (non-plugin, fixed order)                │                │           │
│  │   │   PeopleDomain     → PeopleResult                      │                │           │
│  │   │   OccupancyDomain  → OccupancyResult                   │                │           │
│  │   │   ActivityDomain   → ActivityResult          [v2 NEW]  │                │           │
│  │   │   HouseStateDomain → HouseStateResult                  │                │           │
│  │   └────────────────────────────────────────────────────────┘                │           │
│  │                                                                              │           │
│  │   ┌────────────────────────────────────────────────────────┐                │           │
│  │   │  BUILT-IN DOMAIN PLUGINS  [v2 — IDomainPlugin]         │                │           │
│  │   │   LightingPlugin  → LightingResult                     │                │           │
│  │   │   HeatingPlugin   → HeatingResult                      │                │           │
│  │   │   SecurityPlugin  → SecurityResult                     │                │           │
│  │   └────────────────────────────────────────────────────────┘                │           │
│  │                                                                              │           │
│  │   Third-party IDomainPlugin instances (ordered by topological sort)         │           │
│  └───────────────┬──────────────────────────────────────────────────────────────┘           │
│                  │                                                                          │
│  ┌───────────────▼──────────────────────────────────────────────────────────────┐           │
│  │  [v2]  IInvariantCheck layer → InvariantViolation | None × N                │           │
│  │        → HeimaEvent(type="anomaly.*")  →  EventStore + notification         │           │
│  └───────────────┬──────────────────────────────────────────────────────────────┘           │
│                  │                                                                          │
│  ┌───────────────▼──────────────────────────────────────────────────────────────┐           │
│  │  Apply + Execute  (IApplyExecutor per domain)                                │           │
│  └───────────────┬──────────────────────────────────────────────────────────────┘           │
│                  │                                                                          │
│  ┌───────────────▼──────────────────────────────────────────────────────────────┐           │
│  │  HeimaReaction pipeline                                                      │           │
│  │     [v2]  OutcomeTracker.on_reaction_fired(reaction_id, ...)                 │           │
│  └───────────────┬──────────────────────────────────────────────────────────────┘           │
│                  │                                                                          │
│  ┌───────────────▼──────────────────────────────────────────────────────────────┐           │
│  │  [v2]  OutcomeTracker.check_pending(snapshot)                                │           │
│  │        → positive / negative outcomes  →  ILearningBackend                  │           │
│  └───────────────┬──────────────────────────────────────────────────────────────┘           │
│                  │                                                                          │
│  ┌───────────────▼──────────────────────────────────────────────────────────────┐           │
│  │  CanonicalState update  (key/value, string-namespaced by plugin_id.key)      │           │
│  │     [v2]  SnapshotStore.async_append(HouseSnapshot) on-change               │           │
│  └──────────────────────────────────────────────────────────────────────────────┘           │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

### §4.2 Offline Path

```
OFFLINE — coordinator-owned, every 6h:
┌──────────────────────────────────────────────────────────────────────────────┐
│  [v2]  IBehaviorAnalyzer.analyze(event_store, snapshot_store) × N            │
│        → list[BehaviorFinding]                                               │
│        → FindingRouter:                                                      │
│            kind="pattern"     → ProposalEngine  (ReactionProposal)          │
│            kind="activity"    → ProposalEngine  (ActivityProposal)  [NEW]   │
│            kind="anomaly"     → AnomalyEngine   (AnomalySignal)            │
│            kind="correlation" → InferenceEngine (InferenceSignal)           │
└──────────────────────────────────────────────────────────────────────────────┘
```

### §4.3 Inference Path

```
INFERENCE — every cycle, before domain evaluation:
┌──────────────────────────────────────────────────────────────────────────────┐
│  [v2]  ILearningModule.infer(InferenceContext) × N                           │
│        → SignalRouter → domain/type signal buckets                           │
│        InferenceContext includes previous_activity_names from CanonicalState │
└──────────────────────────────────────────────────────────────────────────────┘
```

### §4.4 Event-Driven Trigger

```
EVENT TRIGGER — replaces periodic-only timer:
┌──────────────────────────────────────────────────────────────────────────────┐
│  HA state_changed subscription × registered signal entity classes            │
│  → per-class debounce (2–10s) → async_evaluate()                            │
│  Periodic fallback: every 300s (sunset, calendar, slow-changing sensors)     │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Key invariants (inherited from v1, extended for v2):**
- No v2 component may block the hot-path eval cycle with I/O.
- All v2 writes from the hot path are scheduled as fire-and-forget tasks.
- Signals and invariant violations are additive inputs; they never silently replace hard sensor data.
- Core domains (People, Occupancy, Activity, HouseState) are not plugins: always evaluated first, in fixed order.
- Plugin domains are evaluated in topological order after core domains.
- `CanonicalState` is unchanged: generic key/value, string-namespaced by convention.
- Time is a contextual feature, not an evaluation trigger.

---

## §5 Plugin Framework

### §5.1 Plugin Interface Catalog

All plugin interfaces are Protocols defined in `runtime/plugin_contracts.py`.

| Interface | Kind | Sync/Async | Description |
|---|---|---|---|
| `IInputNormalizerPlugin` | Normalizer | Sync | Maps raw HA entity states → canonical observations |
| `IDomainPlugin` | Domain | `compute()` sync | Domain node in the DAG; declares `domain_id`, `depends_on`, `compute()`, `reset()`, `diagnostics()` |
| `IActivityDetector` | Activity | `detect()` sync | Primitive activity detector registered with `ActivityDomain` |
| `IApplyExecutor` | Executor | Async | Executes a specific action type |
| `IHeimaBehavior` | Behavior | Async | Side effect post-cycle |
| `IHeimaReaction` | Reaction | Async | Reactive behavior triggered on snapshot history |
| `IBehaviorAnalyzer` | Analyzer | Async | Offline analysis of EventStore + SnapshotStore |
| `ILearningModule` | Learning | `analyze()` async, `infer()` sync | Offline model training + per-cycle synchronous inference |
| `IInvariantCheck` | Constraint | Sync | Per-cycle structural constraint check |
| `IOutcomeVerifier` | Verifier | Sync | Verifies reaction outcomes |
| `IOptionsSchemaProvider` | Config | Sync | Plugin extends the options flow |

### §5.2 IDomainPlugin in Detail

```python
class IDomainPlugin(Protocol):
    @property
    def domain_id(self) -> str: ...

    @property
    def depends_on(self) -> list[str]: ...

    def compute(
        self,
        canonical_state: CanonicalState,
        domain_results: DomainResultBag,
        signals: list[InferenceSignal] | None = None,
    ) -> DomainResult: ...

    def reset(self) -> None: ...

    def diagnostics(self) -> dict[str, Any]: ...
```

`compute()` must never perform I/O. Core domain IDs (`"people"`, `"occupancy"`, `"activity"`,
`"house_state"`) are valid `depends_on` targets.

### §5.3 DAG Resolution

Resolved once at `finalize_dag()`. Kahn's topological sort. `HeimaDomainCycleError` on cycle;
`HeimaMissingDependencyError` on missing dependency. Core domains always prepended in fixed order.

### §5.4 DomainResultBag

Immutable per-cycle accumulator. Plugins access dependencies via
`domain_results.require("activity")` etc.

**CanonicalState vs DomainResultBag coherence rule:** `canonical_state` = stable last committed
state. `domain_results` = current-cycle output of upstream domains (not yet committed). Never
merge or average the two views.

### §5.5 Core vs Built-in vs Third-Party Plugins

| Category | Examples | Characteristics |
|---|---|---|
| **Core domains** | `PeopleDomain`, `OccupancyDomain`, `ActivityDomain`, `HouseStateDomain` | Not plugins. Concrete classes in `runtime/domains/`. Fixed order. Cannot be replaced. |
| **Built-in plugins** | `LightingPlugin`, `HeatingPlugin`, `SecurityPlugin` | `IDomainPlugin` shipped with Heima. Declare `depends_on`, sorted by DAG after core. Can be disabled. |
| **Third-party plugins** | Any external plugin | Subject to same rules as built-in plugins. |

### §5.6 IOptionsSchemaProvider

```python
class IOptionsSchemaProvider(Protocol):
    @property
    def options_schema(self) -> vol.Schema: ...
    def options_defaults(self) -> dict[str, Any]: ...
```

Plugin config stored under `options["plugins"][plugin_id]`.

### §5.7 Plugin Lifecycle

```
register(plugin) → finalize_dag() → per-cycle compute() → on-config reset() → no shutdown hook
```

---

## §6 Home Control Taxonomy

| Area | Sub-aspects | Status |
|---|---|---|
| **Presence** | Named persons, anonymous, quorum, away/home detection | Core (PeopleDomain) |
| **Occupancy** | Room occupancy, dwell state machine | Core (OccupancyDomain) |
| **Activity** | Primitive activity detection, hysteresis, composite signal routing | Core (ActivityDomain) — v2 new |
| **House state** | Signals, override, policy resolution, vacation | Core (HouseStateDomain) |
| **Lighting** | Intent resolution, scene apply, hold, manual override | Built-in plugin (LightingPlugin) |
| **Heating** | Branch selection, vacation curve, setpoint apply | Built-in plugin (HeatingPlugin) |
| **Security** | Normalization, arm/disarm, mismatch detection | Built-in plugin (SecurityPlugin) |
| **Events** | Queue, dedup, rate-limit, routing | Core service (not a plugin) |
| **Watering** | Schedule, soil moisture, rain skip | Plugin (planned) |
| **Energy** | Load shifting, tariff-aware scheduling | Plugin (not planned) |
| **Ventilation** | CO₂/humidity-driven fan control | Plugin (not planned) |

Core domains are stable and immutable between major versions. Built-in plugins are reference
implementations. Third-party plugins can replace any built-in plugin or add new domains.

---

## §7 Activity Layer

### §7.1 Concept

An **activity** is a home state observable at the device/sensor level, more granular than
`house_state`. Activities are two-tiered:

- **Primitive activities**: deterministically detected from `NormalizedObservation`. A primitive
  activity is a fact, not an inference (e.g., `stove_on` = stove circuit power > threshold).
  Computed by built-in `IActivityDetector` implementations registered with `ActivityDomain`.

- **Composite activities**: inferred patterns of co-occurring primitives + context (e.g.,
  `movie_night` = `tv_active` + low lux + evening + no movement). Learned offline by
  `ActivityInferenceModule`; emitted as `ActivitySignal` per cycle.

`house_state` and activities are **orthogonal dimensions**. A single activity can be active across
multiple house states (`cooking` is valid in both `house_state=home` and `house_state=working`).
Reactions and domain plugins can condition on either or both.

### §7.2 Data Models

```python
# runtime/domains/activity.py

@dataclass(frozen=True)
class Activity:
    name: str
    confidence: float              # 1.0 for primitive (deterministic); 0–1 for composite
    room_id: str | None            # None = house-level activity
    started_at: float              # monotonic timestamp of phase ACTIVE entry
    duration_s: float              # total seconds spent in ACTIVE phase this session
    context: dict[str, Any]        # extensible; keys namespaced by contributor (e.g. "people.person_id")

@dataclass(frozen=True)
class ActivityResult:
    active: tuple[Activity, ...]      # confirmed active activities, sorted by confidence desc
    candidates: tuple[Activity, ...]  # in candidate window, not yet confirmed
```

`Activity.context` is the generic extension point. It is empty in all v2 built-in detectors.
Future plugins (e.g., a per-person activity tracker) store their attributes here under a
namespaced key (e.g., `"people.person_id": "alice"`), consistent with the `CanonicalState`
namespacing convention. Adding new attributes to `context` is non-breaking.

### §7.3 ActivityDomain

`ActivityDomain` is a core domain (not a plugin). It is evaluated in fixed order after
`OccupancyDomain` and before `HouseStateDomain`.

```python
# runtime/domains/activity_domain.py

class ActivityDomain:
    def evaluate(
        self,
        observation: NormalizedObservation,
        canonical_state: CanonicalState,
        activity_signals: list[ActivitySignal] | None = None,
    ) -> ActivityResult:
        """
        1. Run all registered IActivityDetector.detect() — produces ActivityDetection | None per detector.
        2. Advance each detector's HysteresisState machine.
        3. Collect confirmed-active primitives (phase=ACTIVE) into ActivityResult.active.
        4. Collect candidate primitives into ActivityResult.candidates.
        5. Merge composite ActivitySignal objects into ActivityResult.active
           (confidence from signal, already filtered by SignalRouter).
        Must be synchronous and I/O-free.
        """

    def register_detector(self, detector: "IActivityDetector") -> None:
        """Register a primitive activity detector. Called at coordinator startup."""

    def reset(self) -> None: ...
    def diagnostics(self) -> dict[str, Any]: ...
```

`ActivitySignal` objects (from `ActivityInferenceModule`) are merged into `ActivityResult.active`
at step 5, alongside confirmed primitive activities. Composite activities in the result carry the
signal's confidence.

### §7.4 IActivityDetector

```python
# runtime/plugin_contracts.py

class IActivityDetector(Protocol):
    @property
    def activity_name(self) -> str:
        """Unique activity name. Used as Activity.name."""
        ...

    @property
    def room_id(self) -> str | None:
        """Room scope, or None for house-level."""
        ...

    @property
    def candidate_period_s(self) -> float:
        """Seconds condition must hold before activity is confirmed."""
        ...

    @property
    def grace_period_s(self) -> float:
        """Seconds activity remains active after condition disappears."""
        ...

    def detect(
        self,
        observation: NormalizedObservation,
        canonical_state: CanonicalState,
    ) -> ActivityDetection | None:
        """
        Return ActivityDetection if the activity condition is currently met,
        None otherwise. Synchronous, I/O-free, O(1).
        """
        ...

@dataclass(frozen=True)
class ActivityDetection:
    activity_name: str
    confidence: float = 1.0
    room_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
```

### §7.5 Hysteresis State Machine

Each registered `IActivityDetector` has independent per-cycle hysteresis state:

```python
@dataclass
class ActivityHysteresisState:
    activity_name: str
    phase: Literal["absent", "candidate", "active", "grace"]
    phase_since_ts: float   # monotonic; time of last phase transition
    duration_s: float       # cumulative time in "active" phase (current session)
    context: dict[str, Any] # from last ActivityDetection
```

Per-cycle transition logic (run by `ActivityDomain.evaluate()`):

```
detection = detector.detect(observation, canonical_state)
now = monotonic()

match state.phase:
    case "absent":
        if detection:
            state.phase = "candidate"
            state.phase_since_ts = now
            state.context = detection.context

    case "candidate":
        if not detection:
            state.phase = "absent"        # false start — reset
        elif (now - state.phase_since_ts) >= detector.candidate_period_s:
            state.phase = "active"
            state.phase_since_ts = now
            state.duration_s = 0.0
            emit HeimaEvent(type="activity.started", activity_name=..., room_id=...)

    case "active":
        if detection:
            state.duration_s += now - state.phase_since_ts
            state.phase_since_ts = now
            state.context = detection.context
        else:
            state.phase = "grace"
            state.phase_since_ts = now

    case "grace":
        if detection:
            state.phase = "active"        # signal returned — stay active
            state.phase_since_ts = now
        elif (now - state.phase_since_ts) >= detector.grace_period_s:
            state.phase = "absent"
            emit HeimaEvent(type="activity.ended", activity_name=..., duration_s=...)
```

Activities in phase `"active"` appear in `ActivityResult.active`.
Activities in phase `"candidate"` appear in `ActivityResult.candidates`.

### §7.6 Built-in Primitive Activity Taxonomy

All built-in detectors require entity bindings configured in the options flow
(section `activity_bindings`). An unbound detector is silently inactive.

| activity_name | Detection condition | candidate_s | grace_s | Required binding |
|---|---|---|---|---|
| `stove_on` | power_sensor > 200 W (configurable) | 5 | 30 | `stove_power_entity` |
| `oven_on` | power_sensor > 500 W (configurable) | 10 | 120 | `oven_power_entity` |
| `tv_active` | `media_player.state` in `{playing, paused}` OR power > 20 W | 10 | 120 | `tv_entity` |
| `pc_active` | power_sensor > 50 W sustained (configurable) | 30 | 60 | `pc_power_entity` |
| `shower_running` | humidity_sensor > threshold AND rate_of_change > 0 | 60 | 300 | `bathroom_humidity_entity` |
| `washing_machine_running` | power_sensor > 200 W OR appliance state = on | 60 | 300 | `washing_machine_entity` |
| `dishwasher_running` | power_sensor > 200 W OR appliance state = on | 60 | 300 | `dishwasher_entity` |

Thresholds are configurable under `options["activity_bindings"][activity_name]`. Defaults above
are conservative and suitable for European households.

### §7.7 Composite Activities and ActivityProposal

Composite activities are **not hardcoded**. They are discovered offline by `ActivityAnalyzer`
(§8) and surfaced as `ActivityProposal` objects for user approval. Until approved, no composite
activity is emitted.

After approval, `ActivityInferenceModule` starts emitting `ActivitySignal` for the pattern each
cycle it is detected (§10.5). The user sees the activity name in diagnostics and can deactivate
it from the options flow.

```python
@dataclass
class ActivityProposal:
    proposal_type: str = "activity_discovered"
    activity_name: str                   # auto-generated slug (e.g. "movie_night")
    primitive_pattern: frozenset[str]    # set of primitive activity names that co-occur
    context_conditions: dict[str, Any]   # e.g. {"hour_range": [20, 24], "room_id": "living_room"}
    occurrence_count: int
    confidence: float
    representative_ts: list[str]         # ISO-8601 timestamps of example occurrences
```

`ActivityProposal` flows through the existing `ProposalEngine` (same review/approval surface
as `ReactionProposal`). Accepted proposals are stored in `ApprovalStore` and loaded by
`ActivityInferenceModule` at startup.

### §7.8 CanonicalState Keys

`ActivityDomain` writes to `CanonicalState` under the `activity.*` namespace:

| Key | Type | Description |
|---|---|---|
| `activity.active_names` | `list[str]` | Names of currently active activities (primitive + composite) |
| `activity.candidate_names` | `list[str]` | Names of activities in candidate window |
| `activity.last_started` | `str` | ISO-8601 timestamp of most recent activity.started event |

These keys are available to all downstream domains and plugins via `canonical_state.get("activity.active_names")`.

---

## §8 IBehaviorAnalyzer and FindingRouter

### §8.1 BehaviorFinding

```python
@dataclass
class BehaviorFinding:
    kind: Literal["pattern", "activity", "anomaly", "correlation"]
    analyzer_id: str
    description: str
    confidence: float
    payload: ReactionProposal | ActivityProposal | AnomalySignal | InferenceSignal
```

- `kind="pattern"` → payload is `ReactionProposal` → routed to `ProposalEngine`
- `kind="activity"` → payload is `ActivityProposal` → routed to `ProposalEngine` (new kind)
- `kind="anomaly"` → payload is `AnomalySignal` → routed to `AnomalyEngine`
- `kind="correlation"` → payload is `InferenceSignal` → routed to `InferenceEngine`

### §8.2 IBehaviorAnalyzer Protocol

```python
class IBehaviorAnalyzer(Protocol):
    @property
    def analyzer_id(self) -> str: ...

    async def analyze(
        self,
        event_store: EventStore,
        snapshot_store: SnapshotStore,
    ) -> list[BehaviorFinding]:
        """
        Offline analysis. Called every 6h. May use async I/O freely.
        Must not mutate EventStore or SnapshotStore. Returns [] on no findings; never raises.
        """
```

### §8.3 FindingRouter

```python
class FindingRouter:
    def route(self, findings: list[BehaviorFinding]) -> None:
        for f in findings:
            match f.kind:
                case "pattern":
                    self._proposal_engine.submit(f.payload)
                case "activity":
                    self._proposal_engine.submit(f.payload)   # same engine, different proposal_type
                case "anomaly":
                    self._anomaly_engine.submit_statistical(f.payload)
                case "correlation":
                    self._inference_engine.submit_correlation(f.payload)
```

### §8.4 Built-in Analyzers

| Analyzer | kind | What it detects | Min support |
|---|---|---|---|
| `PresencePatternAnalyzer` | `pattern` | Arrival/departure time patterns per weekday | 7 events/weekday |
| `HeatingPatternAnalyzer` | `pattern` | Preferred setpoints per house_state | 10 events/state |
| `ActivityAnalyzer` | `activity` | Co-occurring primitive activity patterns → composite activity proposals | 10 co-occurrences |
| `AnomalyAnalyzer` | `anomaly` | Statistical deviations: unusual arrival time, heating outlier | 10 events |
| `CorrelationAnalyzer` | `correlation` | Multi-signal correlations: room pattern → house_state | 15 snapshots/pattern |

`ActivityAnalyzer` reads `HouseSnapshot.detected_activities` to find recurring patterns.
Min support: 10 distinct occurrences of the same primitive co-occurrence pattern, across at least
3 different days. Proposals include an auto-generated `activity_name` (slugified description) that
the user can rename before accepting.

---

## §9 IInvariantCheck

### §9.1 Concept

`IInvariantCheck` runs synchronously every cycle after all domains have computed and before Apply.
It checks structural constraints using only the current `DecisionSnapshot` and `DomainResultBag`.
It must never read `EventStore` or `SnapshotStore`.

| | `IInvariantCheck` | `IBehaviorAnalyzer` |
|---|---|---|
| When | Every cycle (sync) | Every 6h (async) |
| Input | Current snapshot + domain results | EventStore + SnapshotStore |
| Nature | Structural (binary) | Statistical / behavioral (probabilistic) |
| Cost | O(1) | O(N) |
| Output | `InvariantViolation` (immediate) | `BehaviorFinding` (routed) |

### §9.2 IInvariantCheck Protocol

```python
class IInvariantCheck(Protocol):
    @property
    def check_id(self) -> str: ...

    def check(
        self,
        snapshot: DecisionSnapshot,
        domain_results: DomainResultBag,
    ) -> InvariantViolation | None:
        """Synchronous. Must complete in < 0.5 ms — no I/O, no heavy compute."""
```

### §9.3 InvariantViolation

```python
@dataclass(frozen=True)
class InvariantViolation:
    check_id: str
    severity: Literal["info", "warning", "critical"]
    anomaly_type: str
    description: str
    context: dict[str, Any]
```

Immediately converted to `HeimaEvent(type=f"anomaly.{anomaly_type}")` with debounce per check_id.

### §9.4 Built-in Invariant Checks

| check_id | Trigger | severity | Default debounce_s |
|---|---|---|---|
| `presence_without_occupancy` | `anyone_home=True` AND no occupied rooms AND house has sensorized rooms | `warning` | 300 |
| `security_presence_mismatch` | `security_intent="armed_away"` AND `anyone_home=True` | `critical` | 60 |
| `heating_home_empty` | Heating active AND `anyone_home=False` AND `house_state="away"` > threshold | `warning` | 600 |
| `sensor_stuck` | Presence/occupancy sensor unchanged > threshold | `info` | 3600 |

### §9.5 Debounce State Machine

Per-check state: `first_seen_ts`, `last_emitted_ts`, `is_active`. Condition must hold for
`debounce_s` before emission. Re-emits every `re_emit_interval_s` (default 3600 s) if persistent.
Emits `anomaly.resolved` on condition clearing.

### §9.6 Configuration

| Key | Type | Default |
|---|---|---|
| `anomaly_enabled` | bool | `true` |
| `anomaly_sensor_stuck_threshold_s` | int | `86400` |
| `anomaly_heating_empty_threshold_s` | int | `1800` |
| `anomaly_notify_on_info` | bool | `false` |
| `anomaly_re_emit_interval_s` | int | `3600` |

---

## §10 InferenceEngine v2

### §10.1 HouseSnapshot

Unit of observation written on-change to `SnapshotStore`.

```python
@dataclass(frozen=True)
class HouseSnapshot:
    ts: str                               # ISO-8601 UTC
    weekday: int                          # 0=Monday … 6=Sunday
    minute_of_day: int                    # 0–1439 local time

    # PeopleDomain output
    anyone_home: bool
    named_present: tuple[str, ...]        # sorted person slugs

    # OccupancyDomain output
    room_occupancy: dict[str, bool]       # room_id → occupied

    # ActivityDomain output — [v2 new]
    detected_activities: tuple[str, ...]  # sorted names of active activities (primitive + composite)

    # HouseStateDomain output
    house_state: str

    # HeatingDomain output
    heating_setpoint: float | None

    # LightingDomain output
    lighting_scenes: dict[str, str]       # room_id → scene name applied

    # SecurityDomain output
    security_armed: bool
```

Written on-change only. Typical household: 50–200 records/day.
`SnapshotStore`: max 10,000 records, 90-day TTL, persisted via HA `Store`.

### §10.2 InferenceContext

Read-only view passed to `ILearningModule.infer()` each cycle.

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
    previous_activity_names: tuple[str, ...]   # [v2 new] from CanonicalState activity.active_names
```

`previous_activity_names` is populated from `CanonicalState.get("activity.active_names", [])`.
This means `ActivityInferenceModule.infer()` uses the previous cycle's confirmed activities
as features — one-cycle lag is acceptable for composite pattern inference.

### §10.3 InferenceSignal Hierarchy

```python
class Importance(IntEnum):
    OBSERVE = 0   # logged only; never applied in domain resolution
    SUGGEST = 1   # applied only when no hard signal is active
    ASSERT  = 2   # soft override; domain still decides (reserved, not used in v2)

@dataclass(frozen=True)
class InferenceSignal:
    source_id: str
    confidence: float        # 0.0–1.0
    importance: Importance
    ttl_s: int
    label: str               # human-readable reason (diagnostics)

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
class ActivitySignal(InferenceSignal):    # [v2 new]
    activity_name: str
    room_id: str | None
    context: dict[str, Any] = field(default_factory=dict)

@dataclass(frozen=True)
class OccupancySignal(InferenceSignal):
    room_id: str
    predicted_occupied: bool    # stub; not applied in v2
```

`ActivitySignal` is consumed by `ActivityDomain.evaluate()` at step 5 (§7.3): each signal with
`confidence >= 0.60` and `importance >= SUGGEST` is merged into `ActivityResult.active` as a
composite activity.

### §10.4 ILearningModule Contract

```python
class ILearningModule(Protocol):
    @property
    def module_id(self) -> str: ...

    async def analyze(self, store: SnapshotStore) -> None:
        """Offline phase. Reads snapshot history; updates internal model. Called every 6h."""

    def infer(self, context: InferenceContext) -> list[InferenceSignal]:
        """Online phase. Synchronous. Must complete in < 1 ms. Returns [] before first analyze()."""

    def diagnostics(self) -> dict[str, Any]: ...
```

### §10.5 ActivityInferenceModule

`ActivityInferenceModule` is a built-in `ILearningModule` that emits `ActivitySignal` for
user-approved composite activity patterns.

**Model:**
```python
# For each approved ActivityProposal p:
#   pattern_key = frozenset(p.primitive_pattern)
#   context_key = hash of (hour_range, room_id, weekday_filter)
#   counts[(pattern_key, context_key)] = int   # occurrences
#   total[pattern_key] = int
```

**analyze():**
```
For each snapshot in store:
  active_set = frozenset(snapshot.detected_activities)
  for approved_proposal in approval_store.get_approved("activity_discovered"):
    if approved_proposal.primitive_pattern ⊆ active_set:
      if context_matches(snapshot, approved_proposal.context_conditions):
        counts[(pattern_key, context_key)] += 1
        total[pattern_key] += 1
```

**infer():**
```
current_set = frozenset(context.previous_activity_names)
for approved_proposal in approval_store.get_approved("activity_discovered"):
  if approved_proposal.primitive_pattern ⊆ current_set:
    if context_matches_now(context, approved_proposal.context_conditions):
      p = counts[(pk, ck)] / total[pk]   # 0 if unseen
      if p >= 0.60 and support >= 10:
        emit ActivitySignal(
          activity_name=approved_proposal.activity_name,
          room_id=approved_proposal.context_conditions.get("room_id"),
          confidence=p,
          importance=SUGGEST,
          ttl_s=600,
        )
```

Before any `ActivityProposal` is approved, `ActivityInferenceModule.infer()` returns `[]`.

### §10.6 Built-in Learning Modules

| Module | What it learns | Signal emitted | Min support |
|---|---|---|---|
| `WeekdayStateModule` | `P(house_state \| weekday, hour_bucket)` | `HouseStateSignal` | 10 snapshots/slot |
| `RoomStateCorrelationModule` | `P(house_state \| occupied_room_pattern)` | `HouseStateSignal` | 15 snapshots/pattern |
| `HeatingPreferenceModule` | `preferred_setpoint[house_state]` | `HeatingSignal` | 10 snapshots/state |
| `LightingPatternModule` | `P(scene \| room_id, house_state, hour_bucket)` | `LightingSignal` | 8 snapshots/slot |
| `HouseStateInferenceModule` | `P(house_state \| weekday, hour, rooms, anyone_home)` | `HouseStateSignal` | 20 snapshots/context |
| `ActivityInferenceModule` | `P(composite_activity \| primitive_pattern, context)` | `ActivitySignal` | 10 occurrences/pattern |

### §10.7 SignalRouter

Groups signals by subclass type. Filters expired signals. Sorts each bucket by confidence desc.
Returns `dict[type, list[InferenceSignal]]`.

**Conflict resolution:** highest confidence wins. Tie-break: most conservative `Importance`. Log
`WARNING` when ≥ 2 signals in the same bucket have `confidence >= 0.60` and different predicted
values.

### §10.8 Domain Signal Consumption Policy

| Domain | Signal type accepted | Condition for use | Min confidence |
|---|---|---|---|
| `ActivityDomain` | `ActivitySignal` | Approved composite activity; no hard primitive already covering same name | 0.60 |
| `HouseStateDomain` | `HouseStateSignal` | No definitive hard signal (no override, no unambiguous presence, no vacation) | 0.60 |
| `HeatingPlugin` | `HeatingSignal` | `apply_allowed=True` AND `target_temperature is None` AND no manual override | 0.55 |
| `LightingPlugin` | `LightingSignal` | No explicit scene for current house_state AND `manual_hold=False` | 0.65 |
| `SecurityPlugin` | — | Not applicable in v2 | — |
| `OccupancyDomain` | `OccupancySignal` | Stub — accepted in signature; not applied in v2 | n/a |

Signals never override: active user overrides, explicit config values, or safety guards.

### §10.9 House State Learning and User Approval

`HouseStateInferenceModule` learns `P(house_state | weekday, hour_bucket, occupied_rooms,
anyone_home)`. First application triggers a `ReactionProposal`. While pending: applied
transiently. After acceptance: applied silently. After rejection: computed but not consumed;
no re-proposal for the same `(context_key_hash, predicted_state)` pair
(`ApprovalStore`, persisted across restarts).

Confidence model: `confidence = probability × min(1.0, support / MIN_SUPPORT)`.

| confidence range | Behavior |
|---|---|
| < 0.40 | Not emitted |
| 0.40–0.60 | Emitted as `OBSERVE` |
| 0.60–0.80 | Emitted as `SUGGEST` |
| > 0.80 | Applied; may generate auto-apply proposal |

---

## §11 Event-Driven Trigger

### §11.1 Model

The evaluation cycle is triggered by **meaningful state changes** in the home. The periodic timer
is a fallback, not the primary trigger. Time is a contextual dimension for interpreting events,
not a cause.

Two trigger sources coexist:

| Source | When | Debounce |
|---|---|---|
| HA `state_changed` on registered signal entities | Entity state changes | Per-class (§11.2) |
| Periodic fallback | Always | 300 s |

The coordinator maintains a `_eval_pending: bool` flag. Both trigger sources set it to `True` and
schedule a debounced call to `async_evaluate()`. Concurrent triggers within the debounce window
are collapsed into a single evaluation.

### §11.2 Signal Entity Classes

| Class | Entity patterns | Debounce | Rationale |
|---|---|---|---|
| `presence` | `device_tracker.*`, `person.*` | 5 s | Group simultaneous device updates |
| `motion` | `binary_sensor.*motion*`, `binary_sensor.*occupancy*` | 3 s | Brief bursts |
| `door_window` | `binary_sensor.*door*`, `binary_sensor.*window*`, `binary_sensor.*contact*` | 2 s | Edge detection |
| `power_threshold` | `sensor.*power*`, `sensor.*energy*` — only on configured threshold crossings | 5 s | Avoids continuous noise |
| `calendar` | `calendar.*` | 0 s | Calendar transitions are semantically exact |
| `override` | `heima.set_mode` service call | 0 s | User intent is immediate |
| `weather` | Configured weather entity | 10 s | Slow-changing; coarse trigger |

Environmental sensors (lux, temperature, humidity, CO₂) do **not** trigger evaluations. They are
read passively from `NormalizedObservation` on each cycle. Continuous small changes in ambient
sensors should not flood the eval pipeline.

For `power_threshold`: the coordinator tracks the last-evaluated value per entity and only
triggers on crossing a configured threshold (e.g., stove from < 200 W to > 200 W), not on every
watt change.

### §11.3 Debounce Implementation

```python
# coordinator.py (simplified)

def _on_state_changed(self, event: Event) -> None:
    entity_id = event.data["entity_id"]
    entity_class = self._classify_entity(entity_id)
    if entity_class is None:
        return
    debounce_s = DEBOUNCE_BY_CLASS[entity_class]
    if self._debounce_handles.get(entity_class):
        self._debounce_handles[entity_class].cancel()
    self._debounce_handles[entity_class] = self._hass.async_call_later(
        debounce_s, self._trigger_eval
    )

async def _trigger_eval(self, _now=None) -> None:
    if not self._eval_running:
        await self.async_evaluate()
```

`_eval_running` prevents re-entrant evaluation. If a trigger fires while evaluation is in
progress, it schedules a follow-up evaluation after the current one completes.

Entity classification uses a priority list: entities explicitly configured by the user
(in `options["signal_entities"]`) are classified first; HA domain pattern matching is the
fallback.

### §11.4 Periodic Fallback

The 300-second timer fires unconditionally and calls `async_evaluate()`. Its purpose:
- Time-of-day transitions not caused by any sensor change (sunset, schedule windows)
- Calendar events that fire when no other entity changes
- Slow environmental drift that doesn't cross power thresholds but changes context
- Recovery if a state_changed subscription is missed

The periodic fallback does NOT replace event-driven evaluation for presence/activity triggers.

### §11.5 Subscription Lifecycle

At `async_setup_entry()` the coordinator:
1. Subscribes to `EVENT_STATE_CHANGED` with `_on_state_changed` as listener.
2. Schedules the 300-second periodic fallback via `async_call_later` with recursive reschedule.

At `async_unload_entry()`:
1. Cancels all `_debounce_handles`.
2. Cancels the periodic fallback handle.
3. Removes the `EVENT_STATE_CHANGED` listener.

`_classify_entity()` is rebuilt when the options flow changes the `signal_entities` config.

---

## §12 OutcomeTracker

### §12.1 Concept

Closes the learn→act→verify loop. When a `HeimaReaction` fires, registers a pending
verification. On each subsequent cycle, checks whether the predicted event materialized within
the timeout window. Feeds `ILearningBackend` and triggers degradation proposals.

### §12.2 Data Models

```python
@dataclass
class PendingVerification:
    reaction_id: str
    expected_event_type: str
    expected_within_s: float
    fired_at_ts: float
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

### §12.3 Timeout Policy

| Reaction type | Default `expected_within_s` |
|---|---|
| `PresencePatternReaction` | 1800 |
| `ConsecutiveStateReaction` | 600 |
| Custom reactions | 900 (fallback to `outcome_spec.timeout_s`) |

### §12.4 Degradation Proposal

After K=5 consecutive negative outcomes, `OutcomeTracker` submits a `ReactionProposal` to
`ProposalEngine`. At most once per reaction until user accepts or rejects.

---

## §13 House State Learning

Implemented as `HouseStateInferenceModule` (§10.6). Summary:
- Learns `P(house_state | weekday, hour_bucket, occupied_rooms, anyone_home)`.
- Emits `HouseStateSignal(importance=SUGGEST)` when confidence ≥ 0.60.
- `HouseStateDomain` consumes only when no definitive hard input is active.
- First application triggers a `ReactionProposal`; silent after approval.
- `ApprovalStore` persists decisions: `STORAGE_KEY = "heima_inference_approvals"`.
- Rejection is permanent per `(context_key_hash, predicted_state)` until cleared.

---

## §14 Implementation Phases

### Phase A — Plugin Framework

**Unlocks:** declarative DAG, plugin registration, built-in plugins as IDomainPlugin.
**Dependencies:** none (refactor of existing code).

| Deliverable | File(s) |
|---|---|
| `IDomainPlugin`, `DomainResultBag`, `IOptionsSchemaProvider` | `runtime/plugin_contracts.py` |
| `resolve_dag()` with cycle/missing-dep detection | `runtime/dag.py` |
| Engine plugin registration: `register_plugin()`, `finalize_dag()` | `runtime/engine.py` |
| Migrate `LightingDomain` → `LightingPlugin` | `runtime/domains/lighting.py` |
| Migrate `HeatingDomain` → `HeatingPlugin` | `runtime/domains/heating.py` |
| Migrate `SecurityDomain` → `SecurityPlugin` | `runtime/domains/security.py` |
| Coordinator: register plugins, `finalize_dag()` | `coordinator.py` |
| All existing tests green; DAG cycle detection tests | `tests/` |

### Phase B — IBehaviorAnalyzer + FindingRouter

**Unlocks:** unified behavior analysis interface, AnomalyEngine, CorrelationAnalyzer.
**Dependencies:** Phase A.

| Deliverable | File(s) |
|---|---|
| `IBehaviorAnalyzer`, `BehaviorFinding`, `AnomalySignal` | `runtime/plugin_contracts.py` |
| `FindingRouter` (extended for `"activity"` kind) | `runtime/finding_router.py` |
| Migrate `PresencePatternAnalyzer`, `HeatingPatternAnalyzer` | `runtime/analyzers/` |
| New: `AnomalyAnalyzer`, `CorrelationAnalyzer` | `runtime/analyzers/` |
| Coordinator: register analyzers, wire `FindingRouter` | `coordinator.py` |

### Phase C — IInvariantCheck

**Unlocks:** per-cycle structural constraint layer.
**Dependencies:** Phase A.

| Deliverable | File(s) |
|---|---|
| `IInvariantCheck`, `InvariantViolation`, `InvariantCheckState` | `runtime/plugin_contracts.py`, `runtime/invariant_check.py` |
| Engine invariant check loop | `runtime/engine.py` |
| Built-in checks: `PresenceWithoutOccupancy`, `SecurityPresenceMismatch`, `HeatingHomeEmpty`, `SensorStuck` | `runtime/invariants/` |
| Tests: ≥ 1 per check, debounce behavior, resolution event | `tests/invariants/` |

### Phase D — InferenceEngine v2 (base)

**Unlocks:** SnapshotStore, basic learning modules, per-cycle signal collection.
**Dependencies:** Phase A.

| Deliverable | File(s) |
|---|---|
| `ILearningModule`, `InferenceContext`, `InferenceSignal` hierarchy (including `ActivitySignal`) | `runtime/inference/` |
| `SnapshotStore` with `detected_activities` field | `runtime/inference/snapshot_store.py` |
| `SignalRouter` | `runtime/inference/router.py` |
| `WeekdayStateModule`, `HeatingPreferenceModule` | `runtime/inference/modules/` |
| Engine: `_collect_signals()`, `_record_snapshot_if_changed()` | `runtime/engine.py` |
| Domain plugins: `compute(signals=...)` signature update | `runtime/domains/*.py` |
| `RoomStateCorrelationModule`, `LightingPatternModule` | Phase D2 (deferred) |

### Phase E — OutcomeTracker + Feedback Loop

**Unlocks:** act→verify loop, degradation proposals.
**Dependencies:** Phase D.

| Deliverable | File(s) |
|---|---|
| `OutcomeTracker`, `PendingVerification`, `OutcomeRecord` | `runtime/outcome_tracker.py` |
| `HeimaReaction.outcome_spec` | `runtime/reactions/base.py` |
| `StatsLearningBackend` | `runtime/learning_backend.py` |
| Engine: `check_pending()` after Apply | `runtime/engine.py` |
| Tests: positive/negative outcome, degradation trigger | `tests/outcome_tracker/` |

### Phase F — House State Learning

**Unlocks:** `HouseStateInferenceModule`, `ApprovalStore`, user-approval gate.
**Dependencies:** Phases D and E.

| Deliverable | File(s) |
|---|---|
| `HouseStateInferenceModule` | `runtime/inference/modules/house_state_inference.py` |
| `ApprovalStore` | `runtime/inference/approval_store.py` |
| Approval gate in `HouseStateDomain.evaluate()` | `runtime/domains/house_state.py` |
| Options Flow: `house_state_learned_context` proposal type | `config_flow/` |

### Phase G — ActivityDomain

**Unlocks:** primitive activity detection, hysteresis, `ActivityResult` in DAG.
**Dependencies:** Phase A (uses `DomainResultBag`), Phase D (writes `detected_activities` to `HouseSnapshot`).

| Deliverable | File(s) |
|---|---|
| `Activity`, `ActivityResult`, `ActivityDetection`, `ActivityHysteresisState` | `runtime/domains/activity_domain.py` |
| `IActivityDetector` Protocol | `runtime/plugin_contracts.py` |
| `ActivityDomain` with hysteresis state machine | `runtime/domains/activity_domain.py` |
| Built-in detectors: `StoveOnDetector`, `OvenOnDetector`, `TvActiveDetector`, `PcActiveDetector`, `ShowerRunningDetector`, `WashingMachineDetector`, `DishwasherDetector` | `runtime/activity_detectors/` |
| Engine: insert `ActivityDomain` in core evaluation order | `runtime/engine.py` |
| `activity_bindings` section in options flow | `config_flow/` |
| `activity.*` keys in `CanonicalState` | `runtime/domains/activity_domain.py` |
| `InferenceContext.previous_activity_names` populated from CanonicalState | `runtime/engine.py` |
| `HouseSnapshot.detected_activities` populated from `ActivityResult` | `runtime/inference/snapshot_store.py` |
| Tests: hysteresis transitions, candidate/grace, event emission | `tests/activity/` |

### Phase H — Activity Inference and Learning

**Unlocks:** composite activity discovery, `ActivityProposal`, `ActivityInferenceModule`.
**Dependencies:** Phases D, F, and G.

| Deliverable | File(s) |
|---|---|
| `ActivityProposal` dataclass | `runtime/proposal_engine.py` |
| `ActivityAnalyzer(IBehaviorAnalyzer)` | `runtime/analyzers/activity.py` |
| `FindingRouter`: handle `kind="activity"` | `runtime/finding_router.py` |
| `ActivityInferenceModule(ILearningModule)` | `runtime/inference/modules/activity_inference.py` |
| `ApprovalStore`: support `"activity_discovered"` proposal type | `runtime/inference/approval_store.py` |
| Options Flow: `activity_discovered` proposal review surface | `config_flow/` |
| `ActivityDomain.evaluate()`: consume `ActivitySignal` (step 5) | `runtime/domains/activity_domain.py` |
| Tests: ActivityAnalyzer min-support, ActivityInferenceModule infer, signal merge | `tests/activity/` |

### Phase I — Event-Driven Trigger

**Unlocks:** HA `state_changed`-driven evaluation, per-class debounce, reduced periodic interval.
**Dependencies:** Phase G (power threshold detection depends on activity binding config).

| Deliverable | File(s) |
|---|---|
| `_on_state_changed()` listener with entity classification | `coordinator.py` |
| `_classify_entity()` with pattern matching + explicit config | `coordinator.py` |
| Per-class debounce handles | `coordinator.py` |
| `_eval_running` guard against re-entrant evaluation | `coordinator.py` |
| Periodic fallback: 300 s (reduced from current interval) | `coordinator.py` |
| Power threshold crossing detection | `coordinator.py` |
| `signal_entities` section in options flow (explicit entity → class mapping) | `config_flow/` |
| Tests: debounce batching, concurrent trigger collapse, eval guard | `tests/coordinator/` |

---

## §15 File Structure

### New files

| File | Purpose |
|---|---|
| `runtime/plugin_contracts.py` | All plugin interface Protocols + `IActivityDetector` |
| `runtime/dag.py` | `resolve_dag()`, cycle/missing-dep errors |
| `runtime/domain_result_bag.py` | `DomainResultBag` |
| `runtime/finding_router.py` | `FindingRouter` (handles `"activity"` kind) |
| `runtime/invariant_check.py` | `InvariantCheckState`, invariant loop helpers |
| `runtime/invariants/presence.py` | `PresenceWithoutOccupancy` |
| `runtime/invariants/security.py` | `SecurityPresenceMismatch` |
| `runtime/invariants/heating.py` | `HeatingHomeEmpty` |
| `runtime/invariants/sensor.py` | `SensorStuck` |
| `runtime/analyzers/anomaly.py` | `AnomalyAnalyzer` |
| `runtime/analyzers/correlation.py` | `CorrelationAnalyzer` |
| `runtime/analyzers/activity.py` | `ActivityAnalyzer` |
| `runtime/domains/activity_domain.py` | `ActivityDomain`, `Activity`, `ActivityResult`, `ActivityHysteresisState` |
| `runtime/activity_detectors/__init__.py` | Public exports |
| `runtime/activity_detectors/stove.py` | `StoveOnDetector` |
| `runtime/activity_detectors/oven.py` | `OvenOnDetector` |
| `runtime/activity_detectors/tv.py` | `TvActiveDetector` |
| `runtime/activity_detectors/pc.py` | `PcActiveDetector` |
| `runtime/activity_detectors/shower.py` | `ShowerRunningDetector` |
| `runtime/activity_detectors/washing.py` | `WashingMachineDetector` |
| `runtime/activity_detectors/dishwasher.py` | `DishwasherDetector` |
| `runtime/inference/__init__.py` | Public API exports |
| `runtime/inference/base.py` | `ILearningModule`, `HeimaLearningModule`, `InferenceContext` |
| `runtime/inference/signals.py` | `Importance`, `InferenceSignal` hierarchy + `ActivitySignal` |
| `runtime/inference/snapshot_store.py` | `HouseSnapshot`, `SnapshotStore` |
| `runtime/inference/router.py` | `SignalRouter` |
| `runtime/inference/approval_store.py` | `ApprovalStore` |
| `runtime/inference/modules/weekday_state.py` | `WeekdayStateModule` |
| `runtime/inference/modules/room_state.py` | `RoomStateCorrelationModule` |
| `runtime/inference/modules/heating_preference.py` | `HeatingPreferenceModule` |
| `runtime/inference/modules/lighting_pattern.py` | `LightingPatternModule` |
| `runtime/inference/modules/house_state_inference.py` | `HouseStateInferenceModule` |
| `runtime/inference/modules/activity_inference.py` | `ActivityInferenceModule` |
| `runtime/outcome_tracker.py` | `OutcomeTracker`, `PendingVerification`, `OutcomeRecord` |

### Modified files

| File | Change |
|---|---|
| `runtime/engine.py` | Plugin registration, DAG loop, `ActivityDomain` in core order, `_collect_signals()`, `_record_snapshot_if_changed()`, `_run_invariant_checks()`, `OutcomeTracker.check_pending()`, diagnostics |
| `runtime/domains/lighting.py` | `IDomainPlugin`; `compute(canonical_state, domain_results, signals)` |
| `runtime/domains/heating.py` | `IDomainPlugin`; `compute(canonical_state, domain_results, signals)` |
| `runtime/domains/security.py` | `IDomainPlugin`; remove internal mismatch detection |
| `runtime/domains/house_state.py` | Signal consumption + approval gate for `HouseStateSignal` |
| `runtime/domains/occupancy.py` | `compute(signals: list[OccupancySignal] = [])` stub |
| `runtime/analyzers/presence_pattern.py` | Migrate to `IBehaviorAnalyzer` |
| `runtime/analyzers/heating_pattern.py` | Migrate to `IBehaviorAnalyzer` |
| `runtime/reactions/base.py` | Add `outcome_spec` |
| `runtime/reactions/presence_pattern.py` | Populate `outcome_spec` |
| `runtime/reactions/consecutive_state.py` | Populate `outcome_spec` |
| `runtime/proposal_engine.py` | Add `ActivityProposal` support; `submit()` for tracker-triggered proposals |
| `coordinator.py` | All plugin/analyzer/module registrations; event-driven trigger; debounce |
| `config_flow/` | `activity_bindings`, `signal_entities`, `activity_discovered` proposal review |
| `translations/en.json`, `it.json` | Labels for new proposal types, activity names, anomaly notifications |

---

## §16 Design Constraints

| # | Constraint |
|---|---|
| 1 | **No ML libraries in built-in implementations.** All built-in analyzers and modules use pure Python stdlib. `IBehaviorAnalyzer` and `ILearningModule` are explicit plug-in boundaries for advanced third-party implementations. |
| 2 | **No blocking I/O on the hot path.** `infer()`, `detect()`, `_run_invariant_checks()`, `OutcomeTracker.check_pending()`, all hysteresis transitions — all synchronous and I/O-free. All hot-path writes to stores are fire-and-forget tasks. |
| 3 | **HA async patterns only.** `analyze()` and `async_append()` are coroutines. Off-cycle tasks use `async_call_later` with recursive reschedule. |
| 4 | **DAG is resolved once at startup.** `finalize_dag()` runs topological sort at registration time. Cycle and missing-dependency errors are fatal at integration load. |
| 5 | **CanonicalState remains generic key/value.** Plugin state namespaced by convention (`plugin_id.key`). |
| 6 | **Core domains are not plugins.** People, Occupancy, Activity, HouseState are concrete classes in fixed order. Core must be stable and minimal. |
| 7 | **IInvariantCheck must not read EventStore or SnapshotStore.** O(1) structural checks only. |
| 8 | **Signals are additive, never substitutes.** Domains with fully determined hard inputs ignore all `InferenceSignal` objects. Signals never override active user overrides or safety guards. |
| 9 | **All persistent stores use HA `Store`.** Keys: `heima_snapshots`, `heima_inference_approvals`. |
| 10 | **Phase A is behavior-preserving.** Migration of Lighting/Heating/Security to `IDomainPlugin` must not change any externally observable behavior. All existing tests must remain green. |
| 11 | **Time is a contextual dimension, not a trigger.** Evaluation is triggered by state changes. The periodic fallback exists for completeness, not as the primary mechanism. Clock time appears only as a feature in `InferenceContext`, never as the cause of a domain decision. |
| 12 | **Activity.context is the sole forward-compatibility hook.** New per-activity metadata (person scope, intensity, device source) must go into `Activity.context` with a namespaced key. The `Activity` dataclass fields are frozen beyond v2.0. |
| 13 | **Composite activities are always user-approved.** `ActivityInferenceModule.infer()` returns `[]` until at least one `ActivityProposal` is accepted. The system never autonomously activates a composite activity without explicit user consent. |
| 14 | **Event-driven trigger is additive.** The `state_changed` subscription augments, never replaces, the CanonicalState/NormalizedObservation evaluation model. The engine receives no raw HA event payloads — it reads entity state from `hass.states` at eval time, as in v1. |
