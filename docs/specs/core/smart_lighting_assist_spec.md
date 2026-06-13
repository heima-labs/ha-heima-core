# Smart Lighting Assist Spec

## Status

Active — introduced in Phase AB.
Supersedes `contextual_room_lighting_assist_spec.md` and `room_darkness_lighting_assist` (both
types removed with hard cut in Phase AB).

**Last reviewed:** 2026-06-10

---

## Purpose

`room_smart_lighting_assist` is the single unified lighting automation type in v2.

It replaces:
- `room_darkness_lighting_assist` — static, no ambient modulation, no adaptive turn-off
- `room_contextual_lighting_assist` — profile-based, ambient modulation, but no adaptive timeout

The unified type covers the full lifecycle: smart turn-on based on indoor lux, real-time
brightness modulation from outdoor lux (no feedback loop), and adaptive two-step turn-off.

---

## Reaction type

`reaction_type: room_smart_lighting_assist`

---

## Config schema

```yaml
type: room_smart_lighting_assist
room_id: studio

# Lux control
indoor_lux_signal: room_lux         # signal name from room.signals; on/off gate only
outdoor_lux_signal: outdoor_lux     # optional; if absent, no ambient modulation
lux_on_buckets: [dark, dim]         # indoor lux buckets that allow turn-on

# Room type — key into default timeout table and night-mode defaults
room_type: studio                   # see §Room type catalog

# House-state gating
suppress_on_states: [vacation, away]          # states that fully suppress lighting
night_mode_states: [sleeping]                 # states that use night profile instead of suppressing
                                              # whether sleeping suppresses or uses night profile
                                              # is determined per room_type (see §Night-mode defaults)

# Timeout
timeout_mode: learned               # "fixed" | "learned"; default "learned"
base_timeout_min: 6                 # installer override; if absent, uses room_type default
fast_exit_timeout_s: 60             # timeout when visit classified as fast-exit

# Two-step turn-off
dim_brightness_pct: 15              # brightness during dim phase; default 15
dim_ratio: 0.3                      # fraction of effective_timeout spent in dim; default 0.3

# Brightness profiles (same schema as contextual)
# A profile may include house_states: [...] and/or hour_buckets: [...] selectors.
# A night_profile entry (house_states: [sleeping]) is used when house_state is in night_mode_states.
profiles: [...]                     # optional; if absent, uses entity_steps
entity_steps: [...]
```

---

## Turn-on logic

### Condition

At config load, `effective_suppress_states` is computed once:

```
effective_suppress_states =
    suppress_on_states
    ∪ { s for s in night_mode_states
        if room_type in NIGHT_SUPPRESS_ROOM_TYPES }
```

Turn-on fires when:

```
auto_lighting_enabled
AND NOT manual_override_active
AND presence_detected
AND indoor_lux_bucket in lux_on_buckets
AND house_state NOT IN effective_suppress_states
```

`NOT sleep_mode` is removed. House-state gating replaces it with room-type-aware logic.

Profile re-application (lights already on, context changed):

```
needs_apply
AND NOT manual_on_hold
```

---

## Manual override

### Detection — pending-apply records (primary)

HA does not reliably propagate `context.parent_id` to the final state change of a light entity:
many integrations emit the state change with their own context, breaking context-chain detection.
The primary mechanism is therefore **pending apply records**, which do not depend on context
propagation.

`PendingApply` carries the expected outcome of a single service call:

```python
@dataclass
class PendingApply:
    expected_state: str          # "on" | "off"
    timestamp: float             # time.monotonic()
    ttl: float = 5.0             # seconds; covers HA async propagation latency
    expected_brightness: int | None = None
    expected_color_temp: int | None = None
```

`expected_brightness` and `expected_color_temp` are set when the profile step includes those
attributes; they are `None` otherwise (attribute not verified in match).

Match on `STATE_CHANGED` for a tracked entity:

```
if entity_id in pending_applies:
    p = pending_applies[entity_id]
    within_ttl = (now() - p.timestamp) < p.ttl
    state_ok   = new_state.state == p.expected_state
    bri_ok     = p.expected_brightness is None or
                 |new_attrs.brightness - p.expected_brightness| ≤ 5
    ct_ok      = p.expected_color_temp is None or
                 |new_attrs.color_temp_kelvin - p.expected_color_temp| ≤ 100
    if within_ttl AND state_ok AND bri_ok AND ct_ok:
        → heima-owned: consume record, ignore
    else:
        → external: route to override logic
else:
    → external: route to override logic
```

Any change not matched — physical switch, another automation, scene, script, external
integration, other Heima reaction — is classified as **external**. The criterion remains
"not emitted by this reaction instance."

`issued_context_ids`, `ApplyStep.context_id`, and the `LightingRecorderBehavior` TTL path
are **not** used for override detection.

### On external OFF

When an external `off` is received on any entity in the active profile's `entity_steps`:
- cancel any active two-step turn-off sequence
- set `manual_override_active = True`
- turn-on condition fails until the override clears

`manual_override_active` clears on whichever comes first:
- `manual_override_window_min` expires (default 30 min; set to 0 to rely on presence cycle only)
- presence is lost **and** subsequently re-detected (room fully vacated and re-entered)

### On external ON

When an external `on` is received on any entity while the reaction is active or would be active:
- set `manual_on_hold = True`
- profile re-application is suppressed while `manual_on_hold` is true

`manual_on_hold` clears **only** on presence lost → re-detected. No timer fallback.

### Implementation contract

- `RoomSmartLightingAssistReaction` owns `pending_applies: dict[str, PendingApply]` and all
  override state (`manual_override_active`, `manual_on_hold`)
- The reaction exposes `register_pending_apply_for_step(step: ApplyStep)` — called by the
  execution layer **after** apply-plan filtering and immediately before `async_call`; not inside
  `evaluate()`. This prevents stale pending records from steps that are later blocked by
  constraints or guards.
- The reaction exposes `handle_external_light_change(entity_id, new_state)`, called by a
  coordinator-level `STATE_CHANGED` dispatcher
- The dispatcher filters events to entities listed in active smart-lighting reaction profiles
  before routing them; reactions are not subscribed directly to HA events
- `ApplyStep` requires no `context_id` field for this mechanism

### Config field

```yaml
manual_override_window_min: 30    # default 30; set to 0 to rely on presence cycle only
```

---

### Night-mode defaults by room_type

`NIGHT_SUPPRESS_ROOM_TYPES` (sleeping → suppress, not night-profile):

| room_type | sleeping → |
|---|---|
| camera_da_letto | suppress |
| cameretta_bambini | suppress |
| studio | suppress |
| soggiorno | suppress |
| sala_da_pranzo | suppress |
| tinello | suppress |
| garage | suppress |
| ripostiglio | suppress |
| bagno | night profile |
| corridoio | night profile |
| ingresso | night profile |
| cucina | night profile |
| lavanderia | night profile |
| generic | night profile |

Installer can override per-rule via `night_mode_states` and `suppress_on_states`.

### Profile selection

```
if house_state in night_mode_states:
    use profile where house_states contains sleeping  (night profile)
    fallback: color_temp=2200K, brightness=10%
else:
    use profile matching (house_state, hour_bucket)
    fallback: entity_steps or first profile
```

### House-state intensity and color temperature guidance

Profiles should be authored following this guidance:

| house_state | Color temp | Intensity |
|---|---|---|
| `working` | cold (4000–5500 K) | high (70–100 %) |
| `relax` | warm (2700–3000 K) | very low (5–20 %) |
| `sleeping` (night profile) | very warm (2200–2700 K) | very low (5–15 %) |
| `home` morning | neutral-cool (3500–4500 K) | medium (50–80 %) |
| `home` evening | warm (2700–3000 K) | medium (50–70 %) |
| `guest` | neutral (3000–3500 K) | medium-high (60–80 %) |

