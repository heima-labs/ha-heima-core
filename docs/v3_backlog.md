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
- **SR-3** — resolved 2026-09-02. Simplified by `CLAUDE.md`'s own "no backward compatibility, sole
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
