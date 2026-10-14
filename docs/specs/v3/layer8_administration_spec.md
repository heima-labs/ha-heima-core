# Heima v3 - Layer 8: Administration and Resident Surface

**Status:** Defined V3 administration contract, approved 2026-10-13. Not implemented.
**Open corrections:** none.

**Layer:** 8 of 8. Presents and edits what Layers 0–6 define: Layer 0's composed configuration
generation, configuration history, response ingress, committed-state observers and diagnostics;
Layer 1's places and topology; Layer 2's registries; Layer 3's learning definitions and findings;
Layer 4's semantic resolver definitions; Layer 5's Reactions, proposals, governance commands and
decision records; Layer 6's recipients, notification history and request answers. It implements the
Layer-8 decisions L8-C1 to L8-C9 first recorded in `docs/v3_backlog.md` ("Layer 8 specification
decisions"); this spec now owns them. Upstream contracts introduced for it: CA4-78 (configuration
history), CA4-79 (decision record), CA4-80 (derived observer subscriptions), CA4-82 (owner changes
handed to Layer 8), CA4-83 (`Room` registry), CA4-84 (opening names), CA4-85 (Reaction names).

## 1. Purpose

Layer 8 is how people see and govern Heima. It must make the house's state, Heima's decisions and
their reasons clear to residents, and make every configuration, review and authority decision
complete, safe and explainable for administrators — through one surface, in the user's language,
without ever becoming a second source of truth.

## 2. Scope and boundaries

Layer 8 owns:

- the single Heima panel and its role-based content (§3, §4);
- the session change set, its preview and its application (§6);
- the history timeline and restore (§7);
- the "Why?" explanation views (§8);
- the house map and its presentation data (§9);
- the HA entities Heima publishes (§10);
- the guided first start (§11);
- the translation resources and glossary of user-facing text (§12).

Layer 8 does not own any configuration meaning, validation, authority rule, decision or fact. It
sends typed commands to the owning layer and renders typed results; it never writes another
layer's store, never evaluates a guard or a policy itself, and never runs in an evaluation cycle.

## 3. Core principles

- **One surface, one source of truth.** Every Heima configuration, review and diagnostic lives in
  one panel; the HA config flow only creates the integration (L8-C1). The panel shows what the
  owning layers hold; it keeps no parallel copy that could diverge.
- **Authority is enforced in the backend.** The UI hides what a role cannot use; every command is
  checked server-side against the authenticated HA user (§4).
- **Every object shows its state and its reason.** Status is never shown without the "why" (§8).
- **Configuration changes are previewed and atomic.** No intermediate state invalidates a
  dependent (§6).
- **Nothing hard-coded for one language.** All user-facing text comes from translation resources
  (§12).
- **Never in the hot path.** Panel reads use the in-memory current index, committed-state
  observers or slow-path history queries; commands are slow-path operations. Nothing the panel does
  delays an evaluation cycle.

## 4. Roles and access

```python
PanelRole = Literal["administrator", "resident"]

@dataclass(frozen=True)
class PanelPrincipal:
    ha_user_id: str
    roles: frozenset[PanelRole]
    recipient_id: str | None          # Layer 6 recipient linked through ha_user_id
    consent_authority: bool           # member of HouseholdConsentAuthority (Layer 5 §7.1.1)
```

The principal is resolved by the backend for every request from the HA-authenticated user, never
from client data:

- `administrator` — the HA user is an HA administrator;
- `resident` — the HA user is linked to a Layer-6 recipient or is a `HouseholdConsentAuthority`
  actor.

One person may hold both roles. An HA user with neither role sees only a page saying Heima is not
set up for them. The panel is registered once in the HA sidebar and visible to non-administrator
users; content and commands depend on the roles. Every command declares the roles it accepts, and
the backend rejects any other caller before reaching the owning layer. Layer 5 and Layer 0 still
apply their own checks (for example consent authority, ingress verification).

## 5. Navigation (L8-C3)

Sections are organized by the user's question, not by layer.

