# Heima v3 - Layer 6: Notification and Communication

**Status:** DRAFT for developer review (2026-10-12). Not approved, not implemented, not yet an
authoritative layer in `contract_registry.json`.
**Open corrections:** the upstream changes of §13 and the open points of §14 must be decided
before approval.

**Layer:** 6 of 8. Builds on Layer 0's unified notification delivery outbox (§4.5), authenticated
response ingress (§5.1.3), Runtime Scheduler, composed configuration generation (§4.7) and
recovery confirmation (§7.4.1); Layer 1's operational event mapping (§3.1); Layer 3's
availability-suppression contract (§6.3.1); Layer 4's availability-owner declarations (§7); and
Layer 5's typed occurrences (§6.0). It implements the Layer-6 decisions C1–C6 recorded in
`docs/v3_backlog.md` ("Layer 6 specification decisions").

## 1. Purpose

Layer 6 is the only path by which Heima pushes a notification to a person; configuration, history
and diagnostics surfaces belong to Layer 8. It turns closed typed
occurrences from Layers 0, 3, 4 and 5 into audited operational event facts and delivers them to the
right people through Home Assistant, at the right time, in their language, with buttons when an
answer is possible.

V2 had two disconnected paths: a well-built but never configured event pipeline, and direct
`persistent_notification` calls for proposals. Layer 6 replaces both with one pipeline that also
works without configuration: nothing a person must see is ever dropped silently.

## 2. Scope and boundaries

Layer 6 owns:

- the closed `NotificationKindRegistry` and one core adapter per notification kind (§4);
- recipients, audiences and the Layer-6 configuration generation (§5, §10);
- families, quiet-hours behavior and digests (§6);
- delivery scheduling, rendering, channels, retries, fallback and response transport (§7, §8);
- the `AvailabilityEpisodeTracker` and the `AvailabilityPublicationGeneration` (§9.2);
- notification diagnostics (§12).

Layer 6 does not own:

- the outbox storage, the response ingress, response verification or any response decision
  (Layer 0, and the registered response owners);
- the meaning, timing or identity of any occurrence (its producing layer);
- proposal review, consent authority or any governance command (Layer 5, Layer 8);
- the administrative surface that edits recipients and shows history (Layer 8).

Layer 6 never issues an `ApplyStep`, changes a Reaction, interprets a response, reads Home
Assistant state for a decision, or writes a fact type it does not own.

## 3. Core principles

- **Typed inputs only.** Every notification starts from one closed typed occurrence. No layer
  passes text, an HA entity or a free payload to Layer 6.
- **One audit fact per notification phase, no stored text.** Each accepted phase appends exactly
  one Layer-1 operational event fact together with its outbox `ready` record (Layer 0 §4.5). The
  fact holds closed fields and identifiers only; text is rendered at delivery (Layer 1 §3.1).
- **Never silent by misconfiguration.** A notification whose audience has no reachable recipient
  falls back to `persistent_notification`. A notification is only ever not delivered by an
  explicit rule of this spec (closed item, expired item, family behavior), and every such case is
  counted in diagnostics.
- **Home Assistant infrastructure first.** Delivery uses `notify.*` services, mobile notification
  `tag`s, `clear_notification`, the `mobile_app_notification_action` event, `persistent_notification`
  and one `heima_notification` bus event. Heima adds no own push channel, scheduler UI or user store.
- **Delivery preference is not authority.** Being in an audience grants nothing. Every answer is
  verified by Layer 0's ingress and decided by its owner.
- **No hot-path work.** Adapters run when an occurrence arrives, never inside a Layer-2–5
  evaluation; delivery I/O is asynchronous and never blocks a cycle, an `ApplyStep` or a
  revocation.

## 4. Notification kinds

### 4.1 `NotificationKindRegistry`

The registry is closed, core-owned and frozen at bootstrap. Administrators, learners and plugins
cannot add a kind. Each entry fixes everything that is not configuration:

```python
NotificationFamily = Literal["safety", "attention", "suggestion", "governance"]
NotificationAudience = Literal["residents", "administrators", "consent_authorities"]

@dataclass(frozen=True)
class NotificationKindDescriptor:
    notification_kind: str                 # equals the event fact_type and the Layer-0 claim
    claim_owner_id: str                    # Layer 0 FactTypeClaim owner, e.g. "layer6.reaction_advisory"
    input_type: str                        # the closed typed occurrence the adapter accepts
    audience: NotificationAudience
    default_family: NotificationFamily     # §6.1; availability may resolve to "safety"
    severity: EventSeverity                # fixed per kind (Layer 1 §3.1)
    delivered_phases: frozenset[str]       # phases that reach people; other phases are audit only
    clearing_phases: frozenset[str]        # phases that clear an earlier delivered phase (§7.4)
    response_owner_id: str | None          # Layer 0 §5.1.3 owner when actionable
    context_versions: frozenset[int]       # registered OperationalEventValue.context_version values
```

### 4.2 Initial-V3 kinds

| Kind | Input | Audience | Family | Severity | Delivered phases | Answer |
|---|---|---|---|---|---|---|
| `reaction.follow_up` | `ReactionFollowUpOccurrence` (Layer 5 §6.0) | residents | attention | warning | the one outcome | none |
| `automation.availability` | `AvailabilitySuppressionOccurrence` via the tracker (§9.2) | residents | attention; safety for a `safety.*` binding | warning | `abstaining`, `reason_changed`, `restored` | none |
| `reaction.advisory` | `ReactionAdvisoryOccurrence` (Layer 5 §6.0) | residents | suggestion | info | `opened` (`closed` clears) | `layer5.advisory_feedback`: done / dismiss / not_useful |
| `reaction.action_notice` | `ReactionActionNoticeOccurrence` (Layer 5 §6.0) | residents | safety | info | the one notice | none |
| `recovery.confirmation_request` | `RecoveryConfirmationOccurrence` (Layer 0 §7.4.1) | residents | attention | warning | `opened` (`closed` clears) | `layer0.recovery_confirmation`: approve / dismiss |
| `reaction.consent_request` | `ConsentRequestOccurrence` (Layer 5 §6.0) | consent_authorities | governance | info | `opened` (`closed` clears) | `layer5.household_consent`: grant / decline |
| `proposal.review_pending` | `ProposalReviewOccurrence` (Layer 5 §6.0) | administrators | governance | info | `created`, `approvable_again`, grouped by the digest (§6.3) | none; link to the Layer-8 panel |

Every Initial-V3 kind uses `context_version=1`. A future context change registers a new version and
keeps the previous template while retained history can contain it (Layer 1 §3.1).

### 4.3 Adapter contract

Each kind has exactly one core adapter. On an occurrence it:

1. validates the occurrence against its closed contract (identities non-empty, phase and reason
   fields consistent, sizes bounded) and rejects it otherwise with a diagnostic;
2. builds the event fact: `fact_type=notification_kind`, `where=subject`, `when=occurred_at` (or
   the recovery instant for `interrupted_before_outcome`), `how.source=FactSource(kind="system",
   source_id=claim_owner_id)`, and an `OperationalEventValue` with the kind's severity, its
   `context_version`, its `notification_key` (§7.6) and the occurrence's closed fields mapped to
   scalar `context` entries;
3. commits the fact and the outbox `ready` record in one transaction under
   `(notification_kind, operation_id)` (for `reaction.follow_up`, the transition from its
   `prepared` intent, Layer 0 §4.5.1);
4. hands the record to the delivery scheduler (§7.1).

An exact retry of the same operation returns the existing record; a different payload under the
same key is rejected (Layer 0 §4.5). `context` never contains a display name, rendered text, raw HA
state, an HA entity id other than a registered Actuator id, or a person's identity.

## 5. Recipients and audiences

### 5.1 Recipient model (C1)

A recipient is one person.

```python
@dataclass(frozen=True)
class NotificationEndpoint:
    service: str                      # "notify.<name>", validated against HA's service registry at staging
    supports_actions: bool            # true only for an HA mobile-app notify service

@dataclass(frozen=True)
class NotificationRecipient:
    recipient_id: str                 # stable, administrator-chosen, e.g. "stefano"
    ha_user_id: str | None            # links the person to HA authentication
    locale: Literal["it", "en"] | None    # None: household locale (§8.2)
    endpoints: tuple[NotificationEndpoint, ...]
    audiences: frozenset[Literal["residents", "administrators"]]
```

V2 groups and free routes are not carried over. The administrator only assigns each person to
`residents` and/or `administrators`. Staging rejects duplicate `recipient_id`s, duplicate
`ha_user_id`s, a duplicate endpoint within one recipient, an unknown `notify.*` service and
`supports_actions=True` on a service that is not a mobile-app notify service.

