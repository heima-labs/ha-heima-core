# Heima v3 - Layer 6: Notification and Communication

**Status:** Defined V3 notification contract, approved 2026-10-13. Not implemented.
**Open corrections:** none.

**Layer:** 6 of 8. Builds on Layer 0's unified notification delivery outbox (§4.5), committed-state
observers (§4.8), authenticated
response ingress (§5.1.3), Runtime Scheduler, composed configuration generation (§4.7) and
recovery confirmation (§7.4.1); Layer 1's operational event mapping (§3.1); Layer 3's
availability-suppression contract (§6.3.1); Layer 4's availability-owner declarations (§7); and
Layer 5's typed occurrences (§6.0). It owns the Layer-6 decisions C1–C6 first recorded in
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
Assistant entity state for a decision, or writes a fact type it does not own. It reads from Home
Assistant only configuration: the system language and the registered `notify.*` services.

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
  and one `heima_notification` bus event. Heima adds no own push channel, scheduler UI or user
  accounts; recipient preferences (§5.4) are keyed by `recipient_id`, not a user store.
- **Delivery preference is not authority.** Being in an audience grants nothing. Every answer is
  verified by Layer 0's ingress and decided by its owner.
- **No hot-path work.** Adapters run when an occurrence arrives, never inside a Layer-2–5
  evaluation; delivery I/O is asynchronous and never blocks a cycle, an `ApplyStep` or a
  revocation. The one bounded wait is Layer 5's follow-up preparation acknowledgement, limited by
  its core deadline (Layer 5 §6.0, Layer 0 §4.5.1); delivery is never awaited.

## 4. Notification kinds

### 4.1 `NotificationKindRegistry`

The registry is closed, core-owned and frozen at bootstrap. Administrators, learners and extensions
cannot add a kind. Each entry fixes everything that is not configuration:

```python
NotificationFamily = Literal["safety", "attention", "suggestion", "governance"]
NotificationAudience = Literal["residents", "administrators", "consent_authorities", "house"]

@dataclass(frozen=True)
class NotificationKindDescriptor:
    notification_kind: str                 # equals the event fact_type and the Layer-0 claim
    claim_owner_id: str                    # Layer 0 FactTypeClaim owner, e.g. "layer6.reaction_advisory"
    input_type: str                        # the closed typed occurrence the adapter accepts
    audiences: frozenset[NotificationAudience]  # non-empty; "house" only where admissible (§5.2)
    default_family: NotificationFamily | None   # None: resolved from the descriptor namespace (§6.1)
    severity: EventSeverity                # fixed per kind (Layer 1 §3.1)
    delivered_phases: frozenset[str]       # phases that reach people; other phases are audit only
    clearing_phases: frozenset[str]        # phases that clear an earlier delivered phase (§7.4)
    response_owner_id: str | None          # Layer 0 §5.1.3 owner when actionable
    context_versions: frozenset[int]       # registered OperationalEventValue.context_version values
```

### 4.2 Initial-V3 kinds

| Kind | Input | Audiences | Family | Severity | Delivered phases | Answer |
|---|---|---|---|---|---|---|
| `reaction.follow_up` | `ReactionFollowUpOccurrence` (Layer 5 §6.0) | residents | by descriptor namespace (§6.1) | warning | the one outcome | none |
| `automation.availability` | `AvailabilitySuppressionOccurrence` via the tracker (§9.2) | residents | by descriptor namespace (§6.1) | warning | `abstaining`, `reason_changed`, `restored` | none |
| `reaction.advisory` | `ReactionAdvisoryOccurrence` (Layer 5 §6.0) | residents, house (when `house_delivery`) | suggestion | info | `opened` (`closed` clears) | `layer5.advisory_feedback`: done / dismiss / not_useful |
| `reaction.action_notice` | `ReactionActionNoticeOccurrence` (Layer 5 §6.0) | residents, house (when `house_delivery`) | by descriptor namespace (§6.1) | info | the one notice | none |
| `recovery.confirmation_request` | `RecoveryConfirmationOccurrence` (Layer 0 §7.4.1) | residents | attention | warning | `opened` (`closed` clears) | `layer0.recovery_confirmation`: approve / dismiss |
| `reaction.consent_request` | `ConsentRequestOccurrence` (Layer 5 §6.0) | consent_authorities | governance | info | `opened`, `reissued` (`closed` clears) | `layer5.household_consent`: grant / decline |
| `proposal.review_pending` | `ProposalReviewOccurrence` (Layer 5 §6.0) | administrators | governance | info | `created`, `approvable_again`, grouped by the digest (§6.3) | none; link to the Layer-8 panel (§7.2) |
| `system.health` | `RuntimeHealthOccurrence` (Layer 0 §10.1) | administrators | attention | error | `error_opened`, `restored` (`causes_changed` is audit only; the panel shows current causes live) | none |

