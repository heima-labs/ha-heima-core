# Heima v3 — Layer 0: Cross-Cutting Runtime Facilities

**Status:** Draft — pending developer approval. Not implemented.
**Layer:** 0 of 8 (of the v3 architecture: Substrate, Registries, Learning, Domain resolution,
Reactions, Notification, Extensibility, Admin surface build on top of this one).

This document is self-contained: it defines what Layer 0 is and does without assuming the reader
has read Heima's v2 specs. Where v2 already solved a piece of this problem, that solution is
restated here in full, not referenced as a prerequisite — v2 documents are listed at the end,
background only.

## Normative precedence

This document defines the intended contract for Layer 0 once approved. Until the developer
confirms it explicitly ("ok, proceed"), it is discussion material, not an implementation target.
Once approved and implemented: if code and spec diverge, the divergence must be resolved
explicitly — code is a reference implementation, not the source of truth.

---

## 1. Purpose

Layer 0 collects the runtime facilities that sit **outside the domain DAG** entirely: nothing in
Layers 2-5 (Registries, Learning, Domain resolution, Reactions) may depend on a Layer 0 facility
changing mid-cycle, and nothing in Layer 0 depends on any domain. Five facilities:

1. **Timing** — one execution primitive plus a recurrence policy layer, and non-executing
   comparison types for reasoning about elapsed or absolute time without scheduling anything.
2. **Persistence** — the two-tier storage `HouseFact` (Layer 1) is built on top of.
3. **`FactSource` / `ApplyStepSource`** — one structured-provenance vocabulary spanning facts and
   actions, and the `correlation_id` rules that make "why did the house do this" answerable.
4. **Manual Hold Manager** — represents a resident's explicit or inferred override, with
   deliberately different restart guarantees depending on how confident Heima can be in it.
5. **Recovery / Checkpoint** — pre-DAG classification of runtime health (just started, recovering
   from a power loss, degraded, normal), and the durable checkpoint that backs it.

## 2. Scope

Layer 0 is responsible for:
- the one execution primitive ("at") and the one recurrence policy layer ("cron") every other
  subsystem's time-driven behavior is built from;
- the non-executing comparison types (`Window`, `CalendarWindow`) used to reason about elapsed or
  absolute time;
- `HouseFact` storage mechanics (durable + short-term tiers) — not the `HouseFact` type itself,
  which is Layer 1;
- the non-forgeable provenance vocabulary attached to every `HouseFact` and every `ApplyStep`, and
  the rules for how a `correlation_id` is minted and propagated;
- representing an active manual override, including when (and how safely) it may survive a restart;
- computing pre-DAG recovery/degradation context and the checkpoint that backs it.

Layer 0 is **not** responsible for:
- domain policy logic, signal fusion, or actuator commands (Layers 2-5);
- deciding *what* triggers a re-evaluation cycle. Heima is event-driven: evaluation is triggered by
  meaningful state changes, not by a fixed timer. Timing's periodic fallback (§3.1) is a bounded
  safety net against missed events, not a return to timer-driven evaluation;
- defining the `HouseFact` type, `Location`, `Zone`, or `Topology` (Layer 1) — Layer 0 consumes
  `HouseFact` and references `Location`, it does not own either.

### 2.1 Non-goals

- Prescribing internal class layout beyond the shapes below.
- Domain policies that happen to use a `Window` or a `CronEntry` (e.g. a specific reaction's dwell
  time) — those are Layer 4/5 concerns configuring a Layer 0 primitive.
- Whether `scheduled_routine`-style reactions should delegate to Home Assistant's native
  `schedule.*` helper entity instead of a Heima-owned recurrence picker — open, §11.

---

## 3. Timing

**Time representation**: every `datetime` in this layer — and, by extension, every instant on a
`HouseFact` (Layer 1), a checkpoint entry (§7), or anything else built on top of Timing — is
timezone-aware and stored/compared in **UTC**. A naive `datetime` (no `tzinfo`) is never valid
anywhere in this model — it is ambiguous by construction (local or UTC?) and a classic source of
comparison bugs across sources. The one deliberate exception is `WeeklyRecurrence.hour`/`minute`
(§3.1 below), which are defined in the installation's configured local civil time on purpose,
converted to UTC only at computation time. Conversion to a human-readable local time happens
exclusively at the presentation boundary (admin panel, notifications, diagnostics) — never inside
internal logic.

### 3.1 Execution: `AtJob` and `CronEntry`

```python
@dataclass(frozen=True)
class AtJob:
    job_id: str        # unique within the owning subsystem; re-registering the same job_id
                        # replaces the pending job, it does not error or duplicate it
    owner: str          # subsystem name, e.g. "house_state", "manual_hold", "engine"
    due: datetime        # the wall-clock instant this job is meant to fire at, UTC, timezone-aware
    label: str
```

`AtJob` is the **one** execution primitive: a scheduled one-shot deadline.

**Scheduling semantics**: `due` is a wall-clock instant, but *dispatch itself must be
monotonic-safe* — at arm (or re-arm) time, Timing computes `due - now()` **once** and schedules
that duration on a monotonic timer. The pending countdown is never re-evaluated against wall-clock
time while armed. This means a system clock adjustment (NTP correction, or a Daylight Saving Time
transition) that happens *while a job is pending* cannot cause it to fire early, late, or twice —
the same robustness property Heima's current manual-hold expiry (a hand-rolled monotonic float)
already has, carried forward into the shared primitive instead of reimplemented per subsystem.

