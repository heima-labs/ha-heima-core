# Heima v3 — `HouseFact` foundational model (draft shapes)

> **Historical draft.** The current V3 contracts are [Layer 0](specs/v3/layer0_runtime_spec.md)
> and [Layer 1](specs/v3/layer1_substrate_spec.md); this file preserves earlier reasoning only.

Status: **historical draft, superseded by Layers 0–1, not implemented as written.** Captures the concrete shape of
the four axes converged on in `v3_backlog.md` (what/how/when/where), so the reasoning survives
context loss. Python-flavored pseudocode, not final code — field names/types are proposals.

---

## `HouseFact` — the core primitive

```python
@dataclass(frozen=True)
class HouseFact:
    fact_type: str        # namespaced kind, extends HeimaEvent's existing type/key taxonomy
                           # convention (event_catalog_spec.md) instead of inventing a new one —
                           # e.g. "room_signal.bucket", "house_state", "occupancy", "activity.pattern"
    value: Any             # interpreted payload: bucket label, enum value, bool, structured dict
    where: Location         # WHERE
    when: datetime          # WHEN — a plain timestamp; no wrapper type needed, matches existing
                            # `ts: str` (ISO) convention used across the codebase today
    how: Provenance         # HOW
```

`fact_type` deliberately reuses `HeimaEvent`'s taxonomy rather than inventing a parallel one —
`event_catalog_spec.md` already does this work; `HeimaEvent` itself becomes expressible as a
`HouseFact` with `fact_type` in that taxonomy, not a separate thing.

---

## HOW — `Provenance`

```python
class Freshness(Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    # unifies today's separate `stale: bool` + `available: bool` on NormalizedObservation
    # into one tri-state — "stale but available" and "unavailable" were always distinct
    # meanings wearing two overlapping booleans
    #
    # STALE computation (added 2026-08-31, from the external review pass): generalizes
    # ExternalContext's elapsed-time check (is_slot_stale/last_updated/DEFAULT_STALENESS_MAX_AGE)
    # to every HouseFact, not just weather data. Checked: ordinary NormalizedObservation.stale
    # today defaults to False and is only ever propagated from already-stale fusion inputs
    # (normalization/service.py:364) — no primary observation computes staleness from elapsed
    # time at all today. This closes that gap for every Sensor, not only external ones.

@dataclass(frozen=True)
class Provenance:
    confidence: float                       # 0.0-1.0
    source: FactSource                       # NOT a free string — see below
    freshness: Freshness = Freshness.FRESH
    evidence: dict[str, Any] = field(default_factory=dict)
    # today's DerivedObservation.raw_state / fusion_strategy / inputs / reason all live here
```