Every Initial-V3 kind uses `context_version=1`. A future context change registers a new version and
keeps the previous template while retained history can contain it (Layer 1 §3.1).

A kind declares a set of audiences (CA4-124); the column above lists it. Only `reaction.advisory` and
`reaction.action_notice` admit `house`, always together with `residents`, and deliver to it only
when the occurrence's `house_delivery` is `True` (Layer 5 §6.0, on-site delivery). Every other kind
never reaches `house`.

### 4.3 Adapter contract

Each kind has exactly one core adapter. The availability adapter is invoked by the tracker once per
user-visible binding delivery (§9.2), not once per owner occurrence. On an occurrence it:

1. validates the occurrence against its closed contract (identities non-empty, phase and reason
   fields consistent, sizes bounded) and rejects it otherwise with a diagnostic;
2. builds the event fact: `fact_type=notification_kind`, `where=subject`, `when=occurred_at`
   (`detected_at` for an availability occurrence; the recovery instant for
   `interrupted_before_outcome`), `how.source=FactSource(kind="system",
   source_id=claim_owner_id)`, and an `OperationalEventValue` with the kind's severity, its
   `context_version`, its `notification_key` (§7.6) and the occurrence's closed fields mapped to
   scalar `context` entries;
3. commits the fact and the outbox `ready` record in one transaction under
   `(notification_kind, operation_id)` (for `reaction.follow_up`, the transition from its
   `prepared` intent, Layer 0 §4.5.1);
4. hands the record to the delivery scheduler (§7.1).

An exact retry of the same operation returns the existing record; a different payload under the
same key is rejected (Layer 0 §4.5). `context` never contains a display name, rendered text, raw HA
state, an HA entity id or a person's identity; an `actuator_id` is a Layer-2 logical identity.

## 5. Recipients and audiences

### 5.1 Recipient model (C1)

A recipient is one person. Who that person is in the household comes from the Layer-2 `Person`
(Layer 2 §2.8), never from the recipient record.

```python
@dataclass(frozen=True)
class NotificationEndpoint:
    service: str                      # "notify.<name>", validated against HA's service registry at staging
    supports_actions: bool            # true only for an HA mobile-app notify service

@dataclass(frozen=True)
class NotificationRecipient:
    recipient_id: str                 # stable, administrator-chosen, e.g. "stefano"
    ha_person_id: str | None          # the classified Person (Layer 2 §2.8); household audiences
                                      # derive from its household_role
    endpoints: tuple[NotificationEndpoint, ...]
    administrator: bool               # member of the `administrators` audience
```

V2 groups and free routes are not carried over. Household membership is never configured on the
recipient: a recipient belongs to `residents` exactly when its Person is a `resident`. The
administrator only decides `administrator`. A recipient without a Person is admitted only with
`administrator=True` (for example an installer in a B2B deployment, who may have no HA person). A
recipient whose Person is a `guest` belongs to no household audience; it is reached only through
`house` while a guest stay is active (§5.2). Staging rejects duplicate
`recipient_id`s, two recipients for the same `ha_person_id`, an `ha_person_id` with no active
`Person`, a recipient without a Person and without `administrator`, a duplicate endpoint within one
recipient, an unknown `notify.*` service and `supports_actions=True` on a service that is not a
mobile-app notify service. The HA user of a recipient, used for self-service (§5.4) and the panel
principal (Layer 8 §4), is its Person's stored `ha_user_id`.

### 5.2 Audience resolution

- `residents` is derived: the recipients whose Person is a `resident`.
- `house` (CA4-124) is whoever is in the house and is not addressed as a person: every configured
  `HouseEndpoint` (a device account such as the guest-room tablet), every recipient whose Person is a
  `guest` while `household.guest_stay` (Layer 2 §2.9) is active, and the Heima map card's banner
  (Layer 8 §9.14). A `house` item's content is safe for anyone present: closed fields, room and
  device names only, never a person's identity or a personal fact. Being in `house` never makes a
  guest a resident and grants nothing.
