# Heima Development Plan

## Status Overview
- Completed: `Phase 0`, `Phase 1`
- Completed: `Phase 2`
- Completed: `Phase 3`
- In Progress: `Normalization Layer` (`N1-N4` completed; `N5` materially complete for current rollout, future providers still open)
- In Progress: `Phase 4` (Heating MVP implemented, scheduler-backed, and service semantics aligned; final polish/documentation remains)
- Completed: configurable house-signal bindings (no hardcoded helper entity assumptions in house-state resolution)
- Completed: learning system Phases 1-7 runtime slices (generic event envelope, lighting/heating recorders, proposal persistence, signal recorder, Phase 7 hardening)
- Next: final Heating real-HA validation, then move to `Phase 5`

## Learning / Reactions Runtime Status
- Completed:
  - generic persisted learning-event envelope
  - lighting entity-level recording with provenance and grouping support
  - proposal acceptance normalization for `scene.turn_on` / `script.turn_on`
  - heating learning snapshots based on observed setpoints
  - proposal fingerprint persistence across restart
  - generic signal recorder for `learning.context_signal_entities`
  - `lighting_schedule` midnight-wrap hardening
  - `learning_reset` full runtime reset semantics
- Still open:
  - stronger scene/script provenance expansion to concrete entity batches
  - executable runtime support for accepted heating proposals
  - broader cross-domain analyzers on top of generic `state_change` events

## Live Test Remediation Plan
- Goal:
  - separate true end-to-end coverage from setup tooling, diagnostics, and seeded-learning integration paths
  - stop overstating shortcut-driven scripts as "E2E"
  - make the Docker HA lab deterministic enough to exercise reactions/learning without waiting weeks
- Current lab status:
  - available now in `docs/examples/ha_test_instance`:
    - fake on/off lights (`light.test_heima_living_main`, `light.test_heima_studio_main`)
    - motion/presence helpers
    - fake thermostat + thermal loop
    - fake alarm panel
    - MQTT helpers
    - configured Heima entry with rooms/security/heating/calendar in mounted `.storage`
  - main gaps:
    - fake lights do not expose brightness / color temperature / RGB, so lighting-learning attribute capture is shallow
    - calendar live checks are still environment-dependent, not fully lab-authored
    - live suite mixes provisioning and assertions
    - some proposal tests still depend on shortcuts (`seed_lighting_events`, overrides, config-entry reload)
- Execution tiers:
  - `setup`
    - environment creation/recovery only
    - no pass/fail claims about runtime behavior
  - `live_e2e`
    - real HA-facing entity/service changes only
    - must traverse recorder/runtime/event store using the same path a real HA user/device would hit
  - `seeded_integration`
    - deterministic historical-data generation for analyzer/proposal coverage
    - allowed to accelerate time/history, but must be labeled as non-E2E
  - `diagnostic`
    - read-only assertions on sensors/diagnostics/event stats
- Script reclassification targets:
  - move from live test lane to `setup`:
    - `scripts/live_tests/005_setup_lab.py`
    - `scripts/recover_test_lab_config.py`
  - keep as `diagnostic`:
    - `scripts/live_tests/030_learning_proposals_diag.py`
  - keep as `live_e2e` after cleanup:
    - `scripts/live_tests/000_live_smoke.py`
    - `scripts/live_tests/010_config_flow.py`
    - `scripts/live_tests/040_security_mismatch_runtime.py`
    - `scripts/live_tests/050_calendar_domain.py`
  - downgrade to `seeded_integration` until shortcut paths are removed:
    - `scripts/live_tests/015_learning_reset.sh`
    - `scripts/live_tests/020_learning_pipeline.py`
    - `scripts/live_tests/060_lighting_schedule.py`
- Phase A - Lab Capability Upgrades
  - add richer fake lights to `docs/examples/ha_test_instance/packages/heima_test_lab.yaml`
    - at least 2-3 lights per room
    - expose `brightness` and `color_temp_kelvin` at minimum
    - prefer helper-backed/template-backed state so normal `light.turn_on` calls produce recorder-visible state changes
  - add deterministic calendar fixtures to the Docker lab
    - ensure the configured `calendar.principale` can be driven by test scripts
    - add lab helper flow to create/update known vacation/office/WFH events instead of waiting for ambient calendar state
  - optional later:
    - add extra context-signal entities for learning correlation tests
    - add more than one person source so presence learning can be driven without runtime overrides
