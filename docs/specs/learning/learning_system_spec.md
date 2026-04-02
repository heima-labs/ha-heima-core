# Heima Learning System — Specification v1

**Status:** Active v1 learning contract
**Date:** 2026-03-30
**Last Verified Against Code:** 2026-03-30

---

## Normative precedence

This document defines the intended learning architecture, data contracts, and behavioral rules.

Interpretation rule:
- if implementation and spec diverge, the divergence must be resolved explicitly
- code is a reference implementation, not the source of truth

## Scope and non-goals

In scope:
- learning event model
- persistence contracts for learnable events and proposals
- analyzer lifecycle and proposal semantics
- proposal acceptance into executable reactions

Not a goal of this document:
- prescribing one exact internal module layout
- documenting every implementation detail of the current codebase
- replacing narrower domain specs where they define domain-specific actuation semantics

## 0. Architectural Rationale — Batch vs Continuous Learning

This section documents the architectural decisions on how Heima learns, justified by analysis of
production systems (Alexa Hunches, Google Home) and academic literature (CASAS dataset, MIT PlaceLab,
Association Rule Mining on IoT streams).

### 0.1 Decision: batch periodic learning, not continuous

**Heima uses batch periodic learning.** The `ProposalEngine` runs offline on a schedule (every 6h)
and reads the accumulated `EventStore`. It does **not** update its models incrementally on every
eval cycle.

**Reasons:**

| Problem with continuous learning | Impact on a home assistant |
|---|---|
| Catastrophic forgetting | A seasonal pattern (summer late arrivals) gets overwritten by autumn behavior |
| Instability from temporary deviations | One sick week at home should not cancel "always at office on Monday" |
| Premature proposals | A pattern seen only twice fires as a suggestion — false positive rate is very high |
| Computational cost on the hot eval path | The eval cycle must be deterministic and fast; pattern analysis is expensive |

Alexa Hunches uses deep device embeddings trained offline in batch on large cross-customer corpora,
with only lightweight per-device context updated online. Google Home Routines Suggestions (legacy)
used frequency-based batch analysis. The academic literature on CASAS (WSU) and MIT PlaceLab
consistently uses offline training on multi-week windows before making any predictions.

**Conclusion:** batch periodic is the right choice for Heima. It matches the temporal scale of home
routines (days/weeks), it is deterministic and debuggable, and it keeps the hot eval path clean.

### 0.2 Decision: observe always, analyze periodically

The observation layer runs on every evaluation cycle and writes to `EventStore`. This is the
**continuous** part.

The analysis layer (`IPatternAnalyzer` implementations) runs periodically and is the **batch** part.

This separation is part of the intended architecture:
- behaviors append learning events asynchronously
- analyzers run on an offline cadence and read accumulated events from storage

No analyzer code ever runs in `async_evaluate()`.

### 0.2.1 Learning system model

Heima has one learning system, not multiple competing learning subsystems.

That learning system consists of:
- one shared event substrate
- one shared proposal model
- one shared proposal acceptance and reaction rebuild pipeline
- multiple learning pattern plugins that learn different kinds of recurring behavior
- an explicit built-in registry that can enable or disable plugin families through configuration

Each learned behavior can also be described along two orthogonal semantic axes:
- **Trigger family** — what kind of recurring condition or context causes the behavior
- **Response family** — what kind of user behavior is replayed or proposed after the trigger

Examples:
- temporal trigger + lighting replay response
- room-signal threshold trigger + generic steps response
- room-signal threshold trigger + lighting replay response

Examples of learning pattern plugins:
- temporal room/light routine plugins
- room-scoped composite assist plugins
- preference-oriented plugins such as heating or arrival/preheat behavior

Normative rule:
- a new learning capability SHOULD be modeled first as a new learning pattern plugin inside the shared
  learning system
- it SHOULD become a separate subsystem only if it truly requires a different storage,
  proposal, or runtime execution model
- if a plugin family is admin-authorable, that capability SHOULD be declared by the plugin itself
  rather than by a separate universal builder
- `trigger family` and `response family` are the preferred conceptual tools for deciding whether a
  new behavior extends an existing plugin family or needs a different one

Bridge clarification before Strada 3:
- the learning side may already be plugin-family-driven while the reaction rebuild/review side is
  still partially centralized
- before major domain expansion, the reaction/plugin substrate SHOULD be brought to the same level
  of explicit ownership as the learning/plugin substrate

Bridge clarification before Strada 4:
- proposal lifecycle policy SHOULD also become plugin-owned
- a learning plugin SHOULD eventually own not only:
  - analyzer output
  - proposal types
  - admin-authored template exposure
  - presentation hooks
- but also:
  - logical identity strategy
  - follow-up slot strategy
  - fallback follow-up matching policy
  - minor-drift / suppress-follow-up policy

This avoids re-centralizing domain-specific lifecycle semantics inside `ProposalEngine` as more
domains become first-class.

Strada 4 direction:
- after lighting, `composite_room_assist` is the intended next domain-strong stream
- the goal is not to add many new templates immediately, but to make the existing composite domain:
  - more stable in proposal identity
  - clearer in proposal/review wording
  - more robust for future tuning
- this domain is also the intended bridge toward more complex cross-domain orchestration later,
  including future heating work
- the first composite slice SHOULD align learned and admin-authored proposal identity on the same
  room + primary-signal semantics before broader tuning work
- proposal quality gates for composite SHOULD prefer ratio-based support thresholds where that is
  semantically clearer than absolute-only thresholds

Composite quality policy guidance:
- stable follow-up entity selection SHOULD be driven primarily by support ratio across confirmed
  episodes, with an optional minimum absolute episode floor as a guard
- optional corroboration signals SHOULD be promoted into the core proposal payload only when their
  support ratio is high enough to be considered structurally stable
- these thresholds SHOULD be modeled as a configurable analyzer policy rather than as scattered
  hardcoded values
- v1 does not require a polished UI for all such policy knobs, but the runtime/config model SHOULD
  allow them to be overridden from learning configuration
- if equivalent composite candidates emerge for the same logical slot during one analyzer pass,
  the analyzer SHOULD keep only one dominant candidate rather than surfacing multiple near-duplicates

### 0.3 Decision: minimum training window before emitting proposals

Based on the literature, a pattern is considered reliable only when it has been observed a sufficient
number of times across a sufficient time span. Producing proposals too early is worse than producing
none (false positives cause user distrust that is hard to recover from — Alexa research confirms this).

**Heima rules (apply to all analyzers):**

| Condition | Threshold | Rationale |
|---|---|---|
| Minimum occurrences per pattern key | ≥ 5 | ARM minimum support; used by `PresencePatternAnalyzer` |
| Minimum distinct weeks spanned | ≥ 2 | Prevents a single-week anomaly from triggering a proposal |
| Minimum confidence to surface proposal | ≥ 0.4 | `ProposalEngine.min_confidence` filter |
| Recommended observation period before first useful proposal | 3–4 weeks | Literature consensus (CASAS, MIT PlaceLab, industry) |

The `min_arrivals=5` in `PresencePatternAnalyzer` satisfies the occurrence threshold.
The week-span check is added for `LightingPatternAnalyzer` (see §P9) and should be retrofitted to
existing analyzers in a future iteration.

### 0.4 Decision: propose-then-confirm, never auto-execute

All patterns detected by analyzers surface as `ReactionProposal` objects that the user must
explicitly accept in the Options Flow. Execution never happens automatically on first detection.

This mirrors the universal pattern in mature systems:
- Alexa Hunches: phase 1 = verbal suggestion, phase 2 = Automatic Actions (opt-in)
- RL Shadow Mode (arxiv 2410.23419): agent acts only after reward of autonomous action exceeds
  the human controller baseline — a formal version of the same principle

In Heima terms: after the user accepts a proposal, the resulting `HeimaReaction` becomes active and
executes automatically. The user can always mute or delete it from the Reactions step.

### 0.5 Decision: source discrimination is mandatory for lighting (and heating)

Recording actions emitted by Heima itself as "user behavior" would create a positive feedback loop:
Heima learns to reinforce its own previous decisions, regardless of actual user preferences.

**Rule:** every recorder behavior MUST set `source` on the event.
- `source="heima"`: action was emitted by Heima's apply plan in this cycle.
- `source="user"`: action was detected from HA state changes not caused by Heima.

Analyzers MUST filter on `source="user"` when inferring user preferences.

`HeatingEvent` already has this field. `LightingEvent` adds it (see §P7).
`PresenceEvent` does not need it (presence is always a user action, Heima does not move people).
`HouseStateEvent` does not need it (transitions are system-level, not analyzed for user preference).

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

## 1.1 Capability Matrix (informative)

| Phase | Status | Notes |
|---|---|---|
| P1 EventStore | Implemented | `runtime/event_store.py` with persistence, TTL, cap, query |
| P1b EventRecorderBehavior | Implemented | `runtime/behaviors/event_recorder.py` |
| P2 PresencePatternAnalyzer | Implemented | `runtime/analyzers/presence.py` |
| P3 HeatingPatternAnalyzer | Implemented/Partial | preference path implemented; eco path depends on verified `house_state` away sessions |
| P4 ProposalEngine | Implemented | `runtime/proposal_engine.py`, periodic coordinator run |
| P5 Approval Flow | Implemented | Config flow step `proposals` accepts/rejects proposals |
| P6 Generalization | Partial | `IPatternAnalyzer` exists; ecosystem/process still RFC |
| P7 LightingEvent | Implemented | `HeimaEvent(event_type="lighting")` — unified EventStore; EventContext shared |
| P8 LightingRecorderBehavior | Implemented | `runtime/behaviors/lighting_recorder.py` |
| P9 LightingPatternAnalyzer | Implemented | `runtime/analyzers/lighting.py` |
| P10 Learning Config Flow | Implemented | `config_flow/_steps_learning.py` — outdoor_lux, temp, weather, signals |
| P11 Generic Signal Recorder | Implemented | `runtime/behaviors/signal_recorder.py` records `state_change` events for configured context entities |
| P12 Learning registry & family controls | Implemented | built-in `LearningPluginRegistry`, `enabled_plugin_families`, diagnostics reflect enabled/disabled families |
| P13 Admin-authored proposal path | Implemented/Partial | origin-aware proposal model, plugin-declared templates, first end-to-end flow for `lighting.scene_schedule.basic`, reaction provenance + diagnostics implemented |
| P14 Reaction plugin realization bridge | Implemented | reaction build/normalize ownership moved from engine core to explicit `ReactionPluginRegistry`; review/authoring presenter hooks reduce config-flow hardcoding |
| P15 Proposal lifecycle hook bridge | Implemented | `ProposalEngine` lifecycle policy moved from hardcoded `reaction_type` branches to plugin-owned lifecycle hooks |
| P16 Composite domain-strong stream | In progress | strengthen proposal quality, identity, tuning readiness, and bounded UX for the existing composite room-assist family before larger cross-domain domains |

