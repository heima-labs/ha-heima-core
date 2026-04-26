# Heima Investor UI Development Plan

Status: Draft  
Scope: Investor-facing UI delivery plan for admin and non-admin surfaces  
Target: v1.x demo slice

## Purpose

Heima needs a UI slice that is not merely functional, but presentable in an investor setting.

The goal of this plan is to turn the existing UI specs into a bounded development sequence that produces:

1. a strong non-admin product surface
2. a credible admin/operator surface
3. a stable demo flow that can be shown live without relying on raw diagnostics or ad-hoc explanation

This plan is intentionally product-first. It is not a generic dashboard cleanup effort.

## What The Existing Specs Already Give Us

The current UI specs are materially stronger on the non-admin side than on the admin side.

### Strong Inputs Already Available

- `heima_non_admin_dashboard_spec.md`
  - defines the primary household surface
  - includes information architecture, tone, exclusions, and success criteria
- `heima_view_entities_specification.md`
  - defines the canonical UI contract
- `heima_view_model_builder_spec.md`
  - defines the semantic translation layer from canonical runtime outputs to UI entities
- `heima_display_interface_specification.md`
  - defines kiosk/display architecture and device behavior
- `heima_monitoring_spec.md`
  - defines operator-facing monitoring layers and daily/debug/audit intent

### Current Imbalance

The non-admin surface is already specified as a product surface.

The admin surface is not.

Today the admin/operator experience is spread across:

- options flow
- diagnostics scripts
- debug dashboard YAML
- monitoring spec

This is enough for development and testing, but not enough for an investor-grade admin console.

## Product Surfaces Needed For An Investor Demo

The investor demo should be designed around exactly three surfaces.

### 1. Non-Admin Home Surface

Audience:

- household user
- guest
- investor observing product clarity

Purpose:

- show what Heima understands right now
- show what matters without exposing internals
- establish trust, calmness, and product coherence

Primary source of truth:

- `heima_non_admin_dashboard_spec.md`
- semantic view entities

### 2. Admin Control Surface

Audience:

- installer
- advanced owner
- operator
- investor evaluating product seriousness

Purpose:

- show that Heima is configurable, inspectable, and controllable
- expose proposals, reactions, key automations, and operational state
- avoid feeling like a raw Home Assistant entity browser

Primary source of truth today:

- `heima_monitoring_spec.md`
- options flow specs
- production/debug dashboard examples

Gap:

- there is no canonical admin dashboard spec yet

### 3. Demo/Display Surface

Audience:

- live investor presentation
- kiosk/tablet mode

Purpose:

- ensure the product can be shown cleanly on a fixed device
- guarantee deterministic recovery after idle, browser refresh, or restart

Primary source of truth:

- `heima_display_interface_specification.md`

## Gaps We Need To Close

### Gap A: Non-Admin Spec Exists, But The Runtime UI Contract Is Not Yet The Real Daily Surface

The semantic view-model direction is correct, but it is only valuable if the dashboard actually consumes it.

Today the example dashboards are still much closer to monitoring/operator surfaces than to the intended end-user product surface.

### Gap B: Admin Surface Is Operational, Not Presentational

The current monitoring/debug assets are good for engineering.

They are not yet a strong investor-facing admin console because they still read as:

- diagnostics-first
- entity-first
- debug-first

rather than:

- product control center
- system value overview
- confidence-building operator surface

### Gap C: The Story Between The Two Surfaces Is Not Yet Deliberately Choreographed

For an investor demo, the UI cannot just be "good screens".

It needs a sequence:

1. non-admin clarity
2. admin control and intelligence
3. learning/proposal credibility

### Gap D: Visual System Is Under-Specified Relative To The Stakes

The non-admin spec gives direction, but we still lack a bounded design system for the investor slice:

- typography choices
- color rules
- spacing rhythm
- card hierarchy
- state styling
- icon discipline
- empty/error state treatment

Without this, the implementation risks looking like a polished YAML dashboard rather than a product.

## Investor UI Strategy

The investor slice should not try to solve every UI problem in Heima.

It should solve exactly this:

1. make the non-admin surface feel like a real product
2. make the admin surface feel serious and controlled
3. make both surfaces share one coherent visual language

This means:

- no raw-entity-first dashboard design
- no debug surfaces shown as the main product
- no "everything in one page" approach
- no over-expansion into rarely used settings during the investor slice

## Development Plan

## Phase 1: Lock The Investor Demo Surface Model

Deliver:

- confirm the three-surface model:
  - non-admin home
  - admin control center
  - debug/investigation surface kept separate
