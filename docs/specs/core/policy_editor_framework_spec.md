# Policy Editor Framework Spec

**Status:** Draft implementation target  
**Created:** 2026-07-01  
**Scope:** Domain-specific admin policy editors for Heima domains and plugin families  
**Related:** `options_flow_spec.md`, `reaction_identity_spec.md`, `apply_step_contract.md`, `learning/admin_authored_automation_spec.md`

## Purpose

Heima needs admin-facing configuration surfaces for explicit policies that are too structured and
domain-specific for raw YAML, but should not become a generic Home Assistant automation builder.

This spec defines a shared pattern that all future domain/plugin policy editors must follow.

The framework is a **UI and materialization contract**, not a new runtime engine.

## Core Decision

Heima policy editors are domain-specific.

They MUST expose the language of the owning domain:

- camera privacy policy;
- room lighting policy;
- heating house-state policy;
- notification routing policy;
- watering sector policy.

They MUST NOT expose a generic:

```text
trigger + condition + action + service payload
```

builder.

The generic automation-builder shape belongs to Home Assistant automations, not Heima.

## Design Rule

Every policy editor must fit this model:

```text
domain subject + domain state/context + bounded domain action
```

Examples:

| Domain | Subject | State/context | Bounded action |
|---|---|---|---|
| Security | Camera | alarm state + house state | privacy on/off |
| Lighting | Room | occupancy + lux + house state | smart lighting profile |
| Heating | Climate/home | house state + alarm state | preset/HVAC/branch |
| Notifications | Heima event category | severity + route context | recipient group |
| Watering | Sector | weather/rain/manual hold | water/skip/schedule |

## Non-Goals

Policy editors MUST NOT provide:

- arbitrary HA service call builders;
- arbitrary condition trees;
- chained actions, delays, or script-like sequences;
- raw `ApplyStep` editing in the primary UI;
- cross-domain action composition unless the owning domain spec explicitly defines it;
- a second persistence model outside `options.reactions.configured` or the domain's existing
  options contract.

Advanced JSON/YAML inspection may exist for diagnostics, import, or support workflows, but it must
not be the default authoring path.

## Runtime Contract

Policy editors must materialize into existing runtime artifacts.

Preferred persistence targets:

1. `options.reactions.configured` for policy rows that execute through reactions.
2. Existing domain option sections for policies that are already native domain configuration.

A policy editor MUST NOT introduce a new execution engine.

If a policy executes actions, it should produce normal reaction configs that rebuild through the
registered reaction plugin system.

## Policy Editor Descriptor

Each domain/plugin-owned editor should be described by a stable descriptor.

Minimum descriptor fields:

```python
PolicyEditorDescriptor(
    policy_type="security.camera_privacy_policy",
    owner_domain="security",
    title="Camera privacy policies",
    persisted_target="reactions.configured",
    supported_subjects=("camera_source",),
    materialized_reaction_types=("alarm_state_action",),
)
```

Required semantics:

| Field | Meaning |
|---|---|
| `policy_type` | Stable id for metadata, diagnostics, and editor routing. |
| `owner_domain` | Domain/plugin family that owns validation and wording. |
| `title` | User-facing editor title. |
| `persisted_target` | Persistence area, usually `reactions.configured`. |
| `supported_subjects` | Domain-specific subjects the editor can author. |
| `materialized_reaction_types` | Reaction types the editor may generate. |

The descriptor may later live in the plugin registry, but the same contract applies if the first
implementation is flow-local.

## Policy Row Model

Each editor should define a bounded `PolicyRow` model.

Policy rows are UI/domain objects, not runtime objects. They are materialized into runtime config.

Required row concepts:

- stable row identity;
- domain subject reference;
- bounded context/filter fields;
- bounded action field;
- enabled/disabled state when applicable;
- presenter summary;
- validation errors.

The row must be round-trippable:

```text
PolicyRow -> persisted config -> PolicyRow
```

Round-trip support can use metadata stored alongside the runtime fields, but the runtime must be
able to ignore that metadata.

## Materializer Contract

Each policy editor must provide or define:

1. `materialize(row) -> persisted config updates`
2. `parse(config) -> row | imported-row | None`
3. `slot_key(row) -> str`
4. `label(row) -> str`
5. `summary(row) -> str`
6. `validate(row) -> errors`

### `materialize`

Converts a policy row into the canonical persisted shape.

For reaction-backed policies this includes:

- `reaction_type`;
- normalized runtime fields;
- `enabled` when applicable;
- provenance metadata;
- policy-editor metadata;
- label updates in `reactions.labels`.

### `parse`

Reads existing persisted config back into policy rows.

It must support two cases:

- native generated rows with metadata;
- compatible imported rows when safe.

