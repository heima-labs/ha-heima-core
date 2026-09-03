# Heima v3 — Sensor Registry, Fusion, and Actuator (draft shapes)

Status: **draft for discussion, not approved, not implemented.** Builds on `v3_house_fact_draft.md`
(`HouseFact`, `Location`, `Window`). Grounded in the analysis in `v3_backlog.md` — two layers, not
one flat list; 3 existing fusion strategies confirmed properly generalized, 1 missing
(Precedence), 2 apparent "special cases" found to be integration gaps, not missing capabilities.

---

## Layer A — `Sensor`

```python
@dataclass(frozen=True)
class Sensor:
    sensor_id: str
    entity_id: str
    where: Location            # WHERE, from v3_house_fact_draft.md
    fact_type: str             # namespaced: "occupancy.raw", "room_signal.illuminance",
                                # "context_signal", "house_signal.sleep_window",
                                # "external.outdoor_temp", "presence", etc.
    interpretation: Interpretation
    device_id: str | None = None   # added 2026-08-31 — HA's own device_registry id, reference
                                     # only (never a live dependency, same pattern as Zone↔Label/
                                     # Zone↔Topology). Groups sibling entities in the panel UI and
                                     # powers "register one role, suggest the others" discovery.
    unit: str | None = None         # added 2026-08-31 — HA's unit_of_measurement at registration
                                     # time, for numeric fact_types. Used to detect drift (the
                                     # entity's live unit no longer matches what buckets/thresholds
                                     # were defined against), not to perform unit conversion —
                                     # HA already does that; Heima just needs to know and flag.
```

Collapses all **9** of today's separate entity-lists (`occupancy_sources`, `learning_sources`, room
`signals`, `house_signal_entities`, `media_active_entities`, `sleep_charging_entities`,
`work_activity_entities`, `context_signal_entities`, and `ExternalContext`'s `{slot: entity_id}`
mapping, found in the 2026-08-31 external review pass) into one registry — each becomes a set of
`Sensor` records distinguished by `fact_type`, not a separately-validated, separately-selected list.
`workday_entity` becomes a `Sensor` too, but its calendar-override behavior is a `Precedence`
`FusionRule` (below), not a property of the sensor itself. `ExternalContext`'s slots become
`Sensor(fact_type="external.<slot>", where=Location(scope="casa"))`; its adapters (OWM, Protezione
Civile) stay ordinary HA integrations exposing ordinary entities — not a Layer-6 (third-party
plugin) concern.

### `Interpretation` — how a raw HA state becomes a `HouseFact` value

```python
@dataclass(frozen=True)
class BooleanInterpretation:
    extra_on_states: frozenset[str] = frozenset()
    # today's InputNormalizer.boolean_signal(extra_on_states=...) — e.g. {"charging", "full"}
    # additive to the default vocabulary, per the sleep-normalizer fix precedent

@dataclass(frozen=True)
class Bucket:
    label: str
    upper_bound: float | None   # None = open-ended top bucket

@dataclass(frozen=True)
class BucketInterpretation:
    buckets: tuple[Bucket, ...]         # ordered lowest to highest, e.g. dark/dim/ok/bright
    burst: Window | None = None          # reuses Timing's Window — "sudden bucket jump within X"
    burst_direction: Literal["up", "down", "both"] | None = None

@dataclass(frozen=True)
class MediaActivityInterpretation:
    pass   # fixed, already-correct media_player vocabulary (on/playing/paused/buffering) —
           # media_activity.py's existing logic, not reinvented

@dataclass(frozen=True)
class PresenceInterpretation:
    pass   # added 2026-08-31 — today's InputNormalizer.presence() vocabulary (device_tracker/
           # person states), same shape as BooleanInterpretation, different vocabulary. Every
           # presence entity (room or whole-house) is a Sensor with this interpretation; a
           # person's `presence_rule` (observer/resident/recurrent) becomes their weight in a
           # WeightedQuorumStrategy FusionRule, not a new field here.

@dataclass(frozen=True)
class CalendarInterpretation:
    # added 2026-08-31 — today's CalendarDomain._classify() vocabulary: keyword-matching on event
    # summaries against admin-defined keywords, with a priority order for conflicts. Works against
    # any calendar.* entity regardless of backing (Google Calendar, CalDAV, HA's native
    # local_calendar) — internal vs. external is a source choice, not a modeling one.
    keywords: dict[str, list[str]]      # category -> matching keywords
    priority_order: list[str]           # tie-break order when multiple categories match

Interpretation = (
    BooleanInterpretation | BucketInterpretation | MediaActivityInterpretation
    | PresenceInterpretation | CalendarInterpretation
)
```

**Room occupancy vs. whole-house presence — same `Interpretation`/`FusionRule` shape, independently
tuned, never a shared timing policy.** Both are `Sensor(fact_type="presence"/"occupancy")` combined
by a `FusionRule` with `WeightedQuorumStrategy`, but each `FusionRule` instance carries its own
`Window` (dwell/hysteresis) — room occupancy keeps today's existing default (`on_dwell_s=0`,
instant-on; `off_dwell_s=120s`, debounced-off, already real in `_steps_rooms.py`), whole-house
presence can use a more conservative `Window` independently. They already run in separate DAG
domains today (`OccupancyDomain` vs. `PeopleDomain`), evaluated independently per cycle — reusing
the same strategy *type* is reusing pure logic, not sharing a blocking path or a timing policy.

---

## Layer B — `FusionRule` (how N `Sensor` facts become 1 derived `HouseFact`)

