# Admin-Authored Automation Spec

**Status:** v1 improvement target  
**Scope:** Admin-authored automations alongside learned proposals in Heima v1  
**Related:** `learning_system_spec.md`, `proposal_lifecycle_spec.md`, `core/reactive_behavior_spec.md`

## 1. Goal

Heima v1 currently learns automations from observed behavior and presents them as proposals for review.

This spec defines a second, parallel channel:

- the HA admin can request an automation directly
- Heima helps author it
- Heima can later propose tuning or follow-up on the authored automation

The goal is not to replace learned proposals, but to extend the system with an explicit admin-authored path.

## 2. Core Model

Heima should treat automations as having an `origin`:

- `learned`
- `admin_authored`
- `hybrid` for future combined cases

An automation is still a reaction configuration at runtime, but its origin matters for:

- UI wording
- review and ownership
- tuning suggestions
- lifecycle tracking

## 3. Admin-Authored Flow

The admin-authored flow is a request-driven path:

1. the HA admin states the intent
2. Heima translates that intent into a candidate automation
3. the admin reviews and confirms the generated configuration
4. the confirmed automation is stored as an authored reaction configuration

This path is distinct from learned proposals because it starts from a human request, not from an observed pattern.

## 4. Lifecycle

Admin-authored automations should keep a small lifecycle, separate from learned proposal lifecycle.

Recommended states:

- `draft`
- `confirmed`
- `active`
- `tuning_requested`
- `retired`

Meaning:

- `draft`: Heima has prepared a candidate automation, but it has not been confirmed yet
- `confirmed`: the admin approved the authored automation
- `active`: the automation is in use at runtime
- `tuning_requested`: Heima has detected a possible refinement and is asking for a human decision
- `retired`: the automation should no longer be considered active

In v1, these states can remain conceptual or diagnostic as long as the runtime still stores a simple reaction configuration plus origin metadata.

## 5. Relation to Learned Proposals

Learned proposals and admin-authored automations should share the same runtime reaction system, but not the same source semantics.

Shared:

- `ReactionProposal` shape or a closely related review artifact
- reaction configuration persistence
- acceptance/rejection workflow
- diagnostics and explanation payloads

Different:

- learned proposals come from observed behavior
- admin-authored automations come from explicit human intent
- tuning proposals for authored automations should be labeled as follow-up, not as a fresh learned pattern

## 6. Reaction Integration

Heima should not create a separate execution model for admin-authored automations.

At runtime, an authored automation should still become a normal reaction configuration, with metadata such as:

- `origin`
- `author_kind`
- `source_request`
- `created_at`
- `last_tuned_at`

This keeps the runtime consistent and avoids forking the execution model.

## 7. Tuning and Follow-Up

After an admin-authored automation is active, Heima can observe whether it matches reality well.

Heima may then propose:

- threshold adjustments
- schedule shifts
- room or device scope refinements
- split or merge suggestions
- disable/retire suggestions

These are not learned proposals in the strict sense. They are follow-up recommendations attached to an existing authored automation.

Recommended follow-up labels:

- `tuning_suggestion`
- `scope_refinement`
- `schedule_adjustment`
- `retire_candidate`

## 8. Ownership and Permissions

Only the HA admin should be able to create or confirm admin-authored automations.

This is a product-level rule, not a convenience rule:

- it protects high-impact automation choices
- it keeps the authoring path aligned with system trust boundaries
- it avoids accidental automation creation by non-admin users

## 9. UX Expectations

The UI should make the origin visible:

- learned proposal
- admin-authored automation
- tuning suggestion for an existing automation

The user should always be able to tell:

- where the automation came from
- whether it is still a draft or already active
- whether Heima is asking for initial approval or later tuning

## 10. Minimal v1 Increment

The smallest useful v1 step is:

- keep learned proposals as they are
- add an admin-authored request path
- reuse the existing reaction configuration machinery
- expose the `origin` concept in diagnostics and UI wording

No new behavior graph is required.
No new runtime engine is required.

## 11. Open Questions

Questions that should be answered before a larger implementation:

- should an authored automation have the same review UI as a learned proposal?
- should tuning suggestions be surfaced in the config flow or elsewhere?
- should `hybrid` be introduced only when both user intent and learning evidence materially contribute?
- should authored automations be allowed to spawn learned follow-ups automatically, or only after an explicit admin approval?

