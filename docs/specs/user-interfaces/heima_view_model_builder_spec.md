# Heima View Model Builder Specification (v1.0)

---

## 1. Purpose

This document specifies the **View Model Builder** — the component responsible for transforming Heima's canonical output signals into the localized view entities consumed by the UI.

The builder is the only authorized producer of view entities. No other component writes to `sensor.heima_*_view` or `sensor.heima_room_*_view`.

---

## 2. Position in the System

The builder is a post-engine layer. It runs after each Heima engine evaluation cycle and after any `input_select.heima_language` change.

```
[Heima Engine]
    ↓ canonical signals (heima_house_state, heima_security_state, ...)
[View Model Builder]
    ↓ localized, structured attributes
[View Entities]
    ↓ read-only
[UI Layer]
```

The builder is strictly **read-only** with respect to the engine. It reads canonical signals and writes view entities only. It never modifies domain state.

---

## 3. Canonical Input Sources

The builder reads exclusively from Heima canonical output signals. It never reads raw Home Assistant entities directly.

### 3.1 House State

| Canonical Signal | Type | Description |
|---|---|---|
| `heima_house_state` | `str` | Current house state |
| `heima_house_state_reason` | `str` | Human-readable reason string |
| `heima_house_state_path` | `str` | Transition path label |
| `heima_anyone_home` | `bool` | Aggregate occupancy flag |
| `heima_people_count` | `int` | Number of people detected at home |
| `heima_people_home_list` | `list[str]` | Names or slugs of people at home |

### 3.2 Security

| Canonical Signal | Type | Description |
|---|---|---|
| `heima_security_state` | `str` | Normalized alarm state (`disarmed`, `armed_home`, `armed_away`) |
| `heima_security_reason` | `str` | Reason string for current security state |

### 3.3 Heating

| Canonical Signal | Type | Description |
|---|---|---|
| `heima_heating_state` | `str` | Heating domain output state |
| `heima_heating_phase` | `str` | Active phase (`heating`, `maintaining`, `idle`, ...) |
| `heima_heating_branch` | `str` | Decision branch label |
| `heima_heating_target_temp` | `float` | Current target temperature |
| `heima_heating_current_setpoint` | `float` | Setpoint currently applied |

### 3.4 Occupancy (per room)

| Canonical Signal | Type | Description |
|---|---|---|
| `heima_occupancy_<room_id>` | `bool` | Room occupancy state |
| `heima_occupancy_<room_id>_last_change` | `str` | ISO timestamp of last occupancy change |

### 3.5 Lighting (per zone)

| Canonical Signal | Type | Description |
|---|---|---|
| `heima_lighting_intent_<zone_id>` | `str` | Active lighting intent for zone (`auto`, `scene_relax`, ...) |
| `heima_lighting_hold_<room_id>` | `bool` | Manual hold active for room |

### 3.6 Reactions / Learning

| Canonical Signal | Type | Description |
|---|---|---|
| `heima_reaction_proposals` | `str/json` | Active improvement proposals |
| `heima_reactions_active` | `str` | Currently active reactions summary |

---

## 4. Output Entities

See `heima_view_entities_specification.md` for the full schema of each output entity.

| View Entity | Primary Canonical Sources |
|---|---|
| `sensor.heima_home_view` | `heima_house_state`, `heima_house_state_reason`, `heima_anyone_home`, `heima_people_count`, `heima_security_state`, `heima_heating_target_temp` |
| `sensor.heima_insights_view` | `heima_house_state_reason`, `heima_reaction_proposals`, `heima_reactions_active`, `heima_anyone_home` |
| `sensor.heima_security_view` | `heima_security_state`, `heima_security_reason` |
| `sensor.heima_climate_view` | `heima_heating_state`, `heima_heating_phase`, `heima_heating_target_temp`, `heima_heating_current_setpoint` |
| `sensor.heima_room_<room_id>_view` | `heima_occupancy_<room_id>`, `heima_occupancy_<room_id>_last_change`, `heima_lighting_intent_<zone_id>` (if zone mapped to room) |

---

## 5. Transformation Rules

### 5.1 heima_home_view

**State**: copy of `heima_house_state`

**title**: localized label for house state value

| heima_house_state | title (it) | title (en) |
|---|---|---|
| `home` | "Casa attiva" | "Home active" |
| `relax` | "Casa in relax" | "Home in relax mode" |
| `away` | "Nessuno in casa" | "Nobody home" |
| `sleeping` | "Casa in riposo" | "Sleeping mode" |
| `working` | "Modalità lavoro" | "Working mode" |
| `vacation` | "Vacanza" | "Vacation mode" |

**subtitle**: localized rendering of `heima_house_state_reason`

**pills**: ordered list of up to 4 items, built from available canonical signals:

1. formatted `heima_heating_target_temp` (if heating enabled)
2. localized security summary from `heima_security_state`
3. localized presence summary from `heima_anyone_home` + `heima_people_count`
4. additional contextual pill if available (e.g. heating phase)

