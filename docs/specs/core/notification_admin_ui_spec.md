# Heima Notification Admin UI Spec

**Status:** Planned v2 UI layer over the existing notification recipient model  
**Last Updated:** 2026-07-15

## Purpose

Heima already has a logical notification model based on:

- `recipients`
- `recipient_groups`
- `route_targets`
- `notification_service_capabilities`

That model is correct for runtime delivery, but the current editing surface is too close to raw
JSON/YAML. This spec defines a domain-specific admin UI that lets an administrator configure
notification people, groups, and execution policy profiles without manually writing structured
payloads.

## Scope

In scope:

- admin-facing guided UI for notification recipients
- admin-facing guided UI for recipient groups
- default routing configuration
- reusable execution policy profiles for runtime confirmation and promotion routing
- validation and preview behavior
- persistence mapping to the existing options schema

Out of scope:

- changing runtime notification routing semantics
- introducing a new authorization model
- replacing Home Assistant notify services
- changing promotion review authority; promotion decisions remain HA-admin-gated

## Design Principle

The UI is a guided editor over the canonical model, not a second configuration model.

Persisted notification routing options remain compatible with the existing schema:

```yaml
notifications:
  recipients: {}
  recipient_groups: {}
  route_targets: []
  notification_service_capabilities: {}
```

The UI may also introduce named execution policy profiles. These profiles are a higher-level
configuration layer that reactions can reference instead of embedding a full `execution_policy`
inline.

The admin should not need to write this structure directly in normal use.

## Concepts

### Recipient

A recipient is a stable logical identity for a person or delivery alias.

Example:

- `stefano`
- `antonia`
- `kitchen_display`

Each recipient maps to one or more concrete HA notify services.

Persisted shape:

```yaml
recipients:
  stefano:
    - mobile_app_iphone_stefano
```

UI label:

- "Recipient"

Required fields:

- recipient id
- notify services

Recipient labels:

- if `recipient_id` matches a canonical `people_named.slug`, the UI should display that person's
  `people_named.display_name`
- if no matching person exists, the UI should display the recipient id
- notification recipients must not introduce a separate persisted `display_name` field in the first
  implementation

This avoids duplicating the existing person model. If future non-person recipients need richer
labels, that should be introduced as an explicit recipient metadata schema rather than ad hoc
fields inside `recipients`.

### Notify Service

A notify service is a concrete Home Assistant `notify.*` service, stored without the `notify.`
prefix.

Example:

- HA service: `notify.mobile_app_iphone_stefano`
- persisted value: `mobile_app_iphone_stefano`

Each service can expose capabilities.

Initial capability:

```yaml
notification_service_capabilities:
  mobile_app_iphone_stefano:
    supports_actions: true
```

`supports_actions` is required for resident runtime confirmation notifications.

### Recipient Group

A recipient group is a stable logical group containing recipient ids.

Example:

```yaml
recipient_groups:
  residents:
    - stefano
    - antonia
  admins:
    - stefano
```

Groups are one-level only:

- groups contain recipients
- groups do not contain other groups

### Default Route Targets

Default route targets are logical recipients or groups used by generic Heima event delivery.

Example:

```yaml
route_targets:
  - residents
```

Default route targets must not be overloaded to express every specialized workflow. Specialized
workflows should use named execution policy profiles or explicit reaction-level targets where
needed.

### Execution Policy Profile

An execution policy profile is a named, reusable policy that controls how a reaction is executed.

Example:

```yaml
reactions:
  execution_policy_profiles:
    ask_residents_default:
      mode: ask_residents
      confirmation:
        target_groups:
          - residents
        expires_in_minutes: 10
        on_timeout: skip
        use_default_route_targets: false
      promotion:
        enabled: true
        target_groups:
          - admins
```

Reaction reference:

```yaml
execution_policy_ref: ask_residents_default
```

Profiles avoid copying notification targets into every reaction. If a household changes group
membership or adjusts a reusable policy, referenced reactions can follow that change without
editing every reaction individually.

