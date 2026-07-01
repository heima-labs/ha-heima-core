# Camera Privacy Policy UI Spec

**Status:** Draft implementation target  
**Created:** 2026-07-01  
**Related:** `policy_editor_framework_spec.md`, `privacy_guard_for_alarm_states.md`, `manual_hold_framework_spec.md`, `apply_step_contract.md`, `options_flow_spec.md`

## Purpose

Camera privacy rules are now expressible with `security.camera_evidence_sources` plus
`reactions.configured[*].reaction_type = "alarm_state_action"`, but the raw YAML/JSON shape is not
admin-friendly.

The UI target is a domain-specific **Camera Privacy Policy** editor. It must help the admin express
camera privacy intent without exposing generic automation concepts such as arbitrary triggers,
conditions, service calls, or raw `ApplyStep` payloads.

This editor is the first concrete specialization of the shared Policy Editor Framework. Its design
must follow `policy_editor_framework_spec.md`.

## Product Boundary

This UI is **not** a Home Assistant automation builder.

It is a bounded Heima security policy surface:

- subject: configured camera source;
- actuator: that camera's `privacy_entity`;
- trigger dimension: alarm state;
- context dimension: Heima house state;
- action: privacy on, privacy off, or unchanged;
- guard: existing shared manual-hold framework.

The UI MUST NOT expose:

- arbitrary HA services;
- free-form condition trees;
- chained actions or delays;
- generic `target` / `params.entity_id` editing;
- non-camera actuators.

Advanced JSON/YAML editing may exist as a separate diagnostic escape hatch, but it is not the
primary UX.

## User Model

The admin thinks in terms of:

- "Camera Corridoio";
- "privacy is on while alarm is disarmed";
- "privacy is off when alarm is armed away";
- "privacy is off at night unless house state is guest";
- "manual hold blocks Heima from changing this switch".

The UI should render that language directly.

## Entry Point

Add a security-domain entry point in Options Flow:

- preferred menu label: `Camera privacy policies`;
- acceptable parent: Security menu or Reactions menu;
- the surface remains admin-only through the existing Options Flow admin gate.

The existing `security.camera_evidence_sources` object editor remains available for low-level camera
source configuration, but it should not be the main path for privacy policy authoring.

## Camera Source Setup

The policy editor starts from a camera source.

For each camera source, show:

| Field | Source | Editable in policy UI |
|---|---|---:|
| Camera id | `security.camera_evidence_sources[*].id` | No after creation |
| Display name | `display_name` or id | Yes |
| Role | `role` | Yes |
| Privacy switch | `privacy_entity` | Yes, entity selector constrained to `switch.*` |
| Manual hold helper | `manual_hold_entity` | Yes, optional entity selector constrained to `input_boolean.*` |

If no camera source exists, the UI may offer "Add camera privacy source" with the minimum fields:

- `id`;
- `role`;
- `privacy_entity`;
- optional `manual_hold_entity`.

The UI must preserve existing evidence fields (`motion_entity`, `person_entity`, `vehicle_entity`,
`contact_entity`, etc.) when editing privacy fields.

## Policy Rule Model

A camera privacy policy row is:

| Field | Values |
|---|---|
| Camera | one configured camera source with `privacy_entity` |
| Alarm states | one or more of `disarmed`, `armed_home`, `armed_away`, `armed_night`, `triggered` |
| House-state filter | `always`, `only`, `except` |
| House states | list of known Heima house states, required for `only` and `except` |
| Privacy action | `turn_on` or `turn_off` |
| Enabled | boolean |

UI labels should use domain wording:

- `turn_on` -> "Privacy on";
- `turn_off` -> "Privacy off";
- `always` -> "Any house state";
- `only` -> "Only when house state is";
- `except` -> "Except when house state is".

## Persisted Runtime Shape

The UI must persist rules as normal configured reactions. It must not introduce a second execution
engine.

Each policy row materializes an `alarm_state_action` reaction:

```yaml
reaction_type: alarm_state_action
enabled: true
alarm_states:
  - armed_night
skip_house_states:
  - guest
steps:
  - domain: switch
    target: switch.interna_privacy
    action: switch.turn_off
    params:
      entity_id: switch.interna_privacy
```

House-state filter mapping:

| UI filter | Persisted field |
|---|---|
| `always` | omit or empty `only_house_states` and `skip_house_states` |
| `only` | `only_house_states` |
| `except` | `skip_house_states` |

Privacy action mapping:

| UI action | ApplyStep |
|---|---|
| Privacy on | `domain=switch`, `action=switch.turn_on`, `target=params.entity_id=privacy_entity` |
| Privacy off | `domain=switch`, `action=switch.turn_off`, `target=params.entity_id=privacy_entity` |

For direct camera privacy switch actions, `target` and `params.entity_id` must be identical, per
`apply_step_contract.md`.

Enabled mapping:

- enabled policy row -> omit `enabled` or set `enabled: true`;
- disabled policy row -> set `enabled: false`.

The runtime already skips configured reactions whose `enabled` field is false.

## Round-Trip Metadata

To make generated rules editable without parsing arbitrary reactions heuristically, the UI should
store metadata alongside the normalized runtime fields:

```yaml
admin_authored_template_id: security.camera_privacy_policy
source_template_id: security.camera_privacy_policy
source_request: template:security.camera_privacy_policy
camera_privacy_policy:
  camera_source_id: interna
  privacy_entity: switch.interna_privacy
  house_filter_mode: except
  house_states:
    - guest
  privacy_action: turn_off
```

The runtime must ignore this metadata. The options flow uses it for listing, editing, duplicate
detection, and deletion.

Implementation note: current `alarm_state_action` normalization returns only canonical runtime
fields. The implementation MUST use the Policy Editor Framework's two-level normalization model:

1. keep the runtime normalization focused on the fields consumed by `alarm_state_action`;
2. preserve the allowed persisted-config envelope fields on the same configured reaction entry.

The UI MUST NOT create a separate persistent metadata map for camera privacy policies. The configured
reaction remains the authoritative persistence unit.

These envelope keys must survive options normalization:

- `enabled`;
- `origin`;
- `author_kind`;
- `created_at`;
- `source_proposal_id`;
- `source_proposal_identity_key`;
- `admin_authored_template_id`;
- `source_template_id`;
- `source_request`;
- `camera_privacy_policy`.

Without this change, the UI would be able to create policy metadata but would lose it after the next
normalization pass.

If metadata is missing, the UI may display a compatible `alarm_state_action` as "advanced imported"
only when all of these are true:

- exactly one step;
- step domain is `switch`;
- step target equals `params.entity_id`;
- the entity equals a configured camera source `privacy_entity`;
- action is `switch.turn_on` or `switch.turn_off`.

Imported rows should be editable only after the UI writes the metadata back on save.

## Reaction IDs and Labels

Generated reaction ids should be stable and readable:

```text
camera_privacy_policy__<camera_source_id>__<alarm_states_slug>__<house_filter_slug>__<privacy_action>
```

Use slug-safe separators (`__`, `-`, `_`) rather than colon-delimited ids. Reaction ids appear as
mapping keys in YAML/object-editor payloads and should remain easy to paste, quote, and manipulate.

Labels should be human-readable:

```text
Corridoio privacy: off when alarm is armed_night except guest
```

The options flow must persist these labels in `reactions.labels[reaction_id]`; they are not runtime
fields on the reaction config itself.

If an existing reaction id conflicts with different content, append a short deterministic suffix.

## Validation

The UI must reject:

- camera policy rows without a camera source;
- camera sources without `privacy_entity`;
- `privacy_entity` outside `switch.*`;
- `manual_hold_entity` outside `input_boolean.*`;
- empty alarm state list;
- `only` or `except` filter with an empty house-state list;
- duplicate rows that produce the same camera + alarm states + house filter + privacy action slot.

Validation messages should be domain-specific. Do not surface generic `required` when the submitted
payload is an entire options object or the wrong level of YAML.

For the existing low-level `camera_evidence_sources` object editor, if the top-level submitted value
contains `security` or `reactions`, the error should say that the field accepts only camera evidence
sources.

## UX Shape

### List View

Show one row per generated policy:

| Camera | Alarm | House state | Privacy | Manual hold |
|---|---|---|---|---|
| Corridoio | disarmed | any | on | input_boolean.corridoio_privacy_hold |
| Corridoio | armed_away | any | off | input_boolean.corridoio_privacy_hold |
| Corridoio | armed_night | except guest | off | input_boolean.corridoio_privacy_hold |

Actions:

- add policy;
- edit policy;
- duplicate policy;
- disable/enable policy;
- delete policy.

### Edit View

Fields:

1. Camera selector.
2. Privacy switch display and optional edit link.
3. Alarm states selector.
4. House-state filter mode.
5. House-state selector when mode is `only` or `except`.
6. Privacy action segmented choice: `on` / `off`.
7. Enabled toggle.
8. Read-only summary.

