# Resident Runtime Confirmation Spec

**Status:** Draft vNext
**Date:** 2026-07-12
**Related specs:** `core/events_and_notifications_spec.md`,
`core/notification_recipients_spec.md`, `core/apply_step_contract.md`,
`core/manual_hold_framework_spec.md`, `learning/context_conditioned_lighting_learning_spec.md`

## Purpose

Resident runtime confirmation lets Heima ask residents before applying a specific runtime action
that has already been approved or configured by an admin.

This is a runtime execution-control feature, not a proposal-review feature.

This feature is intended for automations that are useful but should remain assistive until household
behavior shows that residents usually want the action to happen automatically.

Example:

- Heima has an accepted learned lighting reaction for a room.
- Around the learned context, the reaction would turn one light off and set another light to low
  brightness.
- Instead of applying the scene immediately, Heima asks residents whether to apply it now.
- If residents often approve, Heima may later ask whether this specific reaction should become
  automatic.

## Scope

In scope:

- per-reaction execution policy: apply directly or ask residents first
- runtime action requests generated from concrete `ApplyStep` plans
- actionable resident notifications for approve/dismiss decisions
- target resolution through the existing notification recipient model
- bounded request expiration and deduplication
- configurable timeout behavior: skip or apply when residents do not answer
- confirmation outcome tracking per reaction
- promotion prompts from `ask_residents` to `auto_apply`
- progressive cooldown when residents decline promotion with "not now"
- admin-visible override/reset controls for promoted reactions

Out of scope for the first implementation slice:

- arbitrary actions embedded in notification payloads
- resident editing of reaction configuration from a notification
- multi-step conversational flows in chat or voice assistants
- requiring all residents to approve before an action may run
- long-lived persisted action requests across Home Assistant restarts
- using this mechanism for admin proposal review
- storing runtime confirmation requests in the learning proposal backlog
- enabling this behavior for every reaction family by default

## Non-Goals

Resident runtime confirmation must not replace:

- learning proposal review
- admin-authored policy editors
- manual hold
- safety constraints
- notification routing configuration

Normative rule:

- Admin approval/configuration decides whether a reaction may exist.
- Resident runtime confirmation decides whether one concrete occurrence of that reaction should be
  applied now.
- Promotion approval decides whether that already-approved reaction may stop asking residents in
  future occurrences.

## Relationship to Proposal Review

Heima has two distinct decision flows.

### Stable configuration flow

The existing proposal flow is a stable configuration flow:

```text
learning/admin proposal
-> admin review
-> accept/reject/edit
-> configured reaction
-> runtime execution
```

This flow is owned by the learning/admin proposal lifecycle. Accepting a proposal creates or updates
persistent reaction configuration.

### Runtime confirmation flow

Resident runtime confirmation is a one-shot execution flow:

```text
configured reaction already exists
-> reaction runtime fires
-> concrete apply plan is produced
-> resident actionable notification
-> approve/dismiss
-> apply or skip this occurrence only
```

This flow is owned by runtime execution. Approving a runtime request must not create a new reaction,
accept a learning proposal, or modify the stable configured-reaction payload.

### Separation Rules

Normative rules:

- `RuntimeActionRequest` is not a `ReactionProposal`.
- Runtime action requests must not appear in the admin learning proposal review queue.
- Runtime action requests must not use proposal `accepted` semantics, because proposal acceptance
  means "persist this behavior", while runtime approval means "apply this occurrence once".
- Runtime action requests may reuse architectural patterns from proposals: persisted records,
  explicit status, stable ids, deduplication keys, event/notification emission, diagnostics, and
  lifecycle cleanup.
- Any shared helper must preserve the semantic separation between proposal review and runtime
  execution approval.

| Flow | Object | Decider | Effect | Lifetime |
|---|---|---|---|---|
| Learning/admin review | `ReactionProposal` | Admin | Creates or updates configured reaction | Long-lived |
| Runtime confirmation | `RuntimeActionRequest` | Resident | Applies or skips one occurrence | Short-lived |
| Auto-apply promotion | Promotion review state | HA admin | Changes execution policy for one existing reaction | Long-lived config effect |

## Core Concepts

### ExecutionPolicy

Each eligible reaction may declare an execution policy.

```yaml
execution_policy:
  mode: auto_apply
```

Supported modes:

| Mode | Meaning |
|---|---|
| `auto_apply` | Current behavior: eligible runtime steps are applied directly. |
| `ask_residents` | Runtime steps are converted into a resident action request and are not applied until approved. |

Default rule:

- If no `execution_policy` is configured, behavior is `auto_apply`.
- Existing reactions must continue to behave as they did before this feature.

The execution policy belongs to the reaction instance, not to the analyzer family globally.

Eligibility rule:

- reaction families must explicitly opt in to resident runtime confirmation
- unsupported reaction families must ignore `ask_residents` configuration with a validation error,
  not silently fall back to direct apply