| Section | Role | Question | Content |
|---|---|---|---|
| Overview | both | What is happening and what must I do? | House map (§9), automations active or blocked with reason, items to do |
| House | admin | How is the house made? | Rooms (`enclosure`), openings (`other_side`), topology, zones and zone roles (Layer 1/2) |
| Devices | admin | What does Heima see and command? | Sensors with interpretations, Actuators, fusion rules and formulas (Layer 2) |
| Understanding | admin | How does Heima understand the situation? | Semantic resolver definitions: occupancy, presence, activity (Layer 4) |
| Automations | admin | What does Heima do, and why? | Reactions (state, decisions, history), proposals, artifact adoption, consent authority (Layer 5) |
| Learning | admin | What is it learning? | Learning definitions and family enablement, artifacts, findings (Layer 3) |
| Notifications | admin | Who receives what? | Recipients, family options, notification history (Layer 6) |
| System | admin | Is Heima healthy? | Health, diagnostics, holds (read-only), recovery, history (§7) |
| To do | resident | What do I need to answer? | Consent requests, recovery confirmations, advisories with feedback, including requests delivered without buttons |
| Automations | resident | What do automations do for me? | Read-only state and decisions with reasons; own consents with revoke |
| Notifications | resident | What did Heima tell me? | Notifications addressed to the resident's audiences (Layer 6 records audiences, not per-person deliveries) |

The resident Overview shows the house map and what Heima is doing, in plain language and without
technical identifiers. Every configuration section shows the pending-changes bar (§6).

## 6. Editing configuration (L8-C4)

### 6.1 Two kinds of action

- **Configuration edits** are Layer 0 §4.7 mutations: adding, changing or removing any Layer-1/2
  place or registry object, a learning definition, a semantic resolver definition, a Reaction
  configuration (including descriptor-specific preparation inputs such as the comfort-trajectory
  prerequisite generation), Layer-6 recipients and family options. They enter the session change
  set. A learner-origin Reaction's configuration is not editable from the panel (Layer 5 §4.2): it
  changes only through a new reviewed proposal; the panel offers disablement and shows why. Any
  Reaction, learner-origin included, can be removed (Layer 5 §4.2). Any
  Reaction can be renamed: `display_name` is catalog metadata, unique across Reactions, and a
  rename never creates a configuration generation (Layer 5 §4.2).
- **Immediate actions** are governance or answer commands that are not configuration mutations:
  promotion, disablement, consent grant or revoke, consent-authority changes, proposal review,
  artifact adoption mode, answers to requests, finding acknowledgement, house-map layout edits.
  They take effect at once after a confirmation dialog that states their consequence, and never
  enter the change set. Accepting a learned proposal is the one immediate action that creates
  configuration: it may name the new Reaction and commits it as one composed generation with an
  empty impact record (Layer 5 §4.1); an open change set is then rebased (§6.4).

### 6.2 Session change set

```python
EditOperation = Literal["add", "replace", "remove"]

@dataclass(frozen=True)
class ConfigurationEdit:
    owner_layer: Literal["layer2", "layer3", "layer4", "layer5", "layer6"]
    object_kind: str                  # closed per owning layer, e.g. "sensor", "zone", "reaction"
    object_id: str
    operation: EditOperation
    expected_fingerprint: str | None  # the object's definition fingerprint the edit was based on
    payload: CanonicalJsonObject | None   # complete typed definition for add/replace

@dataclass(frozen=True)
class ChangeSet:
    base_composed_generation_id: str
    edits: tuple[ConfigurationEdit, ...]  # at most one edit per object, canonical order
```

Editable object kinds, closed per owning layer (rooms, openings, zones and topology are staged with
the Layer-2 generation, Layer 0 §4.7):

| `owner_layer` | `object_kind` |
|---|---|
| `layer2` | `room`, `opening`, `zone`, `zone_role_binding`, `sensor`, `fusion_rule`, `actuator` |
| `layer3` | `learning_definition` (including its family enabled state) |
| `layer4` | `semantic_resolver_definition` |
| `layer5` | `reaction` (admin-direct configuration; `display_name` or removal for any Reaction), `guard_profile`, `comfort_trajectory_prerequisite` |
| `layer6` | `recipient`, `family_options` |

