# Admin-Authored Automation Spec

**Status:** v1 improvement target  
**Scope:** Admin-authored automations alongside learned proposals in Heima v1  
**Related:** `learning_system_spec.md`, `proposal_lifecycle_spec.md`, `core/reactive_behavior_spec.md`

## 1. Goal

Heima v1 currently learns automations from observed behavior and presents them as proposals for review.

This spec defines a second, parallel channel that stays inside the same proposal/reaction system:

- the HA admin can request an automation directly
- Heima helps instantiate a precompiled proposal template
- Heima can later propose tuning or follow-up on the authored automation

The goal is not to replace learned proposals, but to extend the system with an explicit
admin-authored path whose capabilities are declared by the relevant plugin family.

## 2. Core Model

Heima should treat proposal/reaction artifacts as having an `origin`:

- `learned`
- `admin_authored`
- `hybrid` for future combined cases

An authored automation is still a normal reaction configuration at runtime, but its origin matters for:

- UI wording
- review and ownership
- tuning suggestions
- lifecycle tracking

The authoring capability is not universal. It is declared by the plugin family that owns the
proposal/reaction shape:

- `supports_admin_authored = true` means the plugin family MAY expose admin-authored templates
- `supports_admin_authored = false` means the family is learned-only unless the spec explicitly says otherwise
- template IDs, display labels, and schema fragments SHOULD come from the plugin declaration, not from a
  standalone automation builder

## 3. Admin-Authored Flow

The admin-authored flow is a request-driven path that still materializes a proposal inside the shared
proposal/reaction pipeline:

1. the HA admin states the intent
2. Heima selects a plugin-declared template and instantiates a candidate proposal
3. the admin reviews and confirms the generated configuration
4. the confirmed automation is stored as an authored reaction configuration

This path is distinct from learned proposals because it starts from a human request, not from an
observed pattern, but it is not a separate automation engine.

## 4. Lifecycle

Admin-authored automations do **not** introduce a separate runtime engine or a second state machine.
They share the same proposal lifecycle as learned proposals, with `origin = "admin_authored"` and
plugin provenance preserved in diagnostics.

Normative clarification:

- proposal system persisted status remains the standard v1 set:
  - `pending`
  - `accepted`
  - `rejected`
- admin-authored automations do **not** add a second persisted proposal status machine
- the labels below are UX/diagnostic labels only
- they MUST NOT replace or overload the persisted proposal `status` field

In v1, the following conceptual UX labels are sufficient:

- `draft` for a plugin-instantiated proposal awaiting admin confirmation
- `confirmed` for an accepted authored proposal
- `active` for the resulting reaction configuration at runtime
- `tuning_requested` for follow-up suggestions emitted later by Heima
- `retired` for an authored automation that should no longer be considered active

These labels are primarily UX/diagnostic labels. The runtime artifact remains a standard
`ReactionProposal` plus the accepted reaction configuration.

Recommended mapping:

- proposal `status = pending`, `origin = admin_authored` -> UX label `draft`
- proposal `status = accepted`, `origin = admin_authored` -> UX label `confirmed`
- configured reaction rebuilt from an accepted admin-authored proposal -> UX label `active`

`tuning_requested` and `retired` describe follow-up product states around the authored automation.
They are not proposal `status` values and should be modeled through diagnostics or linked
follow-up proposals rather than by extending the base persisted status enum in v1.

## 5. Relation to Learned Proposals

Learned proposals and admin-authored automations should share the same runtime reaction system, but not the same source semantics.

Shared:

- `ReactionProposal` shape or a closely related review artifact
- `origin` metadata
- reaction configuration persistence
- acceptance/rejection workflow
- diagnostics and explanation payloads

Different:

- learned proposals come from observed behavior and plugin analysis
- admin-authored automations come from explicit human intent and a plugin-declared template
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

These are not learned proposals in the strict sense. They are follow-up recommendations attached to
an existing authored automation and should still flow through the same proposal/reaction substrate.

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
- add an admin-authored request path that instantiates plugin-declared templates
- reuse the existing reaction configuration machinery
- expose the `origin` concept and plugin provenance in diagnostics and UI wording
- keep the authoring surface bounded to a small set of plugin-defined templates

No new behavior graph is required.
No new runtime engine is required.

## 11. Open Questions

Questions that should be answered before a larger implementation:

- should an authored automation have the same review UI as a learned proposal?
- should tuning suggestions be surfaced in the config flow or elsewhere?
- should `hybrid` be introduced only when both user intent and learning evidence materially contribute?
- should authored automations be allowed to spawn learned follow-ups automatically, or only after an explicit admin approval?