### 5.2 Audience resolution

- `residents` and `administrators` are the recipients assigned to them.
- `consent_authorities` is derived, never configured: the recipients whose `ha_user_id` matches an
  actor of the current `HouseholdConsentAuthority` (Layer 5 §7.1.1). A consent-authorized person
  without a recipient record gets the fallback channel.
- Resolution happens at delivery time against the active Layer-6 generation, so a later change of
  recipients applies to notifications not yet delivered.

### 5.3 No silent drop

If an audience resolves to no recipient with at least one endpoint, the notification is delivered
through the fallback channel (§7.3). This is also the behavior of an unconfigured installation.

## 6. Families, quiet hours and digests

### 6.1 Families (C3)

Families are closed and fixed per kind (§4.2). The only kind whose family depends on its input is
`automation.availability`: it is `safety` when the binding it is delivered for belongs to a
`safety.*` descriptor (for example a window held open while weather protection is active), and
`attention` otherwise.

Priority maps to Home Assistant mobile push options: `safety` uses the time-sensitive
interruption level (iOS) and high priority (Android); the other families use the platform default.
Heima never uses the iOS critical-alert level.

### 6.2 Quiet hours

Quiet hours are the casa `quiet_hours.active` fact already used by the Layer-5 `quiet_hours.v1`
guard. Layer 6 reads its latest committed value; it has no own schedule. If the fact is not
configured there are no quiet hours.

| Family | During quiet hours | Administrator option |
|---|---|---|
| `safety` | delivered immediately | none: can never be silenced |
| `attention` | held; delivered when quiet hours end | may be set to silent |
| `suggestion` | held; one end-of-quiet-hours digest of the still-open advisories (§6.4) | none |
| `governance` | held; delivered when quiet hours end, proposals through their digest | may be set to silent |

"Silent" for a family means its notifications produced during quiet hours are retired undelivered
when quiet hours end; their audit facts remain. While `quiet_hours.active` is unavailable, Layer 6
treats quiet hours as not active, so nothing is held indefinitely.

### 6.3 Proposal digest (C4)

- Only `proposal.review_pending` is grouped. A proposal is open from its latest `created` or
  `approvable_again` phase until a later `closed` (Layer 5 §6.0).