- supported reaction families must register a runtime-confirmation descriptor
- the first supported family is learned context-conditioned lighting scenes

### RuntimeConfirmationDescriptor

The runtime confirmation layer is generic. Domain-specific semantics are supplied by each reaction
family that opts in.

Conceptual contract:

```python
@dataclass(frozen=True)
class RuntimeConfirmationDescriptor:
    reaction_type: str
    occurrence_key: Callable[[HeimaReaction, DecisionSnapshot, list[ApplyStep]], str]
    render_request: Callable[[HeimaReaction, list[ApplyStep], str], RenderedRuntimeRequest]
    validate_stored_plan: Callable[
        [RuntimeActionRequest, DecisionSnapshot],
        RuntimePlanValidationResult,
    ] | None = None
    validate_context: Callable[
        [RuntimeActionRequest, DecisionSnapshot],
        RuntimePlanValidationResult,
    ] | None = None
```

Responsibilities:

| Hook | Purpose |
|---|---|
| `occurrence_key` | Defines the deduplication key for one runtime occurrence. |
| `render_request` | Produces resident-facing title/message text from the stored steps. |
| `validate_stored_plan` | Optional domain-specific pre-apply validation for the stored plan. |
| `validate_context` | Optional domain-specific context revalidation when configured. |

Rules:

- a reaction family must not support `ask_residents` without a descriptor
- the central runtime owns request lifecycle, notification transport, timeout handling, and generic
  pre-apply filtering
- the descriptor must not apply steps directly
- `validate_stored_plan` must not recompute a replacement action plan by re-running the reaction
- if `validate_stored_plan` is absent, only generic pre-apply validation runs
- if a family exposes `require_context_revalidation: true`, the descriptor must implement
  `validate_context`; otherwise the configuration is invalid

Examples:

| Reaction kind | Descriptor occurrence key strategy |
|---|---|
| Scheduled lighting scene | `reaction_id`, local date, scheduled window |
| Context-conditioned lighting scene | `reaction_id`, context activation window, local date |
| Alarm state action | `reaction_id`, alarm entity, transition state/timestamp bucket |

### ConfirmationPolicy

When `mode: ask_residents`, the policy may include confirmation settings:

```yaml
execution_policy:
  mode: ask_residents
  confirmation:
    target_groups:
      - residents
    expires_in_minutes: 10
```

Fields:

| Field | Type | Default | Meaning |
|---|---:|---:|---|
| `target_recipients` | list[str] | `[]` | Logical recipient ids from the notification recipient model. |
| `target_groups` | list[str] | `[]` | Logical recipient group ids from the notification recipient model. |
| `use_default_route_targets` | bool | `true` when no explicit targets are configured | Whether to fall back to global notification `route_targets`. |
| `expires_in_minutes` | int | `10` | Time after which approving the request has no effect. |
| `on_timeout` | str | `skip` | Behavior when no resident answers before expiration: `skip` or `apply`. |
| `require_context_revalidation` | bool | `false` unless the descriptor supports it | Whether domain-specific context validation must still pass before stored steps run. |

Target precedence:

1. If `target_recipients` or `target_groups` is non-empty, use those explicit targets.
2. Otherwise, if `use_default_route_targets` is true, use the global notification `route_targets`.
3. Otherwise, the request has no target and must fail closed.

At least one effective notification target must resolve through the canonical notification recipient
model. If none resolves, Heima must not silently auto-apply. It must mark the request `failed` and
record the delivery failure in diagnostics.

`on_timeout` semantics:

| Value | Meaning |
|---|---|
| `skip` | If nobody answers before `expires_at`, Heima skips the stored plan. |
| `apply` | If nobody answers before `expires_at`, Heima applies the stored plan after pre-apply validation. |

Default rule:

- `on_timeout` defaults to `skip`.
- `dismiss` always prevents apply, even when `on_timeout: apply`.
- `approve` applies immediately, before timeout, if pre-apply validation passes.

### RuntimeActionRequest

A runtime action request is the bounded, concrete object residents can approve or dismiss.

It represents a concrete apply plan already produced by an existing configured reaction. It does not
represent a candidate automation and does not participate in proposal acceptance.

Conceptual model:

```python
@dataclass
class RuntimeActionRequest:
    request_id: str
    reaction_id: str
    reaction_type: str
    occurrence_key: str
    title: str
    message: str
    apply_steps: list[ApplyStep]
    created_at: datetime
    expires_at: datetime
    on_timeout: str
    status: str
    confirmation_targets: list[str]
    context_snapshot: dict[str, Any]
    apply_result: RuntimeApplyResult | None = None
    failure_reason: str | None = None
```

```python
@dataclass
class RuntimeApplyResult:
    applied_steps: int = 0
    blocked_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    blocked_reasons: dict[str, int] = field(default_factory=dict)
    failed_reasons: dict[str, int] = field(default_factory=dict)
    skipped_reasons: dict[str, int] = field(default_factory=dict)
```

Required statuses:

| Status | Meaning |
|---|---|
| `pending` | Request was created and may still be answered. |
| `approved` | A resident approved and Heima processed the stored plan. |
| `dismissed` | A resident rejected this occurrence. |
| `timeout_skipped` | The request reached `expires_at` and `on_timeout: skip` skipped the steps. |
| `timeout_applied` | The request reached `expires_at` and `on_timeout: apply` processed the stored plan. |
| `cancelled` | Heima or an admin invalidated the pending request before resident approval, dismissal, or timeout resolution completed. |
| `failed` | Heima could not create or deliver the request, or could not apply approved/timeout-applied steps. |

Status and apply result rule:

- `status` describes how the request was resolved
- `apply_result` describes what happened to the stored steps
- partial application uses the same terminal status as the trigger that caused apply
- if zero steps were applied because every step was blocked or failed, status must be `failed`
  with `failure_reason: all_steps_blocked` or `failure_reason: apply_error`
- no separate `outcome` field is stored; consumers must derive outcome from `status`,
  `apply_result`, and `failure_reason`

Example partial result:

```yaml
status: approved
apply_result:
  applied_steps: 1
  blocked_steps: 1
  failed_steps: 0
  blocked_reasons:
    manual_hold_active: 1
```

Required `failure_reason` values:

| Value | Meaning |
|---|---|
| `no_actionable_route` | No concrete notify service supports actionable delivery. |
| `manual_hold_active` | Manual hold blocked all applicable steps. |
| `target_unavailable` | Required entity or service was unavailable. |
| `context_revalidation_failed` | Descriptor context validation rejected the stored plan. |
| `all_steps_blocked` | Apply filters blocked every stored step. |
| `apply_error` | Executor failed while applying stored steps. |
| `validation_failed` | Generic pre-apply validation failed. |

Status vocabulary rule:

- use `approved` for runtime request approval
- use `dismissed` when a resident explicitly answers no/skip
- use `cancelled` only when the pending request is invalidated before it is resolved by resident
  answer or timeout
- do not reuse proposal status wording such as `accepted` for runtime request outcomes
- use `accepted` only for learning/admin proposal lifecycle records

`cancelled` examples:

- the source reaction is disabled or deleted before anyone answers
- the source reaction configuration changes before anyone answers
- the source reaction is disabled, deleted, or changed before the timeout handler processes it
- the integration unloads/reloads and invalidates pending requests
- an admin explicitly clears pending runtime requests

Status transition rule:

- status transitions must be idempotent
- only the first valid resident response for a pending request may decide the outcome
- later responses for the same `request_id` must be ignored and counted as stale responses

Normative security rule:

- Notifications must only carry a `request_id` and action code.
- The executable `ApplyStep` list must be stored by Heima in the runtime request, not trusted from
  the notification response.
- The stored `ApplyStep` list is the concrete plan residents are approving, dismissing, or allowing
  to time out.

### Resident Action

Resident responses for a runtime action request:

| Action | Effect |
|---|---|
| `approve` | Apply the stored steps if the request is still valid. |
| `dismiss` | Do not apply the stored steps for this occurrence. |

An ignored notification is not equivalent to `dismiss`. It is resolved by the configured
`on_timeout` behavior.

## Runtime Flow

### Direct Apply Flow

For `execution_policy.mode == auto_apply`:

1. The reaction evaluates.
2. It returns `ApplyStep` instances.
3. Existing runtime filters run.
4. Surviving steps are applied as they are today.

### Ask Residents Flow

For `execution_policy.mode == ask_residents`:

1. The reaction evaluates.
2. It returns `ApplyStep` instances.
3. Safety and structural validation run.
4. Heima creates or reuses the pending request for the current occurrence.
5. The steps are not applied.
6. Heima sends an actionable notification to configured resident targets.
7. If a resident approves before expiration, Heima runs pre-apply validation on the stored plan and
   applies if valid.
8. If a resident dismisses, Heima records the dismissal and applies nothing.
9. If nobody answers before expiration, Heima applies `on_timeout`:
   - `skip`: mark `timeout_skipped` and apply nothing.
   - `apply`: run pre-apply validation on the stored steps, then mark `timeout_applied` or
     `failed`.

### Runtime Layer Ownership

Reaction classes should not implement notification delivery directly.

Preferred ownership:

- reactions produce `ApplyStep` plans
- a central runtime confirmation layer diverts eligible plans into requests
- the notification pipeline handles delivery
- the action response handler applies stored steps after pre-apply validation

This keeps resident confirmation reusable across lighting, camera privacy, climate, and future
domains.

### Event Gating and Rate Limits

Runtime action requests are not ordinary informational events.

Rules:

- creating an actionable request must not be suppressed by event category gating
- creating an actionable request must not be suppressed by generic event dedup/rate-limit controls
- occurrence-level deduplication defined by this spec is the controlling anti-spam mechanism
- Heima may still emit separate informational events about request creation, delivery failure, or
  outcome; those informational events may use the normal event pipeline

