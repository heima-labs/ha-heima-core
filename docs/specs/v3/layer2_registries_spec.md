# Heima v3 — Layer 2: Registries

**Status:** Draft — pending developer approval. Not implemented.
**Layer:** 2 of 8. Builds on Layer 1 (`docs/specs/v3/layer1_substrate_spec.md` — `HouseFact`,
`Provenance`, `Location`) and Layer 0 (`docs/specs/v3/layer0_runtime_spec.md` — `Window`,
`FactSource`, Persistence). This document does not restate either contract; it assumes the reader
has them, since all three are the same v3 architecture and Layer 2 does not exist without them.

This document is self-contained with respect to Heima's v2 specs: it defines what Layer 2 is and
does without assuming the reader has read them.

## Normative precedence

This document defines the intended contract for Layer 2 once approved. Until the developer confirms
it explicitly ("ok, proceed"), it is discussion material, not an implementation target. Once approved
and implemented: if code and spec diverge, the divergence must be resolved explicitly — code is a
reference implementation, not the source of truth.

---

## 1. Purpose

Layer 2 is where raw Home Assistant entities become `HouseFact`s, and where several `HouseFact`s
become one derived `HouseFact`. Three concepts:

1. **`Sensor`** — registers exactly one HA entity as exactly one `fact_type` at exactly one
   `Location`, with an `Interpretation` that turns its raw state into a typed `HouseFact.value`.
2. **`FusionRule`** — how N `Sensor`-produced facts become one derived `HouseFact`, via one of five
   closed strategies.
3. **`Actuator`** — an inventory record of a commandable entity. Never itself a fact producer, never
   itself a command.