- The first open, undelivered proposal starts a core-fixed 30-minute collection window (one
  elapsed `AtJob`). When it fires, one notification per administrator ("N proposals awaiting
  review, M new", link to the Layer-8 panel) counts every proposal still open and marks the
  undelivered ones as delivered. Because a digest replaces the previous one, it always counts
  every open proposal, not only the new ones.
- At most one proposal digest per recipient every 4 hours; proposals arriving after a digest wait
  for the next allowed one. A digest due during quiet hours is sent when they end.
- All digests use one fixed tag per audience, so a new digest replaces the previous one on the
  phone. When no proposal remains open, Layer 6 sends `clear_notification` on that tag.
- Each covered record transitions to `delivered`; a proposal closed before its digest retires
  undelivered (Layer 0 §4.5).

### 6.4 Advisory digest (C3)

During quiet hours, each `reaction.advisory` `opened` record is held. When quiet hours end, Layer 6
selects the held advisories whose activation is still open (no `closed` phase yet) and delivers them
per resident as one notification. A closed advisory retires undelivered. A digest that contains one
advisory is delivered as that advisory's ordinary actionable notification (§14, point 3, for several).

## 7. Delivery

### 7.1 Scheduler

The delivery scheduler is an in-memory coordinator rebuilt from the outbox at process start. For
each `ready` record it decides exactly one of: deliver now, hold (quiet hours or digest window),
group into a digest, or retire undelivered (§7.5). It uses the Layer-0 Runtime Scheduler for every
timer; it has no own timer.

### 7.2 Primary channel

For each resolved recipient, Layer 6 sends one call to each endpoint `notify.*` service with:

- the rendered title and message (§8);
- `data.tag`: the item tag (§7.4), so a retry or later phase replaces, never duplicates;
- `data.actions`: only for an actionable phase and only on an endpoint with `supports_actions`;
- `data.url` (or `clickAction`) for a proposal digest, pointing to the Layer-8 panel;
- the push priority of §6.1.

A recipient is reached when at least one of its endpoints accepted the call.

### 7.3 Retries and fallback

Failed endpoint calls are retried with a core-fixed growing schedule (§14, point 1). When every
endpoint of every resolved recipient has failed after the last retry, or when the audience has no
reachable recipient (partial reachability: §14, point 2), Layer 6 creates a `persistent_notification` with `notification_id` equal to the
item tag. An actionable phase delivered only through the fallback carries no buttons; it remains
answerable from the Layer-8 surface through the same ingress (C2). The record becomes `delivered`
once every resolved recipient was reached or the fallback accepted. A failed fallback keeps the
record `ready` and is retried with the same schedule; diagnostics expose it.

### 7.4 Item tags and clearing

The item tag identifies one notified item across its phases:

| Kind | Item tag source |
|---|---|
| `reaction.advisory` | `reaction_activation_id`, `member_index` |
| `recovery.confirmation_request` | `request_id` |
| `reaction.consent_request` | `reaction_id`, `configuration_generation_id`, `authority_transition_id` |
| `proposal.review_pending` | one fixed digest tag per audience |
| `automation.availability` | `automation_scope_id`, subject |
| other kinds | the record's `notification_key` |

The tag is `"heima:" + notification_kind + ":" + sha256(RFC-8785 tag source)[:32]`. A clearing
phase (§4.1) sends `clear_notification` on the item tag to every recipient that received the
opening phase and dismisses the fallback `persistent_notification`; it shows no new message.
Clearing is best effort and never changes the item's state. Because successive phases of one item
share its tag, the phone always shows only the item's latest phase: an automation that is blocked,
restored and blocked again within minutes leaves one notification showing its current state.

### 7.5 Retirement without delivery

A `ready` record retires undelivered only when:

- its item closed before delivery (advisory, proposal, recovery confirmation, consent request);
- its item expired (a recovery request past `expires_at`);
- its family is silent during quiet hours (§6.2);
- it is a pre-restart advisory without a closing phase (Layer 5 §6.0).

The audit fact always remains. Each retirement increments a diagnostic counter by kind and cause.

### 7.6 Notification keys and repeat suppression

Every kind uses `notification_key = notification_kind + ":" + operation_id`; for
`reaction.follow_up` this is exactly the key of Layer 5 §6.0. The availability adapter derives its
`operation_id` as SHA-256 of `"automation.availability.operation.v1:"` + RFC-8785
`[run_id, automation_scope_id, subject_key, reasons, transition, episode_sequence]`, where `run_id`
is the tracker's fresh per-process identity and `episode_sequence` counts the episodes of that key
in the run (Layer 3 §6.3.1). Retries within one run keep the key; a restart creates a new one.

There is no time-based deduplication window: a notification is never delayed or dropped because a
similar one was sent recently. Repeats are prevented by the outbox's per-operation uniqueness and,
on the phone, by the item tag (§7.4). The key is never a fact identity.

### 7.7 Responses

Layer 6 encodes each button as an HA mobile action identifier
`"HEIMA:" + response_request_id + ":" + action`. On a `mobile_app_notification_action` event with
that prefix it passes the request id, the action and the event's authenticated HA user context to
Layer 0's ingress (§5.1.3), and does nothing else. It never interprets, validates or answers a
response itself; an unknown prefix is ignored. The response request id comes from the occurrence
(§13, U1).

### 7.8 Home Assistant bus event

After each delivery (including the fallback and each digest) Layer 6 fires one
`heima_notification` event with closed fields only: `notification_kind`, `family`, `audience`,
`phase`, `operation_id` (or the digest's covered count) and `channel` (`notify` or
`persistent_notification`). It carries no text, recipient or person identity. Users may build their
own automations on it; Heima never consumes it.

## 8. Rendering and languages (C6)

### 8.1 Templates

Each `(notification_kind, context_version)` has one core-fixed template per supported locale,
selected further by the closed `context` fields (phase, intent, closing reason, outcome). Templates
are versioned with the core and not editable by administrators. A template uses only closed context
fields, the subject Location and names resolved from the current configuration (room, opening,
Actuator, Reaction). A name longer than 64 characters is truncated; an identifier that is no longer
configured is shown as the identifier. An unknown `context_version` renders a generic text with the
kind and identifiers.

Rendered output is bounded: title at most 120 and message at most 600 UTF-8 bytes in every locale,
checked by template tests. Templates must respect the content rules already fixed upstream, for
example the follow-up labels an observation with its time and never claims an interrupted command
completed (Layer 5 §6.0), and an unmanaged-after-restart notice never asserts that Heima switched
the device off (Layer 3 §6.3.1).

### 8.2 Locale

The household locale is HA's `hass.config.language`; a recipient may declare its own `locale`.
Initial V3 supports `it` and `en`; any other language falls back to `en`. A digest covering several
recipients is rendered per recipient. The fallback channel uses the household locale. Layer 8
renders event history with the same templates in the viewer's locale.

## 9. Kind-specific adapters

### 9.1 `reaction.follow_up`

The adapter implements Layer 0 §4.5.1 and Layer 5 §6.0 without change: it prepares the intent at
the boundary, validates the occurrence against it, commits the event and `ready` together,
finalizes an unfinished intent as `interrupted_before_outcome` after restart, and reconciles a
degraded preparation when storage returns.

### 9.2 `automation.availability`

```python
@dataclass(frozen=True)
class SuppressionKey:
    suppression_owner_id: str
    suppression_scope_id: str
    subject_key: str                  # canonical LocationKey text

@dataclass(frozen=True)
class AvailabilityPublicationBinding:
    automation_scope_id: str          # declared by Layer 5 for one configured Reaction
    reaction_descriptor_id: str       # selects the family (§6.1)
    enabled: bool
    resident_visible: bool

@dataclass(frozen=True)
class AvailabilityPublicationGeneration:
    generation_id: str
    definition_fingerprint: str
    index: Mapping[SuppressionKey, tuple[AvailabilityPublicationBinding, ...]]
```

Layer 6 composes the generation at staging from the exact owner keys declared by Layers 3, 4 and 5
and the bindings declared by Layer 5. It rejects a binding whose key has no declared owner, a
duplicate `automation_scope_id` for one key, and an automatically authorized resumable Reaction
without an enabled resident-visible binding for `active_channel_unmanaged_after_restart` (Layer 5
§3.2). The `AvailabilityEpisodeTracker`, its episode/sub-episode rules, the reconciliation at a
generation swap, `binding_deactivated` and the per-run identity are exactly those of Layer 3 §6.3.1.

### 9.3 Advisory, action notice, consent and proposal adapters

These adapters map their Layer-5 occurrences one to one. Closing phases (`closed` of an advisory,
consent request or proposal) append their audit fact, retire any undelivered opening record of the
same item, and apply §7.4 clearing when the opening phase was delivered. The advisory and consent
adapters attach the occurrence's response request to the opening delivery.

### 9.4 `recovery.confirmation_request`

`opened` is delivered with approve/dismiss to residents; `closed` clears it. An `opened` record still
undelivered at `expires_at` retires undelivered. A delivery failure never changes the request
(Layer 0 §7.4.1).

## 10. Configuration generation

The Layer-6 generation referenced by `LayerGenerationRef(layer="layer6")` (Layer 0 §4.7) contains:

```python
@dataclass(frozen=True)
class Layer6Generation:
    generation_id: str
    definition_fingerprint: str
    publication: AvailabilityPublicationGeneration
    recipients: tuple[NotificationRecipient, ...]          # canonical recipient_id order
    silenced_families: frozenset[Literal["attention", "governance"]]
```

Publication keys enter Layer 0's dependency index. Recipients and family options have no
dependents: changing them produces an empty impact record and needs no confirmation. The
generation swaps between cycles with the rest of the composed generation; records not yet delivered
are routed with the new recipients.

## 11. Restart and recovery

- The scheduler is rebuilt from the outbox: every `ready` record is scheduled again unless §7.5
  retires it (at-least-once delivery; a repeat on the phone is replaced through its tag).
- Follow-up intents are recovered by Layer 0 §4.5.1.
- Pre-restart advisories without a closing phase retire undelivered.
- Recovery confirmations invalidated by the restart arrive as `closed` occurrences from Layer 0.
- Digest windows restart from the current open set; the 4-hour spacing is not persisted, so a
  restart may send one extra digest.
- The availability tracker starts empty (Layer 3 §6.3.1).

## 12. Diagnostics

Layer 6 contributes to the existing diagnostics surface:

- per kind: occurrences accepted and rejected, facts appended, records ready, delivered and
  retired undelivered by cause;
- per recipient and endpoint: attempts, failures, last success, and the channel used;
- fallback deliveries and failed fallbacks;
- held items by family and digest state (window open, next allowed digest);
- audiences with no reachable recipient;
- responses forwarded to the ingress, and ignored action events.

Diagnostics never contain rendered text or person identities beyond `recipient_id`.

## 13. Required upstream changes

Before approval these must be applied as a reviewed CA4 item:

- **U1 — Response request id on actionable occurrences.** `ConsentRequestOccurrence` and
  `ReactionAdvisoryOccurrence` must carry `response_request_id: str | None` (set on `opened`), the
  id their owner declared to the ingress. `RecoveryConfirmationOccurrence` already carries
  `request_id`. Without it Layer 6 cannot build the buttons.
- **U2 — Binding declaration fields.** Layer 5's availability-binding declaration must include the
  Reaction's descriptor id, used for the family (§6.1).
- **U3 — Layer-6 generation contents.** Layer 0 §4.7 names only the availability publication
  bindings as Layer-6 configuration; it must also name recipients and family options, with no
  dependents.
- **U4 — Consent authority identities.** Layer 5 §7.1.1 must state that each
  `HouseholdConsentAuthority` actor reference is an HA user id, the identity Layer 0's ingress
  verifies, so §5.2 can derive `consent_authorities` from recipients' `ha_user_id`.

## 14. Open points for the developer

1. **Retry schedule.** Proposed: 30 s, 2 min, 10 min, then fallback; failed fallback retried every
   30 min.
2. **Fallback scope.** HA's `persistent_notification` cannot target one user. Proposed: the fallback
   is created once when at least one resolved recipient stays unreachable, and is visible to every
   HA user.
3. **Advisory digest with several advisories.** HA allows at most three buttons per notification,
   so a grouped advisory notification cannot carry feedback buttons for each item. Proposed: the
   grouped notification has no buttons, and feedback for each advisory remains possible from the
   Layer-8 surface.
4. **Clearing a delivered advisory when it closes.** Proposed: yes, silently through its tag (no
   message), so its feedback buttons do not stay on the phone after the request is withdrawn.
5. **Availability family.** Proposed: every availability notice bound to a `safety.*` Reaction is
   `safety`, not only `manual_hold_active` (C3 named that case).
6. **Household consent declined by one of several authorities.** Today one `decline` closes the
   request for the household; other authorities can still grant from the Layer-8 surface. To be
   decided whether a decline should close the request or only record that person's answer.
7. **HA user in mobile action events.** Verify in HA's documentation that
   `mobile_app_notification_action` carries the authenticated HA user of the device, which the
   ingress requires.

## 15. Initial acceptance criteria

- Each Initial-V3 kind: a valid occurrence produces exactly one fact and one `ready` record under
  its operation id; an exact retry produces none; a conflicting retry is rejected; an invalid
  occurrence produces neither and one diagnostic.
- No event fact contains a title, message, display name or person identity; a template test
  renders every kind, phase and `context_version` in `it` and `en` within the length bounds.
- An installation with no recipients delivers a follow-up warning through `persistent_notification`.
- A recipient with two endpoints, one failing, is reached through the other; all endpoints failing
  through every retry produces the fallback; a failed fallback stays `ready`.
- An actionable phase is sent with buttons only to `supports_actions` endpoints; through the fallback
  it has none. A button press reaches Layer 0's ingress with the request id, action and HA user,
  and Layer 6 neither validates nor decides it.
- During quiet hours: an action notice is delivered at once; a follow-up is delivered when they end;
  with `attention` silenced it is retired undelivered and its fact remains; two advisories opened at
  night, one still open in the morning, produce one morning notification for the open one and a
  retired record for the other.
- Three proposals within 30 minutes produce one digest; one approved before the window ends is not
  counted; a fourth proposal one hour later waits for the 4-hour spacing; closing every open
  proposal clears the digest on the phone.
- A recovery confirmation `closed` clears the opening notification; an opening still undelivered
  at `expires_at` retires undelivered.
- An availability episode bound to a weather-protection Reaction is delivered as `safety` during
  quiet hours; the tracker scenarios of Layer 3 §6.3.1 pass unchanged.
- After a restart every `ready` record is delivered again with the same tag, a pre-restart
  advisory without closure retires undelivered, and no delivery blocks an evaluation cycle.
- Every delivery fires one `heima_notification` event with closed fields only.
