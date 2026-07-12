# Resident Runtime Confirmation Spec

**Status:** Draft vNext  
**Date:** 2026-07-12  
**Related specs:** `core/events_and_notifications_spec.md`,
`core/notification_recipients_spec.md`, `core/apply_step_contract.md`,
`core/manual_hold_framework_spec.md`, `learning/context_conditioned_lighting_learning_spec.md`

## Purpose

Resident runtime confirmation lets Heima ask residents before applying a specific runtime action
that has already been approved or configured by an admin.

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
- the first supported family is learned context-conditioned lighting scenes

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
| `require_context_revalidation` | bool | `true` | Whether the original reaction gates must still pass before approved steps run. |

Target precedence:

1. If `target_recipients` or `target_groups` is non-empty, use those explicit targets.
2. Otherwise, if `use_default_route_targets` is true, use the global notification `route_targets`.
3. Otherwise, the request has no target and must fail closed.

At least one effective notification target must resolve through the canonical notification recipient
model. If none resolves, Heima must not silently auto-apply. It should record a delivery failure and
leave the request unapproved until it expires.

### RuntimeActionRequest

A runtime action request is the bounded, concrete object residents can approve or dismiss.

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
    status: str
    confirmation_targets: list[str]
    context_snapshot: dict[str, Any]
    outcome: RuntimeActionOutcome | None = None
```

Required statuses:

| Status | Meaning |
|---|---|
| `pending` | Request was created and may still be answered. |
| `approved` | A resident approved and Heima attempted to apply the steps. |
| `dismissed` | A resident rejected this occurrence. |
| `expired` | The request reached `expires_at` without an applicable decision. |
| `cancelled` | Heima invalidated the request because the reaction/configuration changed. |
| `failed` | Heima could not create or deliver the request, or could not apply approved steps. |

Status transition rule:

- status transitions must be idempotent
- only the first valid resident response for a pending request may decide the outcome
- later responses for the same `request_id` must be ignored and counted as stale responses

Normative security rule:

- Notifications must only carry a `request_id` and action code.
- The executable `ApplyStep` list must be stored by Heima, not trusted from the notification
  response.

### Resident Action

Resident responses for a runtime action request:

| Action | Effect |
|---|---|
| `approve` | Apply the stored steps if the request is still valid. |
| `dismiss` | Do not apply the stored steps for this occurrence. |

An ignored notification is not equivalent to `dismiss`. It becomes `expired`.

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
7. If a resident approves before expiration, Heima revalidates and applies.
8. If a resident dismisses, Heima records the dismissal and applies nothing.
9. If nobody answers before expiration, Heima records expiration and applies nothing.

### Runtime Layer Ownership

Reaction classes should not implement notification delivery directly.

Preferred ownership:

- reactions produce `ApplyStep` plans
- a central runtime confirmation layer diverts eligible plans into requests
- the notification pipeline handles delivery
- the action response handler applies stored steps after validation

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

Examples:

| Reaction kind | Occurrence key inputs |
|---|---|
| Scheduled lighting scene | `reaction_id`, local date, scheduled window |
| Context-conditioned lighting scene | `reaction_id`, context activation window, local date |
| Alarm state action | `reaction_id`, alarm transition id or state change timestamp bucket |

Normative rule:

- At most one pending request may exist for the same `(reaction_id, occurrence_key)`.
- If the same reaction evaluates again while the request is pending, Heima must not resend the same
  notification unless a domain policy explicitly allows reminder notifications.

Reminder notifications are out of scope for the first implementation slice.

## Validation Before Approval Apply

Approving a notification is not sufficient by itself. Before applying steps, Heima must validate:

1. the request exists
2. status is `pending`
3. current time is before `expires_at`
4. the source reaction still exists and is enabled
5. the stored `reaction_id` and `reaction_type` still match the source configuration
6. manual hold does not block the steps
7. apply filters still allow the steps
8. if `require_context_revalidation` is true, the reaction gates still pass

If validation fails:

- Heima must not apply the steps.
- The request should be marked `failed`, `expired`, or `cancelled`, depending on cause.
- Diagnostics must explain the failure reason.

## Manual Hold Interaction

Manual hold remains authoritative.

Rules:

- Creating a runtime action request must not register a pending apply.
- Pending apply registration happens only immediately before executing approved steps.
- If a resident approves but manual hold now blocks the affected scope, Heima must not apply the
  blocked steps.
- Partial application should follow the same apply filtering semantics used by ordinary runtime
  steps. If the existing executor applies surviving steps independently, resident-approved steps may
  do the same. If a domain requires atomic execution, that domain must document it separately.

## Notification Contract

The existing notification recipient model remains canonical:

- recipients
- recipient groups
- route targets

Resident runtime confirmation extends notification payload capability, but does not introduce a
parallel routing model.

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

Promotion requests use the same targets as runtime confirmation by default. A future version may add
separate `promotion.target_recipients` and `promotion.target_groups`, but the first slice should keep
one target model per reaction.

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

For lighting steps, the renderer should be able to describe:

- turning a light off
- turning a light on
- brightness percentage or low/medium/high approximation
- color temperature or color only when meaningful

## Confirmation Outcome Tracking

Heima tracks confirmation outcomes per reaction.

Conceptual model:

```yaml
confirmation_stats:
  shown: 12
  approved: 10
  dismissed: 1
  expired: 1
  failed: 0
  first_shown_at: "2026-07-01T20:00:00+02:00"
  last_shown_at: "2026-07-11T20:00:00+02:00"
  last_approved_at: "2026-07-11T20:01:00+02:00"
  last_dismissed_at: null
