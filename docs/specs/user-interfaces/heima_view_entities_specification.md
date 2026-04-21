# Heima View Entities Specification

## Canonical View Model for UI Consumption (v1.1)

---

# 1. Purpose

This document defines the **canonical data contract** between the Heima core and any user interface (Home Assistant dashboard, custom panel, or external frontend).

It specifies:

* which entities Heima exposes
* their structure
* their semantics
* constraints and guarantees

This is a **product-level contract**, not an implementation detail.

The view entities are produced by the **View Model Builder** layer, which reads exclusively from Heima's canonical output signals — never from raw Home Assistant entities. See `heima_view_model_builder_spec.md`.

---

# 2. Design Principles

## 2.1 UI-Agnostic Contract

The view model must be consumable by:

* Lovelace dashboards
* custom HA panels
* external applications

## 2.2 Fully Resolved Output

All entities must expose:

* human-readable text
* already localized values
* formatted data

The UI must not:

* compute logic
* format values
* translate strings

---

## 2.3 Deterministic Structure

Each entity must:

* have a fixed schema
* respect field constraints
* avoid optional ambiguity

---

## 2.4 Minimal Entity Set

The system exposes:

* few entities
* rich attributes per entity (not separate attribute entities)

---

# 3. Entity Naming Convention

View sensor entities follow:

```text
sensor.heima_<domain>_view
```

Room view entities follow:

```text
sensor.heima_room_<room_id>_view
```

Where `<room_id>` is the user-configured slug as defined in Heima's room configuration (e.g. `soggiorno`, `camera`, `cucina`, `garage`). There is no canonical fixed room set.

---

# 4. Core View Entities

## 4.1 Home View

### Entity

```text
sensor.heima_home_view
```

### State

Mirrors `heima_house_state` canonical values:

```text
home | relax | away | sleeping | working | vacation
```

### Attributes

```yaml
title: string           # localized house state label, ≤ 30 chars
subtitle: string        # localized explanation of current state, ≤ 60 chars

pills: list[string]     # max 4 localized summary strings

status:
  temperature: string   # formatted temperature string (e.g. "21,2 °C")
  security: string      # localized security summary
  presence: string      # localized occupancy summary

priority: normal | attention | critical
last_update: timestamp
```

### Constraints

* `title` ≤ 30 chars
* `subtitle` ≤ 60 chars
* `pills` max 4 items, each ≤ 30 chars
* `status.temperature` is a formatted string, never a raw float

### Example

```yaml
state: relax
title: "Casa in relax"
subtitle: "Luci soft nel soggiorno, ambiente stabile"
pills:
  - "21,2 °C"
  - "Sicurezza ok"
  - "Nessuno in casa"
status:
  temperature: "21,2 °C"
  security: "Sicurezza ok"
  presence: "Nessuno in casa"
priority: normal
last_update: "2026-04-20T18:42:00+02:00"
```

---

## 4.2 Insights View

### Entity

```text
sensor.heima_insights_view
```

### State

```text
normal | attention | critical
```

### Attributes

```yaml
items:
  - text: string              # localized insight string, ≤ 40 chars
    severity: info | warning | critical
```

### Constraints

* max 3 items
* ordered by severity descending, then by recency
* text ≤ 40 chars per item

### Example

```yaml
state: normal
items:
  - text: "Nessuno in casa da 1h 12m"
    severity: info
  - text: "Meteo fallback attivo"
    severity: info
```

---

## 4.3 Security View

### Entity

```text
sensor.heima_security_view
```

### State

View abstraction over `heima_security_state` canonical values:

```text
ok | warning | alert
```

Mapping from canonical:

| heima_security_state | heima_security_view state |
|---|---|
| `disarmed` (no mismatches) | `ok` |
| `armed_home` | `ok` |
| `armed_away` + anyone home | `alert` |
| mismatch detected | `alert` |
| `armed_away` | `warning` |

### Attributes

```yaml
summary: string         # localized one-line state description

items: list[string]     # localized structured access point states (2–4 items)

alerts: list[string]    # localized active alerts (empty when state is ok)
```