**priority**: derived from:

* `critical` → security alert active (mismatch detected)
* `attention` → `heima_house_state` is `away` with open alerts
* `normal` → all other cases

### 5.2 heima_insights_view

**State**: `critical` if any item has severity `critical`; `attention` if any `warning`; `normal` otherwise.

**items**: up to 3 items, derived from:

* `heima_house_state_reason` → always included as base insight (severity `info`)
* `heima_reaction_proposals` → surface active proposals as insights (severity based on proposal type)
* occupancy duration: if `heima_anyone_home` is false, derive "Nessuno in casa da Xh Xm" from `heima_occupancy_*_last_change`

Items are ordered: `critical` first, then `warning`, then `info`. Truncated to 3.

### 5.3 heima_security_view

**State mapping**:

| heima_security_state | Condition | view state |
|---|---|---|
| `disarmed` | — | `ok` |
| `armed_home` | — | `ok` |
| `armed_away` | `heima_anyone_home` is false | `warning` |
| `armed_away` | `heima_anyone_home` is true | `alert` |
| any | mismatch reason active | `alert` |

**summary**: localized string derived from `heima_security_state` + `heima_security_reason`

**items**: static configured access point labels (defined per installation). Each item is a localized string expressing the state of a configured access point (e.g. "Ingresso chiuso"). The list of access points to include is part of builder configuration, not hardcoded.

**alerts**: populated only when `state == alert`. Derived from `heima_security_reason` when mismatch is active.

### 5.4 heima_climate_view

**State mapping**:

| heima_heating_phase | view state |
|---|---|
| `heating` | `heating` |
| `maintaining` | `comfort` |
| `idle` | `idle` |
| `cooling` | `cooling` |
| other / unavailable | `idle` |

**temperature**: formatted `heima_heating_current_setpoint` (or `heima_heating_target_temp` as fallback). Format respects locale.

**summary**: localized comfort assessment based on `heima_heating_phase`

**detail**: localized description of `heima_heating_branch`

**trend**: `stable` by default in v1. Trend computation (based on `heima_heating_current_setpoint` delta over time) is a v2 enhancement.

### 5.5 heima_room_<room_id>_view

**State mapping**:

| heima_occupancy_<room_id> | Condition | view state |
|---|---|---|
| `on` | — | `active` |
| `off` | last change < 30 min ago | `idle` |
| `off` | last change ≥ 30 min ago | `off` |

**title**: localized display name of room (from room configuration `display_name`, not raw `room_id`)

**line1**: primary status. If room is `active`, derive from lighting intent of the mapped zone (if available). If `idle` or `off`, use occupancy status string.

**line2**: secondary status. If lighting hold active (`heima_lighting_hold_<room_id>`), surface hold notice. Otherwise use contextual secondary string.

**features**: derived from available signals for the room:

* occupancy feature → state from `heima_occupancy_<room_id>`
* lighting feature → state from `heima_lighting_intent_<zone_id>` (if zone mapped)

**actions**: intent identifiers configured per room. Not derived from canonical signals.

---

## 6. Room-to-Zone Mapping

Room views may need to reference lighting zone signals. The mapping between `room_id` and `zone_id` is provided by builder configuration, which reads from Heima's room and lighting zone configuration options.

A room with no mapped zone will omit lighting-related content from `line1`, `line2`, and `features`.

---

## 7. Localization Pipeline

1. Builder reads `input_select.heima_language` at runtime
2. Language is passed to the string resolver
3. All string fields are resolved through the resolver before writing to view entities
4. Numeric values (temperature, humidity) are formatted by the resolver
5. The view entity **state** value remains language-neutral (e.g. `relax`, not `"Casa in relax"`)

---

## 8. Update Lifecycle

| Trigger | Action |
|---|---|
| End of engine evaluation cycle | Rebuild all view entities |
| `input_select.heima_language` change | Rebuild all view entities (no engine re-run) |

The builder skips writing an entity if the computed output is identical to the current state (avoid unnecessary HA state churn).

---

## 9. Error Handling

| Situation | Behavior |
|---|---|
| Canonical signal missing | Use safe localized fallback string; do not omit field |
| Language not supported | Fall back to `it` |
| Room has no canonical signals | Write empty `line1`/`line2` with fallback string; keep entity alive |
| Malformed canonical value | Log warning; treat as unavailable; apply fallback |

The builder must never raise an exception that prevents other view entities from being updated.

---

## 10. Implementation Notes

* The builder is a coordinator-level component, not a domain.
* It is invoked by the coordinator after each engine cycle.
* It does not participate in the engine DAG.
* It has no side effects on domain state.
* All string catalogs (translations) are static at v1; no external translation service is required.

---

## 11. Non-Goals

* The builder does not compute domain logic.
* The builder does not modify canonical state.
* The builder does not read raw HA entities.
* The builder does not expose debug or trace data through view entities.

---

END OF SPEC
