# Topology-Aware Climate Reactions Spec

**Status:** Draft — first pass, not yet approved. Not phased/numbered in `docs/v2_dev_plan.md` until
approved.
**Date:** 2026-08-27
**Scope:** Two new Reactions that close the loop between Room Topology (`Opening.orientation`,
`Connection.connection_type`), the Actuator Registry (`cover.*` entities placed at a room/opening),
and `ExternalContext` (outdoor weather signals) — first named as a concrete need in
`core/actuator_registry_spec.md`'s own Purpose section ("too much sun on the south side, and
there's a shutter there"):

1. **Ventilation Advisor** — should the house ventilate right now, and (eventually) which window
   pair is most effective, based on indoor/outdoor psychrometric differential and wind exposure.
2. **Weather Safety Close** — close `cover.*` actuators when wind or rain crosses a configured
   threshold, reopening automatically only what it closed itself.

Plus two small, additive data-model changes both Reactions depend on:
- `ExternalContext`: new `wind_bearing` slot (`adapters/external_context_contract.md` → v1.1).
- Room signals (`rooms[i].signals`, `room_sources.py`): new optional `opening_id` field.

**Related specs:** `core/room_topology_spec.md` (`Opening`/`Connection`/`Room`, reused unchanged),
`core/actuator_registry_spec.md` (`Actuator`, reused unchanged — this spec is exactly the
"future consumer" its own Purpose section anticipated), `adapters/external_context_contract.md`
(gains `wind_bearing`, v1.0 → v1.1), `core/apply_step_contract.md` (`ApplyStep` reused unchanged),
`core/reactive_behavior_spec.md` §6.3.1 (generic composite assist reaction contract — the pattern
Weather Safety Close follows), `core/manual_hold_framework_spec.md` (`heima_owned` classification,
reused for Weather Safety Close's auto-reopen), `core/resident_runtime_confirmation_spec.md`
(hard dependency — both VA3's `open_cover` and Weather Safety Close's open/close both go through
Runtime Confirmation, each with its own `RuntimeConfirmationDescriptor`; two more reaction families
opting in, alongside the only one so far, `context_conditioned_lighting_scene` — relative build
order between VA3 and Weather Safety Close not yet decided).

---

## Overlap Check

Per project convention, every new construct here was checked against what already exists before
being added:

| Need | Reused as-is | New |
|---|---|---|
| Which `cover.*` entity is where | `Actuator.entity_id`/`room_id`/`opening_id` (AU/AV) | — |
| Window/door orientation | `Opening.orientation` (AR) | — |
| Room adjacency for cross-ventilation | `Connection` graph (AR) | pathfinding *over* it (new, VA3) |
| Outdoor weather | `ExternalContext` (`outdoor_temp`, `outdoor_humidity`, `wind_speed`, `rain_*`) | `wind_bearing` |
| Command dispatch | `ApplyStep(domain="cover", action="open_cover"/"close_cover")` | — |
| "Did Heima or the resident change this" | `ManualHoldManager.classify_state_change` → `heima_owned` (existing, used today for camera privacy) | — |
| Indoor temperature/humidity per room | *nothing generic exists* | reuse `rooms[i].signals` as a **directory** (entity_id lookup by `room_id`/`device_class`), read the raw numeric state directly — no new runtime API |
| "Which sensor covers this specific window" | *nothing exists* | `rooms[i].signals[].opening_id` (new, optional) |
| Generic parametric Reaction pattern | `RoomSignalAssistReaction` (`signal_assist.py`), `core/reactive_behavior_spec.md` §6.3.1 | Weather Safety Close follows the same shape |

No new registry, no migration of `rooms[i].signals`' existing runtime consumer
(`EventCanonicalizer`/`engine.signal_bucket()`) — see the discussion in this spec's own history:
a full "Sensor Registry" sibling to Actuator Registry was considered and rejected as premature
abstraction, since `signals` already works and is stateful (event-driven bucket/burst detection),
not just static config.

---

## Data Model Changes

### `ExternalContext.wind_bearing`

Adds one canonical slot to `adapters/external_context_contract.md`:

| Slot | Type | Unit | Description |
|---|---|---|---|
| `wind_bearing` | float | ° (0-359, meteorological convention: direction the wind is blowing *from*) | Current wind direction |

This is a **MINOR** contract bump (1.0 → 1.1): new optional slot, existing adapters remain
compatible without changes (degrades the same way every other optional slot does — absent slot
disables the features that depend on it, here: VA2/VA3's directional scoring; VA1 and Weather
Safety Close are unaffected, since neither uses wind direction).

Degradation row to add to that spec's own table:

| Slot absent | Heima behavior |
|---|---|
| `wind_bearing` | Ventilation Advisor's directional scoring (VA2/VA3) disabled; VA1 (thermal/enthalpy gate) and Weather Safety Close both unaffected |

### Room signal `opening_id`

Extends each entry of `rooms[i].signals` (`room_sources.py`, `normalize_room_signals()`) with one
new optional field:

```jsonc
{
  "entity_id": "sensor.living_room_temp",
  "signal_name": "room_temperature",
  "device_class": "temperature",
  "buckets": [...],
  "opening_id": "opn_living_south_window"   // new, optional
}
```

- Purely additive metadata: no change to `_normalize_signal_buckets`, `EventCanonicalizer`, or
  `engine.signal_bucket()`/`signal_burst_recent()`. A signal's `opening_id` is invisible to the
  existing bucket/burst state machine — it is only read by the new Reactions below, directly from
  parsed `rooms[i].signals`, the same way they read `entity_id`.
- Validation mirrors `actuators.py:validate_actuators()` exactly (same severities, same message
  shape): dangling `opening_id` (references a room-topology Opening that no longer exists) →
  `warning`; `opening_id` belongs to a different room than the signal's own `room_id` → `error`.
- No automatic linking. The developer confirmed there is no reliable way to auto-derive
  sensor-to-opening placement from existing data (a temperature sensor's `entity_id`/`device_class`
  says nothing about which window it's near) — this is set manually, exactly like Actuator's own
  `opening_id`.
- Not admin-panel-editable in this phase (config-flow only, same as the rest of `rooms[i].signals`
  today). Admin-panel exposure is out of scope here — see Open Questions.

---

## Reaction 1: Ventilation Advisor

Third full rewrite of this Reaction's algorithm after two critical-review rounds (citations,
hardcoded-veto bug, dead output branch, `T_target` sourcing gap, and others — see this spec's own
history). This version, "V1", deliberately descopes anything that didn't have a solid answer rather
than papering over it — most notably it drops the earlier "cooling need" concept entirely (see VA1)
instead of inventing an unfounded `T_target` source.

Staged, ordered by dependency and blast radius (same discipline as AU/AV/AR's own admin-editor
slices and AW1-3's sequencing):

- **Opening Classification** (`EXTERNAL`/`INTERNAL`/`UNRESOLVED`) — a foundational step, not staged
  under VA1-3: evaluated once and reused by both VA2 (needs to know which openings are `EXTERNAL`)
  and VA3 (needs `INTERNAL` connections for path-finding).
- **VA1** — thermal/enthalpy benefit gate, per room. Answers "should the house ventilate at all
  right now, and where?" as a diagnostic, no window selection, no `ApplyStep` yet.
- **VA2** — per-opening directional exposure scoring (inlet/outlet proxies), still no `ApplyStep`.
- **VA3** — path-finding (same-room and cross-room), pairing, scoring, and the actual `ApplyStep`
  output.

### Opening Classification

Foundation for VA2/VA3, evaluated first. `external`/`internal` are **not** attributes of `Opening`
itself (no such field exists on it) — they're derived from `Connection`:

| Classification | Rule |
|---|---|
| `EXTERNAL` | A `Connection` exists referencing this `Opening` with `room_b == "outside"` |
| `INTERNAL` | A `Connection` exists referencing this `Opening` with `room_b` a real room |
| `UNRESOLVED` | No `Connection` references this `Opening` at all |

`UNRESOLVED` openings are **excluded from every calculation below**, not assumed external by
default — inferring "probably a window, probably external" from `Opening.type` alone would be
guessing at topology information the model doesn't actually have. Exposed as an Installation
Validation-style diagnostic/configuration warning (a real, actionable gap: the installer likely
just forgot to declare the `Connection`), not silently dropped.

### VA1 — Thermal/Enthalpy Benefit Gate

Inputs, one room at a time:

- `T_r`, `RH_r`: from `rooms[i].signals` entries with `device_class in {temperature, humidity}` and
  matching `room_id` — read as **raw numeric state** (`hass.states.get(entity_id).state`), not via
  `engine.signal_bucket()` (which only returns a semantic label like `"warm"`, not a value in °C —
  the formula below needs the number). **Multiple sensors in the same room** (more than one
  `signals` entry with matching `room_id` and `device_class`): arithmetic mean of the available
  numeric readings, excluding any `unavailable`/`unknown` entity — a stated choice for this spec,
  not derived from anything existing (no precedent for multi-sensor aggregation within a room for
  this purpose elsewhere in the codebase; `weighted_quorum`/`source_weights` in `room_sources.py`
  fuse presence/occupancy booleans, a different problem). A room with **no** sensor at all is simply
  not evaluated (excluded from `B_r` computation, not defaulted to any value) — see VA3 for how a
  path handles a *transit* room with no sensor, which is a related but distinct case.
- `T_out`, `RH_out`: `ExternalContext.outdoor_temp`/`outdoor_humidity`.
- Fixed atmospheric pressure `P = 101.325 kPa` (no pressure sensor assumed).

**No cooling-need concept in V1** (deliberate descope, not an oversight): an earlier draft of this
spec included `N_r`/`N_min`/`T_target` ("does this room actually need cooling relative to a target
temperature") gated behind an undefined data source (no per-room target temperature exists anywhere
in Heima today). Rather than inventing one, V1 determines only whether outdoor air is *more
favorable* than the room's current state — not whether the room *needs* it. Consequence, accepted
deliberately: V1 can recommend ventilating a room that's already comfortable, as long as outside is
measurably better. Acceptable because every recommendation is gated behind Resident Runtime
Confirmation (a person reviews before anything happens, see VA3) — reintroducing a "need" concept
once a target-temperature source is settled (e.g. Heating's own per-zone setpoint) is a natural V2
candidate, not built here.

Psychrometric calculation, applied to both indoor and outdoor readings — standard saturation
vapor pressure / humidity ratio / moist-air enthalpy relations from psychrometrics, in the general
form published by ASHRAE's Fundamentals Handbook. **Citation not yet verified against the primary
source** (edition, chapter, and equation numbers should be confirmed against an actual ASHRAE
Fundamentals Handbook copy before this is presented as an authoritative reference elsewhere, e.g. in
user-facing documentation) — flagged here rather than asserting a precise citation from memory:

```
p_ws(T) = 0.61078 * exp(17.2694 * T / (T + 237.3))      # saturation vapor pressure, kPa
p_v     = (RH / 100) * p_ws(T)                           # partial vapor pressure, kPa
W       = 0.621945 * p_v / (P - p_v)                     # humidity ratio, kg water / kg dry air
h       = 1.006 * T + W * (2501 + 1.86 * T)              # specific enthalpy, kJ/kg dry air
```

Per room:

```
ΔT_r = T_r - T_out
Δh_r = h_r - h_out
```

Thermal benefit — enthalpy is a hard gate, temperature sets the continuous magnitude (a deliberate
change from an earlier draft's geometric-mean blend of both, which let a marginal enthalpy reading
still contribute partial credit; a single source of truth, not a formula plus a separately-restated
veto that can drift out of sync — the earlier draft's hardcoded-veto bug came from exactly that
duplication):

```
B_r = clip((ΔT_r - ΔT_min) / ΔT_ref, 0, 1)   if Δh_r > Δh_min
B_r = 0                                       otherwise
```

Global gate — if no measured room has `B_r > 0`, stop here:

```
if no room has B_r > 0: return VENTILATION_NOT_NEEDED   (no pairing attempted)
```

Default parameters (all configurable, none are physical constants — see Limitations):

| Parameter | Default | Role |
|---|---|---|
| `ΔT_min` | 0.5 °C | Minimum thermal advantage, also hysteresis floor against sensor noise |
| `Δh_min` | 0 kJ/kg | Minimum enthalpy advantage (hard gate) |
| `ΔT_ref` | 3 °C | `B_r` normalization scale, tuning not physical |

Output at this stage: a diagnostic fact per room (`b_r: float`), exposed the same way
`HouseStateDomain`'s `topology_context` was scoped in the deferred AT spec — explanatory only, no
`ApplyStep`.

### VA2 — Directional Exposure Scoring

Per `EXTERNAL` window `Opening` (type `window`/`door_window`) with a known `orientation`, resolved
to degrees via a full, explicit mapping table (not left partial):

| `orientation` | `canonical_degrees` |
|---|---|
| `north` | 0 |
| `northeast` | 45 |
| `east` | 90 |
| `southeast` | 135 |
| `south` | 180 |
| `southwest` | 225 |
| `west` | 270 |
| `northwest` | 315 |

```
θ_i = canonical_degrees(orientation)
α_i = wrap180(wind_bearing - θ_i)
d_i = cos(α_i)                            # +1 windward, 0 parallel, -1 leeward
```

`wrap180(x)`, defined precisely (not left implicit): maps any angle difference onto `[-180, 180)`
degrees before taking the cosine, so the 359°/0° wrap-around doesn't produce a spurious ~360°
difference:

```
wrap180(x) = ((x + 180) mod 360) - 180
```

Lineage, stated explicitly: this is our own simplification of the relative-angle formulation NIST
CONTAM uses for wind-pressure modeling (`θ_rel = θ_w - θ_s`, wind direction relative to a facade's
azimuth) — but we substitute a bare `cos(α_i)` for NIST CONTAM's actual output, a real aerodynamic
pressure coefficient `C_p` that depends on wind angle, building shape, exposure, and terrain, none
of which we model. `d_i` is therefore explicitly **not** a `C_p` — a declared geometric
approximation, not the physical quantity NIST CONTAM computes. `Opening.orientation`'s 8-bucket
resolution (45° steps) is coarse but sufficient for `cos()` at this level of approximation.

Inlet/outlet decomposition (an improvement over an earlier draft's single subtraction-based
directional score, which gave partial credit to a pairing even when one side was only mediocre —
this correctly requires *both* a good inlet *and* a good outlet):

```
I_i = max(0, d_i)     # geometric predisposition to be an inlet
O_i = max(0, -d_i)    # geometric predisposition to be an outlet
```

Still diagnostic-only output at this stage (per-opening `d_i`, `I_i`, `O_i`), no `ApplyStep`.

### VA3 — Path-Finding, Pairing, and Selection

**Candidate pairs.** Every distinct pair `(i, j)` of `EXTERNAL` openings. `owner(i) == owner(j)` is
explicitly allowed (two windows in the same room) — see below.

**Same-room case.** If `owner(i) == owner(j) == r`: the path is trivially `R_p = {r}`, no internal
`Connection` needed, topologically valid by construction. Still subject to the thermal benefit,
directional scoring, and wind conditions below like any other pair.

**Cross-room case.** If `owner(i) != owner(j)`: enumerate **all simple paths** between the two rooms
using only currently-traversable `INTERNAL` connections (no cycles). House topology graphs are small
(a handful to a few dozen rooms, low branching factor) — `TopologyGraph.connections` already gives
the adjacency list, so exhaustive simple-path enumeration is cheap; no performance reason to
restrict to the shortest path only (an earlier draft did, then reverted this — see this spec's own
history).

**Path validity.** A path `p = (r_1, ..., r_n)` is valid (`V(p) = 1`) when every `Connection` on it
is currently traversable **and** it isn't `UNSAFE`. `UNSAFE`: at least one room `r` on the path,
*with known sensor data*, violates a harm bound —

```
UNSAFE if, for some r on the path: (T_out - T_r > ΔT_harm) OR (h_out - h_r > Δh_harm)
```

— i.e. outdoor air would measurably worsen (heat/humidify) a room the path merely passes through,
not the room actually being ventilated. Protects transit rooms (which aren't required to have
`B_r > 0` themselves — a corridor doesn't need to benefit, it just must not be harmed).

**Missing sensor data on a path.** A room on the path with no T/RH data can't have its harm check
evaluated — it is **not** auto-discarded and **not** treated as safe by default. Each path carries an
`observation_status`:

```
COMPLETE  — every room on the path has sensor data (harm check fully evaluated)
PARTIAL   — at least one room on the path has no sensor data (harm check skipped for it)
```

`COMPLETE` paths are preferred over `PARTIAL` ones (tie-break order below). If *every* candidate
path for a pair is `PARTIAL`, the pair can still be selected, but the eventual recommendation is
marked `confidence: LOW` (vs. `HIGH` when a `COMPLETE` path was used) — a future physical
window-automation feature built on top of this recommendation should apply a more conservative
policy for `LOW`-confidence output; V1 itself only recommends, it doesn't act unsupervised (see
Runtime Confirmation, below).

**Path benefit.**

```
B_p = max(B_r for r in R_p with known B_r)     if at least one room in R_p has known B_r
B_p = 0                                         if no room in R_p has known B_r
```

(Second line is a fix over an earlier draft, where the max over a possibly-empty set was left
undefined.) `max`, not average — deliberate: a path is worth taking if it serves *at least one*
room well, since a corridor or neutral zone shouldn't dilute that by being averaged in (it's already
protected separately by the harm constraint above, not by contributing to the benefit score).

**Best path per pair, with tie-breakers:**

```
P_ij = max over valid paths p of (V(p) * B_p)
p*_ij = the path achieving that max
```

Ties broken, in order: (1) prefer `COMPLETE` over `PARTIAL`; (2) fewer `Connection`s traversed
(a tie-breaker only, not the objective — an earlier draft used path length as the *primary*
selection criterion, which is what caused the shortest-path-only regression mentioned above);
(3) deterministic ordering of path identifiers, for stable output.

**Directional score.** For the pair, using VA2's `I`/`O`:

```
W_i→j = min(I_i, O_j)
W_j→i = min(I_j, O_i)
W_ij  = max(W_i→j, W_j→i)          # the surviving direction sets suggested inlet/outlet
```

**Pair score:**

```
Score_ij = P_ij * W_ij             # both factors in [0,1], so is Score_ij
```

**Window-to-actuator resolution** (unchanged from an earlier draft): an `Opening` participates only
if an `Actuator` exists with `opening_id` equal to that `Opening`'s `opening_id` — that Actuator's
`entity_id` is what gets commanded. No bound Actuator → the opening cannot be part of any pair, not
treated as any placeholder score.

**Wind speed** is *not* used to rank pairs against each other (it's a single outdoor measurement,
identical for every pair at a given evaluation), and does **not** enter `Score_ij` or the
`CROSS_VENTILATION_RECOMMENDED` gate (below) either — that gate compares raw `wind_speed` to
`V_min` directly. `A_V` below is purely an informational display value (part of the output payload,
"how favorable is the wind," on a continuous 0-1 scale) — not a threshold, not a gate, not consumed
anywhere else in this algorithm:

```
A_V = clip((wind_speed - V_min) / (V_good - V_min), 0, 1)
```

| Parameter | Default | Role |
|---|---|---|
| `V_min` | 0.5 m/s | Minimum wind to call a recommendation "cross-ventilation", not just thermal |
| `V_good` | 3.0 m/s | Reference for "very favorable" wind |
| `Score_min` | 0.15 | Minimum pair score to recommend cross-ventilation (guards against a high-benefit pair with a near-zero directional score being presented as real cross-ventilation) |
| `ΔT_harm` | 1.0 °C | Max tolerated thermal worsening of a transit room |
| `Δh_harm` | 2.0 kJ/kg | Max tolerated enthalpy worsening of a transit room |

**Output — exactly 3 states** (an earlier draft had a 4th, `VENTILATION_NOT_RECOMMENDED`, that
turned out to be unreachable dead code given the VA1 global gate already guarantees its own
precondition by construction — removed):

1. `VENTILATION_NOT_NEEDED` — VA1's global gate failed, no measured room has `B_r > 0`. No pairing
   attempted.
2. `CROSS_VENTILATION_RECOMMENDED` — best pair has `Score_ij >= Score_min` and `wind_speed >= V_min`.
   Carries: inlet/outlet opening, path, rooms traversed, the room driving `B_p`, `B_p`, `W_ij`,
   `Score_ij`, `wind_speed`, `A_V`, `confidence` (`HIGH`/`LOW`).
3. `VENTILATION_THERMALLY_FAVOURABLE` — at least one room has `B_r > 0` but no cross-ventilation
   recommendation clears the bar above (covers every case previously split out as single-sided
   ventilation, insufficient wind, no valid pair, unfavorable orientation, or low directional score
   — collapsed into one state after the earlier draft's two overlapping outcome names were found to
   describe the same situation). May still name the favorable rooms/openings, without asserting
   exchange effectiveness.

`ApplyStep` output, gated behind Resident Runtime Confirmation
(`core/resident_runtime_confirmation_spec.md`), never auto-applied, `on_timeout: "skip"` (no answer
→ nothing happens) — resolved earlier in this spec's history: `CROSS_VENTILATION_RECOMMENDED`
proposes `open_cover` for the winning pair's two actuators; `VENTILATION_THERMALLY_FAVOURABLE`
proposes `open_cover` for the single best-`B_r` room's actuator(s), still confidence-qualified in
the request text — interpretation made explicit here since the algorithm's own wording ("può
indicare") left it soft; flag if a purely-diagnostic (no `ApplyStep`) reading was intended instead
for this second state.

### Limitations

The model assumes `Opening.orientation` is a usable proxy for relative wind exposure. It does not
model: opening area, real open percentage, opening height, room volume, `Cp` coefficients, discharge
coefficients, external obstructions/shading, terrain roughness, elevation differences, local dynamic
pressure, or quantitative stack effect — all of which would be needed for an actual airflow-rate
estimate. `Score_ij` is a **ranking score only**: not a flow rate, not a probability, not a percentage
of air exchange, not ACH. The graph is deliberately used only for reachability, path alternatives,
and a boolean-per-path harm check — never as a fluid-dynamics simulation.

| Element | Nature |
|---|---|
| `p_ws`, `W`, `h` (psychrometrics) | Standard ASHRAE-style approximation (exact citation not yet verified) |
| `d_i = cos(α_i)` | Our own simplification of NIST CONTAM's relative-angle formulation, **not** a `Cp` aerodynamic coefficient |
| `ΔT_min`, `Δh_min`, `ΔT_ref`, `ΔT_harm`, `Δh_harm`, `V_min`, `V_good`, `Score_min` | Configurable tuning parameters, not physical constants |
| `B_p`, `P_ij`, `Score_ij`, `A_V` | Our own topology-derived ranking constructions, not measurable quantities — `A_V` in particular is display-only, not used in any gate |

---

## Reaction 2: Weather Safety Close

One generic, parametric Reaction (mirrors `RoomSignalAssistReaction`'s shape and
`core/reactive_behavior_spec.md` §6.3.1's generic composite assist contract) instead of two
one-off classes — wind and rain are mechanically identical: threshold on an `ExternalContext` slot
→ close `cover.*` actuators → auto-reopen only what it closed.

### Config contract

```jsonc
{
  "reaction_type": "weather_safety_close",
  "source_slot": "wind_speed",              // wind_speed | rain_last_1h | rain_forecast_next_6h
  "close_threshold": 12.0,                  // unit matches the slot (m/s or mm)
  "reopen_source_slot": "wind_speed",       // defaults to source_slot; see note below for why a
                                             // forecast-driven instance must override this
  "reopen_threshold": 8.0,                  // unit matches reopen_source_slot, not source_slot —
                                             // separate, lower threshold — hysteresis, avoids
                                             // flapping open/closed near the boundary
  "scope": "all_covers"                     // v1: every Actuator whose entity_id starts with
                                             // "cover." — no orientation filtering (see Reaction
                                             // rationale below)
}
```

Second example, a forecast-driven instance — illustrates why `reopen_source_slot` exists:

```jsonc
{
  "reaction_type": "weather_safety_close",
  "source_slot": "rain_forecast_next_6h",   // proactive: close ahead of predicted rain
  "close_threshold": 2.0,                   // mm forecast over the next 6h
  "reopen_source_slot": "rain_last_1h",     // reactive: reopen based on the LIVE outdoor rain
                                             // sensor, not the forecast
  "reopen_threshold": 0.2,                  // mm actually measured in the last hour
  "scope": "all_covers"
}
```

**Fixed gap**: reopening cannot simply reuse `source_slot`'s own value dropping below threshold when
`source_slot` is a forecast (`rain_forecast_next_6h`) — a rolling forward-looking forecast has no
meaningful moment where "the condition that triggered the close has passed," unlike an instantaneous
measurement (`wind_speed`, `rain_last_1h`). `reopen_source_slot` (new field, defaults to
`source_slot` when omitted) lets a forecast-triggered close be reopened based on the live outdoor
rain measurement (`ExternalContext.rain_last_1h` — already the "external rain sensor," no new slot
needed) instead of the forecast that triggered it. For `wind_speed`/`rain_last_1h`-sourced instances
(already live, instantaneous signals), `reopen_source_slot` defaults to the same slot and the
behavior is unchanged from a simple hysteresis gap.

- **Scope is unfiltered by design**, unlike Ventilation Advisor: strong wind and heavy rain are a
  risk from any direction (gusts, turbulence), so this closes every `cover.*` Actuator above
  threshold — window shutters *and* freestanding awnings alike (both are `cover.*` entities;
  distinguishing them by `opening_id` presence isn't needed here since both should close).
- Multiple configured instances (one per `source_slot`) are expected — e.g. one for `wind_speed`,
  one for `rain_forecast_next_6h` — each independently tracking its own closed-by-Heima set.

### Behavior

Both directions go through Resident Runtime Confirmation (`core/resident_runtime_confirmation_spec.md`)
via a `RuntimeConfirmationDescriptor` for `reaction_type: "weather_safety_close"` — **resolved**,
not auto-applied directly (one of two new reaction families opting in this spec, alongside VA3,
next to the only one so far, `context_conditioned_lighting_scene`). The two directions use different
`on_timeout`, no new mechanism needed — `RuntimeActionRequest.on_timeout` already supports exactly
this per-request:

1. Each cycle, read `ExternalContext[source_slot]`. If `>= close_threshold`, create a
   `RuntimeActionRequest` with `apply_steps = [ApplyStep(domain="cover", action="close_cover",
   target=entity_id), ...]` for every in-scope Actuator not already tracked as closed-by-this-reaction,
   and **`on_timeout: "apply"`** — if nobody answers, Heima closes anyway (safety-first default).
   Mark the entity tracked once the request resolves to applied (approved or timeout-applied).
2. When `ExternalContext[reopen_source_slot]` drops to `<= reopen_threshold`, for every entity in
   the tracked set: check
   ownership via `ManualHoldManager.classify_state_change` (was the last change to this entity
   `heima_owned`, i.e. still in the state Heima itself put it in, not overridden externally since).
   If still Heima-owned, create a `RuntimeActionRequest` with an `open_cover` step and
   **`on_timeout: "skip"`** (default) — no surprise reopening if nobody answers. If the resident
   changed it manually in the meantime, drop it from the tracked set silently — no request, no
   override.
3. Structural precedent for "close now, track ownership, reverse on condition" is
   `lighting_vacancy_off.py`; precedent for reusing `heima_owned` classification for a hold/release
   decision is the camera-privacy handling in `engine.py`
   (`handle_camera_privacy_state_changed`/`handle_security_state_changed_for_camera_privacy`).
4. Config-flow only in this phase — **resolved**, see Open Questions §4/§5's resolution: no admin
   panel section, consistent with every other generic parametric Reaction today.
5. Always notifies the resident when a request is created (both directions) — **resolved**, reuses
   the existing Notification Delivery Policy framework (Phase AP) the same way Runtime Confirmation's
   own notification transport already does for `context_conditioned_lighting_scene`.

---

## Validation

- Room signal `opening_id`: reuses `actuators.py:validate_actuators()`'s exact pattern (dangling →
  warning, room mismatch → error), added as an equivalent check for `rooms[i].signals` wherever
  room-level validation already runs.
- `wind_bearing`: no new validation — degrades like every other optional `ExternalContext` slot
  (absent → dependent feature disabled, no error), per that contract's own §Degradation.
- Weather Safety Close: `close_threshold` must be a positive number; `source_slot` and
  `reopen_source_slot` must each be one of `wind_speed`/`rain_last_1h`/`rain_forecast_next_6h`;
  `reopen_threshold` must be `<= close_threshold` only when `reopen_source_slot == source_slot`
  (they're on different unit scales otherwise, e.g. mm forecast vs. mm/h live — that comparison is
  meaningless across slots and must not be validated as if it were the same one).

## Testing Requirements

- Opening classification: `EXTERNAL` (`Connection.room_b == "outside"`), `INTERNAL` (`Connection` to
  a real room), `UNRESOLVED` (no `Connection` at all) — the latter excluded from every downstream
  calculation and surfaced as a diagnostic warning, not silently dropped or defaulted to external.
- VA1: psychrometric formula unit tests against known reference values (pending final citation, see
  Limitations); `B_r`'s enthalpy gate tested independently of its temperature magnitude, including
  with non-default `ΔT_min`/`Δh_min`; multi-sensor-per-room averaging, including one sensor
  `unavailable`; a room with zero sensors is excluded from `B_r` entirely, not defaulted.
- VA2: `d_i` correctness for all 8 orientation buckets against a range of `wind_bearing` values,
  including the wrap-around case (e.g. bearing near 0°/360°); `wrap180()` itself at its own boundary
  (`x = 180`, `x = -180`, `x = 359`); `I_i`/`O_i` are mutually exclusive (never both nonzero).
- VA3, path-finding: same-room pair (`owner(i) == owner(j)`) produces a trivial single-room path with
  no `Connection` required; a fixture with two alternate cross-room paths where only the
  *non-shortest* one is open still finds it (regression coverage — an earlier draft restricted to
  shortest-path-only); a closed door on every candidate path discards the pair entirely; harm check
  (`ΔT_harm`/`Δh_harm`) correctly discards a path through a transit room it would measurably worsen,
  and does *not* discard one through a room it merely fails to help; a transit room with no sensor
  data marks the path `PARTIAL` (not discarded, not treated as safe) and downgrades the eventual
  recommendation's `confidence` to `LOW` only when every candidate path for the pair is `PARTIAL`;
  `B_p` is `0`, not undefined/erroring, when literally no room on a path has known sensor data
  (empty-max edge case).
- VA3, pairing and output: tie-break order (`COMPLETE` over `PARTIAL`, then fewer connections, then
  deterministic id order) exercised with a fixture forcing each tie-break level in turn; a window
  with no bound Actuator is excluded from pairing entirely, not scored as `d_i = 0`; wind speed does
  not affect which pair wins (`argmax Score_ij`), only whether the result clears
  `CROSS_VENTILATION_RECOMMENDED`'s `wind_speed >= V_min` bar; exactly 3 reachable output states,
  with an explicit regression test that the removed 4th state (`VENTILATION_NOT_RECOMMENDED`) is
  gone, not just unused.
- Weather Safety Close: threshold crossing triggers close; hysteresis gap prevents flapping at the
  boundary; reopen only fires for `heima_owned` entities, never for a resident-overridden one;
  multiple configured instances (wind + rain) don't interfere with each other's tracked sets;
  `reopen_source_slot` distinct from `source_slot` (forecast-triggered close, live-sensor-triggered
  reopen) reopens on the live signal even while the forecast that originally triggered the close is
  still above its own threshold.
- Live test (per this project's convention for any new websocket/runtime-observable surface): if
  this ships with any new admin-panel/observability surface, a `scripts/live_tests/0NN_*.py` script
  following the AU/AV/AW precedent.

---

## Open Questions

**Resolved:**

1. ~~Does VA3's `open_cover` auto-apply, or go through Resident Runtime Confirmation?~~ **Both
   directions go through Runtime Confirmation** (`RuntimeConfirmationDescriptor` per reaction type),
   not auto-applied. VA3's `open_cover` uses `on_timeout: "skip"` (no answer → nothing happens);
   Weather Safety Close's `close_cover` uses `on_timeout: "apply"` (no answer → closes anyway,
   safety-first default), its `open_cover` uses `on_timeout: "skip"`. No new mechanism —
   `RuntimeActionRequest.on_timeout` already supports this per-request.
2. ~~Are VA2/VA3 in scope for the same phase as VA1?~~ **Yes** — all three are planned, sequential
   slices of one phase (not deferred roadmap), same discipline as AW1-3.
3. ~~Multi-path selection?~~ **Confirmed, superseded by VA3's later rewrite**: all simple paths
   between the two rooms are evaluated, not just the shortest; the winning path per pair is the one
   maximizing `B_p` (best thermally-served room on that path, subject to harm constraints), with
   path length demoted to a tie-breaker only. See the Reaction 1 §VA3 section above for the current
   formula — this superseded an intermediate boolean "is at least one path fully open" formulation
   from an earlier round of this same open question.
4. ~~Weather Safety Close admin-panel visibility?~~ **Config-flow only**, consistent with every
   other generic parametric Reaction (`RoomSignalAssistReaction` etc.) — no dedicated admin-panel
   section in this phase.
5. ~~Room signal `opening_id` admin-panel exposure?~~ **Config-flow/JSON only**, same reasoning as
   #4 — no picker UI in this phase.
6. ~~Notification on Weather Safety Close firing?~~ **Always notifies**, both directions, via the
   existing Notification Delivery Policy framework (Phase AP) — same transport Runtime Confirmation
   itself already uses.

All Open Questions resolved.

## Acceptance Criteria

- `wind_bearing` added to `adapters/external_context_contract.md` as v1.1, degrading gracefully when
  absent; existing adapters (OWM, DPC) remain valid without changes.
- `rooms[i].signals[].opening_id` parses, validates (dangling/room-mismatch), and is fully ignored by
  `EventCanonicalizer`/`engine.signal_bucket()` — zero behavior change for the 4 existing consumers
  (`lighting_assist`, `signal_assist`, `contextual_lighting_assist`, `smart_lighting_assist`).
- Opening classification (`EXTERNAL`/`INTERNAL`/`UNRESOLVED`) matches `Connection.room_b` derivation
  exactly; `UNRESOLVED` openings never silently participate as if external.
- VA1 correctly computes `B_r` per room from real `ExternalContext` + `rooms[i].signals` data,
  exposed as a diagnostic fact, no `ApplyStep`; global gate (`VENTILATION_NOT_NEEDED`) short-circuits
  before any pairing is attempted.
- VA3 produces exactly one of the 3 defined output states per evaluation, never more, never the
  removed 4th state; `CROSS_VENTILATION_RECOMMENDED` and `VENTILATION_THERMALLY_FAVOURABLE` both
  request their `open_cover` step(s) via Runtime Confirmation (`on_timeout: "skip"`), never applied
  directly; `confidence` is `LOW` exactly when every candidate path for the winning pair was
  `PARTIAL`, `HIGH` otherwise.
- Weather Safety Close closes every in-scope `cover.*` Actuator above threshold via a
  `RuntimeActionRequest` (`on_timeout: "apply"`), and requests reopening (`on_timeout: "skip"`) only
  for entities it closed itself and that remain `heima_owned`, never overriding a resident's manual
  action. Both directions notify.
- All Open Questions above resolved (or explicitly deferred with a named reason) before this spec
  moves from Draft to Approved.
- Mandatory merge-to-main procedure applies before any part of this lands on `main`, per CLAUDE.md.
