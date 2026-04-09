# Heima — People Presence Rules SPEC
## Presence Contribution Semantics for Canonical People

**Status:** Draft target for next implementation slice  
**Last Updated:** 2026-04-09

This document defines how canonical Heima people contribute to global presence signals such as:
- `anyone_home`
- `people_count`
- `people_home_list`

It introduces `presence_rule` as an explicit per-person contract.

---

## Scope

In scope:
- `presence_rule` values and semantics
- contribution to global presence aggregates
- options-flow behavior for canonical people
- diagnostics and migration expectations

Out of scope:
- device-tracker selection logic inside Home Assistant `person.*`
- detailed semantics for `people_debug_aliases`
- future policy differences beyond presence aggregation

---

## Product Goal

Not every Home Assistant `person.*` should contribute to global household presence in the same way.

Examples:
- a tablet permanently left at home should not keep `anyone_home = true`
- core residents should count normally
- frequent but non-core residents should still be tracked and counted when present, while remaining
  distinguishable from core residents

Heima therefore needs a first-class per-person rule instead of forcing admins to abuse
`presence_method` for exclusion.

---

## Data Model

Each canonical person in `people_named` SHOULD support:
- `presence_rule`

Allowed values:
- `observer`
- `resident`
- `recurrent`

If the field is missing, the runtime MUST treat it as:
- `resident`

Recommended shape:
```yaml
people_named:
  - slug: stefano
    display_name: Stefano
    person_entity: person.stefano
    presence_method: ha_person
    presence_rule: resident
```

---

## Rule Semantics

### `observer`

Use for:
- devices or identities that should be tracked in Heima
- people-like entities that must remain visible/debuggable
- presences that MUST NOT contribute to household occupancy aggregates

Normative behavior:
- the person state MAY still be normalized and exposed individually
- the person MUST NOT contribute to:
  - `anyone_home`
  - `people_count`
  - `people_home_list`
- the person MUST remain visible in diagnostics and per-person runtime state

Example:
- tablet permanently in the house

### `resident`

Use for:
- normal household members

Normative behavior:
- the person contributes normally to:
  - `anyone_home`
  - `people_count`
  - `people_home_list`

This is the default rule.

### `recurrent`

Use for:
- frequent non-core household presences
- recurring family members or guests who stay for short periods but still matter operationally

Normative behavior for v1:
- the person contributes to:
  - `anyone_home`
  - `people_count`
  - `people_home_list`
- the person remains distinguishable from `resident` in config, diagnostics, and future policy work

Interpretation:
- `recurrent` counts as present
- `recurrent` is not excluded
- `recurrent` exists so future house-state and policy logic can distinguish “core resident” from
  “recurring non-core resident” without breaking aggregate presence semantics now

---

## Aggregate Presence Contract

Let:
- `counted_people_home` = canonical people currently `home` with `presence_rule in {resident, recurrent}`
- `observer_people_home` = canonical people currently `home` with `presence_rule = observer`

Normative rules:
- `anyone_home` MUST be true when:
  - at least one `counted_people_home` exists, or
  - anonymous presence logic independently marks the house occupied
- `people_count` MUST count only:
  - `resident`
  - `recurrent`
  - any separately counted anonymous presence contribution already defined by the runtime
- `people_home_list` MUST include only:
  - `resident`
  - `recurrent`
- `observer` MUST NOT appear in `people_home_list`

Recommended diagnostics:
- expose both:
  - counted people
  - excluded observer people currently home

---

## Config Flow UX

The canonical `People` edit form SHOULD expose:
- `presence_rule`

Recommended labels:
- `Observer`
- `Resident`
- `Recurrent`

Recommended help text:
- `Observer` → tracked but excluded from household presence aggregates
- `Resident` → normal household member
- `Recurrent` → recurring non-core resident, still counted as home

The field belongs only to canonical `People`.
It MUST NOT replace the separate `people_debug_aliases` model.

---

## HA-Backed Import And Reconciliation

For imported canonical HA people:
- Heima SHOULD materialize `presence_rule = resident` by default

Reconciliation rules:
- reconciliation MUST preserve a reviewed `presence_rule`
- reconciliation MUST NOT silently reset `observer` or `recurrent` back to `resident`
- if a legacy person has no `presence_rule`, migration/defaulting MUST treat it as `resident`

---

## Runtime Expectations

The runtime SHOULD distinguish:
- per-person normalized state
- aggregate presence contribution

Normative direction:
- `presence_rule` affects aggregate presence contribution
- `presence_rule` does not suppress individual person evaluation

Implication:
- an `observer` person can still appear as `home`
- but that state is observational only and excluded from global presence aggregates

---

## Diagnostics And Observability

Diagnostics SHOULD expose for each canonical person:
- `slug`
- `person_entity`
- `presence_method`
- `presence_rule`
- whether the person is currently counted toward household presence

Recommended summary fields:
- `counted_people_home`
- `observer_people_home`
- `excluded_observer_count`

This is important because `observer` intentionally creates a difference between:
- “this person-like entity is home”
- “this entity should count for household presence”

---

## Migration

Migration target:
- existing `people_named` entries without `presence_rule` MUST behave as `resident`

This keeps backward compatibility and prevents silent behavior change for existing households.

---

## Future Direction

This spec deliberately keeps v1 semantics conservative:
- `resident` and `recurrent` both count as home
- only `observer` is excluded

Future policy work MAY use `presence_rule` to differentiate:
- house-state promotion thresholds
- notification routing
- heating/security preferences
- guest-aware automation behavior

Those future differences are not part of this slice.
