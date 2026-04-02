# Proposal Lifecycle Spec

**Status:** v1 improvement target  
**Scope:** Learning proposal lifecycle in Heima v1  
**Related:** `learning_system_spec.md`

## 1. Goals

This spec tightens the lifecycle of learning proposals in Heima v1 without introducing a v2-style behavior graph or a large engine rewrite.

Goals:

- keep persisted review states minimal and stable
- support update-in-place for the same logical pattern
- make proposal recency and staleness explicit
- reduce duplicate proposals caused by minor parameter drift
- keep proposal lifecycle centralized in `ProposalEngine`

## 2. Lifecycle Ownership

Lifecycle is owned by the learning core, primarily `ProposalEngine`.

Pattern analyzers:

- detect behavioral patterns
- emit `ReactionProposal`
- provide `learning_diagnostics`

`ProposalEngine`:

- deduplicates and refreshes proposals
- persists review state
- computes staleness and pruning eligibility
- exposes lifecycle diagnostics

This keeps lifecycle policy consistent across learning plugins.

Normative bridge clarification:
- `ProposalEngine` SHOULD remain the owner of persistence, merge ordering, refresh, and pruning
- but domain-specific lifecycle semantics SHOULD be delegated to plugin-owned hooks rather than
  being hardcoded on `reaction_type`

Required lifecycle hooks per proposal family SHOULD include:
- `identity_key(proposal)`
- `followup_slot_key(proposal)`
- `fallback_followup_match(existing, candidate, followup_slot_key)`
- `should_suppress_followup(candidate, accepted)`

Lifecycle applies equally to learned and admin-authored proposals. The `origin` of a proposal is
orthogonal to its review `status`; the same lifecycle rules should work for both unless a specific
plugin family documents a stricter exception.

## 3. Persisted States

Persisted proposal `status` remains:

- `pending`
- `accepted`
- `rejected`

The following are **not** primary persisted states in v1:

- `refreshed`
- `stale`
- `superseded`
- `archived`

These concepts may appear in diagnostics or pruning logic, but they do not replace the three review states above.

## 4. Logical Identity

### 4.1 Principle

Proposal identity must represent the **behavioral slot** of a pattern, not the latest estimate of its parameters.

Identity fields define "this is still the same proposal".

Evidence fields define "this proposal is now better supported or slightly shifted".

Lifecycle ownership rule:
- the definition of logical identity for a proposal family SHOULD live with that plugin family's
  lifecycle hooks, not as a central `ProposalEngine` branch on `reaction_type`

### 4.2 Identity vs Evidence

Fields suitable for logical identity:

- `reaction_type`
- `plugin_family`
- `room_id`
- `house_state`
- `weekday`
- `time_bucket`
- `primary_signal_name`

Fields that must remain evidence, not identity:

- `confidence`
- `observations_count`
- `weeks_observed`
- `episodes_*`
- `target_temperature`
- `median_arrival_min`
- `brightness`
- `color_temp_kelvin`
- `entity_steps`
- exact matched entity lists

For admin-authored proposals, template identifiers and plugin provenance belong with identity or
diagnostics only if they define the authored slot itself. Human-authored details that change over
time should remain evidence.

### 4.3 Built-in identity strategy

Built-in proposals should converge on these identity keys:

- `presence_preheat|weekday=<weekday>`
- `heating_preference|house_state=<house_state>`
- `heating_eco`
- `lighting_scene_schedule|room=<room_id>|weekday=<weekday>|bucket=<time_bucket_30m>|scene=<scene_signature>`
- `room_signal_assist|room=<room_id>|primary=<primary_signal_name>`
- `room_cooling_assist|room=<room_id>|primary=<primary_signal_name>`
- `room_air_quality_assist|room=<room_id>|primary=<primary_signal_name>`
- `room_darkness_lighting_assist|room=<room_id>|primary=<primary_signal_name>`

Composite domain clarification for the next iteration:
- the current composite identity remains intentionally coarse and room-scoped
- before the composite domain becomes fully domain-strong, identity SHOULD be reviewed so that:
  - materially different composite proposal families in the same room stay distinct
  - repeated evidence refreshes the same logical slot instead of creating noise
  - future tuning can target the correct active reaction without relying on brittle proposal wording
- any refinement MUST remain plugin-owned and SHOULD avoid reintroducing central branching in
  `ProposalEngine`

Composite proposal quality clarification:
- for composite proposal families, not every observed entity list change should become a new core
  proposal payload
- support thresholds SHOULD prefer ratios when the question is “how consistently is this element
  part of the pattern?”
- examples:
  - follow-up entities promoted into the proposal payload
  - optional corroboration signals promoted into the structural config
- absolute floors MAY still be used as guards, but SHOULD not be the only criterion when a
  percentage better represents stability
- these thresholds SHOULD come from a configurable analyzer policy, even if v1 initially uses
  built-in defaults
- if multiple composite candidates still emerge for the same logical slot in one analysis pass,
  the analyzer SHOULD retain only one dominant representative candidate