`expected_fingerprint` is the SHA-256 of the RFC-8785 canonical definition of that object in the
base generation, computed by Layer 8 itself, so every kind has one without an owner-specific
fingerprint; `None` exactly for `add`.

The change set lives in the administrator's browser session; it is not persisted or shared, and
leaving the page warns before losing it. Each edit is validated immediately by the owning layer's
staging validator and its errors are shown next to the field. Editing the same object again
replaces its edit.

### 6.3 Preview

`preview_change_set(change_set)` asks Layer 0 to stage the candidate composition (§4.7) and returns:

```python
@dataclass(frozen=True)
class ChangePreview:
    base_composed_generation_id: str
    changes: tuple[ObjectDiff, ...]       # field-level old/new values per edited object
    impact: ImpactRecord                  # Layer 0 §4.7 canonical record
    impact_fingerprint: str
    errors: tuple[StagingError, ...]      # blocking, each with its object reference
```

The page shows three blocks: what changes, effects on the rest of the house (breaking and
semantic-only entries in plain language, each linked; for example "this automation returns to
trial and needs promotion and consent again"), and blocking errors. Preview is a slow-path
staging run; it never mutates anything.

### 6.4 Apply

`apply_change_set(change_set, impact_fingerprint, operation_id)` commits through Layer 0 §4.7 with
the base generation and the reviewed fingerprint (none needed when the impact record is empty).
If the active generation changed meanwhile, Layer 0 rejects it without mutation; Layer 8 rebases
the edits on the new base — an edit whose `expected_fingerprint` no longer matches is a conflict
the administrator resolves field by field — and shows the preview again. An exact retry with the
same `operation_id` returns the first result.

## 7. History and restore (L8-C4a)

System → History is one timeline built only from existing durable records:

| Entry | Source |
|---|---|
| Configuration commit | Layer 0 manifest and layer generation records (retained indefinitely, Layer 0 §4.7) |
| Governance action | Layer 5 authority, consent, consent-authority, adoption and proposal-review transitions |
| System commit | Layer 0 bootstrap manifest after a code upgrade |

Each configuration entry shows who, when, the field-level diff against the previous generation and
the effects that were confirmed. Filters: section, object, person. Administrators see the actor's
HA display name; residents see names only for their own actions and "an administrator" otherwise. Every object page shows its own
slice.

**Restore** never applies anything. It loads into the session change set the edits that turn the
current configuration into the chosen generation (whole generation, or one object from its page),
and any entry can be removed before preview. The result is a new generation. Restore covers
configuration only: a restored Reaction returns as a new generation of the same Reaction root in
`notification_only` (Layer 5 never inherits promotion, consent or adoption), and learned artifacts,
facts and history are untouched. A removed object returns with its original identity when that
identity is free; a removed Reaction's id is never given to another Reaction (Layer 5 §4.2). The
current core validates the restored configuration; anything no longer valid is a preview error.

## 8. Explanations (L8-C5)

Every object (room, actuator, automation, notification) has a "Why?" view answering "why is it in
this state" or "why did it act, or not act, at time T".

```python
@dataclass(frozen=True)
class ExplanationNode:
    kind: Literal["effect", "decision", "trigger", "semantic_conclusion", "observation",
                  "configuration", "authority", "data_unavailable"]
    reference: str                    # typed id of the fact, record or generation it renders
    at: EvidenceInstant | None
    summary_key: str                  # translation key of the rendered sentence (§12)
    summary_args: CanonicalJsonObject # closed values and resolved names only
```

The chain is built on demand, by a slow-path query, from:

- `ApplyStep` sources, `actuator.target_lifecycle` and follow-up facts for an effect;
- the Reaction's `reaction.decision.<digest>` state at that time (outcome, reasons, failed guard
  capabilities, admission), reconstructed as of T like any state fact (Layer 5 §5.2, Layer 0 §4.0);
- the trigger's own state history, to detail a `not_triggered` decision ("nothing fired");
- semantic facts with their evidence and the `correlation_id` of the same cycle for conclusions
  and their inputs;
- the configuration generation active at that time (Layer 0 §4.7) for thresholds and bindings;
- the history timeline for authority (disabled, in trial, awaiting consent).

