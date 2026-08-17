# Heima Admin Observability Panel Spec

**Status:** Draft vNext
**Date:** 2026-07-16
**Scope:** Custom Home Assistant admin panel, runtime explainability, learning transparency
**Related specs:** `core/heima_monitoring_spec.md`, `core/events_and_notifications_spec.md`,
`core/resident_runtime_confirmation_spec.md`, `core/manual_hold_framework_spec.md`,
`core/runtime_checkpoint_and_power_recovery_spec.md`, `learning/proposal_lifecycle_spec.md`,
`learning/learning_system_spec.md`, `core/apply_step_contract.md`

## Purpose

Heima needs a real custom admin panel that makes the system transparent while it is running.

The panel must let an HA admin answer, without reading logs or running scripts:

1. What is Heima doing right now?
2. Why did Heima do or not do a specific thing?
3. What is Heima learning, with which evidence, and what will it ask the admin to review?
4. Which runtime requests, manual holds, notification routes, and proposal groups are currently
   affecting behavior?

This is a custom admin panel requirement. It must not be implemented as a minimal Options Flow
diagnostic page.

## Non-Goals

The admin observability panel must not become:

- a replacement for domain-specific policy editors
- a replacement for Home Assistant logbook/history
- a general-purpose Grafana-style metrics dashboard
- an external telemetry product
- a user-facing resident dashboard
- a read/write automation builder that duplicates Home Assistant automations

The panel may expose safe admin actions such as opening a reaction editor, clearing a manual hold,
or reviewing a pending promotion, but its first responsibility is explanation and inspection.

## Product Principles

### Explainability First

Every automated decision must be inspectable as:

```text
observed inputs -> matched rules/conditions -> blockers/guards -> execution decision -> outcome
```

The panel must show both positive and negative reasoning:

- why something matched
- why something did not match
- why something was skipped
- why something is waiting
- why something is blocked
- why something was learned
- why something was suppressed, grouped, or hidden from review

### Live State and Recent History

The panel must show:

- current state
- recent decision history
- currently pending items
- current learning/proposal backlog

It must not require the admin to reproduce an issue before any explanation is available.

### Domain-Agnostic Core, Domain-Specific Detail

The panel must use a generic observability model for:

- reactions
- apply steps
- runtime confirmations
- manual holds
- proposals
- learning evidence
- notifications

Domain-specific details may be added as structured extensions, but the panel must not hardcode
lighting-only, camera-only, or security-only assumptions.

### Safe Redaction

The panel is admin-only, but it must still follow the same redaction rules as diagnostics:

- secrets, tokens, auth headers, and raw credentials must never appear
- sensitive free-form values must be redacted when they may contain credentials
- entity IDs may be shown because they are required for local administration
- resident names and notification recipient IDs may be shown to HA admins

## Delivery Scope

This spec describes the target admin panel. Implementation must be phased so the first production
slice is useful and bounded.

### Read-Only Foundation

The first foundation slice is read-only and includes:

- backend observability snapshot contract
- redacted snapshot API for HA admins
- custom panel shell
- Overview
- Runtime Activity
- Health
- basic Reaction Inspector
- basic Manual Hold Center
- basic Runtime Confirmation Center
- Notification Routing Inspector

This foundation must not include write actions beyond links to existing Home Assistant/integration
configuration surfaces. Safe admin actions may be added only after this foundation is stable and
only through allowlisted backend boundaries.

### Production Inspector Scope

The production inspector scope adds:

- complete Decision Trace
- complete Reaction Inspector
- reaction detail routes/drawers
- production-grade filtering and search
- Learning Monitor
- Proposal Backlog Inspector
- proposal grouping/bundling transparency
- richer filtering and deep links
- exportable redacted observability snapshot for support/debugging

This scope maps to AO8 in the development plan.

### Advanced Debugging Scope

The advanced debugging scope adds entity-centric debugging and focused negative reasoning:

- Entity Impact Inspector
- "Why not now?" focused evaluation for one reaction
- trace timeline views grouped by reaction or entity

This scope maps to AO9 and AO10 in the development plan.

### Safe Admin Actions

Safe admin actions may include:

- clear admin-clearable holds
- reset runtime confirmation stats
- review promotion
- review proposal or proposal group

Future safe admin actions may include:

- acknowledge non-critical findings
- open/edit specific policies or reactions through stable Home Assistant/config-flow entry points

These actions must not be implemented before the read-only foundation is stable. Every action must
remain explicit, HA-admin-only, confirmed when behavior-changing, and audited through the runtime
observability event buffer.

Implemented AO7 actions:

- clear admin-clearable manual holds
- review runtime-confirmation promotion prompts
- reset runtime-confirmation promotion state
- review individual proposals
- review house-state proposal batches, including dismiss-similar semantics

Future candidate actions:

- acknowledge non-critical findings
- open/edit specific policies or reactions through stable Home Assistant/config-flow entry points

### Custom HA Admin Panel

Heima must expose a custom Home Assistant panel for HA admins.

Required properties:

- visible only to Home Assistant admins
- implemented as a real custom panel/web UI, not as an Options Flow page
- available from the Home Assistant sidebar or integration entry point
- capable of showing structured, navigable data
- capable of polling or subscribing for updates
- capable of deep-linking to specific reactions, requests, proposal groups, or events

The panel may be implemented with Home Assistant frontend conventions, but the backend contract
must not depend on a specific frontend framework.

### Observability Snapshot Backend

The backend must expose a single stable observability snapshot contract.

Conceptual shape:

```python
HeimaObservabilitySnapshot = {
    "meta": {...},
    "health": {...},
    "runtime": {...},
    "decision_traces": [...],
    "reactions": [...],
    "manual_holds": {...},
    "runtime_confirmations": {...},
    "notifications": {...},
    "recovery": {...},
    "learning": {...},
    "proposals": {...},
    "house_state": {...},
    "health_findings": [...],
    "recent_events": [...],
}
```

### Minimal Snapshot Schema

The first implementation must define these fields at minimum.

#### `meta`

```python
{
    "schema_version": 1,
    "generated_at": "2026-07-16T12:00:00+00:00",
    "entry_id": "...",
    "engine_version": "0.x.y",
    "is_partial": False,
    "partial_reasons": [],
    "retention": {
        "mode": "in_memory",
        "description": "history_since_last_restart",
        "started_at": "...",
    },
}
```

#### `health_findings[]`

```python
{
    "finding_id": "stable-id",
    "severity": "info|warning|error|critical",
    "reason_code": "no_actionable_route",
    "summary": "Runtime confirmation has no actionable route.",
    "affected_object_ids": ["reaction:r1", "group:residents"],
    "suggested_action": "Enable actions on at least one notify service.",
    "links": [{"kind": "notification_route", "id": "residents"}],
    "first_seen_at": "...",
    "last_seen_at": "...",
    "acknowledged": False,
}
```

`severity` here is intentionally a 4-level subset (`info|warning|error|critical`) of the general
`debug|info|warning|error|critical` event severity enum (`core/event_catalog_spec.md`) — health
findings are always admin-actionable by definition and never produced at `debug` level. This is a
deliberate scoping, not an inconsistency with `recent_events[]` below.

`acknowledged` is reserved for forward compatibility and must remain `False` until a persisted
health-finding acknowledgement model is implemented.

#### `recent_events[]`

```python
{
    "event_id": "stable-or-buffer-id",
    "timestamp": "...",
    "category": "reaction|manual_hold|notification|proposal|learning|health|admin_action",
    "severity": "debug|info|warning|error|critical",
    "summary": "...",
    "reason_code": "manual_hold_active",
    "object_links": [{"kind": "reaction", "id": "r1"}],
}
```

#### `decision_traces[]`

```python
{
    "trace_id": "...",
    "reaction_id": "r1",
    "occurrence_key": "...",
    "timestamp": "...",
    "outcome": "applied|skipped|blocked|waiting|failed|not_matched",
    "reason_codes": ["matched", "manual_hold_active"],
    "input_summary": {...},
    "condition_results": [...],
    "guard_results": [...],
    "apply_steps": [...],
    "links": [...],
}
```

#### `reactions[]`

```python
{
    "reaction_id": "r1",
    "reaction_type": "context_conditioned_lighting_scene",
    "label": "Studio contextual lighting",
    "enabled": True,
    "muted": False,
    "origin": "admin_authored|learning_accepted|migration|unspecified",
    "execution_policy": {
        "source": "inline|profile|profile_with_override|default_auto_apply|unresolved_reference",
        "mode": "auto_apply|ask_residents",
        "profile_id": None,
        "config_error": None,
    },
    "last_outcome": "applied|skipped|blocked|waiting|failed|unknown",
    "latest_trace_id": "...",
}
```

#### `runtime_confirmations`

```python
{
    "pending": [...],
    "pending_count": 0,
    "recent_completed": [...],
    "recent_completed_count": 0,
    "stale_responses": 0,
    "duplicate_occurrences": 0,
    "completed_by_status": {...},
    "scheduled_timeouts": [...],
    "action_event_subscription_active": False,
    "promotion_reviews": [...],
}
```

