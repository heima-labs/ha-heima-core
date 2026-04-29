# Heima Frontend Stack Plan

Status: Draft  
Scope: Investor-demo frontend stack for Home Assistant dashboards  
Target: v1.x UI presentation slice

## Purpose

This document fixes the frontend stack for the Heima investor demo.

The goal is not to explore the full Home Assistant custom-card ecosystem.
The goal is to choose a bounded stack with a high visual ceiling, low integration risk,
and a clear implementation order.

## Decision

The recommended stack for the investor slice is:

1. `Mushroom`
2. `layout-card`
3. `card-mod`
4. `browser_mod`
5. `button-card` only where Mushroom is not sufficient

This is the preferred path for both:

- the non-admin home surface
- the future admin control center

## Roles

### 1. Mushroom

Primary role:

- default card vocabulary
- high-quality baseline visuals
- tiles, chips, entity summaries, compact status surfaces

Why:

- much better visual baseline than native Lovelace
- good enough for most cards
- reduces the amount of bespoke YAML needed

Usage guidance:

- use as the default first choice
- do not replace it with `button-card` unless there is a clear visual reason

### 2. layout-card

Primary role:

- real layout control
- responsive section composition
- stable tablet/desktop arrangement

Why:

- native layout control is too weak for a serious investor-facing surface
- Heima needs deliberate hierarchy, not a generic card flow

Usage guidance:

- use for page-level and section-level layout
- define a small number of stable dashboard layout templates

### 3. card-mod

Primary role:

- visual refinement
- spacing, radius, shadows, background surfaces, typography tweaks

Why:

- needed to make the dashboard feel product-like instead of default Home Assistant

Usage guidance:

- use sparingly and systematically
- prefer shared styling rules over one-off per-card hacks
- do not encode business logic in CSS/template tricks

### 4. browser_mod

Primary role:

- bounded popup/detail experiences
- kiosk/tablet browser control
- investor-demo navigation safety

Why:

- useful for room details, security detail, or secondary admin views
- useful for stable presentation on a dedicated device

Usage guidance:

- use for overlays and kiosk support
- do not use it as a substitute for information architecture

### 5. button-card

Primary role:

- bespoke hero cards
- premium quick action row
- selected high-value room cards if needed

Why:

- highest visual flexibility
- useful when Mushroom cannot reach the desired presentation quality

Usage guidance:

- use only for a small number of signature cards
- do not build the whole dashboard on `button-card`
- keep it as a precision tool, not the base framework

## Explicit Non-Choices

### Native Lovelace Only

Rejected as the main path.

Reason:

- too low visual ceiling for an investor demo
- too likely to read as “a Home Assistant dashboard” instead of a product surface

### Bubble Card As The Primary Stack

Rejected as the primary foundation.

Reason:

- visually strong, but too opinionated for the Heima visual direction
- less controlled fit for a calm, premium, product-grade domestic surface

### kiosk-mode

Rejected for new adoption.

Reason:

- archived
- not the right new dependency for a high-stakes demo

### button-card Everywhere

Rejected.

Reason:

- too much complexity
- too much YAML surface area
- too easy to create an unmaintainable custom frontend in disguise

## Implementation Order

## Phase F1

Install and validate:

- `Mushroom`
- `layout-card`
- `card-mod`
- `browser_mod`

Acceptance:

- all four resources load cleanly in the target HA instance
- no custom frontend errors
- test dashboard can reference all four

## Phase F2

Rebuild the non-admin home surface using:

- semantic `heima_*_view` sensors
- `layout-card` for structure
- `Mushroom` as primary card system
- `card-mod` for polish

Acceptance:

- the non-admin home surface feels clearly better than the current YAML reference
- it can be shown to a non-technical person without explanation of HA internals

## Phase F3

Evaluate the remaining visual gaps.

Decision point:

- if the hero and room cards are already good enough, stay on Mushroom
- if not, add `button-card` only for:
  - hero
  - quick actions
  - maybe room cards

Acceptance:

- bespoke cards remain bounded
- the dashboard does not become a button-card monoculture

## Phase F4

Apply the same stack to the admin control center.

Acceptance:

- shared visual language across admin and non-admin
- admin remains denser, but recognizably the same product

## Design Constraints

The stack must be used under these constraints:

- the semantic UI contract stays in the backend (`heima_*_view`)
- no reconstruction of core meaning in the frontend
- no raw diagnostics on the main non-admin surface
- no growing dependency list without a specific visual reason
- no parallel custom frontend app in this slice

## Success Criteria

The stack choice is successful if:

- the resulting UI looks like a product, not a themed HA board
- the implementation remains bounded and maintainable
- the non-admin and admin surfaces share a coherent visual language
- the investor demo does not depend on engineering-only dashboards

The stack choice is not successful if:

- the number of frontend dependencies keeps growing without discipline
- the YAML becomes too custom to maintain
- business logic leaks back into cards/templates
- the result still looks like a generic Home Assistant board