When the needed facts are beyond retention, the chain ends with a `data_unavailable` node; it
never guesses. Administrators see the full chain with codes and links; residents see the same chain
rendered in plain language, without identifiers.

## 9. House map (L8-C3a)

The Overview shows a native map, never a third-party card.

1. **Automatic schematic.** Rooms from `Topology` laid out by their connections, one tab per
   floor, exterior rooms visually distinct.
2. **Optional real plan.** An administrator uploads an image or SVG per floor and places each room
   (a polygon, or an SVG element) and each device on it.

```python
@dataclass(frozen=True)
class MapPlacement:
    target_kind: Literal["room", "actuator", "sensor", "opening"]
    target_id: str                    # Heima identity, never an HA entity id
    floor_id: str
    shape: CanonicalJsonObject        # polygon points or an SVG element id, normalized coordinates

@dataclass(frozen=True)
class HouseMapLayout:
    floor_plans: Mapping[str, str]    # floor_id -> stored plan asset id
    placements: tuple[MapPlacement, ...]
```

Plans are stored in HA's storage directory, at most 2 MiB per floor, and an SVG is sanitized (no
scripts, no external references) before storage. The layout is Layer-8 presentation data stored
with HA's storage helper, not Layer-1 `Topology`
and not part of the composed generation; editing it is an immediate action. A placement whose
target no longer exists is hidden and listed for cleanup; a renamed object updates on the map.

Overlays: room occupancy and casa presence, light and Actuator channel state, opening state where a
registered Sensor or Actuator channel reports it,
automations active or blocked with their reason (§8 on click). The map updates live through
Layer 0 committed-state observers (§10.3); it never polls.

## 10. HA entities published by Heima (L8-C6)

### 10.1 Contract

These are new entities created by Heima for its conclusions, distinct from the user's own entities
that Heima reads (Sensors) and commands (Actuators). They are read-only: Heima publishes no
`select`, `switch` or `number`.

| Entity | HA platform / class | Source | Default |
|---|---|---|---|
| Casa presence | `binary_sensor` / presence | Layer 4 `presence@casa` | enabled |
| Room occupancy (one per room with an occupancy resolver) | `binary_sensor` / occupancy | Layer 4 room occupancy | enabled |
| Activity (one per activity resolver: scope × `activity_id`) | `binary_sensor` | Layer 4 `activity.<activity_id>` | enabled |
| Automation state (one per Reaction) | `sensor` / enum: `automatic`, `trial`, `awaiting_consent`, `blocked`, `invalid` | Layer 5 mode and current block | diagnostic, disabled |
| Pending items | `sensor` / count, attributes `proposals`, `requests` | Layer 5 and Layer 0 (§10.3) | enabled |
| Heima health | `sensor` / enum: `ok`, `degraded`, `error` | Layer 0 health | enabled |

### 10.2 Rules

- Unique ids derive from Heima identities (room id, resolver id, reaction id); names are the
  effective names of Layer 2 §2.7 combined through translation keys, so renames propagate. An activity entity's name combines its
  scope name with the translated activity label.
- A fact-backed entity is `unavailable` whenever its Heima fact is unavailable, with one declared
  exception: an activity entity is `on` when its claim is `active` and `off` otherwise, including
  `available=False`. Activities are independent claims (Layer 4 §3.1), so each has its own entity
  and none is merged into a per-room value. A `positive_only` profile publishes `available=False`
  for "no positive evidence" (Layer 4 §9.4); `off` therefore means "not detected now", the HA
  convention for detection sensors, never "proven inactive". A future `bipolar` profile declares its
  own mapping when reviewed; a projection-backed
  entity (§10.3) is `unavailable` until its projection is rebuilt after start. None shows a stale
  value.
- Attributes contain closed fields only (for example the block reason code), never free text or a
  person's identity. States and attributes use HA entity translations (§12).
- An entity is created when its object is committed and removed from HA's entity registry when
  its object is removed.
- No per-person entity: HA's `person.*` exists and V3 has no per-person state.

### 10.3 Feeding