Layer 2 collapses **9 independently-invented entity-list mechanisms** found in the current codebase
(`occupancy_sources`, `learning_sources`, room `signals`, `house_signal_entities`,
`media_active_entities`, `sleep_charging_entities`, `work_activity_entities`,
`context_signal_entities`, and `ExternalContext`'s `{slot: entity_id}` mapping) into one registry —
each becomes a `Sensor` record distinguished by `fact_type`, not a separately-validated, separately
selected list with its own admin-panel section.

## 2. Scope

Layer 2 is responsible for:
- `Sensor` and `Interpretation` — which HA entities Heima reads, and how their raw state becomes a
  typed `HouseFact.value`;
- `FusionRule` and its five strategies — how multiple `Sensor` facts combine into one derived fact,
  and which of Layer 1's confidence functions (§4.2 of the Layer 1 spec) each strategy uses;
- the separate formula registry `FormulaStrategy` (one of the five) points into;
- `Actuator` — the commandable-entity inventory.

Layer 2 is **not** responsible for:
- the `HouseFact`/`Provenance` shape, or the confidence/availability rules that govern them — those
  are Layer 1's; Layer 2 only decides *which* rule applies to *which* producer, per Layer 1's own
  boundary (Layer 1 §4.2: "Layer 1 has no visibility into [what's being combined]... Layer 2 [does]").
- storage, timing, or provenance mechanics — Layer 0's, unchanged, consumed as-is.
- issuing commands to an `Actuator` — that is a Reaction's job (Layer 5); an `Actuator` record here is
  inventory only, never itself a command.
- domain policy that reads `Sensor`/`FusionRule` output (Layer 4) or acts on it (Layer 5).

### 2.1 Non-goals

- A generic plugin API for third-party `Interpretation`/`FusionStrategy` variants — Layer 7's
  concern, if and when it's opened; this document assumes core-team-authored registrations only,
  consistent with `PatternLearnerConfig` (Layer 3) being declared the same way.
- Redesigning the `Room`/device inventory model — `where: Location` and `device_id` reference it,
  Layer 2 does not own it (same boundary Layer 1 already states for `room_id`).

---

## 3. `Sensor`

```python
@dataclass(frozen=True)
class Sensor:
    sensor_id: str
    entity_id: str
    where: Location            # Layer 1 §5
    fact_type: str             # Layer 1 §3 naming convention — e.g. "occupancy.raw",
                                 # "room_signal.illuminance", "presence", "external.outdoor_temp"
    interpretation: Interpretation
    device_id: str | None = None   # HA device_registry id, reference only — never a live dependency,
                                     # same pattern as Zone↔Label (Layer 1 §6). Groups sibling
                                     # entities in the admin panel and powers "register one role,
                                     # suggest the others" discovery (e.g. a thermostat's Sensor role
                                     # suggests its hvac_unit Actuator role, same physical device).
    unit: str | None = None         # HA's unit_of_measurement at registration time, for numeric
                                     # fact_types. Used to detect drift (the entity's live unit no
                                     # longer matches what a BucketInterpretation's thresholds were
                                     # defined against) — never to perform unit conversion; Home
                                     # Assistant already does that, Heima only needs to know and flag
                                     # a mismatch as a diagnostic.
```

Every Home Assistant entity Heima cares about is registered exactly once, here — one registry, not
several independently-configured entity lists for different purposes (§1). `workday_entity` becomes
a `Sensor` too; its calendar-override behavior is a `PrecedenceStrategy` `FusionRule` (§5), not a
property of the sensor itself. `ExternalContext`'s slots become
`Sensor(fact_type="external.<slot>", where=Location(scope="casa"))` — the adapters behind them (OWM,
Protezione Civile) stay ordinary HA integrations exposing ordinary entities, not a Layer 7 concern.

### 3.1 `available` when the entity — or its interpretation — has nothing to report

A `Sensor` is what actually sets `Provenance.available` (Layer 1 §4.1) — this is where "there is no
real observation here" is first decided, and it is a concrete, resolved rule with two distinct
triggers, not left to each producer's discretion:

- **The entity itself is unreachable**: HA reports `unavailable`, `unknown`, or the entity does not
  exist. `available=False`, `confidence=None` (Layer 1 §4.1). The `Interpretation` (§4) is not run at
  all in this case; there is no raw state to interpret. (`value` carries no defined content here —
  Layer 1 §3 — a producer may leave it at `None`, but nothing downstream may rely on that.)
- **The entity is reachable, but its `Interpretation` cannot produce an interpretable value from what
  it read**: `available=False`, `confidence=None`, same as above. This is **not** a property every
  `Interpretation` has — `BooleanInterpretation`/`BucketInterpretation`/`MediaActivityInterpretation`/
  `PresenceInterpretation` all decode from a vocabulary HA itself defines and closes (a fixed
  `media_player`/`device_tracker` state enum, or bucket bounds that cover the entire real line by
  construction, §4) — once the entity is reachable, they always produce a value, no "can't interpret"
  case exists for them. `CalendarInterpretation` is the one exception: its vocabulary
  (`keywords`) is admin-defined and open, so a real event can legitimately match no configured
  category — and "no current event to classify" is the same case. This is *not* a value in the
  category-space `keywords` produces (there is no implicit "none" category) — it is the absence of a
  signal from this `Sensor`, which is exactly what `available=False` exists to mean, not a value to
  invent. (This is what makes `PrecedenceStrategy`'s `workday_entity` fallback, §5.1, actually work:
  it falls through to the raw entity specifically because the calendar `Sensor` reports
  `available=False` here, never because it reports some "none" value `PrecedenceStrategy` would have
  to special-case.)
- **Otherwise**: the `Interpretation` produces `available=True` with a real `value` and `confidence=1.0`
  (Layer 1 §4.2 — a raw reading is either fully trusted or absent, no in-between without a concrete
  evidentiary reason).

---

## 4. `Interpretation` — how a raw HA state becomes a `HouseFact` value

```python
@dataclass(frozen=True)
class BooleanInterpretation:
    extra_on_states: frozenset[str] = frozenset()
    # additive to the default on/off vocabulary — e.g. {"charging", "full"} for a battery-backed
    # switch whose "on" states go beyond the plain on/off HA already knows. Additive specifically so
    # a new device's quirky state name doesn't require special-casing anywhere downstream.

@dataclass(frozen=True)
class Bucket:
    label: str
    upper_bound: float | None   # None = open-ended top bucket

@dataclass(frozen=True)
class BucketInterpretation:
    buckets: tuple[Bucket, ...]         # ordered lowest to highest, e.g. dark/dim/ok/bright
    burst: Window | None = None          # Layer 0 §3.2 — "sudden bucket jump within X seconds"
    burst_direction: Literal["up", "down", "both"] | None = None

@dataclass(frozen=True)
class MediaActivityInterpretation:
    pass   # fixed, already-correct media_player vocabulary (on/playing/paused/buffering) — carried
           # forward unchanged, not reinvented

@dataclass(frozen=True)
class PresenceInterpretation:
    pass   # same shape as BooleanInterpretation, different vocabulary (device_tracker/person
           # states). Every presence entity (room-scoped or whole-house) is a Sensor with this
           # interpretation; a person's weight in group presence becomes their weight inside a
           # WeightedQuorumStrategy FusionRule (§5), not a field here.

@dataclass(frozen=True)
class CalendarInterpretation:
    keywords: dict[str, list[str]]      # category -> matching keywords
    priority_order: list[str]           # tie-break order when multiple categories match
    # keyword-matching on event summaries against admin-defined keywords. Works against any
    # calendar.* entity regardless of backing (Google Calendar, CalDAV, HA's native local_calendar)
    # — internal vs. external is a source choice, not a modeling one.

Interpretation = (
    BooleanInterpretation | BucketInterpretation | MediaActivityInterpretation
    | PresenceInterpretation | CalendarInterpretation
)
```

A closed union, five variants — consistent with how this model treats every other closed vocabulary
(`FusionStrategy` below, `RecurrencePattern`, `FactSourceKind`). A sixth variant is added the same
deliberate way `FusionStrategy` gained `FormulaStrategy` (§5.1): when a genuinely distinct decoding
pattern is found, not for a single sensor's convenience.

**Room occupancy vs. whole-house presence — same `Interpretation`/`FusionRule` shape, independently
tuned, never a shared timing policy.** Both are `Sensor(fact_type="occupancy"/"presence")` combined
by a `FusionRule` with `WeightedQuorumStrategy` (§5), but each `FusionRule` instance carries its own
`stability` (§5.2) — room occupancy keeps a fast-on/slow-off default (`Stability(to_true=None,
to_false=Window(seconds=120))`), whole-house presence can use a more conservative pair independently. They run in
separate consumers evaluated independently per cycle; reusing the same strategy *type* reuses pure
logic, not a shared blocking path or a shared timing policy.

---

## 5. `FusionRule` — how N `Sensor` facts become one derived `HouseFact`

**Genuinely separate from `Sensor`, not folded into it** — not every `Sensor` needs fusing (a
context-recording sensor can stand alone with no `FusionRule` referencing it), and not every fusion
has the same shape.

```python
@dataclass(frozen=True)
class FusionRule:
    fusion_id: str
    sensor_ids: tuple[str, ...]   # order matters for PrecedenceStrategy, irrelevant otherwise
    strategy: FusionStrategy
    produces: str                  # fact_type of the derived HouseFact
    where: Location                 # location of the derived fact — may be coarser than its
                                     # members (e.g. room occupancy derived from several
                                     # room-placed sensors, or a casa-scoped fact from several
                                     # room-scoped ones)
    stability: Window | Stability | None = None  # §5.2 — debounce/hysteresis on the *output*,
                                                   # applies regardless of which strategy produced
                                                   # it; not part of FusionStrategy itself
```

### 5.1 The five strategies

```python
@dataclass(frozen=True)
class DirectStrategy:
    pass   # 1:1 passthrough — relabels one Sensor's fact under a new fact_type/Location, unchanged

@dataclass(frozen=True)
class BooleanSetStrategy:
    mode: Literal["any", "all"]
    min_available: int = 1
    # a floor on how many configured sensor_ids must be available before this strategy reports
    # anything at all — see §5.5. Default 1 restates the general "empty population ->
    # available=False" rule with no extra requirement; raise it deliberately for a strategy where a
    # single surviving input shouldn't be trusted to speak for the rest (e.g. a 5-sensor security
    # corroboration check where 1-out-of-5 responding is a degraded read, not a confident one).

@dataclass(frozen=True)
class WeightedQuorumStrategy:
    weights: dict[str, float] = field(default_factory=dict)   # sensor_id -> weight, default 1.0
    threshold: float = 1.0
    min_available_weight: float = 0.0
    # a floor on total available weight (not configured weight) before this strategy reports
    # anything at all — see §5.5. Default 0.0 restates the general "empty population ->
    # available=False" rule with no extra requirement; a nonzero value is how a producer declares
    # "I don't trust a result computed from only a small fraction of my configured sensors" —
    # exactly the min_support-style completeness gate, kept separate from confidence itself
    # (Layer 1 §4.2), not blended into it.
    # a plain count-threshold ("at least N active") is this strategy with every weight = 1 — not a
    # separate strategy.

@dataclass(frozen=True)
class PrecedenceStrategy:
    pass   # tries sensor_ids in order, first Fact with a definitive (available) value wins — e.g.
           # HouseState's own top-level resolution order, one layer up (§5.1 continued below for
           # workday_entity, which needs care not to be misread as a flat 5-way chain)

@dataclass(frozen=True)
class FormulaStrategy:
    formula_id: str
    # Closes the "genuine calculation" gap the other four don't cover (Heating's Season derived from
    # outdoor_temp with hysteresis; a future "effective outdoor temperature" from temp+wind+humidity)
    # — carries no calculation logic itself, only a reference into a separate, core-team-curated
    # formula registry (§5.3), so a new formula never requires reopening this union or any code that
    # pattern-matches on it. Resolved 2026-09-02, v3_backlog.md, closing AR-4.

FusionStrategy = (
    DirectStrategy | BooleanSetStrategy | WeightedQuorumStrategy | PrecedenceStrategy | FormulaStrategy
)
```

A closed union of five — not an open-ended plugin registry (an earlier draft of the architecture
recap described it as one; corrected, `v3_backlog.md`, AR-4 follow-up). Exhaustive pattern-matching
on `FusionStrategy` is a real property every consumer can rely on; the one extension point is
`FormulaStrategy`'s own registry (§5.3), not the union itself.

**`workday_entity`, worked through precisely — two mechanisms at two levels, not one flat chain.**
The recurring shorthand for this case ("office > day_off > holiday > wfh > raw entity") reads like a
single 5-way `PrecedenceStrategy` and is easy to misimplement as one. It isn't: `CalendarInterpretation`
(§4) already takes a `keywords: dict[str, list[str]]` — multiple categories handled by **one**
`Sensor`, with its own `priority_order` breaking ties when one event's text matches more than one
category's keywords. `PrecedenceStrategy` solves a different problem — falling back to a different
*Sensor* when one has nothing to say — not classifying ambiguity within one. The correct shape is
**one** `Sensor` with a `CalendarInterpretation` whose `keywords`/`priority_order` resolve
office/day_off/holiday/wfh internally, and **one** `FusionRule(strategy=PrecedenceStrategy())` with
exactly two `sensor_ids`: that calendar-derived `Sensor`, then the raw `workday_entity` `Sensor` as
the fallback when the calendar `Sensor` produces no match (`available=False`) at all. Four Sensors
feeding a flat 5-item precedence chain would work mechanically too, but would leave
`CalendarInterpretation.priority_order` doing nothing for this case — a sign the modeling is wrong,
not just a stylistic choice between two equally-valid shapes.

### 5.2 Stability is orthogonal to strategy

Dwell/hysteresis (`FusionRule.stability`) applies to the **output**'s stability over time,
independent of which strategy produced it — debounce and hysteresis are a property of *any* derived
fact settling before it's trusted, not specific to one combination method. It composes with all five
strategies identically; `FusionStrategy` itself carries no timing concept.

**Asymmetric by default need, not just by option — a single `Window` cannot express "instant on,
debounced off."** A room's light triggered by presence must turn on the instant presence is
detected, never after a dwell delay (the room would sit dark for no reason); the same fact should
often *not* revert to vacant on the first gap in motion, to avoid flicker from an ordinary pause.
This asymmetry is already real and working in today's code (`on_dwell_s=0`, `off_dwell_s=120s` for
room occupancy) — a single symmetric `stability: Window` would either delay the light turning on
(reintroducing exactly the problem it must not have) or drop hysteresis on the off-transition
entirely. For strategies with a natural true/false polarity (`BooleanSetStrategy`,
`WeightedQuorumStrategy` used with a boolean threshold):