---

## 2. Architecture Overview

```
HA Event Loop (hot path — eval cycle)
┌──────────────────────────────────────────────────────────┐
│  engine.async_evaluate()                                 │
│    ↓ on_snapshot()                                       │
│    EventRecorderBehavior / LightingRecorderBehavior /    │
│    HeatingRecorderBehavior / SignalRecorderBehavior      │
│                       ──── append() ──→ EventStore       │
│    (writes presence / house_state / heating / lighting / │
│     generic state_change events)                         │
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

**Normative architecture rules:**
- event writes must be asynchronous and must not stall the hot evaluation path
- analyzers run off-cycle and never inline in the hot evaluation path
- proposal generation is a coordinator-level concern, not a per-cycle decision concern
- the same persisted event substrate is shared by all analyzers

---

## 3. Data Models

### 3.0 EventContext — shared context snapshot

Every pattern event carries an `EventContext` that captures the state of the house at the moment
the event occurred. This enables analyzers to detect correlations between actions and context
(e.g., "lights dimmed when it was dark outside and house_state=relax").

```python
# runtime/event_store.py

@dataclass(frozen=True)
class EventContext:
    # --- Time (always present, derived from local datetime) ---
    weekday: int                          # 0=Monday … 6=Sunday
    minute_of_day: int                    # 0–1439 (local time)
    month: int                            # 1–12 (season proxy)

    # --- Aggregated house state (always present) ---
    house_state: str                      # e.g. "morning", "relax", "away"

    # --- Occupancy (always present, derived from PeopleResult) ---
    occupants_count: int
    occupied_rooms: tuple[str, ...]       # rooms with detected presence

    # --- External environment (None if sensor not configured) ---
    outdoor_lux: float | None             # luminosity — is it dark/light outside?
    outdoor_temp: float | None            # outdoor temperature
    weather_condition: str | None         # "sunny", "cloudy", "rainy", etc.

    # --- Strong signals (user-configured, max 10 entities) ---
    # Entities the user declares relevant for learning context.
    # Captured at event time as entity_id → state string.
    # Examples: projector, TV, alarm panel, music player.
    signals: dict[str, str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "weekday": self.weekday,
            "minute_of_day": self.minute_of_day,
            "month": self.month,
            "house_state": self.house_state,
            "occupants_count": self.occupants_count,
            "occupied_rooms": list(self.occupied_rooms),
            "outdoor_lux": self.outdoor_lux,
            "outdoor_temp": self.outdoor_temp,
            "weather_condition": self.weather_condition,
            "signals": dict(self.signals),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "EventContext":
        return cls(
            weekday=int(raw.get("weekday", 0)),
            minute_of_day=int(raw.get("minute_of_day", 0)),
            month=int(raw.get("month", 1)),
            house_state=str(raw.get("house_state", "")),
            occupants_count=int(raw.get("occupants_count", 0)),
            occupied_rooms=tuple(raw.get("occupied_rooms", [])),
            outdoor_lux=float(raw["outdoor_lux"]) if raw.get("outdoor_lux") is not None else None,
            outdoor_temp=float(raw["outdoor_temp"]) if raw.get("outdoor_temp") is not None else None,
            weather_condition=str(raw["weather_condition"]) if raw.get("weather_condition") else None,
            signals={str(k): str(v) for k, v in raw.get("signals", {}).items()},
        )
```

**Design constraints:**
- `signals` is bounded to 10 entries max (enforced by the recorder at construction time).
  More entities → diminishing returns for analysis, higher storage cost.
- `outdoor_lux`, `outdoor_temp`, `weather_condition` are `None` when the corresponding entity
  is not configured. Analyzers must handle `None` gracefully.
- `occupied_rooms` uses `tuple` (hashable) rather than `list` to preserve `frozen=True` semantics
  on the parent event dataclass.
- `signals` is a regular `dict` (same pattern as `HeatingEvent.env`); the reference is frozen even
  if the dict itself is technically mutable.

**Configuration** (new fields in integration options, `learning` sub-key):
```yaml
learning:
  outdoor_lux_entity: sensor.outdoor_illuminance   # optional
  outdoor_temp_entity: sensor.outdoor_temperature  # optional
  weather_entity: weather.home                     # optional
  context_signal_entities:                         # optional, max 10
    - media_player.projector
    - binary_sensor.tv_power
```

Normative source-selection rule:
- the learning system MUST treat room-scoped signals declared in `rooms[*].learning_sources` as the
  primary source set for room-aware learning
- `learning.context_signal_entities` MUST be treated as an additive global override set, not as
  the only source of learnable non-temporal signals
- the effective learning signal set is therefore:
  - room-scoped entities from `rooms[*].learning_sources`
  - union supported entities from `learning.context_signal_entities`
  - de-duplicated by entity id

Normative configuration rule:
- the room model SHOULD keep occupancy and learning inputs as separate room-level concepts
- the intended v1.1+ shape is:
  - `rooms[*].occupancy_sources` declares which entities participate in occupancy resolution
  - `rooms[*].learning_sources` declares which entities may be used as learnable trigger/context
    signals
- this is preferred over a mixed room-source model because it keeps user intent explicit and avoids
  coupling occupancy semantics to learning semantics

Normative signal-quality rule:
- learning plugins MUST prefer stable, normalized signals over raw noisy or semantically ambiguous
  inputs
- not every entity listed in `rooms[*].learning_sources` is automatically a good learning signal
- the runtime MAY filter room learning sources by supported domain / signal semantics before persisting
  `state_change` events

Recommended v1 interpretation:
- good default learning signals:
  - normalized `sensor.*` entities with stable numeric semantics
  - room-scoped `switch.*` entities that represent meaningful user follow-up actions
  - selected `binary_sensor.*` entities only when their semantics are explicit and stable
- poor default learning signals:
  - highly noisy raw motion pulses
  - redundant low-level transport entities
  - entities whose semantics are not normalized enough for repeatable inference

### 3.0.1 Trigger signals vs observed responses

Not every entity relevant to a room should be treated in the same way by the learning system.

The learning system distinguishes at least these roles:
- **trigger/context signal**
  - an entity observed to understand *when* a behavior tends to happen
  - examples:
    - room lux
    - room humidity
    - room temperature
    - room CO2
- **observed response**
  - an entity observed to understand *what the user did*
  - examples:
    - lights the user turned on
    - thermostat target the user changed
    - fan/switch the user activated

Normative rule:
- an entity MAY belong to the room model without automatically becoming a learnable trigger signal
- lights are the canonical example:
  - they are often a response family observed by lighting-oriented learners
  - they are not, by default, room trigger signals for composite sensor-based plugins

Product consequence:
- Heima can learn:
  - *when* the room became dark from lux-like trigger signals
  - *what* the user did from lighting response events
- this is not a contradiction; it is an intentional separation between trigger semantics and
  response semantics

**Migration from v1 events:**
Existing `PresenceEvent`, `HeatingEvent`, `HouseStateEvent` records on disk do not have an
`EventContext`. Deserialization handles this gracefully: if `"context"` key is absent, a minimal
`EventContext` is reconstructed from the top-level fields that existed previously (e.g., `weekday`,
`minute_of_day`, `house_state`), with all new fields set to `None` / empty defaults. Old records
remain queryable; they simply carry less context. No `STORAGE_VERSION` bump is required.

---

### 3.1 Pattern Events

All events embed an `EventContext` instead of duplicating contextual fields inline.
`HeatingEvent.env` is subsumed by `context.signals` + `context.outdoor_temp` (kept for now during
migration; will be removed once recorders are updated).

```python
# runtime/event_store.py

@dataclass(frozen=True)
class PresenceEvent:
    ts: str                                  # ISO-8601 UTC
    event_type: Literal["presence"]          # discriminator
    transition: Literal["arrive", "depart"]
    context: EventContext

@dataclass(frozen=True)
class HeatingEvent:
    ts: str
    event_type: Literal["heating"]
    temperature_set: float
    source: Literal["user", "heima"]
    context: EventContext
    # env kept temporarily for migration compatibility; deprecated

@dataclass(frozen=True)
class HouseStateEvent:
    ts: str
    event_type: Literal["house_state"]
    from_state: str
    to_state: str
    context: EventContext

@dataclass(frozen=True)
class LightingEvent:
    ts: str
    event_type: Literal["lighting"]
    room_id: str
    action: Literal["on", "off"]
    # Light state at action time (None if not available)
    scene: str | None
    brightness: int | None                   # 0–255
    color_temp_kelvin: int | None
    rgb_color: tuple[int, int, int] | None
    source: Literal["user", "heima"]
    context: EventContext

PatternEvent = PresenceEvent | HeatingEvent | HouseStateEvent | LightingEvent
```

**Key changes from v1:**
- `PresenceEvent`: `weekday` + `minute_of_day` removed from top level → live in `context`
- `HeatingEvent`: `house_state` removed from top level → lives in `context.house_state`
- `HouseStateEvent`: gains `context` (previously had none)
- `LightingEvent`: new type (see §P7), designed with `context` from the start
- All analyzers that previously accessed `event.weekday` etc. must now access `event.context.weekday`

### 3.2 ReactionProposal

```python
# runtime/analyzers/base.py

@dataclass
class ReactionProposal:
    proposal_id: str = field(default_factory=lambda: str(uuid4()))
    analyzer_id: str = ""
    origin: Literal["learned", "admin_authored"] = "learned"
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

Future extension point:
- a `ReactionProposal` MAY eventually expose multiple **acceptance modes**
- each acceptance mode would describe a different supported way to turn the same learned pattern
  into an executable reaction
- this is not yet part of the v1 persisted runtime contract; current proposals still have one
  effective acceptance path each

### 3.3 Statistical Algorithm Model

The v1 built-in analyzers use **pure descriptive statistics only** — no external libraries, no training phase, no model files.

#### PresencePatternAnalyzer — algorithm

```
Input: list[PresenceEvent] for one weekday, transition="arrive"
       n = len(arrivals)  (context.minute_of_day values)

Require: n ≥ MIN_ARRIVALS (default 5)

# Access via event.context.weekday and event.context.minute_of_day
samples = [e.context.minute_of_day for e in arrivals if e.context.weekday == weekday]

median = samples_sorted[n // 2]          # 50th percentile, O(n log n) sort
p25    = samples_sorted[n // 4]          # 25th percentile
p75    = samples_sorted[3 * n // 4]      # 75th percentile
IQR    = p75 - p25                       # interquartile range (minutes)

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
Input: list[HeatingEvent] where source="user", grouped by context.house_state
       n = len(temps)

Require: n ≥ 10

median = temps_sorted[n // 2]
spread = max(temps) - min(temps)        # full range, not IQR

# Confidence: 1.0 when all setpoints identical, 0.3 floor when spread≥5°C
confidence = max(0.3, 1.0 - spread / 5.0)

Output: ReactionProposal(reaction_type="heating_preference", confidence=confidence)
```

**Pattern A (eco opportunity):** event-count heuristic, no statistical fit. If `away_duration > 2h`
(inferred from `HouseStateEvent` transitions) and subsequent user setpoint raise > 1°C is observed
in ≥3 distinct sessions → emit proposal with fixed `confidence=0.7`.

#### Confidence interpretation

| confidence | Meaning |
|---|---|
| ≥ 0.8 | High regularity — proposal is ready to accept |
| 0.5–0.8 | Moderate regularity — worth reviewing |
| < 0.5 (floor 0.3) | Low regularity — informational only |

`ProposalEngine` may filter out proposals below a configurable `min_confidence` threshold (default 0.4).

---

## 4. Phase P1 — EventStore

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

### 6.1 Algorithm

```
For each weekday 0..6:
  arrivals = [e.context.minute_of_day for e in presence_events
              if e.transition=="arrive" and e.context.weekday==weekday]
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

Detects two patterns from `HeatingEvent` + `HouseStateEvent`:

**Pattern A — eco opportunity:**
`away` period > 2h followed by `home` where temperature was raised with `source="user"` → suggest explicit eco heating branch.

Implementation note:
- eco sessions are derived from real `house_state` transitions (`home -> away -> home`)
- accepted eco proposals now carry `eco_target_temperature`
- accepted heating proposals are rebuilt into `HeatingPreferenceReaction` / `HeatingEcoReaction` and are executable

**Pattern B — consistent temperature preference:**
```
For each house_state:
  temps = [e.temperature_set for e in heating_events
           if e.source == "user" and e.context.house_state == hs]
  if len(temps) < 10: skip
  median = sorted(temps)[len(temps)//2]
  spread = max(temps) - min(temps)
  confidence = max(0.3, 1.0 - spread / 5.0)
  → emit ReactionProposal(reaction_type="heating_preference")
```

**HeatingRecorderBehavior** (prerequisite): a `HeimaBehavior` that compares observed heating setpoints between consecutive snapshots. Source detection is based on the observed thermostat value matching a recent Heima-applied target; otherwise the event is treated as `source="user"`.

---

## 8. Phase P4 — ProposalEngine

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

When a new proposal from an analyzer matches an existing one (same analyzer-defined fingerprint):
- Status `"accepted"` or `"rejected"` → skip (do not re-surface)
- Status `"pending"` → update `confidence` + `updated_at` in-place

The runtime persists `ReactionProposal.fingerprint` and uses it as the primary dedup key. The fallback fingerprint remains coarse and exists only for backward compatibility with older stored proposals.

### 8.4 Sensor

After each analysis run, proposal state must be published to a runtime observability surface:
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
- Accept → persist the proposal as accepted and mark it non-pending
- Reject → persist the proposal as rejected and mark it non-pending

### 9.2 Acceptance → Configured Reaction

Acceptance writes the proposal's suggested reaction config into persisted reaction configuration.

Normative rule:
- accepting a proposal must produce enough persisted configuration to rebuild an executable
  reaction later, without depending on transient UI session state

### 9.3 Reaction instantiation from config

When persisted accepted proposals are rebuilt into runtime reactions:

Normative rebuild rule:
- persisted accepted proposals must rebuild into executable runtime reactions
- proposal types that are user-acceptible in the approval flow must not end up in an
  “accepted but non-executable” state
- rebuild semantics must depend only on persisted configuration and stable runtime inputs

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

Built-in Learning Pattern Plugins are registered by the learning orchestration layer through a
central built-in registry. Future domains may add their own plugins without changing the core
proposal substrate.

### 10.4 Learning Pattern Plugin contract

`IPatternAnalyzer` is the minimal protocol boundary behind a **Learning Pattern Plugin**.

A Learning Pattern Plugin is the product-level concept used to add one learnable family of recurring
behavior to the shared learning system.

Each plugin owns:
- the pattern semantics it recognizes
- the matching logic it applies to the shared event substrate
- the proposal types it emits
- the suggested reaction contract it targets after user acceptance

Minimum plugin metadata:
- `plugin_id`
- `analyzer_id`
- `plugin_family`
- emitted `proposal_types`
- supported `reaction_targets`
- `supports_admin_authored` (bool, default false)
- `admin_authored_templates` (optional, empty unless the family is authorable)

Where a `reaction_target` may be:
- a concrete `reaction_class`, or
- a user-completable reaction contract that becomes executable only after the user finishes
  proposal acceptance/configuration

The v1 built-in plugins (`PresencePatternAnalyzer`, `HeatingPatternAnalyzer`,
`LightingPatternAnalyzer`, room-scoped composite assist analyzers) use simple descriptive
statistics or deterministic matchers that require no external dependencies and produce predictable
results on small datasets.

This is a deliberate v1 constraint, **not** an architectural one. Any analyzer that satisfies the protocol can be dropped in without changing `ProposalEngine`, `EventStore`, or any other component:

| Analyzer tier | Examples | Drop-in viable? |
|---|---|---|
| v1 — descriptive stats | Median, IQR, range | ✅ (default) |
| v2 — robust statistics | Kernel density, DBSCAN clustering | ✅ |
| v3 — time-series | ARIMA, changepoint detection | ✅ |
| v4 — probabilistic | GMM, Bayesian online learning | ✅ |
| v5 — ML | scikit-learn, tflite, ONNX runtime | ✅ (requires HA add-on or venv with deps) |

**Rules for Learning Pattern Plugins:**
1. Must be async-safe: no blocking I/O inside `analyze()`.
2. Must not modify `EventStore` (read-only access).
3. Must return `list[ReactionProposal]` with `confidence` in [0.0, 1.0].
4. Should emit no more than ~10 proposals per run (ProposalEngine is not a feed).
5. May maintain internal state between calls (cache last run result, etc.).

Normative product rule:
- a plugin is the preferred unit of extension for new learnable pattern families
- multiple plugins may share helper matchers, confidence shaping logic, or proposal builders
- plugin identity MUST remain stable enough that proposals and diagnostics stay understandable
- the initial v1 registry MAY remain built-in only; dynamic third-party loading is not required
- the registry MAY be filtered by enabled plugin families from configuration; disabled families MUST
  not emit proposals in that runtime session

### 10.5 Admin-authored proposals

Admin-authored automations are not a separate execution model.
They are precompiled `ReactionProposal` artifacts emitted by plugins that explicitly declare
admin-authoring support.

The admin-authored path uses the same shared proposal/reaction substrate as learned proposals:
- same persisted proposal store
- same acceptance/rejection workflow
- same rebuild pipeline into executable reactions
- same diagnostics surface, with `origin = "admin_authored"`

What differs is provenance:
- learned proposals originate from observed behavior and batch analysis
- admin-authored proposals originate from a human request and a plugin-declared template

Normative rules:
- only plugins that declare `supports_admin_authored = true` MAY expose admin-authored templates
- admin-authored templates SHOULD be precompiled and bounded, not a universal free-form builder
- the `origin` field MUST remain visible in diagnostics and review UX
- follow-up tuning proposals for authored automations MUST preserve the same shared substrate and
  SHOULD keep enough provenance to relate the tuning proposal back to the authored origin

Lighting tuning clarification:
- when a tuning proposal targets an active `LightingScheduleReaction`, the proposal/review layer
  SHOULD support a structured diff over the active reaction rather than only generic follow-up text
- minimum diff categories for v1 lighting tuning:
  - schedule/time change
  - brightness change
  - color temperature change
  - entity-set change
- the follow-up review SHOULD show only the categories that actually differ between the active
  reaction config and the proposed config

Composite tuning clarification:
- when a tuning proposal targets an active composite room-assist reaction, the proposal/review
  layer SHOULD support a bounded structured diff over the active reaction rather than only generic
  follow-up wording
- minimum useful v1 composite tuning diff categories are:
  - primary threshold change
  - primary threshold mode change
  - primary signal entity-count change
  - corroboration threshold change, when a corroboration exists
  - corroboration threshold mode change, when a corroboration exists
  - corroboration entity-count change
  - actuation payload count change:
    - `steps` count for generic signal assist
    - `entity_steps` count for room lighting assist
- the follow-up review SHOULD show only the categories that actually differ between the active
  reaction config and the proposed config
- v1 composite tuning does not require a dense comparison UI; the bounded options-flow review is
  sufficient if it can render these categories clearly
- if future automation management requires dense queue browsing, history inspection, or
  side-by-side comparison, that SHOULD be introduced as a dedicated management surface rather than
  by overloading the bounded options flow
- the first domain-strong composite tuning coverage SHOULD include both:
  - `room_signal_assist`
  - `room_darkness_lighting_assist`
- these two families are sufficient for v1.x because they exercise both bounded actuation payloads:
  - `steps`
  - `entity_steps`

Composite runtime-confidence clarification:
- v1 composite confidence SHOULD not depend only on the raw count of confirmed episodes
- confidence SHOULD also reflect minimum evidence quality, especially:
  - `episodes_confirmed`
  - `weeks_observed`
  - corroboration consistency when relevant
- patterns that barely meet the minimum count/weeks gate SHOULD remain below the maximum confidence
  unless evidence is stronger than the floor
- composite follow-up suggestions SHOULD also support minor-drift suppression when the candidate:
  - targets the same logical identity slot
  - keeps the same primary/corroboration signal entity sets
  - keeps the same actuation payload size
  - changes thresholds only by a small amount
- this suppression is especially valuable for:
  - `room_signal_assist`
  - `room_darkness_lighting_assist`
- the thresholds that define “minor drift” SHOULD come from configurable composite lifecycle policy,
  not from hardcoded constants scattered in lifecycle hooks
- v1 does not require a polished UI for these knobs, but the runtime/config model SHOULD allow
  overrides from `learning` configuration in the same spirit as analyzer quality policy

Composite operability clarification:
- diagnostics SHOULD expose a composite-domain summary comparable in spirit to `lighting_summary`
- that summary SHOULD make it easy to answer:
  - how many composite reactions are active
  - how many composite proposals are pending
  - how many pending items are tuning vs discovery
  - which rooms and primary signals are currently represented
- diagnostics/audit examples for composite SHOULD prefer compact human labels aligned with proposal
  review wording, not only long narrative descriptions

Current v1 implementation notes:
- built-in plugin descriptors already declare:
  - `supports_admin_authored`
  - `admin_authored_templates`
- the registry may declare more authorable templates than the options flow currently exposes
- the first end-to-end implemented admin-authored template is:
  - `lighting.scene_schedule.basic`
- room-scoped composite templates are declared in plugin metadata but are not yet all exposed as
  dedicated authoring wizards

### 10.6 Learning observability and configured reaction provenance

The learning surface is now expected to expose three distinct diagnostic views:

1. plugin/family diagnostics
- plugin metadata
- enabled vs disabled families
- declared admin-authored capability and templates

2. proposal diagnostics
- pending / accepted / rejected proposals
- `origin`
- `identity_key`
- `last_observed_at`
- explainability and config summary

3. configured reaction diagnostics
- active configured reactions summarized by provenance
- at minimum:
  - `total`
  - `by_origin`
  - `by_author_kind`
  - `reaction_ids`

For lighting-heavy deployments, diagnostics SHOULD also expose a lighting-oriented summary view so
operators do not need to reconstruct lighting state manually from generic proposal and reaction
payloads.

Recommended v1 lighting summary fields:
- `configured_total`
- `configured_by_room`
- `configured_by_slot`
- `pending_total`
- `pending_tuning_total`
- `pending_discovery_total`
- `pending_by_room`
- `slot_collisions`

For lighting-specific operability in Strada 3:
- diagnostics SHOULD also expose small, stable pending examples separated by follow-up kind
- at minimum, a lighting summary MAY expose:
  - `pending_tuning_examples`
  - `pending_discovery_examples`
- examples SHOULD be lightweight and product-facing rather than raw internal payload dumps
- examples SHOULD prefer room / slot / confidence / concise label fields over full config bodies

Normative rule:
- when an accepted proposal is rebuilt into a configured reaction, provenance SHOULD remain attached
  so diagnostics can distinguish legacy/unspecified reactions from `learned` and `admin_authored`
  ones

---

---

## P7. LightingEvent — Detail

### P7.1 Field rationale

| Field | Why |
|---|---|
| `entity_id` | Granularità per entità: Heima impara quale specifica luce l'utente tocca, non solo la stanza |
| `room_id` | Contesto stanza per il grouping in scene candidate (fase 2 di P9) |
| `action` | Both "on" and "off" are learnable; going to bed at 23:00 is as valuable as waking at 07:00 |
| `scene` | When a named scene is activated, the proposal can replicate it exactly, not just "turn on" |
| `brightness` | Dim at 10% warm for cinema vs full brightness for cooking — same action, different intent |
| `color_temp_kelvin` | Warm (2700K) vs cool (5000K) is a strong behavioral signal for time-of-day and activity |
| `rgb_color` | Captures colored light settings (e.g., party, relax ambient); `None` for white-only lights |
| `source` | Critical: only `source="user"` analyzed (see §0.5) |
| `context` | Full `EventContext` — enables correlation with outdoor darkness, house_state, projector state, etc. |

### P7.2 Light attribute capture

Attributes are read from the HA entity state at the moment of the user action:

```python
new_state = event.data.get("new_state")
attributes = new_state.attributes if new_state else {}

entity_id = event.data.get("entity_id")                # str — entità specifica
brightness = attributes.get("brightness")               # int 0-255 or None
color_temp_kelvin = attributes.get("color_temp_kelvin") # int or None
rgb_color_raw = attributes.get("rgb_color")             # [r, g, b] list or None
rgb_color = tuple(rgb_color_raw) if rgb_color_raw else None
```

When `action="off"`, brightness/color fields are always `None` (the light has no state to read).

### P7.3 Storage integration

The persisted learning-event substrate must support a `lighting` event kind whose payload can be
deserialized together with the shared `EventContext`.

`STORAGE_VERSION` is **not bumped**: unknown event types return `None` in the switch — already
the fallback behavior. New records simply start appearing alongside old ones.

### P7.4 Capacity considerations

~10–30 `LightingEvent` per day in a typical household. At TTL=60 days: 600–1800 lighting events,
well within the 5000-record shared cap. Each event serializes to ~400–700 bytes (larger than v1
events due to `EventContext`).

Revised storage estimate including `EventContext` on all event types:

| Event type | Est. size | Daily volume | 60-day total |
|---|---|---|---|
| PresenceEvent | ~400 B | ~4 | ~240 |
| HeatingEvent | ~500 B | ~6 | ~360 |
| HouseStateEvent | ~450 B | ~10 | ~600 |
| LightingEvent | ~600 B | ~20 | ~1200 |
| **Total** | | | **~2400 records / ~1.4 MB** |

Comfortably within the 5000-record cap and HA Storage limits.

---

## P8. LightingRecorderBehavior

### P8.1 Responsibility

Observe HA entity state changes for configured light entities, determine whether the change was
caused by Heima or by the user, and append `LightingEvent` objects to `EventStore`.

### P8.1.1 Provenance and correlation terminology

This section uses two related concepts repeatedly:

- **Provenance**: metadata used to explain the origin of an observed state change. In practice,
  provenance answers: "did this change come from the user, from Heima, or from a recent Heima batch
  that likely caused it?"
- **Correlation**: metadata used to link multiple observed events that belong to the same logical
  action burst, even when Home Assistant delivers them as separate `state_changed` events.

Why provenance matters:
- the learning system must analyze only genuine user behavior when it is trying to infer habits
- otherwise Heima would learn from its own reactions and reinforce them incorrectly
- provenance is therefore the guardrail that prevents feedback loops in the event stream

Why correlation matters:
- real routines are often multi-entity and multi-event
- Home Assistant emits one event per affected entity, not one semantic "routine" object
- the analyzer needs a way to understand that "light A off, light B on, light F on" was one grouped
  interaction, not three unrelated actions

Normative rule:
- provenance decides whether an event is learnable as `source="user"` or should be treated as
  Heima-caused and skipped
- `correlation_id` links the remaining observed events that belong to the same batch, so analyzers
  can reconstruct grouped patterns from separate entity-level records

### P8.2 Source discrimination — the core challenge

The lighting domain applies scenes and per-entity light services, and accepted reactions can also
invoke `script.turn_on`. The recorder must not re-record those same changes as `source="user"`.

Reference implementation pattern: layered recent-apply provenance

When the recorder receives a HA `STATE_CHANGED` event for a light entity, it checks in order:
1. **Entity-level applies** tracked by `LightingDomain` for direct `light.turn_on` / `light.turn_off`
2. **Entity-level scene expansion**: when Heima applies `scene.turn_on`, the runtime resolves a
   best-effort set of light entities from the room area and marks them in the same apply batch
3. **Recent script batches**: `script.turn_on` is tracked as a short-lived batch-level provenance
   fallback for nearby observed light changes; when the originating reaction exposes a `room_id`,
   the batch is scoped to that room and may also carry expected room light entities
4. **Room-level fallback TTL**: recent room apply timestamps still prevent obvious self-recording loops

This is intentionally hybrid:
- deterministic when exact entity provenance is known
- best-effort for scenes
- short-window heuristic fallback for scripts, narrowed to room/entity scope when the runtime can
  infer it safely

In other words, provenance is layered because the runtime does not always know the full concrete
entity set in advance:
- direct light applies give exact provenance
- scenes give best-effort expanded provenance
- scripts often require a recent-batch heuristic

The recorder always prefers the strongest provenance available before falling back to weaker forms.

### P8.3 Room and scene resolution

The recorder resolves:

- `room_id`: derived from HA entity registry `area_id` matched against configured Heima rooms.
  Entities not belonging to any configured room are ignored.
- `scene`: currently stored as `None` in recorded lighting events. Grouping relies on
  entity-level changes plus `correlation_id`, not on guaranteed extraction of a named scene from
  every `state_changed`.

In practice, grouped scene/script effects are correlated through recent apply provenance and HA
context IDs when available.

For `scene.turn_on`, the runtime SHOULD expose a short-lived scene batch. When the HA scene state
declares concrete member entities, those members SHOULD be preferred as the expected subjects; room
light scope remains the normative fallback when scene membership is not introspectable.

Heating remains domain-specific for observed-source discrimination, but when an observed thermostat
setpoint matches a recent Heima apply, the runtime SHOULD expose provenance using the same common
metadata language (`source`, reaction origin, expected domains, expected subjects).

### P8.4 `ScriptApplyBatch` runtime contract

The runtime maintains a short-lived, in-memory `ScriptApplyBatch` contract for each recent
`script.turn_on` execution that should influence recorder source attribution.

Normative fields:
- `script_entity`
- `applied_ts`
- `correlation_id`
- `source`
- `origin_reaction_id` (optional)
- `origin_reaction_class` (optional)
- `room_id` (optional)
- `expected_domains` (optional, best-effort)
- `expected_subject_ids` (optional, best-effort)
- `expected_entity_ids` (optional, best-effort)

Normative rules:
- this contract is runtime-local provenance, not a persisted learning event
- recorder behaviors MAY use it to suppress Heima-caused follow-up state changes across domains
- recorders MUST prefer narrower scopes when available:
  - exact `expected_subject_ids`
  - exact `expected_entity_ids`
  - then `room_id + expected_domains`
  - then `room_id`
  - only then broader short-window fallback behavior

### P8.3.1 `correlation_id`

`correlation_id` is the runtime field used to connect multiple entity-level events that belong to
the same logical action.

Typical sources of `correlation_id`:
- a Home Assistant `context.id` propagated through related service calls and resulting state changes
- a Heima-generated batch id for recent apply tracking when the runtime initiates a grouped action

How it is used:
- the recorder stores it on each relevant event
- analyzers use it to group nearby per-entity changes into one higher-level routine candidate
- diagnostics can use it to explain why multiple separate events were treated as one burst

Why it is necessary:
- without `correlation_id`, grouping would rely only on time windows and room matching
- that is useful but weaker, especially for scenes/scripts and for future cross-domain behaviors
- with `correlation_id`, the runtime can preserve a stronger notion of "same action" across several
  observed entity changes

### P8.4 Registration

The lighting recorder is an event-driven behavior. It does not infer lighting events from snapshot
diffs alone; it listens to HA light state changes for the configured light entities.

```python
async def async_setup(self) -> None:
    self._unsub = self._hass.bus.async_listen(
        EVENT_STATE_CHANGED, self._handle_state_changed
    )

async def async_teardown(self) -> None:
    if self._unsub:
        self._unsub()
```

The runtime must ensure setup and teardown happen with integration load/unload semantics.

### P8.5 Event construction

```python
async def _handle_state_changed(self, event: Event) -> None:
    entity_id = event.data.get("entity_id", "")
    new_state = event.data.get("new_state")
    if new_state is None:
        return
    if entity_id not in self._entity_to_room:
        return  # not a configured light entity

    # source discrimination (entity -> scene batch -> script batch -> room TTL)
    if self._is_recent_heima_apply(entity_id=entity_id, room_id=self._entity_to_room[entity_id]):
        return  # Heima caused this, skip

    action: Literal["on", "off"] = "on" if new_state.state == "on" else "off"
    lighting_event = HeimaEvent(
        ts=new_state.last_changed.isoformat(),
        event_type="lighting",
        context=self._context_builder.build(self._last_snapshot),
        source="user",
        data={
            "entity_id": entity_id,          # entità specifica — chiave per entity-level analysis
            "room_id": self._entity_to_room[entity_id],
            "action": action,
            "scene": None,
            "brightness": brightness,
            "color_temp_kelvin": color_temp_kelvin,
            "rgb_color": rgb_color,
        },
    )
    self._hass.async_create_task(self._store.async_append(lighting_event))
```

---

## P9. LightingPatternAnalyzer

### P9.1 Responsibility

**Implementation note**

The current reference implementation can already learn and replay multi-entity lighting routines using:
- per-entity recorded lighting events
- `room_id`
- `correlation_id`
- aggregated entity attributes (`brightness`, `color_temp_kelvin`, `rgb_color`)

This is sufficient for v1 proposals such as:
- "living, Monday ~20:00: main on at 190 bri / 2850K, spot on at 96 bri / 3200K, floor off"

The main remaining gap is stronger provenance for arbitrary `script.turn_on` flows that touch many
entities across domains; the current implementation already applies short-lived batch provenance as a fallback,
but does not yet reconstruct the full concrete entity set touched by every script.

Rilevare configurazioni ricorrenti di luci per stanza e giorno della settimana, e proporre
all'utente di automatizzarle come una reazione temporizzata. L'analisi avviene in tre fasi:

1. **Entity-level pattern detection** — per ogni `(entity_id, action, weekday)`, rileva se
   l'entità viene modificata in modo ricorrente a un orario consistente.
2. **Scene candidate grouping** — raggruppa le entità della stessa stanza con `scheduled_min`
   simili (entro `SCENE_GROUP_WINDOW_MIN = 15 min`) in un'unica "scena candidata".
3. **Proposal emission** — emette una `ReactionProposal` per ogni scena candidata, con la lista
   completa degli stati entità da applicare.

Questo approccio cattura l'intento reale dell'utente: "ogni lunedì sera configuro il living così",
senza frammentare in 4-8 proposte separate per ogni singola luce.

### P9.2 Algorithm

#### Fase 1 — Entity-level pattern detection

```
Input: all HeimaEvent(event_type="lighting") from EventStore where source="user"

entity_patterns = {}   # (entity_id, action, weekday) -> EntityPattern

For each key (entity_id, action, weekday):
    matching = [e for e in lighting_events
                if e.data["entity_id"] == entity_id
                and e.data["action"] == action
                and e.context.weekday == weekday]

    Gate 1: len(matching) >= MIN_OCCURRENCES (default 5)
    Gate 2: distinct ISO weeks >= MIN_WEEKS (default 2)
    If either gate fails: skip

    samples_sorted = sorted(e.context.minute_of_day for e in matching)
    n = len(samples_sorted)
    median    = samples_sorted[n // 2]
    p25       = samples_sorted[n // 4]
    p75       = samples_sorted[3 * n // 4]
    IQR       = p75 - p25
    base_confidence = max(0.3, 1.0 - IQR / 120.0)
    evidence_factor = min(1.0, len(matching) / 8.0)
    weeks_factor    = min(1.0, weeks_observed(matching) / 3.0)
    confidence = round(
        max(0.3, base_confidence * (0.85 + 0.15 * evidence_factor) * (0.9 + 0.1 * weeks_factor)),
        3,
    )

    # Attributi fisici aggregati (action="on" only)
    brightness       = _median_int([e.data["brightness"] for e in matching])
    color_temp_kelvin = _median_int([e.data["color_temp_kelvin"] for e in matching])
    rgb_color        = _mode_rgb([e.data["rgb_color"] for e in matching])

    entity_patterns[(entity_id, action, weekday)] = EntityPattern(
        entity_id, action, weekday,
        room_id=matching[0].data["room_id"],
        scheduled_min=median,
        confidence=confidence,
        brightness=brightness,
        color_temp_kelvin=color_temp_kelvin,
        rgb_color=rgb_color,
    )
```

`_median_int(values)`: mediana dei valori non-None; `None` se meno di `MIN_OCCURRENCES // 2`
valori sono presenti (luce senza dimmer o attributo non disponibile).

`_mode_rgb(values)`: moda dei vettori `[r,g,b]` non-None (confronto esatto); `None` se
misto o insufficiente. La rgb ha precedenza su `color_temp_kelvin` se entrambi presenti.

#### Fase 2 — Scene candidate grouping

```
# Raggruppa per (room_id, weekday), poi clusterizza per scheduled_min

for (room_id, weekday), patterns in group_by_room_weekday(entity_patterns):
    sorted_patterns = sorted(patterns, key=lambda p: p.scheduled_min)

    # Gap-based clustering: nuovo cluster se gap > SCENE_GROUP_WINDOW_MIN
    clusters = []
    current_cluster = [sorted_patterns[0]]
    for p in sorted_patterns[1:]:
        if p.scheduled_min - current_cluster[-1].scheduled_min <= SCENE_GROUP_WINDOW_MIN:
            current_cluster.append(p)
        else:
            clusters.append(current_cluster)
            current_cluster = [p]
    clusters.append(current_cluster)

    for cluster in clusters:
        scheduled_min = median([p.scheduled_min for p in cluster])
        confidence    = mean([p.confidence for p in cluster])   # media, non min
        entity_steps  = [p.as_entity_step() for p in cluster]
        Emit SceneCandidate(room_id, weekday, scheduled_min, confidence, entity_steps)
```

**Confidence del gruppo:** media delle confidence individuali. Riflette la qualità complessiva del
pattern; penalizza meno i casi in cui la maggioranza delle entità è consistente ma una sola è
leggermente più variabile.

**Confidence operativa v1:** la confidence lighting NON dovrebbe dipendere solo da IQR.
Anche pattern con IQR molto basso ma evidenza minima (es. appena 5 eventi su 2 settimane) dovrebbero
restare leggermente meno confident di pattern osservati più spesso e su più settimane. In v1:
- IQR resta il driver principale
- `observations_count` e `weeks_observed` agiscono come moltiplicatori moderati, non come gate nuovi

**Noise gate operativo v1:** oltre alla confidence, il lighting analyzer può scartare pattern con
evidenza appena minima ma già troppo dispersi nel tempo. In pratica:
- un pattern lighting con solo `5` osservazioni su `2` settimane e `IQR` ancora ampia non dovrebbe
  diventare proposal solo perché supera di poco il `min_confidence` globale
- in v1 è accettabile introdurre un gate conservativo del tipo:
  - evidenza minima (`observations_count <= 5` e `weeks_observed <= 2`)
  - dispersione temporale già larga (`IQR > 30`)
  - quindi pattern scartato come rumoroso

Questo NON introduce sessioni multi-evento o un nuovo modello: è solo un filtro pragmatico per
ridurre proposal lighting deboli ma formalmente valide.

#### Finestra runtime adattiva

`window_half_min` per lighting non dovrebbe essere sempre fisso. In v1 può essere derivato dalla
stabilità del cluster:
- pattern molto stretti → finestra più piccola
- pattern più variabili ma ancora accettati → finestra più larga

Recommended v1 mapping:
- `IQR <= 5` → `window_half_min = 5`
- `IQR <= 15` → `window_half_min = 10`
- altrimenti → `window_half_min = 15`

#### Fase 3 — Proposal emission

Per ogni `SceneCandidate`, emetti una `ReactionProposal` (vedi §P9.3).

**Why IQR, not std-dev:** same rationale as `PresencePatternAnalyzer` — robust to outliers.

**Why `MIN_WEEKS=2`:** previene che una settimana di comportamento consistente (es. settimana di
vacanza) generi proposte spurie. Mancante in `PresencePatternAnalyzer` (open item futuro).

**Why entity-level + grouping, not session detection on raw events:** il session detection richiede
clustering temporale sugli eventi grezzi e una misura di similarità tra sessioni diverse — complessità
significativa. Il grouping post-analisi (fase 2) ottiene lo stesso risultato lavorando su mediane già
calcolate, con un algoritmo molto più semplice.

**Why no HA scene creation:** Heima non crea scene HA persistenti. Applica gli stati entità
direttamente tramite il service `light.turn_on`/`light.turn_off`. La logica è self-contained e non
dipende dalla configurazione scene dell'utente.

### P9.3 Output proposal

Una proposta per `SceneCandidate` (= per stanza × giorno × cluster orario):

```python
ReactionProposal(
    analyzer_id="LightingPatternAnalyzer",
    reaction_type="lighting_scene_schedule",
    description=(
        f"{room_id}: {WEEKDAY_NAMES[weekday]} ~{hhmm(scheduled_min)} — "
        + ", ".join(
            f"{step['entity_id'].split('.')[-1]} {'on' if step['action']=='on' else 'off'}"
            + (f" {step['brightness']}bri/{step['color_temp_kelvin']}K"
               if step['action'] == 'on' and step['brightness'] else "")
            for step in entity_steps
        )
    ),
    confidence=confidence,
    suggested_reaction_config={
        "reaction_class": "LightingScheduleReaction",
        "room_id": room_id,
        "weekday": weekday,
        "scheduled_min": scheduled_min,
        "window_half_min": derived_window_half_min,
        "house_state_filter": None,
        "entity_steps": [
            # Un dict per entità nel cluster
            {
                "entity_id": "light.living_main",
                "action": "on",
                "brightness": 128,          # int o None
                "color_temp_kelvin": 3000,  # int o None
                "rgb_color": None,          # [r,g,b] o None
            },
            {
                "entity_id": "light.living_spot",
                "action": "on",
                "brightness": 64,
                "color_temp_kelvin": 3500,
                "rgb_color": None,
            },
            {
                "entity_id": "light.living_floor",
                "action": "off",
                "brightness": None,
                "color_temp_kelvin": None,
                "rgb_color": None,
            },
        ],
    },
)
```

### P9.4 Fingerprint for deduplication

```
f"LightingPatternAnalyzer|lighting_scene_schedule|{room_id}|{weekday}|{scheduled_min}"
```

Il `scheduled_min` nel fingerprint è la mediana del cluster, arrotondata a 5 minuti per evitare
che piccole variazioni di un'iterazione all'altra creino proposte duplicate.

```python
fingerprint_min = (scheduled_min // 5) * 5
fingerprint = f"LightingPatternAnalyzer|lighting_scene_schedule|{room_id}|{weekday}|{fingerprint_min}"
```

### P9.4.1 Scene quality and collision handling

Lighting scene proposals SHOULD prefer stable, human-legible output over raw cluster exhaust.

Normative quality rules for v1 lighting proposals:
- a scene candidate SHOULD contain at most one step per `entity_id`
- when multiple raw patterns for the same `entity_id` fall into the same logical cluster, the
  analyzer SHOULD collapse them into one representative step rather than emitting duplicates
- proposal descriptions SHOULD be stable and deterministic for the same logical scene candidate
- entity ordering in descriptions and config SHOULD be deterministic so small analyzer churn does
  not create confusing review diffs

Normative collision rule:
- when two lighting scene candidates for the same `(room_id, weekday)` fall into the same
  30-minute identity bucket, v1 SHOULD prefer emitting at most one logical proposal candidate for
  that bucket unless there is a materially different entity set
- proposal identity for lighting MUST therefore combine:
  - `(room_id, weekday, time_bucket_30m)`
  - a stable `scene_signature` derived from normalized `entity_steps`
- `scene_signature` SHOULD use coarse payload normalization so that minor brightness / kelvin drift
  refreshes the same logical proposal instead of creating a new identity slot

Examples of materially different changes:
- added or removed entities
- different dominant on/off intent for one entity
- materially different brightness / color temperature payloads

Minor drift that SHOULD NOT create a separate logical scene:
- a few minutes of schedule movement inside the same 30-minute bucket
- small attribute noise on a minority of samples

### P9.5 LightingScheduleReaction

#### Trigger — RuntimeScheduler

Usa il `RuntimeScheduler` già presente. La reaction implementa `scheduled_jobs(entry_id)` (nuovo
hook no-op su `HeimaReaction` base). L'engine raccoglie i job da tutte le reaction in
`scheduled_runtime_jobs()` e li passa al coordinator via `_sync_scheduler()`. Quando il job
scatta → eval cycle → `evaluate()` verifica la finestra e produce gli step.

```python
def scheduled_jobs(self, entry_id: str) -> dict[str, ScheduledRuntimeJob]:
    due_monotonic = self._next_due_monotonic()
    job_id = f"lighting_schedule:{self.reaction_id}"
    return {
        job_id: ScheduledRuntimeJob(
            job_id=job_id,
            owner="LightingScheduleReaction",
            entry_id=entry_id,
            due_monotonic=due_monotonic,
            label=f"lighting: {self._room_id} {WEEKDAY_NAMES[self._weekday]} ~{hhmm(self._scheduled_min)}",
        )
    }
```

`_next_due_monotonic()`: prossimo wall-clock in cui inizia la finestra
`scheduled_min ± window_half_min` per il `weekday` configurato. L'implementazione reale deve
gestire correttamente le finestre che attraversano mezzanotte.

#### Evaluate — time-window check + debounce

La finestra deve supportare wrap su mezzanotte. Il debounce non è legato semplicemente alla data
wall-clock corrente, ma al giorno logico dell'occorrenza configurata: una schedule `00:05 ± 10 min`
può iniziare il giorno precedente e non deve double-fire dopo mezzanotte.

#### Runtime guardrails

Le lighting reaction non dovrebbero bypassare i guardrail operativi del dominio lighting. In v1:
- un `LightingScheduleReaction` può ancora emettere i suoi `ApplyStep`
- ma gli step lighting reaction-generated devono passare anche da un `apply_filter` behavior che
  rispetta il manual hold della stanza
- se `heima_lighting_hold_<room_id>` è attivo e la stanza è configurata con manual hold abilitato,
  gli step lighting con `source="reaction:<...>"` dovrebbero essere bloccati con una ragione
  esplicita tipo:
  - `lighting.manual_hold:<room_id>`

Questo è un guardrail runtime, non un cambio del modello di learning.

#### ApplyStep — uno per entità

```python
def _build_steps(self) -> list[ApplyStep]:
    steps = []
    for step_cfg in self._entity_steps:
        entity_id = step_cfg["entity_id"]
        action    = step_cfg["action"]
        if action == "on":
            params: dict[str, Any] = {"entity_id": entity_id}
            if step_cfg.get("brightness") is not None:
                params["brightness"] = step_cfg["brightness"]
            if step_cfg.get("rgb_color") is not None:
                params["rgb_color"] = step_cfg["rgb_color"]
            elif step_cfg.get("color_temp_kelvin") is not None:
                params["color_temp_kelvin"] = step_cfg["color_temp_kelvin"]
            steps.append(ApplyStep(
                domain="lighting",
                target=self._room_id,       # per apply-timestamp tracking
                action="light.turn_on",
                params=params,
                reason=f"lighting_schedule:{self.reaction_id}",
            ))
        else:
            steps.append(ApplyStep(
                domain="lighting",
                target=self._room_id,
                action="light.turn_off",
                params={"entity_id": entity_id},
                reason=f"lighting_schedule:{self.reaction_id}",
            ))
    return steps
```

`execute_lighting_steps()` in `LightingDomain` aggiunge due rami:

- `action="light.turn_on"` con `params["entity_id"]`: chiama `light.turn_on` sull'entità specifica
  con gli attributi forniti. Aggiorna `last_apply_ts_by_room[step.target]`.
- `action="light.turn_off"` con `params["entity_id"]` (anziché `area_id`): chiama `light.turn_off`
  sull'entità specifica. Il ramo esistente con `area_id` rimane invariato per gli step del dominio
  lighting ordinario.

#### Config

```python
LightingScheduleReaction(
    room_id="living",
    weekday=0,
    scheduled_min=1200,
    window_half_min=10,
    house_state_filter=None,
    entity_steps=[
        {"entity_id": "light.living_main",  "action": "on",  "brightness": 128, "color_temp_kelvin": 3000, "rgb_color": None},
        {"entity_id": "light.living_spot",  "action": "on",  "brightness": 64,  "color_temp_kelvin": 3500, "rgb_color": None},
        {"entity_id": "light.living_floor", "action": "off", "brightness": None, "color_temp_kelvin": None, "rgb_color": None},
    ],
    reaction_id="LightingPatternAnalyzer|lighting_scene_schedule|living|0|1200",
)
```

Istanziata da `_rebuild_configured_reactions()` quando `reaction_class == "LightingScheduleReaction"`.

### P9.6 Registration

```python
# coordinator.py
proposal_engine.register_analyzer(LightingPatternAnalyzer())
```

---

## P10. Composite Pattern Engine (v1)

### P10.1 Goal

The first cross-domain analyzers in v1 should prove that the generic event substrate can support
multi-signal, room-scoped behavioral inference beyond lighting/heating preferences.

The longer-term goal is not a growing list of unrelated bespoke analyzers, but a small,
reviewable, explainable composite pattern engine that can host several room-scoped behavioral
patterns on the same substrate.

The canonical v1 starter use cases are:
- bathroom occupied
- humidity rises quickly
- optional temperature rise corroborates the episode
- the user usually starts ventilation shortly after

and:
- room occupied
- temperature rises quickly
- optional humidity rise corroborates the episode
- the user usually starts cooling shortly after

The engine should convert repeated occurrences of these composite behaviors into user-reviewable
proposals.

### P10.2 Scope

The first engine version is intentionally narrow.

In scope:
- a small library of room-scoped composite patterns
- signal correlation over a short window
- proposal generation for a generic assist reaction with user-configured actions
- standardized, explainable episode detection over the shared `state_change` substrate
- a declarative pattern catalog that remains smaller than the runtime implementation

Out of scope for v1:
- arbitrary unsupervised cross-domain discovery
- automatic fan entity selection
- automatic actuation without user approval
- probabilistic or ML-heavy shower detection

Normative rule:
- adding a new v1 composite behavior SHOULD prefer extending the pattern catalog over introducing a
  new analyzer with mostly duplicated logic

Normative design direction:
- the v1 system MUST converge toward a declared pattern library plus shared matching and proposal
  infrastructure
- concrete starter cases such as `room_signal_assist` and `room_cooling_assist` are exemplars of
  that library, not permanent architecture exceptions

### P10.3 Core concepts

The composite pattern engine uses the following terms normatively:

- **Composite pattern**: a named, reviewable behavioral template expressed as a primary signal,
  optional corroboration signals, a follow-up action class, support thresholds, and proposal output
  metadata.
- **Episode**: one candidate occurrence of a composite pattern in one room, anchored by a primary
  signal event and evaluated over bounded correlation and follow-up windows.
- **Primary signal**: the first meaningful observed signal that opens an episode, such as a sharp
  humidity or temperature rise.
- **Corroboration signal**: an optional additional signal that strengthens confidence in the
  episode, but is not required for episode existence unless a pattern explicitly marks it as
  required.
- **Follow-up action**: the later user-observed actuation that confirms the inferred behavioral
  intent of the episode.
- **Pattern catalog**: the declarative list of supported composite patterns in v1.
- **Composite assist reaction**: the generic runtime reaction class rebuilt from accepted composite
  proposals.

Normative rule:
- a composite pattern MUST be explainable in terms of these concepts without requiring code
  knowledge

### P10.4 Composite assist plugin architecture

The room-scoped composite assist plugin family has three conceptual layers inside the shared
learning system:

1. **Shared event substrate**
   - `state_change` events with `room_id`, `source`, `context`, and optional `correlation_id`
2. **Composite matcher**
   - deterministic room-scoped episode detector using configured thresholds and windows
3. **Pattern catalog + proposal layer**
   - one library of named patterns that reuses the same matcher and emits stable proposal types

Normative rule:
- the matcher layer is generic and room-scoped
- the pattern catalog decides semantics, thresholds, explanation text, and proposal metadata
- proposal emission must not depend on one-off analyzer-private behavior that is invisible in spec

### P10.4.1 Relationship with other plugins

The room-scoped composite assist family is one plugin family inside the shared learning system.

It does not replace other plugins that may use different matching semantics on the same
event substrate.

Examples:
- the composite assist family is a better fit for patterns like:
  - occupancy + humidity rise -> ventilation assist
  - occupancy + temperature rise -> cooling assist
  - occupancy + low room lux / outdoor darkness -> lighting assist with observed discrete brightness
- the lighting routine family remains a better fit for patterns like:
  - recurring multi-entity light scenes
  - explicit per-entity brightness/color end states
  - schedule-like room routines reconstructed as detailed light steps

Using the two-axis model:
- `lighting routine` is typically:
  - trigger family: temporal
  - response family: lighting replay
- `room_signal_assist` is typically:
  - trigger family: room-signal threshold/composite
  - response family: generic configured steps
- `room_darkness_lighting_assist` is:
  - trigger family: room-signal threshold/composite
  - response family: lighting replay

Normative product rule:
- new explainable room-scoped assist behaviors SHOULD prefer the composite assist plugin family
- an existing or new plugin SHOULD remain separate when it preserves materially richer
  semantics, fidelity, or actuation detail than the composite room-assist model
- the presence of the composite assist family MUST NOT be interpreted as a requirement to remove
  other plugins prematurely

### P10.4.2 Relationship with future Reaction Enhancements

Some future behaviors may need to go beyond a discrete learned reaction and add bounded adaptive or
maintenance semantics on top of it.

Examples:
- after learning a darkness-triggered lighting reaction, propose maintaining a room brightness
  setpoint
- after learning a heating preference reaction, propose maintaining a temperature setpoint

Normative guidance:
- such capabilities SHOULD first be modeled as optional enhancements layered on top of an accepted
  reaction, not as a replacement for the base learned reaction itself
- the base learned reaction SHOULD remain understandable and executable on its own
- v1 composite assists MUST remain discrete/reviewable reaction proposals, not closed-loop control
  systems

### P10.5 Input requirements

The engine reads from the shared `EventStore` and correlates:
- room occupancy evidence from `EventContext.occupied_rooms`
- room-scoped `state_change` events for humidity sensors
- room-scoped `state_change` events for temperature sensors
- optional later user fan/climate activation events if those entities are configured as context signals

Minimum required signals for the v1 ventilation assist:
- one humidity signal mapped to the room
- occupancy evidence in the same room

Optional strengthening signal:
- one temperature signal mapped to the same room

Minimum required signals for the v1 cooling assist:
- one temperature signal mapped to the room
- occupancy evidence in the same room

Optional strengthening signal:
- one humidity signal mapped to the same room

### P10.6 Episode definition

Each composite pattern works in two stages:

1. **Episode detection**
   - find the primary `state_change` event in room `R`
   - compute delta = `new_state - old_state` for numeric values
   - keep only events where:
     - room `R` is occupied in the event context, and
     - the primary delta exceeds the configured primary threshold
   - optionally mark the episode as corroborated if one or more corroboration signals above
     threshold occur in the same room within the same short window

2. **Behavior confirmation**
   - for each detected episode, look for a later user-observed follow-up activation in the same room
     within a bounded follow-up window
   - repeated confirmed episodes with sufficient support become a proposal candidate

Normative rules:
- episode detection must be deterministic for a given ordered event history
- the same event history must produce the same episode boundaries and support counts
- corroboration may affect confidence and explanation, but must not silently redefine the primary
  pattern semantics

### P10.7 Standard pattern fields

Every catalog pattern in the v1 composite engine MUST define:
- `pattern_id`
- `proposal_type`
- `reaction_type`
- `reaction_class`
- `room_scope` semantics
- primary signal predicate and threshold
- primary signal label
- optional corroboration signal predicates and thresholds
- optional corroboration signal label
- follow-up action predicate
- follow-up action label
- correlation window
- follow-up window
- support threshold
- week-span threshold
- confidence shaping rule
- explanation template
- suggested reaction class

The implementation MAY represent these through one or more internal data classes, but the above
fields are the normative contract.

Normative rule:
- the pattern catalog defines semantics and product intent
- the matcher defines only how episodes are detected
- the proposal layer defines only how a matched pattern is surfaced and stored

### P10.8 V1 thresholds

Recommended default thresholds for the first implementation:
- humidity rise threshold: configurable, default `>= 8` percentage points in one observed change
- corroboration temperature rise threshold: configurable, default `>= 0.8 C`
- signal correlation window: configurable, default `10 min`
- fan follow-up window: configurable, default `15 min`
- minimum confirmed episodes: `>= 5`
- minimum distinct ISO weeks: `>= 2`

These thresholds are intended to be simple and explainable, not universally optimal.

Each catalog pattern MAY override these defaults when justified, but every override MUST be:
- explicit in the pattern catalog
- explainable in prose
- covered by deterministic tests

### P10.9 Output proposal

The engine emits a `ReactionProposal` with:
- a stable analyzer id
- a stable reaction type such as `room_signal_assist` or `room_cooling_assist`
- description that explains the inferred pattern in plain language
- confidence derived from support and temporal consistency

The suggested reaction config must be executable after user approval and must not depend on a
domain-specific hardcoded fan semantic.

V1 target config shape:
- `reaction_class="RoomSignalAssistReaction"`
- `room_id`
- `trigger_signal_entities`
- generic runtime matcher fields:
  - `primary_signal_entities`
  - `primary_threshold`
  - `primary_threshold_mode`
  - `primary_signal_name`
  - `corroboration_signal_entities`
  - `corroboration_threshold`
  - `corroboration_threshold_mode`
  - `corroboration_signal_name`
- legacy aliases remain valid for the first humidity/ventilation assist:
  - `humidity_rise_threshold`
  - `primary_rise_threshold`
  - `temperature_rise_threshold`
  - `corroboration_rise_threshold`
- `correlation_window_s`
- `followup_window_s`
- `steps=[]` by default, to be completed by the user in the proposal action configuration flow

Supported v1 trigger modes for the generic matcher fields:
- numeric threshold/delta modes:
  - `rise`
  - `drop`
  - `above`
  - `below`
- binary transition modes:
  - `switch_on`
  - `switch_off`
  - `state_change`

Normative rules:
- composite proposal types MUST remain stable across restart and rebuild boundaries
- accepted proposals MUST rebuild into a runtime reaction without requiring analyzer-only hidden
  state
- diagnostics-visible descriptions MUST remain understandable without inspecting code
- human-readable description text is explanatory only; structured proposal fields remain
  authoritative

For composite patterns, the proposal payload SHOULD also preserve:
- primary signal family name
- corroboration signal family name when present
- observed follow-up entities used to confirm the learned behavior
- episode counts needed for diagnostics and review

### P10.10 Pattern catalog (v1)

The initial v1 catalog contains at least these named patterns:

1. `room_signal_assist`
- primary signal: humidity rise
- optional corroboration: temperature rise
- follow-up action class: ventilation/cooling-like user activation
- canonical example: bathroom shower ventilation assist

2. `room_cooling_assist`
- primary signal: temperature rise
- optional corroboration: humidity rise
- follow-up action class: cooling-like user activation
- canonical example: studio cooling assist

3. `room_air_quality_assist`
- primary signal: CO2 rise
- corroboration: none required in v1
- follow-up action class: ventilation-like user activation
- canonical example: office air-quality ventilation assist

4. `room_darkness_lighting_assist`
- primary signal: room lux low threshold or rapid lux drop
- optional corroboration: outdoor darkness / outdoor lux / time-window context
- follow-up action class: discrete user lighting actuation in the same room
- canonical example: occupied room becomes too dark and the user turns on lights with a learned
  brightness level
- first expected output mode in v1: replay the observed discrete lighting actuation
- non-goal for the first iteration: adaptive closed-loop brightness maintenance

Normative rule:
- new v1 patterns SHOULD be added by extending this catalog and reusing the same composite engine,
  unless a pattern truly requires different episode semantics

### P10.11 Execution model

The accepted reaction must be generic:
- it detects the configured room-scoped composite pattern at runtime
- when the pattern is observed again, it emits the configured `steps`
- the actual actuation target is still chosen by the user through the existing proposal action
  configuration flow

This keeps the analyzer domain-agnostic:
- the analyzer learns "when a fan-like assist is appropriate"
- the user decides which HA action implements that assist in the house

Normative runtime contract:
- the generic runtime reaction for v1 composite assists MUST remain more general than any one
  concrete learned pattern
- a new declared pattern SHOULD reuse the same runtime reaction whenever its execution model is
  "detect room-scoped composite condition, then execute user-configured steps"

Backward-compatibility rule:
- legacy config aliases may remain valid for previously accepted proposals
- the normalized long-term contract is the generic composite contract, not legacy case-specific
  field names

### P10.11.a Actuation plan variants in v1

Composite and lighting proposal families may rebuild into different concrete actuation payloads,
but these should be understood as variants of a shared **actuation plan** concept.

In v1:

- `steps`
  - generic apply/service-oriented actions
  - used by `RoomSignalAssistReaction` and similar generic assist reactions
- `entity_steps`
  - entity-scoped lighting replay/apply actions with richer lighting fields
  - used by lighting-specific reactions such as learned schedules and darkness-lighting assists

Normative clarification:

- v1 does not require a unified runtime payload for all actuation plans
- keeping `steps` and `entity_steps` distinct is acceptable in v1 when it preserves clarity,
  backward compatibility, and simpler runtime code
- specs and diagnostics SHOULD nevertheless describe both as actuation-plan variants rather than as
  unrelated concepts

### P10.11.1 `room_darkness_lighting_assist` execution contract

`room_darkness_lighting_assist` is the first implemented pattern where:
- trigger family = room-scoped composite threshold/correlation
- response family = lighting replay

Because of that combination, the first implementation SHOULD NOT be modeled as a pure
`RoomSignalAssistReaction` fan/switch-style assist.

Preferred v1 execution contract:
- accepted proposals rebuild into a lighting-focused reaction, tentatively
  `RoomLightingAssistReaction`
- the reaction re-detects the room-scoped darkness trigger at runtime
- when triggered, it replays the observed discrete lighting response for the room

Expected first-step replay scope:
- `light.turn_on` / `light.turn_off`
- observed `brightness` when available
- optional observed `color_temp_kelvin` when available

Non-goals for the first iteration:
- adaptive brightness maintenance
- continuous control loops
- alternative acceptance modes in the same proposal

Normative product rule:
- the first version of `room_darkness_lighting_assist` MUST reproduce the observed user response,
  not a generic placeholder action
- if the observed response includes stable brightness information, the replay contract SHOULD
  preserve it

### P10.11.2 `room_darkness_lighting_assist` proposal shape

The first proposal shape SHOULD remain reviewable and explicit.

Suggested target config:
- `reaction_class="RoomLightingAssistReaction"`
- `room_id`
- trigger matcher fields:
  - `primary_signal_entities`
  - `primary_rise_threshold` or low-threshold equivalent for room lux
  - `primary_signal_name="room_lux"`
  - optional corroboration fields for outdoor darkness / outdoor lux
  - `correlation_window_s`
  - `followup_window_s`
- replay payload:
  - `entity_steps`
  - each step SHOULD preserve observed lighting actuation fields when available:
    - `entity_id`
    - `action`
    - `brightness`
    - `color_temp_kelvin`
    - `rgb_color`

Review diagnostics SHOULD also preserve:
- matched lux entities
- matched outdoor corroboration entities when present
- matched follow-up light entities
- whether replay brightness was learned from stable observed follow-up samples

### P10.12 Explainability requirement

Every emitted proposal must be explainable in plain language, for example:

> Bathroom: when occupancy is present and humidity rises rapidly, you usually start ventilation
> within a few minutes.

The diagnostics for the analyzer should make it possible to inspect:
- detected episodes
- corroborated episodes
- confirmed fan-followup episodes
- thresholds used for acceptance

V1 review payload rule:
- the suggested config for a composite proposal SHOULD include a stable
  `learning_diagnostics` object
- `learning_diagnostics` SHOULD expose at least:
  - `pattern_id`
  - `room_id`
  - `primary_signal`
  - `corroboration_signals`
  - `followup_signal`
  - `episodes_detected`
  - `episodes_confirmed`
  - `weeks_observed`
  - `corroborated_episodes`
  - matched primary, corroboration, and follow-up entity sets
- this block is informative for review and diagnostics; the executable reaction contract
  remains the authoritative part of the proposal

### P10.13 Relationship with future pattern families and inference

This composite assist family is the v1 bridge from simple domain-specific preference learning to
more capable cross-domain behavior learning.

It should be understood as:
- one reusable learning plugin family inside the shared learning system
- not as a separate learning subsystem
- not as a universal replacement for all other learning families

If successful, the same substrate can later support:
- kitchen cooking extraction
- bedroom sleep-environment assists
- office/working-mode assists
- generalized multi-signal routines in inference v2

The intended next architectural step is:
- keep the matcher generic
- keep the pattern library explicit and reviewable
- avoid adding one bespoke analyzer class per new room-scoped assist case unless that is
  semantically necessary
- treat new learning capabilities first as candidate plugins inside the same shared
  learning system

Boundary with future discovery systems:
- the v1 composite engine searches known pattern families only
- it does not mine the full event space for arbitrary latent routines

This boundary is intentional because it preserves:
- explainability
- deterministic testability
- product control over what behaviors may be proposed

---

## 11. Informative Appendices

The following sections are informative. They help orient implementation work, but they are not the
normative source of truth for the learning contract.

### 11.1 Reference implementation layout

```
custom_components/heima/runtime/
  event_store.py                    Implemented + LightingEvent (P7)
  proposal_engine.py                Implemented
  analyzers/
    __init__.py                     Implemented
    base.py                         Implemented — IPatternAnalyzer + ReactionProposal
    composite.py                    Implemented — reusable room-scoped composite matcher
    cross_domain.py                 Implemented — ventilation assist + cooling assist analyzers
    presence.py                     Implemented — PresencePatternAnalyzer
    heating.py                      Implemented/Partial — HeatingPatternAnalyzer
    lighting.py                     Implemented — LightingPatternAnalyzer
  behaviors/
    event_recorder.py               Implemented — presence + house_state events
    heating_recorder.py             Implemented — observed heating setpoint events
    lighting_recorder.py            Implemented — user light action events with entity-level payload
    signal_recorder.py              Implemented — generic `state_change` events for configured context signals
  reactions/
    composite.py                    Implemented — reusable runtime composite matcher
    lighting_schedule.py            Implemented — LightingScheduleReaction
    signal_assist.py                Implemented — RoomSignalAssistReaction
```

This section is informative only. It summarizes one known implementation layout, but the
normative contract of this spec does not depend on these exact file boundaries.

---

## 12. Informative Dependency View

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

## 13. Informative Test Plan

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

## 14. Additional Design Constraints

- **No ML libraries in v1.** Built-in analyzers use pure Python: `sorted()`, median/percentile via index arithmetic. Advanced analyzers can be added via the `IPatternAnalyzer` plug-in contract without touching core components (see §10.4).
- **No blocking the eval cycle.** `async_append()` is always scheduled as a task from `on_snapshot()`.
- **PresencePatternReaction stays.** Real-time in-memory firing continues. Analyzers are the offline "proposal" path — complementary, not a replacement.
- **Partial proposals are valid.** `steps: []` is acceptable; user fills targets in Options Flow.
- **Proposal acceptance persists.** Stored in `options["reactions"]["configured"]` (HA config entry options, durable).
- **EventStore writes are batched.** `async_delay_save(fn, 30)` avoids I/O on every event.

---

## 15. Open Questions (informative)

1. **HeatingRecorderBehavior access to `heating_trace`**: preferred option is `engine.heating_trace` property for testability.
2. **`heima_reaction_proposals` sensor format**: value = count of pending proposals (int, allows HA automations on count changes), attributes = full proposals dict.
3. **6h periodic scheduling**: `async_call_later` with recursive reschedule is consistent with existing scheduler pattern in `coordinator.py`.
4. **HeatingEvent source detection**: `source="heima"` when `heating_trace["apply_allowed"]` was True in same cycle; `source="user"` for all other observed setpoint changes.
