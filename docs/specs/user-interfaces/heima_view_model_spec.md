# Heima View Model Specification (v1.2)

## Localization & Formatting Extension

---

## 1. Purpose

This document extends the View Entities Specification (`heima_view_entities_specification.md`) with rules for localization, formatting, and microcopy.

The goal is to ensure:

* UI is fully language-agnostic
* All user-facing text is precomputed by the builder
* Consistency across installations and language changes

---

## 2. Core Principle

> The View Model MUST expose fully localized, human-readable strings as entity attributes.

The UI must never:

* translate strings
* format values
* apply locale rules

All strings are resolved by the View Model Builder before being written to view entities.

---

## 3. Language Configuration

### Entity

```text
input_select.heima_language
```

### Supported values

* `it` (default)
* `en`

When the language changes, the View Model Builder recomputes all view entity attributes.

---

## 4. Localization Strategy

Localized strings are exposed as **attributes on view entities**, not as separate sensor entities.

Example — `sensor.heima_home_view` attributes after builder resolution:

```yaml
title: "Casa in relax"
subtitle: "Luci soft nel soggiorno, ambiente stabile"
pills:
  - "21,2 °C"
  - "Sicurezza ok"
  - "Nessuno in casa"
```

When language changes to `en`:

```yaml
title: "Home in relax mode"
subtitle: "Soft lights in the living room, stable environment"
pills:
  - "21.2 °C"
  - "Security ok"
  - "Nobody home"
```

The view entity state itself (`relax`) remains language-neutral.

---

## 5. Formatting Rules

### Numbers

| Locale | Format |
|---|---|
| `it` | `21,2 °C` |
| `en` | `21.2 °C` |

### Time

| Locale | Format |
|---|---|
| `it` | `18:42` |
| `en` | `6:42 PM` |

### Units

* Units are included in the formatted string
* Never passed as separate values for the UI to append

---

## 6. Microcopy Guidelines

### Tone

* Neutral
* Domestic
* Concise

### Length constraints

| Field | Max chars |
|---|---|
| `title` | 30 |
| `subtitle` | 60 |
| Insight `text` | 40 |
| Room `line1`, `line2` | 40 |

### Examples

```
✔ Sicurezza ok
✔ Nessuno in casa
✔ Garage occupato
✔ Riscaldamento in mantenimento

✘ Il sistema di sicurezza non presenta anomalie
✘ armed_away
✘ hvac_action: idle
```

---

## 7. Fallback Behavior

If localization fails or a source value is unavailable:

* fall back to default language (`it`)
* never return an empty string
* never expose raw canonical values (e.g. `armed_away`, `unknown`, `unavailable`)
* use a safe neutral string (e.g. `"Non disponibile"`)

---

## 8. Non-Goals

The View Model must NOT:

* expose translation keys
* expose structured multilingual objects (e.g. `{it: "...", en: "..."}`)
* require any UI processing
* produce separate entities per localized string

---

## 9. Summary

Localization is:

* centralized in the View Model Builder
* deterministic per language setting
* UI-independent

---

END OF SPEC
