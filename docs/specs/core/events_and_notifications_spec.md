# Heima — Events & Notifications Spec (Consolidated)

**Status:** Active v1 events and notifications contract
**Last Updated:** 2026-07-22

## Purpose

Consolidate the operational contract for:
- event emission model
- routing, recipients and recipient groups
- category gating and delivery controls

This supersedes split reading of:
- `core/event_catalog_spec.md`
- `core/notification_recipients_spec.md`

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
- **Notification service capability**: transport metadata for a concrete `notify.*` service, such
  as whether it can carry actionable notification buttons.
- **Audience**: the intended human surface for a notification. Supported audiences are
  `resident`, `admin`, and `observability`.
- **Informational notification**: a non-actionable notification derived from an event.
- **Actionable notification**: a notification that carries an explicit approve/dismiss or review
  action and is governed by the runtime confirmation or admin review contracts.
- **Aggregation**: collapsing multiple related events into one human-facing notification or keeping
  them only in diagnostics.

Normative rule:
- event production and event delivery are separate stages
- an event may be emitted and still not be delivered, because gating, dedup, rate limiting, or
  routing may suppress it later

## Event Delivery Pipeline

1. Runtime emits canonical events.
2. Event family and severity are classified.
3. Audience policy is resolved.
4. Startup grace is applied for informational push delivery.
5. Persistence thresholds are applied for mismatch/invariant families.
6. Related events are aggregated or collapsed.
7. Category gating is applied.
8. Deduplication, per-key rate limits, and global informational burst limits are applied.
9. Audience targets are resolved to recipient groups/recipients.
10. Recipients are resolved to concrete `notify.*` services.
11. Delivery constraints are applied, including actionable capability filtering when the message
   requires a resident/admin action.
12. Delivery is attempted through HA notify services.

### Pipeline semantics

The pipeline has these required properties:

- emission must use stable event types and keys defined by the catalog/spec set
- routing must operate on logical recipients/groups, not on legacy ad hoc route payloads
- actionable notification delivery must only use services explicitly marked with
  `supports_actions`
- if a message requires an action and no resolved service supports actions, delivery must fail
  closed and record diagnostics instead of silently downgrading to a non-actionable message
- dedup and rate limiting must be keyed, deterministic, and explainable in diagnostics
- compatibility modes such as security mismatch dual emission must operate at emission time, before
  category gating and delivery

## Audience Policy

Heima must separate runtime observability from human notification delivery.

Normative rules:

- all runtime facts may be retained in diagnostics and the admin observability panel
- only selected facts should become push notifications
- technical events must not be routed to residents by default
- admin-facing configuration, degraded-health, invariant, and installation-validation issues must
  target admins or the observability panel, not residents, unless explicitly promoted by policy
- resident-facing notifications must be plain-language, relevant to the resident, and either
  actionable or materially important
- event routing must not infer authorization from notification groups; HA admin authority remains
  the authorization boundary for admin decisions

Default audience mapping:

| Event family | Default notification behavior |
|---|---|
| `runtime_confirmation.*` actionable requests | Resident targets from the reaction execution policy. |
| `promotion.*` reminders | Admin targets only; reminders are informational and the decision remains in HA-admin-gated UI. |
| `security.*` critical safety/security events | Residents and admins, subject to dedup and aggregation. |
| `security.*` diagnostic or configuration events | Admins/observability only. |
| `occupancy.*` mismatch/inconsistency | Observability first; admin notification only after persistence threshold; resident notification only if explicitly configured. |
| `people.*` arrive/leave transitions | Observability only by default. |
| `reaction.*` technical execution events | Observability only by default. |
| `system.*` configuration or health issues | Admins/observability only by default. |

Resident defaults must be conservative. A resident should not receive a burst of low-level events
such as multiple person-arrival messages followed by occupancy mismatch messages. The expected
resident experience is fewer, clearer notifications.

## Category Defaults

The category list is not itself an audience policy. It is a coarse gate used before delivery.

Required defaults:

- `reaction` must be a known category, but disabled for push notification delivery by default
- `people` transitions must not be resident-push-enabled by default
- `house_state` changes must not be resident-push-enabled by default
- `system` remains always observable, but system events still require audience routing before
  becoming push notifications
- unknown/custom event categories may be emitted to the Home Assistant event bus, but must not be
  assumed resident-safe for push delivery

If an admin enables a noisy category for push delivery, Heima must still apply deduplication,
rate-limiting, and aggregation.

