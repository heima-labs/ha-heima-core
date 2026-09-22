# Heima v3 — Architecture Recap

Status: **synthesis of the full v3 design, not a spec.** This document describes how the v3
architecture is meant to work, end to end, organized by logical dependency layer. It does not assume
familiarity with any earlier version of Heima. Each block links to the backlog section or draft file
where the full reasoning/evidence trail lives, for anyone who wants to go deeper — but the recap
itself should be enough to understand the system on its own.

Out of scope, explicitly: `chi` (per-person learning — Heima learns at the household level, not per
resident), push-model plugins (third-party extensions are pulled by the core, never push data in on
their own). V3 uses a deliberate clean-start cutover: it does not migrate V2 configuration, history,
runtime state, or learning; a V2 export can exist only outside V3 as rollback/reference material.

```
Layer 8  Admin / config surface        config_flow forms + admin panel (registries + actions)
Layer 7  Extensibility                 third-party semantic extensions, pull-only, 2 capability tiers
Layer 6  Notification / communication  one pipeline, 3-tier quiet hours, digest
Layer 5  Action / reaction generation  Reactions, template requirements -> auto-proposals
Layer 4  Semantic Resolution (the DAG) independent semantic claims and episodes
Layer 3  Learning / pattern recognition PatternLearner, bounded live signals, proposal analyzers
Layer 2  Registries                    Sensor + Interpretation + FusionRule, Actuator
Layer 1  Substrate primitive           HouseFact: WHAT/WHERE/WHEN/HOW, Location/Zone/Topology
Layer 0  Cross-cutting runtime         Timing, Persistence, FactSource/ApplyStepSource, holds, recovery
```

Layers 0-1 are one foundation slice, with distinct ownership and a bounded reciprocal dependency on
immutable contracts: Layer 0 owns runtime mechanisms and `FactSource`; Layer 1 owns `HouseFact`,
`Provenance`, and spatial value objects. Neither invokes the other's behavior in a cycle. Layers 2-5
are what the engine *does* each cycle. Layers 6-8 are how a human (or another program) *sees and
steers* it. Layer numbering is current as of this revision; it is not load-bearing outside this
document.

---

## Full logical architecture — diagram

![Heima v3 logical architecture: 9 layers, colored by layer, with the runtime data flow between them](img/v3_architecture.png)

Rendered with Graphviz (source kept alongside it at `img/v3_architecture.dot`, regenerate with
`dot -Tpng -Gdpi=150 img/v3_architecture.dot -o img/v3_architecture.png`), so the layout is exact
and stable — not subject to an auto-layout engine's guesswork about node placement.

**Reading it**: each shaded block is one numbered layer. A solid arrow is real per-cycle data flow.
A dashed, labeled arrow is a bounded or exceptional path — narrower than a plain dependency
(`bounded` = one of the 3 audited live-signal exceptions in Layer 3; `admin review` = a statistical
pattern that must be approved before it can act). A dotted arrow is configuration or registration,
never runtime data (Layer 8 configuring a registry, Layer 0 persisting/tagging a fact, Layer 7
registering a plugin).

Walking it top to bottom: a `Sensor` (Layer 2) turns a raw entity state into a `HouseFact`; a
`FusionRule` (Layer 2) may combine several of those into one derived fact, same cycle; both feed
Semantic Resolution (Layer 4) — independently resolved semantic claims and episodes — which in turn
feeds Reactions (Layer 5) in the *same* cycle, producing `ApplyStep`s. `PatternLearner` (Layer 3)
runs on its own slower cycle, mining history rather than the live cycle, and reaches Semantic
Resolution only through the closed, individually authorized signal contracts; its registry analyzers
instead produce a `ReactionProposal` that always needs admin review before becoming a Reaction.
Reactions and Semantic Resolution both emit events into the notification pipeline (Layer 6). Layer 0 underlies everything;
Layer 7 registers third-party extensions into Semantic Resolution and, for their own entities, into the
registries; Layer 8 configures the registries, Reactions, and notification policy.

---

## Layer 0 — Cross-cutting runtime facilities

Five facilities that sit outside the semantic-resolution DAG entirely — nothing in Layers 2-5 can
depend on them changing mid-cycle, and nothing here depends on a semantic claim.