- define which surface is shown in which part of the demo
- define the minimum set of entities, cards, and actions per surface

Acceptance:

- we can explain the product demo in under one minute without opening raw diagnostics
- each surface has a bounded purpose and no role confusion

Notes:

- this phase is mostly product/system design, not frontend implementation

## Phase 2: Implement The Semantic View Layer End-To-End

Deliver:

- real implementation of the view-model builder
- production of:
  - `sensor.heima_home_view`
  - `sensor.heima_insights_view`
  - `sensor.heima_security_view`
  - `sensor.heima_climate_view`
  - `sensor.heima_room_<room_id>_view`
- localization and formatting behavior aligned with spec

Acceptance:

- the non-admin dashboard can be built almost entirely from semantic view entities
- the UI layer no longer needs to reconstruct meaning from raw Heima entities

Notes:

- this is the highest leverage technical step for the non-admin surface

## Phase 3: Build The Investor-Grade Non-Admin Dashboard

Deliver:

- a single canonical non-admin dashboard implementation
- aligned with:
  - `heima_non_admin_dashboard_spec.md`
  - `heima_display_interface_specification.md`
- polished hierarchy:
  - hero
  - quick actions
  - rooms
  - insights
  - security
  - climate

Acceptance:

- a non-admin user can understand house state, comfort, safety, and key actions in seconds
- the dashboard looks intentional and product-like on tablet and desktop
- the dashboard does not expose diagnostics, raw proposal JSON, or technical noise

Non-goals:

- full feature parity with the admin/operator surface

## Phase 4: Define And Build The Admin Control Center

Deliver:

- a new canonical admin surface spec
- a production-like admin control center implementation

The admin control center should include:

- house state and health summary
- proposal backlog
- configured reaction summary
- key family status
- recent learning/progress summary
- bounded entry points into:
  - reactions
  - proposals
  - scheduled routines
  - security presence simulation

It should not be:

- the raw debug dashboard
- a full diagnostics dump
- an entity browser

Acceptance:

- an operator can demonstrate configuration and operability without leaving the admin surface
- an investor can see that Heima is inspectable and governable, not opaque

Notes:

- this is the biggest missing spec today
- this phase should produce both spec and implementation

## Phase 5: Separate Debug Surface From Presentation Surface

Deliver:

- retain the debug dashboard as an engineering tool
- reduce its role in the investor story
- ensure admin surface links into debug/investigation only when needed

Acceptance:

- the demo never depends on raw diagnostics as a primary UX
- engineering visibility remains intact

## Phase 6: Kiosk And Presentation Hardening

Deliver:

- tablet/kiosk setup aligned with display spec
- startup/reload recovery behavior
- inactivity return behavior
- stable theme and layout on the chosen device
- demo-safe test house or live house configuration

Acceptance:

- the investor demo can survive refresh, restart, or navigation mistakes
- the display returns to a known usable state deterministically

## Phase 7: Demo Narrative Hardening

Deliver:

- a bounded, repeatable investor demo path
- preconfigured scenarios that show:
  - current house understanding
  - reaction intelligence
  - proposal/learning credibility
  - admin oversight

Acceptance:

- the demo can be run end-to-end without improvising through engineering tools

## Recommended Implementation Order

This is the recommended sequence:

1. Phase 1
2. Phase 2
3. Phase 3
4. Phase 4
5. Phase 6
6. Phase 7
7. Phase 5 in parallel where useful

Rationale:

- the semantic view layer is the key dependency for a strong non-admin surface
- the admin control center should be built deliberately, not by polishing the debug dashboard
- kiosk hardening matters only after the real dashboard surfaces exist

## Immediate Next Slice

The next slice should be:

1. formalize the missing admin control center spec
2. assess whether the view-model builder exists in code or is still mostly spec-only
3. identify the minimum data contract needed to build the non-admin dashboard without raw entity logic

Concretely, the next development task should answer:

- which view entities already exist in code
- which must still be implemented
- which current dashboards can be retired or demoted once the investor surfaces are ready

## Success Criteria For The Investor Slice

The investor UI work is successful if:

- the non-admin surface feels like a consumer product, not a Home Assistant dashboard
- the admin surface feels trustworthy, bounded, and powerful
- the product can be demonstrated without leading with diagnostics
- both surfaces share a coherent visual and information architecture

The investor UI work is not successful if:

- the main demo still depends on raw entities and debug cards
- the admin story is just "look how many diagnostics we have"
- the non-admin surface looks like a themed entity board
- the visual system is inconsistent across user and admin surfaces
