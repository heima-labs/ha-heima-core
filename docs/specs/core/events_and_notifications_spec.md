# Heima — Events & Notifications Spec (Consolidated)

**Status:** Implemented (v1.x)
**Last Verified Against Code:** 2026-03-12

## Purpose

Consolidate the operational contract for:
- event emission model
- routing, recipients and recipient groups
- category gating and delivery controls

This supersedes split reading of:
- `rfc/event_catalog_spec.md`
- `rfc/notification_recipients_spec.md`

## Event Pipeline (Current)

1. Runtime emits canonical events.
2. Category gating is applied.
3. Dedup and per-key rate limits are applied.
4. Targets are resolved through recipients/groups (logical routing).
5. Delivery is attempted through HA notify services.

## Configuration Surface

Defined in options flow (`core/options_flow_spec.md`):
- `recipients`
- `recipient_groups`
- `route_targets`
- `enabled_event_categories`
- dedup/rate-limit controls
- mismatch policy controls

## Compatibility

Recipient aliases and groups are the canonical model.

Deprecation closed (v1.x):
- runtime delivery uses only logical targets
- options flow no longer exposes `routes`
- legacy `routes` are migration input only (bridge for routes-only profiles during normalization)
- runtime emits `system.notifications_routes_deprecated` when legacy routes are still present

## Source of Truth

- Runtime behavior: current code in notifications/event runtime modules
- Detailed historical catalogs: `rfc/event_catalog_spec.md`, `rfc/notification_recipients_spec.md`
