# Room Topology Consumers Spec (Deferred)

**Status:** Deferred — no committed phase. Split out of `core/room_topology_spec.md` (Phase AR)
after AR1–AR4 concluded and merged to `main`, so the foundational data model/validation/cache/admin
editor could land without gating on these three consumers, none of which block current work.
**Date:** 2026-08-24
**Scope:** How `HouseState`, `Occupancy`, and `Security` would consume `CanonicalState["rooms.topology"]`
(`core/room_topology_spec.md`), plus the corresponding `topology` admin-observability summary. None
of this is implemented; none of it is scheduled.
**Related specs:** `core/room_topology_spec.md` (hard dependency — this spec assumes AR1–AR4's data
model, derivation, and `CanonicalState` exposure already exist and are unchanged by anything here),
`domains/house_state_spec.md` §11 (diagnostics contract this would extend), `core/apply_step_contract.md`
(`blocked_by` convention Security would reuse), `core/admin_observability_panel_spec.md`

## Why This Was Split Out

`core/room_topology_spec.md`'s original Purpose named three consumers (Security, Occupancy,
HouseState) as the motivation for building the topology data model at all. AR1–AR4 built the model,
validation, cache, and admin editor; this document is what remained (the original AR5–AR8) once that
foundation shipped. It was split out, rather than kept as blocking sub-phases of Phase AR, for three
concrete reasons found when re-evaluating whether AR5–AR8 were actually load-bearing:

1. **None of them are prerequisites for anything currently planned.** `core/actuator_registry_spec.md`
   (the concrete next work motivating this re-evaluation) reads `CanonicalState["rooms.topology"]`
   directly — the same way any future comfort/climate Reaction would — and depends only on AR3, not
   on any of these three domains consuming it.
2. **AR5 (HouseState) is purely diagnostic by its own design** — it never changes the resolved
   `house_state` value and never triggers an action (see below). Deferring it indefinitely has zero
   behavioral cost.
3. **AR6 (Occupancy) turned out to be underspecified, not just low-priority.** See Occupancy below —
   there is currently no consumer anywhere in the codebase for a weighted/scored aggregate presence
   signal; `OccupancyResult.occupied_rooms` is a flat, unweighted list, and every downstream reader
   (`house_state.py`, `security.py`, `lighting.py`) does plain set-membership checks. Building the
   room-type weight table this spec originally proposed, with nothing to consume it, would mean
   inventing a whole new "weighted presence" concept speculatively — exactly what the project's own
   working style avoids. If this is picked up later, the weighted-presence consumer must be designed
   first, or named as a real, concrete need — not assumed.
4. **AR7 (Security) is net-new capability, not a gap-fill.** Verified against `runtime/domains/security.py`:
   Security today has zero door/window-based alarm-boundary logic. It works entirely via an external
   `security_state_entity` (a real HA `alarm_control_panel`) plus camera-evidence correlation. Nothing
   about Security's current behavior is broken or degraded by not having this — it would be an
   additional, independent capability, not a fix.

## HouseState (was AR5)

- Depends on: AR3 (reads cached `rooms.topology`).
- After `house_state` resolution runs unchanged (occupancy/presence/calendar logic untouched),
  `HouseStateDomain` separately cross-references `rooms.topology`'s `connection_type` structure
  (`separate`/`outdoor` openings) with the **live** entity state of those openings (not part of
  `rooms.topology`, which is a static cache — a per-cycle lookup like any other domain reading
  current entity state) to produce a fact like "an independent-access opening is currently open."
- This fact is attached to the existing extensible diagnostics contract
  (`domains/house_state_spec.md` §11 — already exposes `house_signals_trace`, `candidate_trace`,
  `resolution_trace`, `override`), under a new key, `topology_context: {open_boundary_openings: [...]}`.
- Purely explanatory: never influences the resolved `house_state` value, never triggers an action. No
  new top-level `house_state` values — the enum stays closed.
- Unconditional (any `house_state`, not just `armed_away`) — this is what distinguishes it from
  Security's use of the same underlying data below (Security's check is gated on `armed_away` and
  triggers an alarm; this one never triggers anything). The two reads are intentionally not shared
  through a common abstraction if both are ever built — the overlap is a few lines each.
- Tests (if built): `topology_context` appears in diagnostics when a `separate`/`outdoor` opening is
  open; `house_state` resolution and its enum values are unchanged before/after.

## Occupancy (was AR6)