Inline `execution_policy` remains valid for compatibility and for reaction-specific behavior.

## Required UI Surfaces

### 1. Recipient Editor

The notification configuration flow must provide a "Recipients" editor.

Required behavior:

- list configured recipients
- create recipient
- edit recipient
- delete recipient
- validate recipient id uniqueness
- validate selected notify services exist when HA service discovery is available
- show an advisory message when no notify service is assigned
- show actionable capability status without treating non-actionable services as invalid by default

Recipient form fields:

- `id`: stable recipient id
- `notify_services`: multi-select of available `notify.*` services
- per-service `supports_actions`: explicit toggle

Recipient id rules:

- recipient ids are stable immutable keys
- recipient ids must be slug-like
- recipient ids must be non-empty and unique
- renaming a recipient is not supported in the first implementation
- to migrate from one recipient id to another, the admin must create the new recipient, update every
  group/profile/reaction reference, then delete the old recipient when it is no longer referenced

Service selection rules:

- show discovered HA notify services without the `notify.` prefix in persisted previews
- do not require the admin to know the raw persisted prefix convention
- allow manual service entry when discovery is unavailable or incomplete
- default `supports_actions` to `false`
- the UI may suggest `supports_actions: true` for discovered mobile-app notify services, but the
  persisted value must come from explicit admin confirmation or override
- actionable delivery validation must use only the persisted `supports_actions` value

Deletion rules:

- if a recipient is used by a group, deletion must be blocked
- the UI should offer a guided path to remove the recipient from groups first
- if removing the recipient from groups would leave a group empty, the UI must show that consequence
  before allowing the group edit to be saved

### 2. Group Editor

The notification configuration flow must provide a "Groups" editor.

Required behavior:

- list configured groups
- create group
- edit group
- delete group
- validate group id uniqueness
- validate every member exists in recipients
- prevent nested groups

Group form fields:

- `id`: stable group id
- `members`: multi-select of recipient ids

Group id rules:

- group ids are stable immutable keys
- group ids must be slug-like
- group ids must be non-empty and unique
- renaming a group is not supported in the first implementation
- to migrate from one group id to another, the admin must create the new group, update
  `route_targets`, execution policy profiles, and any inline reaction policies, then delete the old
  group when it is no longer referenced

Group labels:

- group ids are the persisted source for labels in the first implementation
- the UI may present known recommended ids such as `residents` and `admins` with friendly labels,
  but those labels must not imply hardcoded runtime behavior

Recommended built-in group ids:

- `residents`
- `admins`

These names are recommendations, not hardcoded runtime requirements.

### 3. Default Routing Editor

The notification configuration flow must provide a default routing editor.

Required behavior:

- let the admin select default route targets from recipients and groups
- validate that every selected target exists
- preview the resolved notify services
- preview whether actionable delivery is possible

Persisted field:

```yaml
route_targets:
  - residents
```

The default route targets are used by generic event delivery and by runtime confirmations only when
the reaction's confirmation policy enables `use_default_route_targets`.

### 4. Execution Policy Profile Editor

The notification configuration flow should expose named execution policy profiles.

Purpose:

- avoid copying the same `execution_policy` into many reactions
- make resident confirmation and promotion routing visible and intentional
- allow controlled shared changes across many reactions
- keep reaction-specific overrides possible when needed

Required behavior:

- list configured profiles
- create profile
- edit profile
- delete profile only when unused
- show how many reactions reference each profile
- preview which reactions would be affected by a profile edit
- validate profile references before saving reactions

Profile id rules:

- profile ids are stable immutable keys
- profile ids must be slug-like
- profile ids must be non-empty and unique
- renaming a profile is not supported in the first implementation

Recommended initial profile:

```yaml
ask_residents_default:
  mode: ask_residents
  confirmation:
    target_groups:
      - residents
    expires_in_minutes: 10
    on_timeout: skip
    use_default_route_targets: false
  promotion:
    enabled: true
    target_groups:
      - admins
```

Supported profile fields:

- `mode`
- `confirmation.target_recipients`
- `confirmation.target_groups`
- `confirmation.expires_in_minutes`
- `confirmation.on_timeout`
- `confirmation.use_default_route_targets`
- `promotion.enabled`
- `promotion.target_recipients`
- `promotion.target_groups`
- promotion threshold fields defined by the resident runtime confirmation spec

Profile reference persistence:

```yaml
reactions:
  configured:
    evening_studio_scene:
      reaction_type: context_conditioned_lighting_scene
      execution_policy_ref: ask_residents_default
```

Optional reaction-level override:

```yaml
reactions:
  configured:
    evening_studio_scene:
      reaction_type: context_conditioned_lighting_scene
      execution_policy_ref: ask_residents_default
      execution_policy_override:
        confirmation:
          expires_in_minutes: 5
```

Resolution rules:

1. If `execution_policy_ref` is present and valid, load the referenced profile.
2. Apply `execution_policy_override` as a deep merge over the profile.
3. If `execution_policy_ref` is present but invalid, fail closed and surface a configuration error.
4. If no `execution_policy_ref` exists, use inline `execution_policy`.
5. If neither profile reference nor inline policy exists, behavior remains `auto_apply`.

Override merge rules:

- object values merge recursively
- scalar values replace profile values
- list values replace profile lists
- `null` or empty override values must not delete required profile fields unless the specific field
  explicitly supports clearing
- for target fields such as `target_recipients` and `target_groups`, override lists replace profile
  lists rather than being appended

Compatibility rules:

- existing inline `execution_policy` must keep working
- the UI may offer to convert an inline policy to a named profile
- conversion must require explicit admin confirmation
- editing a named profile changes all reactions that reference it, so the UI must show affected
  reaction count and examples before saving

Profile edit safety:

- before saving a profile edit, show affected reaction count
- show at least a small sample of affected reaction labels
- if a profile is used by active reactions, require explicit confirmation
- do not silently rewrite each reaction when a profile changes; reactions keep the same
  `execution_policy_ref`

Diagnostics must expose, per reaction:

- effective execution mode
- whether policy source is `inline`, `profile`, `profile_with_override`, or `default_auto_apply`
- referenced profile id, when present
- unresolved profile reference, when present
- effective confirmation targets
- effective promotion targets

Inline policy remains valid:

```yaml
execution_policy:
  mode: ask_residents
  confirmation:
    target_groups:
      - residents
    use_default_route_targets: false
```

### 5. Promotion Review Routing In Profiles

Promotion review routing should be configured through execution policy profiles or inline
reaction-level policy.

Purpose:

- define who should be informed when a reaction has enough resident approvals to be promoted
- keep the actual decision inside the HA-admin-gated Heima review surface

Current implementation note:

- Promotion review decisions are already persisted and HA-admin-gated.
- Informational admin notification delivery for pending promotion reviews may be implemented after
  the UI model. Until then, this field is a forward-compatible configuration surface and should be
  clearly presented as controlling promotion reminders, not authorization.
- the UI must not imply that admin reminder notifications are delivered until runtime delivery is
  implemented

Profile-level promotion routing:

```yaml
reactions:
  execution_policy_profiles:
    ask_residents_default:
      mode: ask_residents
      promotion:
        enabled: true
        target_groups:
          - admins
```

## Validation

The UI must validate before saving:

- recipient ids are non-empty and unique
- group ids are non-empty and unique
- recipient and group ids are slug-like
- group members reference existing recipients
- route targets reference existing recipients or groups
- runtime confirmation targets reference existing recipients or groups
- promotion review targets reference existing recipients or groups
- services marked as actionable are concrete notify services
- execution policy profile ids are slug-like, non-empty, and unique
- reaction `execution_policy_ref` values reference existing profiles
- profile deletion is blocked while any reaction references that profile

Actionable validation:

- runtime confirmation targets must resolve to at least one notify service with
  `supports_actions: true`
- if a reaction or profile enables resident runtime confirmation, no actionable resolved service is a
  blocking error