- Phase B - Runner / Suite Structure
  - replace blind executable discovery in `scripts/check_all_live.sh` with an explicit ordered manifest or per-tier suite selection
  - make `setup` an explicit prerequisite, not an in-band "test"
  - keep diagnostics optional/selectable from the runner
  - remove direct `.storage` patching from the canonical E2E path
    - `scripts/patch_heima_dev_options.sh` remains an admin/bootstrap tool only
- Phase C - True E2E Scenario Cleanup
  - presence learning:
    - stop using `heima.set_override` as the primary event generator
    - drive configured person/anonymous sources through real HA entities/MQTT/helpers
    - verify EventStore growth from recorder behavior before asserting proposals
  - lighting learning:
    - make real light toggles mandatory, not warn-only
    - stop relying on `seed_lighting_events` for the main live path
    - prove: light state change -> `LightingRecorderBehavior` -> EventStore -> proposal/acceptance path
  - security mismatch:
    - keep options-flow edits if the scenario explicitly validates runtime behavior under configured policies
    - avoid silent self-healing that hides missing lab prerequisites when the goal is coverage
  - calendar runtime:
    - create the calendar event in the test, then assert house-state/runtime behavior
- Phase D - Seeded Learning Path
  - add a deterministic historical event generator or importer for proposal tests that need multi-week data
  - do not use random event spam as the primary strategy
  - generate structured patterns:
    - weekday arrival windows for presence
    - repeated room/entity schedules with stable brightness/color temp for lighting
    - repeated away/home heating preference sessions
  - add controlled noise only around a strong base pattern
  - label this tier explicitly as `seeded_integration`, not `live_e2e`
- Phase E - Documentation / Acceptance Criteria
  - update `scripts/README.md`:
    - define the four tiers (`setup`, `live_e2e`, `seeded_integration`, `diagnostic`)
    - document which scripts belong to which tier
    - clarify that proposal acceleration is not "true E2E"
  - update `docs/examples/ha_test_instance/README.md`:
    - document the richer lab entities and calendar fixtures
    - document the intended Heima bindings for live learning tests
  - acceptance criteria per tier:
    - `live_e2e`: proves real HA entity/service changes become recorded learning events
    - `seeded_integration`: proves analyzer -> proposal -> acceptance -> configured reaction rebuild with deterministic historical data
    - `diagnostic`: proves sensors/diagnostics reflect runtime state correctly
- Suggested implementation order:
  1. enrich Docker lab lights/calendar fixtures
  2. split setup from live test execution
  3. remove shortcut reliance from presence/lighting live scenarios
  4. add seeded-learning generator for proposal-heavy cases
  5. update docs and runner UX

## Roadmap (with Normalization Rollout)

1. [x] Phase 0 — Architecture Alignment (Core Setup)
- Define runtime structure for domains/behaviors (`runtime/`, `domains/`, `behaviors/`, `domain_registry`, `orchestrator`).
- Establish core data contracts for `DecisionSnapshot`, `ApplyPlan`, and `HeimaEvent`.
- Implement `HeimaEngine` pipeline foundation: snapshot -> policy -> intents -> apply plan -> apply.

2. [x] Phase 1 — Canonical State + Input Binding
- Implement adapters for People/Anonymous Presence and Occupancy (read from HA state).
- Compute `house_state` and reason according to spec priority.
- Update canonical entities continuously through `CanonicalState`.
- Wire state-change triggers to coordinator refresh (`DataUpdateCoordinator`).

3. [x] Phase 2 — Lighting Domain (Policy + Mapping + Apply)
- Implement base policy (house_state + occupancy) and room-scene mapping.
- Support per-room manual hold and scene fallback.
- Add idempotent/rate-limited apply per room.
- Emit `lighting.*` events from Event Catalog.

