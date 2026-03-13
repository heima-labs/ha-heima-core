# Heima Notification Recipients Spec v1

**Status:** Implemented (v1.x) — legacy routes closed runtime-side and removed from UI
**Last Verified Against Code:** 2026-03-12

## Goal

Decouple notification routing from physical `notify.*` service ids so user/device changes do not require reconfiguring all Heima notification behavior.

## Core Model

### 1. Legacy routes

- `routes` is a legacy migration input (`list[notify.*]`).
- It is no longer part of the options-flow editable schema.
- It is no longer consumed directly by runtime delivery.
- If present in persisted options, normalization bridges it to a logical recipient target.

### 2. Recipient aliases

- `recipients` is a mapping:
  - `recipient_id -> list[notify_service_name]`
- Example:
  - `stefano -> [mobile_app_phone_stefano, mobile_app_mac_stefano]`

Recipient ids are logical identities. They should remain stable even if devices change.

Note:
- each `notify_service_name` can be either:
  - a direct device endpoint (for example `mobile_app_phone_stefano`)
  - a Home Assistant native grouped notify endpoint (for example `family_notifications`)
- Heima treats both as plain `notify.*` transport endpoints.

### 3. Recipient groups

- `recipient_groups` is a mapping:
  - `group_id -> list[recipient_id]`
- Example:
  - `family -> [stefano, laura]`

Groups are one-level only in v1:
- group members must be recipient ids
- nested groups are not supported

### 4. Default route targets

- `route_targets` is a list of logical targets used by the event pipeline.
- Each target may be:
  - a `recipient_id`, or
  - a `group_id`

## Routing Resolution

For each emitted event:

1. Resolve each `route_target`
   - recipient -> its mapped services
   - group -> all recipient services of its members
2. Deduplicate final `notify.*` services
3. Deliver through the existing event pipeline

If a `route_target` does not resolve:
- it is ignored
- a runtime diagnostics/error counter is incremented

## Options Flow Shape (v1)

In `Notifications`:

- `recipients` (textarea; one line per alias: `alias=notify_a,notify_b`)
- `recipient_groups` (textarea; one line per group: `group=recipient_a,recipient_b`)
- `route_targets` (textarea; one alias/group id per line, commas also accepted)

## Compatibility

- new routing is canonical
- the pipeline must work when:
  - a migrated routes-only profile exists in persisted options
  - only aliases/groups are configured
  - old persisted options still contain `routes` alongside aliases/groups

## Deprecation Rollout

Phase A (implemented):
- emit runtime warning event: `system.notifications_routes_deprecated`

Phase B (implemented):
- options-flow bridge for routes-only profiles:
  - creates logical recipient alias `legacy_routes`
  - creates logical route target `legacy_routes`
- removes `routes` from normalized options payload

Phase C (closed in v1.x runtime):
- runtime delivery no longer consumes `routes` directly
- routes-only profiles are auto-bridged to logical targets
- options flow no longer exposes `routes`