MVP snapshot consumers must not require fields outside this minimal schema.

Rules:

- The custom panel consumes this snapshot or smaller query-specific projections derived from it.
- UI code must not directly stitch together internal engine, proposal, event, and notification
  structures.
- The snapshot contract must be versioned.
- Unknown sections must be ignored by older frontends.
- Missing sections must degrade gracefully with an explicit unavailable state.

### Query-Specific Views

The backend may expose query endpoints in addition to the full snapshot:

- `overview`
- `reaction/{reaction_id}`
- `decision_trace/{trace_id}`
- `proposal_group/{group_id}`
- `runtime_confirmation/{request_id}`
- `manual_hold/{scope}`
- `learning/family/{family_id}`

These projections must be derived from the same canonical observability data model.

These endpoints are optional projections, not separate sources of truth. AO8 may reuse the full
snapshot directly when it already contains enough data for detail views.

### HA Frontend Integration Contract

The custom panel must be registered through Home Assistant's supported frontend/panel mechanisms.

Implementation requirements:

- panel registration must happen during integration setup and be removed on unload
- the panel must load local integration-owned frontend assets
- the panel must communicate with backend data through HA-authenticated websocket/API calls
- frontend routing must support direct links to major inspectors
- the frontend must not embed secrets or long-lived credentials
- the panel must degrade gracefully when frontend assets fail to load

Preferred backend transport:

- websocket command for snapshot and projections
- optional diagnostic service/export remains separate

Non-admin users must not receive data even if they manually call the websocket/API command.

## Panel Sections

### 1. Overview

The Overview is the first screen. It must answer "what is happening now?"

Required cards/sections:

- Engine status
- Current house state and reason
- Current security/alarm summary when configured
- Active manual holds
- Pending runtime confirmations
- Recent applied/skipped/failed steps
- Proposal backlog summary
- Learning activity summary
- Notification delivery health
- Health findings and config errors

Example content:

```text
Engine: enabled
House state: home
Runtime confirmations: 1 pending
Manual holds: 2 active
Reactions: 14 configured, 2 muted, 1 recently blocked
Proposals: 47 visible groups / 104 real pending proposals
Latest issue: notify.mobile_app_tablet does not support actions
```

### 2. Runtime Activity

The Runtime Activity view shows recent runtime facts in chronological order.

Each item must include:

- timestamp
- category
- entity/reaction/request/proposal identifier when relevant
- concise human-readable summary
- machine-readable reason code
- severity
- link to deeper inspection

Required event classes:

- domain input observed
- state changed
- reaction matched
- reaction did not match
- apply step planned
- apply step applied
- apply step skipped
- apply step blocked
- manual hold acquired/released
- runtime confirmation created/resolved/expired
- notification delivered/skipped/failed
- proposal created/suppressed/grouped/stale/accepted/rejected

Non-match tracing rule:

- match/apply/skip/block/wait/fail events should be traced by default
- full per-reaction `not_matched` traces must not be emitted for every reaction on every cycle by
  default
- non-match data should be summarized as last-evaluated state or captured only when explicitly
  requested for a reaction/debug session
- the panel may expose a "why not now?" query for a specific reaction, which computes or retrieves
  a focused non-match explanation

### 3. Decision Trace

Decision Trace is the core explainability view.

For each inspected reaction occurrence, the panel must show:

- source trigger or evaluation reason
- relevant input snapshot
- reaction identity
- normalized config summary
- execution policy effective source:
  - inline
  - profile
  - profile with override
  - default auto-apply
  - unresolved reference
- condition evaluation table
- blocker/guard evaluation table
- generated apply steps
- manual hold checks
- runtime confirmation decision
- notification routing decision when applicable
- final outcome

Example:

```text
Reaction: camera_privacy_policy__interna__armed_night__turn_off
Outcome: applied

Why:
- alarm state armed_night matched
- house state guest did not block
- manual hold for switch.interna_privacy was inactive
- execution policy: auto_apply
- step switch.turn_off target switch.interna_privacy applied
```

Negative example:

```text
Reaction: studio_context_lighting_2200
Outcome: waiting_for_resident_confirmation

Why:
- weekday Sunday matched
- time bucket 22:00 matched
- activity reading matched
- execution policy profile ask_residents_default selected
- notification route residents resolved to notify.mobile_app_iphone_stefano
- request expires in 9 minutes
```

Blocked example:

```text
Reaction: studio_context_lighting_2200
Outcome: skipped

Why:
- generated 2 apply steps
- light.studio_main blocked by manual_hold_active
- light.desk skipped because dependency light.studio_main was blocked
```

