# Changelog

## [0.17.0] — 2026-08-27

- Fixed: `InputNormalizer.boolean_signal()` only recognized a generic on/off vocabulary
  (`on`/`home`/`open`/`occupied`/`detected`/`true`/`1`), so battery_state companion-app sensors
  reporting `"Charging"`/`"Full"` always normalized to `off` — permanently blocking
  `sleep_charging_min_count` regardless of the device's actual state. Adds an additive
  `extra_on_states` parameter (not a full override, since a single `sleep_charging_entities` list
  can legitimately mix a plain binary_sensor with a battery_state text sensor) and wires the
  house-state charging-evidence call site to recognize `"charging"`/`"full"`.

## [0.16.0] — 2026-08-26

- Actuator Discovery (Phase AV, AV1-3): Phase L's rule-based discovery now suggests `Actuator`
  candidates for `cover`/`fan`/`climate`/`humidifier`/`switch` entities whose HA Area maps to a
  known Room, both in the Options Flow discovery step (accept and it's persisted as a real
  `Actuator`, with an idempotency guard against re-creating a duplicate) and as a room-aware
  entity picker in the Actuators admin form — a `<select>` of suggested entities (selected room
  listed first) with a manual free-text escape hatch, replacing the plain text field. `light`
  stays excluded (owned by Lighting's own domain/Reaction model); discovery only ever proposes
  `room_id`, never `opening_id`.
- The Actuators admin table is now grouped by Room, collapsed by default — an installation can
  have a large number of actuators, and a single flat table had become unwieldy to scan.
- Editing an actuator now opens an inline form directly below the clicked row instead of a shared
  form at the bottom of the section, which required scrolling past every other room's table to
  reach with a long actuator list.

## [0.15.0] — 2026-08-26

- Actuator Registry (Phase AU, AU1-4): a new generic, room/opening-aware inventory of actuator
  entities (covers, fans, climate units, and future equipment classes) — placement only, no
  command/capability model — so future comfort/climate Reactions can resolve "the shutter on the
  south window" without hardcoding entity_ids. Persisted per config entry, validated against
  Installation Validation, cached and exposed via `CanonicalState["rooms.actuators"]`, included in
  recovery's critical-entity tracking. Fully admin-editable through a new "Actuators" section in
  the admin panel (websocket-backed, admin-gated), including in-place editing. Deleting a Room
  Topology Opening still referenced by an Actuator is now blocked with a referential-integrity
  error, mirroring the existing Connection-blocks-delete behavior.
- Fixed: creating a new Opening/Connection/Actuator without a client-supplied id (the normal
  "add new" flow) now returns the server-generated id in the websocket response and the
  admin-action audit trail — previously both were built from the original request payload, which
  has no id for a new record, so the created record was logged/returned with an empty id even
  though the persisted record itself was always correct.
- The Room Topology admin editor's "Add opening" Entity ID field is now an autocomplete dropdown
  (room-resolved, reusing Phase L's discovery rule for door/window sensors) instead of plain free
  text; the Connections table's Opening column now shows a human-readable label
  (type/orientation/entity_id) instead of a bare UUID.
- Fixed a pre-existing, panel-wide bug where typing into any tracked admin-panel input (search
  boxes, every add/edit form field) could scroll the whole page to the top and feel like the field
  lost focus, caused by the full shadow-DOM re-render triggered on every keystroke.

## [0.14.0] — 2026-08-24

- Room Topology (Phase AR, AR1-4): a new declarative spatial data model — room type/floor, doors and
  windows (`Opening`, with optional orientation and monitor entity), and room-to-room/room-to-outside
  connections (`Connection`, with a derived `connection_type: indoor|outdoor|separate`). Persisted
  per config entry, validated against Installation Validation with correct error/warning severity,
  cached and exposed to future consumers via `CanonicalState["rooms.topology"]`. Fully admin-editable
  through a new "Topology" section in the admin panel (websocket-backed, admin-gated), including
  in-place editing of existing openings/connections, not just add/delete.
- Fixed a pre-existing bug (made easy to trigger by the new editor): editing a room's `room_type`
  could make the Heima admin panel vanish from the sidebar until a full Home Assistant restart.
  `async_setup_entry` now re-registers the panel the same way `async_setup` does.
- Editing only cosmetic room fields (`room_type`/`floor`/`geometry`) now uses a light options reload
  instead of forcing a full config-entry reload.
- Fixed the admin panel losing `<details>` (raw JSON) expanded state, and losing in-progress form
  input, on every unrelated re-render (the 15s observability poll, another admin action).
- `room_id: "outside"` is now a reserved value in the room editor — it collided with Room Topology's
  sentinel for "the exterior, not modeled as a Room."
- Room Topology's original consumers (HouseState, Occupancy, Security diagnostics/alarm-boundary
  use) were re-evaluated before this release and found not to block anything currently planned;
  split out to a deferred, unscheduled spec (`docs/specs/core/room_topology_consumers_spec.md`) so
  the data model, validation, cache, and admin editor could ship on their own.

## [0.13.0] — 2026-08-21

- Recovery no longer blocks stabilization on motion/occupancy/presence entities that are
  `unavailable` only because they haven't fired since restart. These entities stay visible in
  checkpoint differences and observability but no longer count toward the recovery unavailable
  ratio (`critical_entities` in admin observability now also reports `gating_total` /
  `gating_unavailable` alongside the full counts).

## [0.12.0] — 2026-08-20

- Runtime checkpoint and power recovery: post-review hardening — missing critical entities are
  classified as unavailable instead of being silently omitted from recovery ratios; checkpoint
  writes are guarded against concurrent recovery; recovery diagnostics expose wall-clock
  timestamps for every phase transition; `ApplyStep.recovery_policy` gained an explicit allow
  vocabulary so camera privacy enforcement can run during recovery when the alarm input is stable.
- Structured runtime source (`ApplyStepSource`): apply steps now carry a typed source (reaction,
  domain, admin command, resident response, timeout, recovery, system, test) instead of a
  free-form string. Legacy string sources remain accepted but are never authoritative. Recovery
  admin bypass, Manual Hold ownership, runtime confirmation provenance, script apply batches, and
  observability all derive from structured sources instead of parsing strings; raw actor ids are
  redacted everywhere they could otherwise leak (diagnostics, observability, checkpoints, logs,
  persisted stores).
- Reaction evaluation is now suppressed during active runtime recovery (except the camera privacy
  policy template, which must keep protecting the home), so scheduled reactions don't misfire or
  lose their trigger window while the system is still settling after a restart.
- `camera_evidence_sources` now accepts both list and dict-keyed-by-id shapes at every runtime
  call site, matching the Options Flow editor's existing tolerance; malformed entries are still
  surfaced as an installer diagnostic instead of being silently dropped.

## [0.11.0] — 2026-08-19

- Fix Hassfest `config_flow.py` file requirement by moving the config flow step
  implementation to `config_flow_steps/` and adding a `config_flow.py` entry point that
  re-exports `HeimaConfigFlow`/`HeimaOptionsFlowHandler`.
- Sort `manifest.json` keys per Hassfest convention (`domain`, `name`, then alphabetical).
- Remove the unsupported `domains` key from `hacs.json`.
- Add brand assets (`icon.png`, `icon@2x.png`) for HACS brand validation.

## [0.10.0] — 2026-07-07

- Release implicit camera privacy manual holds when the configured alarm transitions from
  `disarmed` to any armed state, allowing privacy policies to resume on the next arm cycle.
- Preserve explicit `manual_hold_entity` behavior: helper-backed holds still remain active until
  their helper is turned off.

## [0.9.0] — 2026-07-03

Merge v2 architecture into `main`. Replaces the v1 hardcoded DAG
(`InputNormalizer → People → Occupancy → Calendar → HouseState → Lighting → Heating → Security → Apply`)
with the declarative plugin DAG described in `docs/specs/heima_v2_spec.md`. 1594 tests passing.

Highlights (Phases A–AG, see `docs/v2_dev_plan.md` for full detail):

- Declarative domain DAG with `depends_on` ordering; core domains People → Occupancy → Activity →
  HouseState fixed, plugin domains (Lighting, Heating, Security, Calendar) sorted by dependency.
- `ActivityDomain` as the fourth core domain, with primitive activity detection and hysteresis.
- `InferenceEngine` v2, `OutcomeTracker` act→verify feedback loop, and per-cycle
  `IInvariantCheck` structural checks.
- Behavior analyzers for patterns, anomalies, lifecycle suggestions, and composite/cross-domain
  signals, routed through an approval-gated `ProposalEngine`.
- Proposal lifecycle management: grouping, temporal review bundles, replacement, retirement, and
  maintenance suggestions.
- `ManualHoldManager`: shared framework for respecting user intervention across domains.
- Camera privacy policies driven by alarm state and house-state conditions, authored through a
  domain-specific Policy Editor (Options Flow), built on the generic Policy Editor Framework.
- Installer alert channel, health entity, auto-discovery config flow, and installation validation.
- Room context model, tiered house-state feature enrichment, and global drift detection.
- Developer scripts, operational docs, and canonical specs translated to English (Phase AG); the
  runtime's intentional IT/EN localization for dynamic proposal/reaction text is unaffected.

Not yet merged: Phase AB (Smart Lighting Automation, unified) remains `PLANNED` and continues on a
dedicated branch after this merge.

## [0.8.0] — 2026-04-30

Baseline v1 — 660 test passanti. Punto di partenza per lo sviluppo v2.
