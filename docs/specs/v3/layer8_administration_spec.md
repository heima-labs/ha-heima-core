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
  checked server-side against the authenticated HA user (§4). The one exception is device control
  from the house map, which is an ordinary HA service call under HA's own permissions (§9.8).
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

One person may hold both roles. The house map is open to every authenticated HA user, with or
without a role (CA4-113): HA already shows every entity state to every user, so the map reveals
little beyond the automations' short reasons. An HA user with neither role sees the Overview with
the map only, in resident wording, without links to explanations, items to do or other sections.
The panel is registered once in the HA sidebar and visible to non-administrator users; content and
commands depend on the roles. Every command declares the roles it accepts, and
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
| Learning | admin | What is it learning? | Learning definitions and family enablement, artifacts, findings, live-signal promotion and adoption (Layer 3) |
| Notifications | admin | Who receives what? | Recipients, family options, notification history (Layer 6) |
| System | admin | Is Heima healthy? | Health, diagnostics, holds (read-only), recovery, history (§7) |
| To do | resident | What do I need to answer? | Consent requests, recovery confirmations, advisories with feedback, including requests delivered without buttons |
| Automations | resident | What do automations do for me? | Read-only state and decisions with reasons; own consents with revoke |
| Notifications | resident | What did Heima tell me? | Notifications addressed to the resident's audiences (Layer 6 records audiences, not per-person deliveries) |

The resident Overview shows the house map and what Heima is doing, in plain language and without
technical identifiers. Every configuration section shows the pending-changes bar (§6).

### 5.1 Panel addresses (CA4-106)

Every section and object has a stable address, so notifications, explanations and other objects
can link to exactly what they concern. The scheme is a public contract that other layers use
without calling Layer 8:

```text
/heima/<section>[/<type>[/<id>]][?at=<EvidenceInstant>]
```

| `section` | `type` → `id` |
|---|---|
| `overview` | none |
| `todo` | `request` → Layer 0 response-ingress `request_id` |
| `automations` | `reaction` → `reaction_id`; `proposal` → `proposal_id` |
| `house` | `room` → `room_id`; `opening` → `opening_id`; `zone` → `zone_id`; `map` (no id) |
| `devices` | `sensor` → `sensor_id`; `actuator` → `actuator_id`; `fusion_rule` → `fusion_id` |
| `understanding` | `resolver` → `resolver_id` |
| `learning` | `definition` → learning definition id |
| `notifications` | `item` → Layer 6 item tag |
| `system` | `history` → `composed_generation_id`; `health` (no id) |

- Sections and types are closed English tokens, independent of the viewer's language. A `type`
  without `id` opens that list (for example `/heima/automations/proposal`).
- Ids are Heima's stable identities, percent-encoded; never a name or a Home Assistant `entity_id`,
  so an address carries no personal data and survives a rename. A `request_id` in an address grants
  nothing: answering still goes through the authenticated ingress (Layer 0 §5.1.3).
- `?at=` opens the object's "Why?" view at that instant (§8). Where it is meaningless it is ignored.
- `todo` opens the resident To do section; for an administrator it opens the Overview's items to do
  with that request selected.
- An address whose object no longer exists, or which the viewer's roles cannot see, opens its
  section with the same "This item is no longer available" notice in both cases, so it never
  reveals whether a hidden object exists. Authorization stays in the backend (§4); an unknown
  section or type opens the Overview.

### 5.2 Panel states (CA4-108)

The panel always says whether what it shows is live and whether Heima is working. The states come
from the connection itself, the health projection and the Layer 0 recovery state (§10.3); nothing
polls.

| Situation | Administrator | Resident |
|---|---|---|
| Backend unreachable (integration not loaded, HA restarting, websocket lost on load) | Full-page "Heima is not reachable"; retries on reconnection | Same |
| Live subscription interrupted while open | Last values stay, dimmed, with "updated at <time>"; resynchronized on reconnection | Same |
| `startup_recovery`, before the first committed cycle | Banner "Heima is starting"; map without live overlays | Same |
| No active configuration yet (first start not done) | Empty Overview with "Start setup" (§11) | "Heima is not set up yet; ask an administrator" |
| `power_recovery` or `degraded_recovery` | Banner naming the recovery kind, the pending recovery confirmations and a link to System | "Heima is resuming after an interruption"; confirmations are already in To do |
| Health `degraded` | Banner listing the active degradation diagnostics, linked to System | No banner; affected objects already show as unavailable |
| Health `error` | Banner with the cause, linked to System | "Heima has a problem and may not act as expected" |

At most one banner shows: the most severe, ordered error, unreachable states, recovery, starting,
degraded. `recovery_settling` and `normal` show none. Administrators are also notified of the
error state and its end by the Layer-6 `system.health` notification, which links to
`/heima/system/health` (CA4-109). Resident text is plain language without codes
or identifiers (§12). Every situation's full detail stays in System (§14). A user with no role
(§4) and the map card (§9.14) show the resident text.