- **Timing**: one execution primitive, an "at" job — a scheduled one-shot deadline. A "cron" policy
  layer sits on top of it: a `RecurrencePattern` computes the next due time and re-arms an "at" job
  each time it fires. This is how every **Heima-owned** recurring or periodic job works — a periodic
  safety-net re-evaluation, for example — each is a `CronEntry` owned by whichever subsystem needs it,
  not a separate bespoke timer mechanism per feature. Admin-authored recurrence instead belongs to an
  HA `schedule.*` helper; Heima consumes only its effective state as an ordinary sensor fact and never
  duplicates HA's schedule picker or timezone/DST logic.
  `Window` (a bounded time span) is a separate, non-executing comparison type used for dwell timers
  and correlation/follow-up matching — "has this been true for at least N seconds," "did Y happen
  within N seconds of X." `LearnedWindow` is a `Window` that starts from a seed value and calibrates
  itself from observed `HouseFact` history over time, usable anywhere a plain `Window` is used, not
  a feature bolted onto one specific reaction. `CalendarWindow` extends the same "something at
  instant T" idea to an externally-sourced, named interval with an absolute start/end (a vacation,
  a holiday, a work day) instead of a relative or recurring one. Layer 0 exposes both active windows
  for current facts and complete future windows within a consumer-declared horizon for predictive work
  such as notifying today about tomorrow's event; calendar awareness is Timing infrastructure,
  evaluated before the core DAG runs each cycle, not a semantic resolver or a plugin.
  Duration and civil-time values are validated at configuration staging or dynamic job registration,
  never repaired or rechecked per cycle.
  → `v3_house_fact_draft.md` §WHEN.
- **Persistence**: `HouseFact` storage is **always atomic** — one fact per WHAT/WHERE/WHEN/HOW,
  never a bundled record. It has two tiers: a durable long-term store (for learning and audit) and
  a short-term in-memory buffer (for correlation/follow-up matching within a bounded recent window),
  because those two needs have genuinely different cost profiles — the fast path can never wait on
  disk I/O. A producer declares each fact family as `state` or `event` at composition: state facts use
  canonical identity and write-on-change; unchanged state observations append nowhere, while every
  distinct state transition is retained in deterministic internal append order and latest-state lookup
  remains O(1). Events append every occurrence and are never current state.
  The same bootstrap pass reserves fact-type ownership across layers, preventing a registry producer
  from colliding with a Layer-0-owned family such as manual holds. A "snapshot" (everything true at
  one instant, or in one place, over one window) is never its own stored shape; it's a query
  reconstructed at read time.
  → `v3_backlog.md` §`HouseFact` persistence model.
- **`FactSource` / `ApplyStepSource`**: one structured-provenance vocabulary spanning both facts and
  actions — every `HouseFact` and every `ApplyStep` carries a `kind` (sensor, analyzer, third-party
  plugin, reaction, admin command, resident response, timeout, recovery, system...), a `source_id`,
  an `actor_type`, and a `correlation_id`. Non-forgeable (an untrusted or malformed source gets
  sanitized into a clearly non-authoritative value, never silently trusted) and redacted before it
  reaches diagnostics or storage. This is what makes "why is the house in this state" answerable:
  follow one `correlation_id` from a resolved state back through the facts that fed it to whatever
  produced them.
  → `v3_backlog.md` §Observability, re-grounded.
- **Manual Hold Manager**: a manual hold — a resident's explicit override that suppresses some
  automated behavior in some functional domain — has a state `HouseFact`
  (`fact_type: "manual_hold.<domain>"`, scoped by `Location`, with an immutable `hold_id`,
  `active`, `kind`, and optional pinned state) plus one audit `HouseFact` per transition
  (`fact_type: "manual_hold.<domain>.lifecycle"`: activated, cleared, expired, replaced, restored,
  or restoration discarded). State facts alone answer live-state queries; lifecycle facts make every
  decision auditable. Their `FactSource` is deterministic and complete: a resident-attributed helper
  entity edge, implicit-hold analyzer, admin command, timeout, or Recovery as appropriate. The same helper
  accepts an admin-attributed activation or clear as `admin_command`; automation, service, and
  unattributable edges are rejected rather than misreported as resident action.