`system` interpretation:

- system events are always emitted and retained for observability
- system events are not automatically pushed to every default route target
- configuration and health system events are admin-facing by default
- resident push for system events requires explicit policy

## Security Critical Events

Security-critical events are a bounded subset of security events that may bypass informational
startup grace or burst limits.

Security-critical examples:

| Event condition | Default audience |
|---|---|
| alarm triggered | residents and admins |
| armed away while someone is home | residents and admins |

Non-critical security examples:

| Event condition | Default audience |
|---|---|
| transient security/presence mismatch during startup | observability only |
| security presence mismatch that is not armed-away critical | admins after persistence |
| camera privacy source configuration issue | admins/observability |
| missing or unavailable security diagnostic binding | admins/observability |

Only stable upstream security state may make an event security-critical. Startup reconciliation,
unknown/unavailable states, or incomplete entity snapshots must not be treated as critical.

## Startup Grace Period

Home Assistant restarts and integration reloads can produce temporary inconsistencies while entity
states, availability, presence, room occupancy, and notify services settle.

Normative rules:

- after Heima startup/reload, informational push delivery must enter a grace period
- during the grace period, Heima may emit events and update diagnostics
- during the grace period, Heima must suppress resident/admin push notifications for transient
  mismatch, occupancy, presence, and configuration-summary events unless severity is critical and
  not startup-derived
- actionable runtime confirmation requests are not covered by this suppression once their reaction
  has evaluated normally
- security-critical events may bypass the grace period only when the event is based on stable
  security state and not on incomplete startup reconciliation

Recommended default:

- `startup_notification_grace_s = 300`

The grace period must be visible in diagnostics and in the admin observability panel.

## Persistence Thresholds

Mismatch and invariant notifications must distinguish between a momentary observation and a
persistent operational problem.

Normative rules:

- occupancy/presence mismatch notifications must not be sent immediately on first observation
- each mismatch family must have a persistence threshold before becoming push-notifiable
- warnings that do not persist remain visible in observability only
- when a mismatch resolves before the threshold, no push notification should be sent
- persistence state must be explainable in diagnostics

Recommended defaults:

| Family | Default threshold | Default audience after threshold |
|---|---:|---|
| `occupancy.*` mismatch | 10 minutes | Admin only |
| `security_presence_mismatch` | 5 minutes, unless security-critical | Admins after threshold; residents only for security-critical cases or explicit policy |
| installation/configuration summary issues | startup grace + one stable evaluation | Admin only |

## Aggregation And Collapse

Related events must be collapsed before push delivery when they describe the same operational
situation.

Required behavior:

- multiple person-arrival events in a short window should not produce one notification per person by
  default
- a sequence such as `people.arrive`, `occupancy.inconsistency`, and
  `invariant.presence_without_occupancy` should collapse into one notification only if the condition
  persists beyond threshold
- collapsed notifications must use human-readable text and avoid raw ids when display names are
  available
- the full uncollapsed event list remains available in diagnostics and observability

Recommended aggregation windows:

| Window | Default |
|---|---:|
| presence transition collapse | 2 minutes |
| mismatch aggregation | 5 minutes |
| global notification burst window | 1 minute |

Recommended burst limit:

- no more than 2 informational push notifications per minute globally
- security-critical actionable or alarm events may bypass the informational burst limit, but must
  still deduplicate by key/occurrence

## Message Quality

Human-facing notification text must be designed for the target audience.

Normative rules:

- resident notifications must not expose raw UUIDs when a reaction label, person display name, room
  display name, or policy label exists
- technical wording such as "injected steps", "invariant violation", or raw entity/debug ids must
  not be sent to residents
- admin notifications may include technical identifiers, but should still lead with a readable
  summary
- duplicate notifications with identical user-visible meaning must be deduplicated even when their
  internal event keys differ

## Configuration Surface

Defined in options flow (`core/options_flow_spec.md`):
- `recipients`
- `recipient_groups`
- `route_targets`
- `notification_service_capabilities`
- `enabled_event_categories`
- dedup/rate-limit controls
- audience routing controls
- startup grace controls
- persistence threshold controls
- aggregation/burst controls
- mismatch policy controls

Configuration contract:
- these options control the delivery pipeline and compatibility behavior
- they must not change the semantic meaning of a previously emitted event type, only whether or how
  it is emitted or delivered
- resident-safe defaults must be conservative even when a global route target points at residents

### External model alignment

