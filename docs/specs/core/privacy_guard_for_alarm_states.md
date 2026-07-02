# Camera Privacy Guard for Alarm States

**Status:** Implemented on `feat/v2` via Manual Hold Framework  
**Last audited:** 2026-06-25  
**Phase:** AE — Camera Privacy Guard & Extensible Entity Actions
**UI follow-up:** `camera_privacy_policy_ui_spec.md`

## Purpose

Extend the existing manual-hold pattern to camera privacy actions generated from alarm-state
semantic policies.

The intended end state is:

- Heima can propose camera privacy actions when the alarm enters `armed_night`.
- Camera privacy actions can turn privacy either on or off per configured camera source.
- Automatic entity actions are blocked while the matching manual hold is active.
- Alarm-state actions can be skipped for selected house states such as `guest` and `vacation`.

## Current Implementation Summary

This audit reflects the code currently on `feat/v2`.

| Slice | Status | Notes |
|---|---|---|
| AE1 — manual hold framework | Implemented | Runtime blocking is now owned by `ManualHoldManager`; the previous `EntityReactionGuardBehavior` was removed. |
| AE2 — camera source fields | Implemented | `privacy_entity`, `privacy_action`, and `manual_hold_entity` are accepted and validated. `privacy_entity` alone is allowed. |
| AE3 — house-state filters | Implemented | `AlarmStateActionReaction` normalizes and honors `skip_house_states` and `only_house_states`. |
| AE4 — camera privacy semantic rule | Implemented | `alarm_night_camera_privacy` emits switch steps for configured `privacy_entity` values, honors `privacy_action`, and includes `skip_house_states=["guest", "vacation"]`. |
| AE5 — verification | Implemented | Full pytest passed: `1546 passed` on 2026-06-25. Ruff check/format on touched files passed. Full `scripts/ci_local.sh` was not rerun during this slice. |

## Camera Evidence Sources Contract

Each item in `security.camera_evidence_sources` supports:

| Field | Required | Type | Implemented | Description |
|---|---:|---|---:|---|
| `id` | Yes | string slug | Yes | Unique camera source identifier. |
| `role` | Yes | string | Yes | Camera role, e.g. `entry`, `garage`, `perimeter`. |
| `motion_entity` | No | `binary_sensor.*` | Existing | Motion evidence entity. |
| `person_entity` | No | `binary_sensor.*` | Existing | Person evidence entity. |
| `vehicle_entity` | No | `binary_sensor.*` | Existing | Vehicle evidence entity. |
| `contact_entity` | No | `binary_sensor.*` | Existing | Contact evidence entity. |
| `privacy_entity` | No | `switch.*` | Yes | Privacy-control switch target. |
| `privacy_action` | No | `turn_on \| turn_off` | Yes | Action to perform on `privacy_entity`; default is `turn_on`. |
| `manual_hold_entity` | No | `input_boolean.*` | Yes | Explicit HA helper that blocks automatic privacy actions while on. |

Validation rule:

- At least one of `motion_entity`, `person_entity`, `vehicle_entity`, `contact_entity`, or
  `privacy_entity` must be present.
- `privacy_entity`, when present, must start with `switch.`.
- `manual_hold_entity`, when present, must start with `input_boolean.`.
- `privacy_action`, when present, must be either `turn_on` or `turn_off`.

Current behavior:

- A camera source with only `privacy_entity` is valid.
- A camera source without any evidence or privacy entity is rejected.
- missing `privacy_action` defaults to `switch.turn_on`;
- `privacy_action="turn_off"` generates `switch.turn_off`.

## Entity Reaction Guard Contract

Implemented owner: `custom_components/heima/runtime/manual_hold.py`

Camera privacy uses the shared `ManualHoldManager`:

- each `privacy_entity` maps to `ManualHoldScope("switch", "entity", privacy_entity)`;
- configured `manual_hold_entity` activates an explicit `helper_on` hold for that scope;
- Heima registers pending switch applies before `switch.turn_on` / `switch.turn_off`;
- state changes for configured privacy switches are classified as Heima-owned or external;
- external privacy switch changes activate an entity-scoped implicit hold;
- held switch steps are marked with `blocked_by="manual_hold:..."` and are not executed.