```python
@dataclass(frozen=True)
class Stability:
    to_true: Window | None = None    # e.g. None — a presence-triggered light turns on instantly
    to_false: Window | None = None   # e.g. Window(seconds=120) — debounce the off-transition
```

`FusionRule.stability: Window | Stability | None` — a plain `Window` (or `None`, no dwell at all)
still covers strategies without a boolean polarity (`FormulaStrategy`'s numeric output settling,
`DirectStrategy`/`PrecedenceStrategy` passing through a non-boolean value) with symmetric dwell in
both directions; `Stability` is available specifically where "toward more active" and "toward less
active" are genuinely different questions. Not generalized further (e.g. per-transition dwell across
an N-valued bucket label) — no concrete need for that exists today; the same discipline already
applied to `FusionStrategy`'s own five members, add complexity when a real case demands it, not ahead
of one.

**The mechanism, concretely — not just "debounce happens," but how.** Every cycle, a `FusionRule`
computes its raw candidate value from current `Sensor` facts per its strategy, exactly as if
`stability` were absent. This candidate is compared against the value of the last derived `HouseFact`
this `FusionRule` actually **committed** (wrote):

- If the candidate matches the last committed value: nothing to do, no new fact (Layer 0's
  write-on-change policy already covers this).
- If the candidate differs and no transition is currently pending toward it: start tracking one — a
  small, **ephemeral, in-memory** `(pending_value, pending_since)` pair, per `FusionRule` instance.
  Not persisted, not restart-safe, and deliberately so — nothing here carries a safety consequence
  that would justify surviving a restart (Layer 0 §0's general default: state starts clean unless a
  concrete reason says otherwise), and a fresh restart correctly begins with a full dwell period
  before committing anything, consistent with Recovery's own `startup_recovery` caution (Layer 0 §7).