- Depends on: AR3 (reads cached `rooms.topology`).
- Original proposal: `OccupancyDomain` reads `room_type` from `rooms.topology` and applies a
  room-type-to-weight table (indoor=1.0, balcony=0.5, garage=0.3, basement=0.2, outdoor=0.0,
  transit=low [unconfirmed], external=0.0) when computing "weighted presence."
- **Open question that must be resolved before this can be scoped, not just implemented:** what
  reads the resulting weight? `OccupancyDomain.compute()` today returns
  `OccupancyResult(occupied_rooms: list[str], sensorized_room_count: int)` — a flat, unweighted list.
  Every current consumer (`house_state.py`, `security.py`, `lighting.py`, zone-occupancy checks in
  `engine.py`) does plain `room in occupied_rooms` membership checks; none aggregate or score. There
  is no existing "weighted presence" concept anywhere in the runtime to extend. Before this is
  implemented, a concrete consumer must be named (e.g. a new aggregate "presence confidence" score
  used by some specific downstream decision) — otherwise this ships a weight table nothing reads.
- Existing, unrelated mechanism not to confuse this with: `source_weights`/`weight_threshold`/
  `logic: weighted_quorum` (`room_sources.py`) already lets a room fuse *multiple sensors within
  itself* into one boolean `is_occupied` — that mechanism is orthogonal to this one (which would be
  about weighting a room's occupancy *relative to other rooms*) and is unaffected by anything here.
- Tests (if built, once a consumer is named): weighted presence matches expected values per room
  type, exercised through whatever consumer is defined.

## Security (was AR7)

- Depends on: AR3 (reads cached `rooms.topology`); AR1/AR2 having already enforced the
  shared-`entity_id`/`connection_type` conflict rule, so Security never has to resolve that ambiguity
  itself.
- `SecurityDomain` would read `connection_type` + `Opening.entity_id` from `rooms.topology` for
  alarm-boundary classification: `connection_type: separate` or `outdoor` + `house_state: armed_away`
  + bound entity reporting open → alarm-eligible.
- An `Opening` with no `entity_id` would not be alarm-eligible — it cannot contribute to security
  logic; this must be visible in diagnostics (Installation Validation), not silently absent from
  alarm coverage.
- An `entity_id` shared across `Opening`s whose `Connection`s resolve to different `connection_type`
  values is already rejected by Installation Validation (AR1/AR2) as an `error` and must never reach
  this code path — there is no implicit precedence rule to add here.
- Reaction/apply blocking caused by topology-driven security classification should reuse the existing
  `blocked_by` convention (`core/manual_hold_framework_spec.md`,
  `core/runtime_checkpoint_and_power_recovery_spec.md`), not a new ad hoc format.
- Tests (if built): separate/outdoor connection with `armed_away` triggers correctly; entity-less
  opening does not silently participate in alarm logic; conflicting shared `entity_id` never reaches
  this code path (confirmed by an integration test, since it's rejected upstream).

## Observability (was AR8)

- Depends on: AR2 (validation counts), AR3 (topology counts), and Security above (decision traces) —
  meaning this cannot be built before Security, if Security itself is ever picked up.
- Would add a `topology` diagnostics summary to the AO snapshot (room/opening/connection counts,
  validation counts, unresolved entity references).
- Would ensure topology-driven Security decisions are traceable in existing AO decision traces.
- Tests (if built): AO snapshot includes `topology`; decision traces reference topology-derived
  classifications.

## Sequencing, If Ever Picked Up

The original ordering rationale (still valid if this work resumes): HouseState → Occupancy →
Security, ascending blast radius of a bug — HouseState is purely explanatory (cheapest way to prove
the `rooms.topology` read pattern), Occupancy degrades presence-weighting quality with no safety
implication, Security has the highest blast radius (false-negative alarm coverage) and should be
built last, once the read pattern is already proven on two lower-stakes consumers and once a real
consumer exists for whatever Occupancy scoping question gets resolved. Observability stays last
regardless, since it aggregates state produced by the others.

## Acceptance Criteria (If Resumed)

- Security, Occupancy, and HouseState can consume topology as configuration input without any new
  per-cycle computation or new `InferenceSignal` type.
- `house_state`'s enum is unchanged; topology-derived facts reach HouseState as context/diagnostics
  only.
- Occupancy's weighted-presence concept has a named, concrete consumer before implementation begins —
  not built speculatively.
- Installation Validation / AO gain the additional diagnostics described above.
- Covered by unit and integration tests per the per-domain sections above.
- Mandatory merge-to-main procedure applies before any part of this lands on `main`, per CLAUDE.md.