Entities and map overlays that mirror a state fact (presence, occupancy, activity, Actuator
channel and opening state) are fed by Layer 0 committed-state observers (§4.8), whose subscriptions
Layer 8 derives from the active composed generation and re-declares at each generation swap.
Updates are asynchronous after the cycle commit and coalesced; nothing polls and nothing runs in
the cycle.

Automation state, pending items and Heima health are not state facts. Layer 8 keeps them in
in-memory projections fed by typed changes their owners already produce off the hot path, handed
read-only to Layer 8 as an additional consumer:

| Projection | Inputs |
|---|---|
| Automation state | Layer 5 authority transitions (mode), Layer-6 availability tracker episodes (block and reason) |
| Pending items | Layer 5 proposal-review, consent and advisory occurrences, Layer 0 recovery-confirmation occurrences |
| Heima health | Layer 0 health snapshots and degradation-diagnostic changes |

Health is `error` when no committed manifest is active or persistence writes are failing,
`degraded` when any degradation diagnostic is active, `ok` otherwise. At process start every
projection is rebuilt from the owners' current state (authority projection, open proposals and
requests, current diagnostics), so nothing is persisted and nothing polls.

## 11. First start (L8-C8)

The config flow creates the integration only. On first opening, the panel runs a guided procedure:
rooms → topology → devices → people and notifications → suggested automations. Suggested
automations are only the descriptors whose staged prerequisites are met by what is configured; each
opens an ordinary direct-staging form, and nothing is created without apply. Each step is an
ordinary change set with its preview. Applied steps stay applied; on return the procedure derives
its progress from what is configured, so only the unapplied edits of the current step can be lost.

V2 cutover follows Layer 2 §1.1 unchanged: nothing is imported, and the panel never reads,
displays or interprets a V2 export.

## 12. Languages and terminology (L8-C7)

- No user-facing string in any language is hard-coded. Panel text, Layer-6 templates, HA entity
  names and states, explanation sentences and error messages use translation keys.
- English is the source locale. Each locale is a resource file; Initial V3 ships `en` and `it`.
  A missing locale or key falls back to `en`. A new country needs a resource file, not code.
- The panel follows the HA user's language; notifications follow §8.2 of Layer 6.
- Dates, times, numbers and units follow the viewer's locale and HA's unit system; instants are
  converted from UTC only here (Layer 0 §3).
- One core glossary defines each canonical term once as a translation key ("automation", "trial"
  for `notification_only`, "block" for a suppression, …), shared by panel, templates, entities and
  user documentation. Internal concepts (generation, binding, envelope) never appear in resident
  views and appear in administrator views only with their glossary explanation.
- A test fails if a user-facing literal string exists outside the translation resources.

## 13. Backend contract

**Frontend technology (L8-C9).** The panel is a Lit web component, the same base as HA's own
frontend, registered as an HA custom panel and served by the integration with its build included
in the package. It loads no library from an external CDN and does not reuse the V2 panel code.

- The panel talks to Heima through HA's websocket API with typed commands and queries; every
  message carries the authenticated HA user, which §4 resolves.
- Queries: current state from the in-memory current index; history, timelines, diffs and
  explanations as bounded slow-path queries with explicit time windows and pagination.
- Commands: configuration (§6) through Layer 0 §4.7; governance through Layer 5's common command
  surface (Layer 5 §4.2), whose typed `GovernanceCommandResult` and closed codes Layer 8 renders;
  answers through Layer 0's response ingress (§5.1.3) with the HA user, exactly like a button press;
  finding acknowledgement as Layer-8 view state (Layer 3 §6.1.1); house-map layout (§9).
- Every command carries an `operation_id`; exact retries return the first result.

Message catalog (websocket type prefix `heima/v3/`); "admin" and "resident" are the §4 roles:

| Message | Kind | Roles | Owner path |
|---|---|---|---|
| `session` | query | any HA user | §4 principal and roles |
| `overview` | query | admin, resident | map, automation state, pending items (role-filtered) |
| `objects/list`, `objects/get` | query | admin | active generation, per `object_kind` |
| `change_set/validate_edit` | query | admin | owning layer's staging validator |
| `change_set/preview` | query | admin | Layer 0 §4.7 staging |
| `change_set/apply` | command | admin | Layer 0 §4.7 commit |
| `history/list`, `history/diff` | query | admin | Layer 0 manifests and generations, Layer 5 transitions |
| `history/restore` | query | admin | builds a change set (§7), applies nothing |
| `explain` | query | admin, resident | §8 (resident rendering for residents) |
| `notifications/history` | query | admin, resident | Layer 6 facts, audience-filtered for residents |
| `todo` | query | resident | pending-items projection for the resident's audiences |
| `requests/answer` | command | admin, resident (the owner's declared categories and own checks apply) | Layer 0 response ingress |
| `reactions/promote`, `reactions/disable`, `reactions/set_adoption_mode` | command | admin | Layer 5 §4.2 |
| `reactions/set_consent` | command | resident with consent authority | Layer 5 §4.2 |
| `consent_authority/stage` | command | admin | Layer 5 §4.2 |
| `proposals/review` | command | admin | Layer 5 §4.2 |
| `findings/acknowledge` | command | admin | Layer-8 view state |
| `map/save_layout`, `map/upload_plan` | command | admin | §9 |
| `diagnostics` | query | admin | §14 |
| `subscribe` | subscription | admin, resident | live updates of §10.3, role-filtered |
- Live updates to an open panel come from committed-state observers and the in-memory projections
  of §10.3, pushed over an HA websocket subscription; never polling.

## 14. Diagnostics

The System section renders, read-only, the diagnostics every layer already exposes (Layer 0 §10
and each layer's own): timing, observation continuity, recovery, holds (no manual release exists),
retry queue, committed-state observers, generation and impact history, learning and artifact state,
notification delivery. It also shows Layer 8's own counters: rejected commands by reason, preview
and apply outcomes, rebases and conflicts, published entities and their availability.

## 15. Decisions taken on the draft (2026-10-13)

1. **Users with no role** see only "Heima is not set up for you" (§4).
2. **Map plan assets** are stored in HA's storage directory, at most 2 MiB per floor; an SVG is
   sanitized (no scripts, no external references) before storage (§9).
3. **History actor names:** administrators see the actor's HA display name; residents see names
   only for their own actions and "an administrator" otherwise (§7).
4. **Suggested automations at first start** list only descriptors whose staged prerequisites are
   met by what is configured; each opens an ordinary direct-staging form, and nothing is created
   without the administrator's apply (§11).
5. **Non-fact entities** are fed by owner-produced typed changes into in-memory projections
   (§10.3); the owners name Layer 8 as a consumer (CA4-82).

## 16. Initial acceptance criteria

- A resident cannot call any administrator command even by crafting a request; an administrator
  without consent authority cannot grant consent; both are rejected before the owning layer.
- Replacing a sensor used by an automatic Reaction in one change set (remove, add, rebind) applies
  with no breaking effect and keeps the Reaction automatic; applying the removal alone shows a
  breaking effect that would invalidate the Reaction, losing promotion and consent.
- A change set based on generation N applied after another commit made N+1 is rejected without
  mutation, rebased, re-previewed; a conflicting field edit is shown for resolution.
- Restoring a generation that contained a since-removed Reaction proposes recreating it in
  `notification_only`; removing that entry from the set leaves the Reaction absent.
- "Why did the awning not lower at 15:00?" returns the Reaction's decision state as of 15:00, with
  the trigger's state history when it was `not_triggered`, the generation thresholds of that time,
  and `data_unavailable` beyond retention.
- The house map shows occupancy within one committed cycle of a change, with no polling; a room
  removed from configuration disappears from the map and its entity from HA.
- Every published entity is read-only, `unavailable` when its fact is unavailable (an activity
  entity is `off` instead), translated, and carries no free text or person identity. A room where
  `relax` and `working` are both active shows two activity entities `on`; a cooking entity is `off`,
  never `unavailable`, while the hob is off or unreadable.
- No user-facing literal string exists outside translation resources; switching the HA user's
  language to an unshipped locale shows English.
- No panel query or command delays an evaluation cycle.