**`confidence` computation, standardized 2026-09-01** (`v3_backlog.md`, LP-1+LP-2 — found 4
incompatible formulas across today's modules/analyzers, all called "confidence," not comparable).
Exactly two forms, chosen by the target's declared shape, never reinvented per producer:

```python
# Categorical target (a discrete label: house_state, scene name, activity name):
confidence = count_best_outcome / total_observations        # P(outcome | pattern) — a true match ratio

# Continuous target (a learned numeric value: setpoint, time-of-day):
confidence = max(floor, 1.0 - dispersion / scale)            # inverse dispersion; `floor`/`scale`
                                                                # are named parameters per use site,
                                                                # not ad hoc magic numbers
```

`min_support` (per-`PatternLearner` threshold) stays a separate boolean pass/fail gate — "enough data
to trust this at all" — never blended into the confidence float itself. That blending was the one
formula found actually wrong (`min(1.0, support / min_support)`, mistaking volume for confidence);
both modules that used it (`HeatingPreferenceModule`, `WeekdayStateModule`) are already marked for
removal.

**Corrected 2026-08-31**: `source` is not a free-form string. Phase AS ("Structured Runtime Source",
`DONE`) already solved this exact problem — "how much do I trust where this came from" — for the
*action* side (`ApplyStepSource`, [contracts.py:73-90](custom_components/heima/runtime/contracts.py#L73-L90)):
`kind` + `source_id` + `source_type` + `actor_type` + `actor_id` + `correlation_id`, with a
dedicated `as_redacted_dict()` and non-forgeability guarantees ("forged structured dictionaries are
sanitized and cannot be authoritative"). Its own stated goal was avoiding "a parallel
`ApplyStep.provenance` field" — building a second, independently-designed structured-source type
for `HouseFact` would violate that same principle from the other direction. `Provenance.source`
reuses the same vocabulary instead:

```python
FactSourceKind = ApplyStepSourceKind | Literal["sensor", "analyzer", "third_party_plugin"]
# extends today's ApplyStepSourceKind (reaction/domain/admin_command/resident_response/timeout/
# recovery/system/test/legacy) with the 3 kinds facts need that actions don't

@dataclass(frozen=True)
class FactSource:
    kind: FactSourceKind
    source_id: str                              # entity_id, analyzer_id, or plugin_id
    source_type: str | None = None
    actor_type: ApplyStepSourceActorType = "heima"   # reused as-is, including "unknown" for
                                                       # third-party-plugin-sourced facts by default
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    # actor_id deliberately omitted here unlike ApplyStepSource — facts don't carry a human actor
    # the way an admin_command/resident_response action does; add back only if a concrete need
    # surfaces (e.g. a fact produced as a side effect of a resident's explicit action)

    def as_redacted_dict(self) -> dict[str, Any]: ...   # same redaction discipline as ApplyStepSource
```

Same `correlation_id` mechanism as `ApplyStepSource` — this is what makes the unified explainability
story work: "why is the house in this state" walks one `correlation_id` chain from `HouseState`
through the `HouseFact`s that fed it (each with its `FactSource`) to any resulting `ApplyStep` (with
its `ApplyStepSource`) — one structured-source vocabulary spanning the whole causal chain, not two
systems that happen to look similar.

Deliberately **not** part of `Provenance` (confirmed 2026-08-29, see `v3_backlog.md` item 6):
- `importance` (OBSERVE/SUGGEST/ASSERT) — decorates the inference-signal *use* of a Fact, not
  every Fact. Lives on the signal wrapper, not on `Provenance` itself.
- Proposal review `status` (pending/accepted/rejected) — human governance, not epistemic trust.
  Lives on the proposal wrapper.

### Built on `HouseFact` + `Provenance`

```python
@dataclass(frozen=True)
class InferenceSignal:
    fact: HouseFact
    importance: Importance      # OBSERVE | SUGGEST | ASSERT (unchanged enum)
    valid_for: Window            # replaces bare `ttl_s: int` — reuses Timing's Window type

@dataclass
class ReactionProposal:
    fact: HouseFact              # what's being proposed, where, when detected, how confident
    status: Literal["pending", "accepted", "rejected"]
    identity_key: str            # dedup key (unchanged concept)
    fingerprint: str
    # created_at/updated_at/last_observed_at collapse into `fact.when` (first observed) +
    # a RecurrencePattern-classified history, instead of 3 separate ad hoc timestamps
```

---

## WHEN — Timing subsystem

Two data types (comparison/classification, no execution involved):

```python
@dataclass(frozen=True)
class Window:
    seconds: float
    # bounded time span — same shape serves both:
    #  - dwell ("has fact X been true for at least `seconds`")
    #  - correlation/followup ("did fact Y occur within `seconds` after fact X")
    # the two existing uses (on_dwell_s/off_dwell_s, correlation_window_s/followup_window_s)
    # differ only in which two timestamps they compare, not in shape.

@dataclass(frozen=True)
class LearnedWindow:
    # added 2026-08-31 — generalizes today's room_smart_lighting_assist-only
    # `timeout_mode: "learned"` (+ per-room-type ROOM_TYPE_DEFAULTS seeds) into a Timing-level
    # concept any Window user can opt into, not a bolt-on feature of one reaction type.
    # Same principle already decided for HouseState ("coordinate predefinite che si affinano"),
    # applied generally: seed → calibrated from observed HouseFact history over time.
    seed: Window                    # starting value (e.g. today's per-room-type defaults)
    calibrated_from: str            # fact_type to mine history from, e.g. "occupancy" sessions
    # No fixed formula specified here (e.g. percentile-of-past-durations) — an implementation
    # detail for whichever domain/FusionRule uses this, not a Timing-level policy choice.

Window | LearnedWindow  # anywhere a Window is expected, a LearnedWindow may be substituted

@dataclass(frozen=True)
class WarmupGate:
    # added 2026-09-01 (v3_backlog.md, "Learning warm-up gate" + LP-1/LP-2) — per learning subject
    # (a family/room/reaction, not global), gates whether history counts as eligible input yet.
    min_elapsed: Window   # time floor since the subject became eligible
    min_samples: int      # sample-count floor since the subject became eligible
    # AND semantics, not OR — a single-condition gate fails in a different way each: time-only lets
    # a dense test burst (e.g. an admin toggling something 20x while wiring a room) satisfy a short
    # window instantly, with exactly the data that should be excluded; sample-only lets the same
    # burst satisfy a count floor just as fast. Combined, neither a fast dense burst (fails the time
    # floor) nor a long quiet stretch with no real usage (fails the sample floor) ends the warm-up
    # window alone. "Subject became eligible at" resets via the existing `reset_learning_state()`
    # hook (already called on relevant config changes), not a new mechanism.

@dataclass(frozen=True)
class RecurrencePattern:
    weekdays: frozenset[int]      # 0-6
    hour: int | None = None       # None = any hour (interval-only pattern)
    minute: int = 0
    interval_s: float | None = None  # set instead of weekday/hour for fixed-cadence patterns
                                       # (e.g. the 300s fallback: interval_s=300, weekdays=all)
    # serves both directions:
    #  - scheduling the future ("run every Monday at 07:00", "run every 300s")
    #  - classifying the past (today's ad hoc "weekday:4:hour_bucket:9" proposal-identity keys
    #    become `RecurrencePattern(weekdays={4}, hour=9).matches(fact.when)`)
```

One execution primitive ("at"), one policy layer on top ("cron"):

```python
@dataclass(frozen=True)
class AtJob:
    job_id: str
    owner: str            # subsystem name, e.g. "house_state", "manual_hold"
    due: datetime
    label: str
    # this is what RuntimeScheduler.ScheduledRuntimeJob already is — becomes Timing's base
    # execution unit, unchanged in shape.

@dataclass(frozen=True)
class CronEntry:
    job_id: str
    owner: str
    pattern: RecurrencePattern
    label: str
    # Timing computes next `due` from `pattern` relative to now, arms an AtJob, and on fire
    # recomputes + re-arms. Absorbs:
    #  - scheduled_routine (admin-authored recurring routines)
    #  - the engine's 300s periodic fallback (owner="engine", pattern=interval_s=300) —
    #    confirmed 2026-08-29 this becomes a system-owned CronEntry, no special-casing

@dataclass(frozen=True)
class CalendarWindow:
    # added 2026-08-31 — Calendar as an extension of "at", not a domain/plugin. Same underlying
    # idea as AtJob ("something at instant T") extended to an externally-sourced, named interval
    # instead of an internally-computed point/recurrence: absolute start/end (not relative to
    # "now" like Window), classified by CalendarInterpretation, sourced from an HA calendar.*
    # entity (internal local_calendar or external — see Sensor.CalendarInterpretation).
    start: datetime
    end: datetime
    category: str          # e.g. "vacation", "day_off", "holiday", "wfh", "office"
    source_entity: str
    # Membership checks ("is `now` inside a vacation CalendarWindow") are the same temporal
    # containment operation Timing already does everywhere else — not a separate boolean-fact
    # mechanism bolted on next to it.

# Calendar sits in Layer 0 (Timing/cross-cutting), same rank as "at"/"cron" — not a Layer 4 domain,
# not a Layer 7 plugin (renumbered 2026-09-01, see v3_architecture_recap.md). It was never meant to
# go through Engine.register_plugin(); the previous
# CLAUDE.md description of Calendar as "one of the plugins ordered by dependency" is the thing to
# correct, not the code's current same-cycle, pre-core wiring.
```

---

## WHERE — `Location` and `Zone`

```python
@dataclass(frozen=True)
class Zone:
    zone_id: str
    display_name: str
    room_ids: frozenset[str]
    # flexible membership: a room's zones are found by scanning which Zones reference it,
    # not stored on Room itself. Not nestable (no Zone-of-Zones). Heima-owned; HA Label
    # registry used only as a one-time discovery/suggestion source, never a live dependency.
    # Structurally this is today's `lighting_zones` shape (zone_id/display_name/rooms),
    # promoted from lighting-only to a general Heima concept.

@dataclass(frozen=True)
class Location:
    scope: Literal["casa", "room", "zone", "rooms"]
    room_id: str | None = None     # scope == "room"
    zone_id: str | None = None     # scope == "zone"
    room_ids: frozenset[str] | None = None   # scope == "rooms" — see open question below
```

### Open question surfaced while drafting (not yet decided)

`Location.scope == "rooms"` (an ad hoc, unnamed set of room_ids) doesn't map onto any of the three
already-decided cases (`casa` / one `room` / a persisted `Zone`). It's needed because the house-state
learner already produces facts scoped to dynamically-observed room combinations (e.g. the real
example seen in `learning_audit.txt`: `rooms: bagno_piccolo,studio` for one specific learned
pattern) that are **not** stable, admin-declared Zones — they're whatever rooms happened to be
occupied together in that observation window, discovered after the fact, not defined in advance.

Two ways to resolve this:
1. Keep `Location.scope == "rooms"` as a 4th, anonymous case (as drafted above) — simplest, but
   means `Location` isn't just "a point in the topology graph," it also carries ad hoc set values.
2. Force every multi-room observation to be expressed as **whichever declared Zone's `room_ids`
   happens to match** (or as multiple single-room Facts + a separate aggregation step) — keeps
   `Location` pure ("always a real place"), but the house-state learner would need to either
   auto-create throwaway Zones for combinations nobody asked for, or lose the ability to express
   "these specific rooms together" at all when no matching Zone exists.

**Confirmed 2026-08-29: option (1).** `Location.scope == "rooms"` (ad hoc, unnamed room-id set)
stays as a 4th case, as drafted above.

---

## WHERE, part 2 — `Topology`

**Added 2026-08-31.** `Topology` is not `Location` and not `Zone` — it's a third, complementary
piece of WHERE: the **spatial relationship graph between rooms**, not a place reference and not an
admin-declared grouping. `Location` says *which* place; `Zone` says *an explicit set of rooms
someone grouped*; `Topology` says *how rooms relate to each other physically* — adjacency, openings,
connection type, orientation, floor. This is today's Room Topology model (Phase AR, already solid —
`room_topology.py`'s `TopologyGraph`/`Opening`/`Connection`/`ResolvedConnection`), carried into v3
unchanged in shape, just explicitly placed in the layer diagram instead of floating unplaced.

```python
@dataclass(frozen=True)
class Topology:
    openings: tuple[Opening, ...]              # unchanged from today
    connections: tuple[ResolvedConnection, ...] # unchanged from today
    exposure_by_room: dict[str, tuple[str, ...]] # unchanged from today
    floor_by_room: dict[str, int]
```

**Consumption**: not a fact producer or a fusion input by itself — it's **context that `FusionRule`s,
Reactions, and template requirements can query**. Concretely extends the template-matching model
(`v3_template_matching_draft.md`) with a third requirement kind alongside `SensorRequirement`/
`ActuatorRequirement`:

```python
@dataclass(frozen=True)
class TopologyRequirement:
    needs_outdoor_connection: bool = False   # e.g. cross-ventilation assist needs an operable
                                               # opening to outside
    adjacent_room_type: str | None = None     # e.g. "requires an adjacent room of type X"
```

This directly generalizes what Phase AX ("Topology-Aware Climate Reactions", in progress on a
parallel branch) is hand-building today for climate — cross-ventilation, weather-safety reactions
keyed on room adjacency/openings. Once `TopologyRequirement` exists, AX's climate reactions become a
second concrete template the generic matcher can drive, not a one-off exception — the same relation
the kitchen lighting case already validated for `SensorRequirement`/`ActuatorRequirement`.

**`Zone` suggestions derive from `Topology` — confirmed 2026-08-31.** Discovery can propose Zones
from topology structure (e.g. "these rooms share `floor_by_room`, want a Zone for them?") the same
way discovery already suggests bindings from HA registries elsewhere in this system — a suggestion
input, not a live dependency (a `Zone`, once created, is still plain Heima-owned data per the
existing decision; `Topology` just becomes one more source `discovery.py`-style suggestions can draw
from, alongside the existing HA Label registry suggestion path).