### 4. Reaction Inspector

The Reaction Inspector shows one configured reaction.

Required fields:

- reaction ID
- reaction type
- label
- enabled/muted state
- origin:
  - admin-authored
  - learning accepted
  - migration/import
  - unspecified
- source template ID when any
- admin-authored template ID when any
- normalized reaction config
- generated apply step shape
- dependencies
- supported runtime-confirmation descriptor status
- effective execution policy
- linked manual hold scopes
- last matched occurrence
- last applied/skipped/failed outcome
- latest related decision traces
- latest related runtime confirmations
- latest related proposals when any

The inspector must distinguish:

- configured source data
- normalized/effective data
- runtime-generated data
- historical outcome data

### 5. Manual Hold Center

The Manual Hold Center shows why automations are currently stopped or deferred.

Required fields per hold:

- scope
- source entity
- reason
- message
- release policy
- acquired timestamp
- age
- expiration when any
- release trigger when known
- affected apply steps/reactions

Required navigation and explanations:

- link to affected reaction inspector
- link to source entity in Home Assistant when possible
- explain whether the hold is admin-clearable when future actions are enabled

Clearing an admin-clearable hold is implemented in AO7. It must use the same manual-hold backend
boundary as the service layer, require explicit admin confirmation, and record an admin action
event.

The panel must show default lifecycle rules, for example:

```text
Camera privacy hold for switch.interna_privacy:
active until next disarmed -> armed alarm cycle, or manual clear if configured.
```

### 6. Runtime Confirmation Center

The Runtime Confirmation Center shows resident/admin actionable request state.

Required sections:

- pending runtime requests
- recently completed runtime requests
- stale duplicate responses
- timeout-applied and timeout-skipped requests
- delivery failures
- promotion review state
- promotion cooldown state

Required fields per runtime request:

- request ID
- reaction ID
- occurrence key
- title/message
- confirmation targets
- resolved notification routes
- skipped non-actionable routes
- unresolved targets
- timeout behavior
- expiration timestamp
- stored apply steps
- current status
- response source if known
- final apply result

The panel must clearly distinguish:

- resident approval of one runtime occurrence
- admin approval of a promotion to auto-apply
- proposal acceptance

### 7. Notification Routing Inspector

The Notification Routing Inspector explains how notifications are routed.

Required views:

- recipients
- groups
- default route targets
- concrete `notify.*` services
- `supports_actions` capability
- recent delivery attempts
- delivery failures
- unresolved targets
- non-actionable services skipped for actionable messages

Example:

```text
Runtime confirmation target: residents
Resolved:
- stefano -> notify.mobile_app_iphone_stefano, supports actions
- antonia -> notify.mobile_app_iphone_antonia, supports actions
Skipped:
- notify.persistent_notification, text only
```

### 8. Learning Monitor

The Learning Monitor shows what Heima is learning and why.

Required sections:

- learning families
- evidence growth
- generated proposals
- suppressed proposals
- visible review representatives
- proposal bundles/groups
- stale proposals
- accepted/rejected/dismissed history

For each learned pattern candidate:

- proposal ID
- proposal type/family
- visible representative ID if any
- review group ID
- support and total observations
- confidence
- weeks/days observed when relevant
- time buckets
- rooms/entities/context dimensions
- learning diagnostics payload summary
- why generated
- why suppressed or grouped

The panel must explicitly show the difference between:

- real pending proposal count
- visible representative count after grouping/bundling
- suppressed pending count
- rejected bundle count
- dismissed similar count

This is required so an admin can understand cases like:

```text
Visible queue: 47 groups
Real pending proposals: 104
Suppressed by review group: 57
```

### 9. Proposal Backlog Inspector

The Proposal Backlog Inspector focuses on review mechanics.

Required capabilities:

- filter by proposal type/family
- filter by visible/hidden/suppressed/stale
- inspect one review group
- inspect siblings in the same group
- show why one proposal is the visible representative
- show what will happen on:
  - accept representative
  - reject bundle
  - dismiss similar
  - skip

The panel must preserve the existing semantic distinction:

- rejecting a visible representative must not necessarily reject every similar proposal
- reject bundle and dismiss similar have different meanings and must be visible
- if a more specific sibling remains valid after rejection, the panel must make that clear

### 10. Health and Configuration Findings

The panel must aggregate actionable issues.

Required finding types:

- unresolved entity
- unavailable entity
- unresolved execution policy reference
- invalid notification route
- actionable route missing
- notification service missing `supports_actions`
- identity collision
- lighting slot collision
- manual hold stuck beyond expected lifecycle
- runtime confirmation request delivery failed
- proposal backlog stale
- analyzer disabled or insufficient evidence
- config migration warning