- If the candidate matches an already-pending transition: check the applicable window (`to_true`,
  `to_false`, or the plain `stability` `Window`, whichever applies to this transition's direction) —
  computed live against `pending_since`, the same monotonic-safe elapsed-time discipline as every
  other `Window` comparison in this architecture (Layer 0 §3.2), never cached as a stored "is it
  stable yet" flag. If the window has elapsed (or is `None`, meaning no dwell at all — instant),
  commit: write the new `HouseFact` (`value`/`available`/`confidence` computed fresh at commit time,
  not stale from when the candidate first appeared), clear the pending state.
- If the candidate reverts to match the currently-committed value before its pending window elapses:
  discard the pending transition entirely — this is what makes it real debounce, not just a delay: a
  brief flicker never commits and never leaves a trace, exactly like today's working dwell logic.

### 5.3 The formula registry

```python
FormulaId = str   # e.g. "heating.season_hysteresis", "external.effective_outdoor_temperature"

@dataclass(frozen=True)
class RegisteredFormula:
    formula_id: FormulaId
    min_inputs: int                                                     # formula-specific — Season's
                                                                          # hysteresis needs 1, an
                                                                          # "effective temperature"
                                                                          # might need 2 of 3
    compute: Callable[[Sequence[HouseFact]], tuple[Any, float] | None]  # inputs -> (value, dispersion),
                                                                          # or None — see below
    scale: float
    floor: float
```

`compute` returns `None`, not a degenerate tuple, when it cannot produce a value from what it was
given — the caller passes only the currently-`available` inputs (§5.5's exclusion rule applies here
too), and calls `compute` at all only if their count already meets `min_inputs`; below that floor,
the derived `HouseFact` is `available=False` without ever calling `compute`. `None` from `compute`
itself covers a rarer case: enough inputs were available by count, but the specific combination
still can't yield a sound value (formula-specific — e.g. inputs technically present but mutually
contradictory in a way the formula itself is positioned to detect, not something a bare input count
can catch in advance). Either path — the count check or `compute` returning `None` — ends the same
way: `available=False`, no call to `continuous_confidence`.

