# Heima — Events & Notifications Spec (Consolidated)

**Status:** Active v1 events and notifications contract
**Last Verified Against Code:** 2026-03-12

## Purpose

Consolidate the operational contract for:
- event emission model
- routing, recipients and recipient groups
- category gating and delivery controls

This supersedes split reading of:
- `rfc/event_catalog_spec.md`
- `rfc/notification_recipients_spec.md`

## Scope and non-goals

In scope:
- semantic contract of event emission
- delivery pipeline semantics
- compatibility and routing rules

Not a goal of this document:
- enumerating every individual event payload field in full detail
- describing internal module layout
- documenting historical migration steps beyond what remains behaviorally relevant

## Core concepts

This spec uses the following terms:

- **Event**: a runtime fact emitted by Heima with stable type, key, severity, and context.
- **Category gating**: the rule that whole event families can be enabled or disabled before
  delivery.
- **Deduplication**: suppression of repeated events with the same key inside a short window.
- **Rate limiting**: suppression of repeated events with the same key over a longer throttle
  window.
- **Logical routing**: target resolution through recipients and recipient groups, independent from
  concrete HA notify service names.

Normative rule:
- event production and event delivery are separate stages
- an event may be emitted and still not be delivered, because gating, dedup, rate limiting, or
  routing may suppress it later

## Event Pipeline (Current)

1. Runtime emits canonical events.
2. Category gating is applied.
3. Dedup and per-key rate limits are applied.
4. Targets are resolved through recipients/groups (logical routing).
5. Delivery is attempted through HA notify services.

### Pipeline semantics

The pipeline has these required properties:

- emission must use stable event types and keys defined by the catalog/spec set
- routing must operate on logical recipients/groups, not on legacy ad hoc route payloads
- dedup and rate limiting must be keyed, deterministic, and explainable in diagnostics
- compatibility modes such as security mismatch dual emission must operate at emission time, before
  category gating and delivery

## Configuration Surface

Defined in options flow (`core/options_flow_spec.md`):
- `recipients`
- `recipient_groups`
- `route_targets`
- `enabled_event_categories`
- dedup/rate-limit controls
- mismatch policy controls

Configuration contract:
- these options control the delivery pipeline and compatibility behavior
- they must not change the semantic meaning of a previously emitted event type, only whether or how
  it is emitted or delivered

## Compatibility

Recipient aliases and groups are the canonical model.

Deprecation closed (v1.x):
- runtime delivery uses only logical targets
- options flow no longer exposes `routes`
- legacy `routes` are migration input only (bridge for routes-only profiles during normalization)
- runtime emits `system.notifications_routes_deprecated` when legacy routes are still present

### Compatibility principle

Backward compatibility is achieved by explicit compatibility modes and migration bridges, not by
keeping multiple conflicting routing models permanently active.

Example:
- `security_mismatch_event_mode` may emit explicit, generic, or both event forms
- recipient/group routing remains the canonical delivery model even when legacy payloads are still
  accepted as migration input

## Normative precedence

This document is normative for the consolidated events and notifications contract.

Interpretation rule:
- if implementation and spec diverge, the divergence must be treated as either:
  - a bug in the implementation, or
  - an outdated section of the spec that must be revised explicitly

The codebase is therefore a reference implementation, not the source of truth.

Supporting detail remains available in:
- `rfc/event_catalog_spec.md`
- `rfc/notification_recipients_spec.md`