Each finding must include:

- severity
- stable reason code
- human-readable summary
- affected object IDs
- suggested admin action
- link to the relevant inspector

## Data Model Requirements

### Stable IDs

Every inspectable item must have a stable ID:

- reaction ID
- runtime request ID
- decision trace ID
- manual hold scope
- proposal ID
- review group ID
- notification target ID
- finding ID

### Reason Codes

Every non-trivial outcome must expose machine-readable reason codes.

Examples:

- `matched`
- `condition_not_met`
- `manual_hold_active`
- `dependency_blocked`
- `dependency_failed`
- `no_actionable_route`
- `delivery_failed`
- `unresolved_execution_policy_ref`
- `proposal_group_suppressed`
- `insufficient_evidence`

Reason codes must be stable enough for tests and admin filtering.

### Human-Readable Explanation

The snapshot must include short explanatory text suitable for the panel.

Rule:

- the backend provides domain facts and reason codes
- the frontend may format them
- the frontend must not infer missing semantics from raw nested config alone

### Raw Data Access

Each inspector may expose a raw JSON drawer for advanced debugging.

Rules:

- raw JSON must be redacted
- raw JSON must be secondary to structured explanation
- raw JSON must not be the only way to understand a decision

## Frontend Requirements

### Layout

The custom panel must use a work-focused admin layout:

- left navigation by section
- compact summary cards
- dense tables for events/proposals/reactions
- inspector side panel or detail route
- filters and search
- clear status badges
- timestamps shown with local timezone

No marketing layout, no oversized hero, no decorative UI.

### Required Navigation

Minimum top-level navigation:

- Overview
- Runtime Activity
- Reactions
- Manual Holds
- Confirmations
- Notifications
- Learning
- Proposals
- Health

### Filtering

Required filters:

- time range
- severity
- domain/family
- reaction type
- reaction ID
- entity ID
- status
- reason code
- proposal type
- visible/suppressed/stale

Filtering must be implemented against fields already present in the observability snapshot or
explicit backend projections. The frontend may filter local table rows for display, but it must not
derive authoritative backend counts or grouping semantics locally.

### Refresh Model

The panel must support:

- manual refresh
- periodic refresh
- future live update subscription

Initial implementation may poll.

Polling interval must be configurable or bounded to avoid excessive HA load.

## Backend Integration Requirements

### HA Services and Websocket/API

The implementation may expose:

- a Home Assistant websocket command for the panel
- an HTTP endpoint
- a service response payload for existing diagnostic tooling

Preferred direction:

- websocket/API for panel data
- existing diagnostics service remains export/debug oriented

### Reuse Existing Diagnostics

Existing diagnostics are useful but not sufficient.

The observability backend may reuse:

- `engine.diagnostics()`
- config entry diagnostics
- proposal engine diagnostics
- event store diagnostics
- runtime confirmation diagnostics
- manual hold diagnostics
- reaction plugin diagnostics

But it must normalize them into the admin panel contract.

Diagnostics relationship rules:

- config-entry diagnostics remain raw/export/debug oriented
- observability snapshot is admin-product oriented
- shared high-level counts must not diverge without an explicit reason field
- the frontend must not reimplement proposal grouping, runtime confirmation eligibility, or
  reaction policy resolution from raw diagnostics
- diagnostics may contain more raw detail than the panel, but the panel must contain better
  explanation

### Event Trace Retention

The backend must keep a bounded recent trace buffer.

Required properties:

- bounded memory
- per-entry timestamp
- stable trace/event ID
- links to affected objects
- redacted context
- configurable or fixed retention count

Initial suggested retention:

- latest 500 runtime activity events
- latest 100 decision traces
- latest 100 notification delivery attempts

### Restart Semantics

MVP retention may be in-memory only.

If MVP retention is in-memory:

- the panel must show an explicit "history since last restart" indicator
- missing pre-restart traces must not be presented as "no activity"
- runtime confirmations remain governed by `resident_runtime_confirmation_spec.md`; pending
  runtime requests are not made restart-safe by this panel spec

Future production hardening may persist a compact event/trace ring buffer if production debugging shows that
restart volatility prevents useful investigation.

Persisted traces, if introduced, must be:

- bounded
- redacted before storage
- versioned
- safe to discard during migration failures

## Admin Actions

The read-only foundation may include navigation to existing config flows. Mutations are allowed
only in the safe-admin-action slice and only through existing backend boundaries.

Allowed admin actions:

- clear admin-clearable manual hold
- reset runtime confirmation stats
- review promotion
- review individual proposal
- review proposal group

