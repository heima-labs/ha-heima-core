# Heima v3 — declarative template requirements → generic proposal matching (draft shapes)

> **Historical draft.** The current V3 candidate and Reaction contracts are
> [Layer 3](specs/v3/layer3_learning_spec.md) and
> [Layer 5](specs/v3/layer5_action_reactions_spec.md); this file preserves earlier reasoning only.

Status: **historical draft, superseded by Layers 3/5, not implemented as written.** This is the idea that opened the
whole v3 conversation (the kitchen presence+lux+bulbs walkthrough): Heima should propose an
automation on its own once it has what a template needs, instead of requiring the admin to find
"Crea automazione" and fill the form by hand. Back then (see `v3_backlog.md`'s open questions) this
had no clean foundation to stand on. It does now — `Sensor`/`Actuator`/`FusionRule`
(`v3_sensors_actuators_draft.md`) and `HouseFact`/`Provenance`/`Location`/`Topology`
(`v3_house_fact_draft.md`) give every piece this needs.

---

## `TemplateRequirement` — what a template declares it needs

```python
@dataclass(frozen=True)
class SensorRequirement:
    fact_type: str            # e.g. "occupancy", "room_signal.illuminance"
    required: bool = True     # False = improves the proposal's defaults if present, never blocks it

@dataclass(frozen=True)
class ActuatorRequirement:
    role: str                  # e.g. "light", "hvac_unit"
    min_count: int = 1

@dataclass(frozen=True)
class TopologyRequirement:
    # added 2026-08-31, alongside placing Topology in Layer 1 — generalizes what Phase AX is
    # hand-building today for climate (cross-ventilation, weather-safety reactions keyed on room
    # adjacency/openings) into the same generic matching path as everything else
    needs_outdoor_connection: bool = False
    adjacent_room_type: str | None = None

@dataclass(frozen=True)
class TemplateRequirement:
    sensors: tuple[SensorRequirement, ...] = ()
    actuators: tuple[ActuatorRequirement, ...] = ()
    topology: TopologyRequirement | None = None
```

Added as an optional field on today's `AdminAuthoredTemplateDescriptor`
([registry.py:54-64](custom_components/heima/runtime/analyzers/registry.py#L54-L64)):

```python
@dataclass(frozen=True)
class AdminAuthoredTemplateDescriptor:
    template_id: str
    reaction_type: str
    title: str
    description: str
    config_schema_id: str
    implemented: bool = False
    flow_step_id: str = ""
    requirements: TemplateRequirement | None = None   # NEW — None = opt-out of auto-matching
```

`requirements is None` is how a template opts out of automatic matching entirely — no separate
enable flag needed. `room.smart_lighting_assist.basic` would declare
`SensorRequirement("occupancy")` + `SensorRequirement("room_signal.illuminance", required=False)` +
`ActuatorRequirement("light")` — matches on occupancy + a light actuator alone (matches what we
found this session: the template can't gate on darkness without a lux sensor, but occupancy +
light is still enough to be worth proposing, just with a different default — see below).

---

## The matcher

```python
def match_templates(
    locations: list[Location],
    sensors: list[Sensor],
    actuators: list[Actuator],
    topology: Topology,
    templates: list[AdminAuthoredTemplateDescriptor],
    existing_reactions: list[ReactionProposal],   # already-configured + already-rejected
) -> list[HouseFact]:
    ...
```

For each `Location` (room, and — since `FusionRule`/`Sensor`/`Actuator` all carry `where: Location`
— a `Zone` or even `casa` for house-wide templates) × each template with `requirements` declared:
check whether that `Location`'s registered `Sensor`s/`Actuator`s satisfy `requirements`. A match
that isn't already configured (same `reaction_type` + `Location`) and wasn't already rejected
(checked via `identity_key` — same dedup convention `discovery.py`'s `rejected_candidate_ids` and
the proposal engine already use elsewhere, not a new mechanism) becomes a `HouseFact`:

```
fact_type = "template_match"
where     = <the matched Location>
value     = {template_id, matched_sensor_ids, matched_actuator_ids}
how       = Provenance(confidence=1.0,
                        source=FactSource(kind="analyzer", source_id="template_matcher"),
                        evidence={...})
# source is a FactSource, never a free string (corrected 2026-09-02 — this example predated the
# 2026-08-31 Provenance.source correction and was never updated to match; see
# docs/specs/v3/layer0_runtime_spec.md §5)
```

...wrapped as a `ReactionProposal` (`status: pending`) exactly like every other proposal in this
system — no bespoke review path.

## Deriving defaults — the part that was unresolved back in the original conversation

Each template already has its own default-building function today (e.g.
`_build_admin_authored_room_smart_lighting_assist_proposal`) — the matcher calls the *same*
function, just fed from the matched `Sensor`'s `Interpretation` instead of an admin's form
submission:
- If the matched `room_signal.illuminance` sensor has a `BucketInterpretation`, default to the
  `dim` bucket with `lte` — the concrete recommendation this session settled on for the kitchen.
- If no illuminance sensor matched (only `occupancy` + `light` present, satisfying the
  `required=False` sensor as absent), default instead to `bright`/`lte` — i.e. the "always turn on
  regardless of lux" configuration this session derived by hand for the kitchen case. The matcher
  picks this automatically instead of the admin needing to reason through bucket ordering again.

This directly resolves open question #2 from the original discussion ("quale bucket/soglia di
default proporre — dipende dal room_type") — it doesn't need a room_type heuristic at all once the
matcher can see whether a lux sensor actually exists for that location.

## Volume and notification handling — ties into the (b) notifications work

Template-match proposals are exactly the shape the notifications audit flagged as missing a home
for: not urgent, not "something happened," but "N things are now possible." These get the
**`silent` quiet-hours tier** (never actively pushed) and are exactly what the still-unbuilt digest
capability (`v3_backlog.md`, Tier 1 completeness audit) is for — a periodic "N new automation
suggestions available" summary, not one notification per match. Building the matcher without the
digest capability first would just relocate the spam problem from `house_state_learned_context`
proposals to this new source — noted as a sequencing dependency, not optional.

## Extensibility note

Because this reads `Sensor`/`Actuator`/`AdminAuthoredTemplateDescriptor` generically, a future
third-party `apply`-capability plugin (`v3_backlog.md`, "Third-party plugin API") that registers
its own template with `requirements` declared participates in the same matching pass automatically
— no special-casing needed for built-in vs. external templates.

## Still open

- **Which templates get `requirements` declared first** — not every existing admin-authored
  template has been evaluated for this; needs a pass once this is built.
- **Anti-flood across templates**, beyond routing to the digest: if one `Location` satisfies 3
  templates at once, does the digest show all 3, or rank/limit them? Not decided.