Core-team-curated, not admin-authored and not (today) open to third parties — same governance as
`PatternLearnerConfig` (Layer 3: "declared in code only... no learning family is admin-authored
today"). A `FormulaStrategy(formula_id=...)` looks up its `RegisteredFormula` here; the registry can
grow without ever touching `FusionStrategy` or the code that pattern-matches on it. Mirrors
`NormalizationFusionRegistry`'s existing plugin pattern in the current codebase — not a new
mechanism, the same one, given an explicit home in this model.

### 5.4 Confidence per strategy — the mapping Layer 1 deferred here, now closed

Layer 1 (§4.2) owns three pure confidence functions and one non-computation option, and states that
*which* applies to a given producer is Layer 2's decision. Resolved for all five strategies:

| Strategy | Confidence treatment |
|---|---|
| `DirectStrategy` | Inherit — the single source's own `confidence`, unchanged. |
| `WeightedQuorumStrategy` | `categorical_confidence(winning_weight, total_weight_considered)` — the same-cycle votes *are* the "observations" (Layer 1 §4.2's `total_observations` is deliberately general for exactly this). `winning_weight` is the weight backing whichever outcome is actually being reported — the weight *for* threshold if it was reached, the remaining weight *against* it if it wasn't (`total_weight_considered - winning_weight` in that case) — never always the "for" side regardless of which way the vote went. `total_weight_considered` excludes any `available=False` input entirely (§5.5). |
| `PrecedenceStrategy` | Inherit — the first definitive (available) source's own `confidence`; if every `sensor_ids` entry is `available=False`, none wins and the derived fact is itself `available=False` (§5.5), following directly from the strategy's own definition. |
| `FormulaStrategy` | `continuous_confidence(dispersion, scale, floor)` — always, by construction, since a formula combines multiple continuous inputs into one derived value; `scale`/`floor` come from the formula's own `RegisteredFormula` entry (§5.3). |
| `BooleanSetStrategy` | `combined_confidence(...)` — see below, the one genuinely new case. |

**`BooleanSetStrategy`, worked out from Layer 1's `combined_confidence` (§4.2), by De Morgan
symmetry across the outcome branch:**

- `mode="all"`, outcome `True` (a conjunction — every considered source agreed): `combined_confidence`
  over **all** considered sources' `confidence`, `combinator="min"` — an AND is only as trustworthy
  as its weakest agreeing premise.
- `mode="all"`, outcome `False` (equivalent to "at least one disagreed" — a disjunction over the
  dissenting sources): `combined_confidence` over the **dissenting** sources' `confidence`,
  `combinator="max"`.
- `mode="any"`, outcome `True` (a disjunction over the confirming sources): `combined_confidence` over
  the **confirming** sources' `confidence`, `combinator="max"` — an OR is as trustworthy as its
  strongest confirmation.
- `mode="any"`, outcome `False` (equivalent to "none confirmed" — a conjunction over all considered
  sources): `combined_confidence` over **all** considered sources' `confidence`, `combinator="min"`.

### 5.5 `available=False` inputs never enter a fusion's confidence computation

For every strategy above, a `Sensor`-produced input with `available=False` (§3.1) is **excluded**
from whichever population feeds the confidence computation — never treated as a "False" vote for
`BooleanSetStrategy`, never contributing weight to `WeightedQuorumStrategy`'s total. If excluding
unavailable inputs leaves nothing to combine (every relevant input is `available=False`), the derived
`HouseFact` is itself `available=False`, and no confidence function is called at all (Layer 1 §4.2's
"no meaningful confidence for nothing observed" rule, inherited here without exception).

**Excluding unavailable inputs can leave *something* to combine while still leaving too little to
trust — a distinct problem from the empty-population case, with its own gate, not folded into
`confidence`.** If 4 of a `WeightedQuorumStrategy`'s 5 configured sensors go `available=False`
simultaneously (a Zigbee segment losing power, say), the remaining one sensor's vote is not "empty" —
`categorical_confidence` would happily compute a confident-looking ratio from it alone, even though
almost nothing was actually observed. This is exactly the distinction Layer 1 §4.2 already draws for
`min_support` — "enough data to trust this at all" is a separate boolean gate from "how much the data
agrees" — applied here to input *completeness* rather than sample count: `min_available_weight`
(`WeightedQuorumStrategy`) and `min_available` (`BooleanSetStrategy`), both declared alongside their
strategy (§5.1). Below the floor, the derived `HouseFact` is `available=False` — same outcome as the
fully-empty case, same reason, just a less extreme trigger — never a technically-correct but
misleadingly confident number computed from a handful of survivors. This is deliberately a **local**
gate, per `FusionRule`, not a duplicate of Recovery's system-wide `degraded_recovery` classification
(Layer 0 §7.1): Recovery's classification is about the overall runtime, and would not necessarily
fire when only this one `FusionRule`'s specific inputs are affected while the rest of the house's
entities are fine — the two operate at different granularities and are not meant to substitute for
each other.

---

## 6. `Actuator`

`Actuator`'s existing principle — inventory fact only, never a command — is unchanged:

```python
@dataclass(frozen=True)
class Actuator:
    actuator_id: str
    entity_id: str
    where: Location
    opening_id: str | None = None       # which physical opening this actuator operates, when
                                          # applicable (a shutter) — a mechanical sub-detail of a
                                          # room-scoped actuator, not a WHERE tier of its own
    display_name: str | None = None
    actuator_role: str | None = None    # coarse role: light, shutter, hvac_unit, water_valve...
    device_id: str | None = None        # same HA device_registry reference as Sensor.device_id
                                          # (§3), for panel grouping + sibling-role discovery
```

Two concrete changes from today's model, both already decided, restated here for completeness:
`light` is added to the set of valid roles (today lights bypass the registry entirely, duplicated as
raw `entity_id`s inside every reaction's `entity_steps`); `room_id`/`opening_id` collapse into
`where: Location` for the same reason `Sensor` uses it — one shared WHERE representation instead of
each registry inventing its own room-reference shape.

Commands live only in whichever Reaction (Layer 5) decides to send them — `Actuator` never issues
one itself, and nothing in Layer 2 reads or writes actuator state beyond this inventory record.

---

## 7. Relationship to Layer 0 and Layer 1

- **`HouseFact`/`Provenance` shape**: every `Sensor` and `FusionRule` produces plain `HouseFact`s per
  Layer 1's contract — Layer 2 adds no new envelope, no parallel representation.
- **Confidence functions**: called, never reimplemented (§5.4) — Layer 2's only job is picking which
  Layer-1-owned function applies and supplying its inputs, per the split Layer 1 §4.2 establishes.
- **Storage/timing**: every produced `HouseFact` goes through Layer 0's Persistence and Timing
  exactly as any other fact. `FusionRule.stability` (§5.2) is the one Layer-2-specific addition on
  top: `Window`/`Stability` themselves are comparison values (`Stability` composed of two
  `Window`s), reusing Layer 0's own elapsed-time discipline (§3.2) for the actual check — but the
  pending-transition *tracking* that debounce requires (which candidate is pending, since when) is
  new here, not something Layer 0's `Window` type provides on its own. Every `Window`-typed field in
  this document (`BucketInterpretation.burst`, `FusionRule.stability`, `Stability.to_true`/`to_false`)
  accepts a `LearnedWindow` in its place, per Layer 0 §3.2's general substitution rule — not
  restated at each field individually.
- **`FactSource`**: a `Sensor`-produced fact carries `kind="sensor"` — a direct single-entity read.
  A `FusionRule`-produced fact carries `kind="analyzer"`, per Layer 0 §5's now-precise definition
  ("derived from combining or analyzing existing data rather than one direct entity read" —
  `FusionRule` qualifies by that property regardless of being same-cycle and deterministic, not by
  being statistical; this was genuinely ambiguous before Layer 0 §5 got per-value definitions,
  resolved 2026-09-03, `v3_backlog.md`). `source_id` is the `sensor_id`/`fusion_id`.

Layer 2 depends on both Layer 0 and Layer 1; nothing in either depends on anything defined here.

---

## 8. Not yet decided

- **Exact `fact_type` migration mapping for the 9 collapsed entity-list mechanisms** (§1) — a
  concrete per-list mapping table, not an architectural question, to be worked out when this moves
  toward implementation.
- **`BooleanSetStrategy`'s exclusion policy for `available=False` inputs (§5.5) is the only policy
  considered here, not weighed against alternatives.** An alternative (treating an unavailable input
  as an implicit "False" vote for `mode="all"`, since "we don't know, so we can't confirm all agree")
  was not evaluated in depth — exclusion was chosen for consistency with `WeightedQuorumStrategy`'s
  same treatment, not because the alternative was ruled out on its own merits. Worth a second look if
  a concrete case surfaces where exclusion produces a surprising result.
- **The formula registry's exact registration mechanism** (§5.3) — declared in code only, by analogy
  with `PatternLearnerConfig`, but no concrete registration API is specified here.
- **Whether `Interpretation`/`FusionStrategy` ever open to third-party registration** (§2.1) — tied to
  the same still-open "no backward compatibility vs. a plugin API" tension already on record for
  Layer 7; not decided here, deliberately out of scope for this document.
- **Where a `FusionRule`'s pending-transition state (§5.2) actually lives** — a distinct
  Layer-2-owned ephemeral structure, or grown out of Layer 0's existing short-term in-memory buffer
  (Layer 0 §4.1)? Both are consistent with "ephemeral, not restart-safe"; which one is a mechanical
  choice not made here.

---

## 9. Acceptance criteria (for the eventual implementation phase)

- All 9 entity-list mechanisms named in §1 are removed from the codebase, replaced by `Sensor`
  registrations with no residual parallel list left standing.
- Every `Sensor` sets `available=False`/`confidence=None` exactly per §3.1's rule, in a test that
  forces each of an unreachable entity (`unavailable`, `unknown`, nonexistent entity_id) and, for a
  `CalendarInterpretation` `Sensor` specifically, a reachable entity whose current event matches no
  configured category.
- Every `FusionRule` strategy's confidence is computed exactly per the §5.4 table — called through
  Layer 1's pure functions, never reimplemented — verified for all five strategies including both
  outcome branches of `BooleanSetStrategy`.
- A `FusionRule` with every input `available=False` produces an `available=False` output without
  calling any confidence function, for at least one instance of each strategy.
- A `WeightedQuorumStrategy`/`BooleanSetStrategy` `FusionRule` below its configured
  `min_available_weight`/`min_available` — some inputs available, but not enough — produces
  `available=False`/`confidence=None` without calling `categorical_confidence`/`combined_confidence`,
  distinct from and in addition to the fully-empty case above.
- `RegisteredFormula.compute` returning `None`, and a `FusionRule` below a `FormulaStrategy`'s
  `min_inputs`, both produce `available=False` without calling `continuous_confidence`.
- A `Stability(to_true=None, to_false=Window(seconds=N))` `FusionRule` commits a transition to
  `True` the same cycle the candidate first appears, and a transition to `False` only after the
  candidate has held for `N` seconds — with a test that flips back to `True` mid-window and verifies
  the pending transition is discarded, never partially applied.
- `FormulaStrategy` additions (a new `RegisteredFormula` entry) require no change to `FusionStrategy`
  or to any code that pattern-matches on it, verified by adding a second formula in a test without
  touching the union type.
- `Actuator`'s `light` role is a valid `actuator_role`, and no reaction's `entity_steps` duplicates a
  raw light `entity_id` outside the registry.

---

## Related documents (background only, not required reading)

This spec incorporates and formalizes decisions originally captured in this planning branch's own
`v3_sensors_actuators_draft.md` (Layer A/B, Actuator), `v3_architecture_recap.md` (Layer 2), and
`v3_backlog.md` (the Sensor/FusionRule/Actuator grounding pass, AR-4's `FormulaStrategy` resolution,
and the `combined_confidence` correction). Where this document and any of those differ, this document
is the current word for Layer 2's v3 design.