- **Operational events**: `HeimaEvent` is a transient notification envelope, never a second audit
  store. Each event maps to one append-only `HouseFact`: its type becomes `fact_type`; a structured
  value retains the notification key, severity, rendered title/message, and JSON-compatible context;
  its `Location` and correlation id remain mandatory. Notification deduplication/rate limiting uses
  the key at delivery time without deleting or coalescing historical event facts. The transient
  delivery id is neither fact identity nor a durable parallel field.
  An implicit hold's expiry is handled by
  `Window`/`AtJob` instead of a bespoke timer. A hold's functional `domain` (which behavior is being
  suppressed — lighting, heating, security...) is a separate, orthogonal field from `Location`
  (where), not folded into it.
  **By default, a hold must never silently survive a restart.** Its `HouseFact` can still be
  durably logged for audit and learning ("the resident overrode X, how often") — but the live "is
  this hold active right now" state is never reconstructed from that log after Home Assistant
  restarts. If it were, a suppression could remain silently in effect indefinitely after a restart,
  with the resident unaware it's still blocking a security-relevant behavior. Same `HouseFact`
  shape, two deliberately different read paths: one for history, one for live state, with different
  restart guarantees.
  **Power recovery is baseline-plus-recalculation, not command replay.** For an actuator explicitly
  configured to participate, Heima coalesces its last accepted desired target into the checkpoint;
  after a confirmed outage it combines that baseline with current facts, time, safety, and manual
  holds before calculating one final delta. Thus unchanged conditions restore the house's prior
  desired state, while elapsed time can correctly change it. The coalesced snapshot deliberately has
  no synchronous per-target flush; a target not yet committed at power loss may be absent or older.
  `FactRef.previous_cycle` is likewise performance-bounded: it reads a small snapshot sealed in memory
  after the preceding evaluation, never disk. A clean shutdown lets Layer 0 pre-hydrate that snapshot
  before the next DAG; an unclean restart starts this input unavailable for one cycle rather than
  pretending an older durable record is the immediate predecessor.
  Manual-hold transitions have the opposite durability profile: a small, `fsync`-backed journal makes
  their state/lifecycle facts and restart checkpoint idempotently crash-consistent. If the medium is
  unavailable, the hold remains live for safety but is explicitly `durability_pending`, never quietly
  represented as durable.
  Registry reload is an immutable, atomically swapped configuration generation. Staging computes and
  compares per-producer execution-semantic fingerprints only once, outside the hot path: any changed,
  added, removed, relocated, Zone-affected, or formula-version-affected producer and every
  current-cycle Fusion dependent enter the direct/transitive impact set. Their dwell and prior-cycle
  memory reset and retained facts receive a new semantic configuration fingerprint; display-only
  metadata leaves unrelated runtime state intact.
  Two kinds of hold, not one, with different restart behavior: an **explicit** hold (helper-entity
  backed) is re-read live from Home Assistant every cycle. A narrow checkpoint mapping preserves its
  immutable `hold_id` and pinned state across a restart, but can never override an inactive helper;
  a missing mapping produces a newly observed Recovery activation rather than a fabricated historic
  identity. An **implicit** hold (inferred from an unexpected state divergence) follows
  the default above — with one narrow, opt-in, never-silent exception: an installer may mark a
  specific `Actuator` record eligible for conditional restoration after a *clean* restart (no
  power-restore ambiguity for that entity, current state still coherent with what triggered the
  hold); every such restoration is itself recorded as a `HouseFact` that reaches the resident
  through notification, never quietly. Resolved 2026-09-02, amending this rule's original
  unconditional form.
  → `docs/specs/v3/layer0_runtime_spec.md` §6 (full mechanism, current source of truth for Layer 0).
  → `v3_backlog.md` §"Manual Hold Manager / Recovery-Checkpoint", §"Full architecture re-review"
  (AR-3), §"Layer 0 promoted to a real spec, first amendment found along the way".
