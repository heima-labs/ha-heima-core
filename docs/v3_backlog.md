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

> **Superseded for V3 on 2026-10-13** by Layer 8 decision L8-C1 ("Layer 8 specification
> decisions"): all configuration moves to one Heima panel; the config flow keeps only the initial
> installation. Kept below as history.

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

### Layer 6 specification decisions (approved, 2026-10-12)

Decisions recorded before the Layer-6 specification was written. The approved
[Layer 6 spec](specs/v3/layer6_notification_spec.md) (2026-10-13) now owns them; this list is history.
Inputs are the closed typed occurrences of CA4-65–68.

- **C1 — Recipients.** A `NotificationRecipient` is one person: stable `recipient_id`, optional
  `ha_user_id` (links an actionable answer to the person; authentication stays at Layer 0's
  ingress), `endpoints` (`notify.*` with `supports_actions`, as in V2) and `audiences`. V2 groups
  and free routes are not carried over: each typed notification has a closed audience —
  `residents`, `administrators`, `consent_authorities`. The administrator only assigns people to
  `residents`/`administrators`; `consent_authorities` is derived from `HouseholdConsentAuthority`
  through `ha_user_id`, never configured by hand. Audience membership is a delivery preference,
  never authority. An audience with no reachable recipient never drops a notification silently
  (fallback channel: C2).
- **C2 — Channels (use Home Assistant infrastructure wherever possible).** Primary delivery is the
  recipients' `notify.*` endpoints; closing/replacing a notification uses the mobile notification
  `tag` set to `notification_key`; button answers arrive through HA's `mobile_app_notification_action`
  event, which Layer 6 forwards to Layer 0's response ingress. `persistent_notification` is the
  fallback when an audience has no reachable recipient or every endpoint failed after retries;
  Layer-6 diagnostics record which channel delivered each notification (the Layer-0 outbox stores
  no channel). Retries use core-fixed attempts and growing intervals. An
  actionable notification goes only to `supports_actions` endpoints; without one it is sent without
  buttons and stays answerable from the Layer-8 surface through the same ingress. Every delivered
  notification also fires a `heima_notification` HA bus event with closed fields (type, audience,
  operation id), no text or identity, for users' own automations. Actionable types: recovery
  confirmation (approve/dismiss), household consent (grant/decline, CA4-69), advisory feedback
  (done/dismiss/not_useful, CA4-69); proposal review links to the Layer-8 panel; follow-up,
  availability and action notices are informative.
- **C3 — Families, priority and quiet hours.** Closed families, one per notification type:
  `safety` (weather-protection `reaction.action_notice`; `manual_hold_active` availability on a
  protected channel) high; `attention` (`reaction.follow_up`, other `automation.availability`,
  `recovery.confirmation_request`) normal; `suggestion` (`reaction.advisory`) low; `governance`
  (`reaction.consent_request`, `proposal.review_pending`) low. Core-fixed quiet-hours behavior:
  `safety` bypass; `attention` defer to the end of quiet hours; `suggestion` held and delivered as
  one digest at the end of quiet hours containing only advisories whose activation is still open
  (an advisory closed meanwhile retires undelivered, CA4-71); `governance` defer, with proposal
  reviews grouped by the digest (C4). Quiet hours are the existing casa
  `quiet_hours.active` fact (Layer 5 §3.2), one source for guards and notifications; without it
  there are no quiet hours. The administrator may only turn a deferring family (`attention`,
  `governance`) to silent; `safety` can never be silenced.
- **C4 — Digest.** Only `proposal.review_pending` (administrators) is grouped; consent requests stay
  individual (actionable, rare, deferred in quiet hours) and advisories use the C3 end-of-quiet-hours
  digest. The first open proposal starts a core-fixed 30-minute collection window; at its end one
  notification ("N new proposals to review", link to the Layer-8 panel) covers every proposal still
  open for review; at most one proposal digest per audience every 4 hours, later proposals wait for
  the next one; a digest due in quiet hours is sent when they end. A fixed HA notification `tag` per
  audience makes each digest replace the previous one, and Layer 6 clears it (`clear_notification`)
  when no proposal remains open. Each proposal keeps its own outbox record and audit fact; one
  delivery covers several records, each marked `delivered`; a proposal closed before its digest
  retires undelivered. Open means a latest `created`/`approvable_again` phase without a later
  `closed` (CA4-71). No new fact type, store or schedule.

- **C6 — Languages and text.** Event facts store no resident text (CA4-72): Layer 6 renders title and
  message at each delivery from the fact's closed fields, core-fixed versioned templates, the
  recipient's locale and the currently configured names; Layer 8 renders history the same way.
  The household locale is HA's `hass.config.language`; a `NotificationRecipient` may declare its own
  `locale`. Initial V3 supports Italian and English, with English as fallback. Administrators
  cannot edit templates.

### Layer 8 specification decisions (approved, 2026-10-13)

Decisions recorded before the Layer-8 specification was written. The approved
[Layer 8 spec](specs/v3/layer8_administration_spec.md) (2026-10-13) now owns them; this list is history.

- **L8-C1 — One configuration surface.** Every Heima configuration, review and diagnostic lives in
  one Heima panel. The HA config flow is limited to the initial installation and, if ever added,
  very basic maintenance (for example a database export). Supersedes the 2026-08-31 split
  (config flow for linear settings, panel for registries); the reason is that composed-generation
  staging, impact preview and confirmation (Layer 0 §4.7) need one coherent editing surface.
- **L8-C2 — One panel, content by role.** A single panel serves administrators and residents. The
  role is resolved server-side for every request from the authenticated HA user (administrator:
  HA admin user; resident: HA user linked to a Layer-6 recipient or a `HouseholdConsentAuthority`
  actor); the UI only hides what the role cannot use, and every backend command enforces it.
- **L8-C3 — Navigation by user question.** Administrator: Overview, House, Devices,
  Understanding (Layer-4 resolvers), Automations, Learning, Notifications, System. Resident:
  Overview, To do (consent, recovery confirmations, advisories, including requests delivered
  without buttons), Automations (read-only, why they acted or not, own consents with revoke),
  Notifications (own history). A pending-changes bar in every configuration section leads to the
  impact preview; every object shows its state and its reason; one shared terminology.
- **L8-C3a — Native house map in the Overview.** Heima renders its own map, never a third-party
  card: (1) an automatic schematic from `Topology` (rooms laid out by connections, one tab per floor,
  exterior rooms distinct) with occupancy and presence, light and actuator state, opening state and
  active or blocked automations with their reason; (2) an optional real plan: the administrator
  uploads an image or SVG and places rooms (area or SVG element) and devices on it. Placement is
  Layer-8 presentation data, not Layer-1 `Topology`; rooms and devices stay Heima's own, so renames
  and removals propagate. Users who want `floorplan-card` in their own dashboards bind it to the
  HA entities Heima exposes (L8 decision on exposed entities); Heima neither bundles nor depends on it.
  (Revised by CA4-103: no uploaded plan in Initial V3; layout editing, up direction and map device
  control defined in Layer 8 §9.)
- **L8-C4 — Session change set, applied atomically.** Configuration edits (Layer 0 §4.7 mutations)
  accumulate in the administrator's browser session; a bar shows the pending count and errors, and
  "Review and apply" opens one preview: what changes (field-level diff), effects on the rest of the
  house (the Layer-0 impact record in plain language, breaking and semantic-only, with links) and
  blocking errors. Applying commits everything in one composed generation with the base generation
  and reviewed `impact_fingerprint`; if the active configuration changed meanwhile, the set is
  reapplied on the new base and the preview is shown again. Reason: multi-object changes (replacing
  a sensor, adding a room, changing an opening's exterior side) must not pass through intermediate
  states that invalidate dependents and drop their promotion and consent. The set is not persisted
  or shared; leaving the page warns before losing it. Each edit is validated immediately by the
  owning layer. Immediate actions (promotion, disablement, consent, proposal review, answers,
  finding acknowledgement) never enter the set and take effect at once after a confirmation dialog.
- **L8-C4a — One history timeline with restore.** System -> History shows one timeline built from
  existing durable records: configuration commits (Layer 0 manifests, retained indefinitely by
  CA4-78: who, when, field-level diff against the previous generation, confirmed effects),
  governance actions (Layer 5 authority, consent and proposal-review transitions) and system
  commits (bootstrap invalidations after a code upgrade); filters by section, object and person,
  and every object page shows its own slice. "Restore" never applies anything: it loads the diff
  from the current configuration to the chosen generation into the session change set (L8-C4),
  so the result is a new generation after the ordinary preview. It restores configuration only:
  a restored Reaction returns as a new generation in `notification_only` (Layer 5 never inherits
  promotion or consent), and learned artifacts, facts and history are untouched. Removed objects
  return with their original identity when it is free. The restored configuration is validated by
  the current core; anything no longer valid appears as a preview error. Partial restore: any entry
  of a restore change set can be removed before applying, and every object page offers "restore
  this version" for that object alone.
- **L8-C5 — Explainability.** (1) Every object (room, actuator, automation, notification) has a
  "Why?" panel with a readable causal chain: effect <- decision (Reaction, outcome, reasons) <-
  trigger <- semantic conclusion <- sensor readings, stitched by `correlation_id` and links. (2) A
  durable `reaction.decision` event per evaluation whose trigger fired (CA4-79) answers "why did it
  not act at that time"; when no decision exists, the trigger fact's own state history explains
  that nothing fired, and the thresholds and bindings come from the generation active at that time
  (CA4-78). Beyond fact retention the panel says the data is no longer available. (3)
  Administrators see the full chain with codes and links; residents see the same chain in plain
  language with the localized Layer-6 templates and no technical identifiers.
- **L8-C6 — HA entities published by Heima.** Distinct from the user's own HA entities that Heima
  reads (Sensors) and commands (Actuators) through Layer 2, which are unchanged. Heima publishes
  its own conclusions as new HA entities, created and removed automatically from its
  configuration, for dashboards, `floorplan-card`, user automations, history and logbook.
  (1) Read-only: no Heima `select`, `switch` or `number`; V2-style writable overrides are not
  carried over, behavior changes only through the panel or notification answers. (2) A closed small
  set: casa presence (`binary_sensor`, presence), occupancy per room (`binary_sensor`, occupancy),
  activity per room (`sensor` enum), each automation's state (`sensor` enum `automatic`/`trial`/
  `awaiting_consent`/`blocked`/`invalid` with a closed reason attribute; diagnostic category,
  disabled by default), pending items (`sensor`, proposals and open requests), Heima health
  (`sensor` enum). No per-person entities (HA `person.*` exists; V3 has no per-person state).
  (3) Stable unique ids from Heima ids, names from configuration, `unavailable` when the Heima
  fact is unavailable, closed attributes only, HA translations (it/en), entity removed with its
  object. (4) Entities are fed by Layer 0 committed-state observers whose subscriptions derive from
  the active generation and are re-declared at each generation swap (CA4-80); no polling.
- **L8-C7 — Languages and terminology, internationalized from the start.** No user-facing string in
  any language is hard-coded: panel, notification templates, HA entity names and states, and
  error messages use translation keys, with English as the source locale and per-locale resource
  files (Initial V3 ships `en` and `it`); a new country is a new resource file, not a code change.
  Missing keys fall back to `en`. Dates, numbers and units follow the viewer's locale and HA's unit
  system. One core glossary defines each canonical term once as a translation key (for example
  "automation", "trial" for `notification_only`, "block" for a suppression), shared by panel,
  templates, entities and user documentation. Internal concepts (generation, binding, envelope)
  never appear in the resident view and appear in the administrator view only with a glossary
  explanation. The panel follows the HA user's language.
- **L8-C8 — First start and V2 cutover.** The config flow only creates the integration. The panel
  then opens a guided first-start procedure: rooms, topology, devices, people and notifications,
  suggested automations. Each step is an ordinary session change set (L8-C4) with its preview;
  applied steps stay applied, and on return the procedure derives its progress from what is
  already configured (only the unapplied changes of the current step are lost). V2 cutover follows
  Layer 2 §1.1 unchanged: nothing is imported, and the panel never reads, displays or interprets a
  V2 export; the administrator may consult it outside Heima.
- **L8-C9 — Frontend technology.** The panel is a Lit web component (HA's own frontend base),
  registered as an HA custom panel, served by the integration with its build in the package; no
  external CDN; the V2 panel code is not reused.

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
5. **Guests — model approved 2026-10-19, spec pass in progress (CA4-118..125).** The approved people
   model, its decisions and the systematic sweep are in `docs/v3_people_model_draft.md`; the layer
   changes follow it in eight bounded issues. Original question (raised 2026-10-16 during CA4-113): Schedule: right after
   the Layer 8 completeness review, before any further guest-touching work. Initial V3 has no guest
   concept: Layer 4 §3 and Layer 3 explicitly defer a guest context, and Layer 8 offers guests only
   the map (CA4-113) with a card-level `control_rooms` scope that is not a security boundary.
   Questions to settle:
   - who a guest is: an HA account (companion app), a shared tablet without account, or both;
   - what a guest may do beyond seeing the map, and who grants it (administrator, or also a
     resident) — e.g. a per-HA-user control scope (Layer 8 §9.11);
   - time limits: access that ends with the stay, and who ends it;
   - enforcement: HA has only administrator/non-administrator, so any restriction on an HA account
     is presentational unless control goes through a backend check, which would conflict with the
     apply plan being Heima's only channel to HA;
   - guest presence as context: whether automations, learning and notifications should behave
     differently while guests are present (a guest context fact, its source and authority);
   - privacy: what guests see of residents (presence, automation reasons, history).

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
rule.** **Historical hold model — Superseded by CA4-01 (2026-09-29).** This restoration decision is retained only as historical rationale; the current Layer 0 §6 restores no hold. AR-3 (2026-09-01) and the Phase AQ non-goal it cites both state, unconditionally: an implicit
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

**Historical hold model — Superseded by CA4-01 (2026-09-29).** The following decision text is preserved as a historical record; Layer 0 §6 and the current CA4-01 decision govern Initial V3.

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

**Historical hold model — Superseded by CA4-01 (2026-09-29).** The following decision text is preserved as a historical record; Layer 0 §6 and the current CA4-01 decision govern Initial V3.

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

**Historical hold model — Superseded by CA4-01 (2026-09-29).** The following decision text is preserved as a historical record; Layer 0 §6 and the current CA4-01 decision govern Initial V3.

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

**Historical hold model — Superseded by CA4-01 (2026-09-29).** The following decision text is preserved as a historical record; Layer 0 §6 and the current CA4-01 decision govern Initial V3.

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

---

## Layer 3 ML extension and thermal-topology model, resolved architecturally (2026-09-13)

**Decision applied to Layer 3 and the recap**: `PatternLearner` remains Heima's permanent,
explainable statistical baseline. Layer 3 also explicitly permits bounded ML models when a declared
historical feature/target relationship cannot be represented adequately by bucketed categorical or
continuous statistics. ML training, validation, and artifact persistence are slow-path work only;
published artifacts are immutable and versioned with feature/target schema, source-generation
fingerprints, training coverage, validation metrics, and uncertainty. An invalid, stale,
incompatible, or incompletely covered model is unavailable rather than silently used. ML gains no
direct authority: it remains diagnostic or follows the ordinary analyzer -> proposal -> admin-review
path, and third-party models never gain a live-signal path.

The first concrete V3 ML candidate is a graph-constrained thermal-topology model. Layer 1 Topology
constrains which room/opening thermal-exchange terms are physically possible; Layer 2 provides the
temperature, outdoor-condition, HVAC-action, opening, and optional fan/air-quality facts; Layer 3
learns an effective thermal coupling and temperature trajectory; future Heating/Reaction layers may
evaluate the prediction against comfort, safety, and energy constraints. A minimum useful deployment
has indoor temperature per modeled zone, outdoor temperature, actual HVAC state, topology, and
exterior-opening state. Per-room temperatures and internal-opening states improve inter-room coupling;
CO2, humidity, fan/VMC state, occupancy, solar/illuminance, and energy measurements enable richer
ventilation and efficiency use cases. Without corresponding measurements Heima must not claim physical
airflow or indoor-air-quality prediction, and without adequate observed variation it must report a
parameter as unidentifiable rather than inventing a coefficient.

---

## Layer 3 historical sample binding, resolved architecturally (2026-09-13)

**Decision applied to Layer 3**: every learning sample has an explicit prediction-time anchor `T`.
Anchors are either historical intervals or declared transitions/events. Features are strictly causal:
an as-of state, a bounded aggregate over `[T - Window, T]`, or a finite ordered sequence from that
same past-only interval. Each feature declares fact type, Location, freshness, and whether it is
required; required unavailable/stale/incompletely retained data discards the sample, while optional
missing data needs an explicit model-defined representation. Cross-location input is always named,
never inferred.

Outcomes are explicitly one of point value at a horizon (including zero), event count/occurrence in a
future window, right-censored time-to-event, or absent for unsupervised anomaly/clustering/drift work.
Training may observe a later outcome, but never a feature newer than `T`; this prevents leakage into a
model intended to make a live prediction. Observational correlation is not permission to claim causal
action effect: counterfactual or reinforcement-learning use needs a separate contract.

---

## Cross-layer reread — Layer 5 closure backlog (2026-09-22)

**Status:** closed. All findings from the complete reread of the Layer 0--5 v3 specs and architecture
recap at commit `0063da4` are resolved below and promoted into their owning documents. The later
2026-09-23 scope amendment makes `environment.planned_comfort_trajectory` an evidence-gated
Initial-V3 descriptor rather than a future-only one; it remains dormant until its defined gates pass.

### Critical

#### L5-1 — `ReactionProposal` ontology, resolved (2026-09-22)

**Evidence.** The architecture recap describes a `ReactionProposal` as `HouseFact + Provenance`
wrapped with review status and an identity/fingerprint. Layer 1 explicitly says it is **not** a
`HouseFact`, but a Layer-5 review-workflow record with its own persistence contract. Layer 5 still
leaves its complete schema to define.

**Why it matters.** This decides its persistence identity, audit trail, provenance relationship,
deduplication, lifecycle transitions, and whether proposal evidence is a fact reference or embedded
fact-shaped data.

**Decision.** `ReactionProposal` is a persisted Layer-5 governance record, never a `HouseFact`.
It contains the admitted canonical proposal payload and its candidate/template contract identity;
references the source facts, result/artifact, finding and evidence span; and retains a bounded,
redacted immutable evidence snapshot sufficient to audit a later review even after normal evidence
retention or compatible retraining. The snapshot is an audit attachment, not a fact assertion. Review
status, actor and lifecycle belong exclusively to this record. Layer 3 keeps producing only transient
candidates; Layer 0/1 retain the actual house history and any separate operational audit facts.

**Consequence.** The recap was outdated and has been aligned. The exact record fields remain open;
the review state machine was subsequently resolved under `L5-5`.

**Sources.** `docs/v3_architecture_recap.md` (ReactionProposal section); Layer 1 "What is not a
HouseFact"; Layer 5 "Decisions still to refine".

#### L5-2 — `controlled_channel` registration, resolved (2026-09-22)

**Evidence.** Layer 0 requires an actuator's registered `controlled_channel` for
`actuator.resident_control`. Layer 3 carries it on `ActuationMemberCandidate`; Layer 5 uses it for
`CorrectionAttributionEvent` and matching. Layer 2's `Actuator` record has no such field and says
that `actuator_role` is not a capability model.

**Why it matters.** Resident control, correction attribution, learned actuation membership, and the
eventual `Actuator -> ApplyStep` binding do not have a common, registered semantic target.

**Decision.** `controlled_channel` is a stable, canonical identity unique within one Layer-2
`Actuator`, expressed by a finite `ActuatorChannel` collection. Each channel has a closed core
`channel_kind`, observable-state contract, and core actuation-adapter binding. An Actuator may own zero
channels, so unsupported or observation-only HA endpoints remain representable without becoming
automatically actuatable. Staging validates uniqueness and all closed contract references; composition
supplies Layer 0 a frozen ingress binding rather than creating a live Layer-0-to-Layer-2 lookup.

**Consequence.** Resident control, candidate membership, correction attribution, and later
`ApplyStep` mapping share one registered identity. Exact channel vocabulary and intent translation are
deferred to the remaining mapping decision.

### High

#### L5-3 — Semantic admission versus HA service validation, resolved (2026-09-22)

**Evidence.** Layer 2 rejects a Heima capability catalog and delegates service-schema/support
validation to HA. Layer 5 nevertheless requires compatible logical capability/admission, a member
capability vocabulary, and an exact `Actuator -> ApplyStep` mapping that remains open.

**Why it matters.** Without a boundary, two incompatible capability systems can emerge: a semantic
one for policy selection and a transport one for execution.

**Decision.** The closed channel-kind, observable-state-contract, and adapter registries are a narrow
Heima semantic admission vocabulary: they identify only control dimensions that core policy templates
can reason about and translate. They are not an inventory of HA domains, device classes, or supported
features. Layer 5 admits a member only when its template permits the registered channel kind and
adapter binding. It alone performs the later intent-to-`ApplyStep` translation; Home Assistant remains
the sole authority for the resulting service schema and current endpoint support when applying that
step. No HA feature snapshot or service-parameter schema is persisted in Layer 2.

**Consequence.** A new HA endpoint may be inventoried immediately but cannot enter automatic policy
execution until a core-owned channel contract exists. The exact intent/channel/adapter mapping remains
the separate Layer-5 mapping task.

#### L5-4 — Shared versioned `relation_profile`, resolved (2026-09-22)

**Evidence.** Layer 3 requires each environmental learner declaration to select exactly one
validated `relation_profile`, with support gates, shadow requirements, preview bindings, and
candidate payload. Layer 5 lists its schema as still to refine.

**Why it matters.** The learner cannot safely construct, validate, version, or explain a candidate
whose semantic relation is not normative.

**Decision.** `RelationProfileRegistry` is a core-owned, bootstrap-frozen Layer-5 registry exposed to
Layer 3 solely through its read-only proposal facet. A `RelationProfileRef(profile_id, version)` is one
shared artifact, never parallel learner/policy profiles. Its evidence facet defines the observed
relation, typed slots, outcomes/horizons/units, confounders, evidence gates and shadow requirement;
its policy facet defines permitted template versions, runtime slots, objective/intent compatibility,
guard structure and effect shape. Layer 3 consumes only the former; Layer 5 consumes the latter.

Profiles exclude admin guard values, Actuators, adapter mappings, HA services/payloads and arbitrary
expressions. `EnvironmentalGuardProfile` remains the separate administrative safety configuration, and
the intent/channel/adapter translation remains the subsequent Layer-5 mapping decision. The exact
profile ref is persisted in candidate, proposal and configured policy records; it is immutable and a
new version never silently alters a learner, pending proposal or policy.

**Consequence.** A changed evidence facet produces a new learner fingerprint/artifact/shadow path; a
changed policy facet produces a new candidate and review path. The existing environmental profile names
are profile ids whose exact version is now explicit.

#### L5-5 — Proposal review lifecycle, resolved (2026-09-22)

**Evidence.** Layer 5 specifies pending invalidation (`proposal_incompatible`), acceptance into a
`notification_only` configured policy, and a distinct auto-action promotion. Layer 3 may refresh
evidence but may not overwrite status/mode/scope/guard. The record schema and transition rules are
still open.

**Why it matters.** UI, notifications, idempotency, ownership, audit, retry, stale evidence, and
deduplication cannot align without explicit states, actors, and transition guards.

**Decision.** The sole review dispositions are `pending`, `accepted`, `rejected`, and
`proposal_incompatible`. The latter three are terminal. Only a compatible Layer-3 refresh may update
a `pending` proposal's evidence references and bounded redacted audit snapshot; it cannot alter the
canonical admitted payload or any review/configuration authority. Evidence outside its validity
interval makes the proposal temporarily non-approvable but keeps it `pending` awaiting refresh, rather
than introducing an expiry disposition.

Acceptance is an authenticated, atomic Layer-5 transaction: current revalidation, creation of the
linked `ConfiguredPolicy` in `notification_only`, then recording actor/time/reason/policy identity and
transition to `accepted`. A recoverable current staging failure leaves it pending with a typed
diagnostic; candidate-kind/version incompatibility reaches terminal `proposal_incompatible`.
Rejection records actor/time/typed reason and is terminal. A candidate with the same canonical
fingerprint cannot automatically reopen a rejected proposal; changed semantics yield a new fingerprint
and a new proposal. There is no in-place reopen transition. The configured policy's later lifecycle,
including automatic-action promotion, is separate and never rewrites the accepted proposal.

**Consequence.** Layer 5 defines the review state machine; its exact immutable root and append-only
record layout are resolved separately in `L5-15`.

#### L5-15 — `ReactionProposal` persisted schema, resolved (2026-09-23)

**Decision.** The immutable `ReactionProposal` root contains only its identity, admitted candidate and
descriptor/profile identities, canonical admitted payload, deduplication fingerprint, admission time,
and first evidence-revision id. It has no mutable review fields, raw HA object, or executable command.

Three append-only record types supply the workflow history: `ProposalEvidenceRevision` for compatible
evidence refreshes; `ProposalReviewTransition` for actual terminal moves from `pending`; and
`ProposalReadinessAssessment` for stale evidence or a failed current revalidation that leaves the
proposal pending. Current disposition and evidence are deterministic projections rather than opaque
mutable columns. Every evidence revision binds the original admitted-payload fingerprint; a mismatch is
a new candidate, never a refresh. Snapshots and diagnostic detail are individually bounded and redacted.

**Consequence.** Acceptance atomically creates `ConfiguredReaction` and appends the accepted
transition. Rejection and terminal incompatibility each append their own transition. Failed acceptance
or expiry remains an auditable readiness assessment without inventing a lifecycle state.

#### L5-6 — One Reaction execution pipeline, resolved (2026-09-22)

**Evidence.** Layer 3 distinguishes deterministic direct typed ECA Reactions from generic
action-bearing policy templates that a learner may propose. Layer 5 mainly defines
`PolicyTemplateRegistry` and leaves the general non-policy Reaction contract open.

**Why it matters.** A policy accepted from a proposal could accidentally bypass or duplicate the
same admission, guard, apply, and audit pipeline used by deterministic Reactions.

**Decision.** A core `ReactionDescriptor` is the sole contract from which a `ConfiguredReaction` may
be staged. It declares one or both authoring modes: `admin_direct` and `learner_proposal`. An admin may
create a typed deterministic ECA Reaction only through `admin_direct` staging; Layer 3 may create only
a `ReactionDescriptorCandidate` under `learner_proposal`, followed by proposal review. Both origins
then use the same descriptor validators, `ReactionEvaluationPlan`, immutable `DecisionSnapshot`, action
admissibility, ordered one-endpoint `ApplyStep` protocol, and audit path. The immutable origin is
provenance only, never a runtime engine selector.

**Consequence.** `ReactionProposal` is governance for learned configuration, not a third runtime
shape. A descriptor may deliberately be direct-only, proposal-only, or support both; neither authoring
path may install an arbitrary predicate or command graph. The exact intent/channel/adapter translation
is defined in `L5-13` and has one execution destination.

#### L5-13 — Semantic target to `ApplyStep` mapping, resolved (2026-09-23)

**Evidence.** `L5-2/3` now establish registered `ActuatorChannel`, closed `channel_kind`, and a core
adapter binding, while Layer 5 still explicitly leaves the exact semantic-intent to
channel-kind/adapter to `ApplyStep` translation open.

**Why it matters.** The system has a safe admission boundary but not yet a complete, testable command
contract: the same intent must not translate differently for equivalent channels, and no template may
bypass the one-endpoint, HA-validated `ApplyStep` path.

**Decision.** A closed core translation table is indexed by `(action_intent, channel_kind,
actuation_adapter_id)`. It validates semantic parameters, builds one typed `ChannelTarget`, constructs
its partial expected-state matcher, and encodes a finite ordered sequence of `ApplyCall`s. The target is
a canonical patch: explicitly targeted facets are verified and attributable; omitted facets preserve
current state and receive no implicit default. A light may therefore target power, intensity and colour
in one `light_state`; a valve may target a canonical position; an HVAC state may target mode, setpoint,
fan speed and swing mode.

One `ApplyStep` owns exactly one Actuator/channel semantic target, but may contain multiple one-service
`ApplyCall`s when HA requires separate services. Calls contain no target selector; runtime resolves the
sole entity from the Actuator. They are audited individually as `completed`, `failed`, or
`not_attempted`. A failed call stops remaining calls and later bundle members; a step succeeds only when
all calls complete. There is no automatic compensation and no arbitrary command graph.

**Consequence.** The member-to-step invariant remains one-to-one while preserving composite user
intent. Home Assistant still authoritatively validates each concrete service operation; Layer 2 stores
only the core semantic channel/adapter contract, never an HA feature snapshot.

### Medium

#### L5-7 — Architecture overview stale Layer-4 status, resolved (2026-09-23)

**Decision.** The overview no longer presents initial Layer-4 semantic resolvers as deferred. It now
states that Layers 0--5 are defined and confines the deferred section to genuinely future ownership,
including `security.presence_simulation`; `environment.planned_comfort_trajectory` is instead an
evidence-gated Initial-V3 descriptor.

**Consequence.** The overview remains a maintained explanatory map; it neither reopens settled Layer-4
scope nor turns reserved product directions into initial V3 obligations, while showing the comfort
trajectory's defined Initial-V3 implementation obligation accurately.

#### L5-8 — `relation_profile` terminology, resolved (2026-09-22)

**Evidence.** Layer 3 uses it for learner environmental relations; Layer 5 uses it in policy
template slots.

**Why it matters.** A shared spelling suggests interchangeability even if the artifacts have
different owners, validation, and lifecycles.

**Decision.** The shared `RelationProfileRef` deliberately denotes one versioned artifact with
evidence and policy facets. The term is no longer overloaded: Layer 3 references the evidence facet;
Layer 5 references the policy facet. Candidate contracts use the typed ref, rather than an unversioned
string whose meaning could be inferred from its consumer.

#### L5-9 — Action-side availability reason ownership, resolved (2026-09-23)

**Decision.** `ReactionDescriptor` declares only applicable gates from a closed core table: manual
hold -> `manual_hold_active`; command ownership -> `command_ownership_unavailable`; absent or
incompatible channel/target contract/adapter -> `actuator_capability_unavailable`; unavailable or
unverifiable channel state -> `actuator_state_unconfirmed`; dwell/cooldown -> `cooldown_active`; and
any required guard -> `action_guard_active`. Layer 5 canonicalizes concurrent causes through Layer 3's
existing helper and cannot add, rename, suppress, or prioritize reason codes.

Semantic input, artifact and envelope failures remain pre-admission Layer-3 causes. Staging/review
incompatibility is a typed configuration diagnostic, not a runtime availability occurrence. Once an
action has been admitted, a failed `ApplyCall` is recorded through Layer 5's separate closed execution
audit taxonomy (`service_rejected`, `transport_failed`, `timeout`, `invalid_response`) and never emits
`automation.availability`.

#### L5-10 — Candidate validation authority, resolved (2026-09-23)

**Decision.** Layer 3's read-only proposal facet is advisory preflight only: it may reject a candidate
that is incompatible with the generation it observed, but it neither reserves that generation nor
authorizes persistence, review, or action. A successful preflight result cannot be cached as an
authorization.

Layer 5 is authoritative both when it creates the `ReactionProposal` and when an authenticated actor
accepts it. At each boundary it validates the then-current descriptor/profile versions, canonical
payload/fingerprint, Topology, Actuator inventory, guards and staging configuration. A changed or
incompatible dependency follows Layer 5's typed rejection, pending non-approvability, or terminal
`proposal_incompatible` rule; Layer 3 never silently reinterprets the candidate.

### Low

#### L5-11 — Recap authority and maintenance, resolved (2026-09-23)

**Decision.** The recap and overview are manually maintained orientation documents. Both identify the
authoritative Layer 0--5 specifications as prevailing on any discrepancy, carry a reviewed-through
date, and are updated when confirmed decisions are promoted into a specification. They summarize
ownership and stable contracts, rather than duplicating complete schemas or lifecycle tables.

**Consequence.** The recap now reflects the one `ReactionDescriptor` mechanism, Layer-5 authority over
candidate persistence/review, `ConfiguredReaction`, pre-admission suppression versus execution audit,
and the distinction between active/evidence-gated Initial-V3 and reserved future descriptors.

#### L5-12 — Initial versus reserved-future descriptors, resolved (2026-09-23)

**Original decision (superseded in part on 2026-09-23).** Layer 5 separated active Initial V3
descriptors from a non-normative reserved-future section. The active registry included
`environment.solar_shading`, `environment.external_exchange`, `environment.bathroom_extract`, and
`routine.actuation_bundle`; both `environment.planned_comfort_trajectory` and
`security.presence_simulation` were initially reserved.
The `environment.bathroom_extract` name in this dated decision is historical;
CA4-12 renamed the current Initial-V3 descriptor to `environment.air_extraction`.

**Consequence.** A reserved descriptor can be promoted only through a future core change that defines
its complete owner contracts and acceptance criteria while retaining the one common descriptor/runtime
mechanism. The Layer-0 calendar substrate and `FrozenCalendarView` are already defined and are not a
promotion blocker.

**Scope amendment (2026-09-23).** `environment.planned_comfort_trajectory` is no longer reserved.
It is an Initial-V3 registered descriptor with a stable identifier, evidence-gated `learner_proposal`
path, and Initial-V3 acceptance obligation. It remains dormant, emits neither proposal nor action, and
has no fallback until compatible thermal evidence plus staged HVAC/calendar/comfort prerequisites pass.
`security.presence_simulation` alone remains reserved-future under the preceding consequence.

#### L5-14 — `planned_comfort_trajectory` promotion contract, resolved (2026-09-23)

**Status amendment (2026-09-23):** the contract is complete and
`environment.planned_comfort_trajectory` is a registered, evidence-gated Initial-V3 descriptor. Its
stable identity may be relied upon, but it is dormant for a scope until eligible exact-cell evidence
and its staged prerequisites exist. No future feature development is required when data later becomes
sufficient; the existing candidate, review, shadow and promotion lifecycle applies.

**Contract.**

- **Thermal-response artifact and relation profile (Layers 3 and 5), resolved (2026-09-23):** one
  explicit conditioning scope and one mode (`heating` or `cooling`) produce a bounded, exact-context
  `ThermalResponseParameter`: passive-drift interval, recovery-duration interval and conservative
  recovery time for one thermal-delta bucket. It is derived from separate complete passive-drift and
  active-response cohorts, is shadow-validated against later observed trajectories, and cannot contain
  a target, calendar, command, entity, arrival forecast or unmeasured energy-benefit claim. Layer 5
  uses it only to decide the latest start that conservatively reaches the explicit target by the
  calendar boundary, under its independent bounds and guards;
  missing/expired/non-matching context abstains without fallback or extrapolation.
- **HVAC semantic target contract (Layers 2 and 5), resolved (2026-09-23):** one
  `HvacTrajectoryBinding` declares a unique registered endpoint per heating/cooling mode; the same
  channel may serve both only when its adapter admits each explicit binding. The closed
  `hvac_state.trajectory_setpoint.v1` target contains exactly `mode` (`heating` or `cooling`) and
  `setpoint_c`. `auto`, power, fan speed, swing, preset and humidity are excluded. Layer 5 admits a
  step only with compatible channel/adapter, confirmed current state and an administratively bounded
  setpoint; the Layer-5 translation table alone compiles the resulting target into HA-validated calls.
- **Comfort, safety and consent contract (Layer 5), resolved (2026-09-23):** an administrator stages
  one `ComfortTrajectoryGuardProfile` per conditioning scope. Its heating/cooling absence and return
  targets are each an absolute or current-`FactRef` relative `ThermalBoundRule`, always clamped within
  explicit hard bounds; missing/stale reference means no step, never a fallback. The profile is never
  learned. It permits a direct absence target and a core-generated recovery-only ramp; adapter
  constraints, not admin settings, govern every recovery-knot granularity and cadence. Administrative
  action enablement and household consent are
  separate mandatory gates for automatic action, initially disabled; they do not block proposal or
  notification-only shadow. Revocation while automatic, or any hold/plan/presence/guard failure,
  cancels the corresponding future action work without compensating a command already sent. Layer 5 schedules a future
  re-evaluation, not a frozen command, and may record `late_recovery` only when it safely selects the
  next recovery knot after its calculated start is already past.
- **Descriptor lifecycle gates (Layers 3--5), resolved (2026-09-23):** complete/coherent artifact
  cohorts, exact-context coverage, calibrated intervals and thermal shadow plus atomic cross-layer
  staging admit a reviewable candidate. Acceptance creates only a `notification_only` configured
  Reaction, which completes a bounded operational shadow without `ApplyStep`s while exercising plans,
  dynamic bounds, rescheduling and cancellation. Only a subsequent authenticated administrative
  promotion plus current household consent may enable automatic action.
  End-to-end tests cover departure, targets, recovery timing, edits/cancellations, early return, hold,
  safety, revocation, restart, `late_recovery`, and no compensation of a sent call.

**Already defined, therefore not open here.** Calendar extraction, normalization, bounded staged
requirements, `FrozenCalendarView`, Layer-2 keyword classification, `CalendarPlanBinding`, ambiguity,
and the distinction between an explicit plan and `presence=away` are existing Layer-0/2/5 contracts.

---

## Cross-layer coherence audit follow-up (2026-09-23)

**Status:** closed (2026-09-23). Findings from a read-only re-review of the current Layer 0--5
specifications, architecture overview, diagrams, and recap after the Layer-5 closure work are resolved
below and promoted into their owning documents. The separate CT readiness follow-up remains open as
implementation-detail work, not an unresolved cross-layer contradiction.

### Critical

#### CA-1 — Plugin action authority and the sole Layer-5 path (resolved 2026-09-23)

**Evidence.** The recap's Layer-7 section allows an `apply` plugin to return an `ApplyStep` and command
Actuators, while Layer 5 says `ReactionDescriptorRegistry` is not plugin-extensible and is the sole
contract from which `ConfiguredReaction` and its common action protocol may be staged.

**Why it matters.** A plugin-owned apply path can bypass descriptor staging, current snapshot,
admissibility, suppression, audit and correction-attribution rules, recreating the parallel action
engine V3 explicitly prohibits.

**Decision.** Plugins have no `apply` capability and cannot create `ApplyStep`s, invoke Actuators,
register candidate kinds/descriptors, or establish a private action protocol. They may provide
registered ordinary facts and diagnostics. A plugin may submit a `LearningProposalCandidate` only
under an exact existing core candidate kind and `ReactionDescriptor`; normal Layer-5 validation,
review, staging, admissibility, and audit then decide whether it can ever produce an action.

**Consequence.** A plugin-owned Actuator remains a Layer-2 inventory entry and is commandable only by
the common core Layer-5 pipeline. Plugin-related `ApplyStepSource` data is provenance, not authority.
This supersedes the historical two-capability-tier (`read_only`/`apply`) proposal in the older
`Third-party plugin API` backlog notes; the recap, overview, and Layers 3/5 now state the closed
boundary consistently.

### High

#### CA-2 — One canonical `ReactionDescriptor` identity (resolved 2026-09-23)

**Evidence.** `ReactionDescriptorCandidate` carried `reaction_descriptor_id` and version, while its
embedded `CanonicalEnvelope` also carried `template_id`, `template_version`, and string `profile`.
That exposed two unaliased identities for one logical configuration.

**Why it matters.** Candidate construction, fingerprinting and Layer-5 validation can bind different
identities to one logical configuration, defeating exact-version revalidation and deduplication.

**Decision.** The candidate root is the sole identity owner:
`reaction_descriptor_id`, `reaction_descriptor_version`, and `RelationProfileRef`. `CanonicalEnvelope`
is now only its finite axes, versioned partitions, and supported cells; it carries no descriptor or
profile identity. Layer 5 validates that envelope as part of the root-selected descriptor/profile
contract. Candidate fingerprints include the root identities once and then the canonical envelope value.

**Consequence.** There is no template-to-descriptor alias or double identity to reconcile. Candidate,
proposal, and `ConfiguredReaction` references use descriptor id/version and `RelationProfileRef`.
The associated Layer 0--2 boundaries, overview, governance diagram, and recap now use
`ReactionDescriptor` terminology when they mean this contract; independent Layer-4 semantic templates
and Layer-6 notification templates retain their own meaning.

#### CA-3 — Comfort trajectory is evidence-gated, not a future undefined feature (resolved 2026-09-23)

**Evidence.** Layer 3's future-component items for `planned_comfort_trajectory` and
`hvac_thermal_response` still require Layer-5 mapping, comfort/safety/consent and acceptance contracts
to be completed, although `L5-14` now defines them.

**Why it matters.** Treating the profile/descriptor as a future release item would mean a household
with sufficient later data still needs new product development before Heima can propose its use. That
contradicts the Initial-V3 capability decision and obscures the difference between a defined dormant
contract and missing empirical/configuration prerequisites.

**Decision.** `hvac_thermal_response` and `environment.planned_comfort_trajectory` are registered
Initial-V3, evidence-gated capabilities. Their complete cross-layer contracts are already specified;
the remaining gates are exact-context calibrated thermal evidence, staged HVAC/calendar/comfort
prerequisites, reviewable candidate validation, `notification_only` shadow, authenticated promotion,
and current household consent. Layer 3 supplies only `ThermalResponseParameter`; it never chooses a
target/endpoint, schedules recovery, or commands an Actuator.

**Consequence.** When a household later accumulates sufficient data and the administrator has staged
the required configuration, Heima can create the ordinary proposal without a new descriptor, contract,
or feature implementation. `security.presence_simulation` remains the separately reserved future
descriptor.

### Comfort-trajectory implementation readiness follow-up (2026-09-23)

**Status:** implementation-gated. CT-1, CT-2, CT-3, CT-5 and CT-6 are resolved as specification
contracts. CT-4's contract is also resolved, but its frozen numerical calibration and reproducible
release evidence must be completed before the capability can be released for automatic action. No new
feature design should be required when a household later accumulates sufficient data.

#### CT-1 — Concrete descriptor and evaluation-plan contract (resolved 2026-09-24)

Define the registered `environment.planned_comfort_trajectory` payload, trigger, current guards,
canonical parameters, action bundle shape, and exact `ReactionEvaluationPlan` behavior for absence,
recovery, rescheduling, and cancellation.

**Decision recorded.** Absence is one direct semantic target at observed departure. Recovery is a
core-generated adaptive ramp only: heating steps upward and cooling steps downward toward the return
target. Its sole semantic trigger is `departure`; calendar/dependency changes and one next `AtJob`
cause fresh re-evaluation, not a second trigger or prebuilt command schedule. Every knot reads a fresh
snapshot, emits at most one supported `ApplyStep`, and arms at most one successor job. Late operation
never replays missed knots, bursts calls, violates adapter limits, or jumps to the return target; it
continues only with the next safe step and records `late_recovery`.

**Scope decision (2026-09-23).** A trajectory uses one explicit `ConditioningScope`, shared by its
artifact, HVAC binding, guard profile, and configured Reaction. Initial V3 permits only one `room` or
`casa`; casa requires one administrator-staged canonical temperature `FactRef` and never averages or
infers from room sensors. `zone` and ad-hoc multi-room scopes are rejected until a future contract can
model their heterogeneous thermal dynamics.

**Closure (2026-09-24).** CT-2 fixes the immutable prerequisites, CT-3 fixes candidate identity and
payload, and CT-6 makes each evaluation rule executable. No unresolved descriptor or evaluation-plan
behavior remains.

#### CT-2 — Staged prerequisite aggregate and candidate binding (resolved 2026-09-23)

**Decision.** `ConditioningScope`, `HvacTrajectoryBinding`, `ComfortTrajectoryGuardProfile`, and the
`planned_absence` `CalendarPlanBinding` are staged only as one immutable, append-only
`ComfortTrajectoryPrerequisiteGeneration`, with a contiguous per-scope generation index, complete
canonical fingerprint, authenticated author and timestamp. Cross-contract scope, endpoint, fact,
bound, guard and adapter-constraint validation is atomic: a failed staging request persists no partial
generation.

**Binding and authority.** A candidate, its proposal and its configured Reaction retain the exact
generation id/fingerprint. The learner may bind only an eligible exact-cell thermal artifact; it cannot
choose or mutate any staged administrative value. Consent and administrative action enablement are
current runtime authority, initially disabled on the configured Reaction, and are required only for
automatic `ApplyStep`s, never to propose, review or conduct notification-only shadow.

**Change behavior.** An edit creates a new generation. Pending proposals on an old generation become
`not_approvable` with `staged_prerequisite_incompatible`; a previously automatic reaction cancels future
action jobs and becomes `notification_only`. Nothing is reinterpreted under the new generation: a new
candidate, review, shadow and authenticated promotion are required before automatic action resumes.

#### CT-3 — Thermal artifact to proposal translation (resolved 2026-09-23)

**Decision.** One eligible exact-cell `ThermalResponseParameter` produces one candidate for exactly one
`(conditioning_scope, mode)`, with a single `follow_comfort_trajectory` member bound to the staged
endpoint. The root payload carries only the immutable prerequisite-generation id/fingerprint; member
parameters carry only the selected mode and the member has
`numeric_outcome_requirement=None`. The parameter's step bucket is an action
bound and its recovery-duration estimate remains typed artifact evidence;
neither is copied into immutable member fields. Guards and envelope must
exactly agree with the generation and artifact. This field-placement correction
was made under CA4-12 on 2026-10-07.

**Identity and refresh.** The prerequisite pair, mode, step bucket and envelope are semantic identity
and enter deduplication, so any such change needs a new proposal. Artifact/parameter identity, evidence
references, validity, confidence and uncertainty stay in the evidence revision. They may refresh a
pending proposal only while all semantic fields remain compatible. No learned payload may contain a
comfort bound/target, calendar plan, endpoint mapping, adapter constraint, consent, absolute setpoint,
arrival prediction or command schedule.

#### CT-4 — Initial thermal evidence gates and recovery-step evidence (implementation-gated 2026-09-23)

**Decision.** Initial-V3 threshold values will not be invented in the specification or made
administrator-configurable. A core-owned, versioned `ThermalEvidenceGateCalibration` must be frozen
from a documented BOPTEST matrix, provenance-recorded replay fixtures, and a documented opt-in field
pilot before `hvac_thermal_response@1` can publish an operational artifact. It records support and
temporal-diversity floors for passive and active cohorts, bootstrap quality, response-interval width,
per-horizon trajectory error, interval coverage, independent thermal-shadow episodes, and the maximum
conservative-recovery underprediction rate.

**Exact-bucket rule.** Passive support is qualified per cell/delta cohort; active support and thermal
shadow are qualified per exact cell/delta/recovery-step bucket. No bucket borrows evidence, a threshold
result or a neighbouring parameter. The calibration matrix must exercise supported modes, context/delta/
step partitions, forecast/sensor uncertainty, thermal-mass regimes and actuator responses.

**Implementation gate.** The contract is defined, but concrete frozen values and their reproducible
calibration evidence remain a release-acceptance obligation. Until they exist, the profile is
diagnostic-only and cannot emit a candidate. A changed gate/protocol/fixture/metric is a new
profile-calibration version and never silently changes a pending proposal or configured Reaction.
The field pilot is `notification_only`, requires per-household opt-in, exports only protocol-bounded
redacted aggregate outcomes, and never supplies cross-home runtime data or action authority.

#### CT-5 — Staging and administration surface (resolved; amended 2026-09-24)

**Decision.** The comfort trajectory belongs entirely to the admin panel, not config flow. Layer 8
authenticates/authorizes and renders bounded redacted state; Layer 5 owns validation and every durable
mutation. A typed, version-checked aggregate staging command is the only way to create a prerequisite
generation. Generic `review_proposal` accepts/rejects the learner proposal and acceptance creates only
`notification_only`; no direct reaction creation exists.

**Authority.** An admin may promote or disable automatic action against an exact configuration
generation. Promotion may leave the reaction `authorized_awaiting_household_consent`; it never emits a
command. An explicitly resident-authorized actor, not an admin actor by role alone, separately grants
or revokes household consent for that exact reaction/generation. Revocation cancels future jobs;
successors never inherit consent. Removing a resident authority is version-checked and requires the
admin to explicitly retain or revoke every current consent that removed actor granted; retention is
audited as an admin decision over the resident's pre-existing consent, never as a new admin grant. All
commands carry actor, correlation, target identity and optimistic-concurrency precondition, and failures
persist no partial mutation.

**Visibility.** Shadow is read-only and redacted: generation/artifact/profile identity, readiness,
summarized targets/knots, suppressions, cancellations and `late_recovery` are visible; calendar text,
raw facts, raw HA payloads and unredacted artifacts are not.

#### CT-6 — Executable acceptance scenarios (resolved 2026-09-24)

**Decision.** Comfort trajectory requirements are versioned `Given / When / Then` executable fixtures,
not illustrative prose. They assert an observable trace only: durable records, exact job
replacement/cancellation, `ApplyStep`/`ApplyCall`, and typed diagnostics/audit. A deterministic suite
uses fake clock/calendar/facts/adapter/scheduler and covers candidate/governance identity, direct
absence, adaptive heating/cooling knots, edits/cancellations, safety interruptions, restart,
`late_recovery`, no compensation, shadow, promotion, consent and resident-authority removal with
retain/revoke disposition.

**Separation.** BOPTEST, replay and opt-in field-pilot analysis remain a distinct release-calibration
suite for `ThermalEvidenceGateCalibration`; they establish the frozen model gates and do not replace
ordinary deterministic regression acceptance.

**Dependency.** CA-4 is a direct safety prerequisite because every dynamic thermal bound must be
strictly current-snapshot based. CA-5 and CA-6 are generic governance/persistence work and may proceed
independently, though their resulting contracts will be consumed by CT-2/CT-3.

### Medium

#### CA-4 — Dynamic thermal bounds are strictly current-snapshot based (resolved 2026-09-23)

**Evidence.** `ThermalBoundRule` says its reference must be current, but it uses Layer 2's `FactRef`,
whose `previous_cycle` flag is part of its public shape. The Layer-5 staging rules do not explicitly
require `previous_cycle=False`.

**Why it matters.** A stale outside-temperature bound could produce a valid-looking but obsolete HVAC
target despite the stated current-snapshot safety model.

**Decision.** Every `ThermalBoundRule(kind="relative_to_fact")` requires
`reference.previous_cycle=False`. Staging rejects `True`, including the otherwise legal Layer-2
FormulaStrategy self-memory form. The reference must also be a descriptor/profile-declared current
runtime slot with compatible temperature unit.

**Consequence.** Resolution reads only the current immutable `DecisionSnapshot`. A missing, stale,
invalid, unavailable, or non-temperature current value leaves the rule unresolved and prevents the
step; no previous-cycle, prior-value, default, expression, or HA fallback is permitted.

#### CA-5 — Layer-5 governance and execution diagnostics are closed (resolved 2026-09-23)

**Evidence.** `ProposalReviewTransition.reason_code` and
`ProposalReadinessAssessment.reason_codes` are `str` values described as closed typed diagnostics, but
no Layer-5 registry/enum, ownership, versioning or canonicalization rule exists. `late_recovery` is
also introduced only as prose audit text.

**Why it matters.** Implementations can mint incompatible strings, fragment UI/audit behaviour, and
silently weaken the closed-vocabulary rule used everywhere else.

**Decision.** A core-owned, bootstrap-frozen, versioned `Layer5DiagnosticRegistry` owns separate
closed namespaces: proposal transition reasons (`accepted_by_admin`, `rejected_by_admin`,
`candidate_kind_incompatible`), proposal readiness reasons (expired evidence and descriptor/profile/
topology/Actuator/guard/staged-prerequisite incompatibility), ordinary evaluation reasons
(`trigger_not_matched`, `semantic_guard_unsatisfied`), and execution audit
(`late_recovery`). Proposal readiness tuples are duplicate-free and canonicalized by the registry;
transition codes are constrained to their legal dispositions.

**Consequence.** `ApplyCallFailureReason` remains its separate existing closed execution-failure
taxonomy, and Layer-3 `AutomationSuppressionReason` remains the sole reason tuple for an abstained
evaluation. `ReactionEvaluationResult` no longer permits arbitrary strings. Detail remains bounded
and redacted, never a source of new code semantics.

#### CA-6 — `ReactionProposal` creation and evidence revisions are atomic (resolved 2026-09-23)

**Evidence.** The immutable root requires `initial_evidence_revision_id`, but the schema does not state
that creation atomically appends revision index `0`, that revision ids are unique/contiguous per
proposal, or that no proposal projection may exist without its initial evidence revision.

**Why it matters.** A partial write makes the proposal non-reviewable and undermines the audit identity
the aggregate design was introduced to protect.

**Decision.** Proposal creation is one idempotent aggregate transaction: it persists the immutable
root and exactly one initial evidence revision together, or persists neither. Revision zero must carry
the root's proposal id, `initial_evidence_revision_id`, and admitted-payload fingerprint. No projection,
transition, readiness assessment, or review may observe/reference a root before that revision commits.

Evidence revisions are immutable and append-only with unique contiguous per-proposal indexes `0..n`; a
compatible refresh appends only `n + 1` and keeps the same admitted-payload fingerprint. A repeated
creation attempt returns the complete existing aggregate, never a second root or index-zero revision.
Transition/readiness records can reference only a committed revision belonging to their proposal.

**Consequence.** The storage technology remains open, but it must provide the stated crash-safe
atomicity, ordering, uniqueness, and retry-idempotency behavior. A changed payload remains a new
candidate/proposal rather than a revision refresh.

---

## Post-CT cross-spec coherence audit (2026-09-24) — resolved findings

**Status:** resolved as specification findings. This line-by-line reread of the authoritative Layer
0–5 specifications, architecture overview and recap after CT-1–6 retains the decision history;
the current layer specifications own the normative contracts.

### Critical

#### RC-1 — `ConfiguredReaction` and `ReactionEvaluationPlan` have no persisted contract (resolved 2026-09-24)

**Decision.** `ConfiguredReaction` is a stable Layer-5 policy aggregate with immutable append-only
`ReactionConfigurationGeneration`s. Every generation persists the exact descriptor/profile identities,
subject, descriptor-validated canonical configuration and a canonical callable-free
`ReactionEvaluationPlan`; its fingerprint is the semantic identity for evaluation, jobs, actions and
audit. Root creation atomically creates generation zero; edits append a contiguous successor and never
rewrite prior meaning.

**Authority separation.** Administrative enablement and resident consent are append-only
`ReactionAuthorityTransition`s, not configuration fields. Each configuration successor begins
`notification_only` with automatic authority and consent disabled; its effective mode is derived as
`notification_only`, `authorized_awaiting_household_consent`, or `automatic`. It cancels predecessor
jobs and requires fresh authenticated promotion/evaluation.

**Consequence.** Evaluation/bundle idempotency is
`(reaction_id, configuration_generation_id, snapshot_id)`. `AtJob`, evaluation result, `ApplyStep`,
execution audit and correction attribution retain the exact configuration generation, preventing stale
callbacks, retries or audit from crossing a semantic edit. Direct and learner-proposal origins now use
the same configuration, authority and action path.

### High

#### RC-2 — Generic environmental guard contract is missing and its cited decision does not exist (resolved 2026-09-24)

**Decision.** `EnvironmentalGuardCapabilityRegistry` is assembled only from reviewed core capability
implementations at bootstrap, then versioned and frozen for the active generation. It replaces the
prose/string capability vocabulary without becoming a global hard-coded enum: every entry owns a typed
binding schema, pure current-snapshot evaluator and redaction contract. Admins, learners and plugins
cannot register entries, evaluators or free expressions.

**Profile contract.** An append-only `EnvironmentalGuardProfileGeneration` contains one validated
canonical binding per required capability. A relation profile's exact `EnvironmentalGuardContractRef`
defines permitted entries and the required subset per intent. Candidate and descriptor references are
versioned capability refs only; they cannot carry thresholds. A reaction plan pins the exact profile
generation/fingerprint and required refs. Changing a binding creates a new profile generation and thus
requires a new `ReactionConfigurationGeneration`, fresh promotion and evaluation.

**Consequence.** Every required guard is evaluated only against the immutable `DecisionSnapshot`.
Missing, stale, invalid, unconfirmed or failing input blocks automatic action through the existing
`action_guard_active` reason; no fallback or new notification reason is introduced. The comfort
trajectory pins the same environmental guard-profile generation beside its thermal bounds, so HVAC,
openings, extraction and shading share one guard mechanism.

#### RC-3 — Initial environmental shadow-preview identifier is internally inconsistent (resolved 2026-09-24)

**Decision.** The single canonical schema identity is
`shadow_proposal_preview.reaction_descriptor.environmental.v1`, matching the frozen
`ShadowPreviewBinding` and its `reaction.descriptor@1` candidate contract. The acceptance criteria use
that same exact identity.

**Consequence.** `policy_template` is retired terminology, not an alias or migration path. V3's clean
start rejects it rather than selecting a similarly named preview schema.

### Medium

#### RC-4 — Layer 3 attributes automatic action to a `ReactionProposal` (resolved 2026-09-24)

**Decision.** An `EnvironmentalGuardProfile` complete against the descriptor's guard contract permits
Layer 5 to admit an environmental `ReactionProposal` for review. It never makes the proposal
automatically applicable. Acceptance creates only a `notification_only` `ConfiguredReaction`; automatic
actuation belongs exclusively to that reaction after its separate authenticated promotion and any
required current household consent.

**Consequence.** Layer 3 §4.8.4 now names the correct lifecycle subject while retaining the existing
rule that explicit configured guard limits are evaluated against current facts and resolved semantic
claims for every proposed execution.

#### RC-5 — Calendar-conflict ownership points to Layer 4, which is forbidden to interpret calendars (resolved 2026-09-24)

**Decision.** Layer 0 only extracts and freezes raw per-entity calendar windows; Layer 4 only
transports `FrozenCalendarView` and never interprets it. `CalendarPlanBinding` is the sole V3
predictive-plan consumer: it names a non-empty canonical set of single-entity Layer-0 requirements and
one shared Layer-2 classifier. All sources must be ready. For Initial-V3 `planned_absence`, matching
intervals form a source-neutral union: duplicates collapse and overlapping/adjacent intervals coalesce.

**Consequence.** A classifier's `priority_order` resolves multiple category matches within one window;
it is not an arbitrary ordering or source-precedence mechanism. Differently categorized windows from a
second calendar do not cancel a matching absence plan. Source priority, veto categories, or other merge
semantics remain unavailable until a future descriptor defines and tests them explicitly.

#### RC-6 — Architecture overview omits Layer 4 as a dedicated section and misstates power recovery (resolved 2026-09-24)

**Decision.** The overview now gives Layer 4 its dedicated section between learning and action:
the staged semantic DAG resolves only declared inputs and creates the immutable `DecisionSnapshot`;
it transports, but never interprets, frozen history and calendar views. Recovery exposes the prior
target only as a read-only baseline. Current policy, facts, holds and safety determine one final target,
and at most the delta from freshly read actual state may become an `ApplyStep`.

**Consequence.** The overview's section numbering is realigned from Layer 4 onward. It no longer
describes an unsafe two-command restore-then-correct sequence; no authoritative runtime contract
changed.

#### RC-7 — Recap reintroduces forbidden `HouseFact` ownership and obsolete active-family language (resolved 2026-09-24)

**Decision.** The recap now limits `HouseFact` to persistent house assertions and auditable operational
occurrences, explicitly excluding transient signals/candidates, Layer-5 proposal workflow records, and
commands. Its Layer-3 candidate summary names no stale family inventory: only active analyzers under an
exact registered core candidate kind may emit a candidate. `security.presence_simulation` remains
reserved until the PS-1..PS-5 contract sequence closes.

**Consequence.** The recap agrees with Layer 1 and Layer 5 today, while the presence-simulation
follow-up can promote the descriptor later without retrospectively making it an active learner.

---

## Presence-simulation definition follow-up (2026-09-24) — resolved 2026-09-25

**Status:** resolved. `security.presence_simulation` now has a complete Initial-V3 cross-layer
definition without a descriptor-specific execution path. Its promotion is applied to the authoritative
Layer-5 and Layer-3 specifications and summarized in the architecture overview and recap.

#### PS-1 — Initial-V3 product direction and authoring origin (decided 2026-09-24)

**Decision.** On contract completion, promote `security.presence_simulation` to an Initial-V3 core
`ReactionDescriptor` with `admin_direct` as its initial sole authoring mode. Its first plan is
core-generated from administratively staged bounded parameters, never replayed historical commands and
never learned. Direct staging still creates only a `notification_only` `ConfiguredReaction`; operational
shadow, authenticated promotion and current required resident consent remain ordinary shared gates.

**Future compatibility.** A later generic `TemporalActuationProfileModel` may add a reviewed
learner-proposal route for the same descriptor, after its own profile/artifact, privacy, scheduling and
acceptance contracts are defined. A Twilight-like third-party integration may at most supply a bounded,
versioned profile/artifact through that future core contract. It may not evaluate live policy, schedule
work, generate `ApplyStep`s, or command an endpoint while Heima owns the same reaction path.

**Next point.** PS-5 will define shadow operation, authority promotion and executable acceptance.

#### PS-2 — Atomic configuration and core-generated activity episodes (decided 2026-09-24)

**Decision.** Presence simulation adds no `PrerequisiteGeneration` parallel to the generic
`ReactionConfigurationGeneration`: unlike comfort trajectory, no learner artifact must bind to
pre-staged administrative prerequisites. The authenticated direct-staging command persists one complete
immutable configuration generation, or nothing, with the casa-scoped calendar-plan binding, canonical
eligible light endpoint set, closed temporal/activity profile, and the guard reference completed in
PS-4. Any semantic edit creates a successor configuration generation, cancels predecessor jobs, and
returns to `notification_only` under the ordinary authority lifecycle.

**Authoring surface.** The administrator selects individual registered interior-light endpoints and/or
one or more rooms. At staging each room expands to its then-current eligible interior-light Actuators;
the resulting deduplicated endpoint set is persisted in canonical order. A room is never a mutable
runtime group: a later endpoint addition, removal, relocation, incompatibility, or capability change
cannot silently alter the configured simulation. Empty room expansion and duplicate/unknown/ineligible
endpoint selection are rejected.

**Plan shape.** The initial core generator creates a deterministic but day-varying sequence of bounded
activity episodes, not independent random toggles or replayed historic commands. An episode may contain
a finite ordered bundle of concurrent lights across the selected rooms, with bounded stable periods,
overlap and handoff. The administrator supplies only calendar binding, selected lights/rooms, typed
light targets, one local-civil weekly session start, session duration, and closed activity density
(`quiet`, `ordinary`, `active`). Core implementation constants derive episode count, bundle size,
continuity, durations and variation; a reproducible seed from the configuration generation, local
session and episode index makes shadow, restart and audit explainable. Initial V3 permits no arbitrary
jitter/frequency tuning, raw HA scene/script, history replay, or concurrent external scheduler.

**Episode execution (clarified 2026-10-02).** The Reaction follows its
generated sequence, including planned switch-off after the last activity for
each light it turns on, while the current
session, planned-absence, presence and common action criteria hold. The
generator starts only activity whose planned switch-off fits those session
and absence boundaries. A
committed early return removes the absence prerequisite and cancels unsent
steps, even if the next one would have switched off a light. No restore or
switch-off command is added on cancellation or completion. A sent command is
not compensated. Blocked or unconfirmed planned steps use the common outcome
and follow-up path; no physical result is claimed without observation. The
earlier draft that mandated a closing off step in every episode is withdrawn;
the planned end of the generated sequence still switches off its lights.

**Future compatibility.** A later learned or third-party temporal profile may replace only this
core-generated episode selector through the PS-1 bounded artifact contract. It cannot change the
configured endpoint set, calendar/presence/guard authority, common scheduler, or `ApplyStep` path.

#### PS-3 — Plan, absence continuity, cancellation and rescheduling (decided 2026-09-24)

**Historical clause — Superseded by CA4-01 (2026-09-29):** references below to a `global hold` do not describe Initial-V3 admission. Current holds are per Actuator channel and follow Layer 5 §6.0's endpoint-level rules. The other PS-3 decisions remain historical evidence for the presence-simulation descriptor.

**Eligibility.** An activity episode may be selected only inside the configured local-civil session
window, with an active (never merely upcoming) `planned_absence` interval from the bound calendars and
current confirmed `presence=away`. A calendar plan is context, never proof of absence. During a running
process, a `presence.departure` requests an immediate fresh evaluation; at bootstrap the same current
conditions establish the effective absence directly. A departure during an already-open session selects
only the next still-future episode; there is no backfill. The former departure-as-restart-precondition
wording is superseded by CA2-3.

**Presence continuity.** Layer 5 neither reads a raw camera result nor invents a second
simulation-specific return timeout. It stages only against casa presence whose Layer-2 `FusionRule`
declares non-null `Stability.to_true`; Layer 4's resulting committed `presence.return` is the sole
presence-based terminal cancellation. A transient contradictory or unavailable current presence result
does not close the simulation: the affected episode abstains conservatively, while the session remains
eligible for a later fresh snapshot. The global presence fusion owns source quorum, correlation and the
administrator-staged return-confirmation dwell, so a brief false camera/person classification cannot
interrupt the simulation.

**Scheduling.** The descriptor derives only its next `AtJob`, keyed by reaction/configuration
generation, selected calendar-plan fingerprint, local session and episode index. On firing Layer 5
reads a fresh snapshot, revalidates every gate and derives at most one still-future bundle plus its next
job. Calendar edit/removal/failure/end, committed return, global hold, configuration successor or an
applicable global guard cancels future work. A calendar change that remains eligible replaces the old
job from the fresh plan. Missed work after restart or delay is skipped, never replayed, burst, or
compensated.

**Endpoint-level interruption.** A resident control or applicable hold on one selected light suppresses
that member immediately. The core may emit a reduced or alternate bundle only when the remaining result
is still a complete plausible episode and all members pass ordinary current-snapshot admissibility;
otherwise it skips that episode and considers only the next scheduled one. Loss of eligibility never
issues a cleanup command: already sent calls are not compensated and already-lit endpoints remain under
ordinary current policy or resident control.

#### PS-4 — Endpoint allowlist, common guards, privacy and audit (decided 2026-09-24)

**Endpoint eligibility.** Direct staging admits only an explicitly administrator-selected registered
`Actuator` at `where: room`, with `actuator_role="light"`, a registered channel compatible with the
descriptor's closed `light_state` intent, an observable physical-state contract and a compatible core
adapter. The explicit selection is also the administrator's declaration that the endpoint is an
appropriate interior light for this deterrence use. A room location alone must not be treated as proof
of that fact. No global `simulation_safe` field is added to Layer 2: that would make a
descriptor-specific policy appear to be intrinsic endpoint metadata. Every other endpoint is excluded
by construction, including unselected/outdoor lights, generic switches, openings, locks, alarms, HVAC,
appliances, scripts and scenes.

**Common admission contract.** The descriptor uses the ordinary Layer-5 admission path, with the
stabilized `presence=away` condition from PS-3 as its required `presence` guard, and ordinary current
resident consent, enablement, manual-hold, command-ownership, confirmed-state, cooldown and idempotency
checks. It does not require weather, opening, thermal or an unspecified `privacy` guard merely because
those capabilities exist: interior lighting has no corresponding safety predicate here. No
descriptor-specific guard evaluator or security runtime is introduced.

**Data minimization.** Initial V3 reads and persists neither historical presence nor historic commands,
calendar titles/descriptions or other raw calendar content, HA scenes/scripts, a whole future programme,
or the generator seed. Layer 0 supplies only the already-normalized active `planned_absence` interval.
The core-generated plan is represented durably only by its configuration and a non-reconstructive
fingerprint where correlation requires one.

**Audit.** The ordinary trace/audit path records the reaction and configuration generation identity,
plan fingerprint, session occurrence and episode index, admitted or excluded logical members, each
`ApplyStep` outcome, and closed suppression/cancellation reasons. It contains no resident identity,
calendar text, raw HA payload, historic presence data or generator seed. This makes an administrative
decision explainable without creating a household-behaviour log.

#### PS-5 — Shadow, authority and executable acceptance (decided 2026-09-25)

**Shadow scope.** For the Initial-V3 `admin_direct`, core-generated profile, shadow is an optional,
read-only operational preview, not an evidence gate or a prerequisite for promotion. It can show an
administrator how current calendar, stabilized presence, guards and scheduler would derive an episode,
bundle, suppression or next job, but it emits no `ApplyStep` and cannot validate an uncommanded
physical lighting effect. Staging validation, closed adapter contracts and the executable acceptance
suite own that validation instead.

After valid staging an administrator may authorize automatic action, and an authorized resident may
then grant current consent, without first waiting for a planned absence or shadow occurrence. Leaving a
reaction in `notification_only` for preview remains available by choice. Shadow never self-promotes,
grants consent, or sends a resident-visible notification by default. A future learned or imported
`TemporalActuationProfileModel` must define its own evidence/shadow promotion gate before it can replace
the core generator; this Initial-V3 decision does not weaken that future requirement.

**Still to decide.** Exact promotion/revocation command semantics and the release-blocking executable
acceptance scenarios.

**Authority and consent.** The descriptor uses the common `ConfiguredReaction` authority lifecycle
without a parallel security-specific state machine. An authenticated administrator may promote one exact
current configuration generation only after Layer 5 revalidates its staged configuration, endpoint
inventory, adapter contracts, `presence` guard profile and calendar binding. Promotion does not require
an active absence and sends no command; it records administrative authorization and yields
`authorized_awaiting_household_consent` until current consent exists. An explicitly authorized resident
may grant or revoke consent only for that exact generation. A grant requests a fresh evaluation but
never replays an episode missed while disabled; revocation cancels future jobs immediately.

Administrative disablement likewise cancels future jobs and restores effective `notification_only`
without deleting configuration, audit or preview data. A configuration successor cancels predecessor
jobs and inherits neither administrative authorization nor consent. The shared resident-authority
removal rule applies unchanged: when an admin removes a resident who granted current consent, the admin
must explicitly retain or revoke every affected consent; this records the ordinary audit and cannot
grant a new consent. No alternate command, state machine or authority exception exists for presence
simulation.

**Executable acceptance.** The following release-blocking, versioned `Given / When / Then` fixtures
use a fake monotonic clock, frozen calendar/fact snapshots, registered Actuator/adapter doubles and a
Layer-0 scheduler double. They assert only durable configuration/authority state, exact job
creation/cancellation/replacement, `ApplyStep`/`ApplyCall` traces and closed audit/diagnostic reasons:

1. Atomic staging rejects an empty room expansion, duplicate/unknown/ineligible endpoint, incompatible
   light target or incomplete required guard profile without persisting a partial configuration.
2. In optional `notification_only` preview, active planned absence plus stabilized `away` derives only
   the hypothetical episode/bundle and next job, never an `ApplyStep` or resident-visible notification.
3. Departure during an open session, calendar edit/removal, committed return, transient contradictory
   presence, global/endpoint hold, unconfirmed state, late job and restart respectively produce only
   the PS-3 defined selection, abstention, cancellation or replacement behavior: no raw-camera
   cancellation, catch-up, replay, burst or compensation.
4. A known-invalid original bundle may be replaced only by a freshly derived, complete plausible
   alternate bundle whose every member passes common admission. Otherwise no member is commanded. A
   failure after a sent `ApplyCall` records its partial outcome, stops later work and never compensates
   a completed call.
5. Staging begins disabled; promotion without consent is
   `authorized_awaiting_household_consent`; a current grant enables only fresh evaluation; resident
   revocation, administrative disablement and a configuration successor cancel future jobs and do not
   inherit authority. Resident-authority removal exercises each explicit retain/revoke disposition.
6. Audit/trace fixtures prove that no seed, future programme, calendar text, resident identity,
   historical-presence data or raw HA payload enters the descriptor's stored preview, job or audit
   projections.

These fixtures validate contract orchestration, not learned behavioural plausibility or an uncommanded
lighting effect. A future learned/imported temporal profile needs its own evidence and shadow-promotion
acceptance before it may replace the initial core generator.

### Low

#### RC-8 — Approval/status and cross-reference metadata were not promoted with the closure (resolved 2026-09-25)

**Decision.** Layers 0, 1, 2, 4 and 5 now state their defined V3 contract status while retaining the
accurate `Not implemented` qualifier. Layer 3 distinguishes its defined core contract from explicitly
deferred future components. Layer 3 points to the authoritative Layer-5 §7.1 comfort descriptor;
Layer 2 and recap no longer call Initial-V3 thermal contracts reserved. Overview and recap have current
reviewed-through dates, and the overview separates defined-but-gated Initial-V3 descriptors from truly
deferred Layer 6--8 ownership.

**Consequence.** Documentation now signals the actual boundary: the contracts are settled, while
implementation and explicitly marked future ownership remain open. No runtime contract changed.

---

## Post-PS cross-spec coherence audit (2026-09-25) — closed

**Status:** closed 2026-09-25. Fresh reread of the authoritative Layer 0--5 specifications plus
overview and recap after promotion of `security.presence_simulation`. Every finding below was discussed,
confirmed and promoted into its owning specification; no unresolved CA2 item remains.

### Critical

#### CA2-1 — `security.presence_simulation` cannot satisfy the mandatory `RelationProfileRef` contract (resolved 2026-09-25)

`ReactionConfigurationGeneration` and every `RegisteredReactionDescriptor` require one exact
`RelationProfileRef`, while relation profiles are defined exclusively as the shared evidence/policy
contract of a learner and a policy. The new descriptor is explicitly `admin_direct`, has no Layer-3
candidate or learner profile, and declares no registered profile or guard contract of its own. Its
staging therefore has no legal value for `relation_profile`, `supported_profile_refs`, or the required
presence guard profile. This blocks a conforming implementation and must be resolved without creating a
parallel policy mechanism.

**Decision.** `RelationProfileRef` is required only for a learner-origin configuration: it remains the
one immutable shared evidence/policy contract for `learner_proposal`, candidate and proposal paths.
An `admin_direct` configuration may carry no relation profile, but then its core
`ReactionDescriptor` must declare one exact descriptor-level `EnvironmentalGuardContractRef`; staging
selects exactly one of these two policy sources and rejects every other origin/profile/contract
combination. This is a generic authoring-origin rule, not a presence-simulation exception.

`security.presence_simulation` is direct-only with empty `supported_profile_refs` and declares
`security.presence_simulation.interior_lighting@1`. Its `light_state` intent permits and requires only
the stabilized `presence` capability; manual hold, ownership and confirmed state remain common action
admission checks. The shared `ConfiguredReaction`, plan, scheduler and `ApplyStep` pipeline are
unchanged.

### High

#### CA2-2 — Presence-simulation local-civil session is prose, not a typed Layer-0 temporal contract (resolved 2026-09-25)

The descriptor requires one “local-civil weekly session start and duration” but omits weekdays, exact
type, validation, local-time/DST semantics and canonical fingerprinting. Layer 0 already owns
`WeeklyRecurrence` and `Window`, and expressly forbids bespoke duration/schedule fields in Reaction
configuration. The descriptor must bind its session to those shared types or explicitly define an
equivalent core-owned composed contract.

**Decision.** No new Layer-0 feature is needed. The descriptor's
`PresenceSimulationActivitySession` configuration contains only the existing Layer-0
`WeeklyRecurrence` and `Window` types. Their existing weekday, local-time/DST and duration validation
is authoritative. The pair is not a `CronEntry` and does not create another scheduler: Layer 5 uses it
only to identify a session occurrence while an eligible absence exists and to derive the one ordinary
next `AtJob`.

#### CA2-3 — Restart eligibility conflicted with the no-historical-presence rule (resolved 2026-09-25)

The former wording required the `presence.departure` that began the effective absence. Layer 4 resets
its transition adapter after restart, so its first `away` seeds a baseline and emits no departure;
Layer 5 also cannot query durable presence history. Treating the historical departure as a restart
precondition would therefore disable a valid ongoing absence, or require an unnecessary new durable
policy archive.

**Decision.** A running process uses `presence.departure` only to request an immediate fresh
evaluation. At bootstrap, an active matching planned-absence interval plus current stabilized
`presence=away` establishes the effective absence directly. Layer 5 then derives only the next still
pertinent job from that current snapshot and configuration. It neither persists nor recovers a
pre-restart departure, replays missed work, catches up, or bursts calls. This common rule applies to
both comfort trajectory and presence simulation; a calendar remains context rather than proof because
the current stabilized presence state is independently required.

#### CA2-4 — Descriptor audit minimization conflicted with common consent authority audit (resolved 2026-09-25)

The former presence-simulation wording forbade resident identity in every record/audit projection, but
the common `ReactionAuthorityTransition` stores `actor_ref`; consent and the required retain/revoke
decision on resident-authority removal necessarily need attributable governance records. The same
boundary applies to every descriptor, not only presence simulation.

**Decision.** `actor_ref`, `created_by` and `staged_by` remain only in the common Layer-5 governance
ledger: proposal review, reaction/configuration creation or staging, and authority transitions. No
descriptor operational projection -- plan, preview, job, evaluation result, `ApplyStep`, execution audit
or diagnostic -- may duplicate them. Descriptor data-minimization clauses constrain their operational
records, never the shared governance ledger. Presence simulation now states this boundary explicitly;
comfort trajectory and every future descriptor inherit it from Layer 5 §4.2.

### Medium

#### CA2-5 — Initial descriptor roster incorrectly claimed singleton bundles (resolved 2026-09-25)

Layer 5 said all Initial-V3 descriptors declared singleton bundles and that multi-member bundles were
future-only. This was already contradicted by `routine.actuation_bundle` and is additionally contradicted
by presence simulation's finite concurrent light bundles.

**Decision.** Bundle cardinality is declared by each core descriptor: singleton or a finite ordered
multi-member bundle within its core-owned bound. It never selects another execution path. All shapes use
the same staging, evaluation, complete-bundle admissibility and one-endpoint `ApplyStep` contract. An
alternate bundle may be freshly derived only before admission; a known-invalid original bundle is never
partially executed.

### Low

#### CA2-6 — `ReactionProposal` was incorrectly described as defined by Layer 1 (resolved 2026-09-25)

Layer 5 called `ReactionProposal` a governance record “defined by Layer 1”, while Layer 1 explicitly
classifies it as a Layer-5 workflow record, persisted by its own contract and not a `HouseFact`.

**Decision.** Layer 5 owns and persists `ReactionProposal`; Layer 1 defines only its ontological
distinction from the fact substrate. This is an ownership wording correction with no behavioral or
schema impact.

---

## Post-CA2 full cross-spec coherence audit (2026-09-25) — resolved findings

**Status:** resolved as specification findings. This reread of the authoritative Layer 0–5
specifications, overview and recap after CA2 retains the decision history; the current layer
specifications own the normative contracts.

### High

#### CA3-1 — Layer 0 and recap retained an obsolete prior-cycle-only Layer-4 DAG model (resolved 2026-09-25)

Layer 0 §11 says a Layer-4 semantic resolver can read only prior-cycle outputs of other semantic
resolvers. The recap repeats that claim in its Layer-4 and Layer-5 summaries. Layer 4's authoritative
contract instead stages a deterministic topological DAG in which an edge reads one declared *same-cycle*
upstream semantic claim; only explicitly declared `previous_cycle` values use Layer 0's prior-cycle
snapshot. The stale model can add a cycle of latency or make a valid same-cycle resolver dependency seem
illegal.

**Decision.** Layer 4 owns its same-cycle semantic DAG and deterministic topological evaluation order.
Layer 0 supplies only separately declared `previous_cycle` snapshot values and fresh engine context; it
does not redefine semantic-edge timing. Layer 0 §11 and both recap summaries now state this model.
`activity.sleeping` consuming same-cycle `occupancy=present` remains a concrete contract witness.

### Medium

#### CA3-2 — Obsolete `PolicyTemplate` / `ConfiguredPolicy` ontology remained outside Layer 5 (resolved 2026-09-25)

Layer 5's authoritative mechanism is `ReactionDescriptor` -> `ConfiguredReaction`, but Layer 3, Layer
4, the overview and one Layer-5 prose sentence still use the superseded `PolicyTemplate` /
`ConfiguredPolicy` vocabulary. This is more than cosmetic because Layer 3 still contrasts a direct ECA
Reaction with learner-proposed “policy templates”, although authoring origin is now a property of one
Reaction-descriptor mechanism. The terminology must be normalized without reintroducing two action
paths.

**Decision.** `ReactionDescriptor` -> `ConfiguredReaction` is the sole generic action-bearing
mechanism. `admin_direct` and `learner_proposal` are authoring origins of that one descriptor, never
separate evaluators or execution paths; Layer 3 may submit only candidates for compatible
`learner_proposal` descriptors. The remaining normative old vocabulary in Layer 3, Layer 4, Layer 5
and overview is normalized accordingly. Historical backlog entries retain their original terminology.

#### CA3-3 — Comfort-trajectory absence semantics drifted between Layer 3 and Layer 5 (resolved 2026-09-25)

Layer 5 now establishes an effective absence at bootstrap from current stabilized `presence=away` plus
an active planned-absence interval; `presence.departure` requests an immediate fresh evaluation only
during a running process, while `presence.return` is terminal cancellation. Layer 3 still says the
descriptor “consumes observed departure/return episodes” without this bootstrap distinction. The latter
wording can be read as retaining an observed departure as a mandatory eligibility condition, the rule
CA2-3 intentionally removed.

**Decision.** `presence.departure`/`presence.return` remain generic Layer-4 semantic episodes, while
current-absence eligibility is declared by each absence-based descriptor rather than every Reaction.
For both currently defined planned-absence descriptors, comfort trajectory and presence simulation,
the effective absence requires an active matching plan plus current stabilized casa `presence=away`.
Comfort trajectory now stages the same non-null casa `Stability.to_true` prerequisite already explicit
for presence simulation. During a running process departure requests a fresh evaluation; bootstrap
uses only fresh current conditions and committed return cancels future work. Layer 3's two comfort
summaries now refer to this Layer-5 contract without redefining it. Historical departure/return cohorts
remain a distinct and correct learning concern.

#### CA3-4 — Common governance-identity restriction omitted required Layer-5 configuration records (resolved 2026-09-26)

Layer 5 §4.2 says `staged_by` is restricted to proposal review, reaction/configuration creation or
staging, and authority transitions. Its own schemas also require `staged_by` on
`EnvironmentalGuardProfileGeneration` and `ComfortTrajectoryPrerequisiteGeneration`. Those are valid
common Layer-5 configuration/governance records but are not named by the restrictive enumeration. The
rule should state the intended complete class rather than inadvertently prohibiting fields its schemas
require.

**Decision.** `actor_ref`, `created_by` and `staged_by` are permitted only in common Layer-5
governance or immutable administrator-configuration records: proposal review, Reaction
creation/configuration generations, authority transitions, `EnvironmentalGuardProfileGeneration` and
`ComfortTrajectoryPrerequisiteGeneration`. A future type may retain one only when it belongs to that
same common class. Operational plans, preview, jobs, evaluation results, `ApplyStep`s, execution audits
and diagnostics remain identity-free.

---

## Full V3 specification audit — CA4 (2026-09-26; revalidated 2026-09-27)

**Audit status:** complete. **Correction status:** corrections are in progress. This audit records specification changes, not runtime implementation.

**Scope and method.** A line-by-line reread covered all six Layer 0–5 specifications in `docs/specs/v3/`, the architecture overview, both PlantUML diagrams, `v3_architecture_recap.md`, its Graphviz diagram, all five `v3_*_draft.md` documents, and `specs/INDEX.md`. The review used the current local files, including uncommitted changes, and cross-checked the relevant decisions and previous audit closures in this backlog. Each retained finding below identifies a concrete contradiction, a missing contract, or a documentation defect and includes a closure criterion. Historical drafts are subordinate to the layer specifications: an obsolete historical decision is not itself a new normative defect.

This is an internal specification-coherence audit, not a V2 implementation audit or independent verification of external scientific sources. The original completed reread found CA4-31–38; the later CA4-01 closure audit records separately verified CA4-39–50 below, and the 2026-10-04 post-CA4-01 full reread records CA4-51–60. It cannot prove that no further defect exists; no additional confirmed issue from this pass is intentionally omitted.

**Revalidation of the original appendix.** CA4-01–30 retain their identifiers for tracking. Their English descriptions replace the original Italian text. Claims were narrowed where the earlier wording exceeded the evidence: CA4-01 was subsequently reopened for the 2026-09-28 internal-divergence product decision; freshness in persisted history is distinct from freshness of newly evaluated live facts (CA4-05); successful service completion is not inherently a false claim of physical success (CA4-19); and nested checkpoint data is not proven unrepresentable merely because it must satisfy a depth bound (CA4-28). These narrowed items remain open for the specific residual defects stated below. Already resolved CA/RC/CA2/CA3 decisions are not reopened wholesale. CT-4 remains the existing calibration/release gate and is not duplicated here.

**Severity.** `P0 / Critical`: contradictory authorization rules. `P1 / High`: potentially incorrect action/data behavior or a missing contract required to implement an Initial-V3 capability consistently. `P2 / Medium`: an ambiguous algorithm, lifecycle, schema, or validation requirement. `P3 / Low`: documentation maintenance. Risks describe possible implementations of the written contracts, not observed production failures. The original entries are grouped by severity; later appendices retain discovery order and state each finding's priority explicitly. Stable IDs are deliberately not renumbered.

| Severity | IDs | TODO | IN_PROGRESS | DONE | NOT_APPLICABLE |
|---|---|---:|---:|---:|---:|
| P0 — Critical | CA4-01 | 0 | 0 | 1 | 0 |
| P1 — High | CA4-02–19, CA4-31, CA4-33–34, CA4-36, CA4-39–47, CA4-51–52, CA4-64–66, CA4-70, CA4-86–87, CA4-99–100 | 0 | 0 | 41 | 0 |
| P2 — Medium | CA4-20–28, CA4-32, CA4-35, CA4-37–38, CA4-48–50, CA4-53–58, CA4-61–63, CA4-67–69, CA4-71–76, CA4-79, CA4-83, CA4-85, CA4-88–92, CA4-95–96, CA4-98, CA4-101–104, CA4-106–117 | 0 | 0 | 60 | 1 |
| P3 — Low | CA4-29–30, CA4-59–60, CA4-77–78, CA4-80–82, CA4-84, CA4-93–94, CA4-97, CA4-105 | 0 | 0 | 14 | 0 |
| **Total** | **117 findings** | **0** | **0** | **116** | **1** |

**Tracking rule.** On taking an item, change its status to `IN_PROGRESS` and record owner and start date. Mark it `DONE` only after the owning specification, affected references, and acceptance criteria agree; attach the change and verification references. If subsequent evidence rejects an item, retain it as `NOT_APPLICABLE` with the reason. Update the counts above. Specification closure and runtime implementation are separate activities.

### P0 — Critical

#### CA4-01 — Hold authority and observed divergence

**Status:** DONE (2026-10-04; specification readiness). Reopened 2026-10-03 after the earlier closure missed depth-two serialization and multi-channel follow-up identity. The user approved A1/B1/C2; all three are applied. This does not claim runtime implementation or testing.

| Decision | Current contract |
|---|---|
| A1 — scalar facet projection | Target facet values are lossless bounded canonical JSON text; the follow-up event uses flat `expected.<facet>` and `observed.<facet>` keys. |
| B1 — per-channel follow-up identity | Core hashes Reaction/generation/activation, boundary and Actuator/channel into one stable operation id per channel; outbox, retry, recovery and notification keys use it. |
| C2 — complete inline hold audit | Staging proves the maximum complete `HoldLifecycleValue` fits Layer 1's depth-two/8 KiB limits, or rejects the composition. No detail store or special queue path remains. |

**Closure evidence:** [Nine serialized value/projection examples](specs/v3/ca4_01_serialization_examples.md) validate shape, canonical facets, depth/size, source maps and operation ids. Light and HVAC use Initial-V3 descriptors; the valve case is marked as a future-descriptor serialization example, not an executable Initial-V3 outcome. T10/T11/T17/T18 and new T20/T21 pass their document-level counterexample review; the field matrix covers all 90 fields of nine named types. After aligning the current diagrams and recap, the expanded regex gate classified 243 matching lines as 238 coherent, five marked historical (including the retired Graphviz source) and zero normative residues; `git diff --check` passed. The [full review record](ca4_01_review_record.md) retains every decision, trace, matrix row and historical note.

**Owners and boundaries:** [Layer 0 §4/§6/§13](specs/v3/layer0_runtime_spec.md), [Layer 1 §3–4/§10](specs/v3/layer1_substrate_spec.md), [Layer 2 §6](specs/v3/layer2_registries_spec.md), [Layer 5 §3.2/§6/§7.2/§8](specs/v3/layer5_action_reactions_spec.md), [overview](specs/v3/architecture_overview_defined_layers.md), [recap](v3_architecture_recap.md). Layer 6 must declare bounded renderer output for the follow-up fact. CA4-02 and CA4-17 have separately closed shared admission and dispatch fencing; CA4-18, CA4-38 and CA4-39 retain their separate open scopes.

#### CA4-02 — Shared hold admission and command ownership contract

**Status:** DONE (2026-10-04; specification readiness). **Type:** shared interface/arbitration contract. **References:** [Layer 0 §6](specs/v3/layer0_runtime_spec.md), [Layer 4 §5.1](specs/v3/layer4_domain_spec.md), [Layer 5 §3.2, §6](specs/v3/layer5_action_reactions_spec.md). This does not claim runtime implementation or testing.

**Original gap, now closed:** Layer 5 needed live hold and in-flight ownership inputs plus order-independent arbitration for two Reactions targeting the same channel. Persisted hold facts remain audit, not authority. The Initial-V3 precedence-exception table is explicitly empty; no implicit safety/security winner exists.

**Decision and rationale:** Layer 0 §6.1.1 owns a frozen, scope-aware hold projection; Layer 5 §6.0 owns the frozen in-flight ownership projection and whole-cycle single-writer arbitration. Layer 4 transports both in `DecisionSnapshot` and includes their fingerprints in snapshot identity. After individual non-ownership admission, two bundles contending for any one channel both abstain from action, including conflicting targets, disjoint facets, and identical values. The user confirmed all three cases on 2026-09-28. Initial V3 has no implicit safety/security preemption. This follows the product decision of 2026-09-27: conflicts block both unless a future explicit versioned core exception is approved. Hold matching uses the exact registered Actuator channel and staged whole-channel or changed-facet scope in Layer 0 §6, not a functional domain or descriptor namespace.

**Specification verification:** Layer 0 §6.1.1 owns the frozen `HoldAdmissionView`; Layer 5 §6.0 owns the frozen `CommandOwnershipView` and whole-cycle arbitration; Layer 4 §5.1 transports both and includes their fingerprints in `snapshot_id`. A default whole-channel hold blocks all automatic calls on that channel. Under staged changed-facet scope, a held power facet blocks a direct power command and a brightness command whose declared HA effects also turn power on, while a genuinely disjoint facet remains eligible. Two eligible bundles claiming one channel both receive `command_ownership_unavailable` regardless of evaluation order, including opposing targets, disjoint facets and identical values. A bundle that fails a non-ownership guard claims nothing; a multi-member bundle with one contested key reserves none. Atomic reservation, same-bundle retry, lease lifetime and fresh-read handling after restart are specified in Layer 5 §6.0 and §6.0.1. These are document-level counterexamples, not runtime tests. **Separate scopes:** CA4-17 has closed the asynchronous dispatch fence; CA4-27 remains open for cross-layer generation activation. CA4-19 already closed uncertain physical-outcome reconciliation.

#### CA4-03 — Recovery baselines lose channel, partial-target, and authority information

**Status:** DONE (2026-10-05; specification readiness). **Type:** cross-layer mismatch. **References:** [Layer 0 §7.4](specs/v3/layer0_runtime_spec.md), [Layer 2 §6.1](specs/v3/layer2_registries_spec.md), [Layer 5 §4.2, §6](specs/v3/layer5_action_reactions_spec.md). This does not claim V3 runtime implementation.

`RecoveryTargetSnapshot` is last-write-wins per `entity_id`, although an Actuator can have multiple channels and a target can specify only some facets. Successive independent commands can overwrite information needed for reconstruction. The baseline records an Actuator fingerprint but no originating Reaction/configuration generation. Current policy remains the action gate, but the mapping from an old baseline to its current authorizing policy after removal, edit, or revocation is unspecified.

**Correction:** define baseline granularity, partial-target merge, and association with current authority, including `require_confirmation`. **Closure:** recover two channels and successive partial targets after one originating policy is revoked; retain only the intent admitted by the explicitly defined current-policy rules.

**Approved resolution and verification:** the developer chose to discard target facets from a removed or consent-revoked Reaction. Layer 0 now coalesces one bounded snapshot per `(actuator_id, controlled_channel)`, replacing only targeted facets and retaining their trusted Reaction-generation or direct-command anchor. Layer 5 filters every Reaction facet against current automatic authority and runs the merged target through normal admission; direct facets still need the current Actuator recovery policy and safety checks. Layer 2 cutover discards changed endpoint, execution fingerprint or recovery policy. CA4-39 uses the resulting baseline identity in confirmation proposals. The [CA4-03 review](specs/v3/reviews/CA4-03.md) covers mixed channels, partial targets, revocation and incompatible merges. CA4-45 separately adds this frozen input to `DecisionSnapshot`.

#### CA4-04 — Retention can report completeness after deleting the boundary state

**Status:** DONE (2026-10-05; specification readiness). **Type:** algorithmic defect. **References:** [Layer 0 §4.0–4.3](specs/v3/layer0_runtime_spec.md), [Layer 3 §4.2](specs/v3/layer3_learning_spec.md), [Layer 5 §5.1](specs/v3/layer5_action_reactions_spec.md).

Protecting only the latest state record does not preserve the predecessor needed at a historical window's left boundary. With `A` at day 0, `B` at day 20, a 14-day retention window, and a query for days 10–21, ordinary pruning may delete `A`. The query is inside retention but cannot reconstruct days 10–20. The meaning of `last_early_pruning_at` also needs to distinguish discarded-record time from maintenance time.

**Correction:** retain the necessary boundary predecessor or report the missing reconstruction coverage; apply equivalent rules to the memory buffer. **Closure:** both ordinary time pruning and count pruning return the correct initial state or an explicit truncated result, never an apparently complete unseeded interval.

**Approved resolution:** report incomplete/truncated history when the predecessor or
buffer observation coverage cannot be established; do not retain an additional
predecessor solely for the query. [CA4-04 impact and scenario review](specs/v3/reviews/CA4-04.md)
records the durable, short-term, event and consumer cases. This is specification
review, not a V3 runtime result.

#### CA4-05 — Change timestamps and observation freshness are conflated

**Status:** DONE (2026-10-07; specification readiness). **Type:** temporal-semantic mismatch. **References:** [Layer 0 §4.0–4.4](specs/v3/layer0_runtime_spec.md), [Layer 1 §4.1](specs/v3/layer1_substrate_spec.md), [Layer 2 §3.2](specs/v3/layer2_registries_spec.md), [Layer 3 §4.2](specs/v3/layer3_learning_spec.md).

Write-on-change leaves persisted records and the current index unchanged for identical fingerprints. Layer 1 nevertheless describes `now - fact.when` as sufficient freshness, and Layer 3 uses historical `max_age` gates. Repeated confirmations of an unchanged temperature are indistinguishable in that history from an old unconfirmed observation. This does not establish that a freshly evaluated live fact is necessarily stale. Separately, the historical phrase “latest available state” can skip a newer unavailable record, contrary to unavailable-state semantics.

**Correction:** distinguish transition time, observation freshness, and continuity; resolve the latest record before testing availability. **Closure:** stable refreshed readings, abandoned sources, and unavailable intervals have distinct historical behavior without requiring redundant full-fact writes every cycle. See CA4-33 for process downtime.

**Approved resolution:** `HouseFact.when` is the accepted transition instant;
identical observations append no fact or per-cycle confirmation row. Layer 0
uses durable stream-gap boundaries only for known breaks, in addition to its
existing process interruption and retention coverage. A staged report-age
gate uses HA `last_reported`, not `last_updated`; expiry starts the required
stream's gap at the known expiry even if noticed later. Sources with no
declared report-age gate keep their HA current-state semantics until an
observable failure; Heima does not claim to detect a silent physical fault.
Layer 3 removes transition-age `max_age` from state as-of features and point
outcomes, resolves the latest state before checking availability, and excludes
intervals with source/process gaps. The [CA4-05 impact and scenario review](specs/v3/reviews/CA4-05.md)
records temperature, change-only source, unavailable/recovery and solar cases.
This is specification review, not a V3 runtime test.

#### CA4-06 — Value-only stabilization suppresses required epistemic changes

**Status:** DONE (2026-10-05; specification readiness). **Type:** normative contradiction. **References:** [Layer 2 §5.2](specs/v3/layer2_registries_spec.md), [Layer 0 §4.0, §4.2](specs/v3/layer0_runtime_spec.md).

The stability algorithm suppresses a new fact when the candidate value equals the committed value. Persistence instead requires changes in confidence, availability, or source fingerprint to remain observable at an unchanged value. Comparing against the value of an unavailable fact is also invalid because that value is undefined. There is a related provenance gap: a precedence fusion's `source_id` remains its `fusion_id`, and its configuration fingerprint remains unchanged when it selects a different input. With equal value/confidence, recording the selected input only in evidence does not preserve the source handoff, because evidence is excluded from write-on-change.

**Correction:** value dwell compares only available values; publication compares the full `FactChangeFingerprint`. A stable `FactSource.route_fingerprint` records the evaluated input route of each fusion separately from configuration identity. **Closure:** `True/.9 -> True/.2`, a same-value precedence handoff, and `unavailable -> True` produce the required updates without reading undefined values or incorrectly restarting dwell. [CA4-06 impact and scenario review](specs/v3/reviews/CA4-06.md) records the cases; no V3 runtime test was run.

#### CA4-07 — Physical-evidence confidence contradicts its acceptance example

**Status:** DONE (2026-10-05; specification readiness). **Type:** mathematical ambiguity with a contradictory test. **References:** [Layer 2 §5.3, §9](specs/v3/layer2_registries_spec.md).

The formula sets support to the confidence-weighted true score and total to the sum of selected group votes. If total means those weighted votes, a sole immediate primary with weight 1 and confidence .2 gives `.2/.2 = 1`, whereas acceptance requires correspondingly low confidence. Treating total as a count of groups instead can give support greater than total with weights above 1. A zero-confidence immediate-primary case also needs an explicit zero-total rule.

**Correction:** the numerator remains the winning confidence-weighted group score; the denominator is the sum of configured directional weights of retained, non-conflicted groups before their confidence multipliers. **Closure:** numerical examples for low/zero-confidence primaries, weights above 1, correlated groups, and conflicting evidence satisfy both the declared meaning and `[0,1]` bounds. [CA4-07 impact and scenario review](specs/v3/reviews/CA4-07.md) records the check; no V3 runtime test was run.

#### CA4-08 — The prescribed fast/confirmed composition cannot satisfy formula staging

**Status:** DONE (2026-10-05; specification readiness). **Type:** non-composable contract. **References:** [Layer 2 §2.3, §5.3](specs/v3/layer2_registries_spec.md).

The composition requires two intermediate fusions and a final fusion. `physical_evidence.weighted_evidence` permits only the final room/casa physical output names and Sensor evidence inputs. Two intermediate physical outputs at the same scope collide; distinct intermediate names or Fusion inputs fail its validator. A generic quorum is not specified as preserving the same admission/correlation guarantees.

**Correction:** the developer chose one existing physical-evidence fusion: `immediate` primary for the fast route and independent corroborating-group quorum for confirmation. **Closure:** a complete two-route fixture passes staging with one physical output and no illegal intermediate inputs, while one correlated group cannot forge quorum. [CA4-08 impact and scenario review](specs/v3/reviews/CA4-08.md) records the cases; no V3 runtime test was run.

#### CA4-09 — Routine and correction learning lack the required historical actuation data

**Status:** DONE (2026-10-07; specification readiness; owner: Codex). **Type:** incomplete data interface. **References:** [Layer 0 §4/§5.1.1](specs/v3/layer0_runtime_spec.md), [Layer 2 §6.1](specs/v3/layer2_registries_spec.md), [Layer 3 §4.4.2–4.4.3](specs/v3/layer3_learning_spec.md), [Layer 5 §6–6.1](specs/v3/layer5_action_reactions_spec.md).

`actuator.resident_control` contains actuator/channel/edge identity but no observed target or facet values, and no specified historical join supplies the complete routine member target. Correction counts require every completed ApplyStep, including zero-correction and superseding actions; execution audit has no declared HouseFact history contract supplying those anchors. Targeted-facet attribution and exclusion of Heima-originated observations need the same normalized linkage. The correction section also restricts input to resident-control events while allowing an external/unknown classification without declaring its input route.

**Correction:** define minimal privacy-preserving historical action, observed-target, completion, and attribution projections, including configuration identity, joins, deduplication, and censoring. **Closure:** reconstruct a brightness routine and correction samples with zero, one, multiple, external/unknown, and superseding controls solely through the permitted historical interface.

**Approved resolution and verification:** Layer 0 projects one bounded
write-on-change `actuator.channel_state.<digest>` state per registered
Actuator channel, with canonical post-edge facets, exact changed facets,
edge id and verified origin. The existing three-field
`actuator.resident_control` event remains unchanged and joins by edge id;
the routine descriptor's versioned observed-member projection must produce
one semantic target and pass the normal forward translation round trip.
Layer 5 publishes only admitted target lifecycle phases (`decision`, first
`complete_observation`, `closed`) under one `apply_step_id`; the existing
`actuator.correction` event alone supplies resident counts. External/unknown
edges can yield diagnostics but never resident learning evidence. Layer 3
joins these typed histories, retention and `ObservationCoverage`; no
observation, an unavailable bulb after a wall-switch power cut, process
gap, revocation or superseding decision cannot become a zero sample.
The [CA4-09 impact and scenario review](specs/v3/reviews/CA4-09.md)
checks same-value reads, already-satisfied/late targets, 0/1/2+ counts,
routine target projection, external controls and recovery. V3 runtime has
not been implemented or tested.

#### CA4-10 — Semantic transition triggers have no declared current-cycle before/after input

**Status:** DONE (2026-10-05; specification readiness). **Type:** snapshot-barrier mismatch. **References:** [Layer 0 §4.1](specs/v3/layer0_runtime_spec.md), [Layer 4 §5.1](specs/v3/layer4_domain_spec.md), [Layer 3 §4.4.3](specs/v3/layer3_learning_spec.md), [Layer 5 §5.1–5.2, §7](specs/v3/layer5_action_reactions_spec.md). This does not claim V3 runtime implementation.

A routine may trigger on a completed Layer-4 output transition. The intake group, however, contains Layer-2 changes; the frozen history precedes Layer-4 output, and the semantic map supplies current conclusions. No generic semantic before/after pair is declared for the Layer-5 `state_transition` primitive. Explicit episode adapters cover only their registered transitions and do not create a generic mirror of every semantic state.

**Correction:** define the permitted semantic transition input at the barrier or restrict such triggers to explicitly registered episodes. **Closure:** a routine triggered by a Layer-4 state change fires once in the intended cycle using only the completed snapshot, including unchanged and unavailable cases.

**Approved resolution and verification:** the developer chose one typed previous/current pair. Layer-5 staging declares the exact state key for Layer 0's in-memory `previous_cycle`; after Layer 4 completes, the coordinator places its current state and sealed predecessor in `DecisionSnapshot.state_transition_inputs`. Layer 5 compares canonical typed values within that snapshot, fires on one net transition, treats unchanged values as `not_triggered`, and abstains on unavailable, missing, restarted or changed-producer predecessors. Explicit episode adapters remain for individual event meanings. The [CA4-10 review](specs/v3/reviews/CA4-10.md) covers same-cycle, unchanged, unavailable and restart cases.

#### CA4-11 — Profile-free admin-direct descriptors lack part of the generic plan contract

**Status:** DONE (2026-10-07; specification readiness). **Type:** residual gap after CA2-1. **References:** [Layer 5 §3.1–3.2, §4.2, §5.1, §7.2](specs/v3/layer5_action_reactions_spec.md), [Layer 3 §6.5](specs/v3/layer3_learning_spec.md). This does not claim V3 runtime implementation.

CA2-1 correctly permits `relation_profile=None` with a descriptor-level direct guard contract. Generic runtime slots, comparisons, and temporal shape still refer to the relation-profile policy facet, and the envelope rule refers to its axes. The alternative guard contract supplies capabilities, not a complete alternative source for all those declarations.

**Correction:** specify the direct descriptor's source of slots, temporal primitives, parameters, and applicable envelope axes without inventing a learner relation profile. **Closure:** fully compile and validate presence simulation with no relation profile, through the ordinary shared plan pipeline.

**Approved resolution and specification verification:** the frozen descriptor
version supplies the base typed slot, temporal-plan, comparison, parameter,
bundle and envelope-axis grammar. A learner relation profile narrows that
grammar; a profile-free direct generation uses it with the exact
descriptor-level guard contract. Both compile to the same plan and action
path. `CanonicalEnvelope` remains mandatory: learned cells retain positive
measured support and calibration, while direct cells have both evidence
fields absent. Presence simulation declares zero axes and one empty-key
direct cell, with active calendar, stabilized presence, session, guards,
authority and admission checked separately. Future direct descriptor
versions declare typed slots, pure versioned partitions and bounded joint
cells. A step-programmed Reaction reuses its descriptor-version activation
start criteria in the existing plan trigger field; departure, calendar
refresh and due jobs request re-evaluation, including a fresh bootstrap
start without a fabricated departure. The [CA4-11 impact and scenario
review](specs/v3/reviews/CA4-11.md) covers normal, unavailable, restart,
concurrent-request, cancellation and authority cases. V3 runtime has not
been implemented or tested.

#### CA4-12 — The initial catalog and candidate schema are not mutually complete

**Status:** DONE (2026-10-11; specification readiness). **Type:** incompatible vocabulary and missing schema variants. **References:** [Layer 3 §4.8, §6.4–6.6](specs/v3/layer3_learning_spec.md), [Layer 5 §3, §7](specs/v3/layer5_action_reactions_spec.md).

The earlier mismatch between Layer 3's `reduce_solar_gain` and Layer 5's `limit_solar_gain` was resolved by using the latter exact ID in both contracts. The earlier omission of `thermal_shading` from the initial profile enumeration has also been corrected. The room-neutral `humidity_extraction` and routine relation profiles still lack corresponding complete evidence/policy entries. The earlier common candidate imposed positive numeric deltas and predicted effects on every member, including routines; the partial correction below removes that false requirement but does not close the catalog gap.

**Correction:** publish one versioned descriptor/origin/profile/objective/intent/schema matrix and a typed routine variant where environmental fields do not apply. **Closure:** every initial descriptor has a complete valid example; no placeholder outcome unit or fictitious effect is needed to satisfy mandatory fields.

**Candidate-schema decision (2026-10-07; partial):** keep the outer
`ReactionDescriptorCandidate` unchanged. Its member has an optional typed
`NumericOutcomeRequirement`, required only when the exact descriptor/profile
defines a per-member numeric response. Environmental response thresholds
remain stable candidate semantics; comfort trajectory and routine members
carry no fabricated numeric delta. Measured response, thermal reachability
and whole-bundle routine frequency remain in the exact typed artifact and
refreshable proposal evidence, so compatible retraining does not create a
new candidate. See [the CA4-12 impact and scenario record](specs/v3/reviews/CA4-12.md).
The solar objective ID and the older §6.6 fingerprint wording were aligned
in the same review; neither is an outstanding CA4-12 gap.
CA4-12 remains TODO until the profile/catalog matrix, the routine artifact's
closed keyed validation-report schema and exact relation-profile/validator
registration, and one valid example for every Initial-V3
descriptor are complete. The routine output schema and duplicate-effect
consolidation below are partial corrections, not catalog closure.
The [Initial-V3 registration audit](specs/v3/reviews/CA4-12.md) now lists
the six descriptor paths and distinguishes established joins from missing
concrete entries. It is a verification inventory, not a second runtime
catalog or authority source; unresolved cells still block closure.
The developer has approved both `admin_direct` and `learner_proposal` for
Initial-V3 `environment.solar_shading` and `environment.external_exchange`.
This resolves those two origin sets only. Their profile-free direct guard
contracts and finite direct envelope cells still need exact registration
before either direct path can stage (registered in slices 12a and 12b);
the extraction origin set is registered in slice 12c.
The approved common-contract correction now keys required guards by
descriptor-validated `(action_intent, semantic_variant_id)` and lets a
descriptor's direct envelope use its own fixed axis subset, including the
one empty-key cell when its typed trigger and guards already constrain the
action. The same descriptor may retain richer supported learned cells.
For external exchange, `thermal`, `air_quality` and `hygrometric` are
validated purpose variants; their exact required capability sets and direct
guard contract IDs remain open. This avoids both a union of unrelated guards
and a second evaluator. The direct envelope shape is resolved, but complete
direct registrations/examples still block CA4-12 closure.

**Extraction entry and subsequent control (approved clarification; program open):**
for one `environment.air_extraction` activation, a fan already active at the
qualifying start is untouched, including speed and eventual stop, regardless
of origin or target match. An initially inactive fan may subsequently be
started, changed in speed and stopped by steps actually declared for that
Reaction and passing ordinary admission. Layer 5 §7 now makes the fresh
inactive entry state a pre-target condition; the active case creates no
`already_satisfied` Heima target anchor. Layer 3 §4.8 retains observed entry
state, physical active/speed/stop transitions and verified origin as separate
learning evidence; an active-at-entry no-op is not a Heima-start effect
sample. This choice does not change generic hold or other descriptors.
The earlier Layer-5 one-shot draft specifies only an `activate_extraction`
target, with no modification/terminal step or normal exit. The approved
Initial-V3 descriptor requires a developer-registered step-programmed
specialization; that draft cannot stage as a complete extraction program.
Its implementation must declare typed start, target-modification and end
rules, including the target bounds appropriate to its Actuator channel.
No universal speed or on/off branch is added to Layer 5. See the
[CA4-12 scenario review](specs/v3/reviews/CA4-12.md); no V3 runtime test ran.

**One registered program interface (approved direction, generic contract aligned):**
the descriptor version registers its pure `program_evaluator` specialization;
its compiler persists only canonical parameters and typed bindings in the
existing `ReactionEvaluationPlan`. Layer 5 resolves that exact version and
calls `evaluate_program` with the frozen snapshot and activation state. The
specialization selects start, target change, wait, verified normal end or
abstention and supplies each proposed step's typed target/parameters. Relevant typed
events and the one timed next-step slot request that same evaluation; they
do not create a second trigger or action path. A simultaneous event and due
timer resolve to one descriptor-defined effective target and stable step id
per channel, with ambiguous output abstaining. `normal_exit_contract` is the
terminal rule inside this evaluator. A step selected by an event can release
a `next_reaction_step` hold only with a staged current-state continuation
that survives the mandatory fresh snapshot; Layer 5 retains only a bounded
process-local pending boundary token, never a frozen command or replayable
event. The extraction implementation must specialize this interface for its
start/change/end decisions; its concrete conditions and bounds remain open
CA4-12 work. There is no fan-specific Layer-5 executor or V3 runtime test.

**Managed episode after restart (approved, partial contract):** a descriptor
with a declared ongoing program may opt into resumption only after a fresh
inactive entry and a physically confirmed Heima inactive-to-active edge.
Layer 5 records a compact open/closed per-channel state through Layer 0's
ordinary end-of-cycle batch at episode opening and closure; there is no
per-command flush, periodic write or speed-step update. A committed open
state survives ordinary retention, but a crash before the opening batch
commits leaves no proof. After restart, current Reaction authority, fresh
physical state and current continuation/end rules determine whether a new
activation may act. No hold, old timer, missed step or unobserved learning
interval is restored. At every restart, a channel active on its first fresh valid reading
without usable proof is left untouched regardless of its current trigger and
Layer 5 emits `active_channel_unmanaged_after_restart` through the existing
availability occurrence; Layer 6 owns the resident notice and uses a new
process-run delivery key. Once reported,
the issue persists while the channel remains actively unmanaged, even if
the initiating Sensor ceases to qualify; only a fresh inactive reading or
valid proof resolves it, without a false claim that Heima switched it off.
Heima never infers ownership
from an `already_satisfied` target, a matching external action or a recovery
checkpoint. The earlier one-shot extraction draft had
`managed_episode_resumption=False`; the required Initial-V3 ongoing
specialization declares `managed_episode_resumption=True` and fixed-duration
hold release. Its concrete start/change/end rules remain open CA4-12 work. See the
[CA4-12 restart scenarios](specs/v3/reviews/CA4-12.md); no V3 runtime test ran.

**Room-neutral humidity trigger (approved, partial contract):** the current
descriptor ID is `environment.air_extraction`; its proposed
`humidity_extraction` relation profile is not registered as complete evidence
and policy output yet. The descriptor applies to any registered room with a
compatible extraction fan. It selects exactly one typed relative-humidity
trigger: `level_crossing`, `delta_over_window`, or `rate_over_window` with a
staged positive bounded window for the latter two. Occupancy is a declared
current-room condition only where the configuration requires it. Layer 5 §7
and Layer 3 §6.5 now carry that grammar and its context axes; the profile's
full schema, objective/intent matrix, observed outcome and example remain
open CA4-12 work. The former bathroom/occupied names in the dated L5-12
history above are historical, not aliases for a current descriptor.

**Common environmental transition anchor (approved, partial contract):**
Layer 3 §4.8.1–4.8.2 now permits one profile-declared observed transition on
a staged registered Sensor state or Actuator channel, using Layer 0's
`actuator.channel_state.<digest>` history for the latter. The exact logical
channel, observable-state contract and changed facets are validated; the
first valid post-gap state, a command result and an unrelated facet are not
anchors. Existing cover/opening/HVAC profiles retain their declared physical
meaning. The required Initial-V3 extraction profile and later humidifier or
dehumidifier profiles use the same learner mechanism but must register their
own outcomes, confounders and policies. The
`humidity_extraction` registration remains open; the generic anchor alone
does not authorize a new proposal or action. See the [CA4-12 scenario review](specs/v3/reviews/CA4-12.md).

**Separate estimates for every program phase (approved, partial contract):**
Initial-V3 learning must estimate observed response for physical start,
bounded target modification and termination, not merely retain those edges
as history. The versioned relation profile declares finite, disjoint
`transition_class_id`s with typed pre/post and comparable stable-reference
matchers; `EnvironmentalEpisodeLearner` uses its existing episode, cohort,
artifact and validation paths separately for each class. The
`environmental_response.v1` cell key includes class, profile, context and
horizon. A modification class distinguishes direction and bounded
pre/post target range; no on/speed/off pooling, generic speed branch or
device-specific learner is introduced. Estimates remain conditional
observed contrasts, not automatic command authority. An estimate-dependent
step is suppressed if its exact class/context/horizon cell is ineligible; an
independently declared deterministic step can still pass current admission.
Verified normal exit can close the activation even when its
estimate-dependent terminal target is skipped and reported. This is the
approved general missing-estimate rule; no generic terminal target or
cross-class fallback is inferred. Exact extraction matchers, horizons and
objective/intent registration remain open CA4-12 work. The current candidate's
single objective and member-level numeric threshold do not yet bind a
specific class to each programmed step; a learned multi-step proposal stays
ineligible until that mapping is registered and validated. The
[CA4-12 review](specs/v3/reviews/CA4-12.md) records the residue audit and
cross-kind scenarios; no V3 runtime test ran.

**Learned program decision (approved clarification; partial):** the
developer declares finite legal targets, typed current conditions and
step-to-class mapping. Heima learns the observed response of the exact
physical transition from eligible local histories, including correctly
attributed resident or external actions only where the profile's cohort and
confounder rules allow them. A modification requires both a currently
qualifying need and an eligible conservative response under the reviewed
objective and practical threshold; a favorable historic contrast alone
cannot select a step. The developer does not preassign a speed's extraction
rate or mark later targets indispensable. Current adequacy suppresses an
unneeded modification without changing an independently declared normal
exit. This uses the existing candidate, artifact, program evaluator and
admission path. The exact `humidity_extraction` conditions, matchers,
horizons and objective/intent mapping remain open; this clarification does
not mark CA4-12 DONE. See the [review](specs/v3/reviews/CA4-12.md).

**Whole-bundle frequency decision (2026-10-07; partial):** one routine
output record represents one canonical bundle/context cell, not one member.
Layer 3 now defines the previously missing subject baseline as the fraction
of eligible sliding-window start-time exposure whose full assembly window
contains the complete bundle. The initially written UTC-epoch grid was
rejected because it could split a pattern at an arbitrary boundary; no such
grid remains in the normative routine contract. An offline interval sweep
uses existing event and coverage boundaries, without periodic device
readings. Standard lift is conditional frequency divided by subject baseline
frequency; 1 is no association. An empty or zero baseline gives no finite
lift and cannot qualify a proposal. Overlapping starts are correlated time
exposure, not independent episode support; validation resamples complete
temporal blocks. A baseline window does not create a trigger episode or a
candidate. The same coverage, resident attribution, confounding and
time-partition rules apply to both cohorts. The
[CA4-12 review](specs/v3/reviews/CA4-12.md) records cross-kind and boundary
cases. This resolves the baseline/lift semantics; the output-schema change
below followed, while the catalog remains open.

**Registered-output consolidation (2026-10-07; partial):** the profile's
exact `policy_output_schema_id/version` and validator are the sole measured
effect contract. The descriptor's duplicate `EffectShape`/
`effect_contract_for_intent`, the unused `TypedEffectSummary` union and
profile `effect_contract_id` are retired. No information is dropped:
environmental numeric point/interval/unit/horizon remain in
`environmental_response.v1`; thermal duration bounds remain in
`ThermalResponseParameter`; the new `routine.bundle_frequency.v1` record
retains whole-bundle/context probabilities, `Window` assembly/exposure
durations, trigger counts, calendar diversity and precision/lift intervals,
with a keyed artifact
validation report. Intent compatibility remains in the profile's
`objective_intent_contract_id` and descriptor validators; stable numeric
thresholds remain in `NumericOutcomeRequirement`. A missing routine profile
registration still blocks learned candidate staging. The CA4-12 review has
the exact information mapping and scenarios. CA4-47's old type-definition
record is preserved as history; its current-consumer statement is aligned.

**Slice 12a — `environment.solar_shading` (approved and applied 2026-10-11).** Supported profiles `thermal_shading`/`solar_shading` v"1"; one guard contract `environment.solar_shading.guards.v1` for the direct and learned paths, with `wind` required only for `(increase_shading, exterior_deployable)`; the variant derives from the Actuator's staged `weather_exposed` (new `Actuator.is_external`, IFC `IsExternal` semantics, Layer 2 §6; exposure rule corrected by CA4-62); objective/intent matrix (no `admit_daylight` under `thermal_shading`); one complete direct example and acceptance. Remaining: 12b external exchange (after CA4-62), 12d routine, 12c extraction, 12e cross-descriptor examples. See the [CA4-12 review](specs/v3/reviews/CA4-12.md).

**Slice 12b — `environment.external_exchange` (approved and applied 2026-10-11).** One profile per purpose (`thermal_exchange`, `air_quality_exchange`, `hygrometric_exchange` v"1"); one guard contract `environment.external_exchange.guards.v1` keyed by purpose; new descriptor field `safe_direction_intents` lets a safe-direction variant (`close_to_retain`) have an empty required guard set; objectives `cool_with_outdoor_air`, `warm_with_outdoor_air`, `limit_thermal_exchange` added, and direct-only `close_after_ventilation`; direct trigger is a hysteresis boolean over the purpose quantity, using the new Layer-2 `numeric.difference.v1` for indoor-minus-outdoor temperature or humidity ratio; endpoint must face an exterior side (CA4-62); one direct example and acceptance. Remaining: 12d routine, 12c extraction, 12e examples.

**Slice 12d — `routine.actuation_bundle` (approved and applied 2026-10-11).** Profile `routine_actuation_bundle` v"1" (trigger as one `primary` class, `routine.bundle_frequency.v1`, optional shadow); single objective `reproduce_resident_routine`; both origins; guard contract `routine.actuation_bundle.guards.v1` requiring `presence` for every member and inheriting the environmental safety guards for the same physical action; core-frozen `RoutineEvidenceGateCalibration` and keyed `RoutineValidationReport` reusing the §4.8 temporal block bootstrap; one direct example and acceptance. Remaining: 12c extraction, 12e examples.

**Slice 12c — `environment.air_extraction` (approved and applied 2026-10-11).** Both origins; target `level` 1..N or `off`; intents `activate_extraction`, `adjust_extraction`, `stop_extraction`; program start/step-up/normal end/runtime cap/resident switch-off with staged `start_level`, `max_level`, `settle_window`, `end_level`, `end_dwell`, `max_runtime`; occupancy optional and vacancy never stops the program (developer clarification: the fan also runs while the room is occupied); `humidity_extraction` v"1" with `start`/`modify_up`/`terminate` classes on the `level` facet and humidity-ratio outcome; objectives `reduce_moisture` (start, step-up) and direct-only `end_extraction`; guard contract with no required guard via new `low_risk_intents` (start, step-up) and `safe_direction_intents` (stop). Cross-cutting: `EnvironmentalResponseGateCalibration` fixes horizons and gates for all six `environmental_response.v1` profiles. Remaining: 12e cross-descriptor examples.

**Slice 12e and closure (2026-10-11).** Layer 5 §7.3 publishes the single catalog matrix (descriptor, origins, profiles and output schema, objective/intent, guard contract, program) for the six Initial-V3 descriptors at version "1", with an index of direct examples and learned candidate examples for comfort trajectory, solar shading, air extraction and routine; no example needs a placeholder unit or fictitious effect. Closure criterion met. See the [CA4-12 review](specs/v3/reviews/CA4-12.md); no V3 runtime test ran.

#### CA4-13 — LearnedWindow calibration bypasses the declared learning lifecycle

**Status:** DONE (2026-10-07; specification readiness). **Type:** architectural duplication. **References:** [Layer 0 §3.2](specs/v3/layer0_runtime_spec.md), [Layer 3 §4.4.1, §4.9](specs/v3/layer3_learning_spec.md), [Layer 5 §§3.2, 4.2, 6.0, 7](specs/v3/layer5_action_reactions_spec.md).

**Room-return timing closure (2026-10-07):** `RoomOccupancySurvivalModel.return_delay`
is the first reviewed operational timing target. Layer 3 now permits a
validated action-serving survival artifact with a one-minute first horizon;
Layer 5 binds its typed room `present -> absent` anchor, reads return
cumulative incidence at the staged maximum, and selects a continuous
bounded delay with seed fallback. The generic `routine.actuation_bundle`
descriptor registers an optional one-member vacancy path. It uses the common
Reaction timer, admission and ApplyStep. Each versioned Layer-5 core
intent/channel/adapter translation may declare an exact
`TranslationDelayPermission` with a typed target validator and maximum;
the descriptor stages only a member whose permission matches its path.
This is never inferred from an Actuator role such as `light` and requires
no per-Actuator delay setting. Layer-2 vacancy debounce precedes and adds
to the Layer-5 delay. The [impact and scenario review](specs/v3/reviews/CA4-13.md)
records normal, gap, competing-event, cancellation, fallback and restart
cases; no V3 runtime test ran. Layer 5 §6.0 defines the trigger-driven
replacement job, one-shot admission identity and the translation-permission
check at staging and due time. Bootstrap rejects the Initial-V3 descriptor
if no core translation declares a matching permission; the concrete target
catalog belongs to that versioned core registry, not a device-kind list in
the general specification.

**Current scope (2026-10-06):** the previously selected solar-fraction
forecast `q` is removed from CA4-13's closure requirements and is not an
Initial-V3 timing profile. Sparse local irradiance observations do not
justify treating the next minutes' cloud/exposure fraction as a validated
operational forecast; including post-exit returns in `q` also mismatches a
Reaction whose current occurrence ends on an observed exit. This does not
remove `environment.solar_shading`: its Layer-2 hysteresis and one staged
fixed Layer-5 dwell remain, with the approved in-process gap semantics and
ordinary fresh admission. A movement cooldown remains separate. Historical
solar-`q` exploration and its training-episode proposal are retained only
in [the CA4-13 review](specs/v3/reviews/CA4-13.md), not as a current
registration or required acceptance scenario. CA4-47 subsequently closed the
staged solar-geometry producer for the environmental contracts that actually use it.

The generic `FutureStateFractionOutcome` and bounded selector remain reusable
contracts, but their existence registers no solar timing learner or descriptor
binding. CA4-13 now has a coherent Initial-V3 learned-delay profile, its
eligible model-publication rule, common delayed-trigger job contract and
versioned target-permission rule.
CA4-14 already specifies artifact adoption across egress classes; it is not
reopened by the solar-scope correction.
The Layer-3 validation/shadow, candidate/review, notification-only staging,
common admin promotion and descriptor-required consent sequence already
governs automatic Reactions. Layer 5 §4.2 now defines
`ReactionTimingModelBinding` in the immutable configuration/plan fingerprint;
the artifact revision is excluded. Layer 5 §§4.1–4.2 now define typed
supplemental evidence, initial action-bearing selection and compatible
revision adoption separate from semantic configuration changes.
Layer 5's timing binding now shares the exact typed state and qualifying
values with Layer 3's `FutureStateFractionOutcome`, so a registered
descriptor may use a typed value such as `occupancy=absent` without an extra
projection. The developer approved this generalization; the room-return
path and shared trigger-driven job contract are now specified.
Every delayed Reaction now declares typed timer-gap semantics in its plan:
reset observed dwell, pause verified elapsed time, or count elapsed time after
fresh requalification. The solar path uses the last mode. This removes the
earlier universal reset-on-gap rule. After a process restart the existing
ephemeral-activation/`AtJob` rule applies: no old anchor or job is restored;
a fresh qualifying sustained state starts a full new wait without fabricating
an event edge. The room-return path now uses the common trigger-driven
replacement job and one-shot admission identity.

**Original gap (historical):** Layer 0 allowed `LearnedWindow` wherever a Window is accepted but left history-based calibration to pure FusionRule/SemanticResolver consumers that cannot read history. Layer 3 kept occupancy survival diagnostic-only. CA4-14 has since supplied the artifact-adoption contract; the room-return slice now supplies the operational delayed-trigger path and eligible model publication without historical work on the evaluation path.

**Correction:** any learned delay uses the existing Layer-3 validation/adoption
lifecycle and the common Layer-5 timer; the solar path stays fixed until a
separately reviewed profile/version exists. **Closure:** the room-return
use case has exact versioned translation-owned target permissions, model evidence,
authority, fingerprint, invalidation and the specified trigger-job contract
without historical work on the evaluation path. Solar-`q` publication and
CA4-47 are not CA4-13 gates.

#### CA4-14 — Adaptive adoption conflicts with immutable generations and broad fingerprints

**Status:** DONE (2026-10-06; specification readiness). **Type:** lifecycle mismatch. **References:** [Layer 3 §4.1.2, §4.5, §4.8–4.9](specs/v3/layer3_learning_spec.md), [Layer 5 §4.1–4.2](specs/v3/layer5_action_reactions_spec.md). No V3 runtime test was run.

**Progress:** Layer 5 §4.1 records exact role-tagged supplemental artifact
references in proposal evidence; Layer 3 §6.2 maps them from the candidate.
Layer 5 §4.2 now records action-bearing adopted revisions separately from the
immutable Reaction configuration. A later `pinned` revision gets a distinct
`ReactionArtifactAdoptionProposal` under the same `review_proposal` command;
compatible `bounded_adaptive` revisions append only within the approved
binding/bounds. Layer 3 §4.9 now distinguishes validated diagnostics (no
adoption) and registered live signals (Layer-3 pinned approval or bounded
compatible adoption). Layer 3 §§4.1.2/4.5 now separate the analysis
`definition_fingerprint` from a serving-generation fingerprint, so an
objective/materiality edit preserves the response artifact but changes the
candidate proposal identity. Layer 3 §4.9 and Layer 5 §4.2 now define
authenticated adoption-mode changes that retain the exact current artifact;
entering `bounded_adaptive` revalidates approved bounds, while returning to
`pinned` freezes the current revision. The closed
`("reaction.artifact_adoption", 1)` candidate kind is now registered, so
the Layer-5 review path can admit it. The diagnostic/signal/policy matrix,
serving-only edit, compatible refresh, mode switch, concurrency, crash and
fallback scenarios are reviewed in the
[CA4-14 review](specs/v3/reviews/CA4-14.md).

**Original gap (historical):** Layer 3 permitted automatic bounded parameter/envelope adoption under existing authority while Layer 5 froze plan data and removed authority/consent from successor configurations. The old `pinned` rule incorrectly required Layer-5 proposal handling even for diagnostic/signal-only revisions. Objective/minimum-delta changes were described as serving-only and not requiring artifact invalidation, while the broader definition-fingerprint rule appeared to invalidate artifacts on every definition change.

**Correction:** distinguish training identity, serving identity, and authority; define revision/adoption for each egress. **Closure:** a pinned/adaptive × diagnostic/signal/policy matrix specifies deterministic transitions, including a serving-objective edit and a compatible refresh of an already configured Reaction.

#### CA4-15 — Envelope evidence leaks into semantic deduplication identity

**Status:** DONE (2026-10-05; specification readiness). **Type:** identity inconsistency. **References:** [Layer 3 §6.4–6.6](specs/v3/layer3_learning_spec.md), [Layer 5 §4.1](specs/v3/layer5_action_reactions_spec.md).

`CoverageCell` includes `support` and `calibrated`, and the whole `CanonicalEnvelope` enters the candidate fingerprint. Literal serialization therefore changes semantic identity when support changes, despite the compatible-evidence-refresh rule. Subset checks also need semantic cell keys rather than equality of evidence-bearing records. The §6.6 fingerprint list omits `descriptor_parameters`, which §6.4 includes.

**Correction:** one canonical envelope projection contains ordered axes and exact cell keys while excluding support/calibration evidence; all candidate fingerprint lists include root parameters. **Closure:** support 10→20 preserves proposal identity; a new semantic cell or changed root parameter changes it. Runtime lookup and adaptive subset checks use the same keys. [CA4-15 impact and scenario review](specs/v3/reviews/CA4-15.md) records the cases; no V3 runtime test was run.

#### CA4-16 — Unit drift leaves incorrectly typed quantitative data available to consumers

**Status:** DONE (2026-10-05; specification readiness). **Type:** physical-unit boundary defect. **References:** [Layer 2 §3.3, §4](specs/v3/layer2_registries_spec.md), [Layer 3 §4.8.2](specs/v3/layer3_learning_spec.md), [Layer 5 §7.1](specs/v3/layer5_action_reactions_spec.md).

`NumericInterpretation` does not convert units. A mismatch against the expected unit changes neither availability nor confidence nor value. Thus a source changing from Celsius to Fahrenheit can publish finite `68` through a binding staged as Celsius. Thermal guards and training consume the canonical quantitative contract, without a mandatory mismatch gate in that interface.

**Correction:** a quantitative Sensor stages an exact source/canonical unit contract and a core-registered conversion when needed; missing conversion rejects staging. A later changed/missing applicable HA unit makes the reading unavailable and diagnostic, while unrelated metadata drift remains diagnostic-only. **Closure:** Celsius/Fahrenheit, percentage/fraction, and missing-unit cases cannot generate actions or samples under an incorrect unit interpretation. Attribute paths without applicable HA unit metadata rely on the developer's explicit staged source-unit contract; an unannounced source-scale change is not observable. [CA4-16 impact and scenario review](specs/v3/reviews/CA4-16.md) records the cases; no V3 runtime test was run.

#### CA4-17 — Revocation and rebinding have no common asynchronous dispatch fence

**Status:** DONE (2026-10-04; specification readiness). **Type:** execution lifecycle. **References:** [Layer 2 §2.5, §6.1](specs/v3/layer2_registries_spec.md), [Layer 5 §4.2, §6–6.1, §7.1.2, §8](specs/v3/layer5_action_reactions_spec.md). This does not claim runtime implementation or testing.

**Original gap, now closed:** admission uses a frozen snapshot, while service calls can be submitted after authority or registry changes. The contract needed a generation-aware fence for every HA call, including calls within one `ApplyStep`, and an explicit rule for uncertain outcomes.

**Specification verification:** Layer 5 §6.0 now checks current authority, activation, hold and affected-facet state, and the committed Actuator generation at an in-memory fence immediately before every HA call. The coordinator orders accepted ingress against submission. A changed endpoint cannot receive a call admitted under the old generation; an accepted targeted external edge stops unsent calls, while unrelated changes do not. Layer 5 §6.0.1 keeps uncertain physical outcome separate from call completion and requires a fresh valid read plus current authority before another command; a timeout gives no blind retry or exactly-once claim. Layer 5 §8 now includes a two-call counterexample for revocation, cancellation, rebinding, external edge and timeout. Layer 2 §6 resolves only the registered endpoint at execution. CA4-27 separately retains the cross-layer composition commit/rollback gap.

#### CA4-18 — Programmed Reactions need one stable next-job slot and re-arm rules

**Status:** DONE (2026-10-05; specification readiness). **Type:** scheduling/lifecycle acceptance gap. **References:** [Layer 0 §3.1](specs/v3/layer0_runtime_spec.md), [Layer 5 §3.2, §6.0, §7.1–7.2, §8](specs/v3/layer5_action_reactions_spec.md), [overview](specs/v3/architecture_overview_defined_layers.md), [recap](v3_architecture_recap.md). This does not claim runtime implementation or testing.

**Original gap, now closed.** The former claim that every failed required guard cancels the activation was already superseded: §3.2 returns `not_ended` for temporary input loss or guard veto, and §7.2 distinguishes committed return, valid calendar removal/replacement, valid interval completion, calendar outage and guard veto. The remaining gap was a stable job identity/re-arm rule for a still-active activation when required input went unavailable and later returned. Repeated fresh evaluation could otherwise install duplicate jobs or omit the next eligible step. Presence simulation exposed the gap, but the same scheduling contract applies to comfort trajectory and future step-programmed descriptors; this was a specification risk, not observed runtime duplication.

**Correction:** retain the already defined terminal/nonterminal distinction and add only the missing stable job identity and re-arm/replace rule for a still-active activation after temporary input loss or guard veto. **Closure:** a fake-clock trace with temporary unavailability followed by restored `away` yields exactly one appropriate next job and no missed or duplicated step; committed return terminates that activation; valid calendar replacement, calendar outage and a hold retain their distinct outcomes. Verify §3.2, §7.2 and §7.2.1 together before marking this separate item DONE.

**Approved scope and specification verification.** The developer rejected a light-specific late-off
exception and confirmed that this is a common scheduling problem. Layer 5 §6.0 now gives every
Initial-V3 step-programmed Reaction one activation-stable next-`AtJob` replacement slot, distinct
from the bounded per-channel planned-step identities of one due bundle. An unchanged pending selection keeps its timer;
replacement/cancellation advances a process-local arm revision; a stale or duplicate callback
cannot execute or release a hold. Serialized member admission prevents duplicate commands
even when two evaluations race. Temporary input loss or guard veto keeps the activation,
while a known due hold-release boundary remains available for its non-command evaluation.
Fresh restoration selects at most one descriptor-valid next step; existing missed-step,
normal-exit, hold and follow-up behavior is unchanged. Layer 0 §3.1 defines idempotent owner
cancellation and the callback race boundary. Both Initial-V3 descriptor keys were aligned to
the common slot, with separate presence-simulation and comfort-trajectory fake-clock acceptance
traces; overview and recap summarize the common mechanism.

**Bounded review record:** [CA4-18 impact and scenario review](specs/v3/reviews/CA4-18.md)
traces the approved choice across Layer 0, the common Layer-5 slot, both Initial-V3 descriptors,
hold release and the summaries. Its evidence is textual specification review; the eventual
executable fake-clock suite remains implementation-phase work.

#### CA4-19 — Pending-apply reconciliation has no complete observation contract

**Status:** DONE (2026-09-28). **Review:** the Layer-5 §6.0.1 pending contract and its Layer-0/Layer-3 handoffs were reviewed against the agreed runtime and learning scenarios. **Type:** missing shared execution/observation contract. **References:** [Layer 0 §6, §7.4](specs/v3/layer0_runtime_spec.md), [Layer 5 §6–6.1](specs/v3/layer5_action_reactions_spec.md), [Layer 3 §4.4.2](specs/v3/layer3_learning_spec.md).

Layer 5 explicitly defines successful ApplyStep completion as completion of all service calls. That definition is valid in itself and does not promise physical confirmation. Layer 0 separately relies on pending expected-state matching within a Window to avoid false implicit holds. The shared contract does not close the owner, duration, targeted-facet matcher, partial confirmation, or timeout/unavailability lifecycle of that pending state, nor clearly distinguish it from the completion anchor used by correction learning.

**Correction:** name service completion and observed confirmation separately and define their interaction with hold inference, recovery, and attribution. The provisional contract distinguishes per-facet physical confirmation from HA service completion, skips all calls when a recorded target decision is already fully satisfied, otherwise dispatches the complete core call plan and requires post-dispatch observation for every targeted facet. Failed or timed-out calls remain separate from observed physical state. Partial confirmation can establish a per-facet expectation while the channel lease stays unresolved; full confirmation requires one coherent channel state in which all targeted facets match simultaneously. After a terminal uncertain outcome, a fresh valid read and current-policy decision are required before another command. Correction learning uses a recorded admitted decision and an observed complete target, regardless of call outcome or the verified origin of the matching state; a late matching read may establish a current per-facet expectation for a later hold and a late full-target read may anchor learning, both without revising an `unconfirmed` execution outcome, while merely hypothetical or partial targets are excluded, and repeated evaluations while the complete target remains observed share one learning episode; divergence or observation loss ends it, and a new decision after hold release passes current admission. CA4-09 must provide complete normalized facet history and decision outcomes for this learning contract. **Closure verification (specification, not runtime):** (1) all target facets already match before dispatch: one recorded `already_satisfied` decision, no HA call, later repeated matching evaluations reuse its learning episode; (2) only some facets match: the full core plan runs, each targeted facet needs a post-dispatch read, and a confirmed facet can hold after a later edge while the channel lease remains unresolved; (3) separate facet matches that never coexist remain partial with `target_never_coherent`; (4) service completion/failure/timeout and physical observations remain separate, with no blind replay; (5) after terminal timeout a fresh valid read is required before another command, and a late matching read may establish a current expectation and learning anchor without rewriting the terminal execution result; (6) an unknown or externally produced exact full target may anchor a verified resident correction, while an incomplete target cannot; (7) observation loss and restart invalidate live pending/hold state and require current-policy reconciliation. Layer 3 uses the complete observed target for the count-model window; CA4-09 still owns the durable historical projection needed to implement that model. `git diff --check` passed. CA4-01 is closed by its final cross-layer specification audit; CA4-09 retains the separate durable denominator contract.

**Subsequent closure (2026-10-07):** CA4-09 now defines the normalized channel-state history and target-decision/complete-observation lifecycle required above. The references to CA4-09 as open record the state of this item when it closed on 2026-09-28.

#### CA4-31 — Hold lifecycle events need per-transition idempotency

**Status:** DONE (2026-09-29). **Review:** event-queue identity verified against the channel-hold contract; CA4-38 separately owns bounded queue/degraded behavior. **Type:** identity and retry defect. **References:** [Layer 0 §5.2, §6.4](specs/v3/layer0_runtime_spec.md).

The original finding concerned a hold-specific journal whose `(correlation_id, fact_role)` key could collide for two same-cycle transitions. CA4-01 supersedes that journal and its checkpoint mutation, but the same underlying risk remains for asynchronous lifecycle-event retries: one correlation id may belong to several distinct hold transitions on different channels or successive updates; one multi-facet observation on one channel creates only one transition. A retry must not duplicate an event, and a reused id with different content must not silently erase one.

**Provisional correction:** each `HoldLifecycleValue` has a unique operation id minted per transition, independent of causal `correlation_id`. The queued/in-flight in-memory index compares canonical payloads with no disk I/O and is cleared after durable acknowledgement; the background writer enforces a durable `(fact_type, operation_id)` unique key and compares the payload on collision. A crash before write may lose the final event under the user-approved asynchronous audit contract; no hold is restored from audit.

**Closure verification (specification, not runtime):** one multi-facet observation on one channel yields one hold transition and one operation id; two channel transitions may share a causal correlation but mint distinct operation ids. An exact retry before acknowledgement is coalesced only after canonical payload comparison; after acknowledgement the durable unique key provides the same check. Reuse with different payload is an error. A crash before durable commit may lose the audit event under the approved asynchronous-audit contract; a crash after commit leaves one event, and neither case restores a live hold. Layer 0 §6.1/§6.4 and Layer 5 §6.0 agree on these traces; `git diff --check` passed. CA4-38 retains the separate queue-bound/degraded-retry obligation.

#### CA4-33 — Historical consumers cannot identify observation gaps caused by downtime

**Status:** DONE (2026-10-02; specification closure by Codex after the user authorized parallel CA4-33 work). The 2026-09-30 DONE was premature and omitted shared sample, survival, and environmental consumers; this closure includes them. **Type:** newly identified continuity gap. **References:** [Layer 0 §4.4, §6.4, §13](specs/v3/layer0_runtime_spec.md), [Layer 3 §4.2, §4.4.1–4.4.3, §4.8.1, §5.2, §9](specs/v3/layer3_learning_spec.md), [architecture overview](specs/v3/architecture_overview_defined_layers.md), [recap](v3_architecture_recap.md).

Retention coverage explicitly describes pruning, not whether observations occurred. Restart rules invalidate live prior-cycle state, but no historical process-gap contract tells duration, outcome, and correction-window consumers where observation stopped and resumed. Persisted state before shutdown and after restart can otherwise be joined across an unobserved interval. A gap shorter than a freshness bound is still unobserved; complete retention alone cannot establish a zero-correction or continuous-state window.

**Historical provisional draft, superseded by P1/P2 below:** Layer 0 §4.4 defines one durable process-continuity timeline and a 60-second watermark that advances only after all accepted fact and audit records through its barrier are acknowledged. An orderly stop starts a known gap; after a crash the gap begins no later than the last durable watermark. Startup durably opens the gap, and a fresh valid HA observation closes it. Write failure leaves historical completeness unknown while current-state automation follows ordinary admission. `retention_coverage` remains independent. Layer 3 censors correction and routine assembly windows crossing the gap, including restarts shorter than a freshness bound; matching pre/post states cannot yield a zero or negative sample. Channel-specific `available=False` affects only its dependent windows; unreadable channels are not commanded while readable channels may resume. **Required closure verification, not yet complete:** clean stop, crash with a queued unwritten hold event, repeated failed startup, and a short restart must make every affected duration, outcome, correction, routine, and environmental window incomplete without censoring unrelated later windows. The following P1/P2 decisions supply the type, closed reasons, closure barrier and omitted consumers; the expanded gate and construct matrix still prevent DONE.

**Structural decision CA4-33/P1 — typed historical observation coverage and restart boundary (APPROVED and applied 2026-10-01; consumer-wide verification pending).** Owners: Layer 0 §4.4 defines the historical-read contract and durable process interruption; Layer 3 §4.2 owns shared sample eligibility, with each model owning its event/duration-specific censoring. The present `observation_coverage` string has no type or closed reasons. "First fresh, valid HA observation barrier" could mean one entity has reported, every critical entity has reported, or a completed cycle barrier. Example: Heima restarts at 10:00; at 10:01 HA returns valid light A and an explicit unavailable valve B; a 10:02 learning cycle reads both. Closing the global gap on A's first edge lets one implementation treat B as continuously observed, while waiting for B to recover freezes unrelated light learning indefinitely.

- **Option 1 (recommended):** define one typed `ObservationCoverage` result on every declared historical read, with status `complete|incomplete` and a closed nonempty reason set for incomplete reads: `process_interruption`, `required_stream_unavailable`, `continuity_metadata_unknown`. Keep `retention_coverage` separate. Close the process gap at the first post-restart `CycleInputBarrier` built from a fresh completed HA intake snapshot that exposes valid source health and explicit availability for the staged bindings; the barrier alone is insufficient if it contains only startup timers or cached state. It need not wait for every channel to become readable. A still-unreadable channel is `available=False` and makes only reads requiring it incomplete. For a hard crash, the interruption starts no later than the last all-queue-acknowledged watermark; for clean stop it starts at the final acknowledged observation stop. The closure barrier identity and UTC instant are durable before a historical read may return complete.
- **Option 2:** wait until all registered critical entities are readable. This simplifies one global boundary but prevents unrelated learning for as long as one valve or sensor is broken and contradicts the agreed channel-scoped unavailability behavior.
- **Option 3:** close on the first valid entity edge. This is superficially cheapest but leaves the rest of the HA snapshot indeterminate and cannot prove coverage for other streams.

Option 1 reuses `CycleInputBarrier`, state `available=False`, and the existing stream-scoped history-read idea. It adds one typed return value and no per-Actuator gap journal. Tests must cover clean stop, hard crash after an unacknowledged audit event, failed metadata write, repeated failed startup, short restart, first cycle with only cached state, a fresh intake with one unavailable channel, later channel recovery, retention truncation independently, and equal-time barrier ordering. **Overlap check:** `retention_coverage` measures pruning only; `available=False` measures individual streams; `CycleInputBarrier` already freezes one intake cycle. None alone records a process interruption, so the typed coverage result is necessary but must not duplicate those meanings.

**Structural decision CA4-33/P2 — first incomplete instant (APPROVED and applied,
2026-10-01).** The approved typed `ObservationCoverage` needs a boundary for duration
consumers: status and reasons alone say that a window is incomplete, but cannot tell
`RoomOccupancySurvivalModel` when to right-censor. Example: a room visit starts 09:00,
Heima loses observation at 09:20 and returns 09:25, and the requested horizon ends
10:00. Censoring at 10:00 would falsely count 40 unobserved minutes at risk; dropping
the whole visit loses 20 valid minutes. Layer 0 §4.4 owns the historical-read result;
Layer 3 §4.2/§4.4.1 owns sample/censoring use.

- **Option 1 (recommended):** add `first_incomplete_at: EvidenceInstant | None` to the
  typed coverage result. It is None exactly when complete; otherwise it is the earliest
  process or required-stream gap intersecting the requested interval, clipped to
  the request start when the gap was already open. If metadata is unknown, use
  the request start as a conservative lower bound. A time-to-event
  outcome right-censors at this boundary; point/count outcomes requiring the later
  span reject it. A gap exactly at the requested end is included only under that
  outcome's interval semantics.
- **Option 2:** return every gap interval. This supports more elaborate analysis but
  adds an unbounded collection and overlap rules the initial consumers do not need.
- **Option 3:** return only status/reasons and let each learner query continuity
  metadata independently. This duplicates Layer-0 logic and risks different censor
  boundaries for the same frozen read.

Option 1 solves the earliest-gap problem with one bounded field and no new timeline.
Tests: process gap, unavailable required stream, unknown metadata, equal-time boundary,
retention truncation, and a gap after a valid target event. **Overlap:** the durable
continuity timeline already owns the timestamps but does not expose the first one
through the history-read result; `retention_coverage` cannot supply it. No threshold
or new per-channel journal is introduced.

**Consumer census, read-only review (2026-10-01).** Layer 3 §4.2's shared `SampleBinding` builder must reject an incomplete required feature/outcome window or explicitly right-censor a time-to-event outcome at the first coverage break; a partial event window cannot become a zero event count. §4.4.1 `RoomOccupancySurvivalModel` must right-censor at the first gap rather than treat it as no departure/return or as a competing event. §4.4.2 `CorrectionCountHurdleModel-v1` and §4.4.3 `ActuationRoutinePatternModel-v1` already name process gaps but need the typed read result. §4.8.1 `EnvironmentalEpisode` and its `EnvironmentalReferenceWindow` must reject any required pre-anchor, post-anchor, or exclusion span intersecting the gap; §5.2's training-span inspection must retain the full declared span, exclude gap-crossing samples, and rebuild only when remaining eligible support passes existing gates. Layer 3 §9 and Layer 0 §13 need fixtures for each. No normative consumer changes have been applied pending P1.

**CA4-33 approved application and counterexample review (2026-10-01).** Layer 0
§4.4 now defines `ObservationCoverageStatus`, closed `ObservationGapReason`,
`ObservationCoverage(first_incomplete_at)` and `HistoricalReadResult`; its §13
fixtures check clean/hard restart, metadata failure, fresh-cycle closure,
unavailable channel and endpoint validity. Layer 3 §4.2 consumes coverage in
the shared sample builder; §4.4.1 censors survival at the first gap; §4.4.2
classifies correction censoring; §4.4.3 excludes incomplete routine negatives;
§4.8.1 excludes incomplete transition and reference spans; §5.2 keeps the full
TrainingSpan but excludes affected samples. §9 tests each consumer. Overview and
recap describe the same boundary.

Counterexample T15: a matching occupancy state before and after a two-minute
restart could otherwise add two unobserved minutes to `stay_duration`, produce a
zero correction count or a no-routine negative. The typed gap begins at the last
durable watermark and `first_incomplete_at` censors or excludes each affected
window, even if both states match. A valid target event before the gap remains
observed; a later target event cannot bridge it. Counterexample T19: waiting for
every Actuator would freeze an unrelated light indefinitely, while closing on
light A's first entity edge could falsely certify valve B. The fresh completed
cycle barrier closes only the global gap, and B's explicit unavailability makes
only B-dependent reads incomplete. A cached startup cycle or failed metadata
write cannot certify continuity. These are document traces, not runtime tests.
**Closure verification (specification, not runtime; 2026-10-02).** The expanded
residue gate classified 174 matched lines with zero current-rule residues
(table above). The complete field-level matrix covers all three
`ObservationCoverage` and all three `HistoricalReadResult` fields with producer,
consumer and acceptance fixtures. A touched-section reread cross-checked Layer 0
§4.4/§13, Layer 3 §4.2/§4.4.1–4.4.3/§4.8.1/§5.1–5.2/§9, the overview and recap.
The read found and corrected a shared-builder ambiguity: an absent event means
zero only for a complete event window; with a coverage break, the sample is
excluded or right-censored at `first_incomplete_at`. T15 and T19 now pass their
counterexample traces, including a short restart, unreadable valve, readable
light, valid target before a later gap, and a cached cycle that cannot close it.
`git diff --check` passes. This closes the downtime-observation contract; the
the 2026-10-02 oversized hold-audit detail-reference path was superseded by
CA4-01's approved 2026-10-03 bounded inline fact rule;
the historical continuity contract remains independent of audit representation.

#### CA4-34 — Fusion input validation permits repeated votes from one fact

**Status:** DONE (2026-10-04; specification readiness). **Type:** staging omission. **References:** [Layer 2 §2.3–2.4, §5.1, §5.5, §9](specs/v3/layer2_registries_spec.md). This does not claim runtime implementation or testing.

**Original gap, now closed:** `FusionRule.inputs` had to be non-empty but was not required to contain distinct references. A weighted quorum with inputs `(A, A)`, default weight 1, and threshold 2 satisfied the former numeric checks and could count the same True observation twice. Repetition similarly inflated availability populations. The physical formula's correlation-group protection does not apply to generic quorum/unanimity strategies.

**Specification verification:** Layer 2 §2.3 makes Sensor/Fusion registry ids unique independently of output claims. §2.4 rejects repeated `(fact_type, where, previous_cycle)` keys in one FusionRule, while permitting shared dependencies across different fusions and the already-authorized current/prior self-memory pair of a FormulaStrategy. §9 accepts that legitimate pair and rejects `(A, A)` before a quorum or availability floor can count it twice.

#### CA4-36 — Environmental formulas require configuration that Layer 2 prohibits

**Status:** DONE (2026-10-05; specification readiness). **Type:** cross-layer contradiction. **References:** [Layer 2 §2.4, §5.3](specs/v3/layer2_registries_spec.md), [Layer 3 §4.8.2–4.8.3](specs/v3/layer3_learning_spec.md). This does not claim V3 runtime implementation.

Layer 2 says every current formula except `physical_evidence.weighted_evidence` requires `configuration=None`. Layer 3 requires a core FormulaStrategy with staged immutable opening identity/orientation for solar exposure, and permits explicit installation reference pressure for humidity-ratio derivation. At least the specified per-opening solar formula cannot carry its required configuration through the written staging rule.

**Correction:** register the required typed configuration contracts or model those values as explicitly typed inputs; align the closed formula catalog and validation rules. **Closure:** a per-opening solar calculation and both supported pressure-source forms stage with complete reproducible inputs and no undeclared configuration escape hatch. This is a configuration-contract defect, not a claim that the illustrative solar equation is physically incorrect.

**Specification verification:** Layer 2 registers closed `environment.solar_incidence.v1` and `environment.humidity_ratio.v1` configurations with staging checks for topology orientation, binding identity, typed inputs and exclusive pressure-source choice. Layer 3 references the same contracts. Layer 2 §9 exercises two opening orientations, invalid bindings and both pressure forms. The scenario matrix and implementation boundary are in [CA4-36](specs/v3/reviews/CA4-36.md); the solar-geometry fact producer was completed in CA4-47.

### P2 — Medium

#### CA4-20 — Monotonic deadlines and UTC history ordering have unresolved edge cases

**Status:** DONE (2026-10-10; specification readiness). **Type:** undefined temporal behavior. **References:** [Layer 0 §3.1, §4.0–4.1, §9](specs/v3/layer0_runtime_spec.md), [Layer 4 §9.3](specs/v3/layer4_domain_spec.md).

A monotonic countdown cannot unconditionally preserve an absolute UTC deadline across wall-clock correction, despite the “cannot fire early, late” wording. Layer 0 permits distinct cycles with equal `when`, while the presence adapter requires `last_available_when < observed_at`; telemetry also describes equal-time facts as one cycle. Clock rollback needs an explicit relationship between append order, current state, and historical event time.

**Correction:** distinguish elapsed and civil deadlines and specify equal-time/rollback semantics. **Closure:** a fake clock exercising forward/backward adjustment and equal-time cycles preserves one-shot firing, valid episode identity, and the declared historical ordering.

**Approved resolution (2026-10-10).** Every `AtJob` declares `basis="elapsed"` or `"wall_clock"`; a clock discontinuity greater than 1 second re-arms pending wall-clock jobs against their unchanged due, firing a passed due once (20a/A). Every cycle receives `max(wall_clock_reading, previous_cycle_instant + 1 µs)`, so distinct cycles never share an instant and recorded history never moves backward, including across restart (20b/A). Relaxing the presence adapter to `<=` was considered and rejected because equal-time groups, episode keys and backward clocks would still conflict. A forward jump or a backward jump over 1 second records a process-wide `clock_discontinuity` observation gap (20c/A). Owners: Layer 0 §3.1/§3.5/§4.4; dependents Layer 2/3/4/5, overview, recap. See the [CA4-20 review](specs/v3/reviews/CA4-20.md); no V3 runtime test ran.

#### CA4-21 — Historical aggregates and tier-specific requiredness are underspecified

**Status:** DONE (2026-10-11; specification readiness). **Type:** incomplete shared algorithm. **References:** [Layer 3 §4.2–4.3](specs/v3/layer3_learning_spec.md), [Layer 0 §4](specs/v3/layer0_runtime_spec.md).

The shared `mean`, `rate`, `true_duration`, and sequence resolvers do not fully define duration weighting, interpolation, boundaries, and gap handling on write-on-change history. Separately, rejecting a sample when any required feature is missing can prevent the promised coarser-tier fallback when a rich-tier dimension is absent. Requiredness is not clearly scoped to the entire sample or the selected tier.

**Correction:** define canonical resolver semantics and requiredness per applicable tier. **Closure:** a trace with unequal state durations and a missing rich-only feature has one reproducible training/serving result and an explicit fallback decision.

**Approved resolution (2026-10-11).** (a) One resolver for training and serving: zero-order hold, no interpolation; state aggregates over `[T - window, T]` from the as-of state at `T - window`, time-weighted `mean`, `true_duration` in seconds, `minimum`/`maximum` including the value at `T`; any invalid portion makes the feature missing. `event_count` and sequences use `(T - window, T]`; sequences order equal-time items canonically and keep the most recent `max_items`. `rate` is removed as redundant. (b) Requiredness is scoped to the consumers that read a feature: a dimension of only some tiers excludes the sample from those tiers only; features of every tier, non-tier inputs and the outcome stay sample-wide. Applied in Layer 3 §4.2/§9; see the [CA4-21 review](specs/v3/reviews/CA4-21.md); no V3 runtime test ran.

#### CA4-22 — Signal timestamp admission and expiry wakeups are incomplete

**Status:** DONE (2026-10-11; specification readiness). **Type:** timing/routing gap. **References:** [Layer 3 §6.3](specs/v3/layer3_learning_spec.md), [Layer 4 §5.1, §6](specs/v3/layer4_domain_spec.md).

`emitted_at < snapshot.when < expires_at` rejects a signal stamped at the receiving cycle's timestamp. The order of serving publication relative to that barrier is not closed. Although expired signals must be rejected on evaluation, no owner is assigned to wake evaluation when an admitted signal expires; a materialized assisted claim can otherwise remain visible until another event/fallback cycle.

**Correction:** define boundary inclusivity, publication ordering, and expiry-triggered reevaluation. **Closure:** same-time emission has a declared admission result, and expiry retracts the assisted conclusion under an explicit timing guarantee without depending on incidental external activity.

**Approved resolution (2026-10-11).** (1) Signal inference runs inside the cycle, after Layer-2 facts and before Layer 4, on the frozen intake; `emitted_at` is the cycle instant and admission is `emitted_at <= snapshot.when < expires_at`. (2) Layer 3 arms one replaceable `elapsed` Layer-0 `AtJob` per (contract, subject) at the emitted signal's `expires_at`; its due requests a fresh evaluation, so an assisted conclusion never outlives its signal. A signal belongs only to its emitting cycle; startup replays no expiry callback. Applied in Layer 3 §6.3/§9 and Layer 4 §5.1/§6/§10; see the [CA4-22 review](specs/v3/reviews/CA4-22.md); no V3 runtime test ran.

#### CA4-23 — The literal numeric parser regex is double-escaped

**Status:** DONE (2026-10-04; specification readiness). **Type:** executable documentation error. **References:** [Layer 2 §4](specs/v3/layer2_registries_spec.md).

The inline regex had written the decimal separator as `\\.` rather than `\.`. Inline Markdown does not decode string-literal escaping, so compiling the old printed regex literally did not accept `12.5` as intended.

**Correction and verification:** Layer 2 §4 now prints the directly usable regex and specifies a full-string match; its acceptance text names decimal, exponent and signed cases. A read-only Python check copied the expression from the Markdown and verified `12.5`, `.5`, `1e-3`, `+2`, `-0.25`, and `1.` match, while empty, `.`, `1,2`, surrounding whitespace, incomplete exponent, `NaN`, and a literal backslash do not. This is a specification check, not a runtime implementation test.

#### CA4-24 — ApplyStepSource actor identity contradicts operational minimization

**Status:** DONE (2026-10-04; specification readiness). **Type:** residual schema conflict after CA2-4/CA3-4. **References:** [Layer 0 §5](specs/v3/layer0_runtime_spec.md), [Layer 5 §4.2, §6](specs/v3/layer5_action_reactions_spec.md).

Layer 0 explicitly gives `ApplyStepSource.actor_id` the identity of the person/service authorizing the action. Layer 5 includes that source but forbids actor/resident identity in ApplySteps and execution audit, restricting it to governance/configuration records.

**Correction:** remove/prohibit that operational identity field for V3 or define an allowed non-identity governance reference, consistently across both layers. **Closure:** resident/admin attribution remains auditable in the ledger without copying identity into operational projections.

**Verification.** Layer 0 §5 no longer defines `ApplyStepSource.actor_id`; fact and action provenance
retain only actor category, source and correlation identity. Layer-5 governance transitions retain
authenticated actor attribution. Layer 0 §13 acceptance rejects actor identity in an `ApplyStep`
or execution audit while permitting correlation with the governance decision.

#### CA4-25 — Closed diagnostic namespaces do not cover all required outcomes

**Status:** DONE (2026-10-11; specification readiness). **Type:** incomplete vocabulary. **References:** [Layer 3 §6.3.1](specs/v3/layer3_learning_spec.md), [Layer 5 §4.0, §5.2, §7.1.1, §7.2](specs/v3/layer5_action_reactions_spec.md).

The Layer-5 registry declares two evaluation codes and only `late_recovery` for execution audit. Other requirements call for closed outcomes for stale administrative preconditions, unauthorized actors, late simulation jobs, cancellation, and alternative selection without fully assigning those codes and schemas to an owning namespace. Existing ApplyCall failures and automation-suppression reasons do not automatically define administrative and descriptor audit outcomes.

**Correction:** map each required outcome to its actual registry/code/schema, including first-use states with no artifact. **Closure:** every acceptance scenario can emit a declared typed result without inventing a string or an ArtifactRef; diagnostics remain distinct from resident notification.

**Approved resolution (2026-10-11).** No new registry: the existing `Layer5DiagnosticRegistry` (Layer 5 §4.0) gains `GovernanceCommandRejectionCode` and a typed `GovernanceCommandResult` (`applied`/`idempotent_replay`/`rejected`) for every common and descriptor-specific governance command. `ReactionExecutionAuditCode` is extended with descriptor-neutral codes (`late_step_skipped`, `stale_callback_discarded`, `future_work_cancelled` with a `cause_ref` to the existing exit/authority/generation record, `alternate_bundle_selected`, `bundle_skipped_no_admissible_alternative`, `fallback_served_without_artifact` with `artifact_ref=None` at first use); each descriptor declares its emitted subset. Results go only to Layer 8 and audit; resident output remains follow-up and availability occurrences. See the [CA4-25 review](specs/v3/reviews/CA4-25.md); no V3 runtime test ran.

#### CA4-26 — Admin-authored simulation recurrence conflicts with HA schedule authority

**Status:** DONE (2026-10-10; specification readiness). **Type:** undeclared exception. **References:** [Layer 0 §3.1](specs/v3/layer0_runtime_spec.md), [Layer 3 §8.4](specs/v3/layer3_learning_spec.md), [Layer 5 §7.2](specs/v3/layer5_action_reactions_spec.md).

Layer 0 assigns administrator-authored recurrence to HA `schedule.*` and prohibits duplicated authoring/DST evaluation. Presence simulation instead takes an administrator-authored `WeeklyRecurrence` and derives sessions from it. CA2-2 establishes that this is not a CronEntry, but does not reconcile the broader schedule-authority rule.

**Correction:** use the HA authority or explicitly scope the core session exception, including overlapping sessions. **Closure:** recurrence has one declared authority and deterministic behavior across DST, timezone edits, midnight, and overlapping occurrences.

**Approved resolution (2026-10-10).** The administrator records only the absence in the calendar; lights, density and session window are configured in the presence-simulation Reaction, an ordinary Reaction activated by the calendar absence and stabilized `away`. Layer 0 §3.1 now limits HA-schedule authority to standalone schedules and admits a descriptor-declared time-window parameter that never activates anything by itself. Layer 5 §7.2 fixes session start (existing DST policy), elapsed end, midnight crossing, staging rejection of overlap and timezone-change behavior; the session boundary job is `wall_clock`. A `schedule.*` helper or recurring calendar event as session source was considered and rejected. Hybrid learning direction confirmed: PS-1 stays (Initial V3 unlearned) and the `TemporalActuationProfileModel` is the intended successor, always bounded by the configured window and lights (Layer 3 §8). See the [CA4-26 review](specs/v3/reviews/CA4-26.md); no V3 runtime test ran.

#### CA4-27 — Per-layer atomic reloads do not define a cross-layer commit

**Status:** DONE (2026-10-10; specification readiness). **Type:** incomplete configuration lifecycle. **References:** [Layer 2 §2.5](specs/v3/layer2_registries_spec.md), [Layer 3 §4.1.2, §5.2](specs/v3/layer3_learning_spec.md), [Layer 4 §4.2, §8](specs/v3/layer4_domain_spec.md), [Layer 5 §4.2](specs/v3/layer5_action_reactions_spec.md).

Each layer specifies an atomic swap, but the composition lacks a common commit/rollback rule when a valid producer edit invalidates downstream consumers. Removed/disabled semantic claims have no explicit terminal historical publication, and transitive impact propagation is not fully specified. Persisted `effective_at` also needs a clear relationship to activation completed before a crash.

**Correction:** define the composition barrier, invalidation/terminal outputs, and restart from a committed generation. **Closure:** removing or relocating a producer used by a resolver and Reaction leaves neither mixed generations nor an orphaned available historical claim.

**Approved resolution (2026-10-10).** Every configuration mutation in Layers 2–6 activates as one composed generation whose durable manifest write is the activation and `effective_at` (D1/A). Staging builds a dependency index from staged declarations and classifies every other consumer as breaking, semantic-only or unaffected; a nonempty impact record requires a commit carrying the reviewed base generation and `impact_fingerprint` (D2/iii). Breaking dependents are invalidated in the same commit: learning definitions and artifacts unavailable, state resolvers emit one terminal unavailable fact, Reactions get a disabling authority transition, cancelled jobs and the derived `configuration_invalid` mode until a valid successor that needs fresh promotion and consent (D3). Semantic-only changes keep dependents and only list them (D4). A bootstrap code upgrade applies the same rule under the system actor. The developer required the future Layer 6/7/8 interfaces to state their part explicitly; the overview records publication-generation, plugin dependency and impact-preview obligations. Owner: Layer 0 §4.7; dependents Layer 2 §2.5, Layer 3 §4.1.2, Layer 4 §8, Layer 5 §4.2. See the [CA4-27 review](specs/v3/reviews/CA4-27.md); no V3 runtime test ran.

#### CA4-28 — Recursive immutability and invalid-evidence handling are inconsistent

**Status:** DONE (2026-10-10; specification readiness). **Type:** data-boundary ambiguity. **References:** [Layer 1 §3–4.3 and acceptance](specs/v3/layer1_substrate_spec.md), [Layer 0 §4.1, §6.2–6.4](specs/v3/layer0_runtime_spec.md).

A frozen dataclass plus copied nested dicts/lists prevents neither nested mutation by a consumer nor alteration of a shared snapshot. The recursive freeze requirement is explicit for canonical JSON elsewhere but not equivalently closed for HouseFact payloads. Layer-1 acceptance also requires rejection of NaN in evidence while the fail-soft evidence rule replaces invalid evidence with `{}`; the rejected object must be identified. A canonical checkpoint layout would make depth compliance verifiable, but the earlier assertion that the bound itself makes those records impossible is not retained.

**Correction:** specify deep immutability, depth counting, and whether invalid evidence rejects only evidence or the whole fact. **Closure:** consumer mutation cannot change shared data; admitted hold checkpoints round-trip within bounds; NaN evidence has one specified outcome.

**Approved resolution (2026-10-10).** Construction freezes `value`, `evidence` and retained `PersistedProjection`s recursively in the existing validation pass; equality uses canonical bytes and the wire form is unchanged (28a/A). One collection-depth rule applies to all three: scalars 0, each enclosing collection +1, maximum 2 (28b). A non-finite number in `evidence` discards only evidence with a diagnostic; in `value` it rejects the fact (28c/A). The hold-checkpoint clause no longer applies because CA4-01 removed that checkpoint. Owners: Layer 1 §3/§4.3/§10; dependent Layer 0 §4.1/§6.4. See the [CA4-28 review](specs/v3/reviews/CA4-28.md); no V3 runtime test ran.

#### CA4-32 — Successful hold journaling conflicts with the no-I/O evaluation path

**Status:** NOT_APPLICABLE (2026-09-29; owner: Codex). **Review sequence:** CA4-01 was set to TODO/awaiting while CA4-32 alone was IN_PROGRESS; this item was revalidated, then CA4-01 resumed as the only IN_PROGRESS item. CA4-01 removes the hold-specific journal; the user approved asynchronous lifecycle audit with an explicit crash gap. The original finding was revalidated against the current queue and no narrower CA4-32 ordering defect remained. **Type:** newly identified protocol-ordering conflict. **References:** [Layer 0 §4, §6.4, §8](specs/v3/layer0_runtime_spec.md).

The mandatory journal protocol orders append/`fsync` before live-state update and end-of-cycle enqueue. Hold inference occurs on the evaluation path, which elsewhere must not perform disk I/O. Only the write-failure branch explicitly moves retry to the background and keeps suppression live. The successful path lacks an equally explicit asynchronous handoff and ordering contract.

**Disposition (updated 2026-10-03):** the premise no longer exists. Layer 0 §4.1–4.2 accepts a complete validated changed event into the memory buffer and ordinary ordered durable queue without disk I/O on evaluation; CA4-01's bounded inline hold audit follows that rule. §6.2 updates live admission before durable audit completion, and §6.4 puts the lifecycle fact through the ordinary queue without a hold checkpoint or hold-specific `fsync`. A slow successful or failed background write cannot delay the live hold update; a crash before write may lose the event by the approved audit-gap rule. The original required journal ordering is historical and superseded by CA4-01. The still-unbounded retry queue is CA4-38, not a residual CA4-32 journal protocol. This is a document-level verification, not a runtime test.

#### CA4-35 — Empty routine outcomes are both rejected and needed as negative samples

**Status:** DONE (2026-10-04; specification readiness). **Type:** newly identified sampling contradiction. **References:** [Layer 3 §4.4.3](specs/v3/layer3_learning_spec.md).

Episode construction rejects an empty resulting bundle. The estimator then requires a complete observable trigger window with no matching resident bundle to be a negative observation. A fully observed window with no resident control is such a negative, but its empty episode has already been rejected. The text does not separate invalid positive-candidate bundles from valid no-action denominator observations.

**Correction:** retain complete empty outcomes as explicitly typed negative observations while continuing to prohibit empty actionable candidates. **Closure:** no-action, different valid bundle, ambiguous control, and unobserved window affect precision/lift denominators according to one declared rule, without conditioning the denominator on some action having occurred.

**Verification.** Layer 3 §4.4.3 now retains a complete no-control window under the closed
`no_resident_control` training tag, while only a non-empty `resident_bundle` can become a positive
episode/candidate. Exact matches are positive; other valid bundles and no-control windows are
negative for an eligible candidate. Incomplete, ambiguous, confounded or unavailable candidate
windows are excluded. Acceptance covers all four outcomes and prevents a no-action candidate.

#### CA4-37 — Mixed empty/non-empty keyword lists admit an always-matching category

**Status:** DONE (2026-10-04; specification readiness). **Type:** validation contradiction. **References:** [Layer 2 §4, §9](specs/v3/layer2_registries_spec.md). This does not claim runtime implementation or testing.

**Original gap, now closed:** staging rejected a category with no non-empty normalized keyword, while matching applied substring membership to each normalized keyword. A category containing `["", "vacation"]` therefore passed the old written category check and the empty substring matched every supplied summary. Acceptance already required an empty normalized keyword to be rejected.

**Specification verification:** Layer 2 §4 now rejects an empty category list and every individually empty normalized keyword, including whitespace-only entries mixed with valid entries, before matching. Layer 2 §9 acceptance names those cases and verifies that no rejected mixed list can classify an unrelated summary. The existing matching rule and priority order are unchanged.

#### CA4-38 — The durable retry queue has no resource bound or overflow policy

**Status:** DONE (2026-10-10; specification readiness). **Type:** newly identified degraded-mode resource gap. **References:** [Layer 0 §4.0–4.3, §8](specs/v3/layer0_runtime_spec.md).

Failed durable batches retain their ordered facts for retry while new in-process facts continue to advance. Memory-buffer and durable-store limits do not specify a limit for this separate pending queue. During a prolonged storage outage, continuing non-coalescible events can therefore grow it without a declared bound. The contract cannot simultaneously guarantee unlimited retention of failed writes, finite memory, and uninterrupted admission without specifying a degradation choice.

**Correction:** declare the queue budget, retry ordering, overflow/degradation policy, and corresponding lost-history coverage reporting. **Closure:** a prolonged failed-store scenario stays within the declared resource policy and never reports dropped events or gaps as durably complete history.

**Approved resolution (2026-10-10).** The queue budget is `max(32 MiB, 5% × effective memory limit)`, exactly 32 MiB when no enforceable limit is known, recomputed only with a new health snapshot and revisable from evidence. On ordinary overflow Layer 0 first collapses superseded queued state transitions (keeping the latest per key), then drops the oldest queued events; it never blocks admission and preserves continuity boundaries. CA4-70 defines the exceptional case in which these protected items alone exceed the budget and the subsequent progressive recovery. Each loss extends one bounded per-stream interval committed as a `queue_overflow` gap when storage returns; the watermark advances only past declared losses. Owner: Layer 0 §4.6 with §4.4/§8/§9/§10; dependent Layer 3 §4.4.2. See the [CA4-38 review](specs/v3/reviews/CA4-38.md); no V3 runtime test ran.


### Later P1/P2 findings — priority stated on each entry

#### CA4-39 — Runtime confirmation lacks a lifecycle contract

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P1. **Origin:** R5. This does not claim V3 runtime implementation. **Original gap:** Layer 0 referred to an active runtime confirmation request and checkpointed its transitions without defining identity, expiry, response races or restart authority. **Specification verification:** Layer 0 §7.4.1 defines one typed request per recovery episode/channel, a 24-hour core ceiling, current-proposal invalidation, serialized response recheck, terminal outcomes, immediate checkpoint acknowledgement, and rejection of every pre-restart id. Layer 5 §8, overview and recap use the same boundary. The scenario review is [CA4-39](specs/v3/reviews/CA4-39.md); it separates request authority from physical command confirmation and hold restoration.

#### CA4-40 — Calendar consumer bypasses the frozen view

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P1. **Origin:** B1. This does not claim runtime implementation or testing. **Original gap:** Layer 2 §3.1 told a predictive Layer-4/5 consumer to query `upcoming_starts_within` directly, while Layer 0 §4.1 and Layer 4 §5.1 require Layer 5's staged `FrozenCalendarView`. **Specification verification:** Layer 2 §3.1 now sends only the Layer-5 policy through its staged `CalendarViewRequirement` and frozen `DecisionSnapshot`; Layer 4 transports the view without classifying it. Layer 0 §3.4/§4.1 already owns cache prefetch, freeze and immutable requirement reads. Layer 5 §8 now rejects a mid-cycle direct query or horizon expansion after the barrier and checks a later cache refresh cannot alter that cycle's decision.

#### CA4-41 — Initial semantic episodes are both absent and required

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P1. **Origin:** B2. This does not claim runtime implementation or testing. **Original gap:** Layer 4 §3.1 said no initial resolver emits `SemanticEpisode`, while §9.3 defined `presence.departure`/`presence.return` as occurrences consumed by Layer 5. **Specification verification:** Layer 4 §3.1 and §9 now register exactly one initial casa `presence` transition adapter producing those two types under §9.3's identity, continuity and restart rules. Layer 4 §10 acceptance tests both transitions, unchanged/unavailable input, startup seeding and rejection of unregistered initial episode producers. No generic state-to-event mirror was introduced.

#### CA4-42 — Descriptor consent requirement is not declared

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P1. **Origin:** B3. **Original evidence:** Layer 5 §4.2 permitted `ReactionAuthorityTransition.household_consent=None` only without a descriptor consent gate, but `RegisteredReactionDescriptor` did not declare that gate. Layer 5 §3.2 mapped consent to `action_guard_active` while Layer 3 §6.3.1 excluded authority decisions from availability occurrences. **Decision:** the registry declares frozen `requires_household_consent` per descriptor version; the developer requires consent for the three environmental descriptors, both programmed descriptors and the generic routine, all six Initial-V3 descriptors. **Closure:** the exact descriptor property controls consent-field shape and common authority projection; missing/revoked consent and admin disablement block action without an availability occurrence or false guard-failure code. [CA4-42 impact and scenario review](specs/v3/reviews/CA4-42.md) records all six; no V3 runtime test was run.

#### CA4-43 — Comfort trajectory mode selection is incomplete

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P1. **Origin:** narrower B4. **Original evidence:** Layer 5 §7.1 permitted one `HvacTrajectoryBinding` to declare both heating and cooling, possibly on one channel, without a mode selector. **Developer decision:** one explicit desired mode from a fixed admin selection or staged typed current fact; observed `off` must not prevent a permitted recovery start. **Closure:** each `(scope, mode)` Reaction is eligible only when its mode equals the one desired mode in the frozen snapshot; unavailable/ambiguous desired mode abstains, and conflicting active physical modes block safely. Shared-channel and separate-endpoint scenarios are in [CA4-43 impact and scenario review](specs/v3/reviews/CA4-43.md). No V3 runtime test was run.

#### CA4-44 — Common Reaction authority lacks common Layer-8 commands

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P1. **Origin:** B5. **Original evidence:** Layer 5 §7.1.1 named staging, promotion, consent and disablement commands only for comfort trajectory; other descriptors claimed the common authority lifecycle without callable operations. **Closure:** Layer 5 §4.2 now defines one typed Layer-8 command surface for all six descriptors, with exact generation/authority preconditions, authenticated actor, operation-id retry, atomic failure, and shared promotion/consent/disablement. Comfort prerequisite staging remains its sole descriptor-specific preparation command; §7.1.1 no longer registers duplicate aliases. Exact diagnostic-result vocabulary remains CA4-25. [CA4-44 impact and scenario review](specs/v3/reviews/CA4-44.md) records the cases; no V3 runtime test was run.

#### CA4-45 — DecisionSnapshot omits frozen recovery authority input

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P1. **Origin:** B6. This does not claim V3 runtime implementation. **Original evidence:** Layer 0 §7.4 required current recovery state and target baseline, but Layer 4 §5.1's `DecisionSnapshot` carried neither. **Specification verification:** Layer 0 now freezes a `FrozenRecoveryView` with state, episode and CA4-03 per-channel baselines; Layer 5 freezes current `FrozenReactionAuthorityView`; the coordinator attaches both to `DecisionSnapshot` at the common barrier and includes their fingerprints in `snapshot_id`. Layer 4 transports them opaquely, Layer 5 uses them without a later mutable read, and the dispatch fence still rejects post-barrier revocation. The [CA4-45 review](specs/v3/reviews/CA4-45.md) covers retry, unreadable input and post-barrier changes.

#### CA4-46 — Resident-control and correction events lack reserved claims

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P1. **Origin:** B7. **Original evidence:** Layer 0 §4 reserved three other event types but omitted `actuator.resident_control` and `actuator.correction`; Layer 1 §3.1 did not identify them. **Verification:** Layer 0 §4 now reserves exclusive event claims for the Layer-0 ingress and Layer-5 attribution producers, with their exact value contracts owned by Layer 0 §5.1.1 and Layer 5 §6.1. Layer 1 §3.1 identifies both as audit/learning event facts, not rendered `HeimaEvent`s. Layer 0 §13 rejects another owner's overlapping claim at staging. This closes claim ownership and event shape; CA4-09 retains its separate correction-evidence semantics. **Closure:** one exclusive producer and event/value claim per fact type; collisions rejected at staging.

**Subsequent closure (2026-10-07):** CA4-09 now defines the correction-evidence semantics separately owned by that item. The resident-control event retains the exact three-field value contract established here.

#### CA4-47 — Referenced contract types and solar producer are missing

**Status:** DONE (2026-10-07; specification readiness). **Severity:** P1. **Origin:** B8. This does not claim V3 runtime implementation or testing.

**Original gap.** Layers 0/3/4/5 used `HistoryViewRequirement`, `ScopeKind`, `TimeRange`, `UncertaintySummary`, `OperatingEnvelopeRef`, `TypedEffectSummary`, `PhysicalOccupancyReference`, `EffectShape`, `ActuationBundle`, `LocationSet`, `SemanticAvailabilityContract`, `ClaimParameterSchema`, and `ActivityEvidenceSlot` without complete owner definitions. Layer 3 required `external.solar_elevation`/`external.solar_azimuth` from an unnamed core Layer-2 producer.

**Correction.** The owner contracts now define the current names; `PhysicalOccupancyReference` reuses the same-room `occupancy.physical` `FactSlot` and physical provenance, while CA4-48 already replaced `LocationSet` with `Location`. The two future-only hypothesis fields reuse a bounded JSON object and `CanonicalEnvelope`, with publication still gated on a future registered uncertainty schema. Two core-generated Layer-2 Sensors read one `sun.sun` snapshot, convert its degree attributes to canonical radians, gate freshness and range, and exclusively claim the casa solar facts. The per-opening formula retains its separate orientation; its direct component is zero below the horizon. The [CA4-47 impact and scenario review](specs/v3/reviews/CA4-47.md) records normal, unavailable, recovery, concurrence and authority cases. Verification is specification-only; no V3 runtime test has run.

#### CA4-48 — Scope forms duplicate Location semantics

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P2. **Origin:** B9. **Original evidence:** Layer 3 §4.1.1 and Layer 4 §4.2 used `LocationSet` and `house` beside Layer 1's `Location(scope="rooms")` and `casa`. **Closure:** both staging paths now use the one Layer-1 `Location`/`LocationKey` contract and fingerprint resolved zone membership; equal explicit physical scopes cannot acquire a second spelling. [CA4-48 impact and scenario review](specs/v3/reviews/CA4-48.md) records the cases; no V3 runtime test was run.

#### CA4-49 — Activity and version identifiers lack one canonical vocabulary

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P2. **Origin:** B10. **Original evidence:** Layer 4 §3.1 illustrated `activity.work` while the defined profile is `working`; Layer 3 §4.4.4 used `sleep` beside Layer-4 `activity.sleeping`. Those two phrases now use `activity.working` and current `presence=away`, respectively, without inferring a house-wide sleep claim from room activity. Layer 5 §3/§3.1 now owns exact, distinct wire forms: the outer candidate kind version is JSON integer `1`, while the Initial-V3 relation-profile version is JSON string `"1"` in an exact `RelationProfileRef` object. Layer 3 §6.4 and Layer 5 §8 use those forms and reject coercion or `profile_id@version` as wire input. **Closure:** exact version serialization is declared at the owning contracts with no alternate accepted spelling.

#### CA4-50 — Quiet-hours guard is referenced without a registered capability

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P2. **Origin:** B11 narrowed. **Evidence:** Layer 5 §3.2/§6 includes quiet-hours among guard/admission causes but its bootstrap capability inventory had no quiet-hours entry or other declared owner. **Closure:** identify the typed owner, current input and applicable suppression behavior or remove the unsupported guard reference. Other B11/B12 editorial drift remains within CA4-29/30 and is not duplicated here.

**Approved resolution:** the shared `ReactionGuard` registry now includes
`quiet_hours.v1` with separate version field `"1"`. It reads only the exact
casa-scoped Layer-2 boolean state `quiet_hours.active` from the frozen snapshot;
an HA `schedule.*` helper can supply that state through the existing binding and
interpretation path. Only descriptor intents that declare the capability are
blocked by active or unverifiable quiet hours. Layer-6 notification quiet hours
remain a separate future routing contract. The current presence-simulation
guard contract id also uses the approved `.v1` form, while earlier `@1` mentions
above remain historical decision text. [CA4-50 impact and scenario review](specs/v3/reviews/CA4-50.md)
records the evidence; no V3 runtime test has run.

**Appendix B triage:** B1–B3, B5–B10 are confirmed as the findings above. B4 is narrowed to mode selection; its asserted unavoidable two-Reaction conflict is rejected because one binding can contain both modes. B11's quiet-hours contract becomes CA4-50; its stale references/headings belong to CA4-30. B12 belongs to CA4-29/30. No other Appendix-B claim is treated as a CA4-01 correction.

#### Post-CA4-01 full reread findings (2026-10-04)

A complete line-by-line reread of Layer 0–5, the overview, both PlantUML diagrams, the CA4-01
serialization examples and the recap after CA4-01 closure found CA4-51–60. Each item is new: it is
not covered by an open CA4 entry, except where an entry explicitly says it extends one. Four of them
(CA4-52, CA4-56–58) come from one cross-cutting check: **V3 generalizes what V2 specialized per device
domain.** The shared mechanism is `Actuator` + `ActuatorChannel` (`channel_kind`, observable-state
contract, actuation adapter), one `ApplyStep` protocol, one channel hold, one `ReactionDescriptor`
mechanism and generic learners. A descriptor may legitimately specialize *behavior* (presence
simulation and comfort trajectory are different policies); it must not reintroduce specialization by
*device type* or turn a common mechanism into a descriptor-private one.

**Working rules for these items.** Read the cited lines in full before editing. For an item marked
**Decision required**, first show the developer the problem with the concrete example given, then the
listed options weighed for simplicity, effectiveness and real resolution, and wait for an explicit
choice; do not pick silently. Prefer the smallest correction that removes the contradiction; do not
introduce a new subsystem, registry or type when an existing one can express the rule. Every change
updates the owning acceptance criteria and every dependent reference (overview, recap, examples).

#### CA4-51 — Release mode is undeclared for the two step-programmed descriptors

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P1. **Origin:** 2026-10-04 reread. The developer explicitly chose `next_reaction_step` for both Initial-V3 step-programmed descriptors. This does not claim runtime implementation or testing.

**Original problem, now closed.** A channel hold is released either after `fixed_duration` or at the owning activation's
`next_reaction_step` (Layer 0 §6.1–6.2, Layer 5 §6.0). Layer 5 previously fixed the mode only for the four
trigger-driven descriptors ([Layer 5:1533–1537](specs/v3/layer5_action_reactions_spec.md)). The two
remaining Initial-V3 descriptors, `security.presence_simulation` (§7.2) and
`environment.planned_comfort_trajectory` (§7.1), have both prerequisites for `next_reaction_step`
(stable future step identity and a versioned `normal_exit_contract`) and both mention an "active
next-step hold" (Layer 5:1725, Layer 5:1992–1994), yet neither declared which release mode it used.

**Former consequences.** (a) Layer 2 requires `Actuator.hold_duration` only when a channel is staged for a
fixed-duration Reaction (Layer 2:1670–1677), so staging could not decide whether a light or HVAC
Actuator used only by these descriptors needed `hold_duration`. (b) The old light and HVAC fixtures in
[CA4-01 serialization examples](specs/v3/ca4_01_serialization_examples.md) used
`release_mode="fixed_duration"` with `expires_at`; the approved mode requires `expires_at=null` and
a non-null `anchor_step_id`, now applied in those fixtures.

**Example.** Presence simulation turns the living-room light on at 20:00 (episode 3, step 1) and
plans a switch-off at 21:10 (step 2). At 20:20 the resident dims it. Under `next_reaction_step` the
hold lasts until step 2 at 21:10, which then releases it and switches the light off. Under
`fixed_duration` with a 30-minute `hold_duration` the hold expires at 20:50 and the 21:10 step is an
ordinary step.

**Approved decision.** Both descriptors declare `next_reaction_step`. Lights/HVAC used only by them
need no `hold_duration`; a fixed-duration Reaction on the same Actuator still requires one. The
other considered options were fixed duration for both, or different modes per descriptor.

**Specification verification.** Layer 5 §3.2 declares one descriptor-version-fixed
`hold_release_mode` and validates the existing plan compiler's bounded timed-step identities plus
`normal_exit_contract`. Its §7.1/§7.2 descriptor entries declare the approved mode and stable step
identity rules; §8 exercises different/repeated target steps, guard veto, normal exit, anchor and no
expiry. Layer 2 §6 acceptance confirms the `hold_duration` condition. The
[serialization examples](specs/v3/ca4_01_serialization_examples.md) now have non-null prior scheduled
anchor ids, per-facet step ids and null expiry for light/HVAC. A JSON round-trip/byte-length check
recomputed all nine payloads: light 1827/707/909 bytes, hypothetical valve 1289/638/804 and HVAC
1345/681/862, each depth two. Hold transition operation ids are distinct from hold ids. CA4-18
remains open for the separate next-job re-arm behavior after temporary presence loss.

#### CA4-52 — Presence simulation admits endpoints by `actuator_role`, which Layer 2 forbids

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P1. **Origin:** 2026-10-04 generalization check. This does not claim runtime implementation or testing.

**Original problem, now closed.** Layer 2 says `actuator_role` is a coarse, open-string hint for lookup convention and
sibling discovery only, and is "never ... used as an unstaged Reaction admission vocabulary"
([Layer 2:1542–1549](specs/v3/layer2_registries_spec.md)); admission is by registered
`channel_kind` and adapter (Layer 2 §6.1). Layer 5 §7.2 nevertheless requires each presence-simulation
endpoint to have `actuator_role="light"` ([Layer 5:1938–1940](specs/v3/layer5_action_reactions_spec.md)).
This reintroduces device-type specialization through a free string.

**Example.** A smart plug driving a floor lamp exposes a registered `light_state`-compatible channel
but carries `actuator_role="switch"`; it is rejected although its channel contract qualifies. A
mistyped role `"Light"` silently excludes a real light; a wrong role `"light"` on a non-light switch
passes the role check.

**Correction.** Admit an endpoint by its registered `channel_kind`, observable-state contract and
adapter compatible with the descriptor's `light_state` intent, plus the administrator's explicit
selection (already required). `actuator_role` may only suggest candidates in the Layer-8 picker.

**Specification verification.** Layer 2 §6 describes role as a discovery/UI hint, not a Reaction
lookup or admission key. Layer 5 §7.2 stages only an explicitly selected compatible channel and
adapter; §7.2.1 accepts a qualifying room lamp with role `switch` and rejects role `light` without a
compatible channel. A search across Layer 3/5 found no other role-based admission. Overview and
recap carry the same summary. Descriptor-specific deterrence behavior remains, while the generic
Actuator capability boundary stays device-agnostic.

#### CA4-53 — "One consumer per signal type" contradicts the shared assist signal type

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P2. **Origin:** 2026-10-04 reread. This does not claim runtime implementation or testing.

**Original problem.** Layer 3 §6.3 said an `InferenceSignal` type "identifies exactly one allowed semantic
resolver" ([Layer 3:2602](specs/v3/layer3_learning_spec.md)); Layer 4 §3 and §6 repeat "sole
consumer" for the type ([Layer 4:37, 235](specs/v3/layer4_domain_spec.md)). The one initial type
`indirect.semantic_assist.v1` is routed to two resolver kinds, `room_occupancy` and `activity`
(Layer 4 §6 table), through distinct `IndirectAssistanceContract`s.

**Correction.** Uniqueness belongs to each frozen `(signal_type, contract_id/version)` and its one
resolver kind, claim-parameter tuple and legal scope kinds; an instance's exact subject scope is
checked by the existing routing index. The shared signal type remains unchanged.

**Specification verification.** Layer 3 §6.3 and Layer 4 §3/§6 now state the same contract-level
rule. Layer 3 §9 and Layer 4 §10 acceptance reject routing one contract to two resolver kinds,
wrong claim parameters or an incompatible subject scope, while distinct contracts may reuse the
one signal type for `room_occupancy` and `activity`.

#### CA4-54 — Two canonical encodings for instants and durations

**Status:** DONE (2026-10-07; specification readiness). **Severity:** P2. **Origin:** 2026-10-04 reread.
This does not claim runtime implementation or testing.

**Original problem.** Layer 1 defines `EvidenceInstant` as UTC with six fractional digits and the literal
`+00:00` offset ([Layer 1:302, 313–319](specs/v3/layer1_substrate_spec.md)); Layer 0 uses `Window`
(float seconds) for durations and its acceptance requires `Window` wherever a duration field exists
([Layer 0:1912–1914](specs/v3/layer0_runtime_spec.md)). Layer 3 serializes artifacts with RFC 3339
`Z` instants and integer-millisecond durations ([Layer 3:632–633](specs/v3/layer3_learning_spec.md)),
types its dataclasses with `datetime`/`timedelta` (for example Layer 3:183, 226, 613, 2625) and uses
`Window` in the same layer for `max_ttl` (Layer 3:1165).

**Original counterexample.** The same instant serialized as `2026-10-04T08:00:00.000000+00:00` in a fact and
`2026-10-04T08:00:00Z` in an artifact manifest: two canonical byte forms for one value, so a
fingerprint that crosses the boundary (evidence span, `valid_until`, `evidence_through`) is
implementation-dependent.

**Approved rule, reaffirmed.** Solution A was already the project rule: every declared V3 instant
uses Layer-1 `EvidenceInstant`, including artifact manifests, and every positive elapsed duration
uses Layer-0 `Window` with canonical seconds. The former A/B options reopened an approved decision
in error. Layer-3 `Z` instants and integer-millisecond durations are removed as contract encodings;
millisecond calculations inside a selector are temporary arithmetic. A zero point-outcome horizon
uses `None`; civil weekday/hour/minute coordinates remain local calendar components.

**Closure and verification.** The Layer-1 and Layer-0 owners state the single encodings; affected
Layer-0–5 fields, Layer-3 artifact/result contracts, acceptance, overview and recap use them.
The [CA4-54 impact and scenario review](specs/v3/reviews/CA4-54.md) checks fact/artifact identity,
model horizon, zero horizon, calendar/DST and selector arithmetic. This is textual contract and
scenario evidence; the V3 runtime is not implemented.

#### CA4-55 — A checkpoint write failure is mapped onto `degraded_recovery`

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P2. **Origin:** 2026-10-04 reread.

**Problem.** Layer 0 §7.1 defines `degraded_recovery` as "many entities are currently unavailable"
([Layer 0:1650](specs/v3/layer0_runtime_spec.md)); §7.3 says a failed checkpoint replacement keeps
the dirty flag for retry and emits a diagnostic (Layer 0:1681–1684). §8 instead says Recovery treats
the next cycle "as if still `degraded_recovery`" after a checkpoint write failure (Layer 0:1812–1814).
One classification therefore has two unrelated meanings, and consumers of `RecoveryState` cannot tell
an outage from a storage problem.

**Correction.** Choose one rule: a checkpoint write failure is a persistence diagnostic with retry
(the §7.3 rule) and leaves `RecoveryState` untouched, or, if a conservative signal is really needed,
it uses an explicit separate diagnostic/capability rather than `degraded_recovery`. Align §8 with §7.

**Closure.** `degraded_recovery` has the single §7.1 meaning; §7.3, §8, §10 and acceptance agree on
checkpoint-failure behavior.

**Verification:** [CA4-55 impact and scenario review](specs/v3/reviews/CA4-55.md) checks
the normal-input/write-failure and unavailable-input cases against Layer 0 §7.1, §7.3,
§8, §10 and acceptance. This is specification review, not V3 runtime testing.

#### CA4-56 — A concrete HVAC target contract is defined inside the registry specification

**Status:** DONE (2026-10-04; specification readiness). **Severity:** P2. **Origin:** 2026-10-04 generalization check. This does not claim runtime implementation or testing.

**Original problem, now closed.** Layer 2 is the device-agnostic registry. Its §6.1 defined the concrete
`hvac_state.trajectory_setpoint.v1` facet set, value domain and exclusions
([Layer 2:1654–1661](specs/v3/layer2_registries_spec.md)), which is Layer-5 target-contract content
for one descriptor. Each future descriptor would then add its own device paragraph to Layer 2,
recreating per-device specialization in the generic layer.

**Correction.** Layer 2 retains only the generic registered-channel, observable-state, adapter and
bounded-facet contract. Layer 5 §7.1 is the sole owner of the concrete HVAC target schema.

**Specification verification.** Layer 2 §6 no longer names the HVAC target id or defines its facets.
Layer 5 §7.1 defines exactly `mode`/`setpoint_c`, permitted heating/cooling modes, finite bounded
Celsius setpoint and excluded facets; its deterministic acceptance rejects incompatible channel or
adapter bindings and malformed targets. No second device-specific action path was introduced.

#### CA4-57 — The common guard mechanism is named and framed as environmental

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P2. **Origin:** 2026-10-04 generalization check. **Decision approved:** rename to `ReactionGuard*`.

**Problem.** `EnvironmentalGuardCapability`, `EnvironmentalGuardContract`,
`EnvironmentalGuardProfile(Generation)` and `EnvironmentalGuardCapabilityRef` (Layer 5 §3.2) are the
guard mechanism for every descriptor, including the security/lighting
`security.presence_simulation.interior_lighting@1` contract (Layer 5:218–221) and its `presence`
capability. The name ties a common mechanism to one domain and invites a second, parallel guard
mechanism for non-environmental descriptors.

**Options.** (A) Rename to a neutral `ReactionGuard*` family across Layer 3, Layer 5, overview and
recap (no backward compatibility constraint). (B) Keep the names but state explicitly in Layer 5 §3.2
that they are the sole common guard mechanism for all descriptors. Recommendation to present: A.

**Closure.** One guard mechanism with a name and definition that do not imply a domain; no
descriptor needs or defines a second guard mechanism.

**Verification:** [CA4-57 impact and scenario review](specs/v3/reviews/CA4-57.md)
checks the single registry across environmental, security and routine descriptors.
Historical decision quotations above retain the former names; current Layer 3/5
contracts use `ReactionGuard*`. No V3 runtime test was run.

#### CA4-58 — Profile-specific learned outputs become cross-layer types

**Status:** DONE (2026-10-05; specification readiness). **Severity:** P2. **Origin:** 2026-10-04 generalization check. **Decision approved:** one profile-registered output schema.

**Problem.** The thermal profile introduces its own cross-layer dataclasses,
`ThermalResponseParameter` and `ThermalEvidenceGateCalibration` (Layer 3 §4.8), consumed by Layer 5
§7.1. That is acceptable for one profile, but the specs give no rule for the next one: each new
relation profile could add its own Layer-3→Layer-5 type, gate type and validator, which is the V2
pattern of one bespoke pipeline per feature.

**Options.** (A) Keep typed per-profile outputs, but require each to be a schema registered by its
`RelationProfileRef` (output schema id/version in the relation-profile registry) and consumed only
through that registration, so adding a profile adds a registered schema, not a new contract path.
(B) Leave as is and record the rule only as guidance. Recommendation to present: A, applied to the
existing thermal types without changing their fields.

**Closure.** The relation-profile contract states how a profile publishes a policy-consumable output;
the thermal types are expressed through that rule; no Layer-5 code path is specific to one profile's
output type beyond the descriptor that declares it.

**Verification:** [CA4-58 impact and scenario review](specs/v3/reviews/CA4-58.md)
checks the exact profile/schema/artifact hand-off and distinguishes the thermal
release calibration from a learner-produced output. Layer 3 and Layer 5 acceptance
name the shared path. No V3 runtime test was run.

**Related extensions (no new ID).** CA4-44 is extended: promotion, household consent, consent
authority and disablement are common `ConfiguredReaction` authority (Layer 5 §4.2), but Layer 5
§7.1.1 defines them as comfort-trajectory commands. The closure of CA4-44 must define one common
command set reused by every descriptor, keeping only `stage_comfort_trajectory_prerequisite_generation`
descriptor-specific. CA4-12 covers the original environment-shaped candidate
gap; its per-member numeric/effect fields were partially corrected on
2026-10-07, while the profile/objective catalog remains open.

#### CA4-62 — Topology does not distinguish outdoor spaces

**Status:** DONE (2026-10-11; specification readiness). **Severity:** P2. **Origin:** developer review during CA4-12a (2026-10-11). **References:** [Layer 1 §7](specs/v3/layer1_substrate_spec.md), [Layer 2 §6](specs/v3/layer2_registries_spec.md).

Rooms are opaque ids and the only exterior is the reserved `outside` node, so an outdoor area such as a terrace or garden cannot be a registered space. IFC classifies every space `INTERNAL`/`EXTERNAL` and openHAB nests `Terrace`/`Garden` under an `Outdoor` location; V3 has no equivalent. Until resolved, an outdoor area is modeled as `outside`. **Correction:** decide the Room-registry owner and an indoor/outdoor space classification, then its effect on derived `connection_type`, `weather_exposed`, casa presence/occupancy, thermal learning inputs, external exchange and lighting/presence simulation. **Must precede CA4-12b.**

**Approved resolution (2026-10-11).** V2's room model was reviewed against IFC, gbXML/EnergyPlus and openHAB and not carried 1:1. One physical model serves every consumer: each room's `enclosure` (`interior`/`exterior`, IFC `IfcSpace` semantics, read from the room inventory with default `interior`); `other_side` on every opening, windows included (default `outside`); passable connections only for `door`/`door_window`; `Actuator.is_external` for the device. V2's stored `connection_type` and override (a security alarm-boundary classification) are removed; functional room labels drive no rule. Consumers use derived queries defined once in Layer 1 §7 (`opening_faces_exterior`, thermal-envelope membership). Purpose-specific groupings are Zones with a closed core role (`thermal_envelope`, default all interior rooms; `security_perimeter`, reserved), following `IfcZone`. Exterior rooms are part of casa presence; indoor learning slots bind only thermal-envelope rooms; presence simulation admits exterior-room lights only explicitly; `weather_exposed` is corrected for plain windows and exterior rooms. See the [CA4-62 review](specs/v3/reviews/CA4-62.md); no V3 runtime test ran.

#### CA4-63 — No V3 descriptor protects exposed actuators from weather

**Status:** DONE (2026-10-11; specification readiness). **Severity:** P2. **Origin:** developer review during CA4-12b (2026-10-11). **References:** [Layer 5 §7](specs/v3/layer5_action_reactions_spec.md), [Layer 2 §6](specs/v3/layer2_registries_spec.md).

V2 has a `weather_safety` reaction that closes openings and retracts exterior awnings on wind or rain. V3 guards only veto an opening or deployment; no Initial-V3 descriptor closes or retracts when the hazard arrives. **Correction:** decide a descriptor (e.g. `safety.weather_protection`) acting on `weather_exposed` Actuators and exterior-facing openings, with its hazard inputs, safe-direction targets, restore behavior and priority over other Reactions. To be decided after CA4-12.

**Approved resolution (2026-10-11).** New seventh Initial-V3 descriptor `safety.weather_protection` (Layer 5 §7.4): direct only, one Reaction per hazard with a Layer-2 hysteresis trigger whose exit threshold ends the hazard; explicit staged endpoints limited to `weather_exposed` Actuators; intent `secure_for_weather` declared safe-direction with a core-fixed safe target per channel kind and no required guard. A resident hold is respected with a `manual_hold_active` warning (no preemption); no automatic restore; no runtime confirmation, with a Layer-6 notice of the securing action. Matrix, consent lists and counts updated. See the [CA4-63 review](specs/v3/reviews/CA4-63.md); no V3 runtime test ran.

#### CA4-119 — Manual control mixed how and who

**Status:** DONE (2026-10-19; specification readiness). **Severity:** P1. **Origin:** guest model D6 (`docs/v3_people_model_draft.md`).

**Problem.** `actuator.resident_control` was emitted only for residents, so a guest's or tablet's manual control left no record of who acted; `HoldOrigin` `resident_manual`/`admin_manual` mixed how with who, and a resident who is also an administrator was excluded from learning as `admin_manual`.

**Approved resolution (2026-10-19).** Layer 0 §5 `ControlActor` (`resident`, `guest`, `device`, `administrator`, `physical`) derived from `UserActor` or the approved physical adapter. `actuator.manual_control` replaces `actuator.resident_control` for every verified manual control; origin `manual` replaces `resident_manual`/`admin_manual`, with `HoldLifecycleValue.manual_actor`. Layer 5 `manual_override` with `control_actor`. Layer 3 accepts only `resident` and `physical` as resident evidence; other classes are confounders. Layer 8 explanations show origin and, to residents and administrators, the coarse actor. CA4-01 examples recomputed. See the [CA4-119 review](specs/v3/reviews/CA4-119.md); no V3 runtime test ran.

#### CA4-118 — Every non-administrator was a resident

**Status:** DONE (2026-10-19; specification readiness). **Severity:** P1. **Origin:** guest model (backlog open question 5, `docs/v3_people_model_draft.md`).

**Problem.** V3 had no person classification. The Layer-0 ingress mapped every non-administrator to `resident`, a Layer-6 recipient link made a Layer-8 resident, and consent authority accepted any HA user, so a guest with an account or a guest-room tablet counted as a resident; an administrator's response was recorded as `admin_command`, mixing path and actor; a B2B administrator who is not a resident was indistinguishable from the household.

**Approved resolution (2026-10-19).** Layer 2 §2.8 `Person(ha_person_id, household_role resident|guest, ha_user_id)` classifies HA persons, stored and committed like `Room`; unclassified persons and users with no Person count for nothing. Layer 0 §5: `UserActor(household_role, ha_admin)` with two independent axes, `actor_type="user"`/`"physical"`, `user_response` replaces `resident_response`; ingress `admitted_actors` (`resident`, `admin`). Owners: recovery confirmation admits residents and, as a last resort after 2 hours or with no resident recipient, a non-resident administrator; consent and advisory feedback admit residents only. Layer 5: consent authority references resident Persons with an HA user; reclassification needs dispositions. Layer 6: recipients reference a Person, `residents` derives from it, a recipient without a Person must be an administrator. Layer 8: roles from the two axes, new People section and `people` addresses. See the [CA4-118 review](specs/v3/reviews/CA4-118.md); no V3 runtime test ran.

#### CA4-117 — Global overflow closure raced with nonblocking admission

**Status:** DONE (2026-10-17; specification readiness). **Severity:** P2. **Origin:** Layer 0 implementation review (`docs/v3/reviews/GLOBAL_CLOSURE_COMMIT_RACE_20261017.md` in the implementation worktree).

**Problem.** Layer 0 §4.6 required both nonblocking admission and that any overflow loss while the closure boundary is being established leaves the same global epoch open. With one serialized writer, a loss admitted during the closing COMMIT cannot be durably reflected before that COMMIT without making admission wait on storage; a crash between the COMMIT and the new loss's persistence leaves no trace of it in the epoch row.

**Approved resolution (2026-10-17).** Boundary-position rule: a failed write or loss of an item at or before the closure boundary B aborts the closure; the closing transaction starts only after everything at or before B is durable or declared lost, so later overflow can only discard items after B. Such a loss before the closure is durable opens a new global epoch (always global, own first-loss and invalidation boundary), persisted after the closure record and before any later retained item; the §4.4 watermark cannot pass it meanwhile. A crash between the closure COMMIT and that opening uses the existing process-interruption rule. Admission never waits for the COMMIT; the blocking same-epoch alternative was rejected. Diagnostics count closures followed by an immediate new epoch; §13 adds the race and crash-injection criteria. See the [CA4-117 review](specs/v3/reviews/CA4-117.md); no V3 runtime test ran.

#### CA4-116 — Residents could not adjust their own notifications

**Status:** DONE (2026-10-17; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** Every recipient setting (endpoints, language, audiences) and the only family option (household silent during quiet hours) were administrator configuration in the Layer-6 generation; a resident could not change language, mute a family or skip a device for themselves.

**Approved resolution (2026-10-17).** Layer 6 §5.4: per-recipient `RecipientPreferences` (locale, family level `default`/`quiet_silent`/`off` for `attention`, `suggestion`, `governance`, disabled endpoints with at least one kept) in a Layer-6 store outside the composed generation, saved at once with a revision check by the person for their own recipient or by an administrator. `locale` moves from `NotificationRecipient` to the preferences. Open actionable requests and `safety` are never filtered; personal and household levels combine, most restrictive winning. A record whose every recipient opted out retires with cause `recipient_preferences`, without fallback, and administrators are warned. Layer 8: "My preferences" in the resident Notifications section and `notifications/set_preferences`. Personal quiet-hour schedules deferred. See the [CA4-116 review](specs/v3/reviews/CA4-116.md); no V3 runtime test ran.

#### CA4-115 — Diagnostics could be viewed but not downloaded

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** System rendered every layer's diagnostics, but nothing defined a file an administrator could download and hand to a developer or a script, nor its redaction, bounds or behavior while Heima is in error.

**Approved resolution (2026-10-16).** Layer 8 §14.1: one builder behind the System "Download" button and HA's standard "Download diagnostics"; the `diagnostics` query gains a `window` (24 h default, 7 days). JSON `heima_diagnostics_v1` with per-owner sections: versions, active generation and full configuration, everything System renders, health and recovery, map layout, and windowed decisions, apply outcomes, holds, errors, availability episodes and rejected commands; no raw fact history or learning datasets. Personal data and secrets become in-file stable pseudonyms; Heima ids and `entity_id`s stay. 5 MB cap with `truncated` markers, `section_error` per failing section, available with health `error` and without a manifest, administrators only. See the [CA4-115 review](specs/v3/reviews/CA4-115.md); no V3 runtime test ran.

#### CA4-114 — The guided first start never showed the house map

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** The first start configured rooms and topology without ever showing the result as a map, so a wrong connection, floor or orientation surfaced only later, after devices and automations depended on it.

**Approved resolution (2026-10-16).** Layer 8 §11: a map check step between topology and devices. It shows the §9.3 proposal over the active generation, the §9.6 checks with "Fix" links into the topology form inside the procedure, three plain-language prompts and the optional editor. It never blocks. It has no configuration of its own: shown while topology is applied and no device is registered, passed otherwise; afterwards the view stays at `/heima/house/map`. §9.11 lists no open map topic. See the [CA4-114 review](specs/v3/reviews/CA4-114.md); no V3 runtime test ran.

#### CA4-113 — No map outside the panel, and no map for users without a role

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** The map existed only in the panel, so a wall tablet or dashboard could not show it; and an HA user with neither role, typically a tablet's dedicated user or a guest account, saw only "Heima is not set up for you".

**Approved resolution (2026-10-16).** Layer 8 §4: the house map is open to every authenticated HA user; a user with no role sees the Overview with the map only, in resident wording, without explanations or other sections (§15.1 updated). §9.14: Heima's own `custom:heima-map-card`, auto-registered, the same component as the Overview map, map only; options `floor`, `controls`, `control_rooms` (control limited to listed rooms, explicitly not a security boundary because HA has no per-entity permissions) and `idle_reset`; resynchronization on reconnection and compact §5.2 states. §13: `overview` and `subscribe` accept any HA user for the map part; `subscribe` also carries layout revisions. A per-HA-user control scope and the guest model are deferred (§9.11; open question 5). See the [CA4-113 review](specs/v3/reviews/CA4-113.md); no V3 runtime test ran.

#### CA4-112 — The map had no pan and zoom behavior on phones

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** §5.3 let the map scroll inside its own frame but defined no zoom, no gesture split between map panning and page scrolling, no single-pointer alternative to dragging in the editor (WCAG 2.5.7) and no view state rules.

**Approved resolution (2026-10-16).** Layer 8 §9.13: fitted-width initial view with a minimum scale that keeps 44-pixel device targets; pinch zoom, one-finger pan only beyond the fitted view, no double-tap zoom; always-visible zoom/fit buttons, arrow and +/− keys, Ctrl/⌘+wheel; range up to 3× with glyph-only device groups below a threshold; in edit mode drag on a box moves it, on empty space pans, plus §9.9 move and size buttons; zoom and pan are client-only, reset on floor switch, and a floor badge or room address centers the room; reduced motion jumps. §9.11 no longer lists pan and zoom as open. See the [CA4-112 review](specs/v3/reviews/CA4-112.md); no V3 runtime test ran.

#### CA4-111 — The panel had no phone or accessibility requirements

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** Layer 8 said nothing about phone widths, touch, the back gesture, keyboard use, screen readers, contrast or text scaling, although residents use the panel mostly from the HA companion app; the map had no non-graphic equivalent.

**Approved resolution (2026-10-16).** Layer 8 §5.3: usable from 360 CSS pixels without horizontal page scroll, HA's breakpoints and components, 44×44 touch targets, every view an address so back works, WCAG 2.2 AA (keyboard, roles and names, grouped polite live announcements, no information by color alone, 200% text, reduced motion), logical CSS properties for future right-to-left locales. §9.12: an equivalent map list view with the same states and §9.8 controls, without editor. Acceptance: axe-core per section, keyboard-only paths, 360-pixel and back-gesture tests. See the [CA4-111 review](specs/v3/reviews/CA4-111.md); no V3 runtime test ran.

#### CA4-110 — Runtime error: undefined end of write failure and colliding transition identities

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 0 implementation review (`docs/v3/clarifications/RUNTIME_HEALTH_CA4109.md` in the implementation worktree).

**Problem.** CA4-109 said "durable writes are failing" without saying which observed success ends it (a reconnect, a read, an empty commit or one small write could each be mistaken for recovery), nor how open/setup failures and a closed writer's refusals are reported. Its `operation_id` over `[run_id, episode_sequence, phase, causes]` gave equal ids to distinct transitions that return to earlier causes (A, A+B, A, A+B), so the outbox would treat a real change as a retry or reject it.

**Approved resolution (2026-10-16).** Identity is `[run_id, transition_sequence]`; phase and causes are content; `episode_sequence` removed. Only `error_opened` and `restored` are delivered; `causes_changed` is audit only. Write outcomes come from actual durable writes (mutating transactions, including their connection setup); reads, setup without pending writes, empty commits and closed-writer refusals are not outcomes. `persistence_write_failing` holds while a write kind has retained failed work, or no durable write has committed since the latest failure. A per-kind rule without retained work was rejected: a failed one-shot write (a generation apply) would keep a false error for days. Requiring every failed kind to succeed again was likewise rejected. A rule clearing on any success was rejected because one permanently failing kind would flap. See the [CA4-110 review](specs/v3/reviews/CA4-110.md); no V3 runtime test ran.

#### CA4-109 — Heima's own error state reached nobody unless the panel was open

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** CA4-108 follow-up.

**Problem.** Health `error` (no active manifest, failing durable writes) was only a Layer-8 projection and a published entity; no Layer-6 kind existed, so an administrator learned of it only by opening the panel or automating the entity. The predicate lived in Layer 8 although both causes are Layer-0 facts.

**Approved resolution (2026-10-16).** Layer 0 §10.1 owns the runtime error condition (`no_active_manifest`, `persistence_write_failing`) and emits `RuntimeHealthOccurrence` (`error_opened`, `causes_changed`, `restored`; per-run episodes) outside any cycle to Layer 6 and to Layer 8's health projection, which now share one predicate. New Layer-6 kind `system.health`: administrators, family `attention`, severity `error`, one fixed tag, link `/heima/system/health`. With failing storage the phase is delivered once best effort from memory (existing Layer 0 §4.5 rule); with no active manifest it reaches the fallback `persistent_notification`. `degraded` does not notify. See the [CA4-109 review](specs/v3/reviews/CA4-109.md); no V3 runtime test ran.

#### CA4-108 — The panel had no defined behavior when Heima is unreachable, starting or unhealthy

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** Layer 8 defined the health projection (`ok`/`degraded`/`error`) and Layer 0 hands it the recovery state, but nothing said what either role sees when the backend is unreachable, the live subscription drops, Heima is starting or recovering, no configuration exists yet, or health is degraded or in error.

**Approved resolution (2026-10-16).** Layer 8 §5.2: one table of seven situations with administrator and resident rendering; a single banner, the most severe (error, unreachable, recovery, starting, degraded); dimmed last values with their update time when the live subscription drops; residents see no degraded banner and never codes. The health projection now also takes recovery-state changes. A Layer-6 `system.health` notification for administrators was raised and left for a separate decision. See the [CA4-108 review](specs/v3/reviews/CA4-108.md); no V3 runtime test ran.

#### CA4-107 — Configuration suggestions had sources but no surface

**Status:** DONE (2026-10-16; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** Layer 1 (Zone suggestions from HA labels and Topology), Layer 2 (rooms from HA areas, `EnvironmentalDiscoveryCandidate`, sibling roles by `device_id`) defined suggestion-only sources "for the admin panel", but Layer 8 never said where they appear, how one is accepted, or what dismissing does.

**Approved resolution (2026-10-16).** Layer 8 §6.5: a closed list of four sources shown in House and Devices, computed on demand by a slow-path `suggestions/list` from the active generation and HA registries, never stored or evaluated. Accepting opens the prefilled add form with every admin decision mandatory and yields an ordinary `add` edit through preview and apply. Multiple selection only for rooms from areas. Dismissal is installation-wide Layer-8 view state keyed by `SuggestionKey`, restorable, dropped when its source disappears; a satisfied suggestion disappears by itself. First start uses the same suggestions; automation suggestions stay Layer 5 proposals. Layer 5 needs no change. See the [CA4-107 review](specs/v3/reviews/CA4-107.md); no V3 runtime test ran.

#### CA4-106 — Notifications linked to "the panel" without any panel address

**Status:** DONE (2026-10-15; specification readiness). **Severity:** P2. **Origin:** Layer 8 completeness review.

**Problem.** Layer 6 put a link "to the Layer-8 panel" only on the proposal digest, and Layer 8 defined no addresses, so a notification could only open the panel's home. A request delivered without buttons, or through the fallback `persistent_notification`, gave no direct way to the item to answer; an automation notice could not open its "Why?".

**Approved resolution (2026-10-15).** Layer 8 §5.1 defines a public address scheme `/heima/<section>[/<type>[/<id>]][?at=<instant>]` with closed English sections and types and Heima's stable ids only (no names, no `entity_id`); `?at=` opens "Why?" at that instant. A missing or role-hidden object opens its section with one identical notice, revealing nothing; authorization stays in the backend. Layer 6 §7.2 sets the address per kind (requests to `todo/request`, Reaction notices to `automations/reaction?at=`, digests to their lists) and the fallback message ends with it as a Markdown link. Layer 6 builds addresses from its own ids and never calls Layer 8. See the [CA4-106 review](specs/v3/reviews/CA4-106.md); no V3 runtime test ran.

#### CA4-105 — House-map layout residues: unconnected rooms and several exterior rooms on one side

**Status:** DONE (2026-10-15; specification readiness). **Severity:** P3. **Origin:** house-map review after CA4-103.

**Problem.** CA4-103 placed a room with no same-floor connection against the other boxes, which reads as contiguity that does not exist, and let several exterior strips on one side overlap. The reasons behind the map choices and the refinements deliberately postponed were recorded only in conversation.

**Approved resolution (2026-10-15).** A floor's interior rooms are laid out in connection groups; a group without pinned rooms other than the first moves as a block beside the placed boxes with one empty cell between, on its preferred side (below by default). New dismissible map check "Not connected" (`HouseMapLayout.unconnected_ok`). Several exterior strips on one side are ordered along it and stacked outward on overlap; a corner balcony stays one strip. Layer 8 §9.11 records the rationale and the deferred refinements (half cells, left/top resize, non-rectangular rooms, corner strips, multi-floor rooms, opening position override, uploaded plan, weight tuning) and the map topics still open: phone pan/zoom, Lovelace card, first-start verification step, accessible list. See the [CA4-105 review](specs/v3/reviews/CA4-105.md); no V3 runtime test ran.

#### CA4-104 — Topology could not express doorless passages or connections between floors

**Status:** DONE (2026-10-15; specification readiness). **Severity:** P2. **Origin:** house-map review after CA4-103 (cross-floor connections).

**Problem.** `OpeningType` had only `door`, `window` and `door_window`. An archway, an open-plan boundary or an open staircase could only be declared as a `door`, which let a contact Sensor or an Actuator bind to a non-existent leaf and drew a door on the map. V2's `access_type` (`direct`/`stairs`/`elevator`) had been dropped, and nothing said whether openings between floors were valid or how the map shows them.

**Approved resolution (2026-10-15).** New passable `OpeningType` `passage`: no leaf, always open, no state; owner and `other_side` must be `interior` rooms; `outside`, exterior rooms and `orientation` are rejected, so `opening_faces_exterior` is always false and no Layer-3 exchange profile or Layer-5 advice/weather descriptor can select it (verified: they all filter on that query). Closable means `door`, on any floor. Between floors only `door` and `passage` are valid. A staircase is such a connection or an ordinary one-floor `Room` with its own openings, windows included; multi-floor rooms were rejected as map-only value. Layer 2 rejects `opening_id`/`related_opening_id` on a passage. Layer 8 draws a passage as a gap, adds floor badges that switch tab, proposes floors in ascending order with a cost toward the cells of connected rooms on lower floors, and never draws a connector across floors. A separate `stairs`/`elevator` type was rejected: no consumer needs it. See the [CA4-104 review](specs/v3/reviews/CA4-104.md); no V3 runtime test ran.

#### CA4-103 — The house map had no layout, orientation or control contract

**Status:** DONE (2026-10-15; specification readiness). **Severity:** P2. **Origin:** Layer 8 map design review with the developer, validated on an interactive mockup built on the real V2 topology.

**Problem.** Layer 8 §9 named an "automatic schematic laid out by connections" without a layout rule, so the same topology could be drawn differently by each implementation; rooms without a door, cross-floor stairs, opening sides and device placement were unstated. Opening orientation was unused, there was no rule for a house not aligned to north, and the optional uploaded plan carried asset storage and SVG sanitization for little value once boxes are editable. Whether the map could command devices was undecided.

**Approved resolution (2026-10-15).** Layer 8 §9 rewritten. Rooms are grid boxes (1×1 to 4×3) proposed by one deterministic rule: pinned rooms first, otherwise the highest-degree room; breadth-first placement minimizing a cost over untouched connections, deviation from the room's preferred direction (sum of its exterior-facing opening orientations), distance and bounding-box growth; ties by y then x; frozen weights with fixture tests. A room of degree ≥5 is proposed wider. Exterior rooms are strips on their openings' side. Openings and devices are derived, never stored. One installation-wide up direction in 45° steps, suggested as the one putting the most oriented openings on a full side (NE for a 45°-rotated house); changing it clears placements after a warning. `HouseMapLayout(revision, up, placements: MapRoomPlacement)` replaces `MapPlacement`; saving is an immediate presentation action with a stale-revision check, local undo per edit session, no consequence dialog. Map checks (not adjacent, faces another room, orientation missing, placement ignored) are diagnostics only. Overlays are keyed by channel kind and fact type; the sun overlay uses only the core solar-geometry Sensors. Map device control (tap toggles lights, fans, media and window covers; long press opens HA's more-info; locks, door covers and climate only more-info) calls HA services as the signed-in user, outside Heima's backend, never as an `ApplyStep`; the resulting divergence follows Layer 0 §6. The uploaded plan, `map/upload_plan` and the plan-asset decision are removed. Reused constructs: Layer 1 `CompassOrientation` and `opening_faces_exterior`, Layer 2 channel kinds and solar Sensors, HA more-info. See the [CA4-103 review](specs/v3/reviews/CA4-103.md); no V3 runtime test ran.

#### CA4-102 — A forward correction while the floor holds had path-dependent gap bounds

**Status:** DONE (2026-10-15; specification readiness). **Severity:** P2. **Origin:** Layer 0 implementation (`docs/v3/clarifications/PERIODIC_FORWARD_GAP_DURING_FREEZE.md` in the implementation worktree).

**Problem.** Layer 0 §3.5 did not say how a forward correction is bounded while an earlier backward correction still holds the cycle floor. The periodic-check sentence ("or later under the frozen-floor rule above") could be read as making any gap detected below the floor wait for floor recovery, so the same +3 s correction (floor 100, wall 90 → 94 over 1 monotonic second) ended at the first following cycle when detected at a cycle start but stayed open until floor recovery when detected by the 60-second check.

**Approved resolution (2026-10-15).** Each discontinuity opens its own gap, bounded only by its own correction (direction and, if backward, whether it leaves the wall clock behind the floor); the detection point never changes the end rule. A forward correction while the floor holds takes the forward-jump bounds and ends at the first cycle instant after detection, even if frozen; the earlier backward gap stays open independently until the wall clock exceeds the floor. Waiting for floor recovery was rejected: the frozen interval is already covered by the earlier gap, so the wait adds no information and widens the forward gap. A further backward correction over 1 s while the floor holds takes frozen-floor bounds from its own first frozen instant. Diagnostics report each gap and its end rule individually. Threshold, unchanged due/basis, elapsed monotonic waits and §4.4 durable acknowledgement are unchanged. See the [CA4-102 review](specs/v3/reviews/CA4-102.md); no V3 runtime test ran.

#### CA4-101 — Weekly occurrences had no identity across clock and timezone changes

**Status:** DONE (2026-10-15; specification readiness). **Severity:** P2. **Origin:** Layer 0 implementation (`docs/v3/clarifications/WEEKLY_OCCURRENCE_IDENTITY.md` in the implementation worktree).

**Problem.** The no-replay rule for weekly occurrences did not define which civil occurrence was already served: after a Monday 07:00 `Europe/Rome` firing, a zone change to UTC made Monday 07:00 UTC a future instant that a fresh next-due calculation would serve again; clock regressions, skipped calendar days, merged starts, late delivery and re-registration had the same gap. Review showed that Initial V3 has no weekly `CronEntry` consumer: every Heima-owned recurrence is an `IntervalRecurrence`, admin schedules belong to HA `schedule.*` helpers, and the only `WeeklyRecurrence` use is the presence-simulation session, a descriptor time-window parameter inside an activation.

**Approved resolution (2026-10-15).** The weekly `CronEntry` is removed from Initial V3: `CronEntry.pattern` is an `IntervalRecurrence`, and `WeeklyRecurrence` remains a value type (validation, DST rules, `matches()`) for descriptor time windows and bucketing; a future weekly `CronEntry` needs its own reviewed occurrence-identity contract. The presence-simulation session gets a local rule (Layer 5 §7.2): a session is identified by its requested civil date; within one activation a served date never starts again (timezone change, backward correction, several changes); a shifted start keeps its requested date; two dates resolving to one start make one session; missed starts are not caught up. The record lives in the activation (process memory, bounded by the absence); restart restores none. A generic per-job watermark for weekly `CronEntry`s was rejected as machinery without a consumer. See the [CA4-101 review](specs/v3/reviews/CA4-101.md); no V3 runtime test ran.

#### CA4-100 — A valid duration could produce an unrepresentable or zero-delay deadline

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P1. **Origin:** Layer 0 implementation (`docs/v3/clarifications/INTERVAL_PRECISION.md` in the implementation worktree).

**Problem.** `Window` accepts any positive finite duration, but every derived instant (an `AtJob.due`, a horizon end) is a microsecond `EvidenceInstant`. `Window(0.0000001)` produced `due == now` through a native duration conversion, so an `IntervalRecurrence` could re-fire immediately without end; `0.0000015` s fell between microseconds; a very large duration or horizon could pass the largest instant. Layer 2 (first instant strictly after the source-age expiry) and Layer 5 (whole milliseconds for learned delays) already had different local rules, and the calendar's "Layer-0 registration limits" were undefined.

**Approved resolution (2026-10-14).** Option B with 1(a) and 2(a): `Window` is unchanged; Layer 0 §3.1 adds one deadline-construction rule for every instant derived from an anchor plus a positive duration. The duration's value is the decimal of its canonical RFC-8785 form (`0.1` s = 100 000 µs exactly), the sum is exact, and the derived instant is the first `EvidenceInstant` at or after it, hence always later than the anchor, never early and never a zero-delay loop. Stricter consumers keep their rule (Layer 2 strictly after, Layer 5 whole milliseconds). A derived instant beyond `9999-12-31T23:59:59.999999+00:00` is a rejected dynamic registration (diagnostic, nothing armed) or a staging error for a static horizon, which also defines the calendar horizon limit. Execution lateness is separate. A universal whole-microsecond or millisecond `Window` restriction and consumer-side rejection were rejected because durations calibrated at runtime would be refused. CA4-98/99 are unchanged. See the [CA4-100 review](specs/v3/reviews/CA4-100.md); no V3 runtime test ran.

#### CA4-99 — `wall_clock` jobs were armed against the floored cycle instant

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P1. **Origin:** Layer 0 implementation review (`docs/v3/clarifications/CLOCK_SCHEDULING_REFERENCE.md` in the implementation worktree), reproduced with the real cycle clock, scheduler and a fake timer.

**Problem.** Layer 0 §3.1 computed every countdown as `due` minus the current cycle-instant clock, while also requiring `wall_clock` deadlines to follow the corrected wall clock. After a backward correction §3.5 holds cycle instants above the wall reading, so a `wall_clock` job re-armed against that floor fired early: wall 100 → 98 with due 110 gave 9.999999 s instead of 12 s.

**Approved resolution (2026-10-14).** Clarification of the approved CA4-20 intent, no new product choice: each basis has its own execution reference. `wall_clock` jobs arm and re-arm against the current unfloored wall-clock reading (at a cycle start, the periodic check or bootstrap); `elapsed` jobs against the cycle-instant clock, from which owners derive their dues, so the countdown equals the intended duration while the floor is frozen. §3.5 defines the cycle-instant clock between cycles and states that the cycle instant is history time, not a civil execution reference; facts of a cycle requested by a firing job still receive the floored instant. `CronEntry` "now" follows the basis. Strict history floor, elapsed semantics, canonical unchanged due, replacement/cancellation, no duplicate delivery and CA4-98 gap bounds are unchanged; no tolerance, grace or rounding is introduced. Using the wall reading for every job was rejected because it lengthens elapsed countdowns under a frozen floor. See the [CA4-99 review](specs/v3/reviews/CA4-99.md); no V3 runtime test ran.

#### CA4-98 — A backward clock correction without a frozen cycle had no gap bounds

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P2. **Origin:** Layer 0 implementation (`docs/v3/clarifications/CLOCK_GAP_BOUNDARIES.md` in the implementation worktree).

**Problem.** Layer 0 §3.5 classifies any wall-versus-monotonic difference over 1 s as a discontinuity and, per CA4-20 (20c/A), a backward jump opens a `clock_discontinuity` gap, but its bounds were tied to "the first frozen cycle instant". A correction such as wall 12:00:00 → 12:00:58 over 60 monotonic seconds (−2 s) is a backward discontinuity while the wall clock stays ahead of the cycle floor, so no cycle freezes and the gap had no start. Detection by the 60-second check between cycles and the `clock_regression` condition for a sub-second correction were likewise unstated.

**Approved resolution (2026-10-14).** Clarification within the approved CA4-20 rules, no new product choice: a backward discontinuity always emits `clock_regression`, re-arms `wall_clock` jobs and opens a gap; with the wall clock still ahead of the floor the gap takes the forward-jump bounds (last cycle instant before the detecting comparison → first cycle instant after detection); behind the floor the existing frozen-floor bounds apply. A periodic-check detection acts at detection, bounds the gap on the adjacent cycle instants, and is not detected again by the next cycle. A correction of at most 1 s opens no gap and emits `clock_regression` only when it puts the wall clock behind the floor. Threshold, strictly increasing cycle instants, elapsed countdowns, `wall_clock`-only re-arm, bootstrap/downtime separation and §4.4 acknowledgement rules are unchanged. See the [CA4-98 review](specs/v3/reviews/CA4-98.md); no V3 runtime test ran.

#### CA4-97 — Residues of the numeric-domain change

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P3. **Origin:** residue check after CA4-96.

**Problem.** Layer 2 §2.4 required formula results to be a non-boolean `int` or finite `float` without the integer range that Layer 1's numeric domain imposes on every fact payload; the overview's Layer-1 summary did not mention the numeric domain; overview and recap review lines named only CA4-86–93.

**Approved resolution (2026-10-14).** Wording only: Layer 2 §2.4 references Layer 1 §3 for every value that becomes a fact payload (configuration numbers keep their own contracts); the overview's Layer-1 list states the shared numeric domain; both review lines cover CA4-86–96. See the [CA4-97 review](specs/v3/reviews/CA4-97.md); no V3 runtime test ran.

#### CA4-96 — The generic numeric domain of fact payloads was underspecified

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P2. **Origin:** developer decision of 2026-10-13 recorded in the implementation worktree (`docs/v3/NUMERIC_DOMAIN_HANDOFF.md`) during the Layer 0/1 fact data-model work.

**Problem.** Layer 1 required finite floats and non-boolean quantitative numbers but set no integer range, although RFC 8785 serializes numbers as binary64 and a larger integer would lose exactness or depend on the serializer. Non-generic numeric objects (`Decimal`, `Fraction`, `complex`), numeric strings, and the canonical equality of `1`/`1.0` and of the signed zeros were not stated. Layer 3's `CanonicalJsonObject` already applied the safe range, so the two contracts were inconsistent.

**Approved resolution (2026-10-13; incorporated 2026-10-14).** Layer 1 §3 defines one numeric domain for every `EvidenceValue`-shaped payload (`HouseFact.value`, `Provenance.evidence`, permitted frozen-dataclass fields, `PersistedProjection`): non-boolean `int` in the inclusive range `[-(2**53-1), 2**53-1]`, never converted; finite binary64 `float` including subnormals, no generic range or rounding; `bool` distinct from numbers; no `Decimal`/`Fraction`/`complex`; numeric strings stay strings; field-specific constraints still apply. Canonical JSON writes `1`/`1.0` and both zeros identically; stricter contracts (Layer 3 negative-zero rejection) remain. Invalid value is a hard failure, invalid evidence drops to `{}` with a diagnostic. Layer 0's projection boundary and Layer 5's facet codec reference the domain. Identity, write-on-change, queue and recovery mechanisms are unchanged; configuration keeps its own contracts. No serializer library or code is approved here; CBOR remains only a possible future evaluation. See the [CA4-96 review](specs/v3/reviews/CA4-96.md); no V3 runtime test ran.

#### CA4-95 — Reaction lifecycle gaps: invalid decision state, no exit from `configuration_invalid`, successor follow-up

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P2. **Origin:** CA6 fix verification (V1) and lifecycle completeness review.

**Problem.** (V1) An invalidated Reaction is excluded from evaluation, so its `reaction.decision.<digest>` state kept its last value as current. (G2) A Reaction left `configuration_invalid` stayed invalid until an administrator committed a successor, but a learner-origin configuration changes only through a new proposal and an identical candidate deduplicates against the accepted one, so after an upstream change was undone (a sensor removed and re-added) such a Reaction had no way out; for admin-direct Reactions an identical successor was neither defined nor forbidden. (G4) Layer 5 listed disablement and revocation, but not generation replacement, among causes that emit no follow-up.

**Approved resolution (2026-10-14).** (V1) The invalidating commit emits one `available=False` decision fact, like removal; the next valid evaluation after a successor writes a new value. (G2) A change-set `replace` with the unchanged canonical configuration is a revalidation for both origins: it recompiles the plan and, if valid, ends `configuration_invalid` with a successor in `notification_only`; for learner-origin Reactions it is not a semantic edit (same rule as restore, CA4-90). Layer 8 offers a "revalidate" action. Automatic revalidation was rejected because it contradicts the administrator-commit rule. (G4) Invalidation, removal and a configuration successor emit no follow-up and block a terminal call. See the [CA4-95 review](specs/v3/reviews/CA4-95.md); no V3 runtime test ran.

#### CA4-94 — Residues found in the CA6 fix verification

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P3. **Origin:** line-by-line verification of CA4-86–93.

**Problem.** The verification of CA4-86–93 found wording residues: Layer 0's `resident_response` kind comment still named only runtime confirmation requests; Layer 5 §6.0 still said each `ReactionEvaluationResult` is "recorded" per snapshot; Layer 5 §4.1 said Layer 6 derives availability bindings, which Layer 5 declares; CA4-93 wrongly changed the recap to "seven facilities" (Layer 0 §1 lists six); the new overview communication row omitted Layer 3; the overview said recipients are people "with HA users" although `ha_user_id` is optional.

**Approved resolution (2026-10-14).** Wording only: each place aligned with its owning contract. The separate configuration-invalid decision-state gap (CA6 V1) is tracked on its own. See the [CA4-94 review](specs/v3/reviews/CA4-94.md); no V3 runtime test ran.

#### CA4-93 — CA6 mechanical residues across overview, recap, diagrams and specs

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P3. **Origin:** CA6 full reread (M1–M21 not absorbed by CA4-86–92).

**Problem.** Orientation documents still described Layers 6 and 8 as future or partial (stale review dates, a missing responsibility-map row for each, a "future" Layer 6 in the governance diagram and no Layer 8, only two of the seven Layer-6 event fact types, an unselected notification transport, quiet hours "separate", a recap notification list naming non-existent kinds, an outdated digest text, "six facilities" for seven, a dangling overview sentence). In the specs, Layer 5 §7.1.1 called `HouseholdConsentAuthority` a Layer-8 binding; `reaction.advisory_feedback` had no deduplication key; Layer 8's automation-state projection lacked the configuration-validity input; Layer 3's live-signal governance commands were absent from Layer 8; and Layer 3 called artifact promotion a generation transition.

**Approved resolution (2026-10-14).** Wording and cross-references only, no contract change: overview and recap re-dated and aligned with Layers 6 and 8 (responsibility rows, seven event fact types, transport, quiet-hours relation, communication-table rows, Layer-8 checklist question, repaired sentence); the governance PlantUML marks Layer 6 defined and adds Layer 8; the recap diagram gains the Layer 3/4/0 → 6 and Layer 8 edges. `HouseholdConsentAuthority` is described as a Layer-5 governance record; `reaction.advisory_feedback` joins Layer 0 §4.2's producer-owned append-once keys with `(advisory_operation_id, action)`; the automation-state projection reads the active composed generation; Layer 8 lists Layer 3 promotion and signal-adoption commands, history entries and messages; Layer 3 promotion is an artifact-adoption decision. See the [CA4-93 review](specs/v3/reviews/CA4-93.md); no V3 runtime test ran.

#### CA4-92 — Opening type and orientation were free strings; `entity_id` had no consumer

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P2. **Origin:** CA6 full reread (S7).

**Problem.** `Opening.type` and `Opening.orientation` were free strings although passability, composed translated names, `exposure_by_room` and the solar formula depend on exact values; the only closed orientation list lived in Layer 2's solar formula and was checked only when such a formula was staged. `Opening.entity_id` had no V3 consumer: opening state comes from a `Sensor` with `related_opening_id` or an `Actuator` channel with `opening_id`; it was a V2 carry-over like `access_type`.

**Approved resolution (2026-10-14).** Layer 1 §7 defines `OpeningType = door | window | door_window` (door and door_window passable) and `CompassOrientation` (eight compass points), owned there and referenced by the Layer-2 solar mapping; orientation stays optional and is required only by consumers that use it. `entity_id` is removed; a serialized opening carrying it is rejected. No new opening type (skylight, gate) in Initial V3: a garage door or gate is a `door`, and a horizontal skylight would need its own geometry review. See the [CA4-92 review](specs/v3/reviews/CA4-92.md); no V3 runtime test ran.

#### CA4-91 — Presentation names followed different rules per object

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P2. **Origin:** CA6 full reread (S6).

**Problem.** Every display name was already metadata outside semantic fingerprints, but the rest differed per object: `Sensor` had no name although it appears in explanations, the map and the Devices section (the CA4-84 review wrongly listed Sensor display names); the `Actuator` fallback was unspecified; only Reactions had unique names, so two unnamed south windows in one room composed the same name; explicit names had no length bound while Layer 6 truncates at 64 characters; and Layer 6 templates did not use the Reaction name that CA4-85 introduced for notifications.

**Approved resolution (2026-10-14).** One rule in Layer 2 §2.7 for `Room`, `Zone`, `Opening`, `Sensor`, `Actuator` and Reaction: a `display_name` (required for `Zone`, optional otherwise; `Sensor` gains the field); fallback live from HA (Room area, Sensor/Actuator entity name) or composed through translation keys (Opening, Reaction); explicit names at most 64 characters after NFC; effective names unique per kind within a scope (global for Room, Zone, Reaction; same `Location` for Sensor and Actuator; owning room for Opening), compared after trim, NFC and case-folding, composed names in every shipped locale; a composed collision needs an explicit name; live HA names are not checked. Layer 6 templates use the Reaction name. Automatic ordinal suffixes were rejected because a name would change when a sibling is removed. The stale Layer 2 §2.1 non-goal claiming Layer 2 does not own the Room inventory was corrected. See the [CA4-91 review](specs/v3/reviews/CA4-91.md); no V3 runtime test ran.

#### CA4-90 — Removing a Reaction had no lifecycle

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P2. **Origin:** CA6 full reread (S5).

**Problem.** Layer 8 allowed removing a Reaction and restoring it, and Layer 0 §7.4, Layer 5 and Layer 8 §10.2 presupposed removed Reactions, but no layer defined what removal did to the running activation, jobs, holds, managed episode, open advisory and consent request, the decision claim, pending proposals and the reuse of the id. Separately, a pending artifact-adoption proposal naming a superseded configuration generation stayed pending and not approvable forever, since that generation can never become current again.

**Approved resolution (2026-10-14).** Removal drops the catalog entry in an ordinary composed commit that applies the existing invalidation effects (authority disabled, future jobs cancelled); every other effect follows existing revocation rules (no follow-up or terminal call, advisory and consent closed `authorization_disabled`, owned hold invalidated `authority_revoked`, managed episode closed, recovery facets filtered, bindings closed `binding_deactivated`, entity removed), plus one terminal `available=False` decision fact. Root, generations and transitions stay as history; a `reaction_id` is never reassigned; restore appends a successor generation to the same root in `notification_only`. Learner-origin Reactions may be removed; their restore must equal a committed configuration. Pending adoption proposals naming a generation that is replaced or removed close in that commit as `proposal_incompatible` with the new transition code `target_generation_not_current`. Archiving and physical deletion were rejected. See the [CA4-90 review](specs/v3/reviews/CA4-90.md); no V3 runtime test ran.

#### CA4-89 — The decision record wrote once per cycle and programs had a second outcome vocabulary

**Status:** DONE (2026-10-14; specification readiness). **Severity:** P2. **Origin:** CA6 full reread (S4).

**Problem.** Layer 5 evaluates every enabled Reaction against every `DecisionSnapshot`, and CA4-79 appended one `reaction.decision` event for every non-`not_triggered` evaluation. A Reaction abstaining on a missing input, or a running program, therefore wrote one fact per cycle, not one per trigger firing as estimated, and could exhaust the per-type ceiling; its "appended once" retry rule had no Layer-0 deduplication. Separately, `evaluate_program` returned its own vocabulary (`not_started`, `ongoing`, `normal_exit`, `abstained`), never mapped to `ReactionEvaluationOutcome`, so a program's recorded decision was undefined.

**Approved resolution (2026-10-14).** The decision is a per-Reaction state fact `reaction.decision.<digest>` (digest over `[reaction_id]`, reserved pattern `reaction.decision.*`, owner `layer5.reaction_decision`), whose value holds no per-cycle identity; ordinary write-on-change persists only changes, makes retries idempotent, keeps the latest value unpruned, answers "why at T" through ordinary as-of reconstruction, and bounds each Reaction under its own per-type ceiling. `ReactionEvaluationOutcome` is the one vocabulary for one-shot and programmed Reactions and gains `normal_exit`; `evaluate_program` returns it directly (an active program waiting for its next boundary is `eligible` with no selected step). This supersedes the event shape of CA4-79; a change-suppressed event, recording only fired triggers, and keeping two vocabularies or renaming to new lifecycle names were rejected. See the [CA4-89 review](specs/v3/reviews/CA4-89.md); no V3 runtime test ran.

#### CA4-88 — Published activity entities contradicted Layer 4 and would always look broken

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P2. **Origin:** CA6 full reread (S3).

**Problem.** Layer 8 §10.1 published one `sensor` enum per room for activity, although Layer 4 §3.1 makes each `activity.<activity_id>` an independent claim that may coexist with others in one room. Layer 8 §10.2 also mirrored `available=False` as HA `unavailable`; every Initial-V3 activity profile is `positive_only` and publishes `available=False` whenever there is no positive evidence (Layer 4 §9.4), so the entity would have looked broken most of the day. The Layer-1/4 meaning of `available` (2026-09-10) is unchanged.

**Approved resolution (2026-10-13).** One `binary_sensor` per activity resolver (scope × `activity_id`): `on` when the claim is `active`, `off` otherwise including `available=False`, meaning "not detected now" (HA detection convention), never "proven inactive". This is the one declared exception to the `unavailable` mirroring rule; presence and occupancy keep it. No attribute distinguishes an unreadable anchor input; that remains visible through the input's own unavailability, health and diagnostics. A future `bipolar` profile declares its own mapping. The same edit names occupancy entities per occupancy resolver and corrects the pending-items source to Layers 5 and 0. A per-room enum, `unknown` instead of `off`, a per-room list attribute and no activity entities were rejected. See the [CA4-88 review](specs/v3/reviews/CA4-88.md); no V3 runtime test ran.

#### CA4-87 — Accepting a learned proposal created configuration outside the composed generation

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P1. **Origin:** CA6 full reread (S2).

**Problem.** Layer 5 §4.1 accepted a proposal in one local transaction that created the `ConfiguredReaction`, although Layer 0 §4.7 and Layer 5 §4.2 activate every Reaction configuration only through a composed generation and Layer 8 treated review as an immediate action. The new Reaction's catalog entry and name uniqueness, its Layer-6 publication bindings, its history/buffer/calendar/`previous_cycle` declarations and its dependency-index entry therefore had no activation path. Layer 5 §4.2 and §7.1.1 also described `stage_admin_direct_reaction` and the comfort-trajectory prerequisite as self-committing commands, while Layer 8 and Layer 0 treat them as change-set edits.

**Approved resolution (2026-10-13).** Acceptance stays an immediate governance command and commits one composed generation: the new Reaction (`notification_only`), its catalog entry with an optional `display_name`, and its disabled availability bindings, with an empty impact record (a new consumer breaks nothing) and the `accepted` review transition in the same Layer-0 transaction. A composed-name collision rejects with the existing `validation_failed` code and leaves the proposal pending. `stage_admin_direct_reaction` and `stage_comfort_trajectory_prerequisite_generation` are Layer-5 staging contributions of the Layer-8 change set, effective only at its commit. Acceptance as a change-set edit and a two-phase "pending Reaction" were rejected. See the [CA4-87 review](specs/v3/reviews/CA4-87.md); no V3 runtime test ran.

#### CA4-86 — An HA administrator could not answer resident requests

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P1. **Origin:** CA6 full reread (S1).

**Problem.** Layer 0's response ingress maps an HA administrator to `ha_admin` and every other user to `resident`, and all three Initial-V3 response owners (`layer0.recovery_confirmation`, `layer5.household_consent`, `layer5.advisory_feedback`) declared only `resident`. An administrator who is also a household member, which Layer 5 §7.1.1 permits, was rejected at ingress: consent from a notification, recovery confirmation and advisory feedback were impossible for them, and in a single-administrator home a `require_confirmation` Actuator could never recover.

**Approved resolution (2026-10-13).** The actor category describes the HA account, not household membership. The three owners declare `resident` and `ha_admin`; each keeps its own narrower rule (household consent still requires `actor_ref`, the HA user id, in `HouseholdConsentAuthority`). The operational source kind follows the verified category: `resident` gives `resident_response`, `ha_admin` gives `admin_command`. Multi-category ingress mapping was rejected because it would change the meaning of `resident` in resident-control provenance and correction attribution. See the [CA4-86 review](specs/v3/reviews/CA4-86.md); no V3 runtime test ran.

#### CA4-85 — Automations had no name, and renaming would have reset them to trial

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P2. **Origin:** Layer 8 draft review (G3).

**Problem.** Reactions had no display name, so several Reactions of one descriptor were indistinguishable in the panel, notifications and published entities. Putting a name inside the Reaction configuration would make every rename a successor configuration generation, which restarts in `notification_only` and cancels jobs.

**Approved resolution (2026-10-13).** The Layer-5 layer generation is the Reaction catalog: each entry maps `reaction_id` to its current configuration generation and carries `display_name`, excluded from semantic fingerprints like every other registry name. A rename is an ordinary composed commit that creates a new Layer-5 layer generation pointing to the same configuration generation: no demotion, no job cancellation, empty impact; allowed for learner-origin Reactions too. Effective names (explicit or composed from descriptor label and subject) must be unique after trim, NFC and case-folding. A separate label registry was rejected as a second naming mechanism. See the [CA4-85 review](specs/v3/reviews/CA4-85.md); no V3 runtime test ran.

#### CA4-84 — Connection `access_type` had no source or consumer; openings had no name

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P3. **Origin:** Layer 8 draft review (G2).

**Problem.** `ResolvedConnection.access_type` (`direct`/`stairs`/`elevator`) was a V2 carry-over: V3 derives connections from openings, `Opening` had no such field, and no V3 layer reads it. Openings also had no name for the panel and notifications.

**Approved resolution (2026-10-13).** `access_type` is removed from `ResolvedConnection` (a future consumer adds its own reviewed field). `Opening` gains `display_name: str | None`, presentation metadata excluded from the Topology fingerprint; when absent, the name is composed from type, orientation and room through translation keys. There is no separately authored `Connection`; administrators edit `Opening` records. See the [CA4-84 review](specs/v3/reviews/CA4-84.md); no V3 runtime test ran.

#### CA4-83 — The Room registry was referenced but never defined

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P2. **Origin:** Layer 8 draft review (G1).

**Problem.** Layer 1 reads `floor` and `enclosure` from a "Room registry" and validates zones against it, and Layer 0 §4.7 stages "room inventory attributes" with the Layer-2 generation, but no layer defined the room record: identity, name, floor, enclosure, HA area link. The data model and the panel could not be implemented consistently.

**Approved resolution (2026-10-13).** Layer 2 §2.6 defines `Room(room_id, ha_area_id, display_name, floor, enclosure)`. `floor` and `enclosure` are stored semantic attributes (HA floor level only suggests `floor` at creation), so HA changes never alter behavior without a commit; the name is presentation, read live from the linked HA area unless overridden; at most one room per HA area; semantic fingerprint `(room_id, floor, enclosure)`. See the [CA4-83 review](specs/v3/reviews/CA4-83.md); no V3 runtime test ran.

#### CA4-82 — Layer 8 could not observe non-fact state without polling

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P3. **Origin:** Layer 8 draft open point 5.

**Problem.** Automation state, pending items and Heima health are published as HA entities and shown live in the panel, but they are not state facts, so Layer 0 committed-state observers cannot feed them and no owner named Layer 8 as a consumer of its typed changes.

**Approved resolution (2026-10-13).** Owners hand their existing typed changes read-only to Layer 8, outside evaluation: Layer 5 authority transitions and every §6.0 occurrence; Layer 6 availability-tracker episode changes; Layer 0 recovery-confirmation occurrences, published health snapshots and degradation-diagnostic changes. Layer 8 keeps in-memory projections rebuilt at start from current owner state; no polling, no persisted record, no wait by the owner. See the [CA4-82 review](specs/v3/reviews/CA4-82.md); no V3 runtime test ran.

#### CA4-81 — Layer 6 hard-coded its supported languages

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P3. **Origin:** Layer 8 decision L8-C7.

**Problem.** `NotificationRecipient.locale` was `Literal["it", "en"]` and templates were described per supported locale, so adding a country would need a code change, against L8-C7.

**Approved resolution (2026-10-13).** `locale` is an HA language code accepted only when a translation resource exists; templates are translation keys with per-locale resources (English source; `en` and `it` shipped); missing locale or key falls back to `en`; locale-aware formatting of dates, numbers and units; template tests reject user-facing literals outside resources. See the [CA4-81 review](specs/v3/reviews/CA4-81.md); no V3 runtime test ran.

#### CA4-80 — Committed-state subscriptions could not follow configuration

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P3. **Origin:** Layer 8 decision L8-C6.

**Problem.** Layer 0 §4.8 allowed subscriptions only at bootstrap, but the HA entities Heima publishes depend on configuration (one occupancy entity per room), so adding a room would need a restart or a pattern subscription, which §4.8 forbids.

**Approved resolution (2026-10-13).** A core component may derive its exact-key subscription set from the active composed generation; the set is re-declared atomically at each generation swap boundary: added keys get one initial delivery after the first new cycle, removed keys stop, unchanged keys keep their state. Still core-only, exact keys, never patterns, never changed at other times. See the [CA4-80 review](specs/v3/reviews/CA4-80.md); no V3 runtime test ran.

#### CA4-79 — "Why did it not act?" had no durable answer

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P2. **Origin:** Layer 8 decision L8-C5.

**Problem.** `ReactionEvaluationResult` (outcome and reasons) was "recorded for each snapshot" without a defined store or lifetime; only resident-notified blocks were durable (`automation.availability`). An explanation of a past non-action, the most common user question, was not guaranteed, and the evaluation reasons did not say which guard failed.

**Approved resolution (2026-10-13).** Layer 5 appends one `reaction.decision` event fact (owner `layer5.reaction_decision`, reserved in Layer 0, approved in Layer 1) for every evaluation whose outcome is not `not_triggered`: outcome, reasons, failed guard capability ids (`failed_guard_capabilities`; corrected the same day from non-existent binding ids), execution mode and admission result, keyed by the evaluation identity; trial mode is recorded too. Not-triggered evaluations write nothing (the trigger fact history explains them). Ordinary asynchronous persistence and default 14-day retention; estimated 300-2,000 facts/day, a few MB, under the per-type ceiling. See the [CA4-79 review](specs/v3/reviews/CA4-79.md); no V3 runtime test ran.

#### CA4-78 — Past configuration generations had no retention rule

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P3. **Origin:** Layer 8 decision on change history and restore.

**Problem.** Layer 0 §4.7 durably writes each manifest and layer generation record but defines neither how long they are kept nor how a past one is read, so a change history with field-level comparison and restore (Layer 8) had no guaranteed source; Layer 5 already calls Reaction configuration history immutable.

**Approved resolution (2026-10-13).** Manifests and referenced layer generation records are retained indefinitely and readable by id as a slow-path query; they are outside fact retention, and growth is bounded by administrator commits. No pruning job and no change to commit or evaluation. See the [CA4-78 review](specs/v3/reviews/CA4-78.md); no V3 runtime test ran.

#### CA4-77 — Silencing a family could drop an open actionable request

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P3. **Origin:** Layer 6 review.

**Problem.** With `attention` (or `governance`) set to silent, a recovery confirmation (or consent request) produced during quiet hours was retired undelivered, leaving the resident without the answer buttons while the request was still open.

**Approved resolution (2026-10-13).** Silence applies only to informative phases. A phase with answer buttons whose request is still open is held and delivered when quiet hours end, and retires undelivered only if the request closes or expires first (Layer 6 §6.2, §7.5). See the [CA4-77 review](specs/v3/reviews/CA4-77.md); no V3 runtime test ran.

#### CA4-76 — Binding enablement changed through authority transitions outside any generation

**Status:** DONE (2026-10-13; specification readiness). **Severity:** P2. **Origin:** Layer 6 review.

**Problem.** Layer 3 §6.3.1 keeps each availability binding's enabled state in the publication generation and reconciles at generation swaps, but enabling or disabling a Reaction is a Layer-5 authority transition, which Layer 0 §4.7 excludes from the composed configuration generation. Promoting a Reaction would therefore never reach the index, and an active abstention would never be delivered.

**Approved resolution (2026-10-13).** A binding is enabled exactly while its Reaction is `automatic`. After an authority transition entering or leaving `automatic` commits, Layer 5 pushes a typed `BindingEnablementChange` to Layer 6 asynchronously; Layer 6 applies it as a revision of the current publication index with the existing swap reconciliation. Performance: tracker slow path only, no Layer 0/1 work, no wait by the transition or any cycle, copy-on-write of the affected keys through a reverse index built at staging, nothing persisted. See the [CA4-76 review](specs/v3/reviews/CA4-76.md); no V3 runtime test ran.

#### CA4-75 — Components outside the DAG could not learn of a committed state change

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer 6 draft review.

**Problem.** Layer 6 holds notifications during quiet hours but sits outside the evaluation DAG; Layer 0 offered no way to notify such a component when `quiet_hours.active` changes, so held items had no release trigger. Polling would add latency and a second change-detection path; start/end events would put a domain concept into Layer 0 and mirror a state as events.

**Approved resolution (2026-10-12).** Layer 0 §4.8 adds committed-state observers: core components declare at bootstrap subscriptions to exact state `FactIdentityKey`s; after a cycle commits to the current index, Layer 0 delivers each changed key asynchronously, coalesced to the latest value in cycle order, plus one initial value after the first cycle; subscriber failures are isolated. No fact is written and no DAG edge is created. Layer 6 §6.2 uses one subscription to `quiet_hours.active@casa`. See the [CA4-75 review](specs/v3/reviews/CA4-75.md); no V3 runtime test ran.

#### CA4-74 — Reaction notices could not take their family from the descriptor; Layer-6 review residues

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer 6 draft review.

**Problem.** The approved rule "notification family from the descriptor namespace" applied only to availability, because `ReactionFollowUpOccurrence`/`ReactionFollowUpIntent` and `ReactionActionNoticeOccurrence` did not name the descriptor: a weather-protection step left unconfirmed at night waited for the morning. The review also found residues contradicting approved Layer-6 decisions: Layer 1 still described a deduplication/rate-limiting window, Layer 3 let delivery configuration choose channel and grouping duration, Layer 5 said a delivered advice is "not withdrawn" although Layer 6 clears it silently, and the overview and recap used the old wording.

**Approved resolution (2026-10-12).** The two occurrences and the follow-up intent carry `reaction_descriptor_id`; one closed core table maps descriptor namespaces to families for follow-up, availability and action notices (`safety.*` -> `safety`; `environment.*`, `security.*`, `routine.*` -> `attention`; an unlisted namespace is rejected at staging). Serialization examples recomputed (intent 763/694/747, event 891/786/856 bytes). Residues corrected in Layer 1, 3, 5, overview and recap. See the [CA4-74 review](specs/v3/reviews/CA4-74.md); no V3 runtime test ran.

#### CA4-73 — Layer-6 inputs lack response request ids, binding descriptor and generation contents

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer 6 draft review (2026-10-12), [Layer 6 draft §13](specs/v3/layer6_notification_spec.md).

**Problem.** Writing the Layer-6 draft exposed four upstream gaps. (U1) `ConsentRequestOccurrence` and `ReactionAdvisoryOccurrence` do not carry the id their response owner declared to Layer 0's ingress, so Layer 6 cannot build answer buttons. (U2) Layer 5's availability-binding declaration does not name the Reaction's descriptor, which Layer 6 needs for the `safety` family. (U3) Layer 0 §4.7 names only availability publication bindings as Layer-6 configuration, not recipients and family options. (U4) Layer 5 §7.1.1 does not say that `HouseholdConsentAuthority` actor references are HA user ids, which Layer 6 needs to derive the `consent_authorities` audience.

**Approved resolution (2026-10-12).** (U1) Both occurrences carry `response_request_id`; because ingress declarations do not survive a restart while a pending consent does, Layer 5 declares a fresh request at each process start and emits a new `reissued` consent phase whose id Layer 6 uses to replace the notification through its tag. A `decline` from any authorized resident closes the request for the whole household. (U2) Layer 5's binding declaration names `reaction_descriptor_id`; Layer 6 derives the family. (U3) Layer 0 §4.7 includes recipients and family options in the Layer-6 generation, with no dependents. (U4) `HouseholdConsentAuthority` references are HA user ids. See the [CA4-73 review](specs/v3/reviews/CA4-73.md); no V3 runtime test ran.

#### CA4-72 — Operational event facts stored rendered resident text

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer-6 decision C6.

**Problem.** `OperationalEventValue` persisted rendered `title` and `message`. Every notification wrote language-bound text to disk, history could not be shown in another language, and Layer 5 staging had to prove the longest rendered text in every locale fitted the 8 KiB fact bound.

**Approved resolution (2026-10-12).** `OperationalEventValue` keeps `notification_key`, `severity` and `context` only; `context` holds closed fields and stable identifiers, never display names or text. Layer 6 renders title and message at each delivery from core templates, the recipient's locale and current configured names; Layer 8 renders history the same way; an unconfigured identifier is shown as itself. The renderer-bound staging obligation is removed; serialization examples recomputed. A `context_version` (data shape, not wording) lets the renderer select the template for old and new facts; no template reference is stored. See the [CA4-72 review](specs/v3/reviews/CA4-72.md); no V3 runtime test ran.

#### CA4-71 — Digest and quiet-hours grouping lacked closing phases and undelivered retirement

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer-6 decisions C3/C4.

**Problem.** Layer 6 could not tell whether a proposal or an advisory was still current at a deferred or grouped delivery: `ProposalReviewOccurrence` had no closing phase and `ReactionAdvisoryOccurrence` was one-shot. Layer 0 allowed `retired` only after delivery or from `prepared`, so a deferred item that became moot had no legal end. The proposal operation id over `[proposal_id, phase, evidence_revision_id]` collapsed two returns to approvability under one evidence revision.

**Approved resolution (2026-10-12).** Layer 0 §4.5 allows `ready -> retired` without delivery when Layer 6 decides no notice is due (the audit fact remains) and one delivery covering several ready records; no new outbox field. `ProposalReviewOccurrence` gains `closed` (`accepted`, `rejected`, `proposal_incompatible`, `not_approvable`) and `cause_record_id`, the §4.1 record causing the phase, which keys the operation id. `ReactionAdvisoryOccurrence` gains `opened`/`closed` (`activation_ended`, `authorization_disabled`, `superseded`); closing phases are never delivered to people, and a pre-restart advisory without closure is treated as closed. See the [CA4-71 review](specs/v3/reviews/CA4-71.md); no V3 runtime test ran.

#### CA4-70 — Protected retry-queue items can exceed the hard budget

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P1. **Origin:** implementation design review of CA4-38.

**Problem.** With enough distinct latest state keys or continuity boundaries, protected items alone exceed the finite queue budget. The CA4-38 discard order then has no eligible item despite nonblocking admission and a hard bound.

**Approved resolution (2026-10-12).** After the ordinary per-stream stages, enter one exceptional global `queue_overflow` epoch: a fixed-size earliest-loss marker replaces pending per-stream markers, oldest remaining items may be dropped including latest states and boundaries, and all streams are historically incomplete over the epoch. **Recovery correction approved 2026-10-13:** after fresh complete HA intake, valid producer assertions re-seed individual durable baselines over bounded successive cycle batches. The global gap closes at an acknowledged intake/accounting boundary even with keys still unrecovered; those keys alone retain incomplete coverage until acknowledged. No old state fallback, redated lifecycle proof, whole-re-seed transaction or duplicate live change is introduced. Live current state remains in memory. See [CA4-70 review](specs/v3/reviews/CA4-70.md); no V3 runtime test ran.

#### CA4-69 — Consent and advisory notices could not be answered

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer-6 decision C2.

**Problem.** Only the recovery confirmation had a response owner; household consent could be given only from the admin surface, and advisories collected no feedback although Layer 3 plans a presentation-preference model trained on explicit resident feedback.

**Approved resolution (2026-10-12).** Layer 0's response ingress registers `layer5.household_consent` (grant/decline; applied only for a resident currently in `HouseholdConsentAuthority`, through the same authority transition and precondition as `set_reaction_household_consent`; decline changes no authority) and `layer5.advisory_feedback` (done/dismiss/not_useful; appends a non-authoritative `reaction.advisory_feedback` event fact, reserved for Layer 5). Unanswered advisories are censored, not negative. See the [CA4-69 review](specs/v3/reviews/CA4-69.md); no V3 runtime test ran.

#### CA4-68 — Protective-action, proposal-review and consent notices had no contracts

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer-6 obligations inventory (B3–B5).

**Problem.** Layer 5 §7.4 promised a notice of weather-protection actions, Layer 3 expected Layer 6 to tell administrators about new proposals, and a Reaction awaiting household consent told nobody; none had a typed input for Layer 6.

**Approved resolution (2026-10-12).** Three typed Layer-5 occurrences and reserved Layer-6 event facts: `ReactionActionNoticeOccurrence` → `reaction.action_notice` (descriptors with `resident_action_notice=True`, Initial V3 only weather protection; one per activation summarizing channel outcomes); `ProposalReviewOccurrence` → `proposal.review_pending` (administrators; on creation and when approvable again; grouping belongs to the Layer-6 digest); `ConsentRequestOccurrence` → `reaction.consent_request` (consent-authorized residents; opened/closed; informative in Initial V3, an actionable answer would need a response-ingress owner later; superseded by CA4-69, which makes it actionable). Each once per operation id through the unified outbox; no actor identity or text. See the [CA4-68 review](specs/v3/reviews/CA4-68.md); no V3 runtime test ran.

#### CA4-67 — The recovery confirmation request had no delivery contract

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P2. **Origin:** Layer-6 obligations inventory (B2).

**Problem.** Layer 0 §7.4.1 creates a resident confirmation request after a power recovery, but nothing handed it to Layer 6 to deliver as an actionable notification, nor told Layer 6 when the request closed.

**Approved resolution (2026-10-12).** Layer 0 hands a typed `RecoveryConfirmationOccurrence` to Layer 6 at `opened` (with actions and expiry) and at `closed` (with its terminal state), once per phase by operation id; Layer 6 renders the reserved `recovery.confirmation_request` event fact through the unified outbox and closes or replaces the actionable notification on `closed`. Answers return only through the CA4-65 response ingress. Delivery failure never changes the request. See the [CA4-67 review](specs/v3/reviews/CA4-67.md); no V3 runtime test ran.

#### CA4-66 — `notification_only` mixed trial mode with resident advice, and advice had no contract

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P1. **Origin:** Layer-6 obligations inventory (B1).

**Problem.** `notification_only` meant both the pre-promotion trial (admin preview, no resident notice) and the permanent state of a policy without an endpoint that should advise residents; a manual-window suggestion had no legal member (every member needs an Actuator) and no typed occurrence for Layer 6; Layer 3 referred to an undefined "Layer-5/6 notification template".

**Approved resolution (2026-10-12).** `notification_only` is only the trial mode: no command, no resident notice, admin preview. Members declare `delivery`: `command` or `advice`; an advice member is legal for a descriptor's `advisory_intents` (Initial V3: external exchange open/close, solar shading increase/decrease) and may name only an exterior-facing `opening_id` when there is no Actuator. Advice passes staging, trigger, envelope and guards but no hold/ownership/physical/arbitration gate, is delivered once the Reaction is administratively authorized (household consent gates only commands), and produces one typed `ReactionAdvisoryOccurrence` per activation and member; Layer 6 renders the new `reaction.advisory` event fact (Layer 0 claim reserved, Layer 1 approved type). See the [CA4-66 review](specs/v3/reviews/CA4-66.md); no V3 runtime test ran.

#### CA4-65 — Layer 0 lacks the shared notification delivery and response foundations Layer 6 needs

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P1. **Origin:** Layer-6 obligations inventory, decided before Layer 0/1 implementation.

**Problem.** Layer 0 §4.5 offered a durable outbox only for `reaction.follow_up`, while Layer 6 must also deliver availability notices, notification-only Reaction advice, weather-protection notices, recovery confirmation requests and future review/consent prompts; each would otherwise grow its own store, as V2's two notification paths did. Separately, a resident answer to the recovery confirmation (Layer 0 §7.4.1) had no defined route from the delivery channel back to its owner.

**Approved resolution (2026-10-12).** (D1) Layer 0 §4.5 becomes one unified notification delivery outbox for every notification to a person: `prepared` (only `reaction.follow_up`), `ready` committed in one transaction with the audit event fact, `delivered`, `retired`; unique `(notification_kind, operation_id)`, at-least-once delivery, retention until delivered. Layer 0 owns storage mechanics only; Layer 6 owns every transition decision. (D2) Layer 0 §5.1.3 adds one authenticated response ingress with a closed `ResponseOwnerRegistry` (initially `layer0.recovery_confirmation`): owners declare requests with allowed actions and actor categories; Layer 0 authenticates the HA user, deduplicates and rejects invalid responses before routing a `VerifiedResponse`; Layer 6 only carries answers. No Layer-1 contract changes: new notification fact types are ordinary claims with the existing `OperationalEventValue`. See the [CA4-65 review](specs/v3/reviews/CA4-65.md); no V3 runtime test ran.

#### CA4-64 — Full Layer 0–5 reread (CA5) found cross-section inconsistencies

**Status:** DONE (2026-10-12; specification readiness). **Severity:** P1. **Origin:** CA5 full reread of Layer 0–5, overview and recap after CA4-12/62/63.

**Problem.** 31 findings: three normative contradictions and 28 residues of earlier corrections. (1) Layer 2 §5.7's join rule rejected `numeric.difference.v1`, `environment.solar_incidence.v1` and `environment.humidity_ratio.v1` outputs at a room from casa inputs. (2) Layer 4 `ActivityEvidenceSlot.max_age` measured age from a state's last change, the conflation CA4-05 removed elsewhere (added in parallel by CA4-47). (3) Layer 5 arbitration blocked both bundles even for identical targets, so two weather-protection Reactions closing one window, or protection versus solar shading under rain, could secure nothing.

**Approved resolution (2026-10-12).** (1) A formula may declare an exact destination rule in its `validate_binding`; the join check applies otherwise. (2) `max_age` is removed: freshness comes from availability and Layer 2 `max_source_age`; recent change needs an event/episode slot. (3) Identical complete safe-direction targets on one channel coalesce into one `ApplyStep` (new audit code `coalesced_identical_target`); opposing actions are prevented by guards, not precedence: exterior deployment requires `wind` and `precipitation`, and when a channel is protected every opposing variant must bind those guards to the protection Reaction's own hazard state, checked at staging. Residues fixed: `humidity_extraction` in Layer 3/5 profile lists, objectives, target shapes, KPIs and `level` terminology; single calibration owner for environmental gates; closed CA4-13/27/63 cited as open; CA4-27 "selective" wording; derived Topology/exposure properties in the composed-generation dependency index; exterior-only `exposure_by_room`; no exterior room in the thermal envelope; calendar consumer is Layer 5 only; hold terminology; zone-role references; `follow_comfort_trajectory` intent; `safety.*` namespace; planned-absence presence wording; summaries. See the [CA4-64 review](specs/v3/reviews/CA4-64.md); no V3 runtime test ran.

#### CA4-61 — Planned-absence descriptors duplicate their shared program rules

**Status:** DONE (2026-10-11; specification readiness). **Severity:** P2. **Origin:** developer review of the CA4-26 presence-simulation model.

**Problem.** Comfort trajectory (Layer 5 §7.1) and presence simulation (§7.2) restated the same planned-absence activation, departure/bootstrap, normal exit, next-activation, hold-release, restart and consent rules. Any behavioral change had to be repeated in both, and a future absence program would copy them again.

**Approved resolution (2026-10-11).** A closed, versioned `ProgramFamilyRegistry` in Layer 5 §3.2 with one family, `planned_absence_program` version `"1"`, holds those rules once; a descriptor declares `program_family` and its own `program_evaluator` calls the family's pure component. A family change is a new family version adopted through each descriptor's new version. An unversioned shared section was rejected because it could silently alter configured descriptors. §7.1/§7.2 keep only descriptor-specific behavior; overview and recap summarize. See the [CA4-61 review](specs/v3/reviews/CA4-61.md); no V3 runtime test ran.

### P3 — Low

#### CA4-29 — Current reading paths still lead to superseded models and diagrams

**Status:** DONE (2026-10-04; current reading path). **Type:** documentation drift/duplication. **References:** [recap](v3_architecture_recap.md), [Graphviz](img/v3_architecture.dot), [overview](specs/v3/architecture_overview_defined_layers.md), [support diagram](specs/v3/architecture_support_governance.puml), [HouseFact draft](v3_house_fact_draft.md), [registry draft](v3_sensors_actuators_draft.md), [learning draft](v3_pattern_learner_draft.md), [domain draft](v3_domains_draft.md), [matching draft](v3_template_matching_draft.md).

Historical drafts contain superseded Freshness, proposal-as-HouseFact, registry/strategy, global-house-state, and plugin-action models. Their historical existence is legitimate. The 2026-10-04 architecture alignment removed the obsolete Graphviz diagram from the recap's current reading path and marked its source historical; it corrected the overview's trajectory gate order, the support diagram's Layer-3 serving description and Layer-4 availability route, and the recap's current analyzer-to-candidate path. The remaining CA4-29 work is to audit and mark the older draft links and other current reading paths so they cannot reintroduce retired models. This partial correction does not close the item.

**Correction:** clearly mark historical documents and link their successors; align the current overview/recap/diagrams with authoritative contracts. **Closure:** the current reading path cannot reasonably reintroduce a retired authority or data model; historical rationale remains preserved.

**Verification.** All five older drafts now carry prominent historical banners and links to their
owning layer contracts. The recap's current reading pointers use Layers 0, 1 and 3; its old Graphviz
source and rendered image are identified as historical, while the two PlantUML diagrams and overview
remain the current path. Layer 3's related-documents note also gives its defined spec precedence.
The drafts and old diagram remain available solely as decision history.

#### CA4-30 — Approval metadata, references, and audit headings remain stale

**Status:** DONE (2026-10-04; specification navigation). **Type:** register/reference maintenance. **References:** [index](specs/INDEX.md), [Layer 0](specs/v3/layer0_runtime_spec.md), [Layer 1](specs/v3/layer1_substrate_spec.md), [Layer 2](specs/v3/layer2_registries_spec.md), [Layer 4 §3.1, §9](specs/v3/layer4_domain_spec.md), [Layer 5 §7](specs/v3/layer5_action_reactions_spec.md), RC/CA3 sections above.

Layers 0–2 are marked Defined but retain approval/discussion caveats; Layer 4 retains separate-approval wording beside defined profiles. Layer 5's broad statement that active descriptors may be deterministic/direct conflicts with its learner-only trajectory restriction. Some Layer-0 diagnostics references still point to §9, now telemetry rather than §10 diagnostics; an acceptance identity remains `(policy_id, snapshot_id)` without generation. The index omits V3, and the RC/CA3 headings remain open although their individual findings are resolved. A CT-3 backlink should also point clearly to the current normative mapping.

**Correction:** reconcile status, applicability, vocabulary, and links without rewriting historical decisions. **Closure:** V3 is navigable from the index, section references resolve to their intended contract, and completed audit groups have accurate aggregate status.

**Verification.** The index links the six defined V3 layer specs and separates them from runtime
V2. Layers 0–2 no longer demand an obsolete document-wide approval, Layer 4 names its defined
initial profiles, and Layer 5 limits admin-direct authoring to descriptors that admit it. Current
diagnostic cross-references point to Layer 0 §10, the Layer-5 CT-3 backlink points to Layer 3
§6.4.1, and resolved RC/CA3 group headings say so. The alleged old `(policy_id, snapshot_id)`
acceptance identity was already absent on recheck; Layer 5's current keys include reaction,
configuration generation, activation and snapshot (§4.2/§8). Historical backlog quotations keep
their original wording as dated decision records.

#### CA4-59 — Wrong cross-references and stale statements in the layer specifications

**Status:** DONE (2026-10-04; specification consistency). **Severity:** P3. **Origin:** 2026-10-04 reread. Complements CA4-30 (which keeps the
Layer-0 §9→§10 diagnostics references and the CT-3 backlink); each line below is a separate fix.

1. [Layer 1:139](specs/v3/layer1_substrate_spec.md) cites "(§6.4)"; Layer 1 has no §6.4. Intended:
   Layer 0 §6.1 (staging proof) and §6.4 (runtime check).
2. [Layer 3:1786](specs/v3/layer3_learning_spec.md) cites "item 6's eligibility gates" with no
   resolvable target. Intended: the evidence-gated `hvac_thermal_response` gates of Layer 3 §4.8 /
   §8 item 6; write the explicit section reference.
3. [Layer 4:478](specs/v3/layer4_domain_spec.md) cites "§3.5"; Layer 4 has no §3.5. Intended:
   Layer 2 §3.5.
4. [Layer 3:83](specs/v3/layer3_learning_spec.md) lists "presence simulation" as an example learning
   family, contradicting Layer 3 §7 and the overview (it is an admin-direct Layer-5 descriptor, not a
   learning family). Remove it from the example list.
5. Layer 0 §6.1 uses `FactSource(kind="timeout", actor_type="scheduler")` for hold expiry
   ([Layer 0:1446](specs/v3/layer0_runtime_spec.md)), while `timeout` is defined as an elapsed
   response/confirmation window (Layer 0:1117–1118). Either widen the `timeout` definition to cover
   owner-scheduled deadline expiry or use `system`; keep one meaning.
6. [Layer 1:129](specs/v3/layer1_substrate_spec.md) still describes `HoldLifecycleValue` as "bounded
   hold key, event and origin fields"; it now also carries value and expectation-source maps. Use a
   neutral description that refers to Layer 0 §6.1.
7. [Layer 1:290–293](specs/v3/layer1_substrate_spec.md) says "neither Layer 3 nor Layer 5" may
   pre-render or persist `automation.availability`; Layer 4 is also a suppression owner. Name all
   three.
8. [Layer 0:87–88](specs/v3/layer0_runtime_spec.md) calls configured policies "Layer 4/5 concerns";
   Layer 4 has no policies. Say Layer 5. In the same file, the `AtJob.owner` example "manual_hold"
   (Layer 0:111) should use the divergence-hold owner name.
9. "Not yet decided: none remains" in Layer 0 §12, Layer 1 §9 and Layer 2 §8 contradicts open CA4
   items against those layers (and Layer 0 §8 itself cites CA4-38). Replace with a short pointer to
   the open CA4 IDs that affect the layer, or remove the claim.
10. **Already addressed (2026-10-04):** the [CA4-01 serialization examples](specs/v3/ca4_01_serialization_examples.md)
    now use distinct 64-hex `HoldLifecycleValue.operation_id` values and `hold_id` values for all
    three cases; their byte sizes were recomputed after the CA4-51 fixture alignment.

**Closure.** Every listed reference resolves to the intended contract and every listed statement
agrees with its owning section.

**Verification.** Layer 1 now points to Layer 0's hold proof and runtime validation; Layers 3/4
use the owning profile and computer-fact sections; Layer 0 uses `system`/`scheduler` for a scheduled
hold expiry while `timeout` retains its response-window meaning. The learning-family list, hold-value
description, availability owners, configured-policy owner, and open-issues sections were corrected.
The three hold serialization examples use distinct transition operation ids. This closes the listed
documentation defects, not the separate CA4-30 cross-references.

#### CA4-60 — Recap/overview drift and duplicated normative prose

**Status:** DONE (2026-10-04; specification consistency). **Severity:** P3. **Origin:** 2026-10-04 reread. Complements CA4-29.

1. The recap's Layer-6 section says quiet hours are active on "an active `sleeping` `HouseFact`"
   ([recap:486](v3_architecture_recap.md)). Layer 4 §9.5 makes `activity.sleeping` room-scoped and
   requires a separately reviewed claim for any casa quiet/sleep context. Rephrase as a future
   Layer-6 input to be defined (link CA4-50), without naming `sleeping` as the trigger.
2. The recap's "What's still genuinely open" list is partly obsolete
   ([recap:567, 573–574](v3_architecture_recap.md)): `TemplateRequirement`, `proposal_type`/
   `reaction_type` and `v3_domains_draft.md` belong to retired models. Replace them with current
   terms (`ReactionDescriptor`, `candidate_kind`, `reaction_descriptor_id`) or drop resolved items.
3. Duplication: the channel-hold paragraph in overview §4 (overview lines 93–126) and the recap's
   Divergence Hold Manager bullet restate Layer 0 §6 and Layer 5 §6.0 in dense normative prose, so
   every hold change needs four edits. Reduce each to a 3–5 line summary that links the owning
   sections.
4. Duplication: Layer 1 §3.1 lists the complete `reaction.follow_up` context field set
   ([Layer 1:269–287](specs/v3/layer1_substrate_spec.md)), which Layer 5 §6.0
   (`ReactionFollowUpOccurrence`) already defines. Keep in Layer 1 only the mapping rule (fixed
   occurrence fields plus flattened `expected.<facet>`/`observed.<facet>`, `subject`→`where`,
   `occurred_at`→`when`) and reference Layer 5 for the field list.
5. **Already addressed (2026-10-04):** the CA4-01 entry is compact. Its status, approved A1/B1/C2
   decisions and closure evidence are at the top; the full decision trail is preserved in
   [the CA4-01 review record](ca4_01_review_record.md). This subitem is no longer a CA4-60 closure blocker.

**Closure.** The recap and overview contain no statement contradicting Layer 0–5 and no normative
restatement longer than a summary with links; each follow-up field is defined once.

**Verification.** The recap no longer infers casa quiet hours from room-scoped sleeping, and its
open-work list names current Reaction contracts. The overview and recap summarize the channel
hold with pointers to Layers 0/5 rather than repeating its lifecycle. Layer 1 defines only the
follow-up event mapping; Layer 5 §6.0 remains the sole owner of the occurrence field list.

### Historical specification-correction sequence (snapshot 2026-10-04)

This dated sequence is retained as rationale and includes items closed after the snapshot,
including CA4-18. It is not a current work queue. Check each item's own status and use the
[V3 contract registry](specs/v3/contract_registry.json) and
[specification workflow](specs/v3/spec_workflow.md) for current correction work.

The shared V3 contract must remain generic across Actuator channel kinds and Reaction descriptors;
descriptor-specific behavior may specialize a policy without creating another action, hold, guard,
learning or configuration pipeline. This sequence concerns specification readiness, not runtime
implementation or CT-4's separate release calibration.

1. Resolve the remaining decision-required choices with the developer before applying them:
   CA4-54, CA4-57 and CA4-58. Recheck each cited counterexample first.
2. Close the common substrate, temporal and historical contracts: CA4-04–06, CA4-20–22,
   CA4-28, CA4-38 and CA4-54–55.
3. Close registry, fusion and semantic-input contracts: CA4-07–08, CA4-10, CA4-16,
   CA4-36, CA4-46–49 and CA4-57.
4. Close shared action authority, recovery and execution: CA4-03, CA4-18, CA4-24–27,
   CA4-39, CA4-42–45 and CA4-50. CA4-44 includes the common command surface
   extension recorded with CA4-51–58; CA4-27 retains a scope separate from DONE CA4-02/17.
5. Close learner data, proposal identity and descriptor catalog: CA4-09, CA4-11–15,
   CA4-35 and CA4-58.
6. Align the current reading path only after the owning contracts settle: CA4-29–30 and
   CA4-59–60. Preserve historical rationale, but mark retired models as historical.

Every correction updates its owning acceptance criteria and affected current references. A DONE
specification item is not a claim of runtime implementation or test completion. The separately
deferred V2 `room_smart_lighting_assist` failure remains a diagnostic requirement for V3: an enabled
Reaction that never acts despite plausible triggers must be visible rather than silently ignored.