Note: `house_state = relax` implies by definition that a media player is active somewhere in the
house. Distinguishing "media active in this specific room" vs. "media active in another room"
(`room_relax_media_active`) is not yet exposed as a profile selector and is deferred to a future
enhancement.

Brightness: if `outdoor_lux_signal` configured, modulate the profile brightness using the
outdoor lux bucket scale; otherwise apply static brightness from the active profile or
entity_steps.

---

## Lux signal roles (invariant)

| Signal | Role | Triggers evaluation? |
|---|---|---|
| `indoor_lux_signal` | on/off gate only | No |
| `outdoor_lux_signal` | brightness modulation scale | Yes (debounced) |

Indoor lux is **never** used for brightness modulation. Doing so creates a feedback loop:
light turns on → indoor lux rises → brightness reduced → indoor lux falls → brightness raised
→ oscillation. The outdoor lux signal is decoupled from the actuator and is safe for
continuous modulation.

---

## Two-step turn-off

Once presence is lost and `effective_timeout` is computed:

1. At `t_absence + effective_timeout × (1 − dim_ratio)`: `light.turn_on` at `dim_brightness_pct`
2. At `t_absence + effective_timeout`: `light.turn_off`

If presence is re-detected at any point before turn-off: cancel sequence, return to full
brightness immediately.

Default `dim_ratio = 0.3` means the last 30 % of the timeout is spent in the dim phase.
Default `dim_brightness_pct = 15`.

---

## Smart timeout engine

### `timeout_mode = fixed`

```
effective_timeout = base_timeout_min (configured or room_type default)
fast_exit_threshold = fast_exit_timeout_s × 3

if current_visit_duration < fast_exit_threshold:
    effective_timeout = fast_exit_timeout_s
```

### `timeout_mode = learned` (default)

Per-room ring buffer of the last 50 visit durations (presence_confirmed → presence_lost).

- p25 of ring buffer = `fast_exit_threshold`
- Before 20 visits observed: fall back to fixed mode defaults

```
if current_visit_duration < fast_exit_threshold (p25):
    effective_timeout = fast_exit_timeout_s
else:
    effective_timeout = base_timeout_min
```

Ring buffer size (50) and minimum visits for learning (20) are internal constants.

Visit tracking: the automation records the timestamp when presence is first confirmed for a
visit and computes duration when presence is lost. Data is held in memory; not persisted
across HA restarts. The ring buffer rebuilds over time after a restart.

---

## Outdoor lux as debounced trigger

When an `outdoor_lux_signal` state change is received:
- If the room is currently occupied
- And there is an active `room_smart_lighting_assist` rule with that `outdoor_lux_signal`
→ schedule a lighting evaluation after a debounce (default 60 s, configurable via
  `outdoor_lux_trigger_debounce_s` in learning options).

Indoor lux state changes do **not** trigger a lighting evaluation cycle.

---

## Room type catalog

Default timeout values used when no installer override is provided.

| room_type | base_timeout_min | fast_exit_timeout_s |
|---|---|---|
| bagno | 2 | 30 |
| cucina | 4 | 45 |
| corridoio | 1 | 15 |
| ingresso | 1 | 15 |
| studio | 6 | 60 |
| soggiorno | 8 | 90 |
| sala_da_pranzo | 6 | 60 |
| tinello | 4 | 45 |
| camera_da_letto | 5 | 60 |
| cameretta_bambini | 5 | 90 |
| lavanderia | 3 | 20 |
| ripostiglio | 1 | 15 |
| garage | 3 | 30 |
| generic | 5 | 45 |

If `room_type` is not specified in the rule config, `generic` defaults apply.

---

## Removed types

`room_darkness_lighting_assist` and `room_contextual_lighting_assist` are removed in Phase AB
with no migration path (hard cut). The engine raises a config error if either type is
encountered in `options.reactions.configured`.