### 5.3 Phones and accessibility (CA4-111)

The panel is fully usable from the HA companion app on a phone and with assistive technology. It
reuses HA's frontend components, themes and layout breakpoints wherever they exist.

- **Width.** Every section works from 360 CSS pixels wide without horizontal page scrolling; only
  wide tables and the map scroll inside their own frame. Below HA's narrow breakpoint the section
  navigation collapses into a menu, tables become card lists, forms use one column and the
  pending-changes bar stays fixed at the bottom.
- **Touch.** Interactive targets are at least 44×44 CSS pixels. Every function, the map editor
  included, works by touch.
- **History.** Every view is an address (§5.1), so the phone's back gesture returns to the previous
  view instead of leaving the panel.
- **Standard.** WCAG 2.2 level AA is the target:
  - the whole panel is operable by keyboard, with a visible focus and a logical order;
  - controls have accessible roles and names; live updates are announced politely and grouped, so a
    screen reader is not interrupted at every cycle;
  - color never carries information alone: occupancy, states and severities also have text, an icon
    or a pattern; contrast holds in light and dark HA themes;
  - text scales to 200% without loss of content or function;
  - animation stops under `prefers-reduced-motion`.
- **Direction.** Styles use logical properties (start/end), so a future right-to-left locale needs
  only its resource file (§12).
- **Map.** The house map has an equivalent list view (§9.12) and touch, keyboard and button
  navigation (§9.13).

## 6. Editing configuration (L8-C4)

### 6.1 Two kinds of action

- **Configuration edits** are Layer 0 §4.7 mutations: adding, changing or removing any Layer-1/2
  place or registry object, a learning definition, a semantic resolver definition, a Reaction
  configuration (including descriptor-specific preparation inputs such as the comfort-trajectory
  prerequisite generation), Layer-6 recipients and family options. They enter the session change
  set. A learner-origin Reaction's configuration is not editable from the panel (Layer 5 §4.2): it
  changes only through a new reviewed proposal; the panel offers disablement and shows why. Any
  Reaction, learner-origin included, can be removed (Layer 5 §4.2), and an invalid one can be
  revalidated: the panel's "revalidate" action loads a `replace` with its unchanged configuration
  into the change set (Layer 5 §4.2). Any
  Reaction can be renamed: `display_name` is catalog metadata, unique across Reactions, and a
  rename never creates a configuration generation (Layer 5 §4.2).
- **Immediate actions** are governance or answer commands that are not configuration mutations:
  promotion, disablement, consent grant or revoke, consent-authority changes, proposal review,
  artifact adoption mode, Layer-3 live-signal promotion and signal-artifact adoption (Layer 3 §4.9),
  answers to requests, finding acknowledgement, house-map layout saves (§9.9: presentation only,
  so no consequence dialog).
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
| `layer5` | `reaction` (admin-direct configuration; `display_name`, removal or unchanged-configuration revalidation for any Reaction), `guard_profile`, `comfort_trajectory_prerequisite` |
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

### 6.5 Configuration suggestions (CA4-107)

Lower layers define what Heima may suggest; Layer 8 shows the suggestions where they apply and turns
an accepted one into an ordinary edit. The sources form a closed list:

| Suggestion | Source | Shown in |
|---|---|---|
| A `Room` for an HA area not yet linked: name from the area, floor from the area's HA floor level when it has one | Layer 2 §2.6 | House |
| A `Zone` from an HA label on areas, or from the rooms of one floor | Layer 1 §6, §7.1 | House |
| A `Sensor` from an `EnvironmentalDiscoveryCandidate` (`auto_compatible` or `review_required`) | Layer 2 §3.4 | Devices, under the room of its suggested location |
| Another role of a registered device: an unregistered entity with the same HA `device_id` | Layer 2 §3 (`device_id`) | Devices, on that device |

```python
SuggestionSource = Literal["ha_area", "ha_label", "floor", "discovery_entity", "device_sibling"]

@dataclass(frozen=True)
class SuggestionKey:
    source: SuggestionSource
    source_id: str      # area id, label id, floor number, entity id plus read path, or device id plus entity id
```

- **Computed on demand.** `suggestions/list` is a slow-path query over the active generation and
  HA's area, floor, label, device and entity registries and current state objects. Suggestions are
  never stored, never evaluated in a cycle and never reach a lower layer as data.
