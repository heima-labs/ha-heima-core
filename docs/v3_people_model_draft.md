# Heima v3 — people model: residents, guests, devices (approved model)

Status: **model approved 2026-10-19 and applied to the V3 specs in CA4-118..125; not itself a spec.**
Opened 2026-10-19 from `v3_backlog.md`, open question 5 (guests). The layer specs are authoritative;
this file preserves the model, its decisions and the sweep. Incongruence warnings (§8) are specified
in CA4-126 (`safety.posture_check`).

## 1. Why this exists

V3 has no model of people. Three implicit assumptions hold only in a house without guests:

- "every non-administrator HA user is a resident" (Layer 0 actor mapping, Layer 8 roles);
- "presence means the household" (Layer 4 casa `presence`, Layer 5 absence programs);
- "a notification recipient is a resident" (Layer 6 recipients, Layer 8 roles).

A guest is a non-permanent person who stays in the house for one or more days, sometimes alone
(for example while a resident goes shopping), and must be able to use the house. This model
defines who people are, what they may do, what they may see and how their presence affects
Heima's behavior, independently of any layer. Layer changes are then derived from it, never
patched one by one.

## 2. Reference: how comparable projects model guests

Researched 2026-10-17/19 (sources in the chat record of the guest discussion):

- **Apple Home:** household members drive "last person leaves"; a guest is a separate role of the
  same user, with time windows, excluded from member presence.
- **Google Home:** household members opt in with their phones; Nest sensors detect "someone" without
  identity. Occupancy and household presence are naturally distinct.
- **Homey (core):** roles Owner/Manager/Resident/Guest; guests count toward household presence,
  which breaks "last person left" and is a recurring complaint.
- **Homey Smart Presence:** one person list with an "Is Guest" flag; separate household and guest
  triggers.
- **Home Assistant:** `person.*` links user and trackers; `zone.home` counts everyone; no guest
  flag, so users build groups or an `input_boolean` guest mode.
- **SmartThings / Hubitat:** a guest mode or virtual presence sensor, mainly to stop "house empty"
  routines and alarms while a house sitter is inside.
- **Access control:** real limits exist only on the device (time-limited lock codes) or in an API
  filter (custom RBAC integrations); UI-only restrictions are not a boundary anywhere.

Lessons: one person list from the platform plus a resident/guest classification; household
presence computed over residents only; a declared guest context; access enforced on the device.

## 3. Concepts

### 3.1 Person and household role

- A **person** is a Home Assistant `person.*`, referenced by HA's stable internal person id, never
  by its renameable `entity_id`. Heima creates no person registry and no per-person entity.
- Heima adds one administrator-assigned classification per person:
  `HouseholdRole = resident | guest`. An unclassified person is ignored by every household concept.
- The HA administrator flag is an independent axis: an administrator may be a resident or neither.
- The classification is compiled configuration: Layers 0, 4, 5, 6 and 8 all read it, so it belongs
  to the composed generation, not to out-of-generation data.

### 3.2 Device account

An HA user with no classified person (a shared guest-room tablet in kiosk mode, a wall panel) is a
**device**, not a person. It never contributes to presence and has no household authority. It is
not a person recipient, but it may be a delivery endpoint for house-level notifications addressed
to whoever is in the house (for example "close the windows, it is warmer outside"); see §8 and Q11.

### 3.3 Actor

Every human interaction carries an actor with two independent axes, derived from the authenticated
HA user:

| Axis | Values | Derived from |
|---|---|---|
| household role | `resident \| guest \| none` | the classification of the user's person; `none` for a device account or an unclassified person |
| HA administrator | yes / no | HA's administrator flag |

A wall switch or other physical control has no actor.

- **Learning and household authority** (consent, request answers, stay declaration, advisory
  feedback) read the household role.
- **Heima configuration** reads the administrator flag.
- An administrator is not necessarily a resident: Heima is also a B2B product (installer,
  integrator, property manager). A non-resident administrator configures Heima, but their controls
  teach Heima nothing and they make no household decision except where §6 says so.