Allowed navigation-only actions:

- open reaction editor
- open policy editor
- open proposal review

Future candidate mutation actions:

- mark non-critical finding acknowledged

Rules:

- AO1-AO6 are read-only except for navigation/deep links
- AO7 is the first phase allowed to introduce mutations
- destructive actions require confirmation
- actions must use existing backend boundaries, not mutate internal state directly from frontend
- all actions must record a runtime/admin event

## Security

Access rules:

- HA admin only
- no resident/non-admin access
- no unauthenticated endpoint
- no secrets in snapshots
- no raw tokens or auth headers

The panel must use Home Assistant authentication and authorization.

Security requirements:

- hiding the sidebar item is not sufficient authorization
- every websocket/API command must check HA admin permissions server-side
- every future mutation command must check HA admin permissions server-side
- non-admin attempts must return an authorization error and must not leak partial data
- authorization behavior must be unit-tested
- future mutation actions must emit an admin audit event

## Proposal and Learning Semantics

The panel must use the existing proposal lifecycle and TB grouping semantics.

Rules:

- visible representative counts must come from the proposal/review grouping backend
- real pending counts must come from the proposal backend
- suppressed-by-group counts must come from backend grouping state
- reject bundle and dismiss similar must keep their existing semantics
- the frontend must not recompute similarity buckets as a source of truth
- if the frontend displays local grouping, it must be clearly marked as display-only

The Proposal Backlog Inspector must explain what backend action each available review action will
perform before the admin clicks it.

## Health Finding Lifecycle

Health findings are derived observations, not permanent records by default.

Lifecycle rules:

- a finding appears when its condition is currently true or was observed in the retained event
  window
- a finding disappears when the condition is no longer true and no retained event requires it
- `first_seen_at` and `last_seen_at` apply within the available retention window unless persisted
  finding storage is introduced
- acknowledgement is not part of MVP
- if acknowledgement is introduced later, it must not hide critical active findings by default
- acknowledged findings must reappear if severity increases or affected object IDs change

Severity enum:

| Severity | Meaning |
|---|---|
| `info` | Useful status or explanation; no action required. |
| `warning` | Configuration or runtime condition may need attention. |
| `error` | Feature is not functioning as configured. |
| `critical` | Safety/security-relevant behavior is blocked or actively wrong. |

## Testing Requirements

Required tests:

- observability snapshot schema tests
- redaction tests
- panel API admin-only authorization tests
- decision trace construction tests
- reaction inspector tests
- manual hold center tests
- runtime confirmation center tests
- notification routing inspector tests
- learning/proposal grouping explanation tests
- frontend smoke tests for all top-level routes
- serialization/backward compatibility tests for snapshot versioning

Live tests should verify at least:

- camera privacy policy decision trace
- manual hold active/release trace
- runtime confirmation pending/resolved trace
- notification route with actionable and non-actionable services
- proposal backlog grouping counts

## Phased Implementation

### AO1 — Backend Snapshot Contract

- Define snapshot schema and version.
- Build read-only snapshot aggregator from existing diagnostics.
- Add redaction.
- Add unit tests.
- MVP phase.

### AO2 — Runtime Activity and Decision Trace

- Add bounded trace buffer.
- Emit structured decision traces for reactions and apply steps.
- Expose manual hold and runtime confirmation links.
- The foundation must include match/apply/skip/block/wait/fail traces; full non-match tracing may
  remain a focused query.

### AO3 — Custom Admin Panel Shell

- Register HA custom panel.
- Implement Overview, Runtime Activity, and Health routes.
- Use snapshot API.
- MVP phase.

### AO4 — Reaction and Manual Hold Inspectors

- Implement reaction list/detail.
- Implement manual hold center.
- Add links from runtime events to inspectors.
- MVP may implement basic inspectors; complete inspector detail belongs to AO8.

### AO5 — Runtime Confirmation and Notification Inspectors

- Implement pending/completed request views.
- Implement notification route inspector.
- Show actionable capability decisions.
- MVP may implement basic read-only inspectors; complete delivery history belongs to a future
  notification-delivery-history slice.

### AO6 — Learning and Proposal Transparency

- Implement learning monitor.
- Implement proposal backlog inspector.
- Show representative vs real proposal counts and suppression reasons.
- MVP/production-inspector phase.

### AO7 — Admin Actions

- Add safe actions through existing backend boundaries.
- Add audit events for admin actions.
- Post-read-only phase only.

### AO8 — Usability, Filtering, and Detail Views

AO8 turns the MVP table-oriented panel into a usable production inspector without expanding its
mutation surface.