- **Accepting** opens the ordinary add form, prefilled. Every `required_admin_decisions` item of a
  discovery candidate, and every field the source cannot determine (a room's `enclosure`, a floor
  the area does not give, a Sensor's indoor or outdoor meaning, its opening relation), is marked and
  mandatory. The result is an `add` edit in the change set, validated, previewed and applied like
  any other (§6.2–§6.4); nothing is created without apply.
- **Multiple selection** is offered only for rooms from areas, whose only decisions are floor and
  enclosure; each Sensor needs its own semantic decisions.
- **Dismissing** records the `SuggestionKey` as Layer-8 view state, like finding acknowledgement:
  installation-wide, stored with HA's storage helper, never part of the composed generation.
  "Show dismissed" lists them and restores any. A key whose source no longer exists is dropped.
  A suggestion that the configuration now satisfies (the area is linked, the entity is registered)
  disappears without being dismissed.
- **First start (§11)** draws on the same suggestions for its rooms, topology and devices steps.
- Automations are not suggested here: suggested automations remain Layer 5 proposals (Automations
  section) and the first-start descriptor list (§11).

## 7. History and restore (L8-C4a)

System → History is one timeline built only from existing durable records:

| Entry | Source |
|---|---|
| Configuration commit | Layer 0 manifest and layer generation records (retained indefinitely, Layer 0 §4.7) |
| Governance action | Layer 5 authority, consent, consent-authority, adoption and proposal-review transitions; Layer 3 signal-artifact adoption transitions |
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

The Overview shows a native map, never a third-party card; the same map is also Heima's own
Lovelace card (§9.14). Initial V3 has one form of map: an
automatic schematic derived from the `Room` registry, `Topology` and the registered devices, which an
administrator can adjust. A real plan (an uploaded image or SVG) is not part of Initial V3 (CA4-103).

### 9.1 What the map shows

- **Floors.** One tab per distinct `Room.floor`, in ascending order, labelled from the floor number
  through translation keys.
- **Rooms.** Every `interior` room is a rectangular box of whole grid cells, from 1×1 to 4×3. An
  `exterior` room (terrace, garden) is a visually distinct strip outside the interior boxes (§9.3).
- **Openings.** Every `Opening` is a glyph on one side of its owner room's box: distinct glyphs for
  `door`, `window`, `door_window` and `passage` (a gap in the wall, without a leaf). Its side and
  position are derived (§9.5), never stored.
- **Connections between floors.** A `door` or `passage` to a room on another floor carries a floor
  badge (up or down, with the floor label). Tapping it switches to that floor and highlights the
  connected room.
- **Devices.** An `Actuator` with `opening_id` and a `Sensor` with `related_opening_id` are drawn on
  their opening. Other registered Actuators and Sensors are drawn inside their room's box, grouped by
  rendering kind with a count. Only Heima-registered devices appear; nothing else from HA.
- **Orientation.** One direction is at the top of the map for the whole installation (§9.4). A
  compass shows north; all text stays upright.

### 9.2 Layout data

```python
@dataclass(frozen=True)
class MapRoomPlacement:
    room_id: str          # an interior Room; its floor is Room.floor, never stored here
    x: int                # grid cell of the box's top-left corner, in map coordinates
    y: int                #   (x to the right, y downward)
    w: int                # 1..4 cells
    h: int                # 1..3 cells

@dataclass(frozen=True)
class HouseMapLayout:
    revision: int                                 # incremented by every save
    up: CompassOrientation | None                 # direction at the top; None follows §9.4's suggestion
    placements: tuple[MapRoomPlacement, ...]      # pinned rooms only, unique room_id
    unconnected_ok: tuple[str, ...] = ()          # room_ids whose "Not connected" check is dismissed
```

`CompassOrientation` is Layer 1's closed vocabulary. The layout is Layer-8 presentation data stored
with HA's storage helper. It is not `Topology`, not part of the composed generation, and drives no
behavior outside the panel. Openings and devices have no stored position. A placement whose room no
longer exists, is now `exterior`, or overlaps an earlier placement on the same floor (in `room_id`
code-point order) is ignored, listed as a map check (§9.6) and dropped at the next save. A room that
changes floor keeps its placement on the new floor under the same rule. A rename changes only the
label. An `unconnected_ok` entry for a room that no longer exists is dropped at the next save.

### 9.3 Automatic proposal

Every unpinned interior room receives a position from one deterministic rule. The same layout, up
direction, rooms, openings and enclosures always give the same map, independent of registry order.

1. **Map frame.** An opening's map orientation is its `orientation` rotated by the up direction in
   45° steps. Map sides are top, right, bottom and left.
2. **Preferred direction.** A room's preferred direction is the sum of the unit vectors of the map
   orientations of its openings for which Layer 1's `opening_faces_exterior` is true. A zero sum
   means no preference (a hallway, a windowless bathroom).
3. **Connections and width.** A room's degree is the number of distinct interior rooms on the same
   floor reached through its passable openings. A room of degree 5 or more is proposed
   `min(3, ceil(degree / 2))` cells wide, so that a hallway can touch its rooms; every other room is
   1×1.
4. **Floors.** Floors are proposed in ascending order, so every lower floor is already laid out when
   a higher one is proposed.
5. **Groups.** A floor's interior rooms form groups: rooms joined, directly or through other rooms,
   by passable openings on that floor. A room with no such opening is a group of its own (a garage
   reached only from outside). Groups are laid out one at a time: groups with a pinned room first,
   then by descending number of rooms, then by smallest `room_id`.
6. **Start.** In a group with pinned rooms, they keep their stored positions and the starting room is
   the pinned room of highest degree (ties by `room_id`). Otherwise the starting room is the group's
   room of highest degree (ties by `room_id`), placed at the origin.
7. **Order.** A group's unplaced rooms are taken breadth-first from its placed rooms (pinned ones in
   `room_id` order). A room's neighbors are visited by descending degree, then `room_id`.