The read-only summary should be the primary confirmation surface, for example:

> Heima will turn Corridoio privacy off when the alarm becomes armed night, except when the house
> state is guest. Manual hold is respected.

### Preview

A generated YAML preview may be shown behind "Advanced preview".

The preview is read-only in the primary flow.

## Example: Corridoio Policy Set

The user's desired policy:

- Privacy on when alarm is `disarmed`.
- Privacy off when alarm is `armed_away`, regardless of house state.
- Privacy off when alarm is `armed_night`, except when house state is `guest`.

Materialized reactions:

```yaml
reactions:
  configured:
    camera_privacy_policy__interna__disarmed__any__turn_on:
      reaction_type: alarm_state_action
      enabled: true
      alarm_states:
        - disarmed
      steps:
        - domain: switch
          target: switch.interna_privacy
          action: switch.turn_on
          params:
            entity_id: switch.interna_privacy
      admin_authored_template_id: security.camera_privacy_policy
      source_template_id: security.camera_privacy_policy
      source_request: template:security.camera_privacy_policy
      camera_privacy_policy:
        camera_source_id: interna
        privacy_entity: switch.interna_privacy
        house_filter_mode: always
        house_states: []
        privacy_action: turn_on

    camera_privacy_policy__interna__armed_away__any__turn_off:
      reaction_type: alarm_state_action
      enabled: true
      alarm_states:
        - armed_away
      steps:
        - domain: switch
          target: switch.interna_privacy
          action: switch.turn_off
          params:
            entity_id: switch.interna_privacy
      admin_authored_template_id: security.camera_privacy_policy
      source_template_id: security.camera_privacy_policy
      source_request: template:security.camera_privacy_policy
      camera_privacy_policy:
        camera_source_id: interna
        privacy_entity: switch.interna_privacy
        house_filter_mode: always
        house_states: []
        privacy_action: turn_off

    camera_privacy_policy__interna__armed_night__except_guest__turn_off:
      reaction_type: alarm_state_action
      enabled: true
      alarm_states:
        - armed_night
      skip_house_states:
        - guest
      steps:
        - domain: switch
          target: switch.interna_privacy
          action: switch.turn_off
          params:
            entity_id: switch.interna_privacy
      admin_authored_template_id: security.camera_privacy_policy
      source_template_id: security.camera_privacy_policy
      source_request: template:security.camera_privacy_policy
      camera_privacy_policy:
        camera_source_id: interna
        privacy_entity: switch.interna_privacy
        house_filter_mode: except
        house_states:
          - guest
        privacy_action: turn_off
  labels:
    camera_privacy_policy__interna__disarmed__any__turn_on: "Interna privacy: on when alarm is disarmed"
    camera_privacy_policy__interna__armed_away__any__turn_off: "Interna privacy: off when alarm is armed away"
    camera_privacy_policy__interna__armed_night__except_guest__turn_off: "Interna privacy: off when alarm is armed night except guest"
```

## Implementation Plan

1. Add `security.camera_privacy_policy` template descriptor or equivalent bounded flow entry.
2. Add options-flow list/edit steps for policy rows.
3. Add materializer helpers:
   - policy row -> `alarm_state_action` config;
   - compatible reaction config -> policy row.
4. Add duplicate-slot detection for camera privacy policy rows.
5. Add friendly validation for wrong-level YAML in `camera_evidence_sources`.
6. Extend `alarm_state_action` normalization so camera privacy policy metadata and provenance fields
   are preserved.
7. Add options-flow tests for:
   - creating the three Corridoio rules;
   - editing a rule;
   - deleting a generated rule;
   - preserving existing camera evidence fields;
   - manual hold helper display/persistence;
   - wrong-level YAML error message.
8. Add live diagnostic coverage only after the options-flow path is implemented.

## Acceptance Criteria

- Admin can create the Corridoio three-rule policy set without writing YAML.
- Generated reactions are normal `alarm_state_action` configs and rebuild into runtime reactions.
- Manual hold continues to block privacy switch actions.
- UI does not expose raw `ApplyStep` fields in the main flow.
- Generated metadata survives options normalization/reload and supports edit/delete round-trip.
- Generated labels are persisted in `reactions.labels`.
- Existing `security.camera_evidence_sources` configurations are preserved.
- Wrong-level YAML produces a specific error instead of generic `required`.