- `administrators` is the recipients with `administrator=True`. An administrator may be a non-resident
  (an installer, B2B), so an `administrators` kind (`proposal.review_pending`, `system.health`)
  carries no resident personal data: no person identity, presence or household context.
- `consent_authorities` is derived, never configured: the recipients whose `ha_person_id` is in the
  current `HouseholdConsentAuthority` (Layer 5 §7.1.1). A consent-authorized person without a
  recipient record counts as unreachable, so the fallback applies (§7.3).
- Resolution happens at delivery time against the active Layer-6 generation, so a later change of
  recipients applies to notifications not yet delivered.

### 5.3 No silent drop

If an audience resolves to no recipient with at least one endpoint, the notification is delivered
through the fallback channel (§7.3). The `house` audience is the exception: it is always declared
together with `residents`, so an empty `house` (no device endpoint, no guest, no open card) is
normal and never triggers the fallback. This is also the behavior of an unconfigured installation.
Recipients excluded by their own preferences (§5.4) are not unreachable: they chose not to receive
it, so their exclusion never triggers the fallback.

### 5.4 Recipient preferences (CA4-116)

Each person may adjust their own notifications. Preferences are Layer-6 data stored with HA's
storage helper, outside the composed generation: they have no dependents, are saved at once with no
change set or impact preview, and do not require configuration authority.

```python
PersonalFamily = Literal["attention", "suggestion", "governance"]
FamilyLevel = Literal["default", "quiet_silent", "off"]

@dataclass(frozen=True)
class RecipientPreferences:
    recipient_id: str
    revision: int                                   # incremented by every save
    locale: str | None                              # None: household locale (§8.2)
    family_levels: Mapping[PersonalFamily, FamilyLevel]   # a missing family is "default"
    disabled_endpoints: frozenset[str]              # notify services of this recipient's endpoints
```

- **Family levels.** `default` follows the household behavior (§6.2). `quiet_silent` applies §6.2's
  silent rule to this person only. `off` excludes this person from that family at all times.
  `safety` has no personal level.
- **Never filtered.** A phase with answer buttons whose request is still open (a consent request, a
  recovery confirmation) reaches the person whatever the family level (CA4-77), and `safety` is
  never filtered by family.
- **Endpoints.** Delivery skips the disabled endpoints. A save that would disable every endpoint of
  the recipient is rejected. If an administrator later removes endpoints so that only disabled ones
  remain, the disabled set is ignored until the next save and a diagnostic is raised.
- **Who saves.** A resident through `notifications/set_preferences` for their own `recipient_id`
  (the recipient whose Person's stored `ha_user_id` is theirs), an administrator for any recipient
  (Layer 8 §13). A guest does not edit preferences.
  A save carries the `revision` it was based on; a stale one is rejected without change. A `locale`
  without a translation resource, a family outside `PersonalFamily` or an endpoint the recipient
  does not have is rejected.
- **Lifecycle.** A missing entry means every value is default. When a generation swap removes a
  recipient or one of its endpoints, the entry or the endpoint reference is dropped.
- **Personal quiet hours** with their own schedule are not part of Initial V3: Layer 6 has no
  schedule of its own and uses the casa `quiet_hours.active` fact.

## 6. Families, quiet hours and digests

### 6.1 Families (C3)

Families are closed and fixed per kind (§4.2). For the three kinds that report on a Reaction's
action — `reaction.follow_up`, `automation.availability` and `reaction.action_notice` — the family
comes from the namespace of that Reaction's descriptor (for availability, the descriptor of the
binding it is delivered for), through one closed core table:

| Descriptor namespace | Family |
|---|---|
| `safety.*` | `safety` |
| `environment.*`, `security.*`, `routine.*` | `attention` |

So a window held open while weather protection is active, a weather-protection step left
unconfirmed, the weather-protection action notice and every `safety.posture_check` advisory
(Layer 5 §7.5) are all `safety` notices. A future descriptor
namespace must add its row with the descriptor's core release; bootstrap fails if a registered
Reaction descriptor's namespace has no row, so no namespace falls into a family by default.

Priority maps to Home Assistant mobile push options: `safety` uses the time-sensitive
interruption level (iOS) and high priority (Android); the other families use the platform default.
Heima never uses the iOS critical-alert level.

