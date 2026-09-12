# Heima v3 — Backlog & Findings Log

Working notes for the v3 "whole-engine" reasoning pass (sensors, actuators, reactions,
proposals, notifications, config surface). Not a spec. Items get promoted into a real
spec once scope converges; until then this is where evidence and open questions live so
nothing gets lost across sessions.

Branch: `feat/v3-planning` (isolated worktree, based on `main` at `04a02a1`, created to avoid
colliding with the parallel session working on Phase AX on `feat/ax-topology-climate-reactions`).

Draft shapes live in separate files, cross-referenced from here:
`docs/v3_house_fact_draft.md` (`HouseFact`, `Provenance`, `Timing`, `Zone`, `Location`),
`docs/v3_sensors_actuators_draft.md` (`Sensor`, `Interpretation`, `FusionRule`, extended `Actuator`),
`docs/v3_template_matching_draft.md` (`TemplateRequirement`, the generic proposal matcher — the
original kitchen-automation idea that opened this whole conversation, closed the loop).

---

## Foundational model — representing "the house"

Starting point (developer, 2026-08-29): before touching sensors/actuators/reactions as currently
implemented, define how Heima represents a house at all, and what's needed for awareness of what
happens in it — along three axes the developer named directly: **what** (cosa), **how** (come/how
confident), **when** (quando). Two more axes came up while grounding this against the current
code:

- **where** (dove/space) — decided **2026-08-29: promoted to a first-class axis**, same rank as
  what/how/when.
- **who** (chi/person) — decided **2026-08-29: stays out of scope**, consistent with the existing
  documented household-level-not-per-person limitation.

### What already exists per axis (grounded in code, not invented)

**WHAT** — no common parent type. Coexisting, unrelated: raw HA entity state, room signal bucket
(plain string), `Activity` (pattern + context dict), `HouseState` (canonical enum), per-room
occupancy bool, `HeimaEvent` (type/key/severity/context — has an actual taxonomy,
`event_catalog_spec.md`), ~15 `reaction_type` values.