- **Recovery / Checkpoint**: a lightweight, pre-DAG context computed once per evaluation cycle,
  before any semantic resolver runs — it classifies runtime state (normal / just started / recovering from a
  power loss / degraded because many entities are unavailable / settling back to normal) and makes
  that classification available, read-only, to everything downstream, so behavior can be
  conservative and explainable right after Home Assistant restarts or during a partial outage.
  Backed by a deliberately minimal checkpoint — only an allowlist of critical entities' attributes,
  redacted, written on a periodic cadence (itself a `CronEntry`, owned by this subsystem — Recovery
  consumes Timing's execution primitive like everything else that needs periodic work). It answers
  "did anything change while Heima was offline" cheaply; it is not a general restore mechanism, and
  it never forces every piece of runtime state through the full `HouseFact`/`Provenance` shape —
  some state (like this one) is narrow and minimal on purpose, not by oversight.
  **Same restart rule as Manual Hold**: neither an active hold nor a pending "please confirm this
  before I apply it" runtime confirmation is ever silently restored from a checkpoint after a
  restart — both are the kind of state that must start clean, by design, every time.
  → `v3_backlog.md` §"Manual Hold Manager / Recovery-Checkpoint" +
  §"Full architecture re-review", AR-3.

---

## Layer 1 — The substrate primitive

- **`HouseFact`**: `fact_type` + `value` + `where: Location` + `when: datetime` + `how: Provenance`.
  This is the one shape everything else in the system is built from — a sensor reading, a fused
  derived state, a learned statistical signal, a reviewable proposal, a manual hold, a notification
  trigger. There is no second, parallel representation competing with it for the same kind of
  information; anything that looks like "a thing that's true, somewhere, at some time, with some
  confidence" is a `HouseFact`.
- **`Location`**: always present on a `HouseFact`, never absent. Four forms: `casa` (the whole
  house, the root), a single `room`, a declared `zone`, or `rooms` — an ad hoc, unnamed set of room
  IDs, needed when a fact is genuinely scoped to a dynamically-observed combination of rooms that
  isn't a standing, admin-declared `Zone`.
- **`Zone`**: an admin-declared, named group of rooms — Heima-owned data, not a live reference to
  Home Assistant's own label/grouping features (those can *suggest* a zone at creation time, nothing
  more). A room can belong to several zones at once; zones are not nestable — a zone groups rooms
  directly, never other zones.
