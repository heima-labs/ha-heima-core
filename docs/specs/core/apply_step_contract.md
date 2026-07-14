# ApplyStep Contract

**Status:** Implemented runtime contract

`ApplyStep` is the canonical runtime unit for actions that Heima plans and may execute.

```python
ApplyStep(
    domain="switch",
    target="switch.front_door_privacy",
    action="switch.turn_off",
    params={"entity_id": "switch.front_door_privacy"},
)
```

## Field Semantics

| Field | Meaning |
|---|---|
| `domain` | Heima execution domain or HA service domain for this step. |
| `target` | Heima logical subject of the step. Used for diagnostics, filtering, manual hold scope resolution, and domain-specific routing. |
| `action` | Fully-qualified action, usually `<domain>.<service>`. |
| `params` | Concrete service parameters. For HA entity actions, this must include the HA `entity_id` that will be passed to the service call. |

## Step Dependencies (vNext)

Most `ApplyStep` lists are unordered independent plans: if one step is blocked by manual hold or an
apply filter, unrelated surviving steps may still run.

Reaction families that need ordered semantics must declare dependencies explicitly instead of
relying on list order.

Conceptual optional metadata:

```python
ApplyStep(
    domain="light",
    target="studio",
    action="light.turn_on",
    params={"entity_id": "light.studio_desk", "brightness_pct": 10},
    step_id="studio_desk_dim",
    depends_on=["studio_scene_prepare"],
)
```

Rules:

- `step_id` is unique inside the emitted plan.
- `depends_on` contains `step_id` values from the same plan.
- The runtime must not infer dependencies from list order.
- If a dependency is blocked, skipped, or failed, the dependent step must be skipped.
- Dependency skipping is reported separately from manual hold blocking so diagnostics can explain
  that the step was not attempted because a prerequisite did not run.
- Domains that require all-or-nothing behavior must declare that separately; dependencies only skip
  downstream steps whose prerequisites did not run.

## `target` vs `params.entity_id`

`target` and `params.entity_id` are intentionally separate.

For direct HA entity actions, they usually match:

```json
{
  "domain": "switch",
  "target": "switch.front_door_privacy",
  "action": "switch.turn_off",
  "params": {
    "entity_id": "switch.front_door_privacy"
  }
}
```

In this form:

- `target` identifies the entity as Heima's logical subject.
- `params.entity_id` is the concrete HA service parameter used by execution.

For Heima domain-specific steps, they can differ:

```json
{
  "domain": "lighting",
  "target": "studio",
  "action": "scene.turn_on",
  "params": {
    "entity_id": "scene.studio_evening"
  }
}
```

In this form:

- `target` is the Heima subject, here the room `studio`.
- `params.entity_id` is the concrete HA entity to call, here the scene.

## Authoring Rule

When authoring `light`, `switch`, `input_boolean`, or `climate` entity actions, set
`target` and `params.entity_id` to the same entity unless a domain-specific contract explicitly
documents a different `target`.

Domain-specific steps may use `target` for a room, zone, reaction, or other Heima subject while
placing the HA entity in `params.entity_id`.