Deliverables:

- Add reaction detail view or side drawer.
- Add manual hold detail view or side drawer.
- Add runtime confirmation detail view or side drawer.
- Add proposal/review-row detail view or side drawer.
- Add table filters and search for high-volume sections.
- Improve table layout so long IDs, badges, and execution-policy labels do not wrap into unreadable
  fragments.
- Add copy buttons for IDs, trace IDs, entity IDs, and request IDs.
- Add stable deep links for route + object ID within the custom panel.
- Add "Export snapshot" actions for the already-redacted observability snapshot without exposing
  secrets:
  - download JSON file
  - copy JSON to clipboard
- Add a House State section that explains the current resolver outcome without requiring admins to
  inspect raw JSON.

Backend requirements:

- The existing snapshot may be reused if it already contains enough data.
- If a detail view needs additional derived data, add it to the backend projection rather than
  reconstructing it from raw diagnostics in the frontend.
- Snapshot export must use the same redaction path as the panel data.
- Download and clipboard export must serialize the exact same redacted snapshot object currently
  available to the panel.
- House-state diagnostics must be derived from the existing `house_state` runtime domain
  diagnostics. AO must not reimplement the house-state resolver or infer a different result in the
  frontend.
- No new write actions are introduced in AO8.

AO8 implementation slices:

- AO8.1: backend detail projections for reactions, holds, confirmations, and proposal/review rows
- AO8.2: frontend detail drawer/routes and readable table layout
- AO8.3: filters, search, copy buttons, and stable deep links
- AO8.4: redacted snapshot export
- AO8.5: house-state resolver diagnostics

Reaction detail must show:

- reaction ID, label, type, origin, author kind, template/source metadata
- enabled/muted state
- configured metadata and runtime diagnostics, separated clearly
- effective execution policy
- generated/applicable apply-step summaries when available
- latest decision trace and recent linked traces
- linked manual holds
- linked runtime confirmations or promotion reviews when available
- linked proposal/source proposal when available

Filtering/search minimum:

- reactions: text, reaction type, origin, enabled/muted, last outcome, has linked hold
- traces/events: text, outcome/severity, reason code, reaction ID, entity ID
- holds: domain, scope, release policy, source entity
- confirmations: pending/completed, status, reaction ID
- proposals: visible/suppressed/stale, type, follow-up kind
- house state: candidate name, candidate status, reason, input signal

Tests:

- unit tests for reaction detail projection completeness
- unit tests for snapshot export redaction
- frontend/static smoke tests proving detail routes and filters are wired
- live `080` extension checking at least one reaction has real metadata, not only `unknown`
- snapshot contract tests proving `house_state.candidate_trace`,
  `house_state.candidate_summary`, and `house_state.resolution_trace` are exposed as dictionaries

Acceptance criteria:

- an admin can open one reaction and understand its configured identity, current status, recent
  traces, linked holds, and execution policy without reading raw JSON
- long IDs and badges remain readable on desktop/tablet widths
- high-volume tables can be searched/filtered without changing backend semantics
- snapshot export is redacted and safe to share for support through both download and clipboard
  flows
- an admin can understand why the current house state was selected, which candidates were active,
  and which resolver path/reason won without downloading the snapshot

### AO9 — Entity Impact Inspector

AO9 adds an entity-centric view: "what is affecting this HA entity?"

Motivation:

Admins often debug symptoms through the entity they observe in HA, not through Heima reaction IDs.
For example, a camera privacy switch may remain on/off unexpectedly, or a light may not follow an
expected scene. The panel must let the admin start from the entity and see every Heima object that
can affect it.

Deliverables:

- Add an `Entities` or `Entity Impact` section.
- Build an entity index from apply steps, reaction configs, manual holds, decision traces, runtime
  confirmations, and security camera privacy sources.
- Add entity detail view.
- Add search by entity ID.
- Link entity rows back to reactions, traces, holds, requests, and policies.

Entity detail must show:

- entity ID and domain
- reactions that target or reference the entity
- latest Heima decision trace involving the entity
- recent apply steps involving the entity
- active manual holds involving the entity
- pending applies involving the entity
- runtime confirmations involving the entity
- source policies/config entries that reference the entity when known
- last known outcome from Heima's perspective

Rules:

- The entity inspector is not a replacement for HA logbook/history.
- The panel may show links to HA entity pages/logbook when feasible, but it must not scrape HA
  history.
- Notification routes enter the entity index only when they can be linked to an entity-bearing
  request, apply step, trace, or policy. A generic notification recipient/group is not a Home
  Assistant entity and must not be indexed as one.