4. [ ] Phase 3 — Notification Domain + Event Catalog
- [x] Implement `HeimaEvent` pipeline with dedup/rate-limit.
- [x] Route events to `heima_event` bus and configured `notify.*` services.
- [x] Extend diagnostics with event stats and recent events.
- [x] Wire `heima.command -> notify_event` to unified runtime pipeline (end-to-end).
- [x] Add event category toggles (`people`, `occupancy`, `house_state`, `lighting`, `heating`, `security`; `system` always enabled).
- [x] Centralize runtime event gating before pipeline emission.
- [x] Harden notification routing for startup races (`notify.*` unavailable -> deferred retry, no setup failure).
- [x] Expand core Event Catalog coverage for `people.*`, `occupancy.*`, `lighting.*`, `security.*`, `system.engine_disabled`.
- [x] Add notification recipient aliases / recipient groups while keeping legacy `routes` as a compatibility fallback.
- [x] Complete Event Catalog naming closure for v1 runtime (`security.armed_away_but_home` explicit taxonomy, payload fields aligned to emitted runtime context, deferred stance for `heating.verify_failed`/`heating.apply_failed` documented).
- [x] Deprecate legacy `notifications.routes` with phased rollout:
  - phase A: deprecation notice + docs/UI warnings (done)
  - phase B: migration tooling (`routes` -> logical recipients/targets) (done: options-flow bridge for routes-only profiles)
  - phase C: runtime closed (routes no longer used directly; logical routing only)
- [x] Introduce `security.mismatch` canonical event with subtype model and compatibility mode (`explicit_only|generic_only|dual_emit`) per `docs/specs/rfc/security_mismatch_generalization_spec.md`.

5. [ ] Cross-Cut — Input Normalization Layer (Incremental Rollout N1-N5)
- [x] N1 Foundation: add shared normalization contracts + `InputNormalizer` facade + fusion plugin/strategy registry contract (behavior-preserving legacy-backed adapter).
- [x] N1 Migration: route existing runtime raw reads through the facade (no behavioral change intended).
- [x] N2 Occupancy: compute room occupancy from normalized presence observations; implement `on_dwell_s` / `off_dwell_s` / `max_on_s`.
- [x] N2 Occupancy (operational): move room fusion to registry (`builtin.any_of` / `builtin.all_of`) and use `DerivedObservation` in occupancy decisions.
- [x] N2 Occupancy (operational): implement dwell runtime state machine (`candidate_state/since`, `effective_state/since`) per derived room.
- [x] N2 Occupancy (operational): enforce `max_on_s` timeout with explicit event/diagnostics trace.
- [x] N2 Diagnostics: expose normalization trace for occupancy sources (raw_state -> normalized_state/reason).
- [x] N3 Security: normalize alarm raw states to canonical security observation; migrate `security.*` consistency logic to normalized inputs.
- [x] N4 House Signals + People: normalize house-mode helpers and people source inputs; remove domain-level raw parsing call sites.
- [ ] N5 Plugin Ecosystem Expansion: add external strategy providers behind the same `DerivedObservation` contract.
- [x] N5 Plugin Ecosystem Expansion: `builtin.weighted_quorum` added, wired into room occupancy, with configurable threshold and per-source weights.
- [x] N5 Plugin Hardening: deterministic plugin failure fallback (`unknown|off|on`), global normalizer diagnostics, and local fallback trace in occupancy/presence runtime traces.
- [x] N5 Verification: HA end-to-end tests cover occupancy dwell, weighted quorum, people quorum, anonymous presence, and fail-safe fallback paths.
- [x] N5 Broadening: move beyond presence-only runtime adoption and apply the plugin layer to non-presence signal families.
- [x] N5 Broadening Step 1: introduce shared non-presence boolean-signal strategy config and use plugin-driven corroboration in security mismatch logic.
- [x] N5 Broadening Step 2: move house-mode helper composition to shared non-presence strategy paths instead of ad hoc boolean checks.
- [x] N5 Broadening Step 3: expose reusable strategy configuration contracts for additional non-presence domains (security, house state, future constraints/heating).

6. [ ] Phase 4 — Heating Domain (Safe Apply)
- [x] Replace the legacy heating-intent model with fixed built-in branches keyed by `house_state`.
- [x] Implement apply modes (`delegate_to_scheduler`, `set_temperature`).
- [x] Add safe apply baseline: manual hold guard, small-delta skip, rate limiting, idempotence, startup race tolerance.
- [x] Implement `fixed_target` branch.
- [x] Implement `vacation_curve` branch with outdoor-temp safety floor, phase progression, and target quantization.
- [x] Add Heating observability sensors (`branch`, `current_setpoint`, `last_applied_target`) and core `heating.*` runtime events.
- [x] Add shared Runtime Scheduler and migrate all timed rechecks (occupancy, security, heating) onto it.
- [x] Add automated runtime + HA e2e coverage for Heating MVP and scheduler-driven vacation rechecks.
- [x] Refine manual override detection beyond canonical `heima_heating_manual_hold` (thermostat-native/manual preset inference).
- [x] Decide and implement the fate of `heima.set_mode` (real behavior or removal).
- [x] Add `heating.branch_changed` only if we decide the extra event is operationally useful.
- [x] Improve `vacation_curve` next-check precision from phase-aware scheduling to exact next quantized target-change timing.
- [x] Explicitly document that v1 `scheduler_delegate` means “Heima yields to external scheduler” (no direct scheduler integration).
- [x] Keep retry/verify logic out of Heima v1; if revisited, treat it as a future optional enhancement, not a current task.
- [ ] Run a final real-HA validation pass for Heating branch editing and scheduler-driven progression before calling Heating v1 complete.