### 6.2 Quiet hours

Quiet hours are the casa `quiet_hours.active` fact already used by the Layer-5 `quiet_hours.v1`
guard. Layer 6 registers one Layer-0 committed-state subscription to it at bootstrap (Layer 0 §4.8)
and keeps the latest delivered value; the change to `False` (or to unavailable) releases held
items at once. It has no own schedule and does not poll. If the fact is not configured there are
no quiet hours.

| Family | During quiet hours | Administrator option |
|---|---|---|
| `safety` | delivered immediately | none: can never be silenced |
| `attention` | held; delivered when quiet hours end | may be set to silent |
| `suggestion` | held; one end-of-quiet-hours digest of the still-open advisories (§6.4) | none |
| `governance` | held; delivered when quiet hours end, proposals through their digest | may be set to silent |

"Silent" for a family means its informative notifications produced during quiet hours are retired
undelivered when quiet hours end; their audit facts remain. A phase with answer buttons whose request
is still open (a recovery confirmation, a consent request) is never silenced: it is held and
delivered when quiet hours end, and retires undelivered only if its request closes or expires
first (§7.5). While `quiet_hours.active` is unavailable, Layer 6
treats quiet hours as not active, so nothing is held indefinitely.

Personal levels (§5.4) combine with this table per recipient, the most restrictive winning: `off`
excludes the person; `quiet_silent`, or the household's silent option for that family, makes the
family silent for the person during quiet hours. For `suggestion`, `quiet_silent` excludes the
person from the end-of-quiet-hours digest. The household option is unchanged for everyone else.

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

The digest applies to residents only; `house` delivery is never digested: the map card shows open
items, and a device endpoint receives each phase under the same quiet-hours rule as the household.

During quiet hours, each `reaction.advisory` `opened` record is held. When quiet hours end, Layer 6
selects the held advisories whose activation is still open (no `closed` phase yet) and delivers them
per resident as one notification. A closed advisory retires undelivered. A digest that contains one
advisory is delivered as that advisory's ordinary actionable notification. A digest of several
advisories carries no buttons, because HA allows at most three actions per notification on Android;
feedback on each advisory remains possible from the Layer-8 surface through the same ingress until
its activation closes.

## 7. Delivery

### 7.1 Scheduler

The delivery scheduler is an in-memory coordinator rebuilt from the outbox at process start. For
each `ready` record it decides exactly one of: deliver now, hold (quiet hours or digest window),
group into a digest, or retire undelivered (§7.5). It uses the Layer-0 Runtime Scheduler for every
timer; it has no own timer.

### 7.2 Primary channel

For each resolved recipient, and for each `HouseEndpoint` of a `house` delivery, Layer 6 sends one
call to each endpoint `notify.*` service with:

- the rendered title and message (§8);
- `data.tag`: the item tag (§7.4), so a retry or later phase replaces, never duplicates;
- `data.actions`: only for an actionable phase, only on an endpoint with `supports_actions`, and never
  to a `house` target (a guest or a device never answers; advisory feedback is resident evidence);
- `data.url` (or `clickAction`): the Layer-8 panel address (Layer 8 §5.1) of what the item
  concerns, built from the item's own ids:

  | Kind | Address |
  |---|---|
  | `recovery.confirmation_request` | `/heima/todo/request/<request_id>` |
  | `reaction.consent_request`, `reaction.advisory` | `/heima/todo/request/<response_request_id>` |
  | `reaction.follow_up`, `reaction.action_notice` | `/heima/automations/reaction/<reaction_id>?at=<occurrence instant>` |
  | `automation.availability` | `/heima/automations` (its input carries no `reaction_id`) |
  | `proposal.review_pending` (digest) | `/heima/automations/proposal` |
  | advisory digest (§6.4) | `/heima/todo` |
  | `system.health` | `/heima/system/health` |

- the push priority of §6.1.

A recipient is reached when at least one of its endpoints accepted the call. The per-call payload
is the transient `HeimaEvent` envelope derived from the event fact (Layer 1 §3.1); it is never
persisted.

### 7.3 Retries and fallback