```

Outcome semantics:

- `shown`: request was successfully created and notification delivery was attempted
- `approved`: a resident approved before expiration and validation reached the apply attempt
- `dismissed`: a resident explicitly rejected the occurrence
- `expired`: no applicable answer was received before expiration
- `failed`: delivery, validation, or apply failed

For promotion thresholds, `expired` must not be treated as an explicit rejection by default.

## Promotion From Confirmation to Auto Apply

If residents often approve a specific reaction, Heima may ask whether that reaction should become
automatic.

This is called a promotion request.

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
    min_samples: 5
    min_approval_rate: 0.8
    min_distinct_days: 3
    min_new_approvals_after_dismissal: 3
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
| `min_samples` | `5` | Minimum explicit resident answers before promotion may be proposed. |
| `min_approval_rate` | `0.8` | Minimum approval ratio among explicit answers. |
| `min_distinct_days` | `3` | Minimum distinct local days with approved requests. |
| `min_new_approvals_after_dismissal` | `3` | New approvals required after "not now" before another prompt. |
| `cooldown_schedule_days` | `[14, 30, 60, 90, 180]` | Progressive cooldown after repeated "not now" answers. |

Promotion sample calculation:

```text
answered_samples = approved + dismissed
```

Approval rate calculation:

```text
approval_rate = approved / (approved + dismissed)
```

`expired` and `failed` are excluded from the denominator by default.

Promotion eligibility requires:

```text
answered_samples >= min_samples
AND approval_rate >= min_approval_rate
AND approved_distinct_days >= min_distinct_days
AND promotion is not disabled
AND current time is after any active promotion cooldown
AND new evidence after the latest promotion dismissal satisfies the post-dismissal rule
```

## Promotion Request Actions

Promotion requests must have exactly three resident-facing choices:

| Action id | English label | Effect |
|---|---|---|
| `heima.promotion.approve_auto_apply` | `Yes, make it automatic` | Switch this reaction to `auto_apply`. |
| `heima.promotion.dismiss_not_now` | `No, not now` | Keep asking residents and start/increase cooldown. |
| `heima.promotion.disable_future_prompts` | `Do not ask again` | Keep asking residents, but disable future promotion prompts for this reaction. |

### "No, Not Now" Cooldown

Each `dismiss_not_now` increments a per-reaction dismissal counter.

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

If the resident chooses `disable_future_prompts`, Heima records:

```yaml
promotion:
  enabled: false
  disabled_reason: resident_declined_permanently
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

Admin changes must take precedence over learned promotion state.

If an admin manually sets a reaction to `ask_residents` after promotion, Heima should not immediately
ask again for promotion using old evidence. It must require new evidence after the admin change.

## Authority and Permissions

The first implementation may use a simple household-level model: any recipient who receives the
actionable notification may answer it.

Future implementations may add per-recipient authorization, but the following rules are required
from the first slice:

- approving a runtime request may only apply stored steps for that request
- approving a promotion may only change `execution_policy.mode` for that reaction
- dismissing or disabling promotion may only affect that reaction
- no notification response may create a new reaction or modify unrelated configuration

## Persistence

First implementation recommendation:

- runtime action requests may be in-memory only
- confirmation statistics and promotion state must be persisted

Rationale:

- action requests are short lived and context sensitive
- after a Home Assistant restart, applying an old notification response may be unsafe
- promotion depends on long-term behavior and must survive restarts

Restart behavior:

- pending runtime requests are cancelled or forgotten
- stale notification responses for missing requests are ignored
- confirmation stats remain available

If a restart happens while a promotion request is pending, the promotion request should be treated
like other runtime requests in the first slice: it is no longer actionable after restart unless a
future implementation persists pending requests explicitly.

## Diagnostics

Diagnostics should expose:

- pending runtime action requests
- recent completed requests
- request counts by status
- notification delivery failures
- stale or unknown response counts
- confirmation stats per reaction
- promotion eligibility state per reaction
- active promotion cooldowns
- promotion disabled reactions
- whether an actionable request failed because only non-actionable notify routes were available
- first-writer-wins stale response counts

Example:

```json
{
  "runtime_confirmation": {
    "pending_requests": 1,
    "recent_outcomes": {
      "approved": 10,
      "dismissed": 1,
      "expired": 1,
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
- `ask_residents` diverts steps into a pending request
- duplicate occurrence does not create duplicate pending requests
- approval applies stored steps, not notification-supplied steps
- expired request cannot be approved
- first valid response wins when multiple residents answer
- manual hold blocks approved steps
- confirmation stats update for approved/dismissed/expired/failed
- promotion eligibility thresholds are respected
- "not now" increments cooldown
- promotion requires new evidence after "not now"
- "do not ask again" disables future promotion prompts only
- admin reset requires new evidence before promotion is proposed again

Integration tests:

- notification target resolution uses recipients/groups
- explicit reaction targets override global route targets
- missing actionable routes fail closed instead of auto-applying
- unknown `request_id` responses are ignored and counted
- reaction disabled before approval cancels or invalidates the request
- accepted promotion persists `execution_policy.mode: auto_apply`

Live tests:

- learned lighting scene in `ask_residents` sends an actionable notification instead of applying
- approving the action applies the expected light states
- dismissing the action leaves light states unchanged
- repeated approvals trigger a promotion prompt after thresholds are met
- approving promotion makes subsequent occurrences auto-apply without notification

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
2. Whether text-only informational companion events should be emitted when all actionable routes
   fail.
3. Whether admin-only approval should be configurable for promotion prompts.
4. Whether persisted request storage is needed after the first implementation slice.