8. **Position.** A candidate is any box touching an already placed box of the same group without
   overlapping any box of the floor. The candidate with the lowest cost wins. The cost increases
   with: the distance to each connected room on the same floor it does not touch; the distance from
   the cells of connected rooms on lower floors, so a staircase lines up across floors; the angle
   between its direction from the group's starting room and the room's preferred direction; its
   distance from that starting room; and the growth of the group's bounding box. Ties go to the
   smaller `y`, then the smaller `x`. The weights are core constants, frozen per core version and
   covered by fixture tests (§16).
9. **Separate groups.** A group without pinned rooms, other than the floor's first, is laid out on
   its own and then moved as one block beside the boxes already on the floor, with one empty cell
   between them. It goes on the side of the group's preferred direction (the sum of its rooms'
   preferred directions, by its dominant axis), or below when that sum is zero or the axes tie. It
   is aligned with the left edge (above or below) or the top edge (left or right) of the boxes
   already placed. Separation shows that no passage joins the groups; an administrator may still
   drag a box against another, which is an ordinary shared wall.
10. **Exterior rooms.** An exterior room is a strip outside the bounding box of the interior boxes,
   on the side most of its connecting openings face. A diagonal orientation counts for its top/bottom
   component, and ties go bottom, top, right, left. The strip spans the connected rooms' extent. An
   exterior room with no connecting opening sits below the interior boxes. Several strips on one
   side are ordered along it by the position of their connected rooms (left to right, top to
   bottom; ties by `room_id`); a strip that would overlap an earlier one moves one band further from
   the house. An exterior room connected on several sides (a balcony around a corner) is one strip
   on the side with most of its openings. Exterior strips are never pinned or dragged.

The proposal never moves a pinned room.

### 9.4 Up direction

The suggested up direction is the one among the eight `CompassOrientation` values that puts the most
oriented openings on a full side (a non-diagonal map orientation). Ties go to `north`, then clockwise.
A house whose facades face NE/SE/SW/NW is therefore drawn with `northeast` at the top without any
input. With `up=None` the map follows the suggestion, which updates when openings change. An
administrator can choose another direction in 45° steps or return to the suggestion. Changing the up
direction clears the floor placements, after a warning in the editor, because every opening changes
side. The compass and the sun direction rotate with it.

### 9.5 Opening placement

Derived at render time from the current boxes:

- A passable opening between two interior rooms whose boxes share a wall is centered on the shared
  segment.
- An opening to `outside` or to an exterior room, with an orientation, is placed on the side of its
  map orientation. For a diagonal, the side whose wall still has an exterior stretch is used,
  top/bottom first. It is placed on the longest stretch of that side not shared with another interior
  box. Without an orientation, it goes on the side with the longest exterior stretch (top, right,
  bottom, left on ties).
- A passable opening between rooms on the same floor whose boxes do not touch is placed on the side
  facing the other room, with a dashed connector to it.
- An opening to a room on another floor is placed on the side with the longest stretch not shared
  with another interior box (top, right, bottom, left on ties), with its floor badge and no
  connector.
- Several openings on the same stretch are spread evenly in `opening_id` order.

### 9.6 Map checks

Administrators see map checks in the editor and on the Overview. Map checks are presentation
diagnostics: they never change `Topology`, create a fact or block an apply.

- "Not adjacent": a passable opening drawn with a connector.
- "Faces another room": an oriented opening with an exterior side that has no exterior stretch.
- "Orientation missing": the floor has exterior-facing openings without `orientation`, so the map is
  approximate. It links to the opening in the House section, with the hint to read the direction on
  a phone compass while looking out, or on a north-up satellite map.
- "Placement ignored": a stored placement dropped by §9.2.
- "Not connected": an interior room with no passable opening to any other room, on any floor. It
  links to the room's openings in the House section. It is not an error (a garage reached only from
  outside is valid), so an administrator can dismiss it per room (`unconnected_ok`); it reappears
  if the room is recreated.

### 9.7 Overlays

Live state comes through Layer 0 committed-state observers (§10.3). The map never polls. Rendering
is keyed by an Actuator channel's `channel_kind` and a Sensor's `fact_type`, never by an HA domain
guessed from the entity. A kind with no map rendering shows HA's state icon for its entity. Colors
follow the HA theme, and animation stops under `prefers-reduced-motion`. Initial V3 renderings:

- **Room.** Occupancy fill from Layer 4 room occupancy (occupied, vacant, hatched when unavailable),
  activity badges, casa presence in the header.
- **Light.** A glow in the light's color and brightness when those facets are registered, otherwise
  on/off. The glow is stronger after dark.
- **Cover on an opening.** A band on the opening proportional to the closed fraction, marked while
  moving. An awning extends outside the wall in proportion to its extension.
- **Opening state.** A door leaf or window sash drawn open from the registered opening Sensor or
  Actuator channel.
- **Climate.** Current temperature, with heating or cooling marked.
- **Fan and media.** Spinning blades and a playback indicator.
- **Sun.** When the core solar-geometry Sensors are staged (Layer 2 §3.6) and the sun is above the
  horizon: a light patch through each exterior-facing window or door-window whose orientation is
  within 80° of the solar azimuth, attenuated by its cover and awning, plus a sun marker in the
  azimuth's direction. Without those Sensors there is no sun overlay; the map never reads `sun.sun`
  itself.
- **Automations.** A badge per room: active, blocked or held with the reason. A tap opens §8.

### 9.8 Device control from the map

The map is also a convenient control surface, built on Home Assistant's own controls:

- **Tap** toggles a light, fan or media device, and opens or closes a cover on a `window` or
  `door_window` opening.
- **Long press, secondary click or the details button** opens HA's standard more-info dialog for the
  entity.
- **Never on tap:** locks, covers on a `door` opening (garage door, gate), climate and every other
  kind open the more-info dialog only.

The panel calls the HA service through the frontend's HA connection **as the signed-in HA user**,
with HA's own permissions. This is the one panel action that does not go through Heima's backend.
It is neither a `heima/v3/` command nor a Heima `ApplyStep`, and no Heima authority or consent check
applies. It is an ordinary use of HA controls, not a Heima action: the apply plan remains the only
channel through which Heima acts on HA. Heima observes the resulting state like any other control
use (Layer 0 §6). If it diverges from a current Reaction target, the hold follows Layer 0 §6, and
the map shows the held automation with its §8 explanation. That explanation states only the origin
Layer 0 verified; it never claims more about who acted. Device control is unavailable in edit mode.

### 9.9 Editing the layout

Administrators edit in an explicit edit mode:

- drag a box to another free position, snapped to the grid;
- resize a box from its right edge, bottom edge or corner, from 1×1 up to 4×3;
- rotate the up direction by 45°, or return to the suggested direction;
- reset the current floor to the automatic proposal (clears its placements);
- undo the previous edit (Ctrl/⌘+Z included), at least 50 steps, for the current edit session;
- save or cancel.

A selected box also has buttons that move it by one cell and change its width or height by one
cell, so that every edit has a single-pointer alternative to dragging (§9.13).

A move or resize onto another box is refused. Edits stay local until **Save**, which sends the whole
layout in one `map/save_layout` command carrying the `revision` it was based on. Every room box
present at save becomes a placement. A save based on a stale revision is rejected without change,
and the editor reloads the current layout. Saving is an immediate action without a consequence
dialog, because it changes presentation only (§6.1). It never enters the change set and has no
impact preview. Undo is client-side and ends with the edit session.

### 9.10 Roles

Residents see the same map and overlays and may use §9.8 within their HA permissions. Text is in
plain language, without identifiers or reason codes, and with no edit mode and no map checks. A user
with no role (§4) sees the resident map; tapping an automation badge shows its short reason but opens
no explanation.
Administrators additionally see entity ids and reason codes in details, map checks and the editor.

### 9.11 Rationale and deferred refinements (non-normative)

Why the main choices were made (CA4-103/104/105):

- **Schematic, not a plan.** No smart-home product derives a map from a room graph; all start from
  a supplied or scanned plan. An uploaded plan costs asset storage and SVG sanitization and still
  needs every room placed by hand, while editable boxes reach a recognizable map with less work.
- **Grid boxes, not a generated floor plan.** Floor-plan generation (rectangular duals) needs a
  triangulated planar adjacency graph; a door graph is nearly a tree and says nothing about shared
  walls. A coarse grid is deterministic, testable and easy to correct by hand.
- **Orientation as a preference, up direction in 45° steps.** Houses are rarely aligned to north,
  and opening orientations are 45° steps anyway. Arbitrary angles would skew boxes and text.
- **Exterior rooms as strips.** They are not enclosed; keeping them outside the boxes keeps the
  interior perimeter readable.
- **Separate groups with a gap.** Touching boxes read as connected rooms; a gap avoids a false
  contiguity without forbidding the administrator from closing it.
- **Device control through HA.** The apply plan stays Heima's only channel; HA's services,
  permissions and more-info dialog already exist. Security-relevant kinds never act on a tap.
- **Explicit save and local undo.** The layout is presentation only, so it needs no change set or
  impact preview; the revision check covers two administrators editing at once.