- generic non-actionable notifications may use services without `supports_actions`
- generic default route targets are valid even if none of their resolved services support actions
- promotion reminder targets do not require actionable services because promotion decisions remain
  in the HA-admin-gated review surface

## Preview

The UI must provide a resolution preview.

For each group or target selection, show:

- selected logical target
- resolved recipients
- resolved notify services
- actionable-capable services
- non-actionable services
- deduplicated final services
- unresolved references

For each execution policy profile, show:

- profile id
- effective execution mode
- resident confirmation targets
- promotion review targets
- actionable delivery status for resident confirmation
- number of referencing reactions
- sample referencing reaction labels

Example preview:

```text
residents
Recipients: Stefano, Antonia
Services: mobile_app_iphone_stefano, mobile_app_iphone_antonia
Actionable: 2/2
Deduplicated final services: 2
```

## Persistence Mapping

Given this UI state:

```text
Recipients:
- Stefano -> mobile_app_iphone_stefano, supports actions
- Antonia -> mobile_app_iphone_antonia, supports actions

Groups:
- Admins -> Stefano
- Residents -> Stefano, Antonia

Default routing:
- Residents

Execution policy profiles:
- ask_residents_default -> ask residents, promotion reminders to Admins
```

Persisted options should be:

```yaml
notifications:
  recipients:
    stefano:
      - mobile_app_iphone_stefano
    antonia:
      - mobile_app_iphone_antonia
  recipient_groups:
    admins:
      - stefano
    residents:
      - stefano
      - antonia
  route_targets:
    - residents
  notification_service_capabilities:
    mobile_app_iphone_stefano:
      supports_actions: true
    mobile_app_iphone_antonia:
      supports_actions: true

reactions:
  execution_policy_profiles:
    ask_residents_default:
      mode: ask_residents
      confirmation:
        target_groups:
          - residents
        expires_in_minutes: 10
        on_timeout: skip
        use_default_route_targets: false
      promotion:
        enabled: true
        target_groups:
          - admins
```

## Compatibility

The guided UI must preserve existing valid configurations.

Rules:

- existing `recipients`, `recipient_groups`, `route_targets`, and
  `notification_service_capabilities` must round-trip without loss
- existing inline reaction `execution_policy` values must keep working
- unknown but valid notify service names must remain editable
- legacy `routes` must continue to be handled by existing migration/normalization logic
- the raw object editor may remain available behind an advanced/debug affordance, but it must not be
  the primary admin path
- raw editor saves must pass through the same normalization and validation rules as the guided UI
- raw editor saves involving profile references must validate references and affected reaction
  safety rules

## Non-Goals

This UI must not:

- infer Heima admin authority from notification groups
- treat `admins` as an authorization boundary
- send actionable promotion decisions directly to notification recipients
- require every notification recipient to be a Home Assistant user
- require every Home Assistant user to be a notification recipient
- silently rewrite all referenced reactions when a profile changes

Authorization remains:

- resident runtime confirmations: possession of the actionable notification can approve/dismiss that
  one runtime request
- promotion review: HA-admin-gated Heima review surface

## Implementation Phases

### Phase 1: Guided Recipient and Group Editor

- add recipient list/create/edit/delete UI
- add group list/create/edit/delete UI
- preserve current persisted schema
- add resolution preview

### Phase 2: Default Routing Editor

- add default route target multi-select
- validate and preview resolved routes
- remove need for raw `route_targets` editing in normal flow

### Phase 3: Execution Policy Profiles

- add execution policy profile model and guided editor
- support `execution_policy_ref`
- support optional `execution_policy_override`
- keep inline `execution_policy` compatibility
- validate actionable delivery for effective resident confirmation targets
- expose effective policy diagnostics

### Phase 4: Promotion Review Profile Routing

- add promotion routing fields to execution policy profiles
- validate promotion target references
- implement informational promotion reminder notifications if not already present

### Phase 5: Advanced Raw Editor

- keep raw object editing as an advanced escape hatch
- show validation messages before save
- document that normal administration should use the guided UI