### Rules

* `alerts` empty → state is `ok` or `warning`
* `alerts` not empty → state is `alert`
* `summary` always consistent with state

### Example (ok state)

```yaml
state: ok
summary: "Tutto regolare"
items:
  - "Ingresso chiuso"
  - "Garage chiuso"
  - "Allarme disinserito"
alerts: []
```

---

## 4.4 Climate View

### Entity

```text
sensor.heima_climate_view
```

### State

View abstraction over `heima_heating_phase` canonical values:

```text
comfort | heating | cooling | idle
```

### Attributes

```yaml
temperature: string     # formatted indoor temperature (e.g. "21,0 °C")
humidity: string        # formatted humidity if available (e.g. "52%"), else omitted

summary: string         # localized comfort assessment
detail: string          # localized heating system behavior

trend: stable | rising | falling
```

### Rules

* `temperature` is a formatted string, never a raw float
* `humidity` is omitted entirely if no humidity signal is available
* no historical data exposed
* no graph data exposed

### Example

```yaml
state: heating
temperature: "21,0 °C"
humidity: "52%"
summary: "Comfort buono"
detail: "Riscaldamento in mantenimento"
trend: stable
```

---

## 4.5 Room View

### Entity Pattern

```text
sensor.heima_room_<room_id>_view
```

`<room_id>` is the user-configured slug from Heima room configuration. Examples: `soggiorno`, `camera`, `cucina`, `garage`.

### State

View abstraction over `heima_occupancy_<room_id>`:

```text
active | idle | off
```

| heima_occupancy_<room_id> | room_view state |
|---|---|
| `on` | `active` |
| `off` (recently active) | `idle` |
| `off` (long inactive) | `off` |

### Attributes

```yaml
title: string           # localized room display name

line1: string           # primary localized status line, ≤ 40 chars
line2: string           # secondary localized status line, ≤ 40 chars

features:
  - type: string        # feature type (e.g. "lighting", "occupancy")
    state: string       # localized feature state

actions:
  - action: string      # intent identifier (e.g. "heima_relax", "heima_buonanotte")
```

### Constraints

* `line1`, `line2` ≤ 40 chars
* max 2 lines populated
* `actions` contain intent identifiers only, never service calls
* `title` is the localized display name, not the raw `room_id`

---

# 5. Actions (Intent Layer)

## Entities

```text
script.heima_relax
script.heima_buongiorno
script.heima_buonanotte
script.heima_ospiti
```

These are HA script entities, not view sensors. They are part of the UI contract as the exclusive action surface.

## Rules

* UI invokes only these scripts
* no direct service calls from UI
* scripts encapsulate all Heima domain logic

---

# 6. Localization

## Language Entity

```text
input_select.heima_language
```

## Rules

* all string attributes in view entities must be pre-localized by the builder
* UI must not translate
* fallback language is `it`
* numeric formatting must respect locale (decimal separator, units)

---

# 7. Data Guarantees

The system guarantees:

* no empty critical fields
* no raw unformatted values (e.g. no `armed_away`, no `hvac_action`, no `unknown`)
* consistent attribute schema across updates
* stable entity naming

---

# 8. Update Model

Entities update:

* after each Heima engine evaluation cycle
* on `input_select.heima_language` change

Entities must:

* avoid unnecessary churn (only publish if values changed)
* expose `last_update` on `heima_home_view`

---

# 9. Error Handling

If a canonical source is unavailable:

* fallback to safe localized string (e.g. "Non disponibile")
* never expose `unknown`, `unavailable`, or raw HA state strings
* degrade gracefully: partial data is acceptable, missing schema is not

---

# 10. Non-Goals

The view model must not:

* expose raw HA entities or states
* require UI computation or translation
* include debug data in user-facing fields
* expose internal Heima reasoning traces

---

# 11. Extensibility

New domains must:

* follow the `sensor.heima_<domain>_view` naming convention
* provide structured localized attributes
* be produced by the View Model Builder, not by the domain itself

---

END OF SPEC