Imported rows must be clearly identified if the editor cannot guarantee full fidelity.

### `slot_key`

Returns a duplicate-detection key in domain terms.

It should not depend on user-facing labels.

### `label` and `summary`

Generate concise domain wording for lists, review screens, diagnostics, and labels.

### `validate`

Must return domain-specific errors. It must not leak low-level schema errors such as generic
`required` when the user's mistake is conceptual, such as pasting a whole options payload into a
field that accepts only one section.

## Metadata Contract

Reaction-backed policy editors should persist metadata alongside the runtime config:

```yaml
admin_authored_template_id: <policy_type>
source_template_id: <policy_type>
source_request: template:<policy_type>
<policy_type_slug>:
  ...
```

The exact metadata object is editor-specific, but it must include enough data to reconstruct the
policy row without guessing from raw `ApplyStep` details.

Normalizer compatibility is mandatory:

- metadata required for round-trip editing must survive options normalization;
- provenance fields used by diagnostics must survive options normalization;
- tests must cover metadata survival.

Policy editors MUST NOT create a parallel persistent metadata store for reaction-backed policies.
The configured reaction entry remains the authoritative persistence unit.

The expected implementation model is two-level normalization:

1. **Runtime field normalization** canonicalizes only fields consumed by the reaction builder.
2. **Persisted config envelope normalization** preserves allowed non-runtime fields on the same
   configured reaction entry.

This keeps runtime builders independent from UI/editor metadata while avoiding split-brain state
between `reactions.configured` and a second metadata map.

Envelope preservation must be allowlist-based. It must not pass through arbitrary unknown keys.

Common allowed envelope fields include:

- `enabled`;
- `origin`;
- `author_kind`;
- `source_proposal_id`;
- `source_proposal_identity_key`;
- `created_at`;
- `source_template_id`;
- `source_request`;
- `admin_authored_template_id`;
- editor-specific metadata objects such as `camera_privacy_policy`.

For reaction-backed policy editors, losing `enabled` during normalization is a behavioral bug, not
only a metadata loss, because disabled configured reactions must remain disabled after any
compatibility normalization pass.

## Relationship To Admin-Authored Automations

Policy editors are a stricter subtype of admin-authored configuration.

They share these principles:

- explicit admin intent;
- no separate runtime engine;
- normal reaction persistence when action execution is needed;
- provenance visible in review/diagnostics.

They differ from a generic admin-authored automation builder:

- each editor is owned by one domain/plugin;
- each editor exposes only domain concepts;
- each editor has a bounded action set;
- each editor must be able to explain the policy without showing raw runtime payload.

## Relationship To Plugins

Plugins may provide policy editors only when they can own the full bounded contract:

- subject model;
- validation;
- materialization;
- reverse parsing;
- labels/summaries;
- duplicate slot semantics;
- tests.

A plugin MUST NOT register a policy editor merely to expose arbitrary HA services.

Plugin policy editors should use stable `policy_type` ids scoped to the plugin/domain:

```text
security.camera_privacy_policy
lighting.room_smart_lighting_policy
heating.house_state_policy
notifications.event_route_policy
watering.sector_weather_policy
```

## Options Flow Requirements

Policy editor UIs in Options Flow must:

- remain admin-only;
- provide a list view for existing policy rows;
- provide bounded add/edit/delete flows;
- preserve unrelated domain configuration;
- preserve unrelated reactions;
- write labels to the appropriate label store when generating reactions;
- use the shared reaction persistence model;
- avoid exposing raw runtime fields in the primary flow.

If an editor supports import from existing compatible reactions, imported rows must be marked and
saved through the editor before they become fully managed policy rows.

## Validation Requirements

Every policy editor must validate at three levels:

1. UI row validation.
2. Persisted config validation.
3. Runtime rebuild validation through the owning reaction/domain builder.

Tests must cover:

- create;
- edit;
- delete;
- disable/enable when supported;
- duplicate detection;
- metadata round-trip;
- preservation of unrelated options;
- rebuild into runtime artifacts;
- domain-specific error messages for common wrong-level payloads.

## Accepted First Implementations

The first concrete editor target is:

- `security.camera_privacy_policy`, specified in `camera_privacy_policy_ui_spec.md`.

Future editors must reference this framework spec and document their domain-specific row model,
materializer, reverse parser, validation, and labels.

## Acceptance Criteria For New Policy Editors

A new policy editor is acceptable only when:

- it is domain-specific and bounded;
- it does not replicate HA's generic automation builder;
- it materializes to existing Heima runtime contracts;
- it preserves round-trip metadata;
- it has focused options-flow tests;
- it has runtime/rebuild tests for generated config;
- it has clear diagnostics and labels.