## Alarm-State Action Contract

Implemented reaction: `alarm_state_action`.

`steps` use the canonical `ApplyStep` contract documented in
`docs/specs/core/apply_step_contract.md`. For direct camera privacy switch actions,
`target` and `params.entity_id` must both be the same `switch.*` entity.

Camera privacy actions are direct `switch` apply steps. They are controlled by the global
`engine_enabled` gate and must not depend on `lighting_apply_mode`; that option only controls
Heima-owned lighting-domain execution.

Supported AE fields:

```yaml
only_house_states:
  - home
skip_house_states:
  - guest
  - vacation
```

Runtime behavior:

- If the current `security_state` is not configured, the reaction does nothing and clears
  `_last_fired_state`.
- If `only_house_states` is configured and current `house_state` is not in that list, the
  reaction does nothing.
- If `security_state` is configured but current `house_state` is in `skip_house_states`, the
  reaction does nothing.
- If the same configured alarm state was already fired, the reaction does nothing.
- Otherwise it emits the configured `ApplyStep` list once for that alarm-state entry.

## Camera Privacy Semantic Policy

Implemented rule: `alarm_night_camera_privacy`.

Current implemented behavior:

- Requires `security.security_state_entity`.
- Requires at least one camera source with a valid `privacy_entity`.
- Emits one `alarm_state_action` proposal with:
  - `identity_key="alarm_night_camera_privacy"`;
  - `alarm_states=["armed_night"]`;
  - one switch step per `privacy_entity`;
  - action from `privacy_action`, defaulting to `switch.turn_on`;
  - `skip_house_states=["guest", "vacation"]`.

## Intended Decision Flow

| alarm_state | house_state | manual hold | privacy_action | Result |
|---|---|---|---|---|
| `armed_night` | `home` | off | `turn_on` | emit `switch.turn_on` |
| `armed_night` | `home` | off | `turn_off` | emit `switch.turn_off` |
| `armed_night` | `home` | on | any | block by manual hold |
| `armed_night` | `guest` | off | any | skip by `skip_house_states` |
| `armed_night` | `vacation` | off | any | skip by `skip_house_states` |

`armed_away` camera privacy behavior is not currently implemented by the semantic policy. A future
rule may add an armed-away policy if needed.

## Examples

Enable privacy on armed night:

```json
{
  "id": "front_door",
  "role": "entry",
  "privacy_entity": "switch.front_door_privacy",
  "privacy_action": "turn_on"
}
```

Disable privacy on armed night:

```json
{
  "id": "perimeter",
  "role": "perimeter",
  "privacy_entity": "switch.perimeter_privacy",
  "privacy_action": "turn_off"
}
```

Custom alarm-state action with a positive house-state filter:

```json
{
  "reaction_type": "alarm_state_action",
  "alarm_states": ["armed_home"],
  "only_house_states": ["home"],
  "steps": [
    {
      "domain": "switch",
      "target": "switch.front_door_privacy",
      "action": "switch.turn_off",
      "params": {
        "entity_id": "switch.front_door_privacy"
      }
    }
  ]
}
```

Evidence only:

```json
{
  "id": "driveway",
  "role": "entry",
  "motion_entity": "binary_sensor.driveway_motion",
  "person_entity": "binary_sensor.driveway_person"
}
```

Privacy-only source:

```json
{
  "id": "indoor_cam",
  "role": "entry",
  "privacy_entity": "switch.indoor_cam_privacy"
}
```

## Remaining AE Work

- Run and document full `scripts/ci_local.sh` if required before merge/release.

## Verification Notes

Focused and full verification runs on 2026-06-25:

```bash
.venv/bin/python -m pytest \
  tests/test_manual_hold_manager.py \
  tests/test_alarm_policy_reaction.py \
  tests/test_semantic_policies_n.py \
  -q
```

Result: targeted runs passed; full `pytest tests/ -q` passed with `1546 passed`.