Existing notification systems such as Prometheus Alertmanager and Grafana Alerting use routing
policies, receivers/contact points, grouping, timing, and mute controls. Heima follows the same
separation of concerns:

- classify the event
- choose the routing policy
- group/collapse related events
- apply timing/rate controls
- resolve logical recipients to delivery endpoints

Heima does not adopt Alertmanager's full routing-tree vocabulary because the product model has
home-specific audiences (`admins`, `residents`, `observability`) and actionable runtime
confirmation semantics. The persisted policy model below is intentionally smaller and domain
specific.

### Persisted policy model

The notification policy model is general. New implementation does not need to preserve the old
domain-specific persistence fields for mismatch thresholds.

Canonical shape:

```yaml
notifications:
  audience_targets:
    admins:
      - admins
    residents:
      - residents
  audience_policy:
    people:
      push: observability
    house_state:
      push: observability
    reaction:
      push: observability
    occupancy_mismatch:
      push: admins_after_persistence
    security_presence_mismatch:
      push: residents_and_admins_when_critical_else_admins_after_persistence
    system_config_issue:
      push: admins
  startup_notification_grace_s: 300
  persistence_thresholds:
    occupancy_mismatch: 600
    security_presence_mismatch: 300
    installation_config_issue: 300
  aggregation:
    presence_transition_window_s: 120
    mismatch_window_s: 300
    global_burst_limit:
      max_notifications: 2
      window_s: 60
```

Rules:

- `audience_targets.admins` and `audience_targets.residents` contain recipient ids or group ids
- `observability` is not a recipient, group, or notify service and must not be resolved through
  `route_targets`
- recommended group ids such as `admins` and `residents` are routing conventions only, not
  authorization boundaries
- HA admin authorization remains the authority boundary for admin decisions
- `audience_targets` is the preferred routing model for human-facing event notifications
- `route_targets` remains only a low-level default route for legacy generic event delivery and for
  runtime confirmations whose policy explicitly enables `use_default_route_targets`
- `persistence_thresholds` replaces domain-specific `*_persist_s` notification fields for new
  implementation
- old domain-specific persistence fields do not need to remain authoritative after this policy
  model is implemented

### Audience policy vocabulary

`audience_policy.<family>.push` is a closed vocabulary. Implementations must reject unknown values
instead of treating them as free-form routes.

Allowed values:

| Value | Meaning |
|---|---|
| `disabled` | Do not push. Keep event bus/diagnostics behavior defined by the event pipeline. |
| `observability` | Keep the event in diagnostics/admin observability only. No push delivery. |
| `admins` | Push to `audience_targets.admins`. |
| `residents` | Push to `audience_targets.residents`. Requires explicit admin opt-in for noisy families. |
| `residents_and_admins` | Push to both `audience_targets.residents` and `audience_targets.admins`. |
| `admins_after_persistence` | Push to admins only after the configured persistence threshold is met. |
| `residents_and_admins_after_persistence` | Push to residents and admins after the configured persistence threshold is met. |
| `residents_and_admins_when_critical_else_admins_after_persistence` | Push to residents and admins immediately for security-critical cases; otherwise push to admins after persistence. |

Fallback rules:

- if an admin-facing policy resolves no admin target, Heima must not fall back to residents
- if a resident-facing policy resolves no resident target, Heima must not fall back to admins unless
  the policy explicitly includes admins
- unresolved audience targets must be recorded in diagnostics and shown in the admin observability
  panel
- missing push targets must not prevent event bus emission or diagnostics retention
- actionable runtime confirmations follow `resident_runtime_confirmation_spec.md`; they do not use
  `audience_policy.<family>.push`

Default materialization:

- runtime must apply conservative implicit defaults when `audience_policy`, `audience_targets`,
  `persistence_thresholds`, or `aggregation` are absent
- the UI should display implicit defaults as defaults
- the UI may persist explicit defaults on save, but runtime behavior must not depend on defaults
  being physically written to options

Architecture name:

- the runtime component that applies audience policy, grace, persistence, aggregation, category
  gates, rate limits, burst limits, target resolution, and transport capability filtering is the
  **Notification Delivery Policy**.
- implementation may use a class name such as `NotificationDeliveryPolicy` or
  `NotificationPolicyEngine`, but diagnostics and docs should use "Notification Delivery Policy".

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
- `core/event_catalog_spec.md`
- `core/notification_recipients_spec.md`
- `core/notification_admin_ui_spec.md`
- `core/resident_runtime_confirmation_spec.md`