Rationale:

- if an admin configured a reaction to ask residents, suppressing the actionable request would make
  the reaction silently do nothing
- the request itself already has explicit occurrence identity, expiration, and dedup semantics

## Occurrence Identity and Deduplication

Heima must not create repeated notifications for the same reaction occurrence.

Each request must have an `occurrence_key`.

The concrete occurrence key is produced by the reaction family's
`RuntimeConfirmationDescriptor.occurrence_key` hook.

Normative rule:

- At most one pending request may exist for the same `(reaction_id, occurrence_key)`.
- If the same reaction evaluates again while the request is pending, Heima must not resend the same
  notification unless a domain policy explicitly allows reminder notifications.

Reminder notifications are out of scope for the first implementation slice.

## Pre-Apply Validation

Creating a runtime request proves that the reaction was valid when the request was created. It does
not prove that the stored plan is still safe to apply later.

Before applying stored steps because of resident approval or `on_timeout: apply`, Heima must run
pre-apply validation:

1. the request exists
2. status is `pending`
3. current time is before `expires_at`
4. the source reaction still exists and is enabled
5. the stored `reaction_id` and `reaction_type` still match the source configuration
6. manual hold and apply filters are evaluated for each stored step
7. step dependencies are evaluated after per-step blocking is known
8. required entities/services still exist
9. domain-specific validators, if any, still allow the stored plan
10. if `require_context_revalidation` is true, the descriptor's `validate_context` still allows the
    stored plan

Pre-apply validation must not recompute the action plan by re-running the reaction. It validates the
stored `ApplyStep` list created with the notification.

If validation fails:

- Heima must not apply the steps.
- The request must be marked `failed`, `timeout_skipped`, or `cancelled`, depending on cause.
- `failure_reason` must be populated for `failed` requests.
- Diagnostics must explain the failure reason.
- Heima should notify the original confirmation targets that the requested action was not applied
  because conditions changed.

Cancellation and failure rules:

- If the source reaction was disabled, deleted, or structurally changed before the request was
  resolved, mark the request `cancelled`.
- If a resident approved the request, or `on_timeout: apply` fired, and the stored plan could not be
  applied after validation, mark the request `failed`.
- If `on_timeout: skip` fired, mark the request `timeout_skipped` and apply nothing.

## Manual Hold Interaction

Manual hold remains authoritative.

Rules:

- Creating a runtime action request must not register a pending apply.
- Pending apply registration happens only immediately before executing approved steps.
- If a resident approves but manual hold now blocks the affected scope, Heima must not apply the
  blocked steps.
- Partial application follows the same apply filtering semantics used by ordinary runtime steps.
  Blocked steps are skipped; surviving steps may still be applied.
- A blocked step must not fail the whole runtime request by default.
- If a stored step declares dependencies on other stored steps, Heima must skip that step when any
  required dependency was blocked, skipped, or failed.
- Step dependencies must be explicit metadata on the stored `ApplyStep` plan. Runtime confirmation
  must not infer dependencies from list order.
- Dependency skipping counts as `skipped_steps`, not `blocked_steps`, and diagnostics must identify
  the missing dependency.
- If a domain requires a sequence where later actions are meaningless without earlier actions, that
  domain must either declare dependencies or opt in to atomic all-or-nothing behavior.
- Domains that require atomic all-or-nothing behavior must opt in explicitly through their
  descriptor or domain-specific contract.
- Runtime confirmation diagnostics must report applied, blocked, skipped, and failed step counts.
- Resident-facing "not applied" notifications are sent only when zero steps were applied. Partial
  application is reported in diagnostics in the first slice.

## Notification Contract

The existing notification recipient model remains canonical:

- recipients
- recipient groups
- route targets

Resident runtime confirmation extends notification payload capability, but does not introduce a
parallel routing model.

### Action Capability Configuration

Actionable delivery is an explicit notification-service capability.

Configuration shape:

```yaml
notifications:
  notification_service_capabilities:
    mobile_app_phone_stefano:
      supports_actions: true
```

Rules:

- capability is declared per concrete `notify.*` service name, without the `notify.` prefix
- services without `supports_actions: true` must not be used for actionable requests
- if a recipient resolves to both actionable and non-actionable services, Heima sends the actionable
  request only to the actionable services
- if no actionable service remains after filtering, the request must fail closed with
  `failure_reason: no_actionable_route`
- ordinary informational notifications may still use non-actionable services

### Target Resolution

Runtime confirmation target resolution uses the same logical model as ordinary Heima notifications:

```text
target_recipients + target_groups or default route_targets
-> recipients / recipient_groups
-> concrete notify.* services
```

Rules:

- explicit `target_recipients` and `target_groups` are reaction-level overrides
- absent explicit targets fall back to global `route_targets`
- unresolved targets are ignored and counted
- if no concrete actionable notify service remains, the request must fail closed