- The entity index must be backend-derived so UI counts and links are consistent.
- Domain-specific relationships are allowed only as structured backend metadata. For example,
  camera privacy policy may expose that `switch.interna_privacy` is the privacy entity for source
  `interna`; the frontend must not infer this from naming conventions.

Tests:

- entity index projection tests for light apply steps
- entity index projection tests for camera privacy policy entities
- manual hold entity-link tests
- runtime confirmation entity-link tests
- live smoke test for a camera privacy entity or known test-light entity

Acceptance criteria:

- an admin can search for an entity and see what Heima reactions/holds/traces currently affect it
- camera privacy and lighting cases are explained through the same generic entity-impact model
- no entity relationship is inferred from hardcoded Italian labels, room names, or entity-name
  substrings

### AO10 — Focused "Why Not Now?"

AO10 adds focused negative reasoning for one reaction at a time.

Motivation:

The runtime trace buffer explains what happened recently. It does not necessarily explain why a
specific reaction did not run if it was not part of the filtered apply plan. Admins need an
explicit, bounded query that answers: "if Heima evaluated this reaction now, why would it apply,
skip, wait, or block?"

Deliverables:

- Add an HA-admin-only websocket query, separate from mutation actions.
- Add a reaction detail button/section: `Why not now?`.
- Return a focused evaluation result for one reaction ID.
- Include condition results, guard results, policy decision, manual-hold blockers, runtime
  confirmation decision, and candidate apply-step summaries when available.
- Record an observability event that the admin ran a focused inspection, without changing runtime
  state.

Backend contract:

```python
WhyNotNowResult = {
    "reaction_id": "...",
    "generated_at": "...",
    "outcome": "would_apply|would_wait|would_block|would_skip|not_evaluable|not_found",
    "reason_codes": [...],
    "input_summary": {...},
    "condition_results": [...],
    "guard_results": [...],
    "policy_result": {...},
    "apply_steps": [...],
    "links": [...],
}
```

Rules:

- The query must be read-only.
- The query evaluates against the engine's current canonical/runtime state as seen by the latest
  coordinator cycle. It must not refresh the global snapshot, rebuild all reactions, or recompute
  unrelated domains as a side effect.
- It must not enqueue apply steps.
- It must not create runtime confirmation requests.
- It must not mutate manual holds.
- It must not update proposal lifecycle state.
- It must be rate-limited so the UI cannot trigger expensive focused evaluations on every render.
- The default limit is 2 focused evaluations per minute per config entry.
- If it does not materially complicate the first implementation, this limit should be configurable
  from admin configuration without requiring a Home Assistant restart. Runtime configurability must
  use the normal config entry/options update path and must not introduce a separate ad-hoc state
  store.
- If runtime configurability would add meaningful complexity to the first AO10 slice, ship the
  fixed 2/minute default first and track runtime-configurable rate limits as a follow-up AO10
  sub-slice.
- If a reaction type cannot support focused evaluation yet, return `not_evaluable` with an explicit
  reason instead of guessing.

Implementation guidance:

- Prefer extending reaction/plugin contracts with an optional focused-evaluation hook.
- Do not implement a one-off lighting-only evaluator.
- If the first implementation supports only a subset of reaction types, the API must make the
  unsupported state explicit and the UI must display it clearly.
- Use existing condition/guard/apply-step validation helpers wherever possible.

Tests:

- authorization tests for the focused query
- not-found and not-evaluable tests
- rate-limit tests for the default 2/minute behavior
- read-only tests proving no apply plan, manual hold, runtime request, or options state mutates
- supported-reaction focused evaluation tests
- frontend smoke test for the reaction detail `Why not now?` affordance

Acceptance criteria:

- an admin can ask why one reaction would not run now
- unsupported reaction types fail explicitly, not as `unknown`
- the query is safe to run repeatedly and cannot apply actions
- repeated UI calls are bounded by the configured/default rate limit
- the result links back to traces, holds, entities, and policies when available

## Acceptance Criteria

The feature is complete when an HA admin can answer these questions from the panel:

- What did Heima do in the last few minutes?
- Why did a specific reaction apply, skip, block, or wait?
- Which manual holds are active and what will release them?
- Which runtime confirmations are pending and where were they sent?
- Which notification services support actions and which were skipped?
- What is Heima learning right now?
- Why is a proposal visible or hidden by grouping?
- How many real proposals exist behind visible representatives?
- Which configured reactions are active, muted, broken, or waiting for evidence?
- Which health/config findings require admin action?

The panel must make these answers available without requiring logs, shell scripts, or raw JSON
diagnostics as the primary workflow.