- **`Topology`**: a third, complementary piece of WHERE, distinct from both `Location` and `Zone`.
  `Location` says *which* place a fact is about; `Zone` says *an explicit group someone declared*;
  `Topology` says *how rooms physically relate to each other* — adjacency, openings between rooms,
  connection type, orientation, floor. It is not itself a fact producer or a fusion input — it's
  context that `FusionRule`s, Reactions, and template requirements can query (e.g. "does this room
  have an opening to the outside," "what's adjacent to it") when deciding whether and how to act.
  → `v3_house_fact_draft.md` §WHERE.

---

## Layer 2 — Registries (who produces / consumes facts)

- **`Sensor`**: `binding: ReadBinding` + `where: Location` + `fact_type` + an `Interpretation`
  (resolved 2026-09-08, Layer 2 §3.1). Every Home Assistant **readable signal path** Heima cares
  about is registered exactly once, here — one registry, not several independently-configured entity
  lists for different purposes. A signal path is more precise than an entity id: the same HA entity can
  legitimately produce several `Sensor`s through distinct bindings (e.g. `climate.*` state,
  `current_temperature`, `hvac_action`) while the producer uniqueness invariant stays
  `(fact_type, Location)`, not "one sensor per entity." A `ReadBinding` only extracts the raw input for
  the current cycle (`state`, one attribute, or Layer-0-extracted active calendar windows); an
  `Interpretation` is how that raw input becomes a typed `HouseFact` value, one per genuinely distinct
  decoding mechanism, not one per HA domain (resolved 2026-09-05, collapsing three hardcoded-vocabulary
  variants — boolean/presence/media-activity — into one): an exact-match mapping (a configurable
  raw-string-to-value table plus a default for anything outside it — a `default` value makes it total,
  e.g. boolean on/off; `default=NO_DEFAULT` makes an unmapped state mean "no signal," e.g. a lock or
  alarm vocabulary that only speaks for the states it knows; `default=None` is a real produced value,
  not the sentinel), strict finite numeric normalization to a `float`, a bucket vocabulary (ordered
  numeric thresholds, e.g. dark/dim/bright), or calendar-window aggregation composed with the reusable
  pure `KeywordClassifier` (fuzzy keyword matching with a priority order for conflicts, open-ended by
  nature since admins define the keywords).
- **`FusionRule`**: how N facts become one derived `HouseFact` — inputs may come from `Sensor`s, or
  (resolved 2026-09-04) from another `FusionRule`'s own output, addressed uniformly by
  `fact_type`/`Location` rather than by producer id. A genuinely separate concept from `Sensor`, not
  folded into it, because not every sensor needs fusing (a context-recording sensor can stand alone)
  and not every fusion has just one shape. `FusionStrategy` is a **closed union of five kinds**, not
  an open-ended registry (resolved 2026-09-02, AR-4 follow-up — an earlier version of this recap
  described the strategies as living in "an extensible registry," which turned out to conflict with
  the actual drafted type; the closed union preserves exhaustive pattern-matching, which the project
  favors consistently elsewhere in this model): direct passthrough (relabel one fact under a new
  `fact_type` — always exactly one input, `Location` unchanged; resolved 2026-09-05, no real use case
  survived for changing location during a passthrough), unanimity (true only if every currently-
  available input agrees — resolved 2026-09-08, renamed and narrowed from a `BooleanSetStrategy`
  with an any/all mode: "any" was a pure redundancy with weighted quorum at weight=1/threshold=1.0,
  since "at least one" never needs its bar to scale with population size; "all" survives as its own
  strategy because unanimity's boolean-`True` bar must scale with how many inputs are actually available each cycle,
  which a fixed weighted-quorum threshold cannot express), weighted quorum (also covers a plain count
  threshold — every weight equal to 1 — and, resolved 2026-09-07, deliberately never folds in each
  input's own confidence/reliability, only its configured weight, since weight already is that lever
  and a second one would risk contradicting it), precedence (an ordered fallback chain: try each
  source in order, first definitive value wins — the one strategy allowed to mix source locations
  freely, since a fallback may legitimately be coarser or differently-scoped than what it
  approximates), and
  a fifth, deliberately narrow `FormulaStrategy` for cases where the combination is a genuine
  calculation rather than a generic pattern (e.g. combining temperature, wind, and humidity into one
  effective value, or Heating's Season derivation) — this one variant carries no calculation logic
  itself, only a reference into a separate, core-team-curated formula registry (mirroring
  `NormalizationFusionRegistry`'s existing plugin pattern), so a new formula never requires reopening
  `FusionStrategy` or any code that pattern-matches on it. Each registered formula explicitly declares
  whether confidence is continuous (value plus dispersion), categorical (value plus support/total),
  or inherited from one declared available input; it receives the complete ordered input sequence,
  including unavailable facts, so it can distinguish missing from negative evidence without I/O or
  hidden state. `physical_evidence.weighted_evidence` additionally receives a typed per-input binding
  of role, true/false weights, false requirement, explicit admission, and correlation group. It
  supports both room `occupancy.physical` and casa `presence.physical`: one correlated physical source
  family contributes at most one vote, and only explicitly immediate evidence may take the fast
  primary path. New sensor kinds alter configuration rather than formula code. A formula configuration
  is persisted as bounded canonical JSON and compiled once during generation staging into that
  formula's private immutable type; the evaluator never parses it.
  The formula catalog is core-built and frozen before cycles; its immutable id and semantic
  implementation version are persisted with each resolved binding, while callables are not.
  A changed version selectively invalidates only dependent fusion rules. No formula is assumed
  continuous merely because it calculates something. `Stability` commits a no-dwell transition in the
  same cycle, while a positive dwell owns one token-checked deadline that re-evaluates current
  in-memory inputs at expiry rather than polling or committing an old candidate. It can additionally
  retain a committed boolean result for an explicitly bounded unavailable grace, armed by one deadline
  and never restored after restart; it cancels, rather than completes, an interrupted directional
  dwell. A
  `FusionRule`'s output can carry its own
  stability/dwell `Window`, independent of which strategy produced it — debounce and hysteresis are a
  property of *any* derived fact's stability over time, not specific to one combination method.
  Each fusion owns its compact ephemeral control state, while Layer 0 supplies only deadline jobs and
  historical fact buffering; this keeps control lookups O(1) and avoids treating runtime state as
  history.
  Resolved 2026-09-12: only a `FormulaStrategy`, after its core binding validator has explicitly
  allowed it, can address its exact own *previous*-cycle value (`FactRef.previous_cycle=True`). This
  narrow self-memory makes a recursive/temporal computation (a Bayesian filter using its own last
  posterior as this cycle's prior, an exponential moving average) expressible without a sixth strategy
  or breaking `compute`'s pure signature. The memory arrives as an ordinary `HouseFact` input from
  Layer 0's sealed in-memory snapshot; only after a clean restart is that snapshot pre-hydrated from
  the matching committed durable state.
- **`Actuator`**: an inventory fact only — which entity, where, optionally which physical opening it
  operates, optionally which coarse role it plays (light, shutter, HVAC unit, water valve, switch...
  — deliberately an open string, never a closed enum, since HA's own device domains keep growing),
  and (resolved 2026-09-06, restoring a dropped Layer 0 decision) whether it's eligible for implicit
  manual-hold restoration after a restart — never a command itself. One HA command endpoint has one
  Actuator record; an optional opening must belong to its room, while lights and other ordinary room
  equipment have no opening relation. Commands live only in whichever
  Reaction decides to send them. → `docs/specs/v3/layer2_registries_spec.md`; the older
  `v3_sensors_actuators_draft.md` remains background only and no longer reflects the current `Sensor`
  shape.

---

## Layer 3 — Learning / pattern recognition

Mines the history Layer 2 produces; it is not itself a fact producer in the live, per-cycle sense
Layer 2 is — it runs on its own slow cycle (on the order of hours), reading accumulated `HouseFact`
history rather than the current cycle's live entity states.

Learning requests a retention duration from Layer 0, but that request is not allowed to defeat the
50,000-record per-`fact_type` hard ceiling or the 512 MiB global pruning watermark. Each history read
carries retention coverage; a pruned requested window keeps the learner in warm-up/degraded mode rather
than letting it infer from a silently shortened sample. Latest state records remain protected even
under global storage pressure.

**Disambiguation from Layer 2's `FusionRule`** — same surface shape ("combine multiple facts into
one"), genuinely different job. `FusionRule` combines *current* facts, same cycle, synchronous
logic, no history beyond ordinary stability/dwell handling. `PatternLearner` mines *history*, slow
cycle, statistical bucket-to-outcome models. Concrete example: a composite "effective outdoor
temperature" combining live temperature, wind, and humidity is a `FusionRule` — recomputed every
cycle, needs zero history. A house's own learned thermal-response rate (how fast its indoor
temperature actually rises or falls under given conditions) is a `PatternLearner` — it needs days of
history to mean anything and would make no sense recomputed every cycle.

- **Governing rule**: statistical signals never feed policy directly. The ordinary
  operational path is: a learning module's finding -> an analyzer -> a
  `LearningProposalCandidate` -> Layer-5 validation -> a reviewable `ReactionProposal` -> admin
  review -> a configured rule or reaction. Two output shapes, both downstream of this rule:
  - **`InferenceSignal`** — feeds one named Layer-4 `SemanticResolver`, but only through a closed,
    individually-scoped `IndirectAssistanceContract`. Initial V3 has one signal type,
    `indirect.semantic_assist.v1`, used by the physically referenced positive occupancy contract and
    resident-approved-routine positive sleep-, relax-, and domestic-working-context contracts; every
    other statistical signal is diagnostic-only by design — computed and observable, but never
    consumed by semantic resolution.
  - **`LearningProposalCandidate`** — the registry-analyzer stage's typed hand-off to Layer 5 (one
    analyzer per learning family — heating, lighting, presence, room-assist composites, security
    presence simulation). Layer 5 alone validates it and creates the reviewable `ReactionProposal`,
    always gated by admin review, no exception.
- **`PatternLearner` and optional ML models** — `PatternLearner` is the shared, explainable baseline
  every learning family builds on, instead of each hand-rolling its own bucket/threshold/confidence
  logic: buckets history by an arbitrary key,
  `min_support` as a boolean pass/fail gate ("not enough data" means no output, never "low
  confidence"), a warm-up gate (a combined time-elapsed-and-sample-count floor, per learning
  subject, so a burst of setup/testing activity right after something is enabled or reconfigured
  can't poison the model), a confidence value computed by exactly one of two standard formulas
  depending on what's being predicted (a match ratio for a categorical outcome, an inverse-dispersion
  score for a continuous one — never reinvented per family), and a generalized tiered fallback (try
  the most specific model with enough support, fall back to a coarser one, down to the coarsest).
  A bounded ML model may use the same historical bindings when the baseline cannot express a real,
  measurable relationship. It trains off the hot path, publishes a versioned validated artifact, and
  has no additional authority over semantic claims or actions. Local in-process training is bounded and may
  be deferred under runtime pressure; a future opt-in backend may execute a bounded redacted job in a
  subprocess or remote server, but local Heima retains validation, promotion, inference, and all
  authority. The first candidate is a topology-constrained thermal model: it may estimate effective
  thermal coupling and temperature trajectories from temperature/HVAC/opening facts, while claiming
  airflow or air quality only when corresponding measurements exist.
- **Governance**: whether a learning family runs at all is a single admin-facing toggle, covering
  both the slow-cycle analyzer stage and any bounded live-signal module in the same family — not two
  separate, inconsistently-gated mechanisms.
- **Reads**: Layer 1's `HouseFact`s directly, queried by `fact_type`/`Location`/time window — never
  through a bundled intermediate snapshot shape.
- **Layer 7 (Extensibility) connection**: a third-party plugin may register a separately staged
  analyzer over immutable findings, but it emits only a `LearningProposalCandidate` for Layer-5
  validation — never a learner/model type or a `ReactionProposal` directly. It never gets a seat at
  the live-`InferenceSignal` tier, which stays a short, individually-audited list that only the core
  team extends.
  → `v3_pattern_learner_draft.md` for the concrete shape; `v3_backlog.md` §"Learning pipeline"
  sections and §"Full architecture re-review" (AR-1 through AR-6) for the full reasoning trail.

---

## Layer 4 — Semantic Resolution (the DAG)

Layer 4 materializes independently owned `SemanticState` claims and event-only
`SemanticEpisode` occurrences from Layer-2 facts and bounded Layer-3 signals. Each
`SemanticResolver` is registered, validated and dependency-ordered in a staged DAG. A resolver reads
fresh Layer-2 facts and only the prior-cycle outputs of other resolvers, so the evaluation is
acyclic and deterministic in one pass.

The initial semantic claims are `room_occupancy`, `presence`, and independently scoped
`activity.<activity_id>`. They intentionally do not form one global enum: presence, activity,
quiet/sleep context, planned absence and guest context can coexist and require their own vocabulary,
evidence, availability and safety contracts. The monolithic V2 `house_state` is retired rather than
being recreated as a V3 claim. See the authoritative Layer-4 specification for exact contracts.

---

## Layer 5 — Action / reaction generation

**Freshness rule** — the opposite of the prior-cycle rule inside Layer 4: Reactions read the
*current* cycle's semantic claims and Layer-2 facts. Semantic resolvers restrict dependencies on
other semantic resolvers to prior-cycle outputs specifically to keep the DAG acyclic; Reactions run
strictly *after* the full DAG has resolved for that cycle, so no resolver can depend on a Reaction's
output within the same pass. Layer-2 facts are likewise recomputed before semantic resolution, so a
Reaction can read the current fine-grained detail such as a room's lux bucket.

- **Reactions** produce ordered `ApplyStep`s, each carrying an `ApplyStepSource` (Layer 0's provenance
  vocabulary) and addressing exactly one Layer-2 `Actuator` by id. The runtime alone resolves the HA
  endpoint; a step cannot override it with a target selector, while HA remains the source of truth for
  the service schema and supported operation. A `ReactionProposal` is a `HouseFact` plus `Provenance`,
  wrapped with a review status (pending/accepted/rejected) and an identity/fingerprint for deduplication
  — not a separate, bespoke shape.
- **Template-driven auto-proposals**: an admin-authored automation template can declare what it
  needs — some `Sensor` fact types, some `Actuator` roles, optionally a topology requirement (e.g.
  "needs an opening to the outside"). A generic matcher scans every `Location` against every
  template with requirements declared, and where the registries already satisfy what a template
  needs, it proposes the automation automatically — no per-template bespoke discovery code, one
  generic path for every template that opts in. Its defaults are derived from what the matched
  `Sensor`'s `Interpretation` actually looks like (e.g. which lux bucket exists) rather than a
  guessed room-type heuristic.
  → `v3_template_matching_draft.md`.

---

## Layer 6 — Notification / communication

One pipeline handles every outbound notification — operational events (a reaction fired, a security
condition, a semantic-claim transition) and review items (a new learned proposal, N new automation
suggestions) alike — instead of one sophisticated, configurable path for the former and a separate,
unconfigurable direct-call path for the latter.

- **Quiet hours are resolved per family/type, not as one blanket switch**, in 3 behaviors: `bypass`
  (security-posture-relevant, can't wait — e.g. "went to sleep without arming security"), `defer`
  (held until quiet hours end, folded into the digest), `silent` (never actively pushed at all —
  template-match proposals land here, since "N automations are now possible" is never urgent).
  Quiet-hours-active is a dynamic condition (an active `sleeping` `HouseFact`), not a fixed clock
  window.
- **Digest**: a periodic batch summary ("12 new suggestions today") instead of one push per item —
  the mechanism that makes routing large volumes of low-urgency review items to `defer`/`silent`
  actually usable instead of just delayed spam. Not yet built.
  → `v3_backlog.md` §Notifications.

---

## Layer 7 — Extensibility (third-party plugins)

- **Pull only**: the core always controls when a third-party plugin runs and what it can see —
  plugins never push data or trigger evaluation on their own, matching the same trust envelope
  built-in semantic resolvers already operate under.
- **Registration seam**: a generic `register_plugin(...)` call, validated only for
  duplicate identity and registration timing. The only structural gap is *discovery* — something to
  call it for externally-sourced plugins without hand-editing a hardcoded built-in list; two
  candidate mechanisms (Python entry points vs. a Home Assistant `hass.data` handshake), not yet
  chosen.
- **Needed for untrusted code specifically**: fault isolation (every plugin's `compute()` call runs
  inside a boundary — a failure is skipped for that cycle and surfaced as a diagnostic event, never
  taking the whole engine down) and a version-compatibility check at registration, so an
  incompatible plugin is rejected loudly, never loaded silently broken.
- **Two capability tiers, declared at registration**: `read_only` (facts/signals only —
  fail-closed: if a `read_only` plugin returns an `ApplyStep` anyway, it's dropped and logged, never
  executed) vs. `apply` (can command actuators). Activating `apply`-tier authority for a newly
  registered plugin goes through the same one-time, admin-confirmed, persisted approval flow used
  elsewhere for promoting a pending automated action to trusted status — a new `apply` plugin runs
  in shadow mode (computes what it would do, without doing it) until then.
- **Open tension, not resolved**: this project's "no backward compatibility, sole user of the
  project" stance is incompatible with a public plugin API by definition — shipping this needs a
  conscious, explicit amendment to that rule (e.g. scoped to internal-only contracts), not a silent
  exception.
- **Connection to Layer 2**: a third-party plugin can have its own `Sensor`/`Actuator` entries (a
  soil-moisture sensor for a hypothetical watering plugin, say) — through the same admin-panel
  registry CRUD every built-in `Sensor`/`Actuator` goes through, not a private, invisible read of
  raw entity state. Registration itself stays admin-gated: a plugin may declare what it needs, but
  the registry record is created through the panel, never silently self-registered against
  arbitrary entities — the same reasoning as pull-only, one layer up.
  → `v3_backlog.md` §Third-party plugin API, §"Full architecture re-review" (AR-8).

---

## Layer 8 — Admin / configuration surface

Two UI surfaces, each with a clear job. A linear, step-based config flow for settings that are
genuinely occasional and don't benefit from a registry-style editor (notification delivery policy,
plugin `apply`-authority grants, general settings). An admin panel for everything registry- or
review-shaped, itself with two mutation patterns: a dedicated CRUD endpoint per registry
(`Sensor`/`Zone`/`FusionRule`/`Actuator`/`Topology`, full structural editing — the right tool for
relational/graph-shaped data that a linear form doesn't fit well) and a generic action dispatcher
for point-actions on existing objects (accept/reject/remove one proposal, clear one hold — not full
CRUD, just a discriminated action call). Proposal review, including new template-match proposals,
goes through the generic-dispatcher pattern.
**Still open**: whether Reactions (today reachable from both surfaces, with no dedicated panel
mutation endpoint) should move fully into the panel once template-matching reduces how often an
admin needs to author one by hand.
→ `v3_backlog.md` §Configuration surface.

---

## Cutting across every layer — observability

Not its own subsystem. It's the `correlation_id` chain in `FactSource`/`ApplyStepSource` (Layer 0)
threading through every layer above: a resolved `SemanticState` or `SemanticEpisode` traces back through the `HouseFact`s
that fed it (Layers 1-4, including Layer 3's bounded `InferenceSignal`s), back through any
`ReactionProposal`/reaction that produced them (Layer 5), forward to any `ApplyStep` that resulted
(Layer 5, same vocabulary), surfaced through the admin panel (Layer 8). One thread, not a parallel
explainability system built on top.

---

## What's still genuinely open across all layers

1. Third-party plugin discovery mechanism (entry points vs. an `hass.data` handshake) — not chosen.
2. The digest notification capability — designed for, not built.
3. Routing proposal notifications through the Layer-6 pipeline instead of a separate direct-call
   path — depends on the digest existing first.
4. Which admin-authored templates get a `TemplateRequirement` declared first.
5. Whether Reactions configuration moves fully into the admin panel (Layer 8).
6. The "no backward compatibility" project rule vs. a public plugin API (Layer 7) — needs a
   conscious amendment, not a silent exception.
7. A namespacing convention for third-party-registered identifiers
   (`"plugin.<plugin_id>.<name>"`) — not yet enforced anywhere, needed before Layer 7 ships to avoid
   cross-plugin collisions. Covers `fact_type`, `proposal_type`, and `reaction_type` alike.
8. ~~Functional-policy redesign work...~~ Resolved 2026-09-02 — promoted to `v3_domains_draft.md`
   (Lighting's `PrecedenceRelation`, Heating's reconciled `HeatingBranch` and thermal model,
   Security's `SequentialConfirmationPolicy`).