7. [ ] Phase 5 — Security Domain (Read-Only) + Constraints Layer
- Normalize security state and reason.
- [SKIP] Security apply (arm/disarm commands): some integrations (e.g. SIA) are read-only and do not accept write commands. Skipped by design; security domain stays read-only.
- Implement `system.constraints` behavior with precedence order.
- Integrate constraints in `apply_filter` (block/clamp/defer).

8. [ ] Phase 6 — Behavior Framework v1.1
- Implement behavior registry and hook points (`on_snapshot`, `*_policy`, `apply_filter`).
- Add base behaviors and time-window lighting behavior.

9. [ ] Phase 7 — Watering Domain (Spec v1)
- Add Options Flow for sectors and sensor bindings.
- Create canonical watering entities (intent select, hold, telemetry).
- Implement base policy with lockout and max runtime.
- Implement Mode A mapping (script-based apply) and watering events.

10. [ ] Cross-Cut — Policy Plugin Framework (Future Rollout)
- [x] P0 Spec Foundation: define a cross-domain policy plugin framework mini-spec, explicitly separate from normalization plugins.
- [ ] P1 Framework Only: add policy plugin registry, dispatcher, hook contracts, diagnostics, and safe failure handling.
- [ ] P2 First Real Adoption: migrate Heating `vacation_curve` from fixed branch to first built-in policy plugin while preserving behavior.
- [ ] P3 Domain Expansion: extend policy plugins to Lighting / Watering / Constraints only after Heating is stable.

## Recent Delivered Work (post Phase 2 hardening)
- Options Flow hardening:
  - fixed edit-step navigation for people/rooms/lighting rooms/zones
  - fixed optional selector clearing (scene/entity/routes) using HA suggested values
  - normalized/finalized options consistently across save paths
- Lighting diagnostics:
  - per-zone trace (`requested_intent`, `final_intent`, `zone_occupied`)
  - per-room trace (scene resolution, skip reason, action)
  - multi-zone room conflict detection in diagnostics
- Lighting runtime:
  - room scene mappings fully optional
  - `off` fallback to `light.turn_off(area_id)` when `scene_off` missing
  - support `room.occupancy_mode = none` (actuation-only rooms)
- Specs updated:
  - room occupancy modes (`derived|none`)
  - zone occupancy ignores non-sensorized rooms
  - lighting `off` fallback semantics
- Automated tests expanded (now includes flow-like options tests, lighting runtime regressions, notify pipeline end-to-end)
- Automated tests expanded further:
  - normalization foundation/runtime migration coverage
  - plugin failure fallback and weighted quorum coverage
  - real HA end-to-end tests for normalization-critical paths
- Phase 3 hardening:
  - notification event category toggles in Options Flow
  - centralized event gating in runtime (spec-aligned, `system` always enabled)
  - startup race handling for `notify.*` routes with deferred delivery/retry
  - additional event catalog emissions (`people.*`, `house_state.changed`, occupancy inconsistencies, security inconsistency, zone conflicts)
- Architecture planning:
  - added Input Normalization Layer mini-spec (shared contracts/facade + plugin-based fusion registry + incremental rollout N1-N5) to avoid fragmented smart-policy implementations on raw HA states
  - added Heating Domain mini-spec (scheduler baseline + fixed vacation override branch)
  - added Policy Plugin Framework mini-spec (future cross-domain policy extension, distinct from normalization plugins)
  - added Runtime Scheduler mini-spec and implemented the shared scheduler as the timing substrate for occupancy dwell, mismatch persistence, and Heating timed branches
  - defined and implemented `heima.set_mode` as a final runtime-only house-state override service