Promotion admin notifications use promotion-specific targets configured in the promotion policy. If
no promotion-specific target is configured, Heima may fall back to global `route_targets`, but the
notification remains informational and the approval still requires an HA-admin-gated review surface.

### Actionable Payload

The notification rendering layer must support provider-specific actionable payloads. The internal
contract is provider-neutral:

```python
@dataclass
class ActionableNotification:
    title: str
    message: str
    actions: list[NotificationAction]
    request_id: str
    category: str
```

```python
@dataclass
class NotificationAction:
    action_id: str
    label: str
```

Required runtime action labels:

| Action id | English label |
|---|---|
| `heima.runtime_request.approve` | `Yes` |
| `heima.runtime_request.dismiss` | `No` |

Labels may be localized by UI/notification rendering, but persisted action ids must be stable and
English.

### Response Handling

The response handler must accept only known action ids and known pending `request_id` values.

Unknown or stale responses must be ignored and counted in diagnostics.

Concurrent response rule:

- responses are first-writer-wins
- after one valid `approve` or `dismiss`, the request is no longer pending
- subsequent responses from other residents must not re-apply steps or change the recorded outcome

## User-Facing Text Generation

Requests should summarize the effect using the stored steps.

Example generated text:

```text
Apply the evening lighting scene in Studio?
Turn off Desk Lamp and set Floor Lamp to 10% brightness.
```

Text generation rules:

- use friendly names where available
- include enough detail to make the decision understandable
- avoid exposing raw JSON or HA service names to residents
- keep the message concise
- never allow message text to define executable actions
- render different wording for `on_timeout: skip` and `on_timeout: apply`

For lighting steps, the renderer should be able to describe:

- turning a light off
- turning a light on
- brightness percentage or low/medium/high approximation
- color temperature or color only when meaningful

### Timeout-Specific Wording

For `on_timeout: skip`, the notification is an ask-to-apply prompt:

```text
Apply the evening lighting scene in Studio?
Turn off Desk Lamp and set Floor Lamp to low brightness.
```

Recommended actions:

- `Apply`
- `Skip`

For `on_timeout: apply`, the notification is a notify-with-veto prompt:

```text
Heima will apply the evening lighting scene in Studio in 10 minutes.
Turn off Desk Lamp and set Floor Lamp to low brightness.
```

Recommended actions:

- `Apply now`
- `Skip`

Normative rule:

- Wording must make the timeout behavior clear to residents.
- `on_timeout: apply` must not use wording that implies silence means skip.
- `on_timeout: skip` must not use wording that implies silence means apply.

### Not Applied Wording

If resident approval or `on_timeout: apply` cannot apply the stored plan because pre-apply
validation fails, Heima should send a non-actionable informational notification to the same
confirmation targets.

Recommended wording:

```text
Heima did not apply the requested action.
Conditions changed before it could be applied.
```

For domain renderers that can safely provide detail, the second line may be more specific:

```text
Heima did not apply the Studio lighting scene.
A manual hold or newer state change now blocks it.
```

Rules:

- the notification must be informational only
- it must not include approve/dismiss actions
- it must not expose raw exception text or internal Python errors
- diagnostics must contain the precise technical reason
- not-applied informational notifications must be rate-limited per `reaction_id + failure_reason`
- resident-facing text should group causes into understandable categories, such as:
  - conditions changed
  - manual control is active
  - target device is unavailable
  - automation was disabled

## Confirmation Outcome Tracking

Heima tracks confirmation outcomes per reaction.

Conceptual model:

```yaml
confirmation_stats:
  requested: 12
  approved: 10
  dismissed: 1
  timeout_skipped: 1
  timeout_applied: 0
  failed: 0
  first_requested_at: "2026-07-01T20:00:00+02:00"
  last_requested_at: "2026-07-11T20:00:00+02:00"
  last_approved_at: "2026-07-11T20:01:00+02:00"
  last_dismissed_at: null
```

Outcome semantics:

- `requested`: request was successfully created and actionable delivery was attempted
- `approved`: a resident approved before expiration and Heima processed the stored plan
- `dismissed`: a resident explicitly rejected the occurrence
- `timeout_skipped`: no applicable answer was received before expiration and `on_timeout: skip`
  skipped the plan
- `timeout_applied`: no applicable answer was received before expiration and Heima processed the
  stored plan because `on_timeout: apply`
- `failed`: delivery, validation, or apply failed

For promotion thresholds:

- `approved` counts as explicit positive evidence.
- `dismissed` counts as explicit negative evidence.
- `timeout_applied` never participates in promotion evidence.
- `timeout_skipped` never participates in promotion evidence.
- timeout outcomes are excluded from promotion even when `on_timeout: apply` successfully applied
  the stored plan.

## Promotion From Confirmation to Auto Apply

If residents often approve a specific reaction, Heima may ask whether that reaction should become
automatic.

This is called a promotion review.

Promotion changes stable reaction behavior and is therefore an admin decision. It must not be
approved directly from a resident actionable notification in the first implementation slice.

Conceptual model:

```python
@dataclass
class PromotionReviewState:
    reaction_id: str
    status: str
    first_prompted_at: datetime | None = None
    last_prompted_at: datetime | None = None
    notification_count: int = 0
    target_mode: str = "auto_apply"
    failure_reason: str | None = None
```

Promotion review statuses:

| Status | Meaning |
|---|---|
| `none` | No active promotion review exists for this reaction. |
| `pending_admin_review` | Reaction is eligible and an admin should review it. |
| `approved` | HA admin approved switching the reaction to `auto_apply`. |
| `dismissed_not_now` | HA admin declined promotion temporarily. |
| `disabled_future_prompts` | HA admin disabled future promotion prompts for this reaction. |
| `revoked` | Heima revoked eligibility because new evidence no longer supports promotion. |
| `failed` | Promotion review notification or persistence failed. |

Rules:

- Promotion review state does not contain `ApplyStep` plans.
- Promotion approval may only modify execution policy for the source reaction.
- Promotion approval must happen through an HA-admin-gated Heima surface, such as options flow or a
  future admin panel.
- Promotion notifications are informational prompts to admins; they must not directly approve the
  promotion.
- Pending promotion review state is persisted as part of confirmation/promotion state.
- A pending promotion review must not block runtime `ask_residents` requests.

### Promotion Admin Notification

When a reaction becomes eligible for promotion, Heima should notify configured admin notification
targets that review is available.

Recommended wording:

```text
Heima can make this reaction automatic.
Open Heima settings to review the promotion.
```

Rules:

- the notification is informational only
- it must not include an approve-auto-apply action
- the admin decision must be made in an HA-admin-gated Heima UI
- sending this notification to a non-admin route target grants no approval authority
- if the admin does not open Heima, the reaction remains in `ask_residents`
- resident runtime confirmations continue while promotion is pending
- repeated admin reminder notifications must be rate-limited per reaction according to the
  configured promotion reminder interval

Admin notification targets are configured through logical notification recipients/groups. In the
first implementation, this is routing configuration, not a separate identity or permission model.
Authorization is enforced at the review surface by Home Assistant admin access.

Promotion changes only execution behavior:

```yaml
execution_policy:
  mode: ask_residents
```

to:

```yaml
execution_policy:
  mode: auto_apply
  promoted_from_confirmation: true
  promoted_at: "2026-07-12T12:00:00+02:00"
```

It must not change:

- reaction type
- action steps
- learned context
- safety constraints
- manual hold behavior

Promotion persistence rule:

- the promoted mode must be persisted in an admin-visible configuration surface
- if direct reaction mutation is not safe for a reaction family, Heima may persist a reaction-scoped
  execution override instead
- diagnostics and UI must show whether `auto_apply` came from explicit admin configuration or from
  resident confirmation promotion

### Promotion Policy

Promotion is optional per reaction.

```yaml
execution_policy:
  mode: ask_residents
  promotion:
    enabled: true
    target_recipients: []
    target_groups:
      - admins
    min_samples: 5
    min_approval_rate: 0.8
    min_distinct_days: 3
    min_new_approvals_after_dismissal: 3
    reminder_interval_days: 7
    cooldown_schedule_days:
      - 14
      - 30
      - 60
      - 90
      - 180
```

Default values:

| Field | Default | Meaning |
|---|---:|---|
| `enabled` | `true` | Whether promotion may be proposed. |
| `target_recipients` | `[]` | Logical recipients for informational admin review prompts. |
| `target_groups` | `[]` | Logical groups for informational admin review prompts. |
| `min_samples` | `5` | Minimum explicit resident answers before promotion may be proposed. |
| `min_approval_rate` | `0.8` | Minimum approval ratio among explicit answers. |
| `min_distinct_days` | `3` | Minimum distinct local days with approved requests. |
| `min_new_approvals_after_dismissal` | `3` | New approvals required after "not now" before another prompt. |
| `reminder_interval_days` | `7` | Minimum days between informational admin reminders while a promotion review remains pending. |
| `cooldown_schedule_days` | `[14, 30, 60, 90, 180]` | Progressive cooldown after repeated "not now" answers. |

Promotion sample calculation:

```text
promotion_samples = approved + dismissed
```

Approval rate calculation:

```text
approval_rate = approved / (approved + dismissed)
```

`timeout_skipped`, `timeout_applied`, and `failed` are excluded from the denominator by default.

Promotion eligibility requires:

```text
promotion_samples >= min_samples
AND approval_rate >= min_approval_rate
AND approved_distinct_days >= min_distinct_days
AND promotion is not disabled
AND current time is after any active promotion cooldown
AND new evidence after the latest promotion dismissal satisfies the post-dismissal rule
```

Pending review revocation:

- Heima must re-evaluate promotion eligibility when new explicit resident answers are recorded and
  before displaying the promotion review in the admin UI.
- If a `pending_admin_review` no longer satisfies promotion thresholds, Heima must mark it
  `revoked`.