- a dominant-candidate choice SHOULD prefer stronger evidence and clearer stability, for example:
  - higher confidence
  - more confirmed episodes
  - more corroborated episodes when relevant

### 4.4 Lighting time bucket

For v1, lighting schedules use a **30-minute time bucket** in logical identity.

This is intentionally coarser than exact `scheduled_min` to reduce duplicate proposals caused by minor drift.

Normative clarification:
- proposals that remain inside the same lighting identity bucket SHOULD normally refresh the same
  logical proposal rather than creating bucket-local near-duplicates
- if multiple generated lighting candidates land in the same bucket during one analysis run, the
  analyzer SHOULD prefer one stable representative candidate unless the competing candidates have a
  materially different entity set or payload
- lighting identity MUST therefore include a stable `scene_signature` derived from normalized
  `entity_steps`, not only `(room_id, weekday, time_bucket)`
- `scene_signature` SHOULD be coarse enough to tolerate minor drift in brightness / color
  temperature while still separating materially different scenes in the same bucket
- matching the same lighting slot is NOT by itself sufficient to create a `tuning_suggestion`
- if the candidate differs from the accepted lighting reaction only by minor drift, v1 SHOULD
  suppress the follow-up instead of surfacing review noise

Recommended v1 `minor drift` examples:
- schedule drift within roughly 5 minutes
- small brightness drift for the same entity set
- small color temperature drift for the same entity set

## 4.5 Review wording for lighting proposals

For lighting-specific review UX, wording SHOULD distinguish clearly between:

- `discovery`
  - a newly learned lighting automation candidate
- `tuning_suggestion`
  - a follow-up change over an already active lighting automation

Normative guidance:
- review titles for lighting discovery SHOULD read as a new learned automation, not a generic proposal
- review titles for lighting tuning SHOULD read as an adjustment of an existing automation, not a second discovery
- the same distinction SHOULD be visible both in proposal review wording and in lighting-specific diagnostics summaries

## 5. Lifecycle Fields

In addition to current timestamps, proposals should carry:

- `identity_key`
- `last_observed_at`

Diagnostics may also expose:

- `is_stale`
- `stale_reason`
- `stale_after_s`

For v1, `is_stale` and `stale_reason` can be derived at runtime and do not need to become primary persisted status fields.

## 6. Refresh Rules

When a new generated proposal matches an existing proposal by `identity_key`:

- if existing proposal is `pending`:
  - update `confidence`
  - update `description`
  - update `suggested_reaction_config`
  - update `updated_at`
  - update `last_observed_at`
- if existing proposal is `accepted` or `rejected`:
  - keep review `status`
  - do not create a duplicate proposal
  - v1 may keep accepted/rejected proposals frozen, or update only observational metadata in diagnostics if later needed

This avoids introducing `superseded` for ordinary parameter drift.

## 7. Staleness

`stale` in v1 is a **derived lifecycle condition** for `pending` proposals.

A `pending` proposal is stale when:

- it has not been observed again for longer than a configured threshold

Initial v1 guidance:

- stale is shown in diagnostics
- stale does not change persisted `status`
- stale may later influence pruning

## 8. Pruning

Pruning is separate from status.

Initial v1 direction:

- keep `pending` proposals visible
- allow pruning of very old stale `pending` proposals
- keep bounded retention for `accepted` and `rejected` history

Exact thresholds remain an implementation policy and can be tuned after production observation.

## 9. Why `superseded` is deferred

`superseded` is deferred in v1 because better logical identity plus update-in-place should remove most duplicates that would otherwise require a superseded status.

Only if real-world review flows still produce overlapping proposals for the same logical slot should `superseded` be introduced later.

## 10. Implementation Order

Recommended slices:

1. add `identity_key` and built-in logical identity strategy
2. add `last_observed_at` and refresh semantics
3. expose derived staleness in diagnostics
4. add conservative pruning for very old stale pending proposals

## 11. Source Notes

This proposal is consistent with temporal recommender and drift literature:

- Yehuda Koren, *Collaborative Filtering with Temporal Dynamics*  
  DOI: `10.1145/1557019.1557072`  
  https://cacm.acm.org/research/collaborative-filtering-with-temporal-dynamics/

- Zhang et al., *Timeliness in recommender systems*  
  DOI: `10.1016/j.eswa.2017.05.038`  
  https://www.sciencedirect.com/science/article/abs/pii/S0957417417303603

- Hsu & Li, *Handling sequential pattern decay: Developing a two-stage collaborative recommender system*  
  DOI: `10.1016/j.elerap.2008.10.001`  
  https://www.sciencedirect.com/science/article/abs/pii/S1567422308000446

- Abdallah et al., *A systematic review on recommender system and concept drift*  
  https://eprints.utm.my/92558/

- Yao et al., *A novel temporal recommender system based on multiple transitions in user preference drift and topic review evolution*  
  DOI: `10.1016/j.eswa.2021.115626`  
  https://www.sciencedirect.com/science/article/pii/S0957417421010204