**HOW** — 4 incompatible "how much do I trust this" shapes:
1. `NormalizedObservation`/`DerivedObservation` ([normalization/contracts.py:14-40](custom_components/heima/runtime/normalization/contracts.py#L14-L40)) — richest: `kind/state/confidence(int)/raw_state/source_entity_id/ts/stale/available/reason`. Only used for boolean house signals + evidence-count signals. NOT used for room signal buckets (no confidence/staleness at all) or `media_active` (bespoke function, no Observation).
2. `InferenceSignal`/`HouseStateSignal`/etc. ([inference/signals.py](custom_components/heima/runtime/inference/signals.py)) — `confidence(float)+importance(enum)+source_id`, for learned predictions.
3. `ReactionProposal`/`SignalSuggestion`/`DiscoveredBindingCandidate` — each owns its own `confidence` field, three separate dataclasses.

**WHEN** — 6 separate temporal vocabularies, no shared "time window" type: `on_dwell_s`/`off_dwell_s`, candidate `active_for`/`inactive_for`, `weekday`+`hour_bucket` (house-state proposal identity), `correlation_window_s`/`followup_window_s` (composite patterns), `burst_window_s`/`burst_direction` (signal bursts), `vacancy_delay_min`.

**WHERE** — the best-modeled axis today: Room Topology (Phase AR — adjacency graph, openings,
orientation) is solid, but under-consumed (Phase AT, "Room Topology Consumers", `DEFERRED` —
HouseState/Occupancy/Security don't read it yet). Gaps confirmed by reading `room_topology.py`:
`TopologyGraph` has no "whole house" root node (only a reserved `outside` room_id — see
`ROOM_ID_RESERVED_OUTSIDE`/`OUTSIDE`), and "a named set of rooms" only exists today as
`lighting_zones` (`OPT_LIGHTING_ZONES`), scoped to lighting, not a general topology concept.

### Decisions (2026-08-29)

1. **`HouseFact` must be the actual substrate, not a bolt-on.** A version where existing shapes
   (room signal bucket, `InferenceSignal`, `ReactionProposal.confidence`, `HeimaEvent`) keep
   existing independently and `HouseFact` merely exists alongside them solves nothing — it becomes
   a 5th competing shape. To be worth it, `HouseFact` (what/where/when/how) must be what those
   internally build from. This means rewriting most of `runtime/` internal plumbing (normalization,
   confidence tracking, temporal bucketing) — domain-facing contracts (the DAG, `HouseState` enum,
   `Activity`, reaction identity) can stay conceptually stable at the surface. Developer confirmed:
   optimize for genuinely clean v3 architecture, full rewrite is acceptable if that's what it takes
   — do not default to the less-invasive option just to save work.
2. **New cross-cutting "Timing" subsystem**, same rank as Manual Hold Manager / Recovery-Checkpoint
   (outside the DAG, per architecture invariant #14). Provides the shared "when" primitive(s) the
   3 existing temporal concepts derive from (duration/dwell/window, recurrence pattern
   weekday+hour_bucket-style, correlation/followup window) instead of each subsystem inventing its
   own — and *also* subsumes periodic/scheduled task execution. Today there are 3 separate temporal
   execution mechanisms unified into one (see item 4 below): `RuntimeScheduler`, `scheduled_routine`,
   and the engine's 300s fallback poll.
3. **WHERE is never absent.** Whole-house facts belong to "casa" by definition — `casa` becomes an
   explicit node in the topology model (doesn't exist today; confirmed no naming collision).
4. **Timing execution model: cron-on-top-of-at.** One execution primitive ("at" — a one-shot
   deadline job; `RuntimeScheduler` already essentially is this, `runtime/scheduler.py`), and a
   "cron" policy layer on top: a `RecurrencePattern` computes the next due time and re-arms an "at"
   job each time it fires. This absorbs `scheduled_routine` and the engine's 300s periodic fallback
   as cron entries; `RuntimeScheduler`-style rechecks (e.g. `house_state.py`'s
   `_schedule_candidate_recheck`) become plain "at" jobs through Timing. Confirmed by reading
   `coordinator.py:1901-1923`: the 300s fallback (`_schedule_periodic_fallback` /
   `_async_run_periodic_fallback`) is *already* mechanically a self-rescheduling one-shot
   `async_call_later` timer that triggers a full engine re-evaluation (`_trigger_eval`) — folding it
   into cron as a system-owned entry costs nothing mechanically, it only changes labeling/framing.
   Its purpose (invariant #11: bounded-staleness safety net against missed state_changed events or
   purely wall-clock-driven conditions with no dedicated job) stays valid either way.
   **Confirmed 2026-08-29: folded in as a system-owned cron entry**, no special-casing outside Timing.
   Separately, `Duration`/`Window` (dwell timers, composite `correlation_window_s`/
   `followup_window_s`) is **not** an execution concept — it's a comparison/relation over `HouseFact`
   timestamps, no scheduler involved.
   Execution primitives were already built directly on HA's own `async_call_later` (`RuntimeScheduler`
   and the periodic fallback both do) — the gap was never "not using HA", it's 3 independent call
   sites wrapping the same HA primitive instead of one internal layer. HA's native `schedule.*` helper
   entity (weekly recurring on/off blocks, own editor UI) is a real candidate for `scheduled_routine`
   reactions to delegate to instead of Heima maintaining its own weekday/time picker — trade-off:
   recurrence definition would live outside Heima's config flow, in an HA helper the admin creates
   separately. Not yet decided whether to adopt this for `scheduled_routine`.
5. **Zone: Heima-owned, HA Label registry as discovery input only (not a live dependency) —
   confirmed.** Mirrors the existing Room/Actuator pattern (Heima-owned record with `area_id` as a
   soft reference used only for discovery/suggestion, per `discovery.py`, never a hard runtime
   dependency). Rejected: Zone = HA Label registry directly. Reasons: HA's label registry is global
   and outside Heima's lifecycle control (a label renamed/deleted from HA's generic UI would silently
   break a Heima zone-dependent reaction — same fragility class as the `media_player` domain-mismatch
   bug fixed this week); no place to attach Heima-specific per-zone semantics on a bare label; label
   granularity (area vs. device vs. entity) doesn't map cleanly to "which rooms are in this zone"
   without extra normalization anyway; testing would need registry mocks instead of the plain-dict
   fixtures Room/Actuator tests already use. Confirmed available regardless: HA Floor registry
   (2024.2+) and Label registry (2024.4+), both well within `hacs.json`'s declared min HA version
   (2025.1.0) — no compatibility blocker, just not the chosen ownership model.
   **Confirmed 2026-08-29:** a Room can belong to several Zones at once (flexible, not exclusive
   partitioning — e.g. `cucina` can be in both a `piano_terra` zone and a `zona_giorno` zone). Zones
   are **not** nestable for v3 — a Zone composes Rooms directly only, no Zone-of-Zones. `casa`
   already serves as the implicit top-level root; recursive nesting is premature complexity without
   a concrete driving use case, revisit later if one appears.
6. **HOW closed: `Provenance` as the single epistemic value, becomes `HouseFact`'s "how" field.**
   Fields: `confidence`, `source` (entity_id, or analyzer_id/plugin_id for derived/learned facts),
   `freshness` (fresh/stale/unavailable — unifies today's separate `stale`+`available` booleans on
   `NormalizedObservation` into one tri-state), `evidence` (supporting detail: raw_state,
   fusion_strategy, inputs — today's `DerivedObservation` fields). This fully absorbs
   `NormalizedObservation`/`DerivedObservation` ([normalization/contracts.py](custom_components/heima/runtime/normalization/contracts.py))
   as standalone types — they become `HouseFact` instances with a populated `Provenance`.
   Grounded in reading `inference/signals.py` and `analyzers/base.py`: the 3 "HOW" shapes found
   earlier turned out to be one pipeline of increasing epistemic maturity, not 3 arbitrary variants
   — raw `Observation` → `InferenceSignal` (immediate-decision signal) → `ReactionProposal`
   (durable, human-reviewed change). Two things confirmed as deliberately **separate** from
   `Provenance`, not folded in:
   - **`importance`** (today's `Importance` enum: OBSERVE/SUGGEST/ASSERT, on `InferenceSignal`)
     stays distinct from `confidence` — "how sure" and "how much authority this has over the
     decision" are different questions; two signals can share confidence but differ in importance.
     `importance` decorates the inference-signal use of a Fact, not every Fact.
   - **Proposal review `status`** (pending/accepted/rejected, on `ReactionProposal`) stays out of
     `Provenance` entirely — it's human governance state, not epistemic trust. Proposals are
     `HouseFact + Provenance` wrapped with a review-status + identity/fingerprint (for dedup), not
     part of the universal "how" shape every Fact carries.
   Cross-axis reuse: `InferenceSignal.ttl_s` (today a bare int) becomes a `Duration` from the Timing
   subsystem (item 4) instead of its own field; `ReactionProposal`'s `created_at`/`updated_at`/
   `last_observed_at` (today 3 separate ad hoc timestamps) map onto Timing's temporal tracking
   rather than being reinvented per-proposal.

**All four axes (what/how/when/where) now have a converged direction.** Concrete draft shapes for
`HouseFact`/`Provenance`/`Timing`/`Zone`/`Location` are in `docs/v3_house_fact_draft.md`, including
the resolved `Location.scope == "rooms"` case (ad hoc/anonymous multi-room facts, confirmed
2026-08-29) for facts scoped to dynamically-observed room combinations that aren't a declared Zone.

---

## House State vs. Activity — what learning is actually *for* (2026-08-30)

Developer position: `HouseState` (and `HouseFact`) are core architecture, not a side concern — worth
getting right deliberately rather than leaving as-is.

### What house-state learning does today (traced precisely, not assumed)

In `_resolve_home_substate` ([house_state.py](custom_components/heima/runtime/domains/house_state.py)):
the learned signal (`_select_learned_house_state_signal`) is consulted **only in the final residual
branch**, after override/vacation/guest/away/sleep-candidate/relax-candidate/work-candidate have
*all* already failed to resolve. It never overrides a rule that fired. It can only ever return one
of 4 fixed values (`HOUSE_STATES_HOME_SUBSTATES` = sleeping/relax/working/home,
[const.py:170-174](custom_components/heima/const.py#L170-L174)) — structurally incapable of
inventing a new state, confirmed by the `signal.predicted_state in _HOME_SUBSTATES` filter.
Confirmed against real data: several diagnostics snapshots do show `reason: learned_house_state_signal`
exactly in this residual case — it works as designed. But the volume behind it (544/570 total
proposals) is wildly disproportionate to a mechanism that only ever picks among 4 values for one
`else` branch — this mismatch is what triggered the deeper question.

### Why the fix isn't "open up HouseState's vocabulary"

Checked: `Activity` ([activity_domain.py:17-26](custom_components/heima/runtime/domains/activity_domain.py#L17-L26))
is **already** the open-vocabulary layer — `Activity.name` is a free string, not validated against a
closed enum, and architecture invariant #12 already documents `Activity.context: dict[str, Any]` as
"the only forward-compatibility hook" — deliberately designed for extensibility. `HouseState` is the
opposite by design: closed (`HOUSE_STATES_CANONICAL`, 7 values) and depended on as an exact-match
closed set by *other domains'* safety-relevant config — confirmed real examples:
`HEATING_HOUSE_STATES = list(HOUSE_STATES_CANONICAL)`, and the studio reaction's own
`suppress_on_states: ["away", "vacation"]` / `night_mode_states: ["sleeping"]`. Opening `HouseState`
to an evolving vocabulary would leave every one of those exact-match consumers with no defined
behavior for a state they don't recognize — a fail-open risk on security-relevant config, same class
of bug as the `boolean_signal()` charging gap.

Also checked: **neither layer currently does pattern discovery.** `Activity` has the right shape
(open name + context) but zero discovery mechanism — its only producers are 8 hand-written detectors
(dishwasher/oven/pc/tv/shower/stove/washing/power_media). `HouseState` has a discovery mechanism
(the learning pipeline discussed above) but it's structurally closed to 4 known values. The
capability the developer is asking for — learn genuinely new recurring behavior from the house and
propose it — doesn't fully exist at either layer today.

### Decision (2026-08-30): confirmed, split into two tracks

1. **`HouseState`'s vocabulary stays closed (7 values)**, but learning's role shifts to calibrating
   the *definitions* — per-household thresholds/timing/signal-weighting for when each of the 7
   states fires ("coordinate predefinite che si affinano" — predefined seed definitions, refined by
   observed behavior over time) — not proposing new state names. Resolves "modifichi gli stati
   durante l'uso" safely, without touching the closed-set contract every other domain depends on.
2. **New recurring-behavior discovery is genuinely new work, and belongs to `Activity`, not
   `HouseState`.** A discovery mechanism (doesn't exist today) observes patterns and proposes new
   named Activities for admin review — reusing the same Proposal/`HouseFact`/`Provenance`/status
   machinery already decided for everything else, not a bespoke pipeline. Once approved, a new
   Activity can *feed into* `HouseState` resolution as evidence (the same way `work_activity_evidence`
   already does today) — it never becomes a `HouseState` value itself.

This directly resolves the volume-vs-role mismatch found above: house-state learning's actual job
(track 1) doesn't need hundreds of weekday×hour×room proposals to do it — a much more compact,
continuously-calibrated model is the right shape; the rich, granular discovery work being done today
under `house_state_learned_context` more naturally belongs to track 2 (Activity discovery) once that
exists.

---

## Third-party plugin API (2026-08-30)

Developer wants v3 to evaluate enabling third-party Heima plugins — external developers extending
Heima **without modifying the core**. This reopens a decision already on record in `CLAUDE.md`:
*"Dynamic loading of third-party plugins is not supported... tied to the current product complexity
(attack surface, versioning, compatibility, support burden), not a definitive non-goal."* Treated
as a real reopening, not neutral ground — the four original reasons need addressing, not just
overriding.

**Push eliminated from scope, pull only** (developer decision, 2026-08-30) — collapses the
"a plugin can inject arbitrary facts whenever it wants" risk down to "the core still controls when
a plugin runs and what it sees," matching today's built-in domain model.

### Grounded in existing code — the extension seam already exists

`Engine.register_plugin(plugin: IDomainPlugin)` ([engine.py:738-749](custom_components/heima/runtime/engine.py#L738-L749))
is **already generic** — validates only duplicate `domain_id` and registration timing (rejects
after `finalize_dag()`), nothing else. `_ensure_domain_plugins_finalized()`
([engine.py:760-764](custom_components/heima/runtime/engine.py#L760-L764)) is what currently calls
it, but only for a hardcoded 3-item list (`builtin_domain_plugins()`: security/lighting/heating).
**The only structural gap is discovery** — something needs to call `register_plugin()` for
externally-sourced plugins without editing that hardcoded list. `register_plugin()`/`compute()`
today assume fully-trusted code (zero validation, zero fault isolation) — both are needed
specifically for third-party plugins, not for the trusted built-ins.

### Decisions

1. **Discovery mechanism — two options identified, not yet chosen**:
   - Python entry points (`importlib.metadata.entry_points(group="heima.plugins")`) — pip-native,
     same pattern pytest uses for its plugins, works naturally with HACS (same Python environment).
   - `hass.data` handshake — the plugin is itself an HA custom_component that finds Heima's engine
     instance in `hass.data[DOMAIN]` during its own `async_setup` and calls `register_plugin()`
     directly; needs an `after_dependencies` soft-dependency declaration for setup ordering. More
     idiomatic for how HA integrations already cooperate with each other.
2. **Fault isolation is required and has a direct precedent already in the codebase** — wrap each
   third-party plugin's `compute()` call in a try/except boundary; on failure, skip that plugin for
   the cycle and surface a diagnostic event instead of taking down the whole engine. Not a new
   pattern: `NormalizationFusionRegistry`'s fusion plugins already have exactly this
   (`used_plugin_fallback: fused.reason == "plugin_error_fallback"`, seen when grounding the Sensor
   Registry / `FusionRule` work) — generalize an existing mechanism, don't invent a new one.
3. **Version compatibility check at registration** — plugin declares which `HouseFact`/plugin-API
   version it targets; incompatible versions are rejected loudly at registration, never silently
   loaded broken.
4. **Two-tier capability model, declared by the plugin at registration**: `read_only` vs `apply`.
   - `read_only` plugins may only ever produce `HouseFact`s/signals. **Fail-closed enforcement**: if
     a `read_only`-declared plugin's `compute()` return value contains `ApplyStep`s anyway (bug or
     bad-faith), the core drops them and logs loudly — never executes them silently. Protects
     against a plugin lying about its own declared tier.
   - `apply` plugins may populate the `ApplyPlan` (command actuators) — the higher-stakes
     capability, gated below.
5. **`apply`-tier activation reuses Phase AH (Resident Runtime Confirmation & Auto-Apply
   Promotion), not a new mechanism.** A newly-registered `apply`-capability plugin is, structurally,
   the same shape as a runtime action awaiting auto-apply promotion — don't trust it immediately,
   notify the admin on first activation (reusing `runtime_confirmation_controller.py`'s existing
   actionable-notification machinery, found during the notifications audit), require explicit
   confirmation before its `ApplyStep`s are allowed through. Until confirmed, the plugin can still
   run in "shadow mode" (computes what it would do; those steps are dropped, not applied) — useful
   preview for the admin before deciding. Confirmation is **one-time and persisted** (an admin
   decision saved to options), not re-asked every cycle — consistent with how other admin decisions
   already persist in this codebase. Conceptually, a newly-registered `apply` plugin is itself a
   kind of pending Proposal (`status: pending`) — same review-status model already decided for
   `HouseFact`/`ReactionProposal` (item 6 above), not a bespoke gate.

### Open tension, not yet resolved

`CLAUDE.md`'s "No backward compatibility: sole user of the project" rule is incompatible with a
public third-party plugin API by definition — every future `HouseFact`/`IDomainPlugin` schema
change would need to consider breaking external plugins once any exist. If this ships, that rule
needs an explicit, conscious amendment (e.g. scoped to "no backward compat for internal-only
contracts; the plugin API surface gets real versioning discipline"), not a silent exception.

---

## `HouseFact` persistence model (2026-08-31)

Motivating question: `HouseFact` is said to "enable learning," but learning needs history — is
`HouseFact` ephemeral (computed fresh each cycle) or persisted? Grounded in what already exists
before proposing anything:

- **`EventStore`** ([event_store.py:139-145](custom_components/heima/runtime/event_store.py#L139-L145)):
  disk-persisted via HA `Store`, capped at `MAX_RECORDS = 5000` (count-based ring buffer, not
  time-based). Feeds analyzers for long(er)-term pattern mining.
- **`SnapshotBuffer`**: in-memory only, no disk backing, capacity-capped. Feeds short-term
  correlation/followup matching (composite reactions' `correlation_window_s`/`followup_window_s`).

These two already encode a **deliberate two-tier design**, not an accident — driven by architecture
invariant #2 ("no blocking I/O on the hot path"): correlation matching can't afford disk reads per
cycle, long-term learning can't afford to keep everything in memory forever.

### Three scenarios weighed

1. **Replace both with one unified `HouseFact` store.** Rejected — either imposes one retention
   policy on two genuinely different needs (risking I/O-on-hot-path violations for correlation
   matching), or the unified store just hides two tiers inside one class instead of two — no real
   complexity reduction, and the highest migration risk to the developer's live house's learned
   history.
2. **`HouseFact` builds on top of both** (same two-tier storage mechanics, unified payload type —
   `EventStore[HouseFact]`, a short-term buffer of recent `HouseFact`s instead of
   `DecisionSnapshot`s). **Selected.** Preserves the already-sound, invariant-driven two-tier
   architecture; still achieves "`HouseFact` is the real substrate" (consistent with the item 1
   decision on `Provenance`) without a competing 5th shape; lower migration risk since storage
   mechanics don't change, only the record type flowing through them.
3. **`HouseFact` coexists separately**, `EventStore`/`SnapshotBuffer` untouched, translated at the
   boundary. Rejected — reintroduces the exact "5th competing shape" problem already ruled out for
   `Provenance`, specifically in the place it matters most (what learning actually mines); ongoing
   translation-code maintenance/drift risk; forces third-party plugins to learn two different
   historical-query shapes instead of one.

### Resolving `DecisionSnapshot`'s aggregation — the developer caught a real flaw in the first pass

Initial framing of option 2 said `DecisionSnapshot` (a *bundle* of everything true at one instant,
not a single atomic fact) would need "decomposing" — developer correctly pushed back: that reads as
discarding a legitimate aggregate view purely to force atomicity, which is exactly backwards for a
system meant to also serve generic third-party consumers.

**Corrected resolution**: storage stays **always atomic** — one `HouseFact` per WHAT/WHERE/WHEN/HOW,
written at exactly the granularity the engine already computes at internally (per-room, per-signal —
not a new granularity being invented). A "snapshot" is never its own stored shape — it's a **query/
view reconstructed on read**: "every `HouseFact` true in `Location` X between t1 and t2." Composite
correlation matching does the same filter over the same in-memory short-term buffer it does today,
just over atomic `HouseFact`s instead of bundled `DecisionSnapshot`s — no added I/O, no invariant #2
violation, reconstruction cost is a filter over a small in-memory deque either way.

**Why this serves the third-party-plugin goal specifically** (the developer's stated motivation for
this whole thread): a plugin never needs to learn a bespoke bundle type (`DecisionSnapshot`) to read
Heima's history — it queries `HouseFact` by `fact_type`/`Location`/time window, the same generic API
every other consumer (including native learning) uses. Uniformity comes from *not* having
special-purpose aggregate storage shapes for special-purpose consumers — only atomic facts, with
composable read-time views on top.

---

## Configuration surface (2026-08-31)

Motivating question: with `Sensor`/`Zone`/`FusionRule`/third-party plugins as new first-class
concepts, how should v3's admin-facing configuration be organized so it doesn't reproduce today's
~20-flat-menu fragmentation under new names?

### What already exists — two UI technologies, and (corrected) two mutation patterns within one of them

Not just "20 config-flow menu items" — there are **two parallel UI surfaces** today:
HA-native options config flow (step-based forms, ~20 menu entries) and a separate custom admin
panel (`custom_components/heima/frontend/heima-admin-panel.js`, 3751 lines, 13 routes: activity,
actuators, confirmations, entities, health, holds, house_state, learning, notifications, proposals,
reactions, recovery, topology).

Within the panel, grounded by reading the JS (not assumed), there are **two distinct, already-live
mutation patterns** — first pass here missed the second one (grep only matched literal
`callWS({type: "..."})` strings, missing a call built from a variable):

1. **Dedicated per-registry endpoint** — `heima/actuators/action` / `heima/topology/action`. Full
   structural CRUD with its own validation, for genuinely relational/graph-shaped data (an actuator
   inventory, a room topology graph). A linear step-based form doesn't fit this shape well, which is
   presumably why these two got promoted out of config_flow to the panel already, without this ever
   being declared as an explicit rule.
2. **Generic action dispatcher** — `heima/observability/action` with an `action` discriminator
   (`review_proposal`, `review_proposal_batch`, `clear_manual_hold`, `review_runtime_promotion`,
   `reset_runtime_confirmation_promotion_state` — [heima-admin-panel.js:3600-3625](custom_components/heima/frontend/heima-admin-panel.js#L3600-L3625)).
   For discrete point-actions on existing objects — accept/reject/remove *one* proposal, clear *one*
   hold — not full CRUD. The house-state learning completion viz's "Remove" button (AW3) already
   goes through this, reusing the generic `review_proposal` wiring rather than a bespoke endpoint.
   **Correction to first pass**: this means proposal review already happens partly in the panel
   today, not only via config_flow's "Revisione proposte"/"Gestisci proposte accettate" steps — the
   migration below is completing something already half-done, not starting from zero.

### Decision (2026-08-31): declare the pattern that already emerged organically as the v3 rule

1. **`Sensor` Registry, `Zone`, `FusionRule` → panel, pattern 1** (dedicated CRUD endpoint, same
   shape as `heima/actuators/action`). Structurally identical to `Actuator` (entity + `Location` +
   role/`fact_type`) — same UI treatment, not a new pattern to invent.
2. **Proposal review (including new template-matching proposals from
   `v3_template_matching_draft.md`) → panel, pattern 2** (generic action dispatcher, already
   partly there). Complete the migration: remove "Revisione proposte"/"Gestisci proposte accettate"
   from config_flow once the panel fully covers it, rather than maintaining both.
3. **Config flow keeps genuinely linear, occasional-use settings**: notification delivery policy
   (recipients/groups/routes + the new 3-tier quiet-hours behavior), third-party plugin `apply`
   capability grants (Phase-AH-style one-time confirmation, still fits a simple form), general
   settings, calendar hookup. These don't benefit from a registry/graph editor — a step-based form
   is the right tool, not a compromise.

Not yet decided: whether `reactions` (currently split — creation via config_flow's "Crea
automazione", observability via the panel's `reactions` route, no dedicated mutation endpoint found
for it in the panel) should also move fully to the panel once `Sensor`/`Actuator`-driven template
matching reduces how often an admin needs the manual "Crea automazione" form at all.

---

## Observability, re-grounded — and a correction to `Provenance` (2026-08-31)

Motivating question: today's observability (admin panel, `diagnostics.py`, `learning_audit.py`,
per-domain `diagnostics()` dicts) is already mature — does it need re-grounding on `HouseFact`, and
what does that actually mean concretely?

**Finding: a large part of the answer already exists, and it forced a correction to `Provenance`
as drafted.** Phase AS ("Structured Runtime Source", `DONE`, spec `runtime_provenance_spec.md`)
already solved "how much do I trust where this came from" — for the *action* side. `ApplyStepSource`
([contracts.py:73-90](custom_components/heima/runtime/contracts.py#L73-L90)): `kind` + `source_id`
+ `source_type` + `actor_type` + `actor_id` + `correlation_id`, non-forgeable (structured
dictionaries built by untrusted code are sanitized into non-authoritative legacy sources), redacted
before diagnostics/persistence via a dedicated `as_redacted_dict()`. AS's own stated goal was
avoiding "a parallel `ApplyStep.provenance` field" — `Provenance.source: str` as originally drafted
(2026-08-29) would have been exactly that parallel field, from the fact side instead of the action
side, reintroducing the same problem AS was built to prevent.

**Correction applied to `v3_house_fact_draft.md`**: `Provenance.source` is now `FactSource` — reuses
`ApplyStepSourceKind`/`ApplyStepSourceActorType` as-is, extended with 3 new kinds facts need that
actions don't (`sensor`, `analyzer`, `third_party_plugin`), same `correlation_id` mechanism, same
`as_redacted_dict()` discipline. This also retroactively strengthens the third-party-plugin
fact-spoofing concern raised earlier (Third-party plugin API section) — AS's non-forgeability
guarantee already exists and is tested for actions; extending it to facts is precedented, not new
security surface to invent.

**This is the answer to "observability re-grounded"**: not a new explainability subsystem built on
top of `HouseFact` — it's **one structured-source vocabulary spanning both facts and actions**,
already half-built by AS. "Why is the house in this state" becomes: follow one `correlation_id`
chain from `HouseState` → the `HouseFact`s that fed its resolution (each carrying `FactSource`) →
any resulting `ApplyStep` (carrying `ApplyStepSource`, same vocabulary) → further downstream facts
if applicable. One thread, not two systems that happen to resemble each other.

Not yet decided: whether the admin panel's explainability views (the `entities`/`health`/`activity`
routes, etc.) should be rebuilt to walk this correlation-id chain directly, or whether this stays a
backend-level consistency win that surfaces through existing per-domain diagnostics views largely
unchanged. Lower priority than getting the `FactSource`/`ApplyStepSource` unification itself right.

---

## `Topology` placed in the architecture (2026-08-31)

Gap caught by the developer while reviewing the full architecture recap (`v3_architecture_recap.md`):
Room Topology (Phase AR — adjacency graph, openings, connection type, orientation, floor; already
the best-modeled WHERE-adjacent concept per the original axis grounding) had never been explicitly
placed relative to `Location`/`Zone` in anything drafted today.

**Decision**: `Topology` is a third, complementary piece of WHERE (Layer 1) — `Location` identifies
*which* place, `Zone` is an explicit admin-declared group, `Topology` is *how rooms relate
physically* (today's `TopologyGraph`, carried into v3 unchanged in shape). Not a fact producer or
`FusionRule` input by itself — it's context that `FusionRule`s, Reactions, and template requirements
can query. Extends `TemplateRequirement` (`v3_template_matching_draft.md`) with a third requirement
kind, `TopologyRequirement` (`needs_outdoor_connection`, `adjacent_room_type`), alongside
`SensorRequirement`/`ActuatorRequirement`.

**Direct connection to the parallel workstream**: this generalizes what Phase AX
("Topology-Aware Climate Reactions", in progress right now on `feat/ax-topology-climate-reactions`)
is hand-building for one specific case — cross-ventilation and weather-safety reactions keyed on
room adjacency/openings. Once `TopologyRequirement` exists, AX's climate reactions become a second
concrete template the generic matcher drives, the same relation the kitchen lighting case already
validated for `SensorRequirement`/`ActuatorRequirement` — not a coincidence, evidence the model
generalizes correctly. Worth keeping in mind when eventually reconciling this planning branch with
AX's work.

**`Zone` suggestions derive from `Topology` — confirmed 2026-08-31** (resolves the open question from
the original Zone discussion): discovery can propose Zones from topology structure (e.g. rooms
sharing a floor), the same suggestion-only relationship `Zone` already has with the HA Label
registry — never a live dependency, `Zone` stays plain Heima-owned data once created.

Updated: `v3_house_fact_draft.md` (new `Topology` section + `TopologyRequirement`),
`v3_template_matching_draft.md` (`TemplateRequirement.topology`, matcher signature),
`v3_architecture_recap.md` (Layer 1 and Layer 4).

---

## External review pass — gaps found by stepping outside the architecture (2026-08-31)

Developer prompt: "does v3 now completely and coherently describe a house? What's missing?" Five
gaps found, grounded in code, addressed one at a time in the given order.

### 1. `ExternalContext` — a 9th independently-invented entity-list pattern, missed all day

`ExternalContext` ([external_context.py:38-50](custom_components/heima/runtime/external_context.py#L38-L50)):
weather/adapter data (`outdoor_temp`, `outdoor_humidity`, `outdoor_lux`, `wind_speed`,
`wind_bearing`, `rain_last_1h`, `rain_forecast_next_6h`, `weather_condition`,
`weather_alert_level`, `weather_alert_phenomena`), populated from a `{slot: entity_id}` mapping
(`OPT_EXTERNAL_CONTEXT`) exactly like the 8 lists already collapsed into `Sensor` — but never
examined until this pass.

**Resolved 2026-08-31**: each slot becomes a `Sensor` (`fact_type: "external.<slot>"`,
`where: Location(scope="casa")`). The adapters themselves (OWM, Protezione Civile — separate HA
custom_components) are **not** a Layer-6 conflict — they're ordinary HA integrations exposing
ordinary entities, correctly just more `Sensor` input, not a competing extension mechanism.

**Bonus finding, not just a collapse**: `ExternalContext.is_slot_stale()`/`last_updated`/
`DEFAULT_STALENESS_MAX_AGE` does genuine **elapsed-time-based staleness detection** — checked, and
this does **not exist anywhere else** in the normalizer. `NormalizedObservation.stale` defaults to
`False` and is only ever propagated (`stale=any(obs.stale for obs in inputs)` during fusion,
[normalization/service.py:364](custom_components/heima/runtime/normalization/service.py#L364)),
never computed from elapsed time for a primary observation. **Decision**: generalize
`ExternalContext`'s time-based freshness computation into how `Provenance.freshness` gets computed
for *every* `HouseFact`, not just external ones — this closes a real, previously-invisible gap in
the base `Sensor`→`HouseFact` model itself, discovered only because of this collapse.

### 2. Manual Hold Manager / Recovery-Checkpoint — named since day one, never actually examined

Both named as Layer-0 peers of Timing from the start (architecture invariant #14) but neither was
revisited until this pass.

**Manual Hold Manager — resolved, genuine duplication, re-grounded**:
`ManualHoldScope(domain, subject_type, subject_id)` duplicates `Location` (plus a genuinely
orthogonal `domain` field — *which* functional domain, e.g. lighting, is suppressed, not just
where). `ManualHoldReason.source_entity` (free string) duplicates what `FactSource` already solves.
`ManualHoldState.expires_monotonic`/`release_policy` duplicates `Window`/`AtJob` (Timing).
`PendingApply` (expected_domain/state/attributes, `ttl`, `source_reaction_id/type`, `scope`) is
conceptually "an expected future `HouseFact`, within a Timing `Window`, sourced from a specific
`ApplyStepSource`." An active manual hold becomes a `HouseFact`
(`fact_type: "manual_hold.<domain>"`, `where: Location`,
`how: Provenance(source: FactSource(kind="resident_response", actor_type="resident"))`), expiry uses
`Window`/`AtJob` instead of a hand-rolled monotonic float.

**Recovery/Checkpoint — examined, confirmed as a legitimate exception, left untouched**:
`CheckpointEntityState` ([checkpoint_store.py:42-96](custom_components/heima/runtime/checkpoint_store.py#L42-L96))
is deliberately minimal — only allowlisted attributes, only critical entities, redacted by design —
built specifically to answer "did anything change while Heima was offline" cheaply after a restart.
Forcing this through the full `HouseFact`/`Provenance` shape would be over-engineering in the wrong
direction: the narrowness here is a deliberate safety/efficiency property, not accidental
duplication like the other cases found today. Not every "entity + state + timestamp" shape needs
collapsing — this one earns staying separate.

### 3. No `Device` concept — resolved, minimal addition

`Sensor`/`Actuator` are entity-keyed with no notion that two entities share one physical device.
Checked: HA's own Device Registry is **already** consulted elsewhere in the codebase
(`room_inventory.py:9-112`, via `dr.async_get(hass)`, grouping entities per device within an area
for inventory suggestions) — just never modeled inside the registries themselves.

**Resolved 2026-08-31**: no new Heima `Device` primitive — same "reference HA's native registry,
never a live dependency" pattern already used for `Zone`↔Label and `Zone`↔`Topology`. Add an
optional `device_id: str | None` field to both `Sensor` and `Actuator`, populated from HA's device
registry. Purpose: grouping in the panel UI (Layer 7 — show "these 3 entities are one physical
device" instead of a flat confusing list) and smarter discovery (registering one role from a device
suggests its sibling roles, e.g. a thermostat's temperature `Sensor` role suggests its `hvac_unit`
`Actuator` role too).

### 4. Presence as raw input — resolved, already fully covered by the existing model

Checked `InputNormalizer.presence()` ([normalization/service.py:48](custom_components/heima/runtime/normalization/service.py#L48)):
produces a `NormalizedObservation` with its own vocabulary (`kind="presence"`) — same shape as
`boolean_signal()`, different vocabulary. **Fits the existing model with zero new concepts**: a
4th `Interpretation` variant (`PresenceInterpretation`, sibling to the boolean/bucket/media-activity
ones already drafted), each presence entity is a `Sensor(fact_type="presence", where: casa)`, group
presence ("anyone home") is a `FusionRule` with the same quorum/weighted-quorum strategy already
designed for room occupancy. A person's `presence_rule` (observer/resident/recurrent) simply becomes
that person's weight inside `WeightedQuorumStrategy.weights` — no new field needed anywhere.

**Important clarification the developer raised, and it's structural, not just reassurance**:
unifying the *shape* (`Sensor`+`FusionRule`) does **not** unify the *timing policy*, and does not
introduce a shared blocking path. Room occupancy and whole-house presence become two independent
`FusionRule` instances, each with its own `Window` (dwell/hysteresis) — room occupancy keeps today's
existing default (`on_dwell_s=0`/`off_dwell_s=120s`: instant-on, debounced-off, already the real
default in `_steps_rooms.py` today, not a new invention), while whole-house presence can use a more
conservative `Window` independently, since a few seconds of latency there is fine (even desirable,
to avoid a GPS blip flipping `anyone_home`). They also already run in separate DAG domains today
(`OccupancyDomain` vs. `PeopleDomain`), evaluated independently per cycle — reusing the same
`WeightedQuorumStrategy`/`Window` *type* is reusing a pure-function-shaped piece of logic, not a
shared mutable service with contention. No risk of a dark room waiting several seconds for a light
that's driven by a shared "presence" pipeline — there isn't one.

### 5. Unit of measurement — resolved, lives on `Sensor`, not on `HouseFact`

Checked: `unit_of_measurement` isn't tracked anywhere today, not even by today's room-signal
buckets — a threshold like `{"label": "dark", "upper_bound": 30}` implicitly assumes lux with
nothing recording or checking that assumption. Same risk for temperature buckets
(`{"label": "cool", "upper_bound": 20}` assumes Celsius) — silently nonsensical on a Fahrenheit
install. This gap already existed in v2, not new to v3.

**Resolved 2026-08-31**: `unit: str | None` lives on `Sensor` (registration-time metadata, populated
from HA's `unit_of_measurement` at discovery), **not** on `HouseFact` — avoids bloating every fact
instance with a mostly-redundant string, consistent with `Interpretation` already owning "how to
decode the raw value." Used to **detect drift** (the entity's live unit no longer matches what it
was registered with) and flag it, not to perform unit conversion — HA already does that; Heima's
job is only to know and catch mismatches, fail-loud not silent, same philosophy as everywhere else
today.

### External review pass — closed

All 5 gaps resolved. Draft files updated: `v3_sensors_actuators_draft.md` (`Sensor.device_id`,
`Sensor.unit`, `Actuator.device_id`, `PresenceInterpretation`, the room-vs-house presence timing-
independence note), `v3_house_fact_draft.md` (`Freshness` computation generalized from
`ExternalContext`'s pattern). Manual Hold Manager re-grounding and `ExternalContext`'s collapse into
`Sensor` are captured above (items 1-2) but not yet reflected in dedicated draft file sections —
lower priority than the primitives themselves, revisit if/when this becomes a real spec.

---

## Lighting redesign (2026-08-31)

Developer prompt: "non mi è mai piaciuto sul serio" — full review of the lighting domain,
including external research into how mature/professional smart home systems handle it.

### Found: Lighting is two coexisting internal mechanisms today, not one

- **`LightingDomain`** (`runtime/domains/lighting.py`) — coarse, rule-based: `resolve_zone_intent`
  maps `house_state` + zone occupancy → an intent (evening/relax/night/off), then
  `pick_scene_for_intent_with_trace` applies a pre-configured HA scene per zone, with fallback
  chains (e.g. relax→evening if unconfigured).
- **`room_smart_lighting_assist`/`room_vacancy_lighting_off`** (`composite_room_assist` family) —
  precise, learned/admin-authored: per-room, lux-bucket + occupancy driven, per-entity
  brightness/color control.
- 13 files total touch "lighting" across domains/analyzers/reactions/behaviors/inference —
  confirms this is genuinely one of the richest, most organically-grown subsystems.

**Decision**: keep both, but make the relationship an explicit `PrecedenceStrategy` (the same
`FusionRule` strategy already decided for `workday_entity` and `HouseState`'s own resolution order,
not a new pattern) — `room_smart_lighting_assist` takes priority when configured for a room/zone;
`LightingDomain`'s coarse house_state→scene intent is the fallback default when no precise reaction
exists there. Not redundant, two legitimate tiers that were coexisting by historical accident
instead of by explicit design.

### External research findings (grounded via web search, sources in chat)

1. **Adaptive Lighting** (mature HA community project) validates the existing `PendingApply`
   expected-state-diff manual-override detection — already the right pattern, matches how a
   well-regarded real-world project does the same thing. Nothing to change there.
2. **Circadian/adaptive brightness+color-temperature by time of day** — established practice in
   serious smart homes, genuinely absent from Heima today (fixed brightness/color_temp per
   reaction, no time-of-day variation).
3. **Lutron's Occupancy vs. Vacancy Sensor distinction** — professional/code-driven practice:
   auto-on+auto-off vs. manual-on+auto-off-only (the latter sometimes code-required for certain
   room types, to avoid nuisance auto-on). Heima has no explicit vacancy-only mode today — the
   kitchen's "always-on regardless of lux" config from earlier in this conversation is a workaround
   achieving a similar effect, not a designed mode.
4. **HCI research** (arXiv 2408.04755): "false positives are judged most harshly" by users —
   validates the existing fast-on/slow-off dwell asymmetry and the case for vacancy-mode where
   appropriate; also validates today's `Provenance`/`FactSource` explainability investment
   ("people tolerate more errors when the process is transparent").
5. **Layered lighting design** (ambient/task/accent/architectural) — professional practice treats
   different light *functions* within a room differently; today's `actuator_role="light"` is flat,
   no distinction. Lower-priority finding, not resolved.

### Decision: circadian adaptation is delegated to Adaptive Lighting, not rebuilt in Heima

Not a Layer-6 third-party plugin (that's for code running inside Heima's engine via
`IDomainPlugin`) — Adaptive Lighting is a fully independent HA integration, composes at the entity/
service boundary exactly like the `ExternalContext` weather adapters (item 1 above): its own
entities become `Sensor`s if useful (e.g. `switch.adaptive_lighting_sleep_mode`), the physical light
stays the same `Actuator(role="light")` regardless of who else manages it.

**Critical compatibility requirement, not optional**: Adaptive Lighting only adapts a light when
`light.turn_on` is called *without* specifying color/brightness — an explicit-color call (which is
exactly what `room_smart_lighting_assist`'s `entity_steps` do today, e.g. the kitchen's fixed
`brightness: 190, color_temp_kelvin: 2850`) gets treated by AL as a manual override and **disables**
AL for that light until it's toggled off/on again. Composing with AL without addressing this would
silently break it on every Heima-triggered "on." Resolution: `entity_steps` needs a per-light choice
between "Heima sets brightness/color" (today's behavior, unchanged) and "defer to external adaptive
control" (send `action: on` only, no brightness/color params) — an option on the existing
`entity_steps` shape, not a new architectural layer.

### Decision: adaptive/learned dwell timing generalized into `Timing` itself

Motivating case: dwell time should adapt to how a room is actually used (quick in-and-out → fast
off; longer stays → don't turn off promptly) and low brightness when `house_state == sleeping`.
The house_state-conditioned brightness half is **already covered** by the existing model — a
Reaction (Layer 4) reading `HouseState` as one of its inputs alongside occupancy/lux is exactly what
was always intended; no new concept needed (though today's actual v2 implementation of this,
`night_mode_states`, conflates suppression and profile-selection in one field — worth untangling
when this gets built, not an architecture gap).

The adaptive-dwell half **is** a real architectural finding: today's `timeout_mode: "learned"` +
`ROOM_TYPE_DEFAULTS` seeds ([smart_lighting_assist.py](custom_components/heima/runtime/reactions/smart_lighting_assist.py))
is a bolt-on feature of exactly one reaction type. **Resolved**: added `LearnedWindow` to
`v3_house_fact_draft.md`'s Timing section — a `Window` variant that starts from a `seed` (today's
per-room-type defaults) and calibrates from observed `HouseFact` history over time, usable anywhere
a `Window` is used (dwell timers, correlation windows), not just this one reaction. Same principle
already decided for `HouseState`'s own definitions ("coordinate predefinite che si affinano"),
generalized rather than re-invented per use site.

---

## Heating redesign (2026-08-31)

Same review pattern applied to the next domain, per developer request ("rivediamo gli altri domini
uno alla volta").

### Found: the same disease as Lighting — parallel mechanisms deciding the same physical outcome

- **`HeatingDomain`** (905 lines, `runtime/domains/heating.py`) — branch-based, keyed by
  `house_state`: `disabled`/`scheduler_delegate`/`fixed_target`/`vacation_curve`
  (`HEATING_BRANCH_TYPES`). Coarse, rule-based, analogous to `LightingDomain`.
- **`HeatingPreferenceReaction`/`HeatingEcoReaction`** (`runtime/reactions/heating.py`) — checked:
  these are **fully independent reactions**, own `evaluate()`, own tolerance-matching, call
  `climate.set_temperature` **directly** on the same climate entity, with zero coordination with
  `HeatingDomain`'s branch computation. Structurally identical to Lighting's
  `room_smart_lighting_assist` running parallel to `LightingDomain` — except here it's actually
  riskier, since both paths can independently issue conflicting `climate.set_temperature` calls on
  the *same* entity for the *same* house_state trigger. Not yet manifested as a visible bug in the
  developer's real house only because all 3 `heating_preference` proposals were rejected
  (`learning_audit.txt`), not because the architecture prevents it.

**Decision**: unlike Lighting (kept as two explicitly-related tiers via `Precedence`), here the
cleaner resolution is **full reconciliation, not a precedence relationship between two systems**:
an accepted `heating_preference` proposal should become the `target_temperature` **value** of
`HeatingDomain`'s `fixed_target` branch for that house_state, not a standalone reaction issuing its
own competing `ApplyStep`. One source of truth for "what temperature this state wants," not two.

### External research (web search, sources in chat) — seasonality is discrete, not gradual

Developer's framing confirmed and sharpened by research: heating's seasonal variation is **not**
shaped like lighting's circadian gradient. Nest/Ecobee treat heating vs. cooling as **discrete
modes, each with its own separate setpoint schedule**, switched via an auto-changeover mechanism
compared against real (usually outdoor) temperature — not a continuously-adapting curve. Deadband/
hysteresis research confirms why: a narrow changeover threshold causes short-cycling (the system
flips mode repeatedly around the threshold, e.g. from a door opening or sun on a window) — the
changeover itself needs explicit hysteresis, same as any noisy threshold crossing.

**Decision**: model `Season` as an explicit `HouseFact` (`fact_type: "season"`), not implicit inside
`HeatingDomain`'s branches as today. Derived via a `FusionRule` from `outdoor_temp` (already a
`Sensor` — `external.outdoor_temp`, from the `ExternalContext` collapse decided earlier) **with a
`Window`-based hysteresis** at the changeover threshold, to avoid flapping in shoulder-season
weather. `HeatingDomain`'s branches become keyed on **(`house_state`, `season`)** together, not
`house_state` alone — the desired "home" setpoint in January and in July are different values with
nowhere explicit to live in today's model. Combines with the reconciliation above: a learned/
accepted heating preference now varies by season too, not just by house_state.

---

## Security — reviewed, no duplication found; one quality upgrade identified (2026-08-31)

Unlike Lighting/Heating, checked and confirmed `SecurityDomain` (511 lines) does **not** have the
"two parallel actuator-commanding mechanisms" disease — it's a detection/normalization domain
(`security_state`, `security_reason`, `breach_candidates`), not an actuation domain. Actuation goes
through one clean path already: `alarm_state_action` reactions driven by the Policy Editor Framework
(Phase AF). Its corroboration fusion (`derived_room_evidence` + `anonymous_presence_evidence`)
already correctly uses the generic `derive()` fusion registry (confirmed earlier when grounding
`FusionRule`), unlike Heating's bypassed count-threshold. Security is comparatively healthy already.

**One quality upgrade identified via research** (EN50131/BS8243, professional intrusion-alarm
standards): "Sequential Confirmation" — a genuine alarm requires a **second, independent signal
within a bounded time window** after the first before escalating to a verified/confirmed state (the
threshold for calling authorities), not just any one of several symmetric evidence sources. Today's
corroboration is a **symmetric "any"** fusion (either evidence source is enough), one step simpler
than sequential confirmation.

**Not a bug, a lower-priority enhancement** — and composes from concepts already decided today, no
new primitives needed: `Importance` (OBSERVE/SUGGEST/ASSERT) for staged confidence levels
(unconfirmed candidate = OBSERVE, verified by a second independent signal = ASSERT), and `Window`
(already used for composite correlation) for "did a second independent signal arrive within X
seconds of the first." Noted for later, not scheduled.

---

## Calendar — reviewed, plus a real cross-domain synthesis (2026-08-31)

### Calendar domain itself: clean, no duplication, but structurally inconsistent with the others

Only 368 lines, one file — `CalendarDomain` is a pure input/context domain (classifies HA calendar
events into `vacation`/`day_off`/`holiday`/`wfh`/`office` via keyword-matching on event summaries,
`_classify()`), consumed by others (already feeds `HouseState`'s `workday_evidence` `Precedence`
chain — `calendar_office > calendar_day_off > calendar_holiday > calendar_wfh > raw entity`). No
parallel-actuation disease like Lighting/Heating.

**Found a real structural inconsistency**: unlike Lighting/Heating/Security, `CalendarDomain` is
**not** registered via `Engine.register_plugin()` — it's called directly by the engine
(`engine.py:1734`), passed same-cycle straight into `HouseStateDomain.compute()`, not through
`CanonicalState` from the previous cycle. `CLAUDE.md` describes Calendar as one of "the plugins
ordered by dependency (Lighting, Heating, Security, Calendar, ...)," which doesn't match either the
code or, as resolved below, what's actually correct for it.

**Resolved 2026-08-31 — Calendar is Timing (Layer 0), not a domain or plugin at all.** Registering
it via `register_plugin()` would push it into post-core plugin evaluation, forcing `HouseState`
(core) to read last-cycle-stale calendar data for same-day decisions ("is today a holiday") — a real
behavior regression, not just a cosmetic fix. The developer's framing resolved this more precisely
than "same rank as Time/Recovery": a calendar event is **"at" extended** — the same "something at
instant T" idea generalized to an externally-sourced, *named* interval (absolute start/end, not
relative to "now" like `Window`) instead of an internally-computed point or recurrence. Modeled as
`CalendarWindow` inside Timing itself (`v3_house_fact_draft.md`), sibling to `AtJob`/`CronEntry`/
`Window`/`RecurrencePattern` — not a new "engine context" category, a natural member of the one that
already exists. Membership checks (`is now inside a vacation CalendarWindow`) are the same temporal
containment operation Timing does everywhere else. **The fix is to `CLAUDE.md`'s description, not
to the code's wiring** — Calendar's current same-cycle, pre-core availability was already correct;
it was just never named as Timing infrastructure. Relevant to the upcoming "pluggable domains"
discussion: Calendar was never meant to be dynamically-registrable as a domain in the first place,
so it's out of scope for that question, not a prerequisite blocking it.

### Internal vs. external calendar — dissolved, not decided, same pattern as Zone↔Label/Timing↔schedule.*

Checked: HA has a native `local_calendar` integration (since 2022.12, well within Heima's min
version) — a locally-hosted `calendar.*` entity, no external service needed. **Resolution**: not an
either/or. `CalendarDomain`'s classification (`_classify()`, keyword-matching against admin-defined
keywords + priority order) already works against *any* `calendar.*` entity regardless of backing —
Google Calendar, CalDAV, or `local_calendar`. Formalize as a new `CalendarInterpretation`
(keywords + priority_order) sibling to `Boolean`/`Bucket`/`MediaActivity`/`Presence`
`Interpretation`s, so calendar classification uses the same `Sensor` machinery as everything else.
Recommend (never require) `local_calendar` as the "internal" option for admins without a suitable
existing calendar or who don't want to encode Heima keywords into a shared family calendar — multiple
calendar `Sensor`s (internal + external) can coexist freely.

### Real synthesis: `vacation` house_state, dual-source + traceable + duration-aware — no new primitives

Developer requirement: `vacation` settable via switch OR calendar, the causal source must be
obvious/traceable, and vacation-presence-simulation should only activate for vacations longer than
X days — detected either **preventively** from the calendar event's own span, or **reactively** from
elapsed time in the switch-driven state. Composes entirely from concepts already decided today:

1. **Dual-source `vacation`**: `FusionRule` with `BooleanSetStrategy(mode="any")` combining
   `Sensor(switch.vacation_mode)` (already exists as a `house_signals` entry today) with the
   calendar `Sensor`'s `category == "vacation"` classification. No new strategy.
2. **Traceable ("palese")**: exactly what today's `Provenance`/`FactSource` correction was for — the
   resulting `HouseFact`'s `Provenance.source` names which input actually triggered it (switch vs.
   calendar), inspectable via the `correlation_id` chain from the observability section. This is the
   concrete use case that justifies that work, not just plumbing for its own sake.
3. **`vacation.is_long` — a separate `HouseFact`, not an 8th `HouseState` value** (consistent with
   `HouseState` staying closed). Two detection paths, both already-existing mechanisms:
   - *Predictive*: the triggering calendar event's own `(end - start)` span compared against a
     `Window(X days)` — known as soon as the event exists, before vacation even starts.
   - *Reactive*: elapsed time since `house_state` entered `vacation` — literally the same
     `active_for` dwell-tracking mechanism already used for the sleep/wake/work/relax candidates in
     `HouseState` today, just with a days-scale `Window` instead of a minutes-scale one.
   - Combined via another `BooleanSetStrategy("any")` — either path being true is enough.
4. **Gates the reaction, doesn't redefine the state**: `vacation.is_long` becomes a
   `SensorRequirement` inside `security_presence_simulation`'s `TemplateRequirement` — the
   simulation is only proposed/eligible for long vacations, instead of unconditionally whenever
   `house_state == vacation`.

**Subsumes today's Heating-only `vacation_is_long_entity`/`vacation_total_hours_entity`**
(`heating.py:724-725`) — currently admin-maintained external entities (e.g. a hand-built template
sensor), private to Heating's own `vacation_curve` branch. Under v3, `vacation.is_long` is a general
`HouseFact` both Heating and Security's presence simulation read from the same source, instead of
each domain privately reinventing/requiring its own copy.

---

## Domain roster — consolidated audit (2026-08-31)

Grounded in the engine's actual domain instantiation (`engine.py:263-274` — 9 instances total, no
more, no less: `events_domain`, `people_domain`, `occupancy_domain`, `activity_domain`,
`calendar_domain`, `house_state_domain`, `lighting_domain`, `heating_domain`, `security_domain`).
No `watering` domain exists yet (spec says "planned"); no separate top-level camera-evidence domain
(nested inside `SecurityDomain`, not independently registered).

**Core (fixed order, never plugins — architecture invariant #6):**
- **People** — group presence (quorum/weighted-quorum). Foundational (`anyone_home` gates
  `HouseState`'s first hard-state check). Still justified, unchanged role, re-grounded on
  `Sensor(PresenceInterpretation)`+`FusionRule` (resolved in the external review pass, item 4).
- **Occupancy** — per-room occupancy, feeds Activity/HouseState/Lighting/Heating/Security. Still
  justified, unchanged role, re-grounded on `Sensor`+`FusionRule`+`LearnedWindow` — becomes thinner,
  most of its logic is now "a `FusionRule` instance" rather than bespoke code.
  → possible future compaction, not a removal.
- **Activity** — 8 hand-written primitive detectors (dishwasher/oven/pc/tv/shower/stove/washing/
  power_media). Still justified, and **strengthened**: designated home for new recurring-behavior
  discovery (genuinely missing today — see "House State vs. Activity" section), not just surviving
  unchanged, gaining scope.
- **HouseState** — 7-state closed resolution. Still justified in shape (safety-relevant exact-match
  dependents elsewhere rule out an open vocabulary); gains explicit `PrecedenceStrategy`, season
  awareness (from Heating), dual-source `vacation` + `vacation.is_long` derivation.

**Plugins (registered via `Engine.register_plugin()`, dependency-ordered):**
- **Lighting** — redesigned this session: two historically-parallel mechanisms
  (`LightingDomain` coarse scenes + `room_smart_lighting_assist` precise) made an explicit
  `PrecedenceStrategy` relationship; circadian adaptation delegated to Adaptive Lighting (external
  composition, not rebuilt); `LearnedWindow` for adaptive dwell.
- **Heating** — same disease as Lighting, same class of fix: `HeatingPreferenceReaction`/
  `HeatingEcoReaction` (fully independent, competing `climate.set_temperature` calls) reconciled
  into `HeatingDomain`'s `fixed_target` branch value instead of running in parallel; `Season` added
  as an explicit `HouseFact` with hysteresis, branches keyed on (`house_state`, `season`).
- **Security** — reviewed, **no duplication found**, already the healthiest of the three: single
  actuation path (`alarm_state_action` via Policy Editor Framework), corroboration already properly
  uses the generic fusion registry. One quality upgrade identified (EN50131-style sequential
  confirmation via `Importance` + `Window`, no new primitives) — noted, not scheduled, not urgent.

**Reclassified — never really "domains" in the DAG sense:**
- **Events** (`EventsDomain`) — owns `HeimaEventPipeline`. Layer 0 infrastructure, role unchanged;
  will carry `HouseFact`-shaped payloads internally and eventually absorb proposal notifications
  (Tier 1/Tier 2 unification, still pending — see Notifications section).
- **Calendar** — resolved this session: not a domain or plugin at all, an extension of Timing
  (`CalendarWindow`, Layer 0) — was never meant to go through `register_plugin()`; the fix was to
  `CLAUDE.md`'s description, not the code.

**Overall finding**: no domain warrants elimination — all 7 real domains have solid, confirmed
justification. The recurring pattern wasn't "domain shouldn't exist," it was **"same domain, two
independently-evolved mechanisms deciding the same physical outcome"** (Lighting, Heating) —
resolved via explicit relationships (`Precedence`, reconciliation), not removal. Security and the 4
core domains were already sound. Calendar was miscategorized from the start, not degraded over time.

---

## People — reviewed, no duplication, one nuanced (not confirmed) learning-applicability finding (2026-09-01)

No parallel-mechanism disease — group presence goes through one path (`derive()`,
quorum/weighted-quorum), already confirmed properly using the generic fusion registry.

**Investigated why `presence_preheat` (typical-arrival-time learning) shows `total=0` forever in the
developer's real data**, using the same method as the V3-1 dead-reaction investigation. First
hypothesis — a production emission gap like the sleep-normalizer bug — **ruled out**: initially found
only a *test-seeding* helper (`coordinator.py:1580`, docstring "Inject synthetic arrival events... for
live tests") constructing the `event_type="presence"/"arrive"` shape `PresencePatternAnalyzer`
queries for, which looked like the same class of bug — but a broader search found the **real**
production emitter: `runtime/behaviors/event_recorder.py:67-77` correctly emits this event whenever
`anyone_home` flips false→true, in the actual per-cycle runtime path, not just in tests.

**More likely explanation, not proven — genuinely different in kind from the sleep bug (no provable
vocabulary mismatch found here)**: `PresencePatternAnalyzer` requires 5 same-weekday arrivals spread
across ≥2 weeks. "Arrival" is defined as the *whole house* transitioning from empty to occupied —
for a household where someone is usually home, that transition is inherently rare, not broken.
Unverified without querying the real event history, not chased further.

**Architectural point that stands regardless of the exact cause**: `presence_preheat` implicitly
assumes a commute-like "leaves and returns" pattern. For households usually occupied by someone,
this learning family is structurally low-applicability, not defective — worth knowing before relying
on it as a proposal source in v3, independent of whether the zero total has a further root cause.

---

## Occupancy — reviewed, healthy, a model for how a "learned complement" should look (2026-09-01)

No parallel-mechanism disease. `OccupancyInferenceModule` (142 lines) is explicitly scoped
("Emits OccupancySignal for **sensorless rooms only**") — learns `P(room_occupied | room, weekday,
hour, home)` specifically where direct-sensor `FusionRule` occupancy has no data, not competing with
it. Verified properly wired end-to-end (`_select_occupancy_signals` in `OccupancyDomain`, consumed
via `engine.py:1752-1753`) — unlike `presence_preheat`, this signal is genuinely consumed. No
redesign needed; this is the pattern other "learned" additions should have followed from the start.

---

## Domain review closed — dynamic/pluggable domains (2026-09-01)

All 7 real domains now reviewed (Lighting, Heating, Security redesigned/confirmed; Calendar
reclassified; People, Occupancy confirmed healthy; Activity/HouseState covered earlier). Closing
question: should domains be addable dynamically via plugin?

**Largely already answered by today's Layer-6 work** — `register_plugin()` already exists as an
open seam, two-capability-tier model (`read_only`/`apply`) with Phase AH reuse already designed. The
domain review reframes *why*: none of the 7 current domains need to become third-party plugins
(all justified, staying built-in) — the real motivating case is **adding domains Heima doesn't have
and won't build itself**, e.g. `docs/specs/domains/watering_spec.md` ("planned", never implemented) —
now buildable by an external developer via this mechanism instead of waiting on the core team.

**Two gaps found while closing this out:**

1. **Namespace collision risk** — nothing stops two third-party plugins from both registering
   `fact_type="zone_1"` and silently clobbering each other. Needed: non-built-in `fact_type`s get a
   plugin-prefixed convention (`"plugin.<plugin_id>.<name>"`), not left flat.
2. **Resolved ambiguity: Heima's own config flow/admin panel (Layer 7) does *not* need to become
   pluggable/extensible, and shouldn't.** A third-party domain plugin is itself a separate HA
   integration with its *own* config entry and config flow — same pattern already established for
   `ExternalContext` adapters and Adaptive Lighting composition. It touches Heima only at the
   `register_plugin()` seam (Layer 6) and the shared `Sensor`/`Actuator`/`Zone`/`HouseFact` registries
   (Layer 1-2) as data. Heima's own UI stays closed/first-party; the plugin's configuration surface
   lives entirely outside it.

---

## Learning warm-up gate — new gap found while closing the open questions (2026-09-01)

Triggered by closing item 3 above: no learning family has a concept of "data observed right after
this subject became eligible shouldn't count yet." Checked the 4 things that look adjacent and
aren't:

- `grace_period_s` ([activity_detectors/*.py](custom_components/heima/runtime/activity_detectors/)) —
  per-detector debounce ("wait N seconds before treating a phase as finished"), unrelated to when
  data starts counting for learning.
- `startup_grace_s` ([notifications.py:292](custom_components/heima/runtime/notifications.py#L292)) —
  suppresses notification *delivery* at startup, doesn't touch what gets learned.
- `bootstrap_mode` (Activity, Phase Z) — goes the opposite direction: *lowers* `min_support` to learn
  faster early on, the opposite of waiting.
- `reset_learning_state()` ([engine.py:796](custom_components/heima/runtime/engine.py#L796), called
  on every reaction/behavior on config reload) — clears accumulated state on config change, but isn't
  time/sample-gated: nothing stops the very next observation after a reset from counting immediately.

**Confirmed genuine gap**: none of the ~11 learning families (6 always-on `HeimaLearningModule`
instances + 5 `LearningPluginRegistry` families) discard early post-setup data. Real risk: admin
manually toggling entities while wiring/testing a room, or a family re-enabled after being off, feeds
directly into the model — worse with `bootstrap_mode`, which lowers the sample bar right when the
noisy window is most likely.

**Confirmed the mechanics support a read-time filter, not a new storage mechanism**:
`SnapshotHistoryStore.snapshots()` ([inference/base.py:72-77](custom_components/heima/runtime/inference/base.py#L72-L77))
is read fully from scratch on every `analyze()` call — no incremental online counter. A warm-up gate
is therefore a filter over the same history stream, same "atomic storage, views filtered on read"
principle already decided for `HouseFact` persistence — not a new mechanism.

### Decision (2026-09-01)

**Per-subject, not global** (a mature install adding one new room shouldn't re-gate every other
room), and **a combined time + sample-count threshold (AND, not OR)** — each alone fails a different
way:
- Time-only: a dense test burst (admin toggling something 20x in 2 minutes) satisfies a short time
  window instantly, with data that's exactly what should be excluded.
- Sample-count-only: the same burst satisfies a sample threshold just as fast — the noisy burst
  becomes the very data that unlocks learning.
- Combined: neither a fast dense burst (fails the time floor) nor a long quiet stretch with no real
  usage (fails the sample floor) can end the warm-up window alone.

**Not a pure `Timing` primitive** — `Timing`'s constructs (`Window`/`AtJob`/`RecurrencePattern`/
`CalendarWindow`) are all elapsed-time-only. This is a composite gate: the time half leans on
`Timing` for the elapsed-time floor, the sample half is a plain counter over the same filtered
stream, evaluated together at read time by whatever consumes history (module `analyze()`, analyzer
history queries) — lives alongside `min_support` (already per-module-configurable via Phase S), not
as a new Timing entry.

**Not yet decided**: what counts as "a sample" is family-specific, not a single global unit —
snapshot count for Weekday/HouseState/RoomStateCorrelation (consume `SnapshotHistoryStore`), detected
episode count for `composite_room_assist`-family analyzers, raw event count for others. Needs
per-family grounding before this becomes a concrete shape in `v3_house_fact_draft.md` or elsewhere —
noted here, not yet modeled.

---

## Learning pipeline — do the 6 always-on modules and the registry families overlap? (2026-09-01)

Motivating question: 11 learning-producing things exist (6 `HeimaLearningModule` instances,
unconditionally constructed in `coordinator.py:359-391` — `WeekdayStateModule`,
`HeatingPreferenceModule`, `HouseStateInferenceModule`, `ActivityInferenceModule`,
`LightingPatternModule`, `RoomStateCorrelationModule` — plus the `LearningPluginRegistry`, which
actually has 7 registered families, not 5: presence, heating, lighting, composite_room_assist,
`house_state` (`enabled=False`, `_NoopPatternAnalyzer`, `execution_mode="lifecycle_only"` —
[registry.py:417-431](custom_components/heima/runtime/analyzers/registry.py#L417-L431)),
`scheduled_routine` (admin-authored only, no auto-learning), security_presence_simulation). Do these
two groups duplicate each other?

**Not accidental duplication — one deliberately governed 3-stage pipeline, already decided and
tested (Phase P4b, `DONE`).** Governing rule, found verbatim in
[docs/v2_dev_plan.md:3046-3047](docs/v2_dev_plan.md#L3046-L3047): *"Statistical signals never feed
operational domains directly. The only operational path is: LearningModule signal → analyzer →
ProposalEngine → admin review → configured rule/reaction."*

Of the 6 always-on modules, only 3 are ever actually consumed by a domain, and each consumption is
bounded:
- `ActivityInferenceModule` → `ActivitySignal`, consumed by `ActivityDomain`
  ([engine.py:1768-1769](custom_components/heima/runtime/engine.py#L1768-L1769)) — only for
  already-admin-approved composite patterns.
- `OccupancyInferenceModule` → `OccupancySignal`, consumed by `OccupancyDomain` — only for
  sensorless rooms, confidence ≥ 0.70 (already confirmed healthy in the "Occupancy" section above).
- `HouseStateInferenceModule` → `HouseStateSignal`, consumed via `_select_learned_house_state_signal`
  ([house_state.py:1039-1054](custom_components/heima/runtime/domains/house_state.py#L1039-L1054)) —
  filtered to `source_id == "house_state_inference"` only, and itself only replays contexts already
  approved through `_approved_context_keys` — downstream of admin review, not a raw-stats bypass.

**The other 3 are diagnostic-only by explicit design, confirmed in the phase plan, not a bug**:
`WeekdayStateModule` was deliberately downgraded to `Importance.OBSERVE` in Phase R specifically so
`HouseStateDomain` would stop consuming it (acceptance criterion, `DONE`).
`RoomStateCorrelationModule`/`LightingPatternModule` are explicitly documented in P4b as "remains
diagnostic-only at runtime." `HeatingPreferenceModule` is never read by `HeatingDomain` anywhere in
the code — same effect, consistent with the same rule, just not called out with its own acceptance
checkbox.

### Decision (2026-09-01) — remove the scaffolding that already served its purpose

`LightingPatternModule` and `HeatingPreferenceModule` were built (Phase D) as an early stand-in
*before* the real analyzer existed — the phase plan's own words: "a future analyzer may target the
existing `context_conditioned_lighting_scene` reaction type." That future analyzer now exists and is
the live path for both: `LightingPatternAnalyzer` and `HeatingPatternAnalyzer`
(`LearningPluginRegistry`, already the subject of this session's Lighting/Heating reconciliation
decisions). The two modules still recompute a statistical model from snapshot history every analysis
cycle, emit a signal, that signal is routed and then goes nowhere. **Remove both modules** (and their
`HeatingSignal`/`LightingSignal` emission) in v3 — their purpose is fulfilled, not pending.

**Also remove `WeekdayStateModule`** (found 2026-09-01 while working LP-1/LP-2, below): its key
(`weekday + hour_bucket`, no `anyone_home`) is a strict subset of `HouseStateInferenceModule`'s
`minimal` tier (`weekday + minute_of_day + anyone_home` —
[house_state_inference.py:121-126](custom_components/heima/runtime/inference/modules/house_state_inference.py#L121-L126)),
which is strictly richer on the same axes. Unlike `RoomStateCorrelationModule` (which had a genuinely
orphan feature — occupied-room pattern alone — worth folding in as its own tier), `WeekdayStateModule`
contributes nothing `minimal` doesn't already cover. Phase R's `Importance.OBSERVE` downgrade
(2026-08) already made it inert for decisions; this closes it out — remove entirely, not just
leave at OBSERVE.

### `RoomStateCorrelationModule` — resolved 2026-09-01, folded into `HouseStateInferenceModule`

Unlike Lighting/Heating, its promised successor — P4b's own words, "a future
`HouseStateCorrelationAnalyzer` may turn stable occupied-room patterns into reviewed house-state
proposals" — was **never built**. The `house_state` registry entry found above is a disabled Noop
stub, confirming no such analyzer exists today.

Checked whether it's simply superseded by `HouseStateInferenceModule`'s tiered rich/coarse/minimal
model before deciding: the `coarse` tier's slot key already combines
`weekday + minute_of_day + room_occupancy + anyone_home`
([house_state_inference.py:114-120](custom_components/heima/runtime/inference/modules/house_state_inference.py#L114-L120)) —
it already includes the occupied-room pattern. `minimal` drops `room_occupancy` (weekday+hour+
anyone_home only). `RoomStateCorrelationModule` uses *only* the occupied-room pattern, no weekday/
hour at all — not a clean subset of either existing tier: it's coarser than `coarse` on the time axis
but richer than `minimal` on the room axis. Structurally, it's a **missing 4th tier**, not a
duplicate: room-pattern-alone can reach a confident prediction with far less data than
weekday×hour×room-pattern combinations each individually needing their own `min_support` — exactly
the same fallback-to-less-specific idea the rich→coarse→minimal ladder already implements.

**Decision**: don't build the never-built analyzer, don't retire the module — **fold it into
`HouseStateInferenceModule` as an additional tier** in the existing rich→coarse→minimal ladder,
reusing the same approved-context gating already in place, instead of a new analyzer/proposal
family. Composes directly with the Track 1 house-state calibration redesign already decided — this
is exactly the kind of additional calibration feature that redesign is for, not separate work.

---

## Learning pipeline — critical review, improvement tasks (2026-09-01)

Developer asked for a critical pass over the whole v3 learning pipeline as reconstructed above,
weak points welcome even if they break v2 compatibility. Six findings, to be worked one at a time —
not yet resolved, this is the task list, resolutions get their own dated entries as each is closed.

### LP-1 — "confidence" means 4 incompatible things across the pipeline

Grounded by reading the actual formulas, not just field names:
- `HeatingPreferenceModule`/`WeekdayStateModule`: `min(1.0, support / min_support)` — a volume proxy
  ("how much data do I have"), not outcome consistency.
- `RoomStateCorrelationModule`/`HouseStateInferenceModule`: `count / total` — true match ratio
  (`P(state | pattern)`).
- `HeatingAnalyzer` ([analyzers/heating.py:104](custom_components/heima/runtime/analyzers/heating.py#L104)):
  `max(0.3, 1.0 - spread / 5.0)` — inverse value spread (variance-based).
- `LightingAnalyzer`/`PresenceAnalyzer`
  ([analyzers/lighting.py:143](custom_components/heima/runtime/analyzers/lighting.py#L143),
  [analyzers/presence.py:76](custom_components/heima/runtime/analyzers/presence.py#L76)):
  `max(0.3, 1.0 - iqr / 120.0)` — inverse IQR (timing-tightness-based).

Four different statistical bases, all named `confidence`, not comparable. Latent bug:
`_select_learned_house_state_signal` already picks the max-confidence candidate among sources
(house_state.py:1054) — safe today only because a single source passes its filter. Comparing
confidences across sources (the new room-pattern tier, Track 1 features, any future cross-source
selection) breaks silently once more than one source is eligible. Root cause: the "HOW closed"
`Provenance.confidence` decision fixed *where* confidence lives, never *how it's computed*.

### LP-2 — no shared "learn from history" primitive — every module reinvents bucket+threshold

`WeekdayStateModule`, `HouseStateInferenceModule`, `ActivityInferenceModule`,
`OccupancyInferenceModule` (inference side) and `HeatingAnalyzer`, `LightingAnalyzer`,
`PresenceAnalyzer` (registry side) all hand-roll the same shape: bucket snapshots by a key, count,
gate on `min_support`/`confidence_threshold`. Same disease class already named repeatedly this
session (Provenance, Timing, HouseFact all started as "same pattern, N independent
reimplementations"). Concrete cost: the warm-up gate (already decided) would need manually adding
in ~8-10 places, real risk one gets missed — same bug class as the `boolean_signal()`
charging-states gap. Fixing LP-1 (one confidence formula) and building the warm-up gate both want
this primitive to exist first — likely one piece of work, not two.

### LP-3 — resolved 2026-09-01: extend `register_learning_module` with the same `enabled` flag the registry already has

The registry already does the right thing: an `enabled` flag decided once per options reload
(`enabled=_is_enabled(family, enabled_families)`). Always-on modules have nowhere for that flag —
`engine.register_learning_module(module)` takes no such parameter today.

**Decision**: `Engine.register_learning_module(module, *, enabled: bool = True)` — same shape as the
registry's own flag, not a new mechanism. In `coordinator.py`, construction of `_house_state_module`/
`_activity_module` passes `enabled=_is_enabled(family, enabled_families)`, reusing the existing
`_is_enabled` helper. `_collect_signals()` skips `.infer()` (and `.analyze()`, where the module is
disabled) rather than computing and discarding. `_LEARNING_PLUGIN_FAMILY_OPTIONS` gains `house_state`
and `activity` entries, as already promised in the Q3 closure above.

**Bonus, not separately planned**: skipping `.analyze()` for a disabled module also stops its 6h
rescan entirely (LP-5) — disabling a family now saves real recompute, not just a discarded read.

### LP-3 — original finding (for context)

`enabled_plugin_families` structurally cannot gate the always-on modules

Confirmed via the P4b split (see section above): the registry's `enabled` flag and the coordinator's
unconditional module instantiation are two separate mechanisms. The family-toggle promised for
house_state/activity once Track 1 ships (Q3 closure above) isn't just "add a checkbox" — it needs a
new enable-check inside `HouseStateInferenceModule.infer()`/`ActivityInferenceModule.infer()` (or
wherever they're invoked), a mechanism that doesn't exist today for always-on modules. Naming this
explicitly so the Q3 closure's promised toggle doesn't get scoped as smaller than it is.

### LP-4 — resolved 2026-09-01: `PatternLearner` reads atomic `HouseFact`s directly, no bundle migration needed

**Decision**: `PatternLearner` (LP-1/LP-2) consumes atomic `HouseFact`s directly through the same
generic query API (`fact_type` + `Location` + time window) every other consumer uses — it does not
consume a reconstructed `HouseSnapshot`-shaped view. A bucket key (weekday, house_state,
room_occupancy, heating_setpoint, ...) is just a set of `fact_type`s read over the query window, not
a field on a bespoke bundle. Reintroducing a bundle specifically for learning would recreate, exactly
where it matters most, the "5th competing shape" the persistence decision already ruled out for
third-party plugins.

**Consequence**: no `HouseSnapshot`/`SnapshotHistoryStore` migration is needed for learning at all —
that concept is retired for this purpose, not rewritten. It may still be useful elsewhere (e.g. a
diagnostics view wanting "everything true at instant T"), reconstructed on demand, but learning stops
depending on it.

**Synergy with LP-5**: queries scoped to only the `fact_type`s a given `PatternLearner` instance
actually needs, instead of rescanning an entire bundled snapshot every time — reduces the volume
LP-5 was worried about before LP-5 is even separately addressed.

### LP-4 — original finding (for context)

Every learning module consumes the old bundle shape, not atomic `HouseFact`

The persistence decision (already closed above) makes storage atomic with snapshot-style views
reconstructed on read. Every `analyze()` today consumes `store.snapshots()` — the old bundle. This
isn't only a third-party-plugin migration concern (as framed in that section) — every built-in
learning module's `analyze()` needs rewriting against the new view API. Flagging so the migration
scope isn't underestimated.

### LP-5 — resolved 2026-09-01: not a redesign, an indexing requirement on `EventStore[HouseFact]`

Substantially narrowed by LP-4 already: `PatternLearner` queries are scoped to only the `fact_type`s
a given learner needs, not a full bundle rescan. Two things further de-risk this:
- `analyze()` runs every 6h, off the hot path entirely — architecture invariant #2 (no blocking I/O
  on the hot path) doesn't apply, this was always a background job, not a per-cycle cost.
- 10,000 records rescanned linearly every 6h is already proven fine today.

**Decision**: no redesign needed — just a concrete implementation requirement on the
`EventStore[HouseFact]` persistence layer: **index by `fact_type` (and `Location`)**, so LP-4's
scoped queries are cheap in practice, not merely narrower in name while still scanning everything
underneath. Not an open architectural question anymore — a requirement to carry into that layer's
build, revisit only if real-world volume ever proves the index insufficient.

### LP-5 — original finding (for context)

Full history rescan every 6h doesn't obviously scale to v3's finer granularity

`analyze()` runs every 6h (`_ANALYZE_INTERVAL_S`), each module rescanning up to 10,000 snapshots
(90-day TTL) from scratch. Fine today. v3's atomic, per-room/per-signal `HouseFact` granularity plus
more modules (the new room-pattern tier, Activity discovery track 2, possible third-party learning)
could grow the volume a naive linear view-reconstruction has to scan. Not urgent, worth a design
constraint when the view-query API (LP-4) gets built.

### LP-6 — resolved 2026-09-01: third-party learning allowed, but only through the full P4b pipeline, never as a live signal

Enabled by `PatternLearner` existing now (LP-1/LP-2): a third-party plugin can declare, at
registration, an analyzer built on `PatternLearner` — no hand-rolled bucket/threshold/confidence
logic, which would reopen exactly the governance risk LP-1 just closed for built-ins (a 5th
confidence formula, invented externally this time).

**Decision**: third-party learning output always goes through the complete P4b pipeline —
`PatternLearner → analyzer → ProposalEngine → admin review → configured reaction`. It never gets a
seat at the "always-on module with a live signal" tier (Activity/Occupancy/HouseState today) — that
tier is the sole sanctioned exception to "statistical signals never feed operational domains
directly," and each existing exception is individually bounded and core-team-verified (Activity:
approved patterns only; Occupancy: sensorless rooms only, confidence ≥ 0.70; HouseState: approved
contexts only). Extending that trust to external code isn't auditable the same way — so the line is:
third-party learning always terminates in a reviewable proposal, never a live signal straight into a
domain's `compute()`.

Reuses existing mechanisms, no new ones: the same try/except fault-isolation boundary already decided
for `compute()` extends to `analyze()`/proposal generation; the same `plugin.<plugin_id>.<name>`
namespace convention already decided for third-party `fact_type`s extends to `proposal_type`/
`reaction_type`.

### LP-6 — original finding (for context)

Third-party plugin API never addresses learning, only per-cycle `compute()`

The Third-party plugin API section covers `IDomainPlugin.compute()` (`read_only`/`apply` tiers,
fault isolation, shadow mode) but says nothing about `register_learning_module()` — today a purely
internal call. If a third-party plugin should ever be able to learn something (not just read/write
`HouseFact` per cycle), it has no sanctioned path under the P4b rule (signal → analyzer → proposal →
review) today. Not urgent, open gap to name.

**Working order** (developer + assistant agreed): LP-1 and LP-2 first (same fix serves both), then
the rest one at a time.

### LP-1 + LP-2 — resolved 2026-09-01: `PatternLearner`, one shared primitive

Re-examined the 4 confidence formulas found in LP-1 — not all equally wrong, two are legitimate
answers to the same question ("how consistent is this outcome") for two different target shapes:

- **Categorical target** (house_state, scene name, activity name): `count / total` (match ratio) —
  literally `P(outcome | pattern)`. Already the right formula
  (`RoomStateCorrelationModule`/`HouseStateInferenceModule`).
- **Continuous target** (a learned setpoint, a learned time-of-day): no "match ratio" exists for a
  continuous value — the equivalent is inverse dispersion (tight cluster = confident), already what
  `HeatingAnalyzer`/`LightingAnalyzer`/`PresenceAnalyzer` do, just with ad hoc unparameterized
  constants (`5.0`, `120.0`) picked per call site instead of a named, reusable formula.
- **The one genuinely wrong formula**: `min(1.0, support / min_support)`
  (`HeatingPreferenceModule`/`WeekdayStateModule`) — conflates volume (already `min_support`'s job,
  a boolean gate) with confidence. Both modules using it are already marked for removal above.

**Decision: build `PatternLearner`**, one shared primitive combining everything LP-1/LP-2 found
duplicated:
- bucket history by an arbitrary key (weekday/hour/rooms/any combination)
- `min_support` as a boolean gate ("not enough data" → no output, never "low confidence")
- the warm-up gate (time + sample count, AND — already decided) enforced once here, not
  per-module
- confidence computed by one of exactly two standard formulas, selected by the target's declared
  shape (categorical match-ratio / continuous inverse-dispersion with a named `scale` parameter
  instead of a magic number) — never reinvented per module
- **generalized tiered fallback** (rich → coarse → minimal, today private to
  `HouseStateInferenceModule`) promoted into the primitive itself — developer's call (2026-09-01):
  worth having as a general capability, not HouseState-specific, since the room-pattern tier just
  folded in (above) already proved the ladder generalizes to an extra tier.

Every learning module/analyzer named in LP-2 (`HouseStateInferenceModule` and its now 4 tiers,
`ActivityInferenceModule`, `OccupancyInferenceModule`, `HeatingAnalyzer`, `LightingAnalyzer`,
`PresenceAnalyzer`, and by extension `CompositePatternCatalogAnalyzer`/
`SecurityPresenceSimulationAnalyzer`) gets rebuilt on top of `PatternLearner` rather than hand-rolling
its own bucket/threshold/confidence logic — same "full rewrite where it buys a genuinely clean v3
architecture" latitude already used for `HouseFact` itself. Not yet modeled in a draft file — next
step when this moves from backlog discussion to a real shape.

---

## Full architecture re-review — improvement tasks (2026-09-01)

Developer asked for a critical pass over the whole v3 architecture (`v3_architecture_recap.md`, the
8-layer synthesis, plus the 3 draft files), not just the learning pipeline — looking for gaps or
inconsistencies, incompatibility with v2 welcome. 8 findings, worked one at a time like the LP items
above; the recap's own pre-existing "still open" list (9 items, end of that file) stays valid
separately and isn't repeated here.

- **AR-1** — resolved 2026-09-01. The learning pipeline had no place in the 8-layer model. Learning
  depends on the old Layer 2 (Registries) — it mines the history Registries produce, not just raw
  `HouseFact` shape — so it sits *above* Registries, not beside Substrate. **Decision: renumber**,
  inserting it as the new **Layer 3 — Learning / pattern recognition**, pushing old Layers 3-7 to
  4-8. `v3_architecture_recap.md` is fully renumbered and gained a real Layer 3 section (`PatternLearner`,
  the P4b rule, the 3 bounded live-signal exceptions, the registry-analyzer stage). Historical entries
  in this backlog dated before 2026-09-01 keep the old numbering (Domain resolution was "Layer 3",
  etc.) — `v3_architecture_recap.md` is the up-to-date reference from here on, this backlog is a
  dated log.
- **AR-2** — resolved 2026-09-01. Added `WarmupGate` (`min_elapsed: Window` + `min_samples: int`,
  AND semantics) to the Timing section of `v3_house_fact_draft.md`, alongside `Window`/
  `LearnedWindow`. Added the standardized confidence computation (categorical match-ratio /
  continuous inverse-dispersion, `min_support` kept separate as a boolean gate) to the `Provenance`
  section. `PatternLearner` itself (bucket/tier/fallback mechanics) stays backlog prose — a bigger
  design pass for when this moves from discussion to a real spec, not part of this fix.
- **AR-3** — resolved 2026-09-01. Added both to the recap's Layer 0 list, plus two things found
  while doing it, checked specifically against power-loss/restart recovery (Phase AQ, `DONE`) per
  the developer's request:
  - **Real tension found and closed**: Phase AQ's own non-goal states "implicit manual holds are
    never restored from a checkpoint after restart." The Manual-Hold-as-`HouseFact` decision (external
    review pass) never carried that constraint forward — if a hold's fact sits in the durably-persisted
    `EventStore`, naively querying it for "is this hold active" after a restart would silently violate
    the non-goal (a hold could appear to survive a restart when it must not, for safety reasons — a
    resident could be unaware a suppression is still in effect). **Resolution**: the `HouseFact` may
    still be durably logged for audit/learning; the live "is this active now" state must never be
    reconstructed from that log after a restart. Same shape, two read paths, explicitly different
    restart guarantees — documented directly on the Manual Hold Manager entry in
    `v3_architecture_recap.md` so it isn't lost again.
  - **Dependency found**: Recovery/Checkpoint's own write cadence
    (`recovery.checkpoint.write`, Runtime Scheduler job, `owner=recovery`) becomes a system-owned
    `CronEntry` under Timing's unification — Recovery/Checkpoint isn't fully independent of Timing
    despite being a separate Layer-0 member. Also noted: Timing's `AtJob`/`CronEntry` queue is
    ephemeral by design and doesn't need restart persistence — `CronEntry` re-derives `due` from its
    persisted `RecurrencePattern`, and `AtJob`s owned by ephemeral state (holds, runtime
    confirmations) correctly have nothing to restore, consistent with the same non-goal.
- **AR-4** — "Season" (Heating redesign) has no clean home: described as `FusionRule`-derived from
  `outdoor_temp` with hysteresis, but `FusionRule` is built for combining *multiple* sensors, and the
  stability `Window` (hysteresis) is currently scoped only to "a `FusionRule`'s output," not to a
  bare `Sensor`+`Interpretation` pair. Needs an explicit decision: generalize the stability-`Window`
  concept beyond `FusionRule` outputs, or bless a single-sensor `FusionRule` as a legitimate pattern.
- **AR-5** — resolved 2026-09-01. `FusionRule` combines **current** facts, same cycle, synchronous
  logic (boolean/quorum/precedence/registered formula) — no history beyond the already-existing
  stability/dwell handling. `PatternLearner` mines **history** (days/weeks of past `HouseFact`s) on a
  slow cycle (6h), producing bucket→outcome statistical models. Same surface shape ("combine multiple
  facts into one"), different input (instantaneous vs. historical) and different execution cadence
  (every cycle vs. every 6h). Concrete example from AR-4: Part A (apparent outdoor temperature +
  solar gain) is a `FusionRule` — recomputed every cycle, needs zero history. Part B (house-specific
  thermal-response rate) is a `PatternLearner` — needs 7 days of history to mean anything, would make
  no sense recomputed per-cycle. Documented directly on Layer 2/Layer 3 in
  `v3_architecture_recap.md`.
- **AR-6** — resolved 2026-09-01, no decision needed — the answer was already true in the code, just
  never written down. Traced the exact order in `async_evaluate()`
  ([engine.py:985-1001](custom_components/heima/runtime/engine.py#L985-L1001)):
  `snapshot = self._compute_snapshot(...)` resolves the full DAG for the current cycle, then
  `self._snapshot_buffer.push(snapshot)` pushes it, and only *after* that does
  `_build_apply_plan(snapshot)` call `_dispatch_reactions(self._snapshot_buffer.history())` — by then
  `history()` already includes the just-pushed current-cycle snapshot. **Reactions (Layer 5) already
  read the current cycle's resolved state, the opposite of the Domains rule** — and correctly so:
  Domains restrict each other to previous-cycle specifically to keep the DAG acyclic (nothing can
  depend on an output not yet computed within the same pass); Reactions run strictly *after* the full
  DAG resolves for that cycle, so no circularity risk applies to them, and they can safely see the
  fresh result. The same reasoning covers Layer 2 (`Sensor`/`FusionRule`) facts: recomputed fresh
  every cycle *before* Domains consume them, so anyone reading them afterward (a Domain building its
  own output, or a Reaction reading a fine-grained detail like room lux) sees the current cycle's
  value — the previous-cycle restriction is specifically Domain-reads-another-Domain, not
  Layer-2-read-by-anyone.
  **Formalized as an explicit invariant** (same treatment already given to Calendar — the code was
  already right, only the written description was missing): *"Reactions (Layer 5) read the current
  cycle's resolved CanonicalState/`HouseFact`s, not the previous cycle — they run strictly after
  domain resolution completes, so no circularity risk applies."* Added to
  `v3_architecture_recap.md`, Layer 5.
- **AR-7** — resolved 2026-09-01. Updated the recap's "still open" item (namespacing convention) to
  cover `proposal_type`/`reaction_type` too, per LP-6, not just `fact_type`.
- **AR-8** — resolved 2026-09-01. **Yes, a third-party plugin can have its own `Sensor`/`Actuator`
  entries** (e.g. a soil-moisture `Sensor` for a `watering` plugin), through the **same Layer 8 panel,
  same dedicated-CRUD pattern** already decided for `Sensor`/`Zone`/`FusionRule`/`Actuator` — not a
  separate mechanism. Reasoning: a plugin reading raw HA entity state privately would lose
  `Provenance`/`FactSource`, unit-drift detection, and — most concretely — would be invisible to
  `TemplateRequirement`'s generic matcher (which scans the `Sensor`/`Actuator`/`Topology` registries),
  exactly the "5th competing shape" problem avoided everywhere else today.
  **Registration itself stays admin-gated, not plugin-silent**: a plugin may *declare* what it needs
  (same shape as `SensorRequirement`/`ActuatorRequirement`), but the actual registry record is created
  through the admin panel, not auto-registered by the plugin against arbitrary entities — consistent
  with the already-decided pull-only philosophy ("the core still controls when a plugin runs and what
  it sees"); letting a plugin silently register its own `Sensor`s would reopen the same unaudited-
  injection risk one layer up.

**Working order**: one at a time, AR-1 first, mermaid diagram of the full logical architecture after
all 8 are resolved.

### Full architecture re-review — closed 2026-09-01

All 8 findings resolved: the layer model gained Layer 3 (Learning) and was renumbered 0-8;
`WarmupGate`/confidence formulas promoted to concrete types; Manual Hold Manager/Recovery-Checkpoint
placed in Layer 0 with an explicit restart-safety carve-out; the Heating "Season" placeholder split
into three real concepts (calendar `Season`, an extensible `FusionStrategy` registry, a
`PatternLearner`-based house-specific thermal-response model) plus a per-room precedence treatment
matching Lighting's; `FusionRule` vs. `PatternLearner` disambiguated; the Reaction freshness
invariant formalized; namespace convention extended; Layer 7↔Layer 2 connection stated. Mermaid
diagram of the full logical architecture next.

### AR-4 — part 1 resolved 2026-09-01: a real calendar `Season` is worth adding, separate from Heating's thermal work

Developer split AR-4's original "Season" finding into two genuinely different concepts once pressed
on what it actually meant (see discussion below this section) — part 1 is a real calendar season
(spring/summer/autumn/winter), part 2 (Heating-specific thermal signal + house-learned response) is
still being designed, not yet resolved.

**Real use cases found**, distinct from Heating's real-time weather need — calendar season is
deliberately coarse/slow-changing, which is a feature here, not a bug: Lighting's circadian defaults
(sunrise/sunset shift a lot across seasons), Security's presence-simulation realism (a dark house at
17:00 is normal in December, suspicious in June), the planned `watering` domain (seasonality is
large), season-flavored Activity detection (gardening, etc.).

**Source**: Home Assistant's own built-in `season` integration already exposes a sensor with state
`spring`/`summer`/`autumn`/`winter` (meteorological or astronomical, computed from the configured
location) — same pattern already decided for `ExternalContext`/Adaptive Lighting: an ordinary HA
integration, ingested as a plain `Sensor`, not a special case.

**Gap found**: none of today's `Interpretation` variants (Boolean/Bucket/MediaActivity/Presence/
Calendar) cover "the raw HA state is already the target category, just relabel it, no threshold or
vocabulary decoding needed." Needs a new, minimal `CategoricalInterpretation` variant.

**Explicitly not used by Heating** — too coarse and laggy for a real-time setpoint decision (a cold
snap in April shouldn't be ignored because the calendar says "spring"). Heating's own need is
resolved separately, see AR-4 part 2 below (in progress).

### AR-4 — part 2, Part A resolved 2026-09-01: `FusionStrategy` becomes an extensible registry, not a closed enum

Re-examining what Heating actually needs (developer pushback: the naive "OA Reset" curve is too
simple — depends on the house's own thermal mass, and on wind/humidity, not just outdoor
temperature) split the work into two parts. **Part A — the composite external signal** (temp + wind
+ humidity combined into one "apparent/effective outdoor temperature") is resolved here. **Part B —
a house-specific, learned thermal-response parameter** is still being designed, not yet resolved.

Grounded first: wind measurably increases real heat loss (not just perceived temperature — confirmed
via research on building heat-loss coefficients), humidity has a smaller but real effect via
envelope moisture transfer. None of today's 4 `FusionRule` strategies (Direct/BooleanSet/
WeightedQuorum/Precedence) can combine 3 continuous values via a physical formula — this is a
genuine 5th kind of combination, not a variant of an existing one.

**Developer's question, and why it changes the design**: if every domain-specific formula becomes a
new named strategy, does the strategy set need to be pluggable? Considered and rejected two options:
- **Hand-roll it inside `HeatingDomain`** — rejected: exactly the pattern `FusionRule`/`Precedence`
  exist to eliminate (today's `_compute_house_signal`/`_compute_boolean_count_evidence` hand-rolled
  combination logic, already being migrated *into* `FusionRule` for observability). Burying a new
  formula back inside a domain loses `Provenance`, diagnostics visibility, the already-general
  stability/dwell mechanism (would need reimplementing by hand — the same two-parallel-mechanisms
  disease already found and fixed for Lighting/Heating's actuation paths), and permanently blocks any
  future consumer (Security's presence-simulation realism, a future `watering` domain's frost risk)
  from reading it, not just today's Heating-only use.
- **Open third-party pluggability** — rejected as out of scope: reopens the separate, still-unresolved
  Layer 7 third-party plugin question unnecessarily; this is about core-team-added strategies, not
  externally-authored ones.

**Decision**: `FusionStrategy` becomes a protocol/interface (`combine(facts) -> value`) backed by a
registry, not a closed dataclass `Union` — same shape already used elsewhere in this codebase
(`LearningPluginRegistry`, `NormalizationFusionRegistry`), not a new pattern. The 4 existing generic
strategies stay built-in; a new one (e.g. `apparent_temperature`) is added the same way a new
built-in domain is added — core-team code change, not runtime/admin-authored — but without the
per-addition ceremony of extending a hardcoded `Union` and every `match`/switch that consumes it.

**Where the code lives, and why "near" beats "inside"**: the concrete formula implementation lives in
a module adjacent to the domain that needs it today (e.g. near `runtime/domains/heating.py`), but is
registered into the shared `FusionRule` registry by the same composition-root wiring already used for
domains/analyzers/learning modules (`analyzers/registry.py`'s `create_builtin_learning_plugin_registry()`,
`engine.py`'s `builtin_domain_plugins()`) — not imported by Layer 2 itself, preserving the bottom-up
layering (Layer 2 defines the protocol with zero domain knowledge; the wiring layer, which already
sees every layer, assembles it). Concretely: a plain private method on `HeatingDomain` would (a)
require the registry to reach into a domain class's internals to find it — awkward coupling across
layers — and (b) not be independently unit-testable or reusable the way a small, named, standalone
function is. Physical proximity is for developer convenience (easy to find, since only Heating needs
it today); registration is what preserves everything `FusionRule` already provides for free to
everything that goes through it.

**Solar gain folded into this same formula, not a new dimension — refined 2026-09-01.** Prompted by
research (below) showing solar gain varies meaningfully by season and by which side of the house is
exposed: rather than adding a bucket dimension to Part B (would fragment an already-short 7-day
calibration window, see Part B below), the apparent-outdoor-temperature formula itself gets extended
to also read `Topology.exposure_by_room` (already exists, no new field) + time-of-day (which facade
is sun-facing right now) + `weather_condition` (already an `ExternalContext`/`Sensor` slot, for
sky cover). Physically correct: a sunny south exposure *raises* the effective outdoor temperature
(free solar heat doing part of the work), matching the research finding that solar gain offsets
heat loss in winter. All the complexity stays in one place (this formula); Part B stays unaware
solar gain exists at all, it just receives a more accurate delta.

### AR-4 — part 2, Part B resolved 2026-09-01: house-specific thermal-response rate, another `PatternLearner` instance

Developer scoped the use cases down to 2: eco/away setback aggressiveness, and an anomaly signal —
pre-heating (Ecobee-style "smart recovery") explicitly deprioritized as low-value outside old/rural
housing, not designed further here.

**What Heima actually learns, precisely** (corrected once from an initial "duty-cycle" framing,
which doesn't hold up for modulating heating systems that don't cycle on/off in discrete pulses):
for this specific house, **how fast indoor temperature rises or falls (°C/hour)**, as a function of
the delta between indoor temperature and the Part-A composite outdoor-apparent-temperature, and
whether heating is currently on or off. As a `PatternLearner` instance: bucket key =
`(delta_bucket, heating_state ∈ {on, off})`, continuous target = observed rate of indoor-temperature
change (°C/hour) for that bucket, calibrated from this house's own `HouseFact` history (indoor temp
over time, heating on/off state, outdoor-apparent-temp over time) — no new learning primitive, reuses
`PatternLearner`'s already-standardized continuous-target confidence formula (LP-1).

**Calibration window: a rolling 7 days, not all available history — refined 2026-09-01.** Research
(building-science literature) found that building thermal response genuinely varies by season
(mainly via solar gain, see Part A's update above) and that "a seven-day sliding window of training
data can account for seasonal variations in building parameters" without needing an explicit season
dimension. Rejected: adding `calendar_season` (part 1) as a third bucket dimension here — would
fragment an already-data-scarce calibration 4x, working against the warm-up gate (LP-1/LP-2) that
specifically exists to avoid drawing conclusions from too little data. **Where calendar `Season`
(part 1) still matters for Part B**: as the *seed* — before a house has 7 days of its own real
history, the starting value can vary by calendar season as a coarse generic default, then the
rolling window takes over as real data accumulates. Same "seed → calibrated from history" principle
as `LearnedWindow`, applied here without double-counting season in both the seed and an explicit
bucket.

**One learned model, two consumption paths, deliberately different governance**:
- **Anomaly signal**: today's observed rate deviates from the learned baseline rate for the same
  `(delta, heating_state)` bucket → flag via the existing `AnomalyAnalyzer` pattern (statistical
  baseline deviation → `HeimaEvent`) — both directions matter: heating underperforming when on
  (equipment/valve issue) and losing heat faster than usual when off (open window, degraded
  insulation). No new mechanism, no P4b live-signal exception — this is exactly what
  `AnomalyAnalyzer` already does for other things.
- **Setback aggressiveness**: uses the learned *off-state* rate for the current delta to estimate how
  many degrees the house would drift over a planned eco/away setback period; if that exceeds a safety
  bound (frost risk, uncomfortable-on-return), the setback depth gets capped. **Deliberately not a
  live `InferenceSignal`** — expanding the narrow, individually-audited live-signal exception list
  (Activity/Occupancy/HouseState) casually would weaken exactly the property that makes it
  trustworthy. Instead reuses the same governance already decided for Heating's own reconciliation:
  surfaces as a `ReactionProposal` (a "setback calibration" type), admin-reviewed once, and once
  accepted becomes a **configured parameter inside `HeatingDomain`'s eco/away branch** — same
  treatment already given to `heating_preference` (a branch value, not a competing live signal).

### AR-4 — closed 2026-09-01

All three parts resolved: calendar `Season` (part 1, new `CategoricalInterpretation`), the composite
external-conditions signal (part 2A, `FusionStrategy` becomes an extensible registry), and the
house-specific thermal-response rate (part 2B, another `PatternLearner` instance, feeding
`AnomalyAnalyzer` + a reviewed setback-calibration proposal). The original placeholder "Season"
naming from the Heating redesign section is superseded by this — none of the three final concepts is
actually called "Season."

Research sources (part 2, solar gain / seasonal calibration window):
[Optimizing building heating demand through solar-air temperature integration](https://www.sciencedirect.com/science/article/pii/S2214157X25018490),
[System and method for forecasting fuel consumption for indoor thermal conditioning using thermal performance forecast approach](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10823442),
[Usability of Smart Home Thermostat to Evaluate Impact of Weekdays and Seasons on Sleep Patterns](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9015749/).

### Addendum 2026-09-01 — Heating needs the same per-room precedence treatment as Lighting

Developer prompt: `HeatingDomain` should also support per-room control (smart TRV/radiator valves),
not stay whole-house-only forever. Checked before designing anything:

- **No actuator-role gap**: `VALID_ACTUATOR_ROLES` already has `hvac_unit`
  ([actuators.py:50](custom_components/heima/actuators.py#L50)) — a smart TRV is, in HA, just another
  `climate.*` entity, already covered by the existing role. Nothing new needed at the registry level.
- **The real gap is domain logic**: confirmed `HeatingDomain` tracks a single scalar
  `target_temperature`/`_heating_last_target_temp` ([heating.py](custom_components/heima/runtime/domains/heating.py)) —
  no per-room concept at all today.
- **Same disease, same fix already decided for Lighting**: whole-house `HeatingDomain` stays the
  coarse default (fallback branch), a new precise per-room reaction (parallel to
  `room_smart_lighting_assist`) takes priority where a room has its own `hvac_unit` actuator
  configured — related via the same `PrecedenceStrategy` already decided for Lighting's two-tier
  relationship, not a new pattern.
- **Part A/B (this section, above) need zero redesign**: `Sensor`/`FusionRule`/`PatternLearner` all
  already carry `where: Location` as a first-class dimension, never hardcoded to whole-house. A room
  with its own TRV gets its own Part A (apparent temperature + solar gain for that room's exposure)
  and Part B (that room's own learned thermal-response rate) instance, scoped by `Location` = that
  room instead of `casa` — the existing primitives generalize for free, nothing to invent.

---

## Spec-readiness assessment (2026-09-02)

Developer asked whether the architecture and notes so far are enough to start writing real specs.
Verdict: the conceptual architecture is solid and self-consistent (confirmed via the self-contained
rewrite of `v3_architecture_recap.md` and its diagram), but not yet sufficient — concrete, trackable
gaps, not a vague "needs more polish":

- **SR-1** — resolved 2026-09-02. Promoted to its own draft file, `v3_pattern_learner_draft.md`:
  `TargetShape`/`ContinuousConfidenceParams` (the standardized confidence formulas), `BucketKey`/
  `PatternTier` (the generalized tiered fallback), `PatternLearnerConfig`/`LearnedPattern`, and the
  `infer()`/`propose_candidates()` split matching the two governed consumption paths (live signal vs.
  reviewable proposal). Worked example resolves the Heating thermal-response learner from AR-4 part
  2B concretely, with no new fields needed beyond the base shape.
- **SR-2** — resolved 2026-09-02. Promoted to `v3_domains_draft.md`: a shared `PrecedenceRelation`
  shape (Lighting's coarse/precise relationship, reused for Heating's whole-house/per-room one, not
  invented twice); `EntityStepLightMode` for Adaptive Lighting composition; `HeatingBranch` with the
  reconciled single-source-of-truth target; and, closing a real gap found while drafting —
  `HeatingBranch`'s second dimension can't literally be "season" any more (AR-4 dissolved that into
  3 separate concepts), so it's redrawn as a bucketed version of Part A's apparent-temperature
  `FusionRule` output, with `heating_preference` itself rebuilt as a `PatternLearnerConfig` instead
  of a bespoke analyzer. `SequentialConfirmationPolicy` for Security's optional upgrade, composed
  from `Window`+`Importance` alone.
- **SR-3** — resolved 2026-09-02. **Superseded by the clean-start decision of 2026-09-10 below.**
  Simplified by `CLAUDE.md`'s own "no backward compatibility, sole
  user of the project" stance — there's exactly one real install to migrate, no generic tool needed
  for unknown configs.
  - **Config migration**: a one-time, throwaway script (not a maintained compatibility layer) that
    reads the current real `config_entry` and mechanically produces the new registry records
    (`Sensor`/`Actuator`/`Zone`) from today's 9 entity lists + rooms + actuators. Run once, verified
    by hand against the real house.
  - **Learning history**: **no backfill — deliberately abandoned, not attempted.** Checked with the
    developer first: `away` never triggered historically due to a wrong person-tracker config
    (developer's own setup, not a code bug), `sleeping` never triggered due to the now-fixed
    `boolean_signal()` charging-states bug. Both mean the historical `HouseSnapshot`/`EventStore`
    data doesn't just lack those two states — every period that *should* have been `away`/`sleeping`
    is systematically mislabeled as something else, contaminated, not merely sparse. Backfilling it
    would teach `PatternLearner` a confidently wrong pattern from day one, worse than no history at
    all. v3's `house_state` learning starts cold — exactly the case the warm-up gate
    (`v3_house_fact_draft.md`, `WarmupGate`) already exists to handle gracefully, not a gap.
  - **Cutover**: no single big-bang event — each phase (`V3-1` through `V3-8`) that touches
    user-facing config carries its own small migration step when it ships, verified with the same
    targeted-tests-green-plus-live-verification discipline `CLAUDE.md` already requires for any
    merge, just applied to a larger unit of change.
- **SR-4** — resolved 2026-09-02, after the phase breakdown below made the resolution obvious: none
  of the 3 actually block anything before the phase each naturally belongs to — closing them means
  scoping each explicitly, not deciding their substance today.
  - **Plugin discovery mechanism** (entry points vs. `hass.data`) and the **`CLAUDE.md` "no backward
    compatibility" amendment** both only matter once a real public plugin API exists — that's
    `Phase V3-8`, the last phase, by design (needs V3-2/V3-3/V3-4's contracts settled first). Deferred
    to V3-8, not silently open — nothing before it depends on either answer.
  - **Whether Reactions configuration moves fully into the panel** is different in kind: the recap's
    own framing ("once template-matching *reduces* manual authoring") makes this a question that
    needs real usage data from `Phase V3-6` to answer, not a decision that can be made in advance of
    that data existing. Legitimately not a "decide now" item — explicitly deferred with a trigger
    condition: revisit once `V3-6`'s template matching has been live long enough to show whether
    manual "Crea automazione" volume actually dropped.
- **SR-5** — resolved 2026-09-02, phase breakdown below (own subsection, kept out of this list for
  length). Named `Phase V3-1`...`V3-8` — numeric, deliberately distinct from v2's lettered phases
  (`Phase A`, `AR`, `AS`...) so the two are never ambiguous side by side.
- **SR-6** — addressed by practice, not a separate decision: `v3_pattern_learner_draft.md` and
  `v3_domains_draft.md` (SR-1/SR-2) are the first two pieces actually promoted out of backlog prose
  into concrete, spec-adjacent shape — the same promotion the other draft files already went
  through. Converting the rest happens the same way, phase by phase, not as one big translation
  effort.

### Spec-readiness assessment — closed 2026-09-02

All 6 items resolved: `PatternLearner` and the domain redesigns have concrete shapes; a
dependency-ordered phase breakdown (`Phase V3-1`...`V3-8`) exists; the 3 previously-open decisions
are each explicitly scoped (2 deferred to `V3-8`, 1 deferred to real usage data from `V3-6`) rather
than left blank; migration is scoped per-phase with learning history deliberately starting cold, not
backfilled. The architecture and notes are now sufficient to begin writing a real spec for
`Phase V3-1`, the first slice.

**Agreed next steps, in order**: promote `PatternLearner` and the domain redesigns to concrete
shapes (closes SR-1/SR-2); close SR-4's 3 open decisions one at a time (or explicitly scope them out
of the first phase, not left silently blank); sketch a v2-style phase breakdown (closes SR-5); address
migration strategy at least at a high level (closes SR-3, doesn't need to be exhaustive yet).
**Reordered 2026-09-02**: phase breakdown moved before closing SR-4's 3 open decisions — several of
them may turn out to be scoped to a late phase rather than needing a decision now.

---

## Phase breakdown — `Phase V3-1` through `V3-8` (2026-09-02)

Dependency-ordered, bottom-up by architecture layer (`v3_architecture_recap.md`). Each phase is
meant to be independently implementable and testable, the same discipline `docs/v2_dev_plan.md`
already uses — not a commitment to build all 8, just the ordering if/when each is picked up.

- **Phase V3-1 — Substrate & cross-cutting** (Layer 0 + Layer 1). `HouseFact`/`Provenance`/
  `FactSource` (extending today's `ApplyStepSource`), `Location`/`Zone`/`Topology` (Topology carries
  over unchanged from Phase AR), the Timing primitives (`Window`/`LearnedWindow`/`WarmupGate`/
  `AtJob`/`CronEntry`/`CalendarWindow`), the two-tier `EventStore`/`SnapshotBuffer` persistence.
  Manual Hold Manager migrates onto `HouseFact` (with its restart-safety carve-out, AR-3). Recovery/
  Checkpoint stays untouched by design. Nothing above this phase can start before it lands —
  everything else is *built from* Layer 0-1.
- **Phase V3-2 — Registries** (Layer 2). `Sensor`+`Interpretation` collapsing the 9 separate entity
  lists found in the external review pass; `FusionRule`+`FusionStrategy` as an extensible registry
  (the 4 generic strategies plus `Precedence`); `Actuator` extended with the `light` role and shared
  `Location`. Ships with its own admin-panel CRUD (Layer 8 work bundled in per phase, not a separate
  late UI phase — matches the dedicated-CRUD pattern already decided for this layer).
- **Phase V3-3 — Learning** (Layer 3). `PatternLearner` (`v3_pattern_learner_draft.md`); every
  learning family rebuilt on it; the 3 scaffolding modules removed (`LightingPatternModule`,
  `HeatingPreferenceModule`, `WeekdayStateModule`) and `RoomStateCorrelationModule` folded into
  `HouseStateInferenceModule` as a tier; the warm-up gate; family governance unified across the
  live-module and registry-analyzer tiers (LP-3); atomic `HouseFact` query API (LP-4) with the
  `EventStore` indexing it depends on (LP-5). Depends on V3-1 (reads `HouseFact` history) and V3-2
  (mines what Registries produce).
- **Phase V3-4 — Domain resolution** (Layer 4, core). `HouseState` Track 1 (calibrating the 7 closed
  definitions instead of proposing new ones), `Activity` Track 2 (the missing discovery mechanism),
  Calendar formalized as `CalendarWindow`/`CalendarInterpretation` Timing infrastructure (a
  `CLAUDE.md` wording fix, not a code change), People/Occupancy re-grounded on `Sensor`+`FusionRule`
  (already the healthiest domains, lightest lift here). Depends on V3-2/V3-3.
- **Phase V3-5 — Domain-specific redesigns** (Layer 4 plugins). Lighting's `PrecedenceRelation` +
  Adaptive Lighting composition; Heating's reconciled `HeatingBranch` + the thermal-response
  `PatternLearner` pair (`v3_domains_draft.md`); Security's `SequentialConfirmationPolicy` (lowest
  priority of the three, can slip independently). Depends on V3-2 (Sensor/FusionRule), V3-3
  (PatternLearner) — this is why it's a separate phase from V3-4, not bundled into it.
- **Phase V3-6 — Reactions & template matching** (Layer 5). `ReactionProposal` consolidated onto
  `HouseFact`+`Provenance`; `TemplateRequirement` + the generic matcher
  (`v3_template_matching_draft.md`). Depends on V3-2 (Sensor/Actuator/Topology registries the matcher
  scans) and V3-4/V3-5 (what a Reaction can actually read).
- **Phase V3-7 — Notifications** (Layer 6). Unify the Tier-1/Tier-2 fork, build the digest capability,
  the 3-tier quiet-hours model. **Hard sequencing constraint, not just ordering**: the digest must
  ship no later than V3-6's template-match proposals do, or auto-proposals just relocate the spam
  problem instead of fixing it (already flagged in `v3_template_matching_draft.md`) — V3-7 and V3-6
  should land together, not V3-7 trailing behind.
- **Phase V3-8 — Extensibility** (Layer 7). `register_plugin` discovery mechanism (entry points vs.
  `hass.data`), fault isolation, capability tiers, the `CLAUDE.md` "no backward compatibility"
  amendment. Depends on V3-2/V3-3/V3-4 all being stable — a plugin seam opened before the core
  contracts it plugs into have settled would need re-opening. Last on purpose, not an afterthought.

Migration is not its own phase — see SR-3 below, it cuts across whichever phases touch already-live
config.

---

## Backlog items

### V3-1 — `room_smart_lighting_assist` silently never fires despite valid learned config (studio)

**Found:** 2026-08-29, cross-checking the developer's real config entry
(`config_entry-heima-01KS8ASBC1TSBTYTP9RJRAKKBH.json`) and diagnostics snapshot
(`debug/diagnostics_snapshots/20260828_000001/learning_audit.txt`) against `sensor.heima_reactions_active`.

- Reaction `38f7e744-99cb-413f-9d12-60fdfc9570eb`, room `studio`, `reaction_type: room_smart_lighting_assist`.
- Learned legitimately: `CompositePatternCatalogAnalyzer` confirmed 20 episodes (113 detected) over
  2 weeks, `sensor.sensore_studio_illuminance` as primary signal, followup entities
  `light.finestra_studio` / `light.porta_studio`. Proposal accepted at confidence 0.77 ("10 observed
  episodes" / "12 observed episodes" across two acceptance events).
- Config looks correct per this session's own lte/eq discussion: `primary_bucket: "dim"`,
  `primary_bucket_match_mode: "lte"` (not the `eq` trap), `house_state_filter: null`,
  `suppress_on_states: ["away", "vacation"]`, `enabled: true`.
- **`fire_count: 0` since creation on 2026-06-15** — over 2 months, never fired once
  (`sensor.heima_reactions_active` attributes).
- A second reaction of the same type/room (`57c9fba3-...`, `origin: learned`,
  `house_state_filter: "vacation"`) exists and doesn't even appear in
  `sensor.heima_reactions_active`'s reaction list — possible orphan, or the active-reactions
  sensor silently drops entries whose `house_state_filter` can't currently match. Unconfirmed.
- **Not caught by existing anomaly detection.** `AnomalyAnalyzer` (Phase Q/AA, `DONE`) has
  `presence_pattern_drift` and `lighting_scene_drift` rules — both detect *pattern* drift, neither
  detects "a configured, enabled reaction has never executed." Confirmed by reading
  `runtime/analyzers/anomaly.py`: no such rule exists.

**Why this matters for v3, beyond fixing the one bug:** this is the same reaction type just
configured for the kitchen in this session (see chat: `room.smart_lighting_assist.basic`,
`lte`/`dim`). If the root cause is structural (not a one-off), it'll silently repeat there too,
and nothing in the current observability stack would surface it — there is no "reaction has
fire_count 0 after N days of being enabled + its trigger conditions plausibly occurring" check
anywhere in the system.

**Deferred, not investigated further this session** — developer chose to queue it rather than
debug now (2026-08-29). Candidate root causes to check when picked up (not verified):
- Bucket boundary drift: room's currently configured `room_lux` buckets vs. what the pattern was
  learned against — could have been recalibrated after the reaction was created.
- `require_room_occupancy: true` (in `learning_diagnostics`, not confirmed if enforced at eval time)
  — is studio occupancy actually resolving `True` when expected?
- Corroboration state: both reactions show `corroborated_episodes: 0` against
  `corroboration_promote_min_episodes: 3` — promoted without corroboration ever being satisfied;
  unclear if that's an accepted promotion path or a lifecycle edge case.
- Possible engine-level bug in composite reaction re-evaluation / dedup-apply logic
  (`_needs_apply` / `_entity_steps_need_apply` in `smart_lighting_assist.py`) interacting with
  checkpoint/recovery state across restarts.

---

## Mapping notes (raw evidence, not yet items)

### Learning proposal volume is real, not just a perception

`docs/specs` reference: none yet — this is empirical, from `learning_audit.txt` (2026-08-28 snapshot).

| family | total | accepted | rejected | pending | notes |
|---|---|---|---|---|---|
| house_state | 544 | 220 | 41 | 283 | only family with pending items right now |
| composite_room_assist | 5 | 5 | 0 | 0 | small but 100% acceptance, real patterns (10-20 episodes) |
| lighting (context_conditioned_lighting_scene) | 4 | 3 | 1 | 0 | |
| security_presence_simulation | 6 | 6 | 0 | 0 | 100% acceptance |
| heating | 3 | 0 | 3 | 0 | learned correctly, developer rejected all 3 |
| presence (presence_preheat) | 0 | 0 | 0 | 0 | never produces anything |
| scheduled_routine | 0 | 0 | 0 | 0 | admin-authored only, no auto-learning path |

Built-in self-awareness already exists for some of this: `learning_audit.txt`'s "Weekly Review
Signals" section already computes `quiet enabled families: presence, scheduled_routine` — i.e. the
system already has a notion of "this enabled family produces nothing." Worth reusing/extending
rather than reinventing in v3.

**house_state:presence(other families) ratio ≈ 30:1.** This — not a lack of other learning — is
why the developer's day-to-day experience is "I only ever see house-state notifications."

### Notifications: a two-tier fork, not just "5 fragmented channels" (mapped 2026-08-30)

Revising the earlier framing — it's not 5 unrelated channels, it's **two tiers of the same concern
that never merged**, and each is broken for a different reason.

**Tier 1 — `EventsDomain` → `HeimaEventPipeline` (`runtime/notifications.py`, 1501 lines).**
A proper core-DAG domain (`runtime/domains/events.py`, owns `HeimaEventPipeline` +
`NotificationDeliveryPolicy`). Sophisticated: dedup, rate-limiting, per-audience rendering
(`_render_people_event`/`_render_reaction_event`/`_render_condition_event`/`_render_system_event`),
aggregation windows, actionable notifications with response handling (`ActionableNotification`,
fails closed rather than degrading — deliberate design per its own docstring), route/recipient/group
resolution (Phase AN, AP, both `DONE`). Handles operational events: reaction fired, people
presence, conditions, system health.

Read `HeimaEventPipeline.async_emit` closely (`notifications.py:767-835`): it **always** fires an
internal HA bus event (`self._hass.bus.async_fire(EVENT_HEIMA_EVENT, payload)`), but only calls an
actual `notify.*` service if `effective_routes` resolves to something non-empty from configured
recipients/groups/routes. **No fallback to `persistent_notification` when unconfigured — it just
delivers nothing, silently, by design.**

Checked the developer's real config entry: `notification_recipients`, `notification_groups`,
`notification_routes`, `notification_delivery_policy`, `notification_services` are **all `None`** —
never configured. So Tier 1 has been 100% dormant since setup; `notify_route_delivered: 0` /
`notify_route_errors: 0` / etc. (confirmed via `sensor.heima_event_stats`) is the *correct* output
of an unconfigured-but-working system, not a bug in the pipeline itself.

**Tier 2 — raw `persistent_notification.create` calls in `coordinator.py`.**
`_async_notify_house_state_proposal`, `_async_notify_activity_proposal`,
`_async_notify_signal_discovery_proposal`, `_async_notify_semantic_policy_proposal` (via
`_async_notify_installer_alert`) all call `persistent_notification.create` directly — no dedup
window beyond a bare `notification_id`, no routing, no audience rendering, no way to point it
anywhere but HA's built-in panel, no actionable buttons. **This is the only thing the developer has
ever actually received from Heima.**

**Why the fork exists** (not just "someone forgot"): Tier 1 events are emitted from *inside* the
engine's per-cycle DAG evaluation, where `EventsDomain` naturally sits. Tier 2 producers
(proposal review, signal discovery audit) run as independent async housekeeping tasks in
`coordinator.py`, outside the engine cycle entirely — they never had a natural touchpoint with
`EventsDomain` to route through, so each one grew its own direct `persistent_notification` call
instead.

**Net effect for the developer**: the elaborate, configurable, actionable notification system
(Phase AN/AP, both `DONE`, real engineering investment) is invisible and inert; the thing generating
5-10+/day of real volume is structurally incapable of ever using it, config or no config.

### Tier 1 completeness audit (2026-08-30) — good quality for its original scope, real gaps for proposals

Read `NotificationDeliveryPolicy.decide` in full: it's genuinely well-built — 12 distinct decision
outcomes (`deliver`/`observability_only`/`disabled`/`startup_grace`/`waiting_persistence`/
`suppressed_aggregation`/`suppressed_category`/`suppressed_dedup`/`suppressed_rate_limit`/
`suppressed_burst`/`missing_audience_target`/`delivery_deferred`), a startup grace period, a
deferred-delivery retry queue (`_deferred_route_deliveries`), and `ActionableNotification`
explicitly documented as **fail-closed** rather than silently degrading to text — this is careful
design, not a stub. Reconnecting Tier 2 into it is not just "call the right function" though; three
concrete capability gaps would block it as-is:

1. **No digest/batch-summary capability.** `_aggregation_bucket`/`_aggregation_window_s`
   ([notifications.py:1186-1208](custom_components/heima/runtime/notifications.py#L1186-L1208))
   only coalesce *repeats of the same event* for exactly 2 families (`people` presence transitions,
   `occupancy_mismatch`/`security_presence_mismatch`). There is no mechanism to batch *N distinct
   items* into one message — which is exactly what proposal notifications need ("12 new suggestions
   today", not 12 separate pushes). Without this, connecting proposals to Tier 1 as-is would just
   move the spam problem into the "proper" pipeline instead of fixing it.
2. **No quiet-hours / do-not-disturb window.** Grepped for it — nothing. No time-of-day
   suppression, no tie-in to `house_state == "sleeping"` (a concept that already exists elsewhere,
   e.g. lighting's `night_mode_states`, just never applied here).
3. **Family/policy taxonomy is shaped for discrete "something happened" events, not "N items are
   pending review."** `classify_notification_event_family`
   ([notifications.py:684-705](custom_components/heima/runtime/notifications.py#L684-L705))
   recognizes `people`/`house_state`/`reaction`/`security_critical`/`security_presence_mismatch`/
   `occupancy_mismatch`/`system_config_issue` — note `house_state` here means *operational state
   transitions* (sleeping/working/...), an entirely different thing from `house_state_learned_context`
   *proposals*. There is no family for "a proposal/review item exists" at all; bridging Tier 2 in
   needs a new family (or a new event shape entirely), not just emitting existing `HeimaEvent`s from
   proposal code.

**Actionable notifications exist but are proposal-review-adjacent, not proposal-review-connected.**
`async_send_actionable`/`ActionableNotification` are used **only** by
`runtime_confirmation_controller.py` (Phase AH — confirming a specific pending runtime action before
auto-apply). Nothing wires accept/reject of a *learning proposal* to a notification action button —
that would be new work, not a reconnection of something already built for this purpose.

### Config surface fragmentation, quantified

~20 options-flow menu entries (`init` step `menu_options`), 8 rooms, 8 configured reactions, plus a
separate admin panel (`AO`/`AO8`) for observability — no single "what's configured where" view
inside the config flow itself.

### Reaction lifecycle gaps observed live

- Orphan/duplicate reaction row for the same `(reaction_type, room_id)` pair (see V3-1).
- Kitchen (`cucina`) already has `occupancy_sources` (1) and `learning_sources` (2) configured but
  zero `signals` and zero reactions — partially set up, matches this session's walkthrough.
- Only 2 of 8 rooms (`studio`, `soggiorno`) have any reaction configured at all.

---

## Open questions carried from chat

1. ~~Should every `AdminAuthoredTemplateDescriptor` export declarative `requirements`...~~
   **Resolved 2026-08-31** — modeled in full in `docs/v3_template_matching_draft.md`:
   `TemplateRequirement`/`SensorRequirement`/`ActuatorRequirement` on
   `AdminAuthoredTemplateDescriptor`, a generic matcher against `Sensor`/`Actuator`/`Location`,
   defaults derived from matched `Interpretation` data (closes the room-type-heuristic question
   too), routed through the `silent` quiet-hours tier + the still-unbuilt digest capability
   (explicit sequencing dependency, not optional).
2. ~~Should the 5+ discovery/notification channels...~~ **Resolved 2026-09-01** — yes, unify, but
   not a separate initiative: item 1's resolution already requires digest/batch + quiet-hours for
   `TemplateRequirement`-driven proposals ("sequencing dependency, not optional"). Once that
   infrastructure exists, every Tier 2 producer (`_async_notify_house_state_proposal`,
   `_async_notify_activity_proposal`, `_async_notify_signal_discovery_proposal`,
   `_async_notify_semantic_policy_proposal`/installer_alert —
   [coordinator.py:2388-2541](custom_components/heima/coordinator.py#L2388-L2541), confirmed direct
   `persistent_notification.create` calls, no dedup/routing/actionable buttons) migrates to
   `EventsDomain`/`HeimaEventPipeline` under a new `proposal_review` family (batched), replacing the
   direct calls entirely. No parallel work — the same infrastructure build serves item 1 and this.
3. ~~Why does `house_state_learned_context` operate outside `enabled_plugin_families`...~~
   **Resolved 2026-09-01** — grounded: two independently-evolved learning pipelines exist, never
   reconciled. `LearningPluginRegistry`
   ([registry.py:291](custom_components/heima/runtime/analyzers/registry.py#L291)) — presence/
   heating/lighting/composite_room_assist/security_presence_simulation — is what
   `enabled_plugin_families` actually gates. A separate set of `HeimaLearningModule` instances
   (Weekday/Heating/HouseState/Activity/Lighting/RoomStateCorrelation) is unconditionally constructed
   in [coordinator.py:359-391](custom_components/heima/coordinator.py#L359-L391), with zero
   enable/disable path. `HouseStateInferenceModule` (source of `house_state_learned_context`) lives
   in this second, ungated set — not a deliberate exception, the same parallel-mechanism disease
   found elsewhere today (Lighting, Heating), applied to the learning infrastructure itself.

   **Not a patch to the current gate**: house_state's current mechanism (544 discrete
   weekday×hour×room proposals) is already superseded by the Track 1 redesign ("House State vs.
   Activity" section) — a continuously self-calibrating model with no per-instance proposal to
   approve/reject. Once built, add it as a proper family in `enabled_plugin_families`, for a concrete
   reason beyond consistency: today, rejecting individual house_state proposals already acts as a de
   facto off-switch per context; once learning becomes continuous calibration with no discrete
   instances to reject, the family toggle becomes the **only** lever an admin has to keep a domain on
   fixed seed definitions instead of drifting via calibration. Same reasoning extends to the future
   Activity-discovery family (track 2) and to lighting/heating's own calibration-shaped learning —
   not house_state-specific.

   **When disabling a learning family makes sense at all** (same rationale for every family, core or
   plugin, motivating why the toggle is worth having): admin prefers static, predictable,
   manually-tuned behavior over auto-calibration; isolating which family is responsible for a
   misbehavior during debugging; a household where a pattern structurally doesn't apply (e.g.
   `presence_preheat` for an always-occupied home, already flagged elsewhere in this backlog as
   low-applicability) and its output is pure noise; a fresh install where the admin wants to lock in
   known-good manual thresholds before enough data exists for calibration to be trustworthy.
4. ~~Is there a reason Phase T and Phase AT were deferred that's still valid...~~
   **Resolved 2026-09-01 — Phase T: T1 stays not-worth-building** (redundant with `LightingAnalyzer`,
   reconfirmed by this session's Lighting redesign — the `Precedence` layer doesn't need a
   scene-name-only signal). **T2 is retired, not just still-blocked** — today's "House State vs.
   Activity" decision (track 2) means new learned behavior is never modeled as a house-state rule; it
   becomes a new Activity instead. T2's premise (a "house state rule" `reaction_type`) is superseded,
   not pending — do not resurrect it even if a `scene.*`-accepting reaction type is ever added.

   **Phase AT**: dependency (AR) has been `DONE` for a while — AT was never actually waiting on it,
   it was split out because not yet needed, not because AR was incomplete. AT2 (Occupancy) still
   lacks its named consumer, unchanged. Checked whether this session's `TopologyRequirement`
   (reaction-eligibility gate, Layer 4) subsumes AT1/AT3 — it doesn't: `TopologyRequirement` decides
   whether a *reaction* is offered in a room; AT1/AT3 are `HouseStateDomain`/`SecurityDomain` reading
   topology directly inside their own per-cycle `compute()` — a different layer, complementary, not
   overlapping. Both phases stay `DEFERRED` as-is; only the written rationale is sharpened here.

---

## Layer 0 promoted to a real spec, first amendment found along the way (2026-09-02)

`v3_architecture_recap.md`'s Layer 0 section and this backlog's own Manual Hold Manager /
Recovery-Checkpoint notes (2026-08-31, AR-3) were promoted into a full spec:
`docs/specs/v3/layer0_runtime_spec.md`. Written self-contained (does not assume the reader has read
v2's specs or this backlog) — where v2 already solved a piece of the problem, the spec restates the
solution in full rather than pointing at it. Most of the promotion is direct formalization of
decisions already on record here (Timing's `AtJob`/`CronEntry`/`Window`/`LearnedWindow`, the
two-tier `HouseFact` persistence model, the `FactSource`/`ApplyStepSource` unification). One finding
during the promotion is a genuine new decision, not just formalization:

**Manual Hold Manager — conditional restoration after a clean restart, amending AR-3's blanket
rule.** AR-3 (2026-09-01) and the Phase AQ non-goal it cites both state, unconditionally: an implicit
hold is never restored from a checkpoint after a restart. Developer pushback while reviewing the
Layer 0 spec: is that valid for *every* sensor/actuator regardless of context, or only where the
signal that detects an implicit hold is actually unreliable right after a restart (the
power-restore-artifact ambiguity the rule exists to guard against)?

Grounded against v2's actual `manual_hold_framework_spec.md` before answering (not assumed): v2
**already** distinguishes implicit holds (in-memory, inferred from divergence, never restart-eligible)
from explicit holds (helper-entity-backed, already restart-safe for free via HA's own entity
persistence — no Heima mechanism needed at all). The v3 collapse of both into one generic
`HouseFact`-based hold shape (external review pass, 2026-08-31) had silently dropped this
distinction — reinstated in the Layer 0 spec (§6), not rediscovered as new.

**Resolved 2026-09-02**: for implicit holds specifically, conditional restoration is now possible,
narrowly gated, opt-in, never silent:
- eligibility is a property of the specific actuator/sensor behind the hold
  (`implicit_hold_restore_class`, Layer 2), not of the functional domain — risk varies far more
  within a domain than across domains, resolved and frozen into the hold's own evidence at creation
  time, never queried live from the registry (keeps Layer 0 dependent on nothing above it);
- restoration requires the hold to not have expired, the entity to be classified restore-eligible,
  Recovery's classification to show no restart-cleanliness ambiguity for that entity
  (`power_restore_candidate`/`unknown_during_downtime`, or cycle-level `power_recovery`/
  `degraded_recovery`/`recovery_settling`), and the entity's current live state to still match what
  was captured when the hold was created — all four, not any one;
- every restoration is unconditionally recorded as a `HouseFact` that Layer 6's notification pipeline
  turns into a resident-facing message — never silent, regardless of which check passed. This is what
  actually closes AR-3's original "resident unaware" risk, on top of getting the restore decision
  right.

Default stays "never" (today's v2 behavior, unchanged) until an installer explicitly marks a specific
entity eligible — this is a narrow, explicitly-declared amendment to AR-3/Phase AQ's non-goal, not a
silent reversal of it. Full mechanism, including how the data survives a restart the in-memory table
itself cannot (a redundant, event-triggered checkpoint entry, not the durable `HouseFact` audit log):
`docs/specs/v3/layer0_runtime_spec.md` §6.3.

`v3_architecture_recap.md`'s Layer 0 / Manual Hold Manager entry is updated to match (still states the
default rule, now with a pointer to the narrow exception instead of presenting it as absolute).

---

## Layer 1 promoted to a real spec — AR-4 finally closed, one boundary bug found (2026-09-02)

`v3_house_fact_draft.md` promoted into `docs/specs/v3/layer1_substrate_spec.md` (`HouseFact`,
`Provenance`, `Location`, `Zone`, `Topology`), same self-contained discipline as Layer 0. Two findings
during a cross-spec coherence pass (developer-requested, checking the new spec against
`v3_sensors_actuators_draft.md` and `v3_template_matching_draft.md`, not just against itself) turned
out to matter more than the promotion itself.

**AR-4 finally resolved — `FusionStrategy` stays a closed union, gains a fifth, deliberately narrow
member.** AR-4 (2026-09-01) was left explicitly open: Heating's "Season" (derived from `outdoor_temp`
with hysteresis, a genuine calculation) has no clean home among the 4 confirmed `FusionRule`
strategies. It stayed open long enough that **AR-5, resolved the very next day, silently assumed an
answer to it** — AR-5's own resolution text lists `FusionRule`'s synchronous logic as
"boolean/quorum/precedence/**registered formula**," using a term AR-4 never actually defined. Found
only because the Layer 1 promotion forced a direct read of `v3_architecture_recap.md`'s Layer 2
section side by side with `v3_sensors_actuators_draft.md`'s actual `FusionStrategy` type — and the two
disagreed: the recap described "formula-based strategies... in an extensible registry," while the
concrete draft type was `DirectStrategy | BooleanSetStrategy | WeightedQuorumStrategy |
PrecedenceStrategy` — a closed 4-member union, no formula variant, no registry mechanism at all.

Weighed both pure positions (open registry vs. closed union) before deciding — full reasoning in the
session transcript, not repeated here. **Resolved 2026-09-02, hybrid**: `FusionStrategy` stays a
**closed, exhaustively pattern-matchable union**, consistent with how this model treats every other
closed vocabulary (`HouseState`, `FactSourceKind`, `RecurrencePattern`'s two variants) — but gains a
fifth member, `FormulaStrategy(formula_id: str)`, which carries no calculation logic itself, only a
reference into a **separate, core-team-curated formula registry** (mirroring
`NormalizationFusionRegistry`'s existing plugin pattern, already precedented in the current codebase —
not a new mechanism). A new formula (Season, a future "effective outdoor temperature") is a new
registry entry, never a change to `FusionStrategy` or to code that pattern-matches on it — this is
what the recap's "extensible registry" language was actually reaching for, just misplaced onto the
wrong type. Bonus: `FormulaStrategy` is continuous-shaped by definition (a formula combines multiple
continuous inputs into one value), so its confidence treatment is settled for free —
`continuous_confidence` (Layer 1 §4.2), always. `v3_sensors_actuators_draft.md` and
`v3_architecture_recap.md` (Layer 2 section) updated to match; `layer1_substrate_spec.md` §9 narrowed
accordingly (boolean-set's confidence mapping is still genuinely open, formula-based no longer is).

**Boundary bug found in the new Layer 1 spec itself, self-inflicted**: `layer1_substrate_spec.md` had
defined `TopologyRequirement` inside Layer 1, justified in its own text as "a requirement kind for
automation template matching (**Layer 5**)" — while correctly *not* defining its siblings
`SensorRequirement`/`ActuatorRequirement` there, since those clearly belong to Layer 5's
template-matching concern even though they reference Layer 1/2 types. `TopologyRequirement` is in
exactly the same category (a Layer 5 predicate referencing Layer 1's `Topology`) and was carried over
into Layer 1 only because the original `v3_house_fact_draft.md` draft happened to place it textually
next to `Topology`, never re-examined against the boundary the spec itself later established.
**Resolved 2026-09-02**: removed from `layer1_substrate_spec.md`; canonical definition stays where it
already correctly lived, `v3_template_matching_draft.md`, alongside `SensorRequirement`/
`ActuatorRequirement`. Layer 1 states only that `Topology` is queryable by Reactions and template
requirements, same as it already did for `Sensor`/`Actuator`.

---

## `confidence` standardization corrected: "never ad hoc" was overloaded into "never a third", these
## are different rules (2026-09-03)

Drafting Layer 2's `BooleanSetStrategy` confidence mapping (the one item left open by Layer 1 §9)
exposed that Layer 1 §4.2's own wording — "exactly two standardized forms... never a third" — had
quietly turned a discipline rule into a cardinality cap, and developer pushback ("non sono convinto
che 'mai una terza formula, punto' sia corretto") was right to distrust it.

**What the original LP-1/LP-2 audit actually established**: four incompatible, ad hoc, uncentralized
formulas existed, one demonstrably wrong. The fix that matters is that every confidence computation
goes through a function Layer 1 owns and vets — never one a producer invents at its own call site.
That a hard cap of exactly two happened to fall out of the audit's specific findings was incidental,
not the actual rule, and treating it as load-bearing made the model brittle against a computation
pattern the audit's two source-domains (Learning's categorical/continuous predictions) never needed to
cover: a *deterministic logical combination* over already-known confidences (`BooleanSetStrategy`'s
AND/OR), which is neither a statistical match-ratio nor a passthrough.

**Resolved 2026-09-03**: `combined_confidence(confidences, combinator: "min"|"max")` added as a third
pure function Layer 1 owns (§4.2) — `min` for a conjunction (an AND is only as trustworthy as its
weakest premise), `max` for a disjunction (an OR is as trustworthy as its strongest confirming
premise), by De Morgan symmetry across a `BooleanSetStrategy`'s True/False branches. This closes the
last open item from Layer 1's own confidence-mapping table: `WeightedQuorumStrategy` →
`categorical_confidence`, `DirectStrategy`/`PrecedenceStrategy` → inherit-unchanged, `FormulaStrategy`
→ `continuous_confidence` (already resolved with AR-4), `BooleanSetStrategy` → `combined_confidence`.
The set of functions Layer 1 owns is still closed and small, and still never grown for a producer's
convenience — this one addition was deliberate, vetted, and precedented by the exact same treatment
already given to `FusionStrategy` gaining a fifth member instead of staying artificially capped at
four. `layer1_substrate_spec.md` §4.2 rewritten to state the corrected rule ("never ad hoc," not "never
a third") and §9's boolean-set item is closed.

---

## Layer 2 promoted to a real spec; a process check paid off — closed vocabularies needed per-value
## definitions, not just a closed list (2026-09-03)

`v3_sensors_actuators_draft.md` promoted into `docs/specs/v3/layer2_registries_spec.md` (`Sensor`,
`Interpretation`, `FusionRule`, `Actuator`), same self-contained discipline as Layers 0-1. Assigning
`FusionRule`-produced facts a `FactSource.kind` surfaced a real ambiguity — is a same-cycle
deterministic combination `"sensor"` or `"analyzer"`? — that Layer 0 §5 could not actually answer:
`FactSourceKind`/`FactSourceActorType` were a closed `Literal` list with **no per-value definition**,
unlike `RecoveryState` in the same document, which has one.

Developer asked directly whether this meant Layer 0 and Layer 1 needed re-reviewing before trusting
Layer 2 further. **Answer worked out, not just asserted**: a full re-review of both wasn't warranted
(both had already been through multiple targeted critical passes that found and fixed real issues —
redoing all of that would be expensive and mostly redundant) — but a **targeted scan for the same bug
class** (a closed vocabulary listed without per-value definitions) was, and did find exactly one real
instance: `FactSourceKind`/`FactSourceActorType`. Everything else checked (`Location.scope`,
`implicit_hold_restore_class`, `combined_confidence`'s combinator) already had adequate surrounding
definition. Layer 1 had none of this class of gap at all.

**Resolved 2026-09-03**: `layer0_runtime_spec.md` §5 — every `FactSourceKind` (12) and
`FactSourceActorType` (8) value now has a one-line definition, same treatment `RecoveryState` already
had. This resolved the ambiguity that started this: `"analyzer"` is defined as "derived from combining
or analyzing existing data rather than one direct entity read" — `FusionRule` qualifies by that
property regardless of being same-cycle and deterministic, "analyzer" was never meant to mean
"statistical" specifically. `layer2_registries_spec.md` §7 updated to cite the resolved definition
with confidence instead of asserting it.

**Two further corrections found drafting Layer 2's confidence mapping, both from the same underlying
instinct** (developer: "non sono convinto" applied a second time, this session, productively):

1. **`confidence=0.0` as the unavailable-placeholder was itself the wrong kind of fix.** `0.0` is a
   legitimate point inside the real confidence range, so a producer/consumer that forgets to check
   `available` first reads a plausible low number instead of an unmistakable absence.
   **Resolved**: `Provenance.confidence` (Layer 1 §4) is now `float | None` — `None` exactly when
   `available=False`, mirroring `value`'s own use of `None` (already part of `EvidenceValue`) for the
   same case, and letting a type-checker catch a missing `available` check that a magic number never
   could.
2. **`WeightedQuorumStrategy`/`BooleanSetStrategy` excluding unavailable inputs (§5.5) can leave a
   *nonempty* population that's still too thin to trust** — e.g. 4 of 5 sensors going `available=False`
   together (a lost Zigbee segment) leaves one sensor's vote to compute a confident-looking ratio from
   alone. Not the same case as the fully-empty population (already handled), and not something
   Recovery's system-wide `degraded_recovery` classification (Layer 0 §7.1) reliably catches either —
   that operates at a different, whole-runtime granularity, not per-`FusionRule`. **Resolved**: applied
   the same discipline Layer 1 §4.2 already established for `min_support` (a completeness gate,
   deliberately kept separate from confidence itself) to this case — `min_available_weight`
   (`WeightedQuorumStrategy`) and `min_available` (`BooleanSetStrategy`), both new fields, below which
   the derived fact is `available=False` without a confidence call, same outcome as the empty-population
   case, a less extreme trigger, still never blended into the confidence number.

Also fixed while drafting Layer 2, lower-stakes: the `workday_entity` `PrecedenceStrategy` example
(inherited verbatim from `v3_sensors_actuators_draft.md`, predating `CalendarInterpretation`'s own
`priority_order`) read like a flat 5-way precedence chain when the correct shape is 2 sensors, with
`CalendarInterpretation`'s own `priority_order` resolving the 4 calendar categories internally first —
clarified in `layer2_registries_spec.md` §5.1. `RegisteredFormula.compute` (§5.3) gained a `min_inputs`
field and an escape hatch (`-> tuple[Any, float] | None`) to report "insufficient inputs" instead of
being forced to always return a value.

---

## Layer 2 critical pass (round 2): a real gap in `available`'s scope, a redundant field dropped, an
## asymmetric-timing gap found from a concrete product concern (2026-09-04)

A second critical pass on `layer2_registries_spec.md`, developer-requested, checking Layer 2 against
Layer 0/Layer 1 and against itself. Three findings, each worked through in discussion before editing,
not applied on the first idea.

**1. `available`'s scope was incomplete, and the document already silently depended on the missing
part.** §3.1 only covered raw HA entity unavailability. But §5.1's `workday_entity` `PrecedenceStrategy`
example (added in round 1, same session) already assumed a *second* trigger — the calendar `Sensor`
producing `available=False` when no `CalendarInterpretation` keyword category matches an event, even
though the entity itself is fine. Never stated as a rule. Developer proposed the alternative first (a
default fallback "no event" value) — checked, and rejected on the developer's own reasoning applied
one step further: a fallback value would make the calendar `Sensor` always `available=True`, so
`PrecedenceStrategy` (which selects on `available`, not on value content) would never fall through to
the raw `workday_entity` fallback at all — the very mechanism it exists for stops working. **Resolved**:
§3.1 rewritten with two explicit triggers (entity unreachable; entity reachable but its
`Interpretation` can't produce a value) — the second is not a property of every `Interpretation`, only
`CalendarInterpretation`'s open, admin-defined keyword vocabulary can fail to match; the other four
decode from closed HA-defined vocabularies and always produce a value once available.

**2. `value=None` alongside `available=False` was redundant, and asymmetric with `confidence=None`
for a real reason, not by oversight.** Developer noticed §3.1 set `value=None` *and* `available=False`
together and asked directly: if one implies the other, why two fields? Correct, for `value` — but not
for `confidence`, and the difference matters: `confidence: float | None` becoming `Optional` was
motivated by a genuine type-checker benefit (Layer 1 §4.1, round 1) — a narrow type lets static
analysis force a caller to handle the `None` case. `value: Any` can never get that benefit under any
convention, since `Any` accepts everything regardless of what sentinel is chosen — so making `value`
`None` alongside `available=False` bought nothing, it was redundancy without a reason, plus an
acceptance criterion that only existed to keep two fields in sync for no benefit. **Resolved**: `value`
has no contractual relationship to `available` (Layer 1 §3) — its content is undefined, not
necessarily `None`, when `available=False`; only `confidence`'s `None`-pairing with `available` stays
a real, enforced invariant, for the type-safety reason that doesn't apply to `value`.

**3. A single symmetric `stability: Window` cannot express "instant on, debounced off" — found from a
concrete product scenario, not abstractly.** Developer: a presence-triggered light must turn on
instantly, never after a dwell delay (the room would sit dark for no reason), while the same fact
should often *not* revert on a brief motion gap (avoid flicker). A single `Window` would either delay
the "on" transition (recreating exactly the dark-room problem) or drop debounce on "off" entirely — and
this asymmetry is already real, working code today (`on_dwell_s=0`/`off_dwell_s=120s` for room
occupancy), so losing it would be a regression, not a simplification. **Resolved**: added
`Stability(to_true: Window | None, to_false: Window | None)` for strategies with boolean polarity
(`BooleanSetStrategy`, `WeightedQuorumStrategy` used with a threshold); `FusionRule.stability: Window |
Stability | None` — plain `Window` still covers non-boolean strategies (`FormulaStrategy`) with
symmetric dwell. Not generalized further (e.g. per-transition dwell across N-valued bucket labels) —
no concrete need for that exists, same "add complexity only when a real case demands it" discipline as
`FusionStrategy`'s own five members. This also forced specifying the actual debounce **mechanism**
(§5.2), never previously written down: a `FusionRule` tracks an ephemeral, in-memory, per-instance
pending-transition (`pending_value`, `pending_since`), not persisted (no restart-safety reason exists
for it, matching Layer 0's general "starts clean" default) — committing only once the applicable
window has elapsed, checked live per Layer 0's own elapsed-time discipline, discarded entirely if the
candidate reverts before then. Two Layer 0 consistency fixes made in passing while writing this: every
`Window`-typed field in Layer 2 now explicitly accepts a `LearnedWindow` substitute (Layer 0 §3.2's
existing general rule, previously unhonored in Layer 2's own type annotations), and §7's claim that
`stability` was "a plain `Window`, no Layer-2-specific timing concept" was corrected — the
pending-transition tracking mechanism itself *is* new here, `Window`/`Stability` are only the
comparison values it's built from.

---

## Performance/latency review of Layers 0-2, and `FusionRule` chaining (2026-09-04)

Developer asked directly whether the architecture as built so far actually serves Heima's "decide and
act fast" goal — a cross-cutting review, not tied to one layer. Found the foundations already
latency-conscious (event-driven, durable writes batched off the hot path, `Stability`'s default is
zero wait, confidence functions are trivial pure math) but two things worth making explicit rather
than assumed, both resolved this session.

**No blocking-I/O contract stated for Layer 2's own execution points.** Architecture invariant #2
(no blocking I/O on the hot path) was never restated for `Interpretation` decoding, `FusionStrategy`
evaluation, or specifically `RegisteredFormula.compute` — the one place Layer 2 hands control to an
arbitrary core-team `Callable` with nothing in its type signature preventing a slow implementation.
**Resolved**: new §2.2 in `layer2_registries_spec.md`, a normative constraint enforced by code review
at registration time (not runtime-checkable in general).

**`FusionRule` could not consume another `FusionRule`'s output — reconsidered, and reversed, after
working through why the original 2-wave design wasn't actually buying what it seemed to.** Initial
read: bounding `FusionRule` to only ever consume `Sensor` facts caps evaluation at 2 sequential
"waves," good for predictable latency. Reconsidered once the "core-team-authored only" governance
(§2.1) was factored in properly: since the `FusionRule` dependency graph is static and fully known
before any cycle runs, cycle detection and evaluation ordering are a **one-time, registration-time**
cost (a topological sort), not a per-cycle one — so the 2-wave cap wasn't protecting against a real
per-cycle cost, it was giving up real reuse value (e.g. "zone occupancy" needing to re-derive from raw
per-room sensors instead of reusing an already-correct "room occupancy" `FusionRule`, duplicating
weights/threshold/stability at every consumer) for no latency benefit that a registration-time sort
doesn't already provide for free.

**Resolved**: `FusionRule.sensor_ids: tuple[str, ...]` replaced with `inputs: tuple[FactRef, ...]`
(`FactRef` = `fact_type` + `Location`, the same addressing every other consumer in this model already
uses) — a `FusionRule` never needs to know whether an input came from a `Sensor` or another
`FusionRule`. Cycles rejected loudly at registration; evaluation order is the precomputed topological
sort. The one genuine, non-obvious risk found while working through this: `Stability` (§5.2) **stacks**
across chained `FusionRule`s specifically on the debounced side — a tier-2 fusion watching a
tier-1 fusion's already-debounced output waits its own configured window *on top of* tier-1's, so two
independently-reasonable 120s/60s settings compound to 180s end-to-end, invisibly to whoever configures
either tier in isolation. The instant side (`to_true=None`) does not compound the same way, which is
exactly the case the developer's original light-latency concern cared most about — but the debounced
side is still a real correctness risk (e.g. security-arming logic waiting far longer than intended to
treat a zone as clear), not a low-stakes one. Resolved as a documented review discipline for now
(§5.6), not a structural restriction — two stronger options (a stacking-delay diagnostic; restricting
`stability` to only the top-level `FusionRule` in a chain) considered and deliberately left for later,
recorded in §8, not adopted without data on what a chained configuration actually looks like in
practice.

---

## Final critical re-read of Layer 2, round 3 (2026-09-05)

Developer asked for one more adversarial pass over `layer2_registries_spec.md` before starting Layer
3, specifically hunting for problems, duplications, and rough edges rather than confirming the
already-settled design. Seven findings isolated; discussed one by one, in order.

**1. No registration-time uniqueness invariant for `(fact_type, Location)` → producer.** `FactRef`
addressing ("the current `HouseFact` for this `fact_type` at this `Location`") and §5.6's topological
sort (an edge from A to B when A's `produces`/`where` matches one of B's `inputs`) both silently
assume exactly one producer per `(fact_type, Location)` pair — nothing enforced it. **Resolved,
implemented**: new §2.3 — a `Sensor` or `FusionRule` registration that collides with an existing one
on the same `(fact_type, Location)` is rejected loudly at registration, never accepted, same
discipline as §5.6's cycle rejection; §5.6 itself now cross-references §2.3 as what makes its edge
construction well-defined. Two new acceptance criteria added (§9).

**2. `WeightedQuorumStrategy.weights: dict[FactRef, float]` duplicated `FusionRule.inputs: tuple[FactRef,
...]`** — two parallel structures with no stated rule for divergence, and the only one of the five
strategies not relying solely on `FusionRule.inputs` for its membership. **Resolved, implemented**:
`FusionRule.inputs` stays the single source of truth for every strategy, no exception; `weights` is now
documented as a sparse override dict (only entries that need a non-default weight), and a key in
`weights` absent from `inputs` is a registration-time error, same discipline as finding 1. One new
acceptance criterion added (§9).

**3. §3.1 justified "these 4 Interpretations always produce a value" by assuming HA's vocabulary for
those domains is closed — an assumption about an external system, not a property Heima's own code
enforces.** Cross-checked against the real historical sleep-normalizer bug
([[project_sleep_normalizer_bug]]): `boolean_signal()` silently mistreated `"Charging"`/`"Full"` as
"off" instead of failing loudly — proof the actual existing behavior for boolean-style sensors is
already "unrecognized state → catch-all default," not "vocabulary is closed by HA," and that leaving
this implicit already caused one real bug. Developer's own follow-up went further: `BooleanInterpretation`,
`PresenceInterpretation`, and `MediaActivityInterpretation` are not three mechanisms — they are the
same exact-match-lookup mechanism applied to three separately hardcoded vocabularies, one of which
(media) the developer specifically flagged as not wanting hardcoded any longer.

**Resolved, implemented this session**: the three collapse into one `MappingInterpretation(mapping:
dict[str, EvidenceValue], default: EvidenceValue | None = None)`. `default=<value>` is how today's
boolean/presence/media-activity "always available" behavior is now expressed *explicitly*, as a
declared property of the registration, instead of assumed from a hardcoded vocabulary;
`default=None` is how a producer declares "I only speak for these specific states" — the same
mechanism `CalendarInterpretation`'s open-vocabulary "no match" already used, now generalized instead
of being `CalendarInterpretation`'s unique special case. `Interpretation` shrinks from five members to
three, organized by decoding **mechanism** (exact-match lookup / numeric range / fuzzy keyword scan)
rather than by HA domain — and extends for free to any future closed-discrete-vocabulary HA domain
(lock, alarm panel, vacuum, `climate.hvac_action`...) without ever reopening the union for that
pattern again. Applied to `layer2_registries_spec.md` (§4 definition and prose, §3.1's
available/interpretable rule rewritten per-mechanism instead of per-type, §9 acceptance criteria
extended to test both `default` branches distinctly), `v3_sensors_actuators_draft.md`, and
`v3_architecture_recap.md`'s Layer 2 summary. `v3_backlog.md`'s own historical entries referencing the
old three-variant names (the `PresenceInterpretation` grounding pass, 2026-08-31) are left as-is,
append-only.

**4. `Sensor.unit`'s drift-diagnostic had no defined consumer/mechanism** — the field's purpose was
stated but nobody checks it, when, or what happens on a mismatch. **Resolved, implemented**: new §3.2
— checked at the same point an `Interpretation` already reads the entity's raw state (the live unit is
already in hand there, so this costs nothing beyond what decoding needs anyway, §2.2 unaffected); a
mismatch raises a Layer-0-§9-style diagnostic event, never touching `available`/`confidence`/`value`
for that cycle — a stale unit is a configuration problem for a human, not a data-quality judgment on
this reading. One new acceptance criterion added (§9).

**5. Retracted on re-examination — not a real duplication.** The initial pass flagged the "instant-on
light" example and the "core-team-authored only" governance point as each restated three times. Rereading
every occurrence in full context showed this doesn't hold: the "instant-on" narrative (with its
motivating reasoning) appears exactly once (§5.2); the other two mentions are a one-line dataclass
comment and a numeric restatement inside a different worked example (§5.6), not a re-narration.
"Core-team-authored" similarly appears once as the original definition (§2.1) and once to justify a
different point (the formula registry's governance, §5.3); the §5.6 mention is a literal
cross-reference with a section number, not a restatement. No edit made — the original flag was too
hasty, not verified against the actual text before being raised.

**6. No relationship stated between `FusionRule.where` (destination) and its `inputs`' own locations
(sources) — and the naive fix ("destination must be coarser than or equal to every source") turns out
to be actively wrong for one strategy, not just unstated.** Concrete counter-example found while
discussing this: a `PrecedenceStrategy` computing "effective bedroom temperature," preferring a
dedicated room TRV but falling back to a whole-house outdoor reading
(`where=Location(scope="casa")`) — here the derived fact's destination (`room="bedroom"`) is *finer*
than one of its sources (`casa`), the opposite of "coarser or equal." A single universal rule would
have rejected this legitimate case. **Resolved, implemented** by separating **source location**
(`FactRef.where`, per input) from **destination location** (`FusionRule.where`) and working out the
relationship per strategy, new §5.7: `DirectStrategy` (exactly one input, a registration-time arity
check that was previously only implied in prose — destination must equal that one input's location,
and the strategy's own comment claiming it could relabel "a new fact_type/**Location**" was corrected,
since no real use case for that surfaced); `BooleanSetStrategy`/`WeightedQuorumStrategy`/`FormulaStrategy`
(destination must equal or be coarser than the join of every source, checked via `Zone.room_ids`
membership — these three combine every input simultaneously into one value, so the result can never
be about something finer than any one source); `PrecedenceStrategy` (deliberately exempt — the
bedroom/casa fallback is exactly its intended use, not an edge case to guard against). Four new
acceptance criteria added (§9).

**7. Layer 1 §4.2's escape hatch for a raw `Sensor` reporting `confidence != 1.0` "with a concrete
evidentiary reason" turned out to already be quoted in Layer 2 §3.1 — the actual gap was that Layer 2
gave `Sensor` no mechanism to ever exercise it, so in practice every available `Sensor` fact reported
exactly `confidence=1.0`, making the field's `float` type misleading for this entire producer class:
a value that can only ever be `1.0` or `None` is a boolean wearing a float's clothes.** Developer
pushed back hard on the first proposed fix (formally closing the escape hatch, `confidence=1.0`
always) with the sharper question underneath: what would a genuinely continuous `Sensor` confidence
even mean? A follow-up question then surfaced real confusion worth resolving explicitly: if the value
is supposedly fixed (a device property), why does it become `None` on `available=False` — doesn't
that contradict treating it as an invariant?

**Resolved.** Two separate questions were being asked in one field: `Sensor.reliability` (new,
§3) is a fixed, per-device, registration-time property — a device's own known trustworthiness when it
*has* something to report (e.g. a WiFi-based presence sensor's known false-negative rate,
`reliability=0.85`), never recomputed, never guessed. `Provenance.confidence`, unchanged in shape, is
a property of one specific `HouseFact` — one cycle's specific claim of trust in one specific
observation. `confidence=None` when `available=False` is not a contradiction of `reliability` being
fixed: it does not mean "the device's reliability became unknown," it means there is no observation
this cycle for a trust-value to describe at all — the same "no meaningful confidence for a value that
was never produced" principle Layer 1 §4.2 already applies to every other producer, now correctly
separated from the device-level constant it was being confused with. Mechanically: `available=True`
→ `confidence = Sensor.reliability` (default `1.0`, unchanged behavior for the common case);
`available=False` → `confidence = None` unconditionally, `reliability` simply not consulted. Applied
to `layer2_registries_spec.md` (`Sensor.reliability` field in §3, §3.1's "Otherwise" branch, §7's
Layer 1 relationship note, one new acceptance criterion in §9).

---

## Full cross-layer coherence pass after the Layer 2 round-3 fixes (2026-09-06)

Developer asked for a fresh, full re-read of Layer 0/1/2 together (not just Layer 2 in isolation)
after the round-3 fixes above, explicitly from a senior-service-designer angle: is everything still
coherent, correct, and complete across layers, not just within one document. This surfaced a serious
pre-existing gap (present since Layer 2 was first promoted, not introduced by round 3) and a factual
error in an earlier decision, both corrected.

**`implicit_hold_restore_class` was a decision already made (2026-09-02, Manual Hold restoration) and
written into `layer0_runtime_spec.md` §6.3 as living on "Layer 2's `Sensor`/`Actuator` registry
entries" — but was never actually added to either dataclass when `layer2_registries_spec.md` was
promoted.** Layer 0's entire conditional-restoration mechanism (§6.3) depends on reading this field at
hold-creation time; without it in Layer 2, that mechanism references a contract that doesn't exist.
Found by reading Layer 0 and Layer 2 side by side in full, not by reviewing either in isolation —
exactly the kind of gap a single-layer review misses. Discussed and narrowed to `Actuator` only (not
both, as Layer 0's prose loosely suggested): an implicit hold is defined (Layer 0 §6) as an
*actuator* Heima manages diverging from a commanded state — the eligibility lookup is always on the
commanded entity's `Actuator` record, and a duplicate `Sensor`-side copy would have no call site that
would ever read it, the same "don't keep unexercised flexibility" reasoning already applied to
`Sensor.confidence` above.

**While verifying `Actuator` is generic enough to cover this (developer's question: does it handle
smart bulbs/plugs, any "does something" device?), a second, independent problem surfaced: a
2026-09-01 backlog entry ("Heating needs the same per-room precedence treatment as Lighting") claimed
"`VALID_ACTUATOR_ROLES` already has `hvac_unit` (`actuators.py:50`)" as grounds for "no actuator-role
gap."** Checked against the actual repository, not assumed: no such constant exists anywhere in the
codebase, and today's real `Actuator` class (`custom_components/heima/actuators.py`) has no role
concept at all — `actuator_id`/`entity_id`/`room_id`/`opening_id`/`display_name` only. The citation was
false. The addendum's *conclusion* (no registry redesign needed for per-room TRVs) still holds, but
for a different, correct reason: v2's own actual spec
(`docs/specs/core/actuator_registry_spec.md:205`) already states the registry accepts "one HA entity
(any domain — `cover.*`, `fan.*`, `climate.*`, `switch.*`, …)" — genericity was always structural
(`entity_id: str`, no domain constraint), never dependent on a role list that turns out never to have
existed.

**`actuator_role` itself — new in v3, no v2 precedent — was found under-specified in a way that
mattered once the false citation was cleared: was it meant to be a closed, validated vocabulary (as
"a valid `actuator_role`" in §9's acceptance criteria implied) or an open convention?** Developer's
objection, decisive: Home Assistant has no closed vocabulary of device domains/classes itself — it
adds new ones continuously — so closing `actuator_role` here would mean a new HA device class cannot
be represented until a core-team code release, exactly the risk a naming convention should avoid.
Layer 1 §3 already establishes the identical precedent for `fact_type`, with the identical reasoning
("a closed vocabulary here would fight" routine growth) — applied here the same way. **Resolved**:
`actuator_role` stays a plain, open `str`, documented as deliberately so (mirroring `fact_type`'s own
wording), with a `"switch"` example added (a generic on/off outlet, previously missing even as an
example) — never formalized into an enum. §9's acceptance criterion rewritten to check usage (every
light-commanding reaction goes through the registry) rather than membership in a closed set that was
never going to exist. Applied to `layer2_registries_spec.md` §6 and §9.

**Back to the original gap: `implicit_hold_restore_class` added to `Actuator` only** (§6), restoring
the 2026-09-02 decision. `layer0_runtime_spec.md` §6.3 corrected to say "Layer 2's `Actuator` registry
entries" (was "Sensor`/`Actuator`") — a wording imprecision, not a second decision reopened. Layer 2
§7 updated to state the one point of contact in the Layer-0-depends-on-nothing-above-it direction
(Layer 0 §6.3's restoration mechanism is *defined in terms of* this field, but Layer 0's own runtime
never queries the registry live — only the domain/reaction logic that creates the hold reads it,
once, freezing the result into evidence before Layer 0 ever sees it). One new acceptance criterion
added (§9), verifying the field reaches Layer 0's restoration algorithm end-to-end through a
simulated restart.

**Moderate finding also resolved**: `v3_architecture_recap.md`'s Layer 2 section had drifted from
`layer2_registries_spec.md` on two points introduced by round-3's own fixes — "how N `Sensor` facts
become one derived `HouseFact`" (no longer true once `FusionRule` chaining was added, 2026-09-04) and
"direct passthrough (relabel one fact under a new `fact_type`/`Location`, unchanged)" (now false per
§5.7's `DirectStrategy`-never-changes-`Location` fix). Both corrected, plus the `Actuator` bullet
updated for `implicit_hold_restore_class` and the open `actuator_role` convention.

**Minor finding resolved**: §5.7's join rule was stated as a simple membership check ("every source is
a member of the destination's room set"), correct only when every source is itself `room`-scoped.
Generalized to a coverage check (every room covered by a source, including a `zone`- or
`rooms`-scoped one, must be covered by the destination) so the rule is correct for chained
`FusionRule`s whose sources are themselves coarser than a single room.

**Not a problem, no action taken**: `v3_sensors_actuators_draft.md` still shows pre-round-3 shapes
(`sensor_ids`, `weights: dict[str, float]`, "4 strategies") — left as is. `layer2_registries_spec.md`'s
own footer already states the precedence rule for exactly this situation ("where this document and
any of those differ, this document is the current word") — chasing full parity in a document
explicitly kept as historical grounding would be busywork with no coherence payoff, unlike the two
`v3_architecture_recap.md` staleness points above, which are a live summary presented as current.

---

## Multi-agent adversarial audit of Layers 0-2, and its corrections (2026-09-06/07)

Developer's demand after the round-3 fixes above: a full, skeptical, senior-service-designer re-read
of all three layers together, on the explicit worry that a foundational layer written wrong makes the
whole architecture unsound "by design." Four adversarial review passes were run in parallel (one per
layer plus one cross-layer pass), each instructed to hunt for genuine logical/type defects, not style.
Findings were spot-verified against the actual document text (not taken on faith) before being
reported. Real, confirmed defects found: 7 structural/cross-layer issues, ~9 narrower but real issues,
~10 minor hygiene issues — a materially higher defect count than any single-layer review this session
had produced, confirming the developer's instinct that repeated local edits without a periodic global
re-check accumulate real drift. Corrections below, in the order worked through.

**`WeightedQuorumStrategy`'s confidence formula (§5.4) was self-referential** — the "threshold not
reached" branch defined `winning_weight = total_weight_considered - winning_weight`, solvable only to
a constant (`total/2`) regardless of the actual vote distribution, not implementable as written.
Concrete counterexample worked through with the developer: 3 unit-weight inputs, threshold=3
(unanimity); `weight_for=0` (unanimous rejection) should yield near-total confidence in `False`,
`weight_for=2` (a near-miss) should yield much less — the broken formula couldn't distinguish these
correctly. Before fixing, the developer pushed back on my first proposed replacement (`weight_for`
itself, unmodified, for both branches) with a sharper question: what does this number actually
*represent*? Resolved by cross-checking against how every *other* row in the §5.4 table already treats
confidence — `DirectStrategy`/`PrecedenceStrategy` inherit confidence in the *specific value actually
reported*; `BooleanSetStrategy`'s four De Morgan branches always compute confidence in whichever
outcome (`True` or `False`) is being reported, never an outcome-independent raw signal strength. Given
`Provenance.confidence` is itself defined (Layer 1 §4) as "how much to trust this specific reported
fact," `WeightedQuorumStrategy` must follow the identical rule. **Resolved**: `winning_weight =
weight_for` when `weight_for >= threshold` (confidence in the reported `True`); `winning_weight =
total_weight_considered - weight_for` when it isn't (confidence in the reported `False` — the weight
that did *not* back the "for" side, never `weight_for` itself, which would invert the intended trend:
a near-miss would read as *more* confident than a unanimous rejection). One acceptance criterion (§9)
extended to explicitly test both branches, including the near-miss-vs-unanimous-rejection distinction
by name.

**`categorical_confidence`/`continuous_confidence` (Layer 1 §4.2) had no precondition preventing an
out-of-range result** — `categorical_confidence(6, 5) = 1.2`, `continuous_confidence(dispersion=-2,
scale=1, floor=0) = 3.0`, both violating `Provenance.confidence`'s own documented `0.0`-`1.0` contract
from inside the very functions this architecture centralizes confidence in specifically to prevent
this class of mistake. **Resolved**: explicit preconditions added (`0 <= count_best_outcome <=
total_observations`; `dispersion >= 0`, `0 <= floor <= 1`).

**Self-caught mistake while touching the same code block, corrected before it could compound**: my
first pass also "fixed" a genuine but separate finding — `combined_confidence`'s docstring claimed
"not a passthrough (more than one source feeds it)" while its actual precondition only required a
non-empty sequence (length >= 1), a real mismatch. I tightened the precondition to `len >= 2` — but
before finishing, checked this against Layer 2's actual call sites (the discipline the developer had
just demanded) and found it would have broken a legitimate, expected case: `BooleanSetStrategy` with
`min_available=1` (its own default) can validly have exactly one available/confirming/dissenting
source in a given cycle, and calls `combined_confidence` with that single-element list — a real
runtime occurrence, not a caller bug. Reverted the precondition change; fixed the actual mismatch by
softening the docstring instead, clarifying that a length-1 call is a legitimate degenerate case
(`min`/`max` of a singleton is correctly that source's own confidence), not an error the function
needs to guard against. This is the exact "local fix without a global coherence check" pattern the
developer had just called out — caught this time before it reached the document, not after.

**Layer 1 §10's acceptance criterion directly contradicted Layer 1 §4.2 in the same document.** §4.2
explicitly permits a producer to "note its own method in `evidence`... for diagnostic purposes"; §10
banned recording "which formula/path produced a given `confidence` value" in *any* field whatsoever —
literally the same thing, one permitted, one forbidden. **Resolved**: §10 rewritten to match §4.2's
actual rule — no *dedicated schema field* for this outside `evidence`, and nothing downstream ever
treats such a note as load-bearing, rather than a blanket ban that would fail a spec-compliant
implementation.

**`Provenance.evidence.trigger_state` (Layer 0 §6.3) was typed `dict[str, Any]`, while Layer 1 §4.3
cites this exact field, by name, as its own compliant example of `evidence`'s `EvidenceValue` shape
constraint** ("one level of nested attributes, not deeper"). The type annotation didn't actually say
what Layer 1 claimed it was an example of. **Resolved**: retyped `dict[str, EvidenceValue]`.

**Layer 0 §6.3's restoration algorithm had two further, related gaps, both found and fixed in the same
pass**: (a) steps referenced `recorded_expiry` as though persisted, but the checkpoint's own field list
(`restore_eligible`/`trigger_entity_id`/`trigger_state`) never included an expiry — added
`Provenance.evidence.expiry: datetime`, now carried through the checkpoint and referenced correctly in
the algorithm; (b) nothing said what the algorithm should do if `evidence` had been wiped to `{}` by
Layer 1 §4.3's fail-soft policy — added an explicit first step: if any of the four expected keys is
missing, discard, same conservative outcome as failing eligibility, never undefined behavior on a
safety-relevant decision. §12's acceptance criterion updated from "four checks" to "five checks," with
the fail-soft interaction named explicitly as its own required test case.

**Self-caught slip while renumbering**: my first draft of the new step 1 said "same step as
`restore_eligible=false`" when it is actually a distinct, earlier step (step 1 vs. step 3) — caught on
my own re-read before reporting this batch done, corrected to "same conservative outcome... checked
earlier as its own step." Consistent with the developer's standing instruction this round: re-read
before declaring closed, don't trust the first pass.

All 5 objectively-broken Tier-1 findings from the multi-agent audit are now fixed and cross-checked.
Still open, pending explicit design decisions (not bugs with one obvious fix): `CalendarWindow`'s
missing producer mechanism, and whether `WeightedQuorumStrategy` should also fold each input's own
`confidence`/`reliability` into its result (current answer: no, documented as an intentional
distinction from `BooleanSetStrategy`, not yet written into the spec text). Tier 2 (~9 items) and Tier
3 (~10 items) from the audit remain entirely undiscussed.

---

## `CalendarWindow`'s missing producer, resolved (2026-09-08)

Layer 0 §3.4 said `CalendarWindow` was "classified by a calendar interpretation (Layer 2)" and evaluated
pre-DAG — but Layer 2's actual `CalendarInterpretation` produces a category string on the ordinary
hot-cycle path from a `Sensor`'s current state, not an absolute `start`/`end` interval, and Layer 0 has
no mechanism of its own to run keyword matching without depending on Layer 2. First checked whether
`CalendarWindow` was even needed given `Sensor`+`CalendarInterpretation` already answers "what category
is active right now" every cycle — concluded it's genuinely not redundant: `CalendarWindow` is the only
way to answer forward-looking questions ("is a vacation starting in 3 days") or get an event's actual
end time, neither of which a current-state-only `Sensor` read can provide.

**Resolved** by splitting extraction from classification instead of forcing them together: Layer 0
produces `CalendarWindow(start, end, summary, source_entity)` by mechanically reading a `calendar.*`
entity's raw event list via HA's calendar API, pre-DAG — `summary` is the event's raw, unclassified
text (renamed from `category`, which wrongly implied Layer 0 already classified it). Classifying that
text into a named category ("vacation", "day_off"...) stays exactly where it already lived —
`CalendarInterpretation`'s keyword-matching (Layer 2 §4) — now explicitly documented as a reusable pure
function a Layer 4/5 consumer applies to a `CalendarWindow`'s raw `summary`, against the same
`keywords`/`priority_order` already configured for whichever `Sensor` is registered on the same
`source_entity` — never a second, separately-maintained keyword configuration. This preserves "Layer 0
depends on nothing above it" exactly, at the cost of `CalendarWindow` instances needing a classification
step at the point of consumption rather than arriving pre-classified. Applied to `layer0_runtime_spec.md`
(§2 scope bullet, §3.4 full rewrite, one new §12 acceptance criterion) and `layer2_registries_spec.md`
(`CalendarInterpretation`'s comment, §4).

---

## `WeightedQuorumStrategy`/`BooleanSetStrategy` overlap, resolved; temporal recursion added (2026-09-08)

**Why `WeightedQuorumStrategy` doesn't fold in each input's own reliability, worked through properly.**
Developer wasn't satisfied with the first-pass answer ("they answer different questions") and pushed
for the real reason. Resolved with a concrete counterexample: a group-presence quorum, threshold=1.5,
resident (weight=1.0) and guest (weight=1.0, but a sensor known to be `reliability=0.3`), both report
present. Folding reliability into the vote weight (`effective_weight = weight × reliability`) computes
`weight_for = 1.0 + 0.3 = 1.3 < 1.5` — the low-reliability vote **flips the outcome** from "present" to
"not present," even though two independent readings agreed. The real point: `weight` and `reliability`
are *both* static, core-team-declared properties of the same input — `weight` is already the lever for
"how much should this input count," so a producer who wants to distrust a specific input can already
say so directly by lowering its `weight`. A second channel for the identical intent adds no new
expressive power, only a redundant, ambiguous combination rule. `UnanimityStrategy` (below) is the
mirror case: it has *no* weight field, so `combined_confidence` over each input's own confidence is
its only available lever — this asymmetry is principled, not an oversight. Documented in
`layer2_registries_spec.md` §5.1 (WeightedQuorumStrategy's own comment), not a mechanism change.

**`BooleanSetStrategy` renamed to `UnanimityStrategy`, `mode="any"` removed as a pure redundancy.**
Prompted by developer's own suggestion to unify vote-counting under one interface — worked through
numerically (a 3-sensor "all doors closed to arm" security check) rather than assumed:
- `mode="any"` unifies cleanly and for free: `WeightedQuorumStrategy(weight=1 for every input,
  threshold=1.0)` produces the identical outcome in every availability scenario, since "at least one"
  never needs its bar to scale with population size.
- `mode="all"` does **not** unify the same way: a fixed `threshold` cannot express "100% of whoever is
  currently available" — the bar must track `total_weight_considered`, which shrinks as inputs go
  `available=False` (§5.5). Worked concretely: 3 unit-weight sensors, `threshold=3.0` fixed; if one
  goes offline and the remaining two both agree, `weight_for=2 < threshold=3.0` — the strategy reports
  "not reached" even though every sensor that could respond did agree, a real behavioral regression
  from today's `mode="all"`, not merely a different confidence number.
- An early framing mistake was caught and corrected mid-discussion: the differing *confidence values*
  between the two formulations (e.g. 0.9 via `combined_confidence`'s min vs. 1.0 via
  `categorical_confidence`) is not itself a cost — Layer 1 §4.2 already establishes no consumer ever
  needs to compare which formula produced a confidence value. Only the "all" case's *outcome* breaking
  is the real, disqualifying argument; a tangential side-thread comparing confidence values for `any`
  was a distraction the developer had to explicitly redirect away from.

**Resolved**: kept `BooleanSetStrategy`, renamed `UnanimityStrategy`, `mode` field dropped entirely
(only "all" semantics remain) — the one case with a genuine technical requirement a linear weighted
threshold cannot express. `"any"` documented as `WeightedQuorumStrategy(weight=1, threshold=1.0)` in
that strategy's own comment. `FusionStrategy` stays a 5-member union (extending `threshold` to support
a relative/dynamic bar and eliminating `UnanimityStrategy` entirely — rejected as speculative
complexity with no concrete forcing case, the same discipline already applied elsewhere in this
document, e.g. `FusionStrategy`'s and `Interpretation`'s own growth history). Applied across
`layer2_registries_spec.md` §5.1, §5.4 (De Morgan reduced from four branches to two), §5.5, §5.6
(worked example updated), §5.7, §8, §9, and `v3_architecture_recap.md`'s Layer 2 summary.

**Temporal recursion — `FactRef.previous_cycle` — added after developer pushed back hard on filing a
Bayesian-filter question as "not yet decided."** Asked whether `WeightedQuorumStrategy` could express a
Bayesian filter; answer was no (linear weighted-vote math cannot correctly express multiplicative
likelihood-ratio updating) — a single-cycle Bayesian combination fits `FormulaStrategy` cleanly today,
but a genuinely *recursive* filter (using its own last posterior as this cycle's prior) could not:
`RegisteredFormula.compute` is pure/stateless (§2.2), and §5.6's cycle-detection rule rejects any
`FusionRule` depending on itself, undifferentiated by *when* the dependency is from. Developer's
explicit challenge: don't file this away, find a structural fix that doesn't require revisiting the
layers later. Resolved by generalizing a distinction the architecture already has rather than
inventing one: Layer 0 §10 already lets a domain read `CanonicalState` — the *previous* cycle's
resolved output — never another domain's *current*-cycle output, specifically to keep the DAG acyclic.
The same distinction, applied to `FactRef`, resolves the Bayesian case directly: a previous-cycle
value is already fixed and immutable before the current cycle starts, so referencing it — including a
`FusionRule` referencing its own `produces`/`where` — can never create an ordering conflict, unlike a
current-cycle self-reference (a genuine cycle, correctly still rejected). `Stability`'s own
pending-transition mechanism (§5.2) was already doing something conceptually similar ("compare to my
last committed value") as a hidden, strategy-specific special case; this generalizes the same idea into
an explicit, reusable primitive any `RegisteredFormula.compute` can use, receiving its own "memory" as
one more ordinary `HouseFact` input rather than a hidden side channel — preserving purity, and (an
unplanned bonus) surviving restarts for free via Persistence's durable tier, unlike `Stability`'s
deliberately ephemeral state. Enables not just Bayesian filters but any recursive computation
(exponential moving averages, accumulators) through the existing, closed `FormulaStrategy` mechanism —
no sixth strategy. Added `layer2_registries_spec.md` new §5.8, `FactRef.previous_cycle: bool = False`
in §5, cross-references in §5.6/§5.7/§7/§8, three new acceptance criteria in §9, and a summary in
`v3_architecture_recap.md`.

**Self-caught errors during this batch, both fixed before reporting done** (per the developer's
standing instruction to re-read before declaring closed): a garbled, incomplete sentence left in
`WeightedQuorumStrategy`'s own comment mid-edit ("This differs from `BooleanSetStrategy`... see
`combined_confidence` below deliberately"); and a cross-reference in `FactRef`'s own comment pointing
to "§5.6 for the full mechanism" when the full mechanism is actually in the newly-added §5.8. Both
caught on my own re-read of the diff, not by the developer.

---

## Tier 2 audit items, worked through (2026-09-08 continued)

**Layer 0's reliance on `Provenance.evidence` without restating it — re-examined, found not to be a
real gap.** Layer 0 already discloses the identical "consumes, doesn't own" relationship for
`HouseFact`/`Location` (§2) and, explicitly, for `Provenance` itself (§5: "a `HouseFact`'s `how` field,
`Provenance`, owned by Layer 1"). What Layer 0 defines inside `evidence` (`restore_eligible`,
`trigger_entity_id`, `trigger_state`, `expiry`) is Layer-0-specific *content* placed into a
Layer-1-owned generic *container* — the same pattern Layer 0 already uses for `ManualHoldValue` as
`HouseFact.value` (§6.1), and the same pattern every producer in every layer uses. The one real
violation of Layer 1's `evidence` contract (`trigger_state` typed `dict[str, Any]`) was already found
and fixed in an earlier round. No further action — retracted, not a genuine open item.

**`layer2_registries_spec.md`'s header omitted `Zone` from its declared Layer 1 dependencies**, despite
§5.7 depending on `Zone.room_ids` for the join/coverage check. Resolved: added `Zone` to the header's
dependency list.

**Layer 1 §8 omitting Manual Hold Manager — re-examined the same way, same conclusion.** §8's four
existing bullets are all *structural* dependencies (Layer 1's own type definitions require them —
`Provenance.source: FactSource` must exist, `HouseFact.when` follows Layer 0's UTC convention, etc.).
`ManualHoldValue`/`manual_hold.<domain>` are cited elsewhere only as *illustrative examples* (one
compliant-dataclass example among possible others; one naming-convention example among six) — Layer
1's own correctness doesn't require either to exist. By the same logic, Recovery/Checkpoint (cited for
its "§9-style" diagnostic-event convention) isn't in §8 either, correctly. No real gap — retracted.

**Six objectively-broken Tier-2 items fixed, no design decision needed for any of them:**
- `Location`'s "`room_ids` needs at least 2 entries when `scope='rooms'`" lived only in a field
  comment, not the normative construction rule or §10's acceptance criteria (asymmetric vs. `Zone`'s
  parallel, enforced "at least 1" floor) — added to both.
- `ManualHoldValue.held_state` was typed `dict[str, Any]` while cited by Layer 1 §3 as its own
  compliant `EvidenceValue`-shaped example — retyped `dict[str, EvidenceValue]` in both documents.
- `external.<slot>` (a `fact_type` naming example) was never explained — added a one-clause gloss
  pointing to Layer 2's own external-adapter example (OWM, Protezione Civile).
- "an enum value" as a `HouseFact.value` example was ambiguous against `EvidenceValue`'s closed set
  (an `Enum` member itself doesn't qualify) — clarified it means the member's own primitive `.value`.
- No acceptance criterion tested rejecting a `DirectStrategy` with correct arity (one input) but a
  `where` that doesn't match that input's location — a distinct failure mode from wrong arity, never
  separately stated as enforced. Added both the explicit enforcement statement (§5.7) and the
  acceptance criterion (§9).
- §2.2 names three hot-path execution points needing no-blocking-I/O review (`Interpretation`
  decoding, `FusionStrategy` combination, `RegisteredFormula.compute`), but §9's checklist criterion
  only covered the third — extended to cover all three explicitly.

Full multi-agent audit (2026-09-06/07) previously believed closed except Tier 3 — **found to be a
false close**: re-verifying the original four agent reports against what had actually been discussed
turned up 9 findings, several rated HIGH by the originating agent, that never made it into any
discussion round at all — dropped during my own synthesis, not flagged as retracted, just silently
missing. Corrected the record and started working through them for real, gravest first.

---

## Layer 0 Persistence: write-on-change vs. retention, worked through properly (2026-09-08)

**Finding**: `HouseFact`/`Provenance`, §4's "query reconstructed at read time" promise silently breaks
once write-on-change (§4.2) is factored in — a fact stable for a long time has exactly one durable
record, dated when it first became true; a naive range scan for `[t1, t2]` finds nothing whenever that
record predates `t1`, even though the fact was true throughout the window.

Developer pushed back twice on the first two proposed fixes, each time surfacing a sharper version of
the problem:
1. First fix proposed: state the "as-of + range" reconstruction algorithm explicitly (find the latest
   record at-or-before `t1`, plus every record inside `(t1, t2]`). Developer asked whether a hybrid
   with periodic re-writes (motivated by reaction-latency concerns) made more sense.
2. Checked the actual text before answering: **batching** (§4.2, all writes deferred to end-of-cycle)
   is what protects reaction latency, not write-on-change — even a write-every-cycle policy would
   still be off the hot path. Write-on-change is a separate optimization for disk volume. This meant
   a latency-motivated hybrid wasn't solving the problem it was proposed for.
3. Developer's sharper follow-up: even with correct as-of reconstruction, what happens when the
   at-or-before-`t1` record itself has aged past the `fact_type`'s own retention window and been
   evicted? This exposed something worse than a query bug: **retention could delete the only evidence
   a still-true fact exists at all**, not just make one query return the wrong answer for one range.
4. Resolved: retention must never evict the single most recent record per WHAT/WHERE/HOW key,
   regardless of age — only records superseded by a newer one for the same key are eligible for
   time-based or count-based eviction.
5. Developer's cost objection to (4): doesn't this require a group-by-and-sort over all stored records
   every time pruning runs, more expensive than a slow daily rewrite? Re-derived properly rather than
   asserted: write-on-change's own comparison ("value differs from the last stored value for this
   key," every cycle, for every fact) **already requires** Persistence to maintain a fast,
   incrementally-updated per-key "latest record" lookup — retention's exemption is then just a lookup
   against a structure that has to exist anyway, not a fresh computation, and costs nothing beyond
   what write-on-change already pays. A periodic full rewrite, by contrast, is a real recurring cost,
   forever, for every stable fact in the house.

**Resolved and applied to `layer0_runtime_spec.md`**: §4 states the reconstruction algorithm
explicitly; §4.2 explicitly separates batching (latency) from write-on-change (volume), and names the
latest-value index as a required, explicit structure (not merely implied); §4.3 states the
never-evict-the-latest-record exemption and why it doesn't undermine the count ceiling's own purpose
(a flapping sensor's *superseded* records stay evictable, only its single current record per key is
protected). Two new acceptance criteria added (§12).

---

## `resident_response`'s missing boundary check for the explicit-hold path (2026-09-08)

§5.1's non-forgeability list gave `kind="resident_response"` exactly one boundary condition
("assignable only after matching an active runtime confirmation request") — but the enum's own
comment (§5) says this `kind` covers *two* cases: an explicit manual hold (§6) and a runtime
confirmation response. An explicit hold has no "active request" to match at all, so the stated
boundary simply doesn't apply to it — nothing in the document said what *does* gate this kind for that
case, meaning nothing prevented internal code from constructing
`FactSource(kind="resident_response", actor_type="resident")` for a hold that was never actually
triggered by a resident.

**Resolved**: the real boundary for the explicit-hold case, derived from §6.2's own description
("re-read fresh from that entity's current state every cycle, the same way any other `Sensor`-backed
fact is") — `kind="resident_response"` is assignable there only when constructed from the dedicated
helper/control entity's own `Sensor`-backed state (already trust-checked at Layer 2 §3), never
asserted directly with no such entity read behind it. Stated as its own bullet in §5.1, alongside the
existing confirmation-response one — two independent boundary checks for two cases that don't reduce
to each other, not one rule covering both. The enum's own comment (§5) corrected to point to §5.1
instead of restating (and getting wrong) a single-condition summary. One acceptance criterion (§12)
added, testing both boundaries independently — also closes a separate, previously-unaddressed minor
finding (the existing non-forgeability criterion only checked that fields were carried, never that
forgery attempts are actually rejected).

---

## `LearnedWindow.seed` not clamped to its own `min_seconds`/`max_seconds` (2026-09-08)

§3.2 stated the clamp as an unconditional guarantee ("never allowed to drift below/above it... a Layer
0 guarantee precisely so every call site doesn't have to remember to add its own floor and ceiling"),
citing real flicker/stuck-actuator risk — but nothing constrained `seed` itself against the clamp at
construction time, only calibration's *output*. Since every dwell check runs against `seed` directly
before the first calibration ever completes, an out-of-range seed would defeat the guarantee during
exactly the window (warm-up, no real data yet) where it matters most.

**Resolved**: added an explicit construction-time invariant, `min_seconds <= seed.seconds <=
max_seconds`, validated procedurally the same way `Location`'s construction rule already is. One
acceptance criterion added (§12), testing both an under-range and an over-range seed independently
from calibration's own clamping test.

---

## Short-term buffer horizon vs. `Window`/`LearnedWindow.max_seconds` (2026-09-08)

A dwell check ("has fact X been true for at least `seconds`, continuously") or correlation check
("did Y occur within `seconds` after X") needs the short-term in-memory buffer to actually hold every
change within that `seconds`/`max_seconds` — not just the current value (the separate latest-value
index, §4.2, addresses a different question). Nothing tied the buffer's own bounded horizon to how
large a `seconds` a consumer might configure; a check requiring more history than the buffer retains
can never be satisfied, correctly or not — a silent, permanent false negative.

Developer's directive: reuse §4.3's retention-floor declaration pattern rather than invent a second
mechanism (a hard ceiling on `Window.seconds`, or a disk fallback that would violate the already-stated
"never wait on a disk read" hot-path guarantee, were both considered and dropped for exactly this
reason). **Resolved**: whichever subsystem registers a `Window`-/`LearnedWindow`-based dwell/
correlation check declares its own `seconds`/`max_seconds` requirement against Persistence at
registration time; the buffer's effective horizon is the larger of a system-wide default and every
declared requirement — identical mechanism to §4.3's retention floor, applied to the in-memory tier
instead of the durable one. Applied to `layer0_runtime_spec.md` §3.2 (cross-reference) and §4.1 (the
mechanism itself), with the system-wide default listed in §11 alongside the analogous retention
defaults, and one new acceptance criterion in §12.

All four "grave" findings from the multi-agent audit's Layer 0 report are now resolved.

---

## Backlog ordering bug, found and fixed (2026-09-08)

While closing out the four "grave" items above, noticed the `CalendarWindow` entry (chronologically
resolved right after the multi-agent audit corrections, before the `WeightedQuorumStrategy`/
`UnanimityStrategy` work) had ended up physically appended at the true end of this file instead —
after `LearnedWindow.seed`, several sections later than it belongs. Root cause not fully diagnosed
(likely an `old_string` anchor that matched later than intended during editing), but the effect
violates this file's own append-only-in-order discipline. **Resolved**: moved the `CalendarWindow`
section to its correct chronological position, immediately after the multi-agent audit corrections
and before `WeightedQuorumStrategy`/`UnanimityStrategy`. Content unchanged, position only. Flagged to
the developer rather than silently corrected, consistent with this session's standing instruction to
surface — not hide — coherence slips.

---

## `Topology`'s undefined `Opening`/`ResolvedConnection` types, resolved (2026-09-08)

Layer 1 §7 said `Opening`/`ResolvedConnection` "carry forward unchanged in shape from Heima's existing
room-topology model... Layer 1 does not redefine them" — without ever stating what that shape actually
is. Rated HIGH by the originating audit agent, and rightly so: this is a sharper self-containment
violation than the `Room`/`room_id` deferral it was modeled on. `room_id` really is opaque everywhere
Layer 1 uses it (never inspected internally), but `Topology` treats `Opening`/`ResolvedConnection` as
*structured* data — `orientation`, `connection_type`, `access_type` are fields a reader needs to
understand to know what `Topology`'s own worked examples ("does this room have an operable opening to
the outside") actually mean. A reader with only this document could not have constructed a valid
`Topology` instance.

Checked the actual source, not assumed: `custom_components/heima/room_topology.py` defines `Opening`
(`opening_id`, `room_id`, `type`, `orientation`, `entity_id`) and `ResolvedConnection` (wrapping an
admin-authored `Connection` plus `room_a`/`connection_type`). **Resolved**: both restated in full in
Layer 1 §7, matching the real fields unchanged — `ResolvedConnection` flattened to the query-time
shape a Layer 1 consumer actually reads (`room_a`, `room_b`, `opening_id`, `connection_type`,
`access_type`), leaving the admin-authored `Connection` intermediate type (how these get created) to
Layer 8, which already owns admin-authoring concerns elsewhere in this model. `room_id` fields kept as
plain strings, not `Location` — `Topology` is structural graph data addressed by room id throughout
(`exposure_by_room`/`floor_by_room` already were), not fact attribution, so introducing `Location`
here would be a real, unmotivated change, not a restatement. One new acceptance criterion added (§10),
constructing a full `Topology` instance from the document alone with no reference to the real code's
own internal `Connection` type.

---

## Last four minor Layer 0 findings, closed (2026-09-08)

All objective, no design decision needed:

- **§6.1 overgeneralized** "the in-memory table... determines restart behavior for either kind of
  hold" — §6.2 already says an explicit hold never has an entry in that table at all. Narrowed the
  claim to implicit holds specifically, with an explicit note on why explicit holds are exempt.
- **§5.2's closing instruction said the opposite of its own preceding rule**: "pass down an
  *inherited* `correlation_id` at every one of the origin points" — but an origin point is, by this
  same section's own definition, precisely where there's nothing to inherit *from*. Rewritten as the
  two genuinely separate obligations: mint fresh at each origin, then propagate unchanged downstream.
- **The non-forgeability acceptance criterion only checked that `FactSource` fields were present**,
  never that a forgery attempt is actually rejected — broadened to name all three concrete forgery
  scenarios from §5.1 (fabricated `admin_command`, `third_party_plugin` claiming a closed kind,
  `resident_response`'s two boundaries), not just the one already covered incidentally by the
  `resident_response` fix.
- **The `manual_hold.<domain>.restored` fact (§6.3) left `actor_type` unset**, silently defaulting to
  `"heima"`, when §5's own definition of `"system"` ("Heima's own startup/runtime infrastructure") is
  exactly what Recovery producing this fact actually is. Set explicitly.

**The full multi-agent audit (2026-09-06/07) is now closed for real** — all four Layer 0 "grave" items,
the rediscovered Layer 1 `Topology` HIGH finding, both `Livello 2` cross-layer items, all six objective
Tier-2 fixes, and these four minor items. One backlog-ordering bug (`CalendarWindow`'s misplaced entry)
was also found and corrected along the way, flagged rather than silently fixed. Layers 0-2 have not had
this level of adversarial scrutiny applied and resolved at any earlier point in this planning branch.

---

## Second full multi-agent re-audit (2026-09-08) — developer's 99% prediction confirmed

Developer refused to move to Layer 3 after the above, explicitly predicting at least one more grave
defect remained, and asked for a fresh line-by-line re-read of everything given how much editing had
accumulated. A second round of four parallel adversarial agents (one per layer, one cross-layer) was
run, instructed to re-verify even today's own fixes skeptically rather than trust them. Confirmed
correct: this found real, serious defects — including two I introduced myself today while fixing
other things, and one earlier fix that silently reverted. Findings verified against the actual repo
(including cross-checking Layer 1's `Topology` restatement against the real
`custom_components/heima/room_topology.py`) before being written up, not taken on the agents' word.

**Already fixed while verifying (documented in the findings-report turn, not repeated here in full)**:
fabricated `connection_type`/`access_type` example values in Layer 1 §7 that contradicted the real
enums (`CONNECTION_TYPES`/`ACCESS_TYPES`) I had just restated from that same file minutes earlier;
`Provenance.evidence.expiry: datetime` (added by me 2026-09-07) not `EvidenceValue`-shaped, the exact
class of bug I had just fixed for the sibling `trigger_state` field in the same edit, reintroduced for
the new one; Layer 1 §10's confidence-formula acceptance criterion had reverted to contradicting §4.2
again, despite being fixed 2026-09-07 — re-fixed, cause of the reversion not fully diagnosed;
`Actuator`'s "`room_id`/`opening_id` both collapse into `where`" contradicted `opening_id`'s own field
comment and its continued existence as a separate field — only `room_id` actually collapsed.

**`CronEntry` offline-restart semantics — Layer 0 §3.1 vs §8 gave contradictory policies for the same
scenario.** §3.1: a `CronEntry`'s `due` is simply recomputed against current time on restart, "nothing
about the interrupted countdown needs to be recovered" — zero catch-up. §8: "it fires once
immediately, then resumes its normal cadence... not zero, not N" — exactly one catch-up. Resolved by
recognizing the two `RecurrencePattern` variants genuinely warrant different behavior, not a single
rule papering over both: `IntervalRecurrence` (a periodic safety-net re-check) gets §8's one-time
immediate catch-up fire, where promptness after an outage is the whole point; `WeeklyRecurrence` (a
calendar-anchored routine, "every Monday at 07:00") gets §3.1's zero-catch-up recompute, since firing
a calendar-anchored routine at an arbitrary off-schedule restart moment isn't equivalent to running it
on schedule and could be actively wrong depending on what the routine does. Applied to
`layer0_runtime_spec.md` §3.1 (cross-reference added) and §8 (split into the two cases explicitly).

---

## `Topology.floor_by_room`, and the remaining `Topology` fabrications, closed (2026-09-08)

**`floor_by_room` has no counterpart on the real `TopologyGraph`** (floor lives on the Room registry,
read per-room via `room_floor_of()`), and Layer 1 §2 explicitly disclaims Layer 1 owning a room's
floor "as an inventory record." Resolved by distinguishing *owning/defining* from *reading*: `Zone`
and `room_id` already get this treatment throughout the document (opaque references to data Layer 1
doesn't own) — `floor_by_room` gets the same, an explicit note that it's a read-only aggregate view
over the Room registry's own `floor` attribute, not a redefinition of what floor means or where it's
stored. Applied to Layer 1 §7's `Topology` dataclass comment.

**The rest of `Topology`'s fabrications, found by the same audit, fixed in the same pass**:
- `ResolvedConnection.connection_type`/`access_type` example values (`"door"/"open_plan"`,
  `"normal"/"restricted"`) were invented, not checked against the real code — actual values are
  `"indoor"/"outdoor"/"separate"` and `"direct"/"stairs"/"elevator"` (default `"direct"`, not
  `"normal"`). Corrected against `custom_components/heima/room_topology.py`'s real
  `CONNECTION_TYPES`/`ACCESS_TYPES`, not assumed a second time.
- The "does the house have an outdoor opening" worked example queried `exposure_by_room` for the
  literal string `"outside"` — but `exposure_by_room` holds compass *orientations*
  (`"north"`/`"south"`/etc.), never that string; the query could never return `True` for any house.
  Corrected to `any(c.room_b == "outside" for c in connections)`, `room_b`'s actual reserved value.
- The "nothing lost or renamed" claim about `ResolvedConnection` overstated it slightly — the real
  `Connection.connection_id` (admin-side edit/delete identity) has no counterpart in the flattened,
  read-only shape. Acknowledged explicitly rather than left as an unqualified absolute claim.
- Self-caught while editing: a duplicate leftover sentence fragment ("produces it, which is Layer 8's
  concern, not Layer 1's.") survived from the original text after an edit rewrote the sentence around
  it — removed on re-read before reporting done.

All of `Topology`'s content is now either verified against the real implementation or explicitly
marked as a deliberate simplification, not assumed correct by construction.

---

## `WeightedQuorumStrategy` confidence degenerating to 0.0 under reduced availability, closed (2026-09-08)

**Second-audit finding: `WeightedQuorumStrategy` can report `confidence=0.0` on a `False` outcome even
when every currently-available input actually agrees "for."** Concrete counterexample: 5 sensors at
`weight=1`, `threshold=5.0` (calibrated for the full configured population); 2 go `available=False`;
the remaining 3 are unanimous "for," so `weight_for = total_weight_considered = 3`; `3 < 5` so the
strategy still reports `False` (threshold not reached); `winning_weight = total_weight_considered -
weight_for = 0`, `confidence = 0.0`. Read naively this looks like a formula bug — a unanimous "for"
population producing zero confidence in the opposite outcome.

**Considered and rejected: rescaling `threshold` to `total_weight_considered` so it tracks reduced
availability.** This is exactly the semantics `UnanimityStrategy` already provides (§5.1's own comment
on why "all" cannot be expressed as a fixed `WeightedQuorumStrategy` threshold, and symmetrically why
`WeightedQuorumStrategy` exists at all: to offer an *absolute*, admin-configured bar independent of
current population size, e.g. "need at least 5.0 combined trust-weight to arm"). Making `threshold`
relative would silently turn `WeightedQuorumStrategy` into a re-weighted `UnanimityStrategy` and erase
the reason the two strategies coexist — rejected as removing the one feature that justifies this
strategy's existence, not as a neutral formula fix.

**Resolved by naming, not by changing, the formula**: `winning_weight = total_weight_considered -
weight_for` was already arithmetically correct in every case; what was missing was recognizing that
its `False` branch actually covers three distinguishable situations, only one of which is surprising.
Added an explicit three-way breakdown to Layer 2 §5.4, right after the `WeightedQuorumStrategy` table
row: partial dissent (ordinary), unanimous rejection (ordinary, `confidence=1.0`), and unanimous
non-dissent below a fixed threshold (the counterexample above, `confidence=0.0`, now stated as
**intentional**: zero of the considered weight actually contradicts the opposite outcome, so `0.0` is
the honest signal that this `False` is backed by no dissenting evidence at all, purely a threshold
artifact). No new mechanism, no new parameter — the existing `min_available_weight` gate (§5.5)
already exists for exactly this risk, so the practical resolution is an **operational recommendation**,
not a structural one: whoever sets `threshold` close to the strategy's full configured weight should
set `min_available_weight` close to `threshold` too, so the derived fact goes `available=False` before
this sub-case can be emitted at all. Applied to `layer2_registries_spec.md` §5.4.

---

## Full v3 docs reread after Layer 2 `ReadBinding` change (2026-09-08)

Second manual pass across the whole v3 document set after introducing `ReadBinding` into Layer 2:
`docs/specs/v3/layer0_runtime_spec.md`, `docs/specs/v3/layer1_substrate_spec.md`,
`docs/specs/v3/layer2_registries_spec.md`, `v3_architecture_recap.md`, `v3_house_fact_draft.md`,
`v3_sensors_actuators_draft.md`, `v3_domains_draft.md`, `v3_pattern_learner_draft.md`,
`v3_template_matching_draft.md`, and `docs/img/v3_architecture.dot`.

**Document-state finding**: the three promoted specs under `docs/specs/v3/` are now the only documents
close enough to implementation shape to use as a technical-spec base. The older draft files still
carry known-superseded forms (`Sensor.entity_id`, `BooleanSetStrategy`, `Freshness`,
`dict[str, Any]` evidence, older recurrence shapes). They are still useful as reasoning history, but
must not be consumed as current source material without a visible "superseded by promoted spec"
banner or a rewrite.

**Interventions to complete before writing code-level technical specs:**

**Document hygiene interventions:**

1. Add visible supersession banners to `v3_house_fact_draft.md` and `v3_sensors_actuators_draft.md`, or
   delete/rewrite them once Layer 0-2 are approved; they currently contradict the promoted specs in
   ways that would mislead an implementer.
2. Update domain/template/learner drafts only after the Layer 0-2 blocking items above are closed, so
   they reference `ReadBinding`, `FactRef`, `UnanimityStrategy`, and the promoted `HouseFact` shape
   rather than older draft vocabulary.
3. Keep `v3_backlog.md` as decision history, not as a normative source. New unresolved items should be
   mirrored into the relevant promoted spec's "Not yet decided" section when they affect
   implementation.

---

## Persistence `FactIdentityKey`, resolved (2026-09-08)

Closed the first intervention from the full v3 docs reread. The ambiguous phrase "same
WHAT/WHERE/HOW key" in Layer 0 Persistence was unsafe because HOW includes volatile provenance:
`correlation_id`, evidence, source metadata, and actor/source detail can legitimately change without
changing which real-world fact is being tracked. If HOW participated in the current-value key,
write-on-change would create new latest-value slots for ordinary provenance changes and retention
would protect the wrong "latest" records.

**Resolution applied to `docs/specs/v3/layer0_runtime_spec.md` §4.0/§4.2/§4.3/§12**:
`FactIdentityKey = (fact_type, canonical Location)`. `value`, `when`, and `how` are record content,
not identity. This matches Layer 2's one-producer-per-`(fact_type, Location)` invariant: competing raw
sources must be resolved by `FusionRule` before Persistence sees the final fact, never by storing
separate current values for the same fact under different provenance.

This deliberately does **not** resolve the next intervention ("what fields count as changed for
write-on-change"). The key is now stable; the persisted-change tuple still needs its own decision.

---

## Persistence `FactChangeFingerprint`, resolved (2026-09-08)

Closed the second intervention from the full v3 docs reread. Layer 0 §4.2 previously said
write-on-change compared only `value`, which would lose meaningful current-state transitions:
available sensor -> unavailable sensor with stale/unchanged value, same value with lower confidence,
or same value produced by a different stable source path.

**Resolution applied to `docs/specs/v3/layer0_runtime_spec.md` §4.0/§4.2/§12**:
write-on-change compares `FactChangeFingerprint`, not `value` alone. The fingerprint contains
`available`, `confidence`, canonical `value`, and a stable `FactSourceFingerprint`
(`kind`/`source_id`/`source_type`/`actor_type`). It deliberately excludes `when`, `correlation_id`,
and `evidence`, because including them would reintroduce write-every-cycle churn.

Special case made explicit: when `available=False`, Layer 1 already says `HouseFact.value` is
undefined, so Persistence canonicalizes the fingerprint's `value` to `None` regardless of what the
producer left in the field. Repeated unavailability therefore writes once unless availability,
confidence, or stable source changes.

---

## `MappingInterpretation` no-default sentinel, resolved (2026-09-08)

Closed the third intervention from the full v3 docs reread. Layer 2 overloaded
`MappingInterpretation.default=None` to mean "no fallback / unavailable when unmapped", but Layer 1's
`EvidenceValue` explicitly allows `None`. That made a legitimate output value indistinguishable from
the absence of a default.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §3.2/§4/§9 and
`v3_architecture_recap.md` Layer 2 recap**: introduce a typed sentinel:

```python
@dataclass(frozen=True)
class NoDefault:
    pass

NO_DEFAULT = NoDefault()
MappingDefault = EvidenceValue | NoDefault
```

`MappingInterpretation.default = NO_DEFAULT` means an unmapped raw string produces
`available=False`/`confidence=None`. `MappingInterpretation.default=<EvidenceValue>` means the mapping
is total for unmapped raw strings, including the explicit case `default=None`, which now produces
`HouseFact.value = None` with `available=True`.

Config/storage rule: prefer an absent `default` field to represent `NO_DEFAULT`; a present JSON
`null` means the real `None` value, not the sentinel.

---

## Evidence instant serialization, resolved (2026-09-08)

Closed the first intervention from the full v3 docs reread. `EvidenceValue` is deliberately
JSON-compatible, but Layer 0 had declared the manual-hold `Provenance.evidence.expiry` as a Python
`datetime`, making the checkpoint's supposedly portable evidence payload internally inconsistent.

**Resolution applied to `docs/specs/v3/layer1_substrate_spec.md` §4/§10 and
`docs/specs/v3/layer0_runtime_spec.md` §6.3/§12**: `EvidenceInstant` is the semantic `str` subtype
for a canonical timezone-aware UTC ISO-8601 timestamp with six fractional-second digits and `+00:00`.
`expiry` uses that representation, never a raw datetime object. The hold creator normalizes before
writing; restart recovery parses it once and discards any missing, malformed, naive, or non-UTC value
before it can restore a hold.

---

## Boolean vote semantics, resolved (2026-09-08)

Closed the next intervention from the full v3 docs reread. `UnanimityStrategy` said its inputs must
"agree" and `WeightedQuorumStrategy` counted votes "for", but neither term defined a value domain.
Relying on host-language truthiness would have let values such as `1`, `"on"`, or a non-empty object
be silently treated as votes, despite `HouseFact.value` intentionally admitting many non-boolean
`EvidenceValue` forms.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §5.1/§5.4/§5.5/§9 and
`v3_architecture_recap.md` Layer 2 recap**: both strategies are strictly boolean. Exact `True` is a
vote for and exact `False` a vote against; every other available value is a type mismatch. Rather
than coercing it or silently excluding it, the fusion emits `available=False`/`confidence=None` and a
diagnostic for that cycle. The check occurs at evaluation time because generic `FactRef` carries no
static value-schema declaration; this makes an invalid value visible without inventing a broad type
system solely for two boolean strategies.

---

## Formula confidence contract, resolved (2026-09-08)

Closed the next intervention from the full v3 docs reread. `RegisteredFormula.compute` returned
`tuple[Any, float]`, implicitly treating every formula as a continuous measurement with a dispersion.
That contradicted the existing `heating.season_hysteresis` example and gave formulas an `Any` escape
hatch around Layer 1's `EvidenceValue` contract.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §5.1/§5.3/§5.4/§5.8/§9 and
`v3_architecture_recap.md` Layer 2 recap**: `RegisteredFormula` declares one
`FormulaConfidenceMode` and returns the matching structured result. `continuous` supplies a numeric
value plus dispersion and uses `continuous_confidence`; `categorical` supplies an `EvidenceValue` plus
support/total and uses `categorical_confidence`; `inherit_input` supplies an `EvidenceValue` plus the
configured-sequence index of an available input whose confidence it copies. Result/mode mismatches and invalid mode-specific
parameters fail closed for that cycle with a diagnostic. This makes confidence selection mechanical
while keeping `FormulaStrategy` a narrow, core-team-curated extension point rather than a second
general type system.

---

## Numeric and cardinality validation, resolved (2026-09-08)

Closed the next intervention from the full v3 docs reread. The promoted specs named many necessary
preconditions, but most were prose attached to individual types rather than one implementable
registration boundary. That left open whether a malformed bucket chain, an impossible threshold, a
negative weight, or a zero input population should fail on startup, during evaluation, or not at all.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §2.4/§9 and
`docs/specs/v3/layer1_substrate_spec.md` §4.1/§4.2/§10**: all static numeric and cardinality rules are
validated at registration, before the hot path. This covers finite reliability, total/open-ended bucket
ordering, non-empty fusion inputs, min-available/min-input bounds, strictly positive weights,
threshold and availability-weight bounds, and formula scale/floor constraints. Negative weights were
explicitly rejected: inverse evidence must be normalized to a semantically oriented fact before a
quorum, or modeled as a `FormulaStrategy` calculation.

Layer 1's confidence helpers and `Provenance` construction independently validate their numeric
domains and raise `ValueError` on an invalid call, providing a second boundary against coding errors.
Those runtime guards are constant-time checks over the already-present values; they add no I/O or
waiting to the hot path.

---

## Calendar timeline and predictive reads, resolved (2026-09-08)

Closed the next intervention from the full v3 docs reread. The calendar contract said Layer 0 exposed
active/upcoming windows, but did not define timezone normalization, all-day dates, empty versus failed
reads, overlap resolution, or restart behavior. An initial attempt to narrow the binding to active
windows alone also exposed an essential product requirement: Heima must retain future events so a
consumer can decide today about an event tomorrow.

**Resolution applied to `docs/specs/v3/layer0_runtime_spec.md` §3.4/§12,
`docs/specs/v3/layer2_registries_spec.md` §3.1/§4/§9, and `v3_architecture_recap.md` Layer 0/2**:
Layer 0 owns an asynchronously refreshed, UTC-normalized timeline cache with explicit `ready` versus
`failed` status. It exposes two distinct views: `active_now` for the current fact and
`upcoming_starts_within(..., horizon)` for predictive consumers. A consumer declares its horizon
(e.g. seven days), receives complete future windows rather than categories, and Layer 0 prefetches far
enough to serve it and schedule boundaries without synchronous provider I/O.

All-day events use HA-local midnight-to-midnight-exclusive conversion before UTC normalization;
intervals are `[start, end)`. Calendar matching is now deterministic for active windows only: normalized
keyword substring matching, then configured `priority_order`; future events cannot accidentally change
today's category. Restart takes a fresh snapshot, exposes currently active events, and never replays
past boundaries or trusts checkpointed calendar data.

---

## Canonical Location, Zone, and Topology identity, resolved (2026-09-08)

Closed the next intervention from the full v3 docs reread. Spatial references previously had clear
business meanings but no complete equality, serialization, or validation-boundary contract. That made
duplicate producer detection and durable identity vulnerable to container order and registry-load order.

**Resolution applied to `docs/specs/v3/layer1_substrate_spec.md` §5-§7/§10 and
`docs/specs/v3/layer2_registries_spec.md` §2.3**: `Location` now has a concrete `LocationKey`, with a
`rooms` set serialized in Unicode-code-point order; equality, hashing, `FactIdentityKey`, and producer
uniqueness use it. `ZoneKey` is stable `zone_id`, while its separately ordered definition fingerprint
detects a membership or display-name change. The installation-wide `Topology` canonically orders
openings and connections, validates one opening owner per connection, recomputes derived exposure/floor
views, and fingerprints the deterministic result.

Lightweight value objects validate shape, cardinality, and non-empty opaque identifiers at construction.
References are resolved when their owning registry registers, and Layer 2 resolves each producer's
`Location` in the same pass as its dependency graph: configuration can load in any order, but no unknown
room or zone can reach a running producer.

---

## HouseFact state/event semantics and producer ownership, resolved (2026-09-09)

The manual-hold lifecycle resolution exposed a foundational contradiction: Layer 1 prohibited a
`HouseFact` from representing a transition, while Layer 0 deliberately emitted lifecycle facts; the
existing producer-uniqueness rule also covered only Layer 2 and could not protect Layer-0 facts from
a colliding Sensor or FusionRule.

**Resolution applied to `docs/specs/v3/layer0_runtime_spec.md` §4/§12,
`docs/specs/v3/layer1_substrate_spec.md` §3/§10,
`docs/specs/v3/layer2_registries_spec.md` §2.3/§5/§9, and the architecture recap**: a `HouseFact` is
one immutable atomic assertion, either `state` or `event`, selected by producer metadata rather than a
field on the fact. State facts retain `FactIdentityKey`, write-on-change, latest-value reconstruction,
and latest-record retention protection. Event facts append every occurrence, have no current value or
`FactRef` address, and follow ordinary retention.

`FactTypeClaim` is a composition-time ownership table, not a runtime registry: claims are resolved into
producers before a cycle starts and reject overlapping ownership or state-producer collisions. Layer 0
reserves `manual_hold.*` as state and `manual_hold.*.lifecycle` as event; Layer 2 contributes only
state claims. This makes later layers declare their own fact ownership explicitly without adding I/O or
lookup cost to the reaction path.

---

## HeimaEvent to HouseFact mapping, resolved (2026-09-09)

`HeimaEvent` had a useful operational shape (`type`, `key`, `severity`, `context`) but no complete
translation into the universal fact model. In particular, silently dropping the delivery key or
severity would have broken Layer 6, while persisting a parallel event envelope would have recreated
the competing-model problem Layer 1 is meant to eliminate.

**Resolution applied to `docs/specs/v3/layer1_substrate_spec.md` §3.1/§10 and the architecture
recap**: a `HeimaEvent` is now a transient delivery envelope derived from exactly one append-only
`HouseFact` event. The V3-approved event type maps to `fact_type`; `key`, `severity`, rendered
`title`/`message`, and JSON-compatible `context` live in the named `OperationalEventValue`; the fact
has mandatory typed `Location` and normal Layer-0 causal provenance. The transient delivery id is not
fact identity and is not separately persisted. Only V3-approved event types are admitted; V2 events
remain external archive material and have no migration map or runtime fallback. Persistence never deduplicates event facts. Layer 6 uses
`notification_key` only for delivery deduplication/rate limiting, so suppressing a notification does
not remove an occurrence from audit history, and severity never becomes a fact identity or ownership
key.

---

## Formula inputs retain unavailable evidence, resolved (2026-09-09)

The prior formula contract passed only available inputs to `RegisteredFormula.compute`. That was
insufficient for a room-presence formula: it could not distinguish a sensor reporting definitive
`False` from a sensor that was unavailable, and could therefore declare a room vacant on incomplete
evidence.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §5.3/§5.5/§5.8/§10 and the
architecture recap**: a formula receives every declared input in stable `FusionRule.inputs` order,
retaining each fact's availability. `min_inputs` continues to count only available facts, so it still
prevents a formula from running with no observation at all. Above that floor the formula can use a
positive available input while noticing a missing peer, or return unavailable conservatively. The
generic Direct/Unanimity/WeightedQuorum/Precedence strategies retain their existing unavailable-input
exclusion semantics. An inherited-confidence result may select only an available configured input.

---

## Per-sensor room-occupancy evidence namespace, resolved (2026-09-09)

The one-state-producer identity `(fact_type, Location)` made the earlier shorthand “fuse N occupancy
sensors in one room” impossible: two PIRs producing the same `occupancy.raw` fact would collide and
could not be addressed independently by a `FusionRule`.

**Resolution applied to `docs/specs/v3/layer1_substrate_spec.md` §3 and
`docs/specs/v3/layer2_registries_spec.md` §3/§4/§9**: each room-occupancy source produces
`occupancy.evidence.<kind>.<sensor_id>`. `<sensor_id>` is the stable Heima logical-reading id, never
the mutable HA `entity_id`; it preserves source identity across a binding rename or replacement.
The canonical derived state remains `occupancy` at the room `Location`. This preserves direct
`FactRef` addressing of every contributing sensor without adding a new global fact identity field.

---

## Configurable weighted room-occupancy formula, resolved (2026-09-09)

Hardcoding `motion`, `presence`, and future sensor kinds inside a room-occupancy formula would have
made every new device category a code change. A single undifferentiated vote weight was also
insufficient: a sensor's `True` and `False` readings can carry materially different meaning, and a
missing source must be distinguishable from both.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §2.4/§5.1/§5.3/§9 and the
architecture recap**: the core `occupancy.weighted_evidence` formula takes a closed typed config with
one binding per ordered input. Each binding declares primary/supporting role, independent true and
false weights, and whether availability is required before vacancy can be concluded. It evaluates
only available exact booleans; any primary true or sufficient weighted positive evidence yields
occupied, while vacancy requires sufficient weighted negative evidence plus all required sources.
The categorical result confidence uses evidence scores and potential available weights, preserving
low source reliability and disagreement. New sensor kinds require only a normalized Sensor plus
binding.

---

## Stability unavailable grace, resolved (2026-09-10)

Immediate unavailable output on every short source flap would cause unnecessary downstream churn,
but allowing a pending true/false dwell to complete after its supporting evidence vanished would be
incorrect.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §2.4/§2.5/§5.2/§9 and the
architecture recap**: boolean `Stability` gains optional `unavailable_grace`. On unavailability it
first cancels directional pending state; it then retains only the last committed available output for
the bounded interval, with one Layer-0 `AtJob` and no polling or per-cycle writes. Recovery before
expiry cancels the grace; expiry emits one unavailable fact. Grace is not restart-safe and is cleared
by an impacted reload. It defaults off; room occupancy may opt into 30 seconds, while security rules
remain immediate-unavailable. Diagnostics expose each active grace and its unavailable inputs.

---

## Fusion runtime-state ownership, resolved (2026-09-10)

The pending dwell and unavailable-grace state of a `FusionRule` was known to be ephemeral, but its
owner was left ambiguous between a Layer-2 structure and Layer 0's short-term fact buffer.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §5.2/§8 and the architecture
recap**: Layer 2 owns an O(1) `FusionRuleRuntimeState` by `fusion_id`, containing pending transition
and grace/deadline-token data. Layer 0 owns only the `AtJob`. The state is never persisted, checkpointed,
or encoded as history; it is discarded on restart and selectively at an impacted reload. This prevents
historical `Window` storage from becoming a second control-state mechanism and keeps the hot path
bounded.

---

## Immutable formula registry and selective version reload, resolved (2026-09-09)

The formula contract had a shape and hot-path constraints but no lifecycle: a missing formula, a
semantically wrong input sequence, or a changed implementation could otherwise reach evaluation
without a deterministic staging failure or a scoped recovery path.

**Resolution applied to `docs/specs/v3/layer2_registries_spec.md` §2.5/§5.3/§9 and the architecture
recap**: core modules register formulas only during bootstrap, then freeze an immutable O(1) catalog.
Each entry has an explicit semantic implementation version and a pure binding validator. Staging
resolves the formula and validates inputs, order, output, `previous_cycle`, and typed configuration;
the durable generation records only id, version, and canonical configuration, never code callables.
At a later startup, a changed resolved `(formula_id, implementation_version)` enters the existing
selective impact set: only its dependent/transitive fusion rules reset their ephemeral state, lose
old-generation prior-cycle memory, and force-write under the new configuration fingerprint.

---

## Manual-hold provenance boundary, resolved (2026-09-09)

The lifecycle contract still left `FactSource.source_id` implicit, used the invalid actor value
`"admin"`, and treated a helper merely being active as proof of a resident action. It also split one
replacement operation into two causal chains.

**Resolution applied to `docs/specs/v3/layer0_runtime_spec.md` §5.1/§6.1/§12 and the Layer 0 recap**:
each hold transition now has a complete `kind`/`source_id`/`source_type`/`actor_type` tuple. Explicit
resident actions require a state edge whose HA context identifies a non-admin resident; an
admin-attributed edge on the same dedicated helper legitimately produces `admin_command` with
`actor_type="ha_admin"` for activation or clear. Service, automation, and unknown edges are rejected
with diagnostics. A replacement's old terminal and new activation pairs share the single correlation
id of the action that caused both.

---

## Manual-hold lifecycle facts, resolved (2026-09-09)

Closed the final architecture intervention from the full v3 docs reread. The previous manual-hold
contract declared an active fact and mentioned restoration, but made closing facts optional and left
discarded restoration as diagnostics only. Audit, Recovery, and any future notification consumer could
therefore disagree about what happened to one hold.

**Resolution applied to `docs/specs/v3/layer0_runtime_spec.md` §6/§12 and
`v3_architecture_recap.md` Layer 0**: each hold instance has one immutable `hold_id`. The state fact
`manual_hold.<domain>` records the current transition with `active=True` or `False`; its paired
`manual_hold.<domain>.lifecycle` event records activated, cleared, expired, replaced, restored, or a
specific restoration-discard reason. The state is the only live-state input; events are audit and
notification material.

The source is fixed by transition: helper-backed resident response, legitimate domain inference,
admin command, system timeout, or Recovery. A successful restore recreates both active state and
`restored` event under one fresh Recovery correlation id. Every failed restore emits exactly one
`restoration_discarded` event, including the reason, and never emits an active state fact. This remains
transition-driven and introduces no synchronous I/O or extra polling on the evaluation path.

---

## Explicit manual-hold identity after restart, resolved (2026-09-09)

The helper entity is authoritative for the live state of an explicit hold, but cannot itself retain
the immutable `hold_id` required by the state/lifecycle contract. Treating the helper as wholly
restart-safe therefore left an identity gap: after a restart with the helper still active, Layer 0
could neither prove which instance was active nor close it reliably later.

**Resolution applied to `docs/specs/v3/layer0_runtime_spec.md` §6.2/§7.3/§12 and the Layer 0 recap**:
the immediate checkpoint now contains a narrow active `ExplicitHoldIdentity` record keyed by helper,
domain, and `Location`. It is identity/audit metadata only, never a live-state source. Bootstrap
reconciles it once with the helper: active plus matching record restores the same id; active without
one mints a new id and records a Recovery activation; inactive plus a stale record emits a Recovery
clear and removes it. Normal cycles retain their fresh helper read and incur no additional I/O.

---

## Power-recovery baseline plus current reconciliation, resolved (2026-09-09)

Restoring only the physical states observed before a blackout would replay stale intent after a long
outage; relying only on a fresh policy evaluation loses non-reconstructible desired targets. The
required behavior is both: recover the house baseline, then immediately account for what changed
while it was unavailable.

**Resolution applied to Layer 0 §7.4 and Layer 2 `Actuator`**: opt-in actuators maintain a compact,
last-write-wins checkpoint of their accepted desired target. The checkpoint is batch-coalesced, never
synced for every target change; the resulting bounded staleness is explicitly accepted for
performance. On a confirmed power recovery, current evaluation starts from that baseline but current
facts, time/calendar state, safety, and manual holds take precedence before a single final delta is
applied. No historical command is replayed. Per-actuator policy is `reconcile`, `never` (default), or
`require_confirmation`; Layer 0 stores/exposes opaque targets but never reads the live Actuator
registry or sends a command.

---

## Manual-hold journal and crash consistency, resolved (2026-09-09)

The immediate checkpoint for a hold and the end-of-cycle facts batch are separate durable writes. A
crash between them could leave a `hold_id`, its state fact, and its lifecycle audit disagreeing.

**Resolution applied to Layer 0 §6.2-§6.4/§7.3/§8/§12 and the Layer 0 recap**: every explicit and
implicit hold transition first enters a narrowly scoped `fsync`-backed `ManualHoldJournalEntry` with
its complete fact roles and intended checkpoint update. Fact writes are idempotent by operation/role;
bootstrap replays incomplete entries before any ordinary hold reconciliation and compacts them only
after the facts batch acknowledges. This is not a general event journal. A journal I/O failure keeps
the hold live for safety but marks it `durability_pending`, retries outside the hot path, and honestly
accepts that a crash before successful persistence loses its identity/audit continuity.

---

## `FactRef.previous_cycle` snapshot and restart semantics, resolved (2026-09-09)

The previous contract alternated between “either Persistence tier” and “durable tier after every
restart”. That could put disk I/O into formula evaluation or silently supply an older value after an
unclean stop or failed batch.

**Resolution applied to Layer 0 §4/§12, Layer 2 §5/§5.8/§7/§9, and the recap**: composition declares
the finite set of previous-cycle keys. Layer 0 seals only those values in an O(1) in-memory snapshot
after each cycle; it remains valid through a durable-batch failure while the process is alive. A batch
atomically carries a cycle marker and one clean-shutdown marker is written at orderly exit, allowing
pre-DAG hydration after a clean restart. Any unclean/mismatched/known-failed restart exposes
`available=False` for the first cycle, never an ambiguous older record. No per-cycle fsync and no
formula-side disk read are introduced.

---

## Atomic registry reload and Zone semantic generations, resolved (2026-09-09)

Zone identity intentionally stays stable when membership changes, but the meaning of zone-scoped facts
and Fusion coverage changes with it. A piecemeal reload could therefore mix old membership, a new
Fusion graph, stale debounce state, and old recovery policies in one cycle.

**Resolution applied to Layer 0 §5/§7.4/§12, Layer 1 Zone, Layer 2 §2.5/§9, and the recap**: config
reload stages and fully validates one immutable generation, persists its definition fingerprints, and
swaps it only between cycles. It computes the changed Zone’s direct/transitive Fusion impact set;
only that set loses `Stability` and `previous_cycle` memory. Retained impacted facts are force-emitted
with a non-forgeable configuration fingerprint, removed producers emit terminal unavailable state, and
Actuator recovery targets are discarded when their candidate fingerprint/policy no longer matches.
An invalid candidate leaves the running generation exactly unchanged.

---

## V3 clean-start cutover, resolved (2026-09-10)

The earlier one-time migration-script decision was re-evaluated against the only data worth carrying
forward: the historical learned house state. That history was materially unreliable for a prolonged
period, so converting the old configuration would preserve setup effort without preserving trustworthy
learning value.

**Resolution applied to Layers 0-2, the recap, and this backlog**: V3 starts from new explicit
configuration and cold durable/in-memory fact stores and learning models. It imports neither the nine
legacy entity lists nor any other V2 options, event/history records, runtime checkpoints, or learned
state. There is no one-shot importer, compatibility adapter, legacy event-type map, or silent
in-place conversion. This keeps bootstrap and the cycle hot path free of legacy branches and avoids
claiming semantic continuity that the old learned data cannot support.

A V2 export may be retained outside the V3 runtime solely as rollback/reference material. Cutover is
an explicit operator action that creates or resets V3 configuration; it must not destructively rewrite
the existing V2 configuration. The concrete Layer-8 user interface remains to be specified, but it
cannot alter these semantic guarantees.

---

## Stability dwell deadlines and fast path, resolved (2026-09-10)

The prior `Stability` wording created pending state for every changed candidate and only described an
`AtJob` for availability grace. That delayed a configured no-dwell transition by at least one later
cycle and could delay a positive dwell indefinitely until an unrelated event or periodic fallback.
Both outcomes contradict Heima's reaction-time requirement.

**Resolution applied to Layer 2 §5.2/§9 and the recap**: `None` is a same-cycle fast path, not a
one-cycle dwell: a changed available candidate with no applicable dwell commits immediately. A positive
dwell records one ephemeral pending value/since/due/token/generation and arms exactly one Layer-0
`AtJob`. At expiry, the callback re-evaluates the fusion slice against current in-memory facts and
commits only if its token, generation, and candidate still match; it never writes the value captured
when the deadline was armed. Input changes, unavailability, restart, and impacted reload cancel or
replace the pending deadline. This provides prompt bounded transitions without polling, disk/network
I/O, or a stale-callback race.

---

## Semantic reload fingerprints and complete impact propagation, resolved (2026-09-10)

The prior reload rule identified direct impact only from Zone membership and formula-version changes.
A changed Sensor binding/interpretation/reliability or FusionRule strategy/inputs/stability could
therefore retain old dwell, prior-cycle memory, or current output. It also followed only same-cycle
dependencies even though a `previous_cycle=True` reader still depends semantically on its producer.

**Resolution applied to Layers 0-2, the recap, and acceptance criteria**: staging alone computes one
execution-semantic fingerprint per producer after resolving the complete candidate generation and
compares it with the active generation's already-stored value. The fingerprint contains only
execution-relevant fields; full definition fingerprints retain display/UI metadata for audit but do
not cause runtime churn. The impact set begins with every added, removed, relocated, or semantically
changed producer, including Zone and formula-version effects, then propagates through both current and
previous-cycle Fusion dependencies. Only that set resets fusion control state, invalidates its output
previous-cycle keys, and force-writes retained output under its new semantic fingerprint. This has no
per-cycle hash, comparison, or lookup cost.

---

## Bucket burst removed pending a real event contract, resolved (2026-09-10)

`BucketInterpretation` exposed `burst` and `burst_direction`, but defined neither an output nor
event/state semantics, retention, consumer, or temporal comparison rule. It was configuration without
an implementable behavior.

**Resolution applied to Layer 2 and the recap**: both fields are removed. A future burst requirement
must be modeled as its own explicit fact, normally an event carrying previous/current observation,
direction, and observed window; it must not be hidden in a bucket value or `evidence`, whose
non-load-bearing semantics would make the signal unreliable for policy decisions.

---

## Explicit interpretation input contracts and reusable keyword classification, resolved (2026-09-10)

`CalendarInterpretation` previously combined two separate concerns: aggregation of active calendar
windows and a reusable textual keyword classifier. Numeric continuous readings also had no formal
interpretation despite being required by outdoor temperature and climate attributes; consequently a
future implementation could have guessed coercions or attached an interpretation to incompatible raw
binding input.

**Resolution applied to Layers 0-2, recap, and acceptance criteria**: `KeywordClassifier` is a pure,
configured text-sequence classifier, composed by the calendar-specific active-window wrapper
`CalendarInterpretation` and reusable by a predictive consumer through an explicit configuration.
`NumericInterpretation` normalizes only strictly accepted finite values to `float`; it has no unit,
range, rounding, or fallback policy. Candidate staging enforces the closed binding/interpretation pairing
and all numeric parsing remains deterministic, non-throwing, and free of silent coercions in the hot
path.

---

## `available` means usable fact assertion, resolved (2026-09-10)

Layer 1 described `available=False` primarily as an unreachable or offline source, while Layer 2 also
used it when a successful raw read could not yield a meaningful normalized fact. That made a valid
interpretation failure look like an undocumented exception to the substrate contract.

**Resolution applied to Layers 1-2 and acceptance criteria**: availability is the single consumer
contract for whether a producer can assert a usable value for its fact at that instant. Read failure,
failed interpretation, and insufficient derived evidence are distinct producer-local causes of the
same unavailable result. No shared reason enum is introduced: diagnostics and optional non-load-bearing
evidence retain details without forcing all consumers or all producers into a premature global taxonomy.

---

## Transition history versus current state, resolved (2026-09-11)

The short-term buffer said that every write reached memory immediately, while durable persistence used
write-on-change. It did not establish whether unchanged observations consumed history, nor whether
several real transitions of one state claim in a single cycle could be coalesced and lost.

**Resolution applied to Layer 0, recap, and acceptance criteria**: the O(1) latest-value index and the
transition history are distinct views. A state candidate unchanged against the in-memory current
fingerprint appends nowhere; every changed candidate appends to both the buffer and ordered durable
retry queue, even when the same key changes several times in one cycle. Internal
`AppendOrder(cycle_id, ordinal)` resolves equal timestamp ties without changing `HouseFact` identity or
public shape. A failed batch retains its queue and never makes the live current comparison regress to
an older durable record.

---

## Temporal primitive construction validation, resolved (2026-09-11)

`Window`, learned bounds, recurrence intervals, civil weekly fields, and dynamic deadlines had semantic
descriptions but no single construction contract. Invalid zero/negative/non-finite values or Python
`bool` values could otherwise reach scheduling, retention sizing, or a dwell calculation.

**Resolution applied to Layer 0, recap, and acceptance criteria**: a pure shared validator admits only
finite strictly positive non-boolean durations and validates weekly civil ranges plus UTC-aware
deadlines. Static values are checked while staging startup/reload configuration; a dynamic `AtJob` is
checked once at scheduler registration. Equal learned min/max bounds deliberately remain valid. Nothing
is clamped, corrected, or revalidated in the hot evaluation cycle.

---

## Actuator endpoint ownership and opening coherence, resolved (2026-09-11)

The Actuator registry identified entities but did not forbid duplicate command ownership or connect an
optional opening reference to the candidate topology. Two records could then compete for one recovery
target or implicit-hold classification; a rebind could also leave a target keyed to an endpoint no
longer owned by the logical actuator.

**Resolution applied to Layer 2, recap, and acceptance criteria**: `actuator_id` and command
`entity_id` are each unique within a generation, while Sensors may still observe the same entity and a
device may expose several actuator endpoints. `opening_id` is optional; only when supplied must it
resolve and match the actuator's room. Removal or entity rebind deletes the old recovery target rather
than migrating intent across HA endpoints automatically.

---

## ApplyStep actuator-target boundary, resolved (2026-09-11)

Preventing duplicate Actuator records alone was insufficient: a Reaction could still nominally select
one logical actuator while placing another HA entity, device, or area in the service payload. A Heima
capability catalog was considered and rejected because it would duplicate Home Assistant service and
feature logic.

**Resolution applied to Layer 2, recap, and acceptance criteria**: each ordered `ApplyStep` addresses
one `actuator_id` and carries only one HA service plus non-target parameters. The execution boundary
resolves the entity from the active registry and rejects caller-supplied target selectors. HA validates
the actual service/schema/support at application time. Multi-command reactions emit individual ordered
steps, preserving per-command provenance without reimplementing HA capabilities.

---

## Formula configuration compilation boundary, resolved (2026-09-11)

The formula registry was extensible but `FormulaConfiguration` was a closed union containing only the
occupancy configuration. Replacing it with Layer 1 `EvidenceValue` would have been equally wrong:
formula configuration may legitimately contain an ordered array of binding objects, deeper than that
fact-evidence type intentionally permits.

**Resolution applied to Layer 2, recap, and acceptance criteria**: a `FormulaStrategy` persists only
a bounded canonical JSON object (or `None`). Each core `RegisteredFormula` compiles and validates that
payload once during candidate staging into its own immutable internal configuration type; binding
validation and `compute` receive only this compiled form. The active generation holds that object in
memory, while persistence holds id/version/canonical JSON only. New configured formulas no longer
reopen a global configuration union or add parsing work to the hot path.

---

## Layer 0/1 foundation dependency, resolved (2026-09-11)

The documents correctly had Layer 0 Persistence consume Layer-1 `HouseFact`/`Location` values and
Layer-1 `Provenance` embed Layer-0 `FactSource`, but Layer 1 simultaneously claimed that nothing in
Layer 0 depended on Layer 1. That was a false one-directional layering claim and would invite an
implementation-level import cycle or an ownership workaround disconnected from the actual contracts.

**Resolution applied to Layers 0-1 and the recap**: Layers 0 and 1 are one foundation slice with
separate ownership. Their only reciprocal references are immutable data contracts; Layer 0 never
queries Layer-1 registries or policy, and Layer 1 never executes Layer-0 runtime behavior while
constructing value objects. Bootstrap composes both before cycles, the hot path contains no behavioral
cycle, and code may use a neutral contracts module or type-only references without creating a new
architectural layer.

---

## `IntervalRecurrence` restart policy, resolved (2026-09-11)

An earlier policy required a one-time interval catch-up after restart but persisted neither the
interrupted `due` nor an execution watermark. It therefore asked the implementation to decide whether
an interval was missed without possessing the information required to decide it.

**Resolution applied to Layer 0 and acceptance criteria**: no `CronEntry` replays missed occurrences.
An interval's first post-restart deadline is `now + interval`; a weekly recurrence arms its next civil
occurrence. An owner that needs a startup action declares and executes it in explicit bootstrap logic,
never as an accidental side effect of scheduler recovery. This avoids durable per-interval runtime
state and makes startup work independently reviewable and testable. This supersedes the earlier
interval catch-up decision recorded in the 2026-09-08 review.

---

## Numeric scalar validity, resolved (2026-09-11)

`EvidenceValue` permitted Python `float` without explicitly rejecting `NaN`/infinity despite its JSON
serialization contract. Several quantitative validators also relied on range checks that would accept
Python `bool` as `1` or `0`, although a boolean is evidence semantics, not a numeric configuration.

**Resolution applied to Layers 1-2 and acceptance criteria**: every float carried in fact value or
evidence is finite, recursively; a contract field requiring a quantitative number accepts only a
non-boolean `int` or finite `float`. Explicit boolean fact values and flags remain valid. The shared
confidence helpers and `Provenance` validation enforce the same distinction, so a `bool` cannot enter
confidence, weight, threshold, reliability, support, dispersion, or another numeric path by Python
subclass accident.

---

## Bounded Heima payload boundary, resolved (2026-09-11)

The evidence-size decision needed an explicit ownership boundary as well as a number: accepting a
bounded JSON shape is insufficient if a raw mutable HA `State`, complete attribute map, or event
context can leak by reference into a fact or a runtime buffer.

**Resolution applied to Layers 0-1 and acceptance criteria**: canonical UTF-8 `evidence` and normalized
`HouseFact.value` are each capped at 8 KiB. HA runtime objects are boundary input only; bindings copy
only declared, normalized scalar or small structured projections before fact construction. No Heima
buffer, durable queue, journal, previous-cycle snapshot, recovery snapshot, or checkpoint keeps an HA
runtime object. The calendar cache is explicitly limited to its normalized window fields, not the
provider response.

---

## `FactTypeClaim` glob ownership, resolved (2026-09-11)

The prior wildcard wording did not define whether `*` applied to a whole fact type, one namespace
segment, or a substring, so a claim such as `manual_hold.*.lifecycle` could be implemented differently
by different consumers. Full regex was considered but rejected as unnecessary for this ownership
contract.

**Resolution applied to Layers 0-1 and acceptance criteria**: claims use a minimal dotted glob. A
pattern full-matches the same number of non-empty fact-type segments; `*` matches zero or more
non-dot Unicode code points within one segment, allowing both `*` and partial forms such as `*door*`.
Staging computes pattern overlap. It permits overlapping claims only when their owner and emission kind
are identical, and rejects every other overlap so each concrete fact type has one owner and one
persistence semantic. Matching is compiled at staging and never performed in the hot path.

---

## Retention target versus hard count ceiling, resolved (2026-09-11)

The retention-floor wording claimed that a learner's declared historical duration was guaranteed,
while the same persistence policy allowed the per-`fact_type` count ceiling to evict older records
early for a noisy source. Both statements could not be true.

**Resolution applied to Layer 0 and the recap**: a declared duration is a target honored by ordinary
time-based pruning, while the count ceiling remains a hard per-`fact_type` safety limit. Persistence
durably records the latest count-ceiling eviction and returns `retention_coverage` with every history
read. A consumer requiring a complete window, including a PatternLearner, remains warm-up/degraded
when that window is truncated and emits diagnostics; it never learns from a silently shortened
history. This preserves storage and latency bounds without producing misleading learned output.

---

## Default durable retention, resolved (2026-09-11)

**Decision applied to Layer 0**: the system-wide durable retention baseline is **14 days**. A
fact type with no declared historical requirement uses that target; a consumer that declares 30 or
90 days raises the target for that fact type to the maximum declared duration. The per-fact-type
count ceiling remains a separately chosen hard safety bound and can still surface truncated coverage.

---

## Durable record ceilings and global storage pressure, resolved (2026-09-11)

**Decision applied to Layer 0 and the recap**: each `fact_type` has a hard default ceiling of
**50,000 records**. The durable fact store also has a **512 MiB global pruning watermark**. Above it,
background maintenance removes globally oldest evictable records after normal time/per-type pruning;
affected history reports truncated retention coverage. The watermark is intentionally not an admission
quota: latest state records are never removed and observations are never rejected. If protected latest
states alone exceed it, Heima reports `storage_pressure` for operator action rather than sacrificing
the current house state. Both values are operational defaults and may be revised from evidence in a
future release.

---

## Short-term buffer horizon and isolation, resolved (2026-09-11)

The prior rule used the largest registered `Window` as one global in-memory horizon. One unusually
long correlation would therefore retain every unrelated fact for that duration.

**Decision applied to Layer 0**: each addressable input stream has a **15-minute** default horizon.
State requirements apply to one `FactIdentityKey`; event requirements apply to one `(fact_type,
Location)` stream. A longer declared window extends only its own stream. No absolute maximum is set
before operational evidence exists; diagnostics expose the largest declared horizon and aggregate
buffer memory for a later evidence-based limit.

---

## Recovery checkpoint cadence, resolved (2026-09-11)

**Decision applied to Layer 0**: Recovery owns one 60-second `IntervalRecurrence`. Its callback
performs a checkpoint replacement only when state is dirty, so an idle system incurs no periodic disk
write. Accepted recovery targets coalesce last-write-wins until the next dirty commit; manual-hold
journaling and the already-defined critical recovery transitions retain their stricter immediate
durability semantics. This bounds ordinary target-snapshot staleness without synchronous I/O on every
actuator action.

---

## Admin-authored schedule authority, resolved (2026-09-11)

**Decision applied to Layer 0 and the recap**: an admin-configured routine uses Home Assistant's
`schedule.*` helper as its sole recurrence authority. Heima maps only the helper's effective state
through the ordinary Sensor/Mapping path and lets Reactions consume the resulting boolean fact. It
does not add its own picker, schedule persistence, timezone/DST calculation, or recurrence callback.
`CronEntry`/`AtJob` remain exclusively for Heima-internal timing such as checkpointing and retries.

---

## Implicit-hold restoration eligibility, resolved (2026-09-11)

**Decision applied to Layers 0-2**: `implicit_hold_restore_class` has no global or role-level
inheritance. It defaults to `"never"`, and restoration is enabled only by explicit
`"eligible"` configuration on the individual `Actuator` entry. The resolved value remains frozen
into the hold at creation, preserving the existing restart audit and avoiding hidden policy precedence.

---

## Unanimity under partial availability, resolved (2026-09-11)

**Decision applied to Layer 2**: `available=False` is excluded from `UnanimityStrategy`, never
converted to a `False` vote. Missing observation is not negative evidence. `min_available` is now
mandatory: strict unanimity is expressed as `len(inputs)`, while a lower value is an explicit choice
to operate with partial availability. This prevents both fabricated dissent and an accidental
one-surviving-sensor default.

---

## Closed semantic registries and plugin boundary, resolved (2026-09-11)

**Decision applied to Layer 2**: `Interpretation`, `FusionStrategy`, and `RegisteredFormula` remain
closed core-owned registries. They are not a third-party extension surface because they define hot-path
fact semantics, availability, confidence, DAG behavior, reload impact, and failure handling. A future
general strategy is a core specification change, not a plugin callback. Layer-7 plugins may instead
stage as ordinary fact producers with `FactTypeClaim`/`HouseFact` contracts; their outputs may feed
existing fusion strategies but cannot mutate their union or install callables in the evaluation path.

---

## Cumulative Fusion stability visibility, resolved (2026-09-11)

**Decision applied to Layer 2**: stability may remain at each semantic level in a fusion chain; it is
not restricted to top-level rules and carries no arbitrary warning threshold. Registry staging instead
computes immutable `StabilityPathSummary` metadata: maximum cumulative delay and a deterministic
responsible path for each transition direction, over same-cycle Fusion edges only. The summary is
diagnostic/UI metadata with no runtime behavior or fingerprint impact, making configurations such as
120-second room debounce plus 60-second zone debounce visibly 180 seconds end-to-end.

---

## Prior-cycle references limited to formula self-memory, resolved (2026-09-12)

**Decision applied to Layer 2**: `FactRef.previous_cycle=True` is valid only for an exact
`FormulaStrategy` self-reference: same `produces` and `where`, explicitly permitted by the resolved
core formula's binding validator. It models a prior posterior, moving average, or accumulator without
hidden mutable state. Non-formula use and every cross-producer delayed reference are rejected during
staging. This avoids opaque temporal state machines such as mutual one-cycle dependencies while
retaining the only demonstrated use case; a future cross-producer delay requires its own explicit
temporal contract.