- A revoked promotion review must not be approvable.
- A new `pending_admin_review` may be created later only after fresh evidence satisfies the
  promotion eligibility rules again.

## Promotion Review Actions

Promotion review must expose exactly three admin-facing choices in the HA-admin-gated review
surface:

| Action id | English label | Effect |
|---|---|---|
| `heima.promotion.approve_auto_apply` | `Yes, make it automatic` | Switch this reaction to `auto_apply`. |
| `heima.promotion.dismiss_not_now` | `No, not now` | Keep asking residents and start/increase cooldown. |
| `heima.promotion.disable_future_prompts` | `Do not ask again` | Keep asking residents, but disable future promotion prompts for this reaction. |

### "No, Not Now" Cooldown

Each admin `dismiss_not_now` increments a per-reaction dismissal counter.

Cooldown duration is selected from `cooldown_schedule_days`:

```text
index = min(dismiss_count - 1, len(cooldown_schedule_days) - 1)
cooldown_days = cooldown_schedule_days[index]
```

With the default schedule:

| Dismiss count | Cooldown |
|---:|---:|
| 1 | 14 days |
| 2 | 30 days |
| 3 | 60 days |
| 4 | 90 days |
| 5+ | 180 days |

After cooldown expires, Heima must not immediately reprompt solely because old evidence is still
above threshold. It must observe new positive evidence after the latest dismissal.

Required rule:

```text
now >= last_promotion_dismissed_at + current_cooldown
AND approvals_since_last_promotion_dismissal >= min_new_approvals_after_dismissal
AND approval_rate_since_last_promotion_dismissal >= min_approval_rate
```

Promotion state must therefore retain enough data to separate:

- all-time confirmation statistics
- confirmation statistics after the latest promotion dismissal
- promotion dismissal count
- latest promotion dismissal timestamp

### "Do Not Ask Again"

If the HA admin chooses `disable_future_prompts`, Heima records:

```yaml
promotion:
  enabled: false
  disabled_reason: admin_declined_permanently
  disabled_at: "2026-07-12T12:00:00+02:00"
```

The reaction remains in `ask_residents` mode. Only future promotion prompts are disabled.

## Admin Control Surface

Admins must be able to inspect and change execution policy state.

Required admin capabilities:

- see whether a reaction is `auto_apply` or `ask_residents`
- see whether `auto_apply` was promoted from resident confirmation
- switch a reaction back from promoted `auto_apply` to `ask_residents`
- disable or re-enable promotion prompts for a reaction
- reset confirmation statistics for a reaction
- inspect unresolved notification targets for resident confirmation

Admin actions:

| Action | Effect |
|---|---|
| `reset_confirmation_stats` | Clears confirmation counters and timestamps for one reaction. |
| `reset_promotion_cooldown` | Clears promotion dismissal count and latest promotion dismissal timestamp. |
| `reenable_promotion_prompts` | Sets promotion enabled for a reaction previously disabled by resident/admin choice. |
| `revert_promoted_auto_apply` | Changes a promoted reaction back to `ask_residents` and clears promotion provenance. |

Admin changes must take precedence over learned promotion state.

If an admin manually sets a reaction to `ask_residents` after promotion, Heima should not immediately
ask again for promotion using old evidence. It must require new evidence after the admin change.

## Authority and Permissions

The first implementation uses different authority models for runtime execution and promotion review.

Runtime action requests use a household-level model: any recipient who receives the actionable
runtime notification may answer it.

Promotion review uses Home Assistant admin authority: the notification is informational, and the
decision must be made in an HA-admin-gated Heima surface.

Future implementations may add per-recipient authorization, but the following rules are required
from the first slice:

- approving a runtime request may only apply stored steps for that request
- approving a promotion in the admin UI may only change `execution_policy.mode` for that reaction
- dismissing or disabling promotion in the admin UI may only affect that reaction
- no notification response may create a new reaction or modify unrelated configuration

## Persistence

First implementation recommendation:

- runtime action requests are in-memory only
- in-memory runtime action requests store the concrete `ApplyStep` plan generated at request
  creation time
- confirmation statistics and promotion state must be persisted

Rationale:

- action requests are short lived and context sensitive
- after a Home Assistant restart, applying an old notification response may be unsafe
- promotion depends on long-term behavior and must survive restarts

Restart behavior:

- pending runtime requests are cancelled or forgotten
- stale notification responses for missing requests are ignored
- confirmation stats remain available
- if Home Assistant restarts before timeout, `on_timeout` is not executed for the forgotten request
- if the reaction is still eligible in the same runtime window after restart, it may create a new
  request with a new `request_id`
- `on_timeout: apply` is best-effort and only executes while Home Assistant and Heima remain online
  through the timeout

If a restart happens while a promotion review is pending, the persisted
`pending_admin_review` state remains. Previously delivered informational notifications may be stale,
but the admin review remains available in the HA-admin-gated Heima surface.

If a later implementation persists runtime action requests for restart-safe actionable
notifications:

- it must use a runtime-confirmation store, not the learning proposal backlog
- persisted requests must keep short TTL semantics
- persisted requests must continue to represent one occurrence only
- approval or timeout apply must apply the stored concrete plan only after pre-apply validation
- approval must not create, accept, or edit any `ReactionProposal`
- cleanup must remove timed-out/completed runtime requests independently from proposal lifecycle

## Diagnostics

Diagnostics should expose:

- pending runtime action requests
- recent completed requests
- request counts by status
- applied, blocked, skipped, and failed step counts for completed requests
- notification delivery failures
- stale or unknown response counts
- confirmation stats per reaction
- promotion eligibility state per reaction
- active promotion cooldowns
- promotion disabled reactions
- whether an actionable request failed because only non-actionable notify routes were available
- first-writer-wins stale response counts
- `failure_reason` counts

Example:

```json
{
  "runtime_confirmation": {
    "pending_requests": 1,
    "recent_outcomes": {
      "approved": 10,
      "dismissed": 1,
      "timeout_skipped": 1,
      "timeout_applied": 0,
      "failed": 0
    },
    "promotion": {
      "eligible_reactions": 1,
      "cooldowns": 2,
      "disabled": 1
    }
  }
}
```

## Initial Domain: Learned Lighting Scenes

The first domain should be learned context-conditioned lighting scenes.

Why:

- lighting learning already produces concrete per-entity steps
- steps can include off/on and brightness changes
- the action is understandable to residents
- manual hold integration already exists for lighting

Example reaction configuration:

```yaml
reaction_type: context_conditioned_lighting_scene
execution_policy:
  mode: ask_residents
  confirmation:
    target_groups:
      - residents
    expires_in_minutes: 10
    on_timeout: skip
  promotion:
    enabled: true
entity_steps:
  - entity_id: light.desk_lamp
    action: off
  - entity_id: light.floor_lamp
    action: on
    brightness: 20
```

Example runtime notification:

```text
Apply the evening lighting scene in Studio?
Turn off Desk Lamp and set Floor Lamp to low brightness.
```

Example promotion notification:

```text
You usually approve this lighting scene.
Should Heima apply it automatically from now on?
```

Actions:

- `Yes, make it automatic`
- `No, not now`
- `Do not ask again`

## Testing Requirements

Unit tests:

- execution policy defaults to `auto_apply`
- unsupported reaction families reject `ask_residents`
- supported reaction families must provide a runtime-confirmation descriptor
- runtime action requests are not inserted into the proposal backlog
- `ask_residents` diverts steps into a pending request
- duplicate occurrence does not create duplicate pending requests
- approval applies stored steps, not notification-supplied steps
- timed-out request cannot be approved
- `on_timeout: skip` skips stored steps at timeout
- `on_timeout: apply` validates and applies stored steps at timeout
- first valid response wins when multiple residents answer
- manual hold blocks affected approved steps without failing unrelated surviving steps
- step dependencies skip dependent steps when a prerequisite was blocked, skipped, or failed
- confirmation stats update for approved/dismissed/timeout_skipped/timeout_applied/failed
- failed requests populate `failure_reason`
- partial apply records `apply_result`
- timeout outcomes never participate in promotion evidence
- promotion eligibility thresholds are respected
- "not now" increments cooldown
- promotion requires new evidence after "not now"
- "do not ask again" disables future promotion prompts only
- admin reset requires new evidence before promotion is proposed again

Integration tests:

- notification target resolution uses recipients/groups
- actionable requests filter services by `notification_service_capabilities.*.supports_actions`
- explicit reaction targets override global route targets
- missing actionable routes fail closed instead of auto-applying
- runtime approval does not create or update configured reactions
- unknown `request_id` responses are ignored and counted
- reaction disabled before approval cancels or invalidates the request
- reaction disabled before timeout apply marks the request `cancelled`
- admin-approved promotion persists `execution_policy.mode: auto_apply`

Live tests:

- learned lighting scene in `ask_residents` sends an actionable notification instead of applying
- approving the action applies the expected light states
- dismissing the action leaves light states unchanged
- `on_timeout: skip` leaves light states unchanged after timeout
- `on_timeout: apply` applies expected light states after timeout
- repeated approvals trigger an admin promotion review after thresholds are met
- admin-approved promotion makes subsequent occurrences auto-apply without notification

## Compatibility

Backward compatibility rules:

- existing reactions without `execution_policy` keep direct apply behavior
- notification recipients and groups remain canonical
- non-actionable notify services must not be treated as successful delivery targets for actionable
  requests
- Heima may emit a separate informational event to non-actionable routes, but that event must not
  make the request actionable and must not prevent fail-closed behavior
- this feature must not change proposal statuses or proposal lifecycle semantics

## Open Questions

Open decisions before implementation:

1. Exact Home Assistant actionable notification payload shapes per supported notify provider.
2. Whether persisted request storage is needed after the first implementation slice.