**Confirmed genuinely separate from Layer A** — not every Sensor needs one (context-recording
sensors like today's `learning_sources`/`context_signal_entities` have none at all).

```python
@dataclass(frozen=True)
class FusionRule:
    fusion_id: str
    sensor_ids: tuple[str, ...]   # order matters for Precedence, irrelevant otherwise
    strategy: FusionStrategy
    produces: str                  # fact_type of the derived HouseFact
    where: Location                 # location of the derived fact (may be coarser than members —
                                     # e.g. room occupancy derived from several room-placed sensors)
```

### The 4 strategies (3 confirmed existing + 1 missing, found by grounding against real domains)

```python
@dataclass(frozen=True)
class DirectStrategy:
    pass   # 1:1 passthrough — DirectFusionPlugin, unchanged

@dataclass(frozen=True)
class BooleanSetStrategy:
    mode: Literal["any", "all"]
    # BooleanSetFusionPlugin, unchanged. Confirmed correctly reused today by: OccupancyDomain
    # (any_of/all_of), security corroboration (security.py:341-367, "any"-shaped despite the
    # different name), PeopleDomain group presence.

@dataclass(frozen=True)
class WeightedQuorumStrategy:
    weights: dict[str, float] = field(default_factory=dict)   # sensor_id -> weight, default 1.0
    threshold: float = 1.0
    # WeightedQuorumFusionPlugin, unchanged. Confirmed correctly reused today by: OccupancyDomain
    # (weighted_quorum), PeopleDomain group presence (quorum/weighted_quorum).
    # A plain count-threshold ("at least N active") is this strategy with every weight = 1 —
    # NOT a separate strategy. house_state.py's `_compute_boolean_count_evidence`
    # (sleep_charging_min_count) and `_compute_media_active` ("any active") currently bypass
    # `derive()` and reimplement this by hand — that's a migration to do (route them through this
    # existing strategy), not new capability to build.

@dataclass(frozen=True)
class PrecedenceStrategy:
    pass
    # NEW — the one genuine gap found. Tries `sensor_ids` in order, first Fact with a definitive
    # (non-unknown/unavailable) value wins. Needed today by `workday_entity`'s calendar-override
    # chain (office > day_off > holiday > wfh > raw entity), currently hand-rolled in
    # `_compute_workday_evidence`. Same shape, one level up, as HouseState's own top-level
    # resolution order (manual override > vacation > guest > away > home-substates) — currently
    # also hand-rolled in `_resolve_home_substate`. Both should express as a `PrecedenceStrategy`
    # once this exists, instead of two separate ad hoc implementations of the same idea.

@dataclass(frozen=True)
class FormulaStrategy:
    formula_id: str
    # Resolved 2026-09-02 (v3_backlog.md, AR-4 follow-up) — closes the "genuine calculation" gap
    # (Heating's Season derived from outdoor_temp with hysteresis; a future "effective outdoor
    # temperature" from temp+wind+humidity) that the other 4 strategies don't cover, without
    # reopening this union for every future calculation. Carries no calculation logic itself — only
    # a reference into a separate, core-team-curated formula registry, mirroring
    # NormalizationFusionRegistry's existing plugin pattern (already precedented in the current
    # codebase, per the Layer 7 fault-isolation discussion in v3_backlog.md) — a new formula is a
    # new registry entry, never a change to FusionStrategy or to code that pattern-matches on it.
    # Always continuous-shaped by definition (a formula combines multiple continuous inputs into one
    # derived value) — its confidence always uses Layer 1's `continuous_confidence`, with dispersion
    # computed however the specific registered formula defines it, the same way a
    # `PatternLearnerConfig` supplies its own `continuous_params`.

FusionStrategy = (
    DirectStrategy | BooleanSetStrategy | WeightedQuorumStrategy | PrecedenceStrategy | FormulaStrategy
)
```

Dwell/hysteresis (today's `on_dwell_s`/`off_dwell_s`) is **not** part of `FusionStrategy` — it's a
`Window` (Timing) applied to the *stability* of a `FusionRule`'s output over time, not to how the
inputs combine. Composes cleanly with any of the 4 strategies rather than being its own case.

---

## Actuator — extended, not redesigned

`Actuator`'s existing principle (inventory fact only, never a command —
[actuators.py:1-7](custom_components/heima/runtime/actuators.py#L1-L7)) stays exactly as is. Two
concrete changes:

1. **Add the missing `light` role** to `VALID_ACTUATOR_ROLES` — today lights bypass the registry
   entirely, duplicated as raw `entity_id`s inside every reaction's `entity_steps`.
2. **`room_id`/`opening_id` become `where: Location`**, for the same reason Sensor uses it — one
   shared WHERE representation instead of each registry inventing its own room-reference shape.
   `opening_id` stays as its own field (a mechanical sub-detail of a room-scoped actuator — which
   physical opening a shutter operates — not a WHERE tier of its own).

```python
@dataclass(frozen=True)
class Actuator:
    actuator_id: str
    entity_id: str
    where: Location
    opening_id: str | None = None
    display_name: str | None = None
    actuator_role: str | None = None   # VALID_ACTUATOR_ROLES + "light"
    device_id: str | None = None        # added 2026-08-31 — same HA device_registry reference as
                                          # Sensor.device_id, for panel grouping + sibling-role
                                          # discovery (e.g. a thermostat's Sensor role suggests
                                          # its hvac_unit Actuator role, same physical device)
```