- **Overlays by channel kind and fact type; sun only from the core solar Sensors.** The panel shows
  what the owning layers hold and never guesses from an HA domain or reads HA state outside them.
- **`passage` instead of `stairs`/`elevator`.** No consumer distinguishes them; one doorless
  passable type covers archways, open plans and open staircases. One floor per room for the same
  reason: a floor span would serve only the map.

Deferred refinements, to reconsider after Initial V3 or when real houses show the need:

- half-cell granularity and resizing from the left or top edge;
- L-shaped or other non-rectangular rooms, and exterior strips that wrap a corner;
- rooms spanning several floors (stairwells, double-height spaces);
- an administrator override of an opening's position along its wall;
- an uploaded real plan as an optional background;
- a per-HA-user control scope (rooms a user may control from the map), editable by administrators
  and residents, which also covers a guest with an HA account; it waits for the guest model
  (backlog, open question 5), and like §9.14's scope it would not be a security boundary;
- tuning the proposal weights against a corpus of real topologies;
- the remaining map topic still under discussion: the map as a verification step in the guided
  first start (§11). The accessible list alternative is now §9.12 (CA4-111), pan and zoom are §9.13
  (CA4-112), and the Lovelace card is §9.14 (CA4-113).


### 9.12 List view (CA4-111)

A button, reachable by keyboard, switches the map to an equivalent list: per floor, each room with
its occupancy, activities, devices with their state, openings with their state and automations with
their badge reason. The same §9.8 controls are available on each device, with the same rules (tap
toggles only the allowed kinds; locks, door covers and climate open HA's more-info). The list is the
screen-reader and keyboard path for the map. It is also offered on very narrow screens. It has no
layout editor; editing stays in the map (§9.9).

### 9.13 Pan and zoom (CA4-112)

The map scrolls and zooms inside its own frame (§5.3):

- **Initial view.** The current floor fits the frame's width. The scale never drops below the one
  that keeps device targets inside boxes at 44×44 CSS pixels; a floor that fits only at a smaller
  scale stays at that minimum and pans inside the frame.
- **Gestures.** A pinch zooms. One finger pans only when the map is zoomed beyond its initial view;
  at the initial view the gesture scrolls the page, so the map never traps page scrolling. Double tap
  does not zoom, so the §9.8 tap is not delayed.
- **Buttons and keyboard.** Zoom in, zoom out and fit buttons are always visible. With focus on the
  map, arrow keys pan and +/− zoom. With a mouse, Ctrl/⌘+wheel or a trackpad pinch zooms; the wheel
  alone scrolls the page.
- **Range.** From the fitted view to 3×. Below a threshold scale, device groups show only their glyph
  and count. Text stays upright at every scale.
- **Edit mode.** Dragging a selected box moves it; dragging empty space pans. A selected box has
  44-pixel resize handles and the §9.9 move and size buttons.
- **View state.** Zoom and pan are local to the client: not part of `HouseMapLayout`, the address
  (§5.1) or the revision. Switching floor returns to the fitted view. A floor badge (§9.1) or an
  address that names a room centers the view on that room.
- **Motion.** Under `prefers-reduced-motion`, pan and zoom changes jump without animation.

### 9.14 Lovelace card (CA4-113)

The map is also a Lovelace card, `custom:heima-map-card`, for dashboards and wall tablets. It is
shipped in the integration's frontend build and registered by the integration as a frontend module,
so no manual resource step is needed. It is the same component as the Overview map, not a second
map: rendering, overlays (§9.7), floor badges, pan and zoom (§9.13), the list view (§9.12) and
device control (§9.8) are identical.

- **Access.** Any authenticated HA user, as for the map in the panel (§4).
- **Content.** The map only: no editor, map checks, items to do, notifications or identifiers. An
  automation badge shows its short plain-language reason; its full "Why?" link opens the panel
  address (§5.1) and works only for a viewer with a role.
- **Options**, set in HA's visual card editor:
  - `floor`: the floor shown at load and after an idle reset; the lowest floor by default. Floor
    tabs stay available.
  - `controls`: `true` by default; `false` makes the card view only.
  - `control_rooms`: optional list of `room_id`s chosen by name. When set, §9.8 control works only
    on devices drawn in those rooms or on their openings; everything else is shown but neither a
    tap nor a long press does anything.
  - `idle_reset`: seconds without interaction after which the card returns to `floor` and the
    fitted view; off by default.
- **Scope is not a security boundary.** HA has no per-entity permissions, so the card's HA user can
  control the same entities elsewhere in HA. `control_rooms` restricts only what the card offers; it
  is effective on a tablet locked to one dashboard, for example a guest-room tablet. It is
  configured by whoever edits the dashboard, an HA administrator.
- **Unknown references.** A `floor` or `control_rooms` entry that no longer exists is ignored, and
  the card editor flags it.
- **Size and accessibility.** The card fills its area and follows HA's sections grid; §5.3 applies.
- **Continuity.** On websocket reconnection the card re-reads `overview` and resubscribes. §5.2
  states show as one compact line inside the card, in resident wording. A layout saved in the panel
  reaches open cards and panels through `subscribe` as a new `revision`.

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
| Automation state | Layer 5 authority transitions (mode), the active composed generation (catalog entries, and `configuration_invalid` from each commit's invalidated dependents), Layer-6 availability tracker episodes (block and reason) |
| Pending items | Layer 5 proposal-review, consent and advisory occurrences, Layer 0 recovery-confirmation occurrences |
| Heima health | Layer 0 runtime-error occurrences (§10.1), health snapshots, degradation-diagnostic changes and recovery-state changes (§5.2) |

Health is `error` while Layer 0's runtime error condition holds (Layer 0 §10.1: no active manifest,
or failing durable writes), the same predicate as the `system.health` notification; `degraded` when any degradation diagnostic is active, `ok` otherwise. At process start every
projection is rebuilt from the owners' current state (authority projection, open proposals and
requests, current diagnostics), so nothing is persisted and nothing polls.