- The actor replaces "non-admin means resident" everywhere: commands, request answers, direct device
  control and learning evidence.

### 3.4 Presence and context facts

| Fact (name, D2) | Question | Source | Values |
|---|---|---|---|
| room occupancy, `occupancy@room` | Is someone in this room? | physical evidence only | `present \| absent` |
| casa occupancy, `occupancy@casa` (today's casa `presence`) | Is someone in the house? | physical evidence only (motion, mmWave, contacts, vision person); no identity trackers | `present \| away` |
| household presence, `presence@casa` | Is any resident home? | `person.*` of residents, each a registered sensor | `home \| away` (aggregate only) |
| guest stay, `household.guest_stay` | Is a guest stay declared? | declared by a resident or administrator | `active \| inactive`, optional end, optional guest rooms |

- Each fact has its own departure/return episodes: `occupancy.departure`/`occupancy.return` for the
  casa and `presence.departure`/`presence.return` for the household.
- Declared household context lives under `household.*` (`household.guest_stay`,
  `household.planned_absence`).
- A guest stay is never inferred (Layer 3 already forbids `possible_guest` without direct
  multi-occupant-count evidence) and a guest cannot declare it.
- Every consumer declares which fact it reads. There is no generic "presence".

## 4. Invariants

1. **A guest is never a resident.** No path (recipient link, consent authority, panel role, actor
   class, presence) turns a guest into a resident.
2. **Household role comes only from explicit classification**, never from the HA administrator
   flag, a recipient link or observed behavior.
3. **Guest presence is never inferred**, and a guest stay is declared only by residents or
   administrators.
4. **Resident learning never consumes guest behavior.** Behavior learning stops while the house is
   occupied without residents, and in the guest rooms during a declared stay; guest- and
   device-attributed actions are never resident evidence. Physical learning (for example the
   thermal model) is not about people and continues.
5. **Heima is not a permission system.** No guest-facing restriction claims to be a security
   boundary; HA has only administrator/non-administrator.
6. **Heima never commands locks or alarms for guests.** Lock codes and alarm users belong to their
   integrations; Heima only observes their state and warns about incongruences that do not depend
   on who is inside (§8).
7. **Guests and devices never see resident identity, resident presence or history.**
8. **Each presence consumer names its fact** (§3.4); no consumer reads "presence" generically.

## 5. Situations and behavior

### 5.1 Derived situation: occupied without residents

"Occupied without residents" holds when casa occupancy is `present` and household presence is
`away`. It is derived every cycle, needs no declaration and does not ask who is inside (guest alone,
house sitter, pet sitter, cleaner, untracked resident). Unavailable inputs make it undecidable,
never true by default. While it holds:

- **Behavior learning** accumulates nothing, in every room. **Physical learning** continues.
- **Each Reaction descriptor** declares, fixed in its version and chosen by the developer (never an
  administrator setting), `when_occupied_without_residents: continue | pause`. A paused
  activation resumes when the situation ends.

| Descriptor | Policy |
|---|---|
| `environment.planned_comfort_trajectory` | `pause` |
| `security.presence_simulation` | `pause` (it also pauses on any casa occupancy) |
| occupancy lighting, shading, ventilation, extraction, weather safety | `continue` |
| `routine.actuation_bundle` | `continue` (acts for whoever is inside; learns nothing) |

No warning is raised for this situation: Heima is not a security system, and intrusion belongs to
the alarm integration.

### 5.2 Declared guest stay: hosting with residents home

A guest stay is needed only where §5.1 cannot help: residents and guests at home together, which
cannot be told apart without a declaration. A resident or administrator declares it (panel or
calendar, Q1) with optional end and guest rooms. While active:

- behavior learning is excluded in the guest rooms for the whole stay and continues in every other
  room (Q5);
- guests with an account are reached by the `house` audience (§8);
- every Reaction keeps working for anyone present.

### 5.3 Situation table

| # | Casa occupancy | Household | Guest stay | Situation | Behavior |
|---|---|---|---|---|---|
| S1 | present | home | inactive | normal | — |
| S2 | present | home | active | hosting | §5.2 |
| S3 | present | away | any | occupied without residents | §5.1 |
| S4 | away | away | any | empty | absence programs eligible when a planned absence is active (§5.4) |
| S5 | away | home | any | evidence conflict | diagnostic only (for example a phone left at home) |

### 5.4 Absence programs

`planned_absence_program` descriptors are eligible only when a planned absence is active and
household presence is `away`.

- **Comfort trajectory:** also requires the planned absence to be longer than a minimum duration
  derived from the learned thermal response, 48 hours by default (Q13). It pauses while the house is occupied without residents (§5.1) and resumes when the house
  is empty again. Only a household `return` ends it. It does not read the guest stay.
- **Presence simulation:** pauses whenever casa occupancy is `present`, whoever is inside, and
  resumes when the house is empty again. It does not read the guest stay.

## 6. Authority matrix

Columns combine both actor axes. "Admin" means an HA administrator who is not a resident; an
administrator who is also a resident has the union of both columns.

| Action | admin (non-resident) | resident | guest | device | physical |
|---|---|---|---|---|---|
| Configure Heima, classify persons | yes | only if also admin | — | — | — |
| Declare or end a guest stay | yes | yes | — | — | — |
| Answer advisory feedback | — | yes | — | — | — |
| Answer recovery confirmations | last resort only (below) | yes | — | — | — |
| Grant or revoke household consent | — | if in consent authority | — | — | — |
| Edit own notification preferences | yes | yes | — | — | — |
| Control devices from the map | HA permissions | HA permissions | HA permissions, presentational scope | HA permissions, presentational scope | — |
| Direct device control: Layer 0 hold | yes | yes | yes | yes | yes |
| Direct device control: resident learning evidence | — | yes | — | — | not attributable; covered by §5.1 and §5.2 |

- The consent authority accepts residents only.
- **Recovery confirmation, last resort:** a non-resident administrator may answer from the panel
  only when no resident can: the request has stayed unanswered by residents for a core-fixed
  escalation window (2 hours, CA4-118), or the active notification configuration has no resident
  recipient with an endpoint.

## 7. Visibility matrix

| Information | admin (non-resident) | resident | guest | device |
|---|---|---|---|---|
| House map, occupancy fill, device state | yes | yes | yes | yes |
| Configuration, diagnostics, system health | yes | — (unless admin) | no | no |
| Automation reasons | full, without resident identity | resident wording | sanitized: no person identity, no resident times, no security posture | sanitized |
| Household presence | no | yes | no | no |
| Guest stay | yes (it may declare one) | yes | no | no |
| Notifications | administrators audience | residents audience | `house` kinds during an active stay | `house` kinds (Q11) |
| Content of notifications addressed to residents | no | yes | no | no |
| Notification fallback (`persistent_notification`) | content-free notice + panel link | same | same | same |
| History, explanations, to-do | configuration and system history, actors without resident names | own scope | no | no |

- An administrator who is also a resident sees the union of both columns.
- Like every restriction in this model, hiding resident data from a non-resident administrator is
  presentational: HA gives administrators access to `person.*` and history anyway (invariant 5).
  Heima only does not surface it.

## 8. Notifications

- A notification kind declares a set of audiences instead of one.
- New audience `house`, for kinds whose content is an action to take in the house now and is safe
  for anyone present (no person identity, no personal facts). It is always declared together with
  `residents`, never alone. It resolves to device endpoints and to persons classified `guest` with
  an active stay. A guest is reached only this way and never becomes a resident (invariant 1).
- Kinds that inform or govern (incongruences, recovery, consent, proposals, system health) never
  include `house`.
- Kinds for the `administrators` audience (system health, proposal review) carry no resident
  personal data, because the administrator may be a non-resident (B2B).
- Incongruence warnings go to residents and depend only on occupancy and observed device state,
  never on who is inside: alarm `armed_away` while the house is occupied, a door unlocked while the
  house is empty, windows open while the house is empty and it rains. They need their own kinds and
  are the first candidates for a security kind family.
- Future refinement, not Initial V3: deliver "act here and now" kinds to a resident only while that
  resident is home.

## 9. Lifecycle and declared limits

- **Start and end.** A stay starts with a declaration from the panel (resident or administrator),
  or from a calendar category (Q1), with an optional end. At the end it closes; if the guest is
  still inside with every resident away, §5.1 applies.
- **Guest account.** When a guest with an HA account ends a stay, administrators receive an
  advisory to disable the account. Heima never manages HA users.
- **Recurring guest.** The person stays classified `guest` across stays; each stay is a separate
  declaration.
- **UI.** The primary guest surface is a guest-room tablet (device account, map card with
  `control_rooms`, Layer 8 §9.14). A personal account is supported as a `guest` person.
- **Declared limits.** Heima is not a permission system; physical switches cannot be attributed;
  locks and alarms stay with their integrations; occupancy sees a guest only where physical
  sensors cover the rooms used, so guest rooms should have at least one occupancy sensor
  (diagnostic hint).

## 10. Questions (all resolved 2026-10-19)

- **Q1. Resolved 2026-10-19:** sources are the panel toggle (resident or administrator) and a
  calendar category. Both feed one "declared household context" fact family (guest stay, planned
  absence), produced once and read by every consumer; `planned_absence` migrates to it from the
  per-descriptor `CalendarPlanBinding`.
- **Q2. Resolved 2026-10-19:** household presence is computed over tracked residents, with a
  diagnostic for every resident without presence evidence. An untracked resident alone at home
  reads as "occupied without residents" (§5.1): behavior learning stops and the comfort trajectory
  pauses, both harmless. (The earlier option (b) disabled the unexplained-occupancy warning, which
  no longer exists.)
- **Q3. Resolved 2026-10-19:** the fallback `persistent_notification` carries no content, for
  every audience: only "Heima has an undelivered message for residents/administrators" and the
  panel address. The content is read only in the role-filtered panel; a viewer without the role
  sees nothing there. Answerable phases are answered from the panel as today.
- **Q4. Resolved 2026-10-19:** no `guests` audience. A kind declares a set of audiences (introduced
  regardless of guests). A new `house` audience is added only to "act here and now" kinds, always
  together with `residents`; it reaches device endpoints and guests with an active stay. Residents
  keep receiving those kinds wherever they are (today's behavior); routing by each resident's
  location is a declared future refinement, not Initial V3.
- **Q5. Resolved 2026-10-19:** for the whole stay, exclude resident learning in the guest rooms
  only.
- **Q6. Resolved 2026-10-19, revised:** comfort trajectory: a household `return` ends it; it
  pauses while the house is occupied without residents and resumes when the house is empty
  (§5.4). It no longer reads the guest stay.
- **Q7. Resolved 2026-10-19:** presence simulation pauses on any casa occupancy, whoever is
  inside, and resumes when the house is empty again; it does not read the guest stay.
- **Q8. Resolved 2026-10-19:** no, a guest does not edit notification preferences.
- **Q9. Resolved 2026-10-19:** no, a guest does not see their stay.
- **Q10. Resolved 2026-10-19:** yes, a guest's `person.*` is corroborating evidence of casa
  occupancy, never of household presence.
- **Q11. Resolved 2026-10-19:**
  - A kind declares `house` as an admissible audience; a Reaction descriptor enables it through a
    fixed declaration in its version (for example `on_site_actionable=True`), never an
    administrator setting. Initial V3 candidates: environmental advisories (for example cross
    ventilation) and, per descriptor, action notices.
  - Devices are reached by a banner in the map card (always) and optionally by a device
    `notify.*` endpoint; guests with an account through their own endpoints.
  - Addressing is whole-house in Initial V3; the notification `Location` allows a later room
    filter without a contract change.
  - Guests and devices get no answer buttons; advisory feedback stays resident-only. A banner can
    be dismissed locally with no effect on Heima.
- **Q12. Dissolved 2026-10-19:** unscheduled visits (house or pet sitter, cleaner) need no
  declaration: they are "occupied without residents" (§5.1), and the unexplained-occupancy warning
  is removed.
- **Q13. Resolved 2026-10-19:** the minimum planned-absence duration is derived by Layer 5, as a
  pure function at each evaluation, from the already selected `ThermalResponseParameter` of the
  current cell: `clamp(time to drift by thermal_delta_min at the slowest passive drift rate +
  conservative_recovery_duration, floor, ceiling)`. Default 48 hours when it cannot be derived;
  default, floor and ceiling are fixed by the descriptor version (values set in the spec pass). It
  tunes itself as the thermal model recalibrates; no new learner or artifact. Its rationale is
  thermal applicability only, never an energy-saving claim.

## 11. Next steps after approval

1. Systematic sweep of all V3 specs for every implicit assumption about people, actors, presence
   and recipients (not only the ones found so far, Appendix A).
2. Map each finding to a concept or invariant of this model. A change not derived from the model
   is suspect.
3. Apply coherent changes to all layers in one pass, with new CA4 items and `check_v3_specs.py`
   green.

## Appendix A — systematic sweep (2026-10-19)

Method: every V3 spec (`docs/specs/v3/*.md`, `contract_registry.json`) searched for resident,
household, guest, person, presence, departure/return, recipient, audience, actor, ha_admin,
non-admin, consent, persistent_notification, planned absence, CalendarPlanBinding and HA user, and
each hit classified. Hits where "resident" only means "a person reading Heima's text"
(resident-visible, resident text, resident-facing) are not listed one by one; see D5.

### A.1 Findings by layer

| # | Where | Current assumption | Model ref | Change |
|---|---|---|---|---|
| F1 | L0 §5.1 `FactSourceActorType`, `FactSource.kind` | `resident` = any non-admin user | §3.3 | actor carries household role and admin flag (D1) |
| F2 | L0 §5.1.3 response ingress | non-admin maps to `resident`; owners declare `resident`+`ha_admin` | §3.3, §6 | categories from §3.3; guests and devices never answer |
| F3 | L0 §5.1.1 resident-control edge | any non-admin direct control emits `actuator.resident_control` | §3.3, inv. 4 | emitted only for residents; guest/device control still creates a hold |
| F4 | L0 §6 hold origins (`resident_manual`, `admin_manual`) | manual origin = resident or admin | §6 | origin values per actor class (D6) |
| F5 | L0 §2 outbox note "a person — resident or administrator" | only residents and admins receive | §8 | add `house` targets |
| F6 | L0 recovery/checkpoint | no declared household context | §5.2 | guest stay and its end survive restart |
| F7 | L1 fact-type taxonomy (`presence`, `presence.planned_absence`) | one presence namespace | §3.4 | naming of occupancy, household presence, declared context (D2) |
| F8 | L1 §3.1 event fact types | each kind names one audience | §8 | audience sets |
| F9 | L2 casa-presence evidence | any evidence kind, WiFi/identity trackers included | §3.4 | casa occupancy physical only + guest `person.*` corroborating; new household-presence evidence from resident `person.*` |
| F10 | L2 registries | no person classification | §3.1 | new compiled `resident \| guest` classification of HA persons |
| F11 | L2 `CalendarWindowReadBinding` (active windows only) | calendar facts are active-now only | Q1 | guest stay fits; planned absence needs upcoming windows (D3) |
| F12 | L3 routine learner, correction counts, setpoint learner | resident evidence = `actuator.resident_control`; `no_resident_control` negatives | inv. 4, §5.1, §5.2 | censor episodes while occupied without residents and in guest rooms during a stay |
| F13 | L3 `ContextRegimeNoveltyModel` | household regime always learnable | inv. 4 | behavior learner: censored like F12 (D8) |
| F14 | L3 thermal absence cohorts (`departure`/`return`) | absence = casa presence episodes | §5.1 | physical learning uses occupancy episodes (D7) |
| F15 | L3 §ContextHypothesis, L4 §8 deferral text | guest context deferred, only as future hypothesis | §3.4 | guest stay is declared, never a hypothesis; `possible_guest` stays illustrative |
| F16 | L4 §9.2/§9.3, §10 | one casa presence claim, exactly one transition adapter | §3.4 | casa occupancy + household presence claims, two adapters, guest stay claim |
| F17 | L5 descriptor contract | no policy for occupied without residents; `resident_action_notice` bool | §5.1, §8 | `when_occupied_without_residents`, `on_site_actionable`, audience sets |
| F18 | L5 guard capability `presence` | bound to casa presence | inv. 8 | bound to casa occupancy (routine, presence simulation, air extraction) |
| F19 | L5 `planned_absence_program` | effective absence = plan + casa `away`; casa `return` ends | §5.4 | household presence, pause on §5.1, minimum duration (Q13), household `return` ends |
| F20 | L5 `CalendarPlanBinding` | calendar plan read per descriptor | Q1 | planned absence from the declared-context family (D3) |
| F21 | L5 `HouseholdConsentAuthority` | any `ha_user_id` | §6 | residents only |
| F22 | L5 advisory feedback, correction attribution | `resident` category = non-admin | §3.3 | residents (and admins) only; guest/device never |
| F23 | L6 §4.1 `NotificationAudience`, §4.2 table | one audience per kind | §8 | audience sets, `house` |
| F24 | L6 §5.1 recipients | admin-chosen id, configured `residents` audience | §3.1 | recipients anchored to classified persons; audiences derived |
| F25 | L6 §5.4 preferences (CA4-116) | keyed by `recipient_id` | §3.1 | stable person id; guests have none (Q8) |
| F26 | L6 §7.3 fallback | full content visible to every HA user | Q3 | content-free notice |
| F27 | L6 delivery | no device endpoints | Q11 | map-card banner + optional device `notify.*` |
| F28 | L8 §4 roles | resident = recipient-linked or consent authority | inv. 1, 2 | resident = person classified `resident` |
| F29 | L8 §5 sections | no place to classify persons or declare a stay | §3.1, §5.2 | classification (admin), stay declaration (resident, admin) |
| F30 | L8 §7/§14 history actor names | residents see own names, else "an administrator" | §7 | guest and device actors shown without identity |
| F31 | L8 §9.4 map header, §10.2 entity "Casa presence" | casa presence shown to everyone and exposed as HA entity | §7 | occupancy public; household presence residents only; HA entities per D4 |
| F32 | L8 §9.11, §9.14 | per-user control scope waits for guest model | §6 | scope remains presentational; guest rooms can preset `control_rooms` |
| F33 | L8 no-role rendering | "resident wording" for no-role viewers | §7 | sanitized wording for guests and devices |
| F34 | Architecture overview, contract registry | summaries of the above | — | updated with new contracts and dependencies |

### A.2 Decisions surfaced by the sweep

- **D1. Resolved 2026-10-19:** actor has two axes, household role and HA admin flag (§3.3). B2B:
  a non-resident administrator configures but makes no household decision except recovery
  confirmation as last resort (§6), and does not see resident personal data (§7).
- **D2. Resolved 2026-10-19:** option (a): `occupancy` at casa scope (same fact type as rooms),
  `presence` for the household, `occupancy.*`/`presence.*` episodes, `household.*` for declared
  context (§3.4).
- **D3. Resolved 2026-10-19:** one production point for `household.guest_stay` and
  `household.planned_absence`, both Layer-2 facts read directly by consumers (like
  `quiet_hours.active`); no consumer reads a calendar or the panel itself.
  - Shared production only: sources are a calendar category or a panel declaration (residents and
    administrators, backend-checked, never guests or devices); a panel declaration survives restart;
    sources are combined by union; an unreadable calendar makes the fact unavailable, never false.
  - Own value contract per fact: `guest_stay` is `active | inactive` plus declared guest rooms, read
    from active calendar windows only, panel end optional; `planned_absence` is the current
    coalesced interval with start and end (hence duration) or none, panel end mandatory, read over a
    bounded upcoming horizon to coalesce adjacent or overlapping windows (the Layer-5 union rule,
    moved unchanged).
  - Horizon: fixed by the core, larger than the Q13 minimum ceiling plus the largest recovery
    duration; about 14 days, exact value derived from those ceilings in the spec pass. An end beyond
    the horizon reads as "ongoing, ends after the horizon".
  - Calendar categories `planned_absence` and `guest_stay` are core-reserved names; keywords are
    administrator-defined with suggested defaults per language; two separate classifiers on the same
    calendar, so both facts can be true at once.
  - Layer 5 `CalendarPlanBinding` is removed; Layer 2 calendar reads gain a bounded horizon reusing
    Layer 0 `CalendarViewRequirement`.
- **D4. Resolved 2026-10-19:** a guest stay or planned absence is declared only in the Heima panel
  (backend-checked: residents and administrators). No HA `switch`: any HA user, guests included,
  could flip it. Read-only HA entities expose `household.guest_stay` and
  `household.planned_absence` (end as attribute) for dashboards and user automations. During a stay,
  the declared guest rooms become the default control scope (Layer 8 §9.11) of the guest-room
  tablet and guest accounts: the whole map is visible, controls are offered only for those rooms;
  an administrator can still change the scope. The scope stays presentational (invariant 5). `presence@casa` and `occupancy@casa` are also
  exposed as read-only HA entities (HA already shows `person.*` to every user).
- **D5. Resolved 2026-10-19:** option (a). "Resident" is used only for the household role. The
  "anyone reading Heima" sense (resident-visible, resident text, resident-facing, resident wording)
  is renamed to a neutral term (user-visible, user text, user-facing). Layer 8 text splits into two
  registers: resident text (plain language) and public text (sanitized, for guests and devices,
  §7).
- **D6. Resolved 2026-10-19:** "how" is separated from "who".
  - `HoldOrigin` and the channel-state origin become `manual | external_automation |
    external_integration | unknown` (plus `initial`/`heima` for channel state), with the existing
    proof classes.
  - "Who" is a separate coarse field, never an identity: household role and admin flag for
    authenticated commands, no actor for an approved physical control.
  - One event `actuator.manual_control` replaces `actuator.resident_control`, emitted for every
    verified manual control with that field; Layer 5 `resident_manual_override` becomes
    `manual_override`.
  - Holds apply to every manual control. Layer 3 accepts as resident evidence only manual controls
    with role `resident` or from a physical control, excluding §5.1 and §5.2 periods.
  - Explanations say "changed manually"; residents also see "by a guest" or "from the tablet";
    guests and devices never see who.
- **D7. Resolved 2026-10-19:** physical learning (thermal absence cohorts, passive drift) delimits
  empty-house periods with `occupancy.departure`/`occupancy.return`; `presence.*` serves household
  consumers (comfort-trajectory end, departure/return notifications). Invariant 8 applied to
  learning.
- **D8. Resolved 2026-10-19:** behavior vs physical is classified per learner instance from its
  declared features, never by an administrator: any person-related feature (occupancy, `presence`,
  activity, manual control) makes it behavior learning. Behavior instances exclude §5.1 periods and,
  for guest rooms, §5.2 periods from training, and raise no findings during them. Physical instances
  are unchanged. The rule applies to every learner, so invariant 4 is checkable.
