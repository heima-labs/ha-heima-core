# Heima v3 — Domain-specific redesigns (draft shapes)

Status: **draft for discussion, not approved, not implemented.** Promotes the Lighting, Heating, and
Security redesign decisions out of backlog prose (`v3_backlog.md`, "Lighting redesign", "Heating
redesign", "Security" sections, and AR-4) into concrete shapes — the recap's own "still open" item 9
flagged this as missing. Builds on `v3_house_fact_draft.md` (`Window`/`LearnedWindow`, `HouseFact`),
`v3_sensors_actuators_draft.md` (`FusionRule`/`Interpretation`/`Bucket`), and
`v3_pattern_learner_draft.md` (`PatternLearner`).

---

## Shared shape — `PrecedenceRelation`

Lighting and (see below) the general "coarse domain default vs. precise room-level reaction"
pattern both need the same relationship: a coarse, always-available fallback and a precise mechanism
that wins where configured. Named once, reused, not decided per-domain:

```python
@dataclass(frozen=True)
class PrecedenceRelation:
    domain: str                 # e.g. "lighting", "heating" — the functional domain this governs
    coarse_source: str          # the fallback's identifier (e.g. a domain_id)
    precise_source: str         # the precise mechanism's identifier (e.g. a reaction_type)
    scope: Location              # where this relation applies — usually casa, but can be a Zone
    # Resolution rule: for a given Location, if the precise_source has a configured, enabled
    # instance covering that Location, it wins; otherwise the coarse_source's default applies.
    # This is the same relationship shape `HouseState`'s own top-level resolution order and
    # `workday_entity`'s calendar-override chain already use as a FusionRule PrecedenceStrategy
    # (v3_sensors_actuators_draft.md) — reused here at the domain-relationship level, not a new
    # concept invented for Lighting specifically.
```

---

## Lighting

### The precedence relationship

```python
PrecedenceRelation(
    domain="lighting",
    coarse_source="LightingDomain",              # house_state + zone occupancy -> intent -> scene
    precise_source="room_smart_lighting_assist",  # per-room, lux-bucket + occupancy driven
    scope=Location(scope="casa"),
)
```

Per room: if a `room_smart_lighting_assist` reaction is configured and enabled for that room,
it drives that room's lighting; otherwise `LightingDomain`'s coarse house_state -> zone -> scene
resolution applies, unchanged from today's shape. Not redundancy — two legitimate tiers that were
coexisting by historical accident, now an explicit relationship instead of two independently-evolved
mechanisms.

### Composing with Adaptive Lighting

Not a Layer 7 (third-party plugin) concern — Adaptive Lighting is an independent HA integration,
composing at the entity/service boundary, the same way `ExternalContext`'s weather adapters do. The
one real compatibility requirement: Adaptive Lighting only adapts a light when `light.turn_on` is
called *without* explicit brightness/color — an explicit-color call (today's default for
`entity_steps`) permanently disables AL for that light until manually toggled.

```python
@dataclass(frozen=True)
class EntityStepLightMode:
    mode: Literal["heima_controlled", "defer_to_external"]
    # "heima_controlled" — today's behavior, entity_steps sets brightness/color explicitly.
    # "defer_to_external" — entity_steps sends action="on" only, no brightness/color params,
    # so an external adaptive-lighting integration can still adapt that light. Per-light choice
    # on the existing entity_steps shape, not a new architectural layer.
```

### Adaptive dwell timing

`LearnedWindow` (`v3_house_fact_draft.md`) already covers this generically — today's
`timeout_mode: "learned"` + `ROOM_TYPE_DEFAULTS` bolt-on (private to
`room_smart_lighting_assist`) becomes a plain `LearnedWindow(seed=<room-type default>,
calibrated_from="occupancy")`, usable anywhere a `Window` is expected, not reinvented as a
lighting-specific feature. No new shape needed here beyond what's already drafted.

House-state-conditioned brightness (e.g. dim when `house_state == sleeping`) needs nothing new
either — it's a Reaction reading `HouseState` as one input among others, exactly the existing model.
Worth untangling `night_mode_states` (today conflates suppression and profile-selection in one
field) when this is actually built, not an architecture gap.

---

## Heating

### Reconciliation — one source of truth for the target value

```python
@dataclass(frozen=True)
class HeatingBranch:
    house_state: str                     # one of the 7 canonical HouseState values
    target_temperature: float            # the single source of truth for this branch's setpoint
    source: FactSource                   # traces whether this came from a config default or an
                                           # accepted heating_preference proposal
```

An accepted `heating_preference` `ReactionProposal` becomes the `target_temperature` **value** of
the matching `HeatingBranch`, not a standalone reaction issuing its own competing `ApplyStep`. Today's
`HeatingPreferenceReaction`/`HeatingEcoReaction` (fully independent, calling `climate.set_temperature`
directly, with zero coordination with `HeatingDomain`) are retired as separate reactions — their
learned output feeds into this one table instead. One source of truth for "what temperature this
house wants," never two competing writers on the same entity.

### What replaced "season" as the second branch dimension

The original framing ("branches keyed on `house_state` + `season`") doesn't survive AR-4's
resolution unchanged, because "season" itself dissolved into three separate, non-season-named
concepts (`v3_backlog.md`, AR-4). The second dimension `HeatingBranch` actually needs is a **bucketed
version of Part A's composite apparent-outdoor-temperature** — not a calendar season, not a discrete
weather mode:

```python
Sensor(
    entity_id="<same entity as external.outdoor_temp, or the FusionRule-derived apparent-temp fact>",
    fact_type="heating.apparent_temp_bucket",
    interpretation=BucketInterpretation(
        buckets=(Bucket("cold", 5), Bucket("mild", 15), Bucket("warm", None)),
    ),
)
```

`HeatingBranch` becomes keyed on `(house_state, apparent_temp_bucket)`, and the `heating_preference`
learning family itself is rebuilt as a `PatternLearnerConfig` (`v3_pattern_learner_draft.md`) —
`target_shape=CONTINUOUS`, tier key `("house_state", "heating.apparent_temp_bucket")` — instead of
today's bespoke `HeatingPatternAnalyzer`, per the general "every learning family becomes a
`PatternLearnerConfig`" consolidation (`v3_backlog.md`, LP-1/LP-2). This is what actually delivers
"the desired home setpoint in January and July are different values" — via a bucketed continuous
signal, not a re-invented discrete season enum.

### The thermal-response model

Already fully drafted in `v3_pattern_learner_draft.md`'s worked example (`heating_thermal_response`)
— feeds `AnomalyAnalyzer` and a `heating_setback_calibration` proposal, per AR-4 part 2B. Per-room
instances (for rooms with their own TRV/`hvac_unit` actuator) use the same
`PrecedenceRelation`/`PatternLearnerConfig` shapes with `where` scoped to that room instead of
`casa`, per AR-4's addendum — no new shape needed.

```python
PrecedenceRelation(
    domain="heating",
    coarse_source="HeatingDomain",            # whole-house target_temperature
    precise_source="room_heating_assist",     # a room's own TRV/hvac_unit actuator, if configured
    scope=Location(scope="casa"),
)
```

---

## Security

### Optional upgrade — sequential confirmation

Lower priority, not scheduled (`v3_backlog.md`, "Security" section) — composes entirely from
concepts already drafted, no new primitives:

```python
@dataclass(frozen=True)
class SequentialConfirmationPolicy:
    confirmation_window: Window          # e.g. Window(seconds=120) — EN50131-style: a second,
                                           # independent signal must arrive within this window of
                                           # the first before escalating
    unconfirmed_importance: Importance = Importance.OBSERVE   # a single evidence source alone
    confirmed_importance: Importance = Importance.ASSERT       # two independent sources within
                                                                  # the window
```

Applies to `SecurityDomain`'s existing corroboration fusion (`derived_room_evidence` +
`anonymous_presence_evidence`, already correctly using the generic `derive()`/`FusionRule`
mechanism) — today a symmetric "any" `BooleanSetStrategy`. This upgrade doesn't change the fusion
strategy; it adds a `Window`-gated staging on top, using `Importance` (already decorating
`InferenceSignal` usage, per `v3_house_fact_draft.md`) to distinguish "one source fired" from "two
independent sources corroborated within the window" before a breach candidate is treated as
verified. No new fusion strategy, no new signal type — a policy object composed from existing
`Window`/`Importance`.

---

## Not yet decided

- Whether `HeatingBranch`'s `apparent_temp_bucket` dimension needs its own `PrecedenceRelation` /
  admin-visible concept, or stays purely internal to `HeatingDomain`'s branch table — leaning
  internal (it's a computed bucket, not something an admin configures directly), not confirmed.
- Exact bucket boundaries for `heating.apparent_temp_bucket` (cold/mild/warm as drafted here are
  illustrative, not calibrated against real data).
- `night_mode_states`' suppression/profile-selection conflation (Lighting) — flagged as worth
  untangling, not resolved here; scoped to whenever Lighting's redesign is actually implemented.