## 11. First start (L8-C8)

The config flow creates the integration only. On first opening, the panel runs a guided procedure:
rooms → topology → devices → people and notifications → suggested automations, using the
configuration suggestions of §6.5 in the first three steps. Suggested
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
The integration also registers the map card (§9.14) from the same build.

- The panel talks to Heima through HA's websocket API with typed commands and queries; every
  message carries the authenticated HA user, which §4 resolves. Map device control (§9.8) instead
  calls HA services and opens HA's more-info dialog through the frontend's HA connection.
- Queries: current state from the in-memory current index; history, timelines, diffs and
  explanations as bounded slow-path queries with explicit time windows and pagination.
- Commands: configuration (§6) through Layer 0 §4.7; governance through Layer 5's common command
  surface (Layer 5 §4.2), whose typed `GovernanceCommandResult` and closed codes Layer 8 renders,
  and Layer 3's signal-adoption transitions (Layer 3 §4.9);
  answers through Layer 0's response ingress (§5.1.3) with the HA user, exactly like a button press;
  finding acknowledgement as Layer-8 view state (Layer 3 §6.1.1); house-map layout (§9).
- Every command carries an `operation_id`; exact retries return the first result.

Message catalog (websocket type prefix `heima/v3/`); "admin" and "resident" are the §4 roles:

| Message | Kind | Roles | Owner path |
|---|---|---|---|
| `session` | query | any HA user | §4 principal and roles |
| `overview` | query | any HA user (map part only without a role) | map layout and derived proposal, automation state, pending items (role-filtered) |
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
| `learning/promote_signal`, `learning/adopt_signal_artifact`, `learning/set_signal_adoption_mode` | command | admin | Layer 3 §4.9 (initial `live_signal_eligible` promotion, `adopt_pinned_signal_artifact`, `set_signal_artifact_adoption_mode`) |
| `reactions/set_consent` | command | resident with consent authority | Layer 5 §4.2 |
| `consent_authority/stage` | command | admin | Layer 5 §4.2 |
| `proposals/review` | command | admin | Layer 5 §4.2 |
| `findings/acknowledge` | command | admin | Layer-8 view state |
| `suggestions/list` | query | admin | §6.5, computed from the active generation and HA registries |
| `suggestions/dismiss`, `suggestions/restore` | command | admin | Layer-8 view state (§6.5) |
| `map/save_layout` | command | admin | §9.9, rejected on a stale `revision` |
| `diagnostics` | query | admin | §14 |
| `subscribe` | subscription | any HA user (map overlays and layout revisions only without a role) | live updates of §10.3 and map layout revisions (§9.14), role-filtered |
- Live updates to an open panel come from committed-state observers and the in-memory projections
  of §10.3, pushed over an HA websocket subscription; never polling.

## 14. Diagnostics

