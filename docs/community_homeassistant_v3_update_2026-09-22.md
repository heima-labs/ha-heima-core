# Home Assistant Community Post Draft - Heima v3 Architecture Update

Title: Heima v3 architecture update: facts, learning, semantics, and safe reactions

Hi everyone,

I wanted to share a design update on Heima v3. This is still specification work, not a release
announcement, but the architecture is now concrete enough that feedback would be useful.

The short version: Heima v3 keeps Home Assistant as the source of truth for entities, schedules,
service calls, and device behavior, while adding a stricter internal model for facts, provenance,
learning, semantic state, review workflow, and actions.

The current v3 draft has nine logical layers:

```text
Layer 8  Admin / config surface
Layer 7  Extensibility
Layer 6  Notification / communication
Layer 5  Action / reaction generation
Layer 4  Semantic resolution
Layer 3  Learning / pattern recognition
Layer 2  Registries
Layer 1  Substrate primitive
Layer 0  Cross-cutting runtime facilities
```

The important progress is that Layers 0-4 are now defined enough to stop being vague architecture
boxes:

- Layer 0: timing, persistence, provenance, manual holds, recovery/checkpoint, runtime health.
- Layer 1: the durable `HouseFact` model: WHAT/WHERE/WHEN/HOW, with typed provenance.
- Layer 2: registries for `Sensor`, `FusionRule`, and `Actuator`.
- Layer 3: historical learning/pattern recognition, running off the hot path.
- Layer 4: semantic resolution: current claims such as room occupancy, house presence, and scoped
  activities.

Layer 5 then consumes the immutable post-semantic snapshot and decides whether a configured policy may
act. The key rule is that learning never acts directly:

```text
learning result -> proposal candidate -> Layer-5 validation -> ReactionProposal -> admin review
-> configured policy -> current snapshot evaluation -> admissibility -> ApplyStep
```

## What changed in Layer 5

Two recent clarifications are important.

First, `ReactionProposal` is not a `HouseFact`. It is a persisted Layer-5 governance record: admitted
canonical payload, candidate/template contract identity, source evidence references, a bounded
redacted evidence snapshot, and review state.

Its review dispositions are:

- `pending`
- `accepted`
- `rejected`
- `proposal_incompatible`

`accepted`, `rejected`, and `proposal_incompatible` are terminal. A compatible learning refresh may
update evidence for a pending proposal, but cannot change scope, action bundle, guard profile,
template/version, candidate identity, or review state. If evidence is stale, the proposal stays
pending but is not approvable until refreshed.

Acceptance revalidates against the current registries/topology/actuators/guards, creates a configured
policy in `notification_only`, records actor/time/reason/policy id, then marks the proposal accepted.
Promoting that policy to automatic action is a later, separate authenticated step.

Second, Layer 2 still does not become a Home Assistant capability catalog. Home Assistant remains the
authority for concrete service schemas and runtime support. Heima stages only a narrow semantic
admission contract:

- this actuator has this logical channel;
- this channel has this semantic channel kind;
- this channel has this observable-state contract;
- this channel has this actuation adapter binding.

Layer 5 can then say: "this policy intent may use this channel kind and adapter." It later translates
the semantic intent into an `ApplyStep`; Home Assistant still validates the concrete service call when
it is applied.

## Still open

Layer 5 still has three design areas to finish:

1. The exact `relation_profile` schema: temporal inputs, semantic guards, windows, units, guard
   operators, and whether learner/policy profiles are one shared versioned artifact or two named
   concepts.
2. The exact persisted `ReactionProposal` fields: identity, dedup fingerprint, evidence references,
   redacted audit snapshot, validity interval, review actors, diagnostics, and compatibility metadata.
3. The final semantic intent -> `ActuatorChannel` -> `ApplyStep` mapping, including audit for partial
   bundle execution.

One principle is already fixed: one `ApplyStep` addresses exactly one Layer-2 actuator endpoint. A
known-invalid bundle member blocks the whole bundle before any command is sent. If Home Assistant
fails after some steps were already sent, Heima records a partial outcome and does not invent automatic
compensating commands.

## Why I am posting this here

The design goal is not to make Home Assistant less flexible. Home Assistant already gives us the
flexible entity/service/schedule world. Heima v3 is trying to add a stricter layer above it where
learned suggestions, semantic state, manual holds, safety gates, review workflow, and action
provenance stay explainable over months of real household use.

I am especially interested in feedback on:

- whether the separation between HA capability validation and Heima semantic action admission makes
  sense;
- whether `ReactionProposal` as a governance/workflow record, rather than a fact, feels right;
- whether starting accepted learned automations in `notification_only` is the right safety default;
- what people would expect to see in the admin UI when a learned proposal is stale, incompatible, or
  blocked by current safety/hold/capability conditions;
- whether the remaining Layer-5 questions match the failure modes experienced Home Assistant users
  would worry about.

Again, this is not released yet. The value right now is getting the architecture honest before turning
it into implementation.