**Re-registration**: `job_id` is a replace key, not a uniqueness constraint to reject on conflict —
registering an `AtJob` with an already-pending `job_id` cancels the old timer and arms the new one.
This lets an owner simply "set the deadline to X" without first checking whether one already exists.

```python
@dataclass(frozen=True)
class WeeklyRecurrence:
    weekdays: frozenset[int]   # 0-6, non-empty
    hour: int
    minute: int = 0

@dataclass(frozen=True)
class IntervalRecurrence:
    interval_s: float

RecurrencePattern = WeeklyRecurrence | IntervalRecurrence

@dataclass(frozen=True)
class CronEntry:
    job_id: str
    owner: str
    pattern: RecurrencePattern
    label: str
```

`CronEntry` is the recurrence policy layer on top of `AtJob`. Two separate shapes instead of one
dataclass with optional fields, because "run every Monday at 07:00" and "run every 300 seconds" are
genuinely different kinds of rule, not the same rule with some fields unset — `WeeklyRecurrence`
answers "which wall-clock moments", `IntervalRecurrence` answers "how often, relative to now".

For a `CronEntry`, Timing computes the next `due` from `pattern` relative to now, arms an `AtJob`,
and on fire recomputes and re-arms. For `WeeklyRecurrence`, `hour`/`minute` are civil-time values in
the installation's configured local timezone (Home Assistant's own `time_zone` setting) — computing
the next `due` means taking `now` (UTC), converting to that local zone, finding the next matching
weekday/hour/minute there, then converting the result back to UTC for storage/scheduling. **This
must use timezone-aware calendar arithmetic** (`zoneinfo`, not naive `datetime + timedelta(days=7)`
and not fixed-offset math) — a Daylight Saving Time transition changes whether "the same local
wall-clock time next week" is 167, 168, or 169 hours away in UTC terms, and only correct
calendar-aware arithmetic gets this right; the point of converting through local time at all is that
"07:00" must stay 07:00 for the resident across the transition, not drift by an hour. This
recomputation happens once per re-arm; the resulting delay is then handed to the same monotonic dispatch
mechanism as every other `AtJob`, so Daylight Saving Time only ever touches this one narrow
computation, never the dispatch mechanism itself. `WeeklyRecurrence` also classifies the past, not
just schedules the future: `pattern.matches(fact.when)` answers "did this fact occur on a matching
weekday/hour" for bucketing.

`CronEntry`'s **definition** (owner, pattern, label, job_id) is treated as durable configuration —
an admin-authored recurring routine, or a system-owned periodic safety net, is a standing rule that
outlives any single pending countdown. This is why `CronEntry` state is expected to survive a
restart (the *rule* is re-read from configuration, a fresh `due` is computed against current time,
and a new `AtJob` is armed — nothing about the interrupted countdown needs to be recovered) while a
one-shot `AtJob` that belongs to transient runtime state (see §6, Manual Hold) generally does not:
if nothing persists the reason an `AtJob` should exist, there is nothing to re-arm it from after a
restart. This is a design choice about what counts as durable configuration, not a limitation of
`AtJob` itself — §6 describes a case where a one-shot deadline is deliberately made restart-eligible
by giving the owning subsystem its own durable record to re-arm from.

Every recurring or periodic thing in the system is a `CronEntry` owned by whichever subsystem needs
it — an admin-authored scheduled routine, a periodic safety-net re-evaluation, Recovery's own
checkpoint-write cadence (§7) — never a bespoke timer mechanism invented per feature.

### 3.2 Comparison: `Window` and `LearnedWindow`

```python
@dataclass(frozen=True)
class Window:
    seconds: float
```