Failed endpoint calls are retried after 30 seconds, 2 minutes and 10 minutes (core-fixed). When at
least one resolved recipient is still unreached after the last retry, when a consent authority has
no recipient record (§5.2), or when the audience has no reachable recipient, Layer 6 creates one `persistent_notification` with `notification_id` equal to
the item tag. HA cannot address it to one user: every HA user, guests and device accounts included,
sees it. It therefore carries **no content** (CA4-124): only the core text "Heima has an undelivered
message for residents" (or "for administrators"), in the household locale, and the panel address as a
Markdown link. The content is read only in the role-filtered panel; a viewer without the role sees
nothing there. An actionable phase delivered only through the fallback carries no buttons; it remains
answerable from the Layer-8 surface through the same ingress (C2). The record becomes `delivered`
once every resolved recipient was reached or the fallback accepted. A failed fallback keeps the
record `ready` and is retried every 30 minutes; diagnostics expose it.

### 7.4 Item tags and clearing

The item tag identifies one notified item across its phases:

| Kind | Item tag source |
|---|---|
| `reaction.advisory` | `reaction_activation_id`, `member_index`; one fixed tag per resident for an advisory digest (§6.4) |
| `recovery.confirmation_request` | `request_id` |
| `reaction.consent_request` | `reaction_id`, `configuration_generation_id`, `authority_transition_id` |
| `proposal.review_pending` | one fixed digest tag per audience |
| `system.health` | one fixed tag per installation, so the phone shows only the current health |
| `automation.availability` | `automation_scope_id`, subject |
| other kinds | the record's `notification_key` |

The tag is `"heima:" + notification_kind + ":" + sha256(RFC-8785 tag source)[:32]`. A clearing
phase (§4.1) sends `clear_notification` on the item tag to every recipient that received the
opening phase (after a restart, to every recipient of the audience, since that record is in
memory) and dismisses the fallback `persistent_notification`; it shows no new message. An advisory
digest is cleared when every advisory it covered has closed.
Clearing is best effort and never changes the item's state. Because successive phases of one item
share its tag, the phone always shows only the item's latest phase: an automation that is blocked,
restored and blocked again within minutes leaves one notification showing its current state.

### 7.5 Retirement without delivery

A `ready` record retires undelivered only when:

- it is an audit-only phase (not in the kind's `delivered_phases`), right after its clearing
  action (§7.4);
- its item closed before delivery (advisory, proposal, recovery confirmation, consent request);
- its item expired (a recovery request past `expires_at`);
- its family is silent during quiet hours and the phase is informative (§6.2);
- it is a pre-restart advisory without a closing phase (Layer 5 §6.0);
- it is a consent opening superseded by a `reissued` phase of the same request (§9.3);
- every resolved recipient is excluded by their own preferences (§5.4), cause
  `recipient_preferences`. When only some recipients are excluded, the record is delivered to the
  others; each exclusion is counted per recipient.

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
Layer 0's ingress (§5.1.3), and does nothing else. The mobile app fires this event through its
registration webhook, and HA sets the event context's `user_id` to the HA user the device is
registered to (`mobile_app` `registration_context`); an event without a user is rejected by the
ingress. Because the same webhook can fire any event type, the button payload is not trusted:
the unguessable request id, the verified user and the owner's own check decide. It never interprets, validates or answers a
response itself; an unknown prefix is ignored. The response request id comes from the occurrence
(§13, U1).

### 7.8 Home Assistant bus event

After each delivery (including the fallback and each digest) Layer 6 fires one
`heima_notification` event with closed fields only: `notification_kind`, `family`, `audiences`,
`phase`, `operation_id` (or the digest's covered count) and `channel` (`notify` or
`persistent_notification`). It carries no text, recipient or person identity. Users may build their
own automations on it; Heima never consumes it.

## 8. Rendering and languages (C6)

### 8.1 Templates

Each `(notification_kind, context_version)` has one core-fixed template, selected further by the
closed `context` fields (phase, intent, closing reason, outcome). A template is a set of
translation keys, never a literal string in code; its texts live in per-locale translation
resources (English is the source locale), so adding a language adds a resource file and no code.
Templates are versioned with the core and not editable by administrators. A template uses only closed context
fields, the subject Location, the effective names resolved from the current configuration under
Layer 2 §2.7 (room, opening, Actuator, Sensor and the Reaction itself) and the core-owned localized
label of the Reaction's descriptor. A live Home Assistant name longer than 64 characters is
truncated; an identifier that is no longer
configured is shown as the identifier. An unknown `context_version` renders a generic text with the
kind and identifiers.

Rendered output is bounded: title at most 120 and message at most 600 UTF-8 bytes in every locale,
checked by template tests. Templates must respect the content rules already fixed upstream, for
example the follow-up labels an observation with its time and never claims an interrupted command
completed (Layer 5 §6.0), a `house` item never addresses the reader as the person who acted, and an unmanaged-after-restart notice never asserts that Heima switched
the device off (Layer 3 §6.3.1).

### 8.2 Locale

The household locale is HA's `hass.config.language`; a recipient may choose its own `locale` in
its preferences (§5.4), accepted only if a translation resource exists for it. Initial V3 ships `en` and `it`
resources; a locale without a resource, or a key missing from one, falls back to `en`. Dates,
times, numbers and units are formatted with the locale and HA's unit system, never hard-coded. A digest covering several
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
    user_visible: bool

@dataclass(frozen=True)
class AvailabilityPublicationGeneration:
    generation_id: str
    definition_fingerprint: str
    index: Mapping[SuppressionKey, tuple[AvailabilityPublicationBinding, ...]]
```

```python
@dataclass(frozen=True)
class BindingEnablementChange:
    automation_scope_id: str
    enabled: bool                     # True exactly while the Reaction's mode is `automatic`
    authority_transition_id: str      # the committed Layer-5 transition that caused it
```

**Enablement revisions.** `enabled` changes through Layer-5 authority transitions, which are not
configuration mutations (Layer 0 §4.7), so they do not create a new generation. Layer 5 pushes one
`BindingEnablementChange` after the transition commits (Layer 5 §4.2). Layer 6 applies it as a
revision of the current publication index: same `generation_id`, a new revision number, the same
swap reconciliation as Layer 3 §6.3.1 (a newly enabled binding receives an already active
abstention; a disabled notified binding closes with `binding_deactivated`). A change whose
`authority_transition_id` is already applied, or that names a Reaction of another generation, is
ignored.

Performance is bounded by construction:
- the change is processed in the tracker's own serialized slow path, never in an evaluation cycle,
  never by Layer 0 or Layer 1, and the authority transition never waits for it;
- the generation keeps a reverse index from `automation_scope_id` to its keys, built once at
  staging, so a revision copies only the affected keys (copy-on-write) and swaps one reference;
  its cost is proportional to that Reaction's bindings, not to the index size;
- nothing is persisted: at process start the index is built from the active generation and the
  current Layer-5 authority projection.

Layer 6 composes the generation at staging from the exact owner keys declared by Layers 3, 4 and 5
and the bindings declared by Layer 5. It rejects a binding whose key has no declared owner, a
duplicate `automation_scope_id` for one key, and an automatically authorized resumable Reaction
without an enabled user-visible binding for `active_channel_unmanaged_after_restart` (Layer 5
§3.2). The `AvailabilityEpisodeTracker`, its episode/sub-episode rules, the reconciliation at a
generation swap, `binding_deactivated` and the per-run identity are exactly those of Layer 3 §6.3.1.
The tracker hands each episode change (start, reason change, restoration) read-only to Layer 8's
automation-state projection (Layer 8 §10.3), whether or not a binding is user-visible.

### 9.3 Advisory, action notice, consent and proposal adapters

These adapters map their Layer-5 occurrences one to one. Closing phases (`closed` of an advisory,
consent request or proposal) append their audit fact, retire any undelivered opening record of the
same item, and apply §7.4 clearing when the opening phase was delivered. The advisory and consent
adapters build the answer buttons from the occurrence's `response_request_id`.

A consent request goes to every consent authority. The first answer decides for the household: a
`grant` or a `decline` closes the request (Layer 5 §6.0), and the `closed` phase clears the
notification on every authority's phone. A consent `reissued` phase (after a restart) replaces the
earlier notification of the same item through its tag with buttons carrying the new request id; if
the earlier phase was never delivered, its record retires undelivered.

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
    house_endpoints: tuple[HouseEndpoint, ...]             # canonical endpoint_id order (CA4-124)
    silenced_families: frozenset[Literal["attention", "governance"]]
```

```python
@dataclass(frozen=True)
class HouseEndpoint:
    endpoint_id: str                  # stable, administrator-chosen, e.g. "guest_room_tablet"
    service: str                      # notify.* of a device account, validated at staging
```

A `HouseEndpoint` belongs to no person and has no preferences; staging rejects a duplicate id or
service and an unknown `notify.*` service.

Recipient preferences (§5.4) are not part of the generation. Publication keys enter Layer 0's
dependency index. Recipients, house endpoints and family options have no
dependents: changing them produces an empty impact record and needs no confirmation. The
generation swaps between cycles with the rest of the composed generation; records not yet delivered
are routed with the new recipients.

## 11. Restart and recovery

- The scheduler is rebuilt from the outbox: every `ready` record is scheduled again unless §7.5
  retires it (at-least-once delivery; a repeat on the phone is replaced through its tag). Records
  whose family depends on quiet hours wait for the initial `quiet_hours.active` delivery after the
  first cycle (Layer 0 §4.8); `safety` records do not wait.
- Follow-up intents are recovered by Layer 0 §4.5.1.
- Pre-restart advisories without a closing phase retire undelivered.
- Recovery confirmations invalidated by the restart arrive as `closed` occurrences from Layer 0.
- Consent requests still pending arrive as `reissued` occurrences with a fresh request id (§9.3).
- Digest windows restart from the current open set; the 4-hour spacing is not persisted, so a
  restart may send one extra digest.
- The availability tracker starts empty (Layer 3 §6.3.1).
- Recipient preferences (§5.4) are loaded before the scheduler is rebuilt; a corrupt or unreadable
  store means default preferences for everyone and a diagnostic, never a blocked delivery.
- `system.health`: an error still present after the restart arrives as a new `error_opened`
  (Layer 0 §10.1); the fixed tag replaces the previous message.

**`system.health` without storage or configuration (CA4-109).** While `persistence_write_failing`
holds, the `ready` transaction can fail; Layer 6 then delivers that phase once, best effort from
memory, without a record or audit fact, and diagnoses it (Layer 0 §4.5). While
`no_active_manifest` holds there are no configured recipients, so the phase goes to the fallback
`persistent_notification` (§7.3). The `restored` phase uses the ordinary durable path once storage
works again.

## 12. Diagnostics

Layer 6 contributes to the existing diagnostics surface:

- per kind: occurrences accepted and rejected, facts appended, records ready, delivered and
  retired undelivered by cause;
- per recipient and endpoint: attempts, failures, last success, and the channel used;
- fallback deliveries and failed fallbacks;
- held items by family and digest state (window open, next allowed digest);
- audiences with no reachable recipient;
- per recipient: personal family levels, disabled endpoints, exclusions by family, and the
  ignored-disabled-set diagnostic (§5.4); per audience and family, whether every recipient is
  `off`, shown to administrators as a warning in Layer 8's Notifications section;
- responses forwarded to the ingress, and ignored action events.

Diagnostics never contain rendered text or person identities beyond `recipient_id`.

## 13. Upstream contracts introduced for this layer

- **U1 (CA4-73)** — `ConsentRequestOccurrence` and `ReactionAdvisoryOccurrence` carry
  `response_request_id`; a consent still open after a restart produces a `reissued` phase with a
  fresh id (Layer 5 §6.0).
- **U2** — Layer 5's availability-binding declaration names the Reaction's
  `reaction_descriptor_id` (Layer 5 §6.0, Layer 3 §6.3.1).
- **U3** — Layer 0 §4.7 includes recipients and family options in the Layer-6 generation, with no
  dependents.
- **U4** — every `HouseholdConsentAuthority` reference is an HA user id (Layer 5 §7.1.1).
- **CA4-74** — follow-up and action-notice occurrences carry `reaction_descriptor_id` (§6.1).
- **CA4-75** — Layer 0 committed-state observers (Layer 0 §4.8), used by §6.2.
- **CA4-76** — authority transitions push `BindingEnablementChange` to Layer 6 (Layer 5 §4.2, §9.2).
- **CA4-77** — actionable phases with an open request are never silenced (§6.2).

## 14. Initial acceptance criteria

- `system.health`: an `error_opened` reaches every administrator recipient with the `attention`
  family (held during quiet hours, silenceable), severity `error` and the address
  `/heima/system/health`; `restored` replaces it on the phone through the fixed tag; a
  `causes_changed` produces its audit fact and no delivery (CA4-110). With durable
  writes failing it is still delivered once from memory and diagnosed; with no active manifest it
  appears as a `persistent_notification` (CA4-109).

- Every delivered phase carries the Layer-8 panel address of §7.2 for its kind, built only from the
  item's ids (no name, no `entity_id`); a recovery request delivered without buttons opens
  `/heima/todo/request/<request_id>`, and the fallback `persistent_notification` ends with the same
  address as a Markdown link (CA4-106).

- Each Initial-V3 kind: a valid occurrence produces exactly one fact and one `ready` record under
  its operation id; an exact retry produces none; a conflicting retry is rejected; an invalid
  occurrence produces neither and one diagnostic.
- No event fact contains a title, message, display name or person identity; a template test
  renders every kind, phase and `context_version` in every shipped locale within the length
  bounds, and finds no user-facing literal string outside translation resources.
- An installation with no recipients delivers a follow-up warning through `persistent_notification`.
- A recipient with two endpoints, one failing, is reached through the other; all endpoints failing
  through every retry produces the fallback; a failed fallback stays `ready`.
- An actionable phase is sent with buttons only to `supports_actions` endpoints; through the fallback
  it has none. A button press reaches Layer 0's ingress with the request id, action and HA user,
  and Layer 6 neither validates nor decides it.
- During quiet hours: an action notice is delivered at once; a follow-up is delivered when they end;
  with `attention` silenced it is retired undelivered and its fact remains, while a recovery
  confirmation still open is delivered when quiet hours end; two advisories opened at
  night, one still open in the morning, produce one morning notification for the open one and a
  retired record for the other.
- Three proposals within 30 minutes produce one digest; one approved before the window ends is not
  counted; a fourth proposal one hour later waits for the 4-hour spacing; closing every open
  proposal clears the digest on the phone.
- A recovery confirmation `closed` clears the opening notification; an opening still undelivered
  at `expires_at` retires undelivered.
- An availability episode, an unconfirmed follow-up and an action notice of a weather-protection
  Reaction are delivered as `safety` during quiet hours, while the same kinds for an
  `environment.*` Reaction are held; the tracker scenarios of Layer 3 §6.3.1 pass unchanged.
- After a restart every `ready` record is delivered again with the same tag, a pre-restart
  advisory without closure retires undelivered, and no delivery blocks an evaluation cycle.
- Every delivery fires one `heima_notification` event with closed fields only.
- Promoting a Reaction to `automatic` while its suppression episode is active delivers that
  abstention once through a `BindingEnablementChange` revision; disabling it closes a notified
  binding with `binding_deactivated`; a repeated change is ignored; neither the authority
  transition nor any evaluation cycle waits, and the revision touches only that Reaction's keys.
- Recipient preferences (CA4-116): with `attention` `off` for one resident, a follow-up reaches the
  other residents only; with `attention` `off` for every resident, it retires undelivered with cause
  `recipient_preferences`, no fallback is created, and administrators see the warning; with
  `governance` `off`, an open consent request still reaches the person; `safety` reaches everyone;
  `quiet_silent` retires a night follow-up for that person while others get it in the morning; a
  disabled endpoint is skipped, and disabling the last enabled one is rejected; a resident saving
  another recipient's preferences is rejected; a stale revision is rejected; a recipient with
  `locale="it"` receives Italian text while the household locale is `en`.
- House audience (CA4-124): an `environment.external_exchange` advisory with `house_delivery=True`
  during a guest stay reaches residents, the guest-room `HouseEndpoint` without buttons, the guest's
  own endpoints and the map-card banner; without a stay the guest is not reached; a
  `safety.weather_protection` action notice with no `HouseEndpoint` configured reaches residents and
  the banner and creates no fallback; a recovery confirmation never reaches `house`; at night the
  device endpoint follows the household quiet-hours rule and no `house` digest exists. An unreached
  resident recipient produces one `persistent_notification` whose text is only "Heima has an
  undelivered message for residents" plus the panel link; the `heima_notification` event carries
  `audiences`.
- Recipients and Persons (CA4-118): a recipient whose Person is a `resident` receives `residents`
  kinds; reclassifying that Person to `guest` removes it from `residents` at the next delivery with
  no recipient edit; an installer recipient without a Person and with `administrator=True` receives
  only `administrators` kinds; a recipient without a Person and without `administrator`, or two
  recipients for one Person, is rejected at staging; a guest saving preferences is rejected.
- Items held during quiet hours are released by the committed-state delivery of
  `quiet_hours.active=False`, with no polling job; after a restart the initial delivery of the
  current value decides whether ready records are held.