The System section renders, read-only, the diagnostics every layer already exposes (Layer 0 §10
and each layer's own): timing, observation continuity, recovery, holds (no manual release exists),
retry queue, committed-state observers, generation and impact history, learning and artifact state,
notification delivery. It also shows Layer 8's own counters: rejected commands by reason, preview
and apply outcomes, rebases and conflicts, published entities and their availability.

## 15. Decisions taken on the draft (2026-10-13)

1. **Users with no role** see the Overview with the house map only (§4; CA4-113 replaced the
   earlier "Heima is not set up for you" page).
2. **House map** (CA4-103, 2026-10-15): automatic schematic only; no uploaded plan in Initial V3.
   Device control from the map uses HA's own services and more-info dialog as the signed-in user,
   outside Heima's backend (§9).
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
- House-map proposal fixture: one floor with a hallway connected by doors to living room, kitchen,
  study, bedroom, small bathroom and entrance; a large bathroom reached only from the bedroom; a
  terrace reached by south door-windows of living room, kitchen and study; windows N (bedroom, large
  bathroom), E (small bathroom, study), W (living room); entrance door W. With `up=None` the
  suggested direction is north. The hallway is 3×1, living room, kitchen and study lie along its
  bottom edge, the terrace is a strip below them, and bedroom, small bathroom and entrance lie above
  it. Permuting registry order gives the same layout. Rotating every orientation by 45° suggests
  `northeast` and gives the same layout; forcing `north` on the rotated house gives a different one.
- A pinned room never moves when another room is added; the new room touches a connected room when
  a free touching cell exists. A window whose map side is fully shared with another interior box
  produces "Faces another room"; a door between non-touching boxes produces "Not adjacent". Neither
  changes `Topology`.
- Moving or resizing a box onto another is refused; undo restores the previous layout; a save on a
  stale revision is rejected without change. Changing the up direction clears that floor's
  placements only after the editor's warning.
- A tap on a light calls the HA toggle service as the signed-in user and sends no `heima/v3/`
  message; a tap on a lock or a garage-door cover opens HA's more-info dialog and calls no service.
  When the light is a current Reaction target, the resulting divergence follows Layer 0 §6 and the
  map shows the held automation with its explanation.
- With no core solar-geometry Sensors staged, the map draws no sun overlay and reads no `sun.sun`.
- A staircase room on floor 0 with a `door` to the entrance and a `passage` to a landing on floor 1:
  the passage is drawn on floor 0 with a badge to floor 1 and on floor 1 with a badge to floor 0;
  the landing is proposed in the staircase's cell when that cell is free; an archway `passage`
  between kitchen and living room is a gap without a leaf and has no opening state (CA4-104).
- A garage on the apartment's floor with only a door to `outside` and an east window forms its own
  group: it is placed beside the apartment block with one empty cell between, on the east side, and
  produces "Not connected"; dismissing it hides the check, and dragging the garage against the
  apartment is accepted (CA4-105).
- Every published entity is read-only, `unavailable` when its fact is unavailable (an activity
  entity is `off` instead), translated, and carries no free text or person identity. A room where
  `relax` and `working` are both active shows two activity entities `on`; a cooking entity is `off`,
  never `unavailable`, while the hob is off or unreadable.
- Phones and accessibility (CA4-111): an automated accessibility check (axe-core) of every section,
  in both roles and in light and dark themes, reports no WCAG 2.2 AA violation; keyboard-only
  scenarios answer a request, apply a change set and save the map layout; at 360 CSS pixels no
  section scrolls horizontally; the back gesture after opening a Reaction from a notification
  returns to the previous view; the map's list view offers the same states and controls, and a tap
  on a lock in it opens more-info.
- Map card and access (CA4-113): an HA user with no role opens the panel and sees only the Overview
  map in resident wording, and `objects/list` from that user is rejected; a card added to a
  dashboard renders without any resource step; with `control_rooms: [guest_room]` a tap on the
  guest-room light toggles it, while a tap or long press on the living-room light does nothing; with
  `controls: false` no tap acts; after `idle_reset` the card returns to its `floor` and fitted view;
  a layout saved in the panel redraws an open card; after a websocket drop the card shows the
  interrupted state and resynchronizes; a removed room in `control_rooms` is ignored and flagged.
- Map pan and zoom (CA4-112): at 360 CSS pixels a floor wider than the frame opens at the minimum
  scale with 44-pixel device targets and pans inside the frame; at the fitted view a one-finger swipe
  scrolls the page, and after a pinch it pans the map; a single tap on a light toggles it without
  delay; the zoom buttons and arrow/+/− keys reach every room; in edit mode a box is moved and
  resized with buttons only; a save leaves the layout revision unaffected by zoom and pan; a floor
  badge switches floor and centers the connected room.
- Panel states (CA4-108): during `startup_recovery` both roles see "Heima is starting" and a map
  without live overlays; with health `degraded` an administrator sees a banner linked to System and a
  resident sees none; with health `error` and a pending power-recovery confirmation, only the error
  banner shows; a dropped live subscription dims the last values with their update time and
  resynchronizes on reconnection without a page reload.
- No user-facing literal string exists outside translation resources; switching the HA user's
  language to an unshipped locale shows English.
- With an HA area "Studio" on HA floor level 1 and no linked room, House suggests a room "Studio" on
  floor 1; accepting adds an `add` edit with `enclosure` to confirm, and nothing exists until apply.
  Dismissing it hides it for every administrator until restored; linking the area to a room removes
  the suggestion. A weather entity yields one Sensor suggestion per usable attribute, each requiring
  its outdoor meaning before the edit validates (CA4-107).
- `/heima/automations/reaction/<id>?at=<T>` opens that Reaction's "Why?" at T; after the Reaction is
  removed the same address opens Automations with "This item is no longer available". A resident
  opening an administrator-only object address sees that same notice, byte-identical to the one for
  a missing object (§5.1).
- No panel query or command delays an evaluation cycle.