`Window` is a bounded time span, **not an execution concept** — a comparison/relation over
`HouseFact` timestamps. One shape serves two uses: dwell ("has fact X been true for at least
`seconds`") and correlation/follow-up ("did fact Y occur within `seconds` after fact X"). They
differ only in which two timestamps they compare, not in shape.

```python
@dataclass(frozen=True)
class LearnedWindow:
    seed: Window            # starting value, e.g. a per-room-type default
    calibrated_from: str    # fact_type to mine history from, e.g. "occupancy"
    where: Location          # scope of the history mined for calibration — a LearnedWindow used by
                              # a specific room's reaction calibrates from that room's history, not
                              # an ambiguous global pool
    min_seconds: float       # calibration is clamped to this range; never allowed to drift below it
    max_seconds: float       # or above it

Window | LearnedWindow    # anywhere a Window is expected, a LearnedWindow may be substituted
```

`LearnedWindow` lets a dwell or correlation timer calibrate itself from observed history instead of
using a fixed seed forever. Two properties are load-bearing, not optional refinements:

- **`where` is mandatory**, matching Layer 1's rule that a `Location` is always present, never
  absent — without it, "calibrated from occupancy sessions" is ambiguous between the whole house and
  one specific room, and two `LearnedWindow` instances could silently blend unrelated data.
- **`min_seconds`/`max_seconds` are mandatory clamps.** A `LearnedWindow` feeds dwell timers that
  gate physical actuation — an uncalibrated or degenerate value is a real risk, not a theoretical
  one: a calibrated value drifting toward zero causes flicker (rapid on/off), drifting unbounded
  causes a stuck actuator (a light that never turns off). This is a Layer 0 guarantee precisely so
  every call site doesn't have to remember to add its own floor and ceiling.

No calibration formula (e.g. percentile-of-past-durations) is specified here — that is an
implementation detail for whichever domain/`FusionRule` uses a given `LearnedWindow`, not a
Layer 0 policy choice.

### 3.3 `WarmupGate`

```python
@dataclass(frozen=True)
class WarmupGate:
    min_elapsed: Window   # time floor since the subject became eligible
    min_samples: int      # sample-count floor since the subject became eligible
```

Per learning subject (a family/room/reaction, not global). **AND semantics, not OR**: a time-only
gate lets a dense test burst (e.g. an admin toggling something 20 times while wiring a room) satisfy
a short window instantly, with exactly the data that should be excluded; a sample-only gate lets the
same burst satisfy a count floor just as fast. Combined, neither a fast dense burst (fails the time
floor) nor a long quiet stretch with no real usage (fails the sample floor) ends the warm-up window
alone. "Subject became eligible at" resets whenever the subject's configuration changes materially
(e.g. a room's role is reconfigured) — the reset itself is a subsystem-level concern, not specified
further here.

### 3.4 `CalendarWindow`

```python
@dataclass(frozen=True)
class CalendarWindow:
    start: datetime
    end: datetime
    category: str       # e.g. "vacation", "day_off", "holiday", "wfh", "office"
    source_entity: str
```

Extends the same "something at instant T" idea `AtJob` embodies to an externally-sourced, named,
**absolute** interval (not relative to "now" like `Window`), classified by a calendar
interpretation (Layer 2), sourced from a Home Assistant `calendar.*` entity. Membership checks ("is
`now` inside a vacation `CalendarWindow`") are a plain containment comparison between
timezone-aware datetimes, evaluated fresh every cycle against the current `now` — not a
scheduling operation, so Daylight Saving Time does not affect it as long as `start`/`end`/`now` are
all timezone-aware.

Calendar sits in Layer 0, same rank as "at"/"cron" — **not** a domain (Layer 4), not a third-party
plugin (Layer 7). It is evaluated before the core DAG runs each cycle, same as Recovery/Checkpoint
(§7), and never through a plugin registration mechanism.

Resolving a conflict between two simultaneously-active `CalendarWindow`s with different categories
(e.g. two calendar sources disagreeing) is a Layer 4 concern — Layer 0 only provides the
containment primitive, not a precedence rule between sources.

---

## 4. Persistence

`HouseFact` (Layer 1) storage is **always atomic** — one fact per WHAT/WHERE/WHEN/HOW, written at
exactly the granularity the engine computes at internally (per-room, per-signal), never a bundled
record. A "snapshot" (everything true at one instant, or in one place, over one window) is never its
own stored shape — it is a **query reconstructed at read time**: "every `HouseFact` true in
`Location` X between t1 and t2." A generic consumer (including a Layer 7 third-party plugin) never
needs to learn a bespoke bundle type to read Heima's history — it queries `HouseFact` by
`fact_type`/`Location`/time window, the same API every consumer uses.

### 4.1 Two storage tiers

- **Durable long-term store** — disk-backed, for learning (Layer 3) and audit. Feeds queries over
  days to weeks of history.
- **Short-term in-memory buffer** — no disk I/O, for correlation/follow-up matching
  (`Window`-based, §3.2) within a bounded recent window.

Two tiers because they have genuinely different cost profiles: correlation matching happens on the
hot per-cycle path and can never wait on a disk read; long-term learning needs history that cannot
fit, or be affordably kept, entirely in memory. A `HouseFact` write touches the in-memory buffer
immediately (no I/O cost) and reaches the durable tier through the batching policy below.

### 4.2 Write policy

Writes to the durable tier are **batched at the end of each evaluation cycle** — buffered during the
cycle, flushed once after the domain/reaction pass completes, rather than one disk write per fact.
This keeps the per-fact hot path free of I/O.

**Write-on-change**: a fact is included in the flush only if its value differs from the last stored
value for the same WHAT/WHERE/HOW key. A fact whose value is unchanged from the previous cycle is
not re-persisted to the durable tier (it still updates the in-memory buffer, which has no I/O cost).
This avoids paying disk-write cost for facts that are read every cycle but change rarely (e.g. a
`casa`-scoped fact that's stable for days).

### 4.3 Retention

Retention is **time-based per `fact_type`, with a per-`fact_type` record-count ceiling as a safety
valve** — not one global count-based cap. Two independent reasons this combination, not either alone:

- **Why time-based, not count-based, as the primary policy**: atomic per-fact storage produces far
  more records for the same information than a bundled snapshot would, and Layer 3 learners reason
  about history in days (a `history_window` of 7 days, a `WarmupGate.min_elapsed` of weeks), not in
  record counts. A pure count cap would be exhausted in hours by the finer granularity, silently
  breaking exactly the learning use cases this model exists to serve. Persistence keeps a small
  `fact_type -> retention_floor` table, but — consistent with Layer 0 depending on nothing above it,
  the same rule §6.3 applies to Manual Hold's eligibility check — it never populates that table by
  reaching upward to query Layer 3's registrations. Instead, whichever subsystem registers a learner
  **declares** its retention need against Persistence at registration time (e.g. "retain at least 30
  days of `heating.temperature_rate`") — a one-directional push, not a live query. A `fact_type`'s
  effective retention window is the larger of the system-wide default and every declared floor
  against it, so a learner that needs 30 days is guaranteed that much, without every `fact_type`
  needing an individually hand-tuned setting.
- **Why still a count ceiling, per `fact_type`**: a time-based window alone doesn't protect against
  one pathologically noisy `fact_type` (a flapping sensor writing every few seconds) consuming disk
  space disproportionately. The ceiling is scoped **per `fact_type`**, not global, so one noisy
  `fact_type` evicting its own oldest records early cannot crowd out retention for every other
  `fact_type` sharing a global budget. Hitting the ceiling raises a diagnostic warning (§9), since it
  usually indicates a misbehaving sensor worth investigating, not a config value to silently absorb.

---

## 5. `FactSource` / `ApplyStepSource`

One structured-provenance vocabulary spans both facts and actions. `FactSource`/`ApplyStepSource`
are the values that sit inside, respectively, a `HouseFact`'s `how` field (`Provenance`, owned by
Layer 1) and an `ApplyStep`'s `source` field (Layer 5) — Layer 0 owns this vocabulary and the rules
around it; Layer 1 and Layer 5 own the envelopes it's embedded in. Every `HouseFact` and every
`ApplyStep` carries:

```python
@dataclass(frozen=True)
class FactSource:
    kind: FactSourceKind
    source_id: str                          # stable id within that kind, e.g. an entity id,
                                              # an analyzer id, a reaction id
    source_type: str | None = None          # optional family, e.g. reaction type
    actor_type: FactSourceActorType = "heima"
    correlation_id: str = field(default_factory=lambda: str(uuid4()))  # see §5.2 — this default is
                                              # a safety net only, never relied on in production code
    # deliberately no actor_id: a fact isn't produced by a human the way an admin_command/
    # resident_response action is authorized by one — add it back only if a concrete need surfaces,
    # not by default symmetry with ApplyStepSource

@dataclass(frozen=True)
class ApplyStepSource:
    kind: FactSourceKind                    # minus the 3 fact-only kinds below — an action is never
                                              # kind="sensor"/"analyzer"/"third_party_plugin"
    source_id: str
    source_type: str | None = None
    actor_type: FactSourceActorType = "heima"
    actor_id: str | None = None              # the one field that differs from FactSource: which
                                              # human/service actually authorized this action, when
                                              # known (an admin user id, a resident's response id)
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

FactSourceKind = Literal[
    # fact-only — an action (ApplyStepSource) is never one of these three:
    "sensor",             # a direct read of one raw HA entity, interpreted (Layer 2 Sensor) — one
                            # entity in, one fact out, no combination
    "analyzer",            # derived from combining or analyzing existing data rather than one direct
                            # entity read — a same-cycle deterministic combination (Layer 2 FusionRule),
                            # a slow-cycle statistical computation (Layer 3 PatternLearner), or a
                            # structural match (Layer 5's template matcher). The unifying property is
                            # "derived from something other than a single direct entity read", not
                            # "statistical" specifically — FusionRule belongs here, not under "sensor"
    "third_party_plugin",  # produced by a Layer 7 plugin's own compute(), reading its own registered
                            # entities or combining them
    # shared with ApplyStepSource — both a fact and an action can carry these:
    "reaction",            # a fact recorded as a byproduct of a Reaction firing (Layer 5) — distinct
                            # from the ApplyStep(s) the same Reaction issues, which carry
                            # ApplyStepSource with this same kind on the action side
    "domain",               # produced by a Layer 4 domain's own resolution logic (e.g. HouseState's
                            # resolved value), not sourced from Sensor/FusionRule directly
    "admin_command",        # a direct consequence of an admin-panel action, assignable only after HA
                            # confirms the connection's user is an admin (§5.1)
    "resident_response",    # a direct consequence of a resident's explicit action (an explicit manual
                            # hold, Layer 0 §6; a runtime confirmation response) — assignable only
                            # after matching an active request, never from an unmatched payload
    "timeout",              # recorded because an expected response/confirmation window elapsed with
                            # nothing arriving — assignable only by the in-process timeout controller
    "recovery",             # produced by Recovery/Checkpoint itself (§7) — e.g. an implicit hold
                            # restored after a clean restart (§6.3)
    "system",               # produced by system-owned runtime infrastructure not covered by a more
                            # specific kind above (e.g. a system-owned CronEntry's own bookkeeping)
    "test",                 # produced by test code — never present in production data
    "legacy",               # predates structured provenance, could not be reassigned a real kind at
                            # migration time — never produced by new code
]

FactSourceActorType = Literal[
    "ha_admin",    # a Home Assistant user confirmed as admin by HA's own permission check
    "resident",    # a non-admin resident (a mobile-app response, an explicit-hold helper toggle)
    "heima",       # Heima itself, autonomously — no human in the loop for this specific fact/action;
                    # the default
    "scheduler",   # Timing's own execution (an AtJob/CronEntry firing), not a domain decision
    "service",     # an external HA service call not attributable to a specific admin/resident (e.g.
                    # an automation outside Heima calling into a Heima service)
    "system",      # Heima's own startup/runtime infrastructure (Recovery, Persistence), not a domain
                    # or a human
    "test",        # test code
    "unknown",     # could not be determined — never treated as authoritative for anything requiring
                    # a specific actor
]
```

One vocabulary, two shapes with one deliberate difference — never two independently evolving
designs. `ApplyStepSource` (the action-side sibling, produced whenever a `Reaction` emits an
`ApplyStep`) shares `kind`'s closed vocabulary (minus the 3 fact-only kinds), `actor_type`, and the
`correlation_id` mechanism; it carries `actor_id` because an action can be traced to a specific human
or service that authorized it, while a fact — even one produced as a side effect of a resident's
action — is not itself "authorized by" anyone the way a command is.

### 5.1 Non-forgeability: trust is derived, never stored

There is no persisted or externally-writable "trusted" field. Whether a given `kind` is legitimate
is derived by the code at the boundary that assigns it, never read off the data itself:

- a configured reaction can produce `kind="reaction"`, but cannot declare itself `admin_command`;
- an admin-panel action can produce `kind="admin_command"` only after Home Assistant confirms the
  connection's user is an admin;
- a resident's response can produce `kind="resident_response"` only after it matches an active
  runtime confirmation request;
- a third-party plugin (Layer 7) can produce `kind="third_party_plugin"`, but nothing it returns can
  make the core treat it as `kind="sensor"` or `kind="recovery"`.

Source data arriving from persisted config, proposal payloads, imported data, or any
externally-controlled input is **non-authoritative** until a runtime boundary validates or
reassigns it — an untrusted or malformed source is sanitized into a clearly non-authoritative value,
never silently trusted. This is what protects against, among other things, a Layer 7 plugin lying
about its own declared capability tier. Both `FactSource` and `ApplyStepSource` are redacted before
they reach diagnostics or storage (no secrets, tokens, or raw payloads retained).

### 5.2 `correlation_id`: generation and propagation

A `correlation_id` is what makes "why is the house in this state" answerable — following one id from
a resolved state back through the facts that fed it, and forward to any action that resulted. It is
an opaque string minted **once**, at a well-defined origin point, and propagated unchanged to
everything causally downstream of that origin within the same causal chain — never regenerated by
an intermediate step. Origin points:

- **A per-cycle evaluation**: one `correlation_id` is minted at the start of each engine evaluation
  cycle and propagated to every `HouseFact` (Layer 2 sensor/fusion output, Layer 4 domain output)
  and every `ApplyStep` (Layer 5) produced synchronously within that cycle.
- **A Layer 3 learning analysis run**: `PatternLearner.analyze()` runs on its own slow cycle, mining
  potentially days of history spanning many prior `correlation_id`s — it is a new causal origin, not
  a continuation of any one of them, so it mints its own fresh `correlation_id` for whatever
  `LearnedPattern`/`ReactionProposal` it produces. That output's evidence references the
  `fact_type`/`Location`/time-window query used to mine it, so the chain is still walkable backward
  to the source data, even though the relationship is many-to-one rather than one-to-one.
- **An admin or resident action** (accepting a proposal, clearing a hold, responding to a runtime
  confirmation): a new `correlation_id` is minted at the boundary that authorizes the action (the
  admin-verified handler, or the resident-response matcher), with `actor_type` reflecting who acted.
- **A Recovery-driven event** (§7), including a manual hold restored after a restart (§6.3): mints
  its own new `correlation_id` with `kind="recovery"`, distinct from the id the original hold was
  created under — the restore is its own traceable event, not a continuation of the pre-restart
  chain, since that chain's runtime state no longer exists to continue.

The dataclass-level default (a freshly generated id per instance) exists only as a safety net for
objects constructed outside a tracked causal chain (tests, ad hoc tooling). Production code paths
must explicitly pass down an inherited `correlation_id` at every one of the origin points above,
never rely on the default to "just work".

---

## 6. Manual Hold Manager

A manual hold is a resident's override that suppresses some automated behavior in some functional
domain (lighting, heating, security...) at some `Location`. Two kinds, with genuinely different
detection, release, and restart behavior — collapsing them into one undifferentiated shape would
lose real distinctions, not simplify anything:

- **Explicit hold**: the resident turns on a dedicated control (a helper entity, or an equivalent
  admin/panel-declared override) that unambiguously means "hold this." Because the control itself is
  a Home Assistant entity with state that Home Assistant already persists natively, an explicit
  hold's live status is **not stored or restored by Heima at all** — it is re-read fresh from that
  entity's current state every cycle, the same way any other `Sensor`-backed fact is. Restart safety
  comes for free from Home Assistant's own persistence, with zero additional mechanism needed here.
- **Implicit hold**: Heima infers an override from an *unexpected* state divergence — an actuator
  Heima manages shows a state Heima didn't command, and no other explanation accounts for it. The
  main such explanation is a **pending apply**: after a Reaction issues an `ApplyStep` (§5), Layer 0
  expects the target entity to reach that state within a bounded `Window` (§3.2) — an entity-side
  `HouseFact` change that matches an outstanding expected apply, within its window, is Heima's own
  doing and never triggers an implicit hold; only a divergence with no matching pending apply does.
  This is an inference, not a direct signal, and its reliability is exactly what §6.3 has to reason
  carefully about.

### 6.1 Representation

```python
@dataclass(frozen=True)
class ManualHoldValue:
    active: bool = True
    held_state: dict[str, Any] | None = None   # optional: the specific state/attributes the
                                                 # resident wants respected while the hold suppresses
                                                 # automation here (e.g. a thermostat's target), when
                                                 # the hold pins a value rather than only suppressing
```

An active hold is a `HouseFact`:
- `fact_type`: `"manual_hold.<domain>"` — `domain` is the functional behavior being suppressed
  (lighting, heating, security...), a field orthogonal to `where`, not folded into it.
- `value`: `ManualHoldValue`
- `where`: `Location` (Layer 1) — the scope of the hold.
- `how`: `Provenance(source=FactSource(kind="resident_response", actor_type="resident"))` for an
  explicit hold; for an implicit hold, whatever `kind` the inferring logic legitimately holds (e.g.
  `"domain"`, since a domain's own divergence detection produced the inference) — never
  `resident_response`, since no direct resident action was observed.

**Live state never lives in the durable `HouseFact` log.** The Manual Hold Manager keeps the
authoritative "is this active right now" state in an **ephemeral in-memory table**, keyed by
`(domain, Location)`, each entry holding its own expiry `AtJob` (§3.1). The `HouseFact` above is
still written for durable audit and learning ("how often does the resident override X") — but
reading that durable log is never how "is this active now" gets answered, for either kind of hold.
This matters specifically because it means the in-memory table, not the durable log, is what
determines restart behavior: whatever is in memory when the process stops is gone, full stop,
regardless of what's sitting in durable storage.

**Concurrency**: starting a new hold on an already-held `(domain, Location)` replaces the existing
in-memory entry and its `AtJob` — last-write-wins, not stacked. Clearing a hold (its `AtJob` firing,
or an explicit resident action) removes the in-memory entry; a closing `HouseFact` may optionally be
logged for audit completeness, but — consistent with the rule above — that log entry is never what a
live "is this still active" check consults.

### 6.2 Explicit holds and restart

Nothing further to specify: an explicit hold's live state is read fresh every cycle from the
`HouseFact` its backing entity already produces (an ordinary Sensor-registered fact — the same
`HouseFact` consumption Layer 0 already relies on, §2), not from anything Layer 0 stores itself. It
survives a restart because the entity it's backed by does, natively, in Home Assistant — with no
Heima-owned restart logic involved at all.

### 6.3 Implicit holds and restart

**Default: an implicit hold never survives a restart.** If it were silently restored, a suppression
could remain in effect indefinitely with the resident unaware it's still blocking a
potentially safety-relevant behavior — and immediately after a restart, the very signal implicit
holds are detected from (state divergence) is contaminated: Home Assistant may report power-restore
state before real device state is available, and Heima cannot yet tell that apart from a genuine
manual override. Restoring by default would risk manufacturing a false, permanent override out of a
restart artifact.

**Conditional restoration is possible, gated narrowly, opt-in per entity class, never silent.**

**Eligibility is a property of the actuator/sensor behind the hold, not of the functional domain.**
Risk varies within a domain far more than across domains — a domain-level "Heating may restore its
holds" toggle would be too coarse (a thermal-safety-relevant actuator and a purely comfort one both
being "heating" doesn't mean they carry the same restart risk). Layer 2's `Sensor`/`Actuator`
registry entries carry a classification field for this purpose:

```python
implicit_hold_restore_class: Literal["eligible", "never"] = "never"   # conservative default
```

Whichever logic detects the divergence and creates the implicit hold already knows which entity
triggered it — it reads that entity's `implicit_hold_restore_class` once, at hold-creation time, and
**freezes** the result into the hold's own evidence:

```
Provenance.evidence.restore_eligible: bool         # resolved and frozen at creation; a later change
                                                     # to the registry classification does not
                                                     # retroactively change already-created holds
Provenance.evidence.trigger_entity_id: str          # the entity whose divergence produced this
                                                     # inference — needed by the restart checks below
Provenance.evidence.trigger_state: dict[str, Any]   # that entity's relevant state/attributes at the
                                                     # moment the hold was created
```

Layer 0's restart logic (below) only ever reads these already-resolved fields — it never queries
Layer 2's registry at restart time, preserving the rule that Layer 0 depends on nothing above it.

**How the data survives the restart at all**: the in-memory table is genuinely gone after a restart,
with nothing recoverable from it — that part doesn't change. What makes conditional restoration
possible is a **second, redundant, durable copy**: Recovery's checkpoint (§7) already persists a
narrow, allowlisted snapshot of runtime state to disk on a cadence, and is written **immediately**
(not just periodically) right after a hold is activated, cleared, or materially changed — so the
checkpoint is never more than moments stale relative to the in-memory table at any given time,
including the moment of an unplanned shutdown. The checkpointed entry for an implicit hold carries
`restore_eligible`/`trigger_entity_id`/`trigger_state` verbatim, independent of whether
`trigger_entity_id` happens to also be on Recovery's own general critical-entity allowlist (§7.3) —
the hold's own record is self-sufficient for the checks below, it does not rely on that separate
allowlist covering the right entity by coincidence. This checkpoint copy is intentionally redundant
with the audit `HouseFact` written for the same event (§6.1) — the two serve different purposes
(restart continuity vs. long-term audit/learning trend) and are not a duplication to collapse into
one. On restart, Recovery reads the last-written checkpoint — the same file it already reads to
answer "did anything change while Heima was offline" — and that snapshot, not the vanished
in-memory table, is what the restoration algorithm below runs against.

**Restoration algorithm**, run once at startup, before the first domain evaluates, for each implicit
hold found in the last checkpoint:

1. If the hold's recorded expiry has already passed, discard it — it would have expired anyway.
2. If `Provenance.evidence.restore_eligible` is `false`, discard it. No exceptions past this point —
   this is the per-entity opt-in from above.
3. If Recovery's classification (§7.2) flags ambiguity for `Provenance.evidence.trigger_entity_id`
   (`power_restore_candidate` or `unknown_during_downtime`), or the cycle-level state is not
   `normal`/`startup_recovery`, discard it — this is the restart-cleanliness gate; §7.2 explains
   exactly which states block and why `startup_recovery` alone does not.
4. If `trigger_entity_id`'s **current** live state no longer matches
   `Provenance.evidence.trigger_state` (captured when the hold was created), discard it — the
   premise that justified the inference no longer holds, independent of restart cleanliness.
5. Otherwise: recreate the in-memory entry, compute the remaining delay as
   `recorded_expiry - now()` (preserving the hold's original real-world duration, not restarting a
   full-length window), arm a fresh `AtJob` for that delay (§3.1's monotonic-safe dispatch), and
   **unconditionally record the restoration as a `HouseFact`** — e.g.
   `fact_type: "manual_hold.<domain>.restored"`, `where: Location`, `how: FactSource(kind="recovery")`
   with its own fresh `correlation_id` (§5.2) — using the same mechanism §6.1 already uses for hold
   audit records. Layer 0 never calls into Layer 6 directly; it only produces a fact, exactly as it
   already does for everything else it records, preserving the rule that Layer 0 depends on nothing
   above it. Layer 6's notification pipeline — already designed to consume this kind of event from
   Reactions and Domain resolution — is what turns this fact into "an implicit hold on `<domain>` at
   `<Location>` was restored after restart" for the resident. Restoration is never silent, regardless
   of which entity class made it eligible; this is what actually closes the "resident unaware" risk
   that motivated the default in the first place, on top of getting the restoration decision right.

This is a deliberate, narrow, explicitly-declared amendment to the default rule above — restoring
requires an admin/installer to have explicitly classified the specific entity as eligible; nothing
is restored by default, and nothing is ever restored quietly.

---

## 7. Recovery / Checkpoint

A lightweight, pre-DAG context computed once per evaluation cycle, before any domain runs. It
classifies runtime state and makes that classification available, **read-only**, to everything
downstream — including the Manual Hold Manager (§6.3) — so behavior can be conservative and
explainable right after a restart or during a partial outage.

### 7.1 Cycle-level classification

```python
RecoveryState = Literal[
    "normal",                    # nothing unusual
    "startup_recovery",          # Heima just started; too early to trust anything yet
    "power_recovery",            # evidence of an actual power loss/restore, not just a process
                                   # restart (e.g. a configured UPS/power sensor, or a gap pattern
                                   # across many entities consistent with a power event)
    "degraded_recovery",         # many entities are currently unavailable
    "recovery_settling",         # transitioning back toward normal after one of the above
]
```

### 7.2 Entity-level classification

For each critical entity in the checkpoint's allowlist whose state differs from the last checkpoint
after a restart, Recovery attaches one of:

- **`unknown_during_downtime`**: the difference's cause cannot be determined — it may be a
  power-restore artifact, a manual action during downtime, or device behavior. Never treated as
  evidence *for* anything; it exists to be honest about uncertainty, not to resolve it.
- **`power_restore_candidate`**: the difference plausibly matches the entity's known power-on/reset
  behavior (e.g. a light or switch returning to a default state when power is restored).

Both labels, and the cycle-level states `power_recovery`, `degraded_recovery`, and
`recovery_settling`, are what §6.3's restart-cleanliness gate consults — a "clean" restart is one
where none of the entities behind a given implicit hold carry either label, and the cycle-level
state is `normal` or `startup_recovery`. `startup_recovery` alone does **not** disqualify a restore
candidate: it is the classification necessarily in effect during the very cycle this algorithm runs
in — nothing has been evaluated yet to know otherwise. What disqualifies a candidate is specific
evidence of an actual power event, ongoing degradation, or not yet having settled back to normal,
not merely "just started".

### 7.3 Checkpoint mechanics

Backed by a deliberately minimal checkpoint: only an allowlist of critical entities' attributes,
redacted, persisted to disk. Written:

- **periodically**, on a cadence owned by this subsystem — a system-owned `CronEntry` (§3.1), since
  Recovery consumes Timing's execution primitive like everything else that needs periodic work;
- **immediately** after specific events that must not be lost to periodic-write staleness: a manual
  hold activated, cleared, or materially changed (§6.3 depends on this); a runtime confirmation
  created, approved, dismissed, cancelled, or timed out; a transition back to `normal` from any
  non-normal `RecoveryState`.

It answers "did anything change while Heima was offline" cheaply; it is **not** a general restore
mechanism, and — deliberately — it never forces every piece of runtime state through the full
`HouseFact`/`Provenance` shape. The narrowness (only allowlisted attributes, only critical entities)
is a safety/efficiency property, not an oversight: most runtime state genuinely should start clean
after a restart, and §6.3 is the one narrow, explicitly-gated exception, not a precedent for
widening this into a general restore engine.

### 7.4 Dependency on Timing, and bootstrap order

Recovery is not fully independent of Timing, despite being a separate Layer-0 facility: its periodic
checkpoint write is itself a `CronEntry`. This means at cold start, Timing's `CronEntry` mechanism
must be available before Recovery can arm its own checkpoint-write cadence. This is not a circular
dependency in practice — `CronEntry`'s definition is durable configuration (§3.1), so Timing can
always compute a fresh `due` for Recovery's cadence from scratch on startup, with nothing to recover
from a prior run. The ordering requirement is real and worth stating explicitly, even though it
resolves cleanly: Timing initializes first, Recovery's periodic cadence arms against it, and only
then does Recovery's own pre-DAG classification run for the first post-restart cycle.

---

## 8. Failure handling

Layer 0 underlies every other layer, so a failure here has the largest blast radius in the system.
Silent failure is not acceptable anywhere in this section.

- **`AtJob`/`CronEntry` callback exceptions**: every job's callback runs inside a fault-isolation
  boundary — an exception is caught, logged, surfaced as a diagnostic event (§9), and the job is
  treated as having fired (for a `CronEntry`, the recurrence still re-arms for its next occurrence).
  A single failing job must never take down the engine or silently stop a recurring safety net. This
  mirrors the fault-isolation boundary already required around third-party plugin `compute()` calls
  (Layer 7) — one mechanism, reused, not reinvented here. For an `AtJob` tied to cleanup logic with a
  safety consequence if skipped (e.g. a manual hold's expiry, §6), there is deliberately no automatic
  retry beyond this — a loud diagnostic event is the safety net, not a retry loop that could itself
  mask a persistent underlying bug.
- **Duplicate `job_id` registration**: replace, never error (§3.1) — an owner re-arming the same
  logical deadline is the expected common case, not a conflict to reject.
- **A `CronEntry`'s `due` passes while Heima is offline**: on the next start, it fires **once**
  immediately, then resumes its normal cadence. Missed occurrences during the outage are not queued
  or replayed — coalescing to one immediate fire (not zero, not N) is the deliberate policy.
- **Durable-tier write failure** (§4): logged and surfaced as a diagnostic event; the cycle is not
  aborted and the in-memory buffer is unaffected. The durable tier is important for audit and
  learning but is not the source of truth for same-cycle correctness — losing one write is
  recoverable, crashing the engine over it is not an acceptable trade.
- **Checkpoint write failure** (§7): logged and surfaced; Recovery falls back to treating the next
  cycle conservatively (i.e. as if still `degraded_recovery` for classification purposes) rather than
  silently assuming `normal` on stale or missing checkpoint data.

---

## 9. Diagnostics

Layer 0 state must be inspectable, consistent with the project's broader diagnostics culture (a
runtime/plugins/event-store diagnostics surface already exists for other layers):

- **Timing**: every pending `AtJob` and `CronEntry` (id, owner, due, label), queryable at any time.
- **Recovery**: current `RecoveryState`, age of the last checkpoint write, count and identity of
  entities currently carrying `unknown_during_downtime`/`power_restore_candidate`.
- **Manual Hold Manager**: every active hold (kind, domain, `Location`, since when, remaining time
  if any), and — specifically for §6.3 — a log of restoration decisions (restored, and why each
  discarded candidate was discarded: expired / not eligible / restart not clean / state no longer
  coherent) so an installer can audit why a given hold did or didn't come back.
- **Persistence**: durable-tier size and retention pressure per `fact_type` (§4.3) — how close each
  is to its count ceiling, so a misbehaving sensor's volume is visible before it needs to be
  diagnosed reactively; and, per `fact_type`, its effective retention window and which registered
  learner (if any) declared the floor driving it, so an unexpectedly long or short retention window
  is traceable to its source.

---

## 10. Relationship to the core DAG

Domains (Layer 4) read only the *previous* cycle's resolved output from other domains — this is what
keeps the DAG acyclic. Layer 0 is exempt from that rule by construction: wall-clock time and
Recovery's classification are **engine-computed context**, read-only input available to every domain
and plugin within the *current* cycle, not another domain's output. A domain freely reads Layer 0
context fresh every cycle, the same way it freely reads Layer 2 facts fresh every cycle — neither is
subject to the previous-cycle restriction, because neither is produced by another domain earlier in
the same pass.

---

## 11. Not yet decided

- Whether `scheduled_routine`-style reactions should delegate recurrence definition to Home
  Assistant's native `schedule.*` helper entity instead of a Heima-owned weekday/time picker —
  trade-off is recurrence definition living outside Heima's own configuration surface; not adopted
  or rejected.
- The system-wide default retention window (§4.3) and the default per-`fact_type` count ceiling —
  concrete numbers, not an architectural question, to be set when this moves toward implementation.
- The system-owned checkpoint-write cadence (§7.3) — a concrete interval, not yet chosen.
- Whether `implicit_hold_restore_class` should later grow a role-level default (e.g. "actuators with
  role `hvac_unit` default to eligible") on top of the current flat per-entity field — deliberately
  left as the simplest version for now; revisit if per-entity configuration proves tedious in
  practice.

---

## 12. Acceptance criteria (for the eventual implementation phase)

Not part of this design spec's approval gate — recorded so the implementation phase inherits a
concrete checklist rather than re-deriving one:

- One `AtJob`/`CronEntry` execution path, monotonic-safe by construction; no remaining independent
  timer call site anywhere in the codebase.
- `Window`/`LearnedWindow`/`WarmupGate`/`WeeklyRecurrence`/`IntervalRecurrence`/`CalendarWindow` used
  everywhere a bespoke duration/threshold/schedule field exists today — none left on a domain or
  reaction config directly.
- Every `HouseFact` and every `ApplyStep` carries a non-forgeable, redacted `FactSource`/
  `ApplyStepSource`; a `correlation_id` chain is traceable from a resolved state back to the facts
  that fed it and forward to any resulting `ApplyStep`, per the rules in §5.2.
- An explicit hold's live state is never anything but a fresh per-cycle read; an implicit hold's live
  state never survives a restart unless it passes all four checks in §6.3, and every restoration —
  in every test that exercises one — produces a `HouseFact` that reaches the resident through Layer
  6's notification pipeline, never a direct call from Layer 0 into Layer 6.
- A durable-tier write failure, a checkpoint write failure, or a job callback exception, exercised in
  a test, never crashes the engine and always produces a diagnostic event (§8).
- Recovery/Checkpoint classification is available, read-only, before the first domain runs in every
  test cycle, including the first cycle after a simulated restart.

---

## Related documents (background only, not required reading)

This spec incorporates and, where needed, revises decisions originally made in v2's
`core/manual_hold_framework_spec.md`, `core/runtime_checkpoint_and_power_recovery_spec.md`, and
`core/runtime_provenance_spec.md`, and in this planning branch's own `v3_architecture_recap.md`
(Layer 0), `v3_backlog.md`, and `v3_house_fact_draft.md` (§WHEN). Where this document and any of
those differ, this document is the current word for Layer 0's v3 design.
