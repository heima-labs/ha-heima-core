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
  absolute time; for `CalendarWindow` specifically, the pre-DAG mechanical extraction of raw
  `start`/`end`/summary event data from a `calendar.*` entity (§3.4) — never the classification of
  that raw text into a named category, which is Layer 2's `CalendarInterpretation`;
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

### 2.1 Foundation contract with Layer 1

Layers 0 and 1 form one **foundation slice** with distinct ownership, not a falsely one-directional
stack. Layer 0 owns runtime mechanisms and the `FactSource` vocabulary; Layer 1 owns the immutable
semantic data contracts (`HouseFact`, `Provenance`, `Location`, `Zone`, `Topology`). Persistence and
other Layer-0 mechanisms may accept Layer-1 `HouseFact`/`Location` values, while Layer-1
`Provenance` embeds Layer-0 `FactSource`. This is a bounded reciprocal dependency on immutable
contracts only.

It never permits a behavioral cycle: Layer 0 does not query or invoke Layer-1 registries, topology,
zone resolution, sensor/fusion logic, or domain policy; Layer 1 does not execute Timing, Persistence,
Recovery, or Manual Hold behavior while constructing its value objects. Bootstrap composes these
contracts before cycles begin, and the hot path contains no Layer-0 -> Layer-1 -> Layer-0 call chain.
Concrete module layout may use a neutral contracts module or type-only references to avoid a language-
level import cycle, but this does not create a new architectural layer or change either owner's
normative responsibility.

### 2.2 Non-goals

- Prescribing internal class layout beyond the shapes below.
- Domain policies that happen to use a `Window` or a `CronEntry` (e.g. a specific reaction's dwell
  time) — those are Layer 4/5 concerns configuring a Layer 0 primitive.

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

**Temporal construction validation is mandatory and shared.** One pure validator accepts a duration
only when it is an `int` or `float` but not `bool`, is finite, and is strictly greater than zero; it
normalizes the accepted value to `float`. It is applied to `Window.seconds` and
`IntervalRecurrence.interval_s`. `WeeklyRecurrence.weekdays` is non-empty and contains only non-boolean
integers in `0..6`; `hour` and `minute` are non-boolean integers in `0..23` and `0..59` respectively.
`AtJob.due` must be a timezone-aware UTC instant. No constructor or scheduler silently clamps, rounds,
or corrects an invalid temporal value.

Static configuration shapes are constructed and validated while staging the startup or candidate reload
generation. A dynamic `AtJob` is validated when its owner registers it with Timing, before it reaches
the scheduler; this is not deferred to the callback or repeated in an evaluation cycle. Rejected
configuration leaves the active generation unchanged, while a rejected dynamic job produces a
diagnostic and arms nothing.

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

**Daylight Saving Time execution policy.** This policy applies only while scheduling a
`WeeklyRecurrence`; it does not suppress, merge, or alter already-produced `HouseFact` events or
their UTC timestamps. A requested local civil time can be exceptional at a DST boundary:

- When the requested time is **nonexistent** at the spring-forward transition (for example,
  `02:30` in `Europe/Rome` when the clock advances from `01:59:59` directly to `03:00:00`), the
  routine fires once at the first valid local instant after the gap (`03:00` in this example).
- When the requested time is **ambiguous** at the autumn fall-back transition (for example,
  `02:30` occurs first in CEST and then again one real hour later in CET), the routine fires once
  at the first occurrence (`fold=0`); the second occurrence must not produce a second firing for
  the same civil weekly request.

The next-due calculation must explicitly detect both cases rather than rely on an implementation's
implicit timezone conversion behavior. `pattern.matches(fact.when)` remains a civil-time
classification operation, so either physical occurrence in an ambiguous hour matches the requested
weekday/hour/minute for history and bucketing; only the scheduler applies the single-firing rule.
`IntervalRecurrence` uses elapsed monotonic time and is unaffected by either case. A change to Home
Assistant's configured `time_zone` invalidates the currently armed weekly due and re-arms it between
evaluation cycles using the new zone; it never replays a past weekly occurrence merely because the
zone changed.

`CronEntry`'s **definition** (owner, pattern, label, job_id) is treated as durable configuration —
a system-owned periodic safety net or another Heima-internal recurrence is a standing rule that
outlives any single pending countdown. This is why `CronEntry` state is expected to survive a
restart (the *rule* is re-read from configuration, a fresh `due` is computed against current time,
and a new `AtJob` is armed — nothing about the interrupted countdown is recovered. For an
`IntervalRecurrence`, that fresh deadline is `now + interval`; for a `WeeklyRecurrence`, it is the
next matching civil-time occurrence. Missed occurrences are never replayed implicitly after restart.
An owner that requires an initialization action performs it explicitly during its own bootstrap,
rather than obtaining it indirectly from scheduler catch-up) while a
one-shot `AtJob` that belongs to transient runtime state (see §6, Manual Hold) generally does not:
if nothing persists the reason an `AtJob` should exist, there is nothing to re-arm it from after a
restart. This is a design choice about what counts as durable configuration, not a limitation of
`AtJob` itself — §6 describes a case where a one-shot deadline is deliberately made restart-eligible
by giving the owning subsystem its own durable record to re-arm from.

Every **Heima-owned** recurring or periodic thing is a `CronEntry` owned by whichever subsystem needs
it — a periodic safety-net re-evaluation or Recovery's own checkpoint-write cadence (§7), for
example — never a bespoke timer mechanism invented per feature.

**Admin-authored schedules belong to Home Assistant.** A routine whose recurrence is configured by an
admin uses HA's `schedule.*` helper as its sole authoring and time-evaluation authority. Heima reads
only the helper's effective state through the ordinary Layer-2 `StateReadBinding` plus
`MappingInterpretation`, producing a normal boolean schedule fact that a Reaction may consume. It does
not duplicate HA's picker, recurrence calculation, timezone/DST handling, next-boundary scheduling,
or schedule persistence. A helper state change enters the ordinary evaluation cycle; an unavailable or
uninterpretable helper produces `available=False`, never an implicit schedule activation. This boundary
does not apply to internal maintenance jobs, which remain the `CronEntry`/`AtJob` mechanisms above.

### 3.2 Comparison: `Window` and `LearnedWindow`

```python
@dataclass(frozen=True)
class Window:
    seconds: float
```

`Window` is a bounded time span, **not an execution concept** — a comparison/relation over
`HouseFact` timestamps. One shape serves two uses: dwell ("has fact X been true for at least
`seconds`") and correlation/follow-up ("did fact Y occur within `seconds` after fact X"). They
differ only in which two timestamps they compare, not in shape. When either use is evaluated against
the short-term in-memory buffer (§4.1, the common case, since this is the hot per-cycle path), its
`seconds` requirement is declared against Persistence at registration time, sizing the buffer's own
retention horizon for each input stream accordingly — §4.1 for the mechanism, reused from §4.3's
identical retention-floor pattern.

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
  every call site doesn't have to remember to add its own floor and ceiling. **The clamp is a
  construction-time invariant on `seed` too, not only on values produced later by calibration**
  (corrected 2026-09-08, found in review — previously stated only as a property of the calibrated
  value): `min_seconds <= seed.seconds <= max_seconds` must hold when a `LearnedWindow` is
  constructed, validated procedurally like `Location`'s own construction rule (§5 of the Layer 1
  spec). Before the first calibration ever completes — precisely the warm-up window where this
  guarantee matters most, since no real data has smoothed anything out yet — every dwell check runs
  against `seed` directly; an out-of-range seed would defeat the guarantee exactly when it's needed,
  not in some later edge case.

The same temporal validator applies to every duration field here: `min_seconds` and `max_seconds` are
strictly positive finite durations (never `bool`), `min_seconds <= max_seconds`, and `seed.seconds`
lies inclusively within that range. Equality is intentionally valid: it configures a fixed bounded
window while retaining one uniform representation. Invalid ranges and values fail construction/staging;
calibration clamps only a valid computed candidate within an already valid range.

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
    summary: str        # the event's raw text, exactly as HA reports it — unclassified, see below
    source_entity: str
```

Extends the same "something at instant T" idea `AtJob` embodies to an externally-sourced,
**absolute** interval (not relative to "now" like `Window`), sourced from a Home Assistant
`calendar.*` entity's own event data (`start`/`end`/summary per event, read via HA's calendar API) —
mechanical extraction only. **Corrected 2026-09-08**: an earlier version of this field said
"classified by a calendar interpretation (Layer 2)" and named `category` (not `summary`), as if this
layer produced an already-classified label ("vacation", "day_off"...). It doesn't, and can't: the
keyword-matching logic that turns raw event text into a named category lives in Layer 2's
`KeywordClassifier`, composed by `CalendarInterpretation` (its own spec, §4), and Layer 0 cannot
depend on Layer 2. `summary` is the event's raw text, never classified here. A Layer 4/5 consumer that
needs to ask "is this `CalendarWindow` a vacation" declares the explicit `KeywordClassifier`
configuration it uses; it must not infer one merely from `source_entity`. That same pure classifier may
be shared with a calendar Sensor, but is never a second, separately maintained matching implementation.

### 3.4.1 Extraction, normalization, and timeline reads

Layer 0 maintains an asynchronous, per-entity **calendar timeline cache**. Its snapshot is either
`ready` with a tuple of normalized `CalendarWindow`s, or `failed` with no usable windows. This explicit
status is load-bearing: `ready` plus an empty tuple means “the calendar was read successfully and has
no relevant events”; `failed` means no trustworthy read occurred. The synchronous evaluation cycle
only reads this latest snapshot — it never calls a calendar provider, waits for I/O, or reuses a stale
pre-restart snapshot.

Timed events must provide timezone-aware start/end instants and are normalized to UTC. An all-day event
whose source supplies date-only bounds is interpreted in Home Assistant's configured local timezone as
`[local midnight on start date, local midnight on end date)`, then converted to UTC. Every normalized
window is therefore the half-open interval `[start, end)`: it is active precisely when
`start <= now < end`. This handles adjacent events without a one-instant overlap and keeps DST civil
dates correct because the local-midnight conversion occurs before UTC normalization.

An event with a missing/unparseable instant, `end <= start`, or non-text summary is discarded with a
diagnostic; other events in the same successful provider response remain usable. Layer 0 never alters
a valid summary: it stores the exact source text and does not classify it.

Two read views deliberately expose the same cached timeline. Both retain the explicit outcome rather
than returning only a tuple, so a caller can distinguish an empty successful result from a failed read:

```python
@dataclass(frozen=True)
class CalendarWindowRead:
    status: Literal["ready", "failed"]
    windows: tuple[CalendarWindow, ...]  # always empty when status="failed"
    refreshed_at: datetime | None         # UTC; None when no successful snapshot exists

active_now(entity_id, now) -> CalendarWindowRead
upcoming_starts_within(entity_id, now, horizon: Window) -> CalendarWindowRead
```

When `status="ready"`, `active_now` returns every window containing `now`.
`upcoming_starts_within` returns every non-active window whose `start` is strictly after `now` and
at-or-before `now + horizon`; it preserves each window's original `start`, `end`, `summary`, and
`source_entity`, rather than reducing it to a category.
A predictive consumer that needs seven days therefore declares `horizon=Window(seconds=7 * 24 * 60 *
60)` and can decide today about an event starting tomorrow. Active and upcoming are distinct views, so
an active event is never presented a second time as future work.

Consumers declare their largest upcoming horizon at registration. The cache prefetches through the
maximum declared horizon for that entity, refreshes asynchronously on a `calendar.*` change, before
the next known start/end boundary, and before its prefetched horizon runs out. This lets a scheduled
reaction be armed for an event boundary even when Home Assistant emits no unrelated state change, while
keeping all provider I/O out of the reaction path.

On restart, Layer 0 obtains a fresh snapshot before the first calendar-dependent evaluation, recomputes
the next boundaries, and does not replay past start/end callbacks. An event already active is visible on
that first successful snapshot; a failed initial refresh makes calendar reads `failed` until a later
refresh succeeds. Nothing from a checkpoint is treated as live calendar truth.

Calendar sits in Layer 0, same rank as "at"/"cron" — **not** a domain (Layer 4), not a third-party
plugin (Layer 7). The ready timeline snapshot is read before the core DAG each cycle, same as
Recovery/Checkpoint (§7), and never through a plugin registration mechanism; provider refresh remains
asynchronous as §3.4.1 requires. This pre-DAG placement is exactly why classification cannot happen
here: a `Sensor`/`Interpretation` lookup (Layer 2) runs on the ordinary hot-cycle path (Layer 2 §2.2),
not before it.

Resolving a conflict between two simultaneously-active `CalendarWindow`s whose classified categories
disagree (e.g. two calendar sources disagreeing, once a consumer has classified each) is a Layer 4
concern — Layer 0 only provides the raw interval and the containment primitive, never a precedence or
classification rule between sources.

---

## 4. Persistence

`HouseFact` (Layer 1) storage is **always atomic** — one produced fact record at exactly the
granularity the engine computes at internally (per-room, per-signal), never a bundled record. A
"snapshot" (everything true at one instant, or in one place, over one window) is never its own stored
shape — it is a **query reconstructed at read time**: "every `HouseFact` true in `Location` X between
t1 and t2." A generic consumer (including a Layer 7 third-party plugin) never needs to learn a bespoke
bundle type to read Heima's history — it queries `HouseFact` by `fact_type`/`Location`/time window,
the same API every consumer uses.

**Fact emission semantics and ownership.** `HouseFact` remains one universal record shape, but its
producer declares one of two persistence semantics before the engine starts:

```python
FactEmissionKind = Literal["state", "event"]

@dataclass(frozen=True)
class FactTypeClaim:
    fact_type_pattern: str  # full dotted glob pattern, §4 below
    owner_id: str           # stable producing subsystem/registry id
    emission_kind: FactEmissionKind
```

A **state** assertion describes the current value of a real-world claim and uses the identity,
write-on-change, latest-value, and reconstruction rules below. An **event** assertion records one
occurrence at `when`; every emission is durably appended, it has no current-value slot, and it is never
read as current state. `FactTypeClaim` is bootstrap/configuration metadata, not a field of `HouseFact`
and not a runtime lookup: the engine composes all claims before admitting producers and resolves the
emission kind once into each producer's Persistence call.

**Claim pattern grammar.** A concrete `fact_type` is one or more non-empty segments separated by
`.`; it never contains `*`. A `fact_type_pattern` has the same dotted shape, and each pattern segment
is a non-empty sequence of literal Unicode code points and zero or more `*` characters. The pattern
matches only a complete fact type with the same number of segments. Within one segment, `*` matches
zero or more Unicode code points other than `.`, while every other character matches itself exactly;
there are no regex operators, escapes, flags, or recursive cross-segment wildcard. Thus
`manual_hold.*door*` matches `manual_hold.pippodoor` and `manual_hold.doorpippo`, but not
`manual_hold.lighting.lifecycle`; `manual_hold.*.lifecycle` matches the latter.

During staging, the engine determines whether two dotted glob patterns have a common valid concrete
fact type. Their overlap is valid when and only when both `owner_id` and `emission_kind` are equal;
otherwise the candidate generation is rejected. This is not about constraining a legitimate partial
match: it guarantees that every concrete fact type has one persistence semantic and one owner. For
example, `manual_hold.*` as `state` and `manual_hold.*.lifecycle` as `event` do not overlap because
their segment counts differ; `manual_hold.*.*` as `state` would conflict with the lifecycle claim.
The glob compilation and overlap check are staging-only; no pattern match or conflict lookup occurs in
the evaluation path.

Every statically-addressable state producer also contributes a global `(fact_type, Location, owner_id)`
claim during the same composition pass. The engine rejects duplicate `(fact_type, Location)` claims,
regardless of layer; a namespace-owning dynamic producer such as Manual Hold is protected by its
exclusive `FactTypeClaim` instead. Layer 2 registrations contribute only `state` claims. Future layers
must make the same declaration before their producers are admitted. This is a startup/configuration
validation table, not a second facts registry or a hot-path abstraction.

State-history and event-history reads are deliberately different. For a state fact, the query is the
at-or-before-window-start record plus changes inside the window, as specified below. For an event fact,
the query returns exactly the appended records whose `when` lies in the requested interval; it never
invents an at-or-before record or reconstructs a current value. A request for a current value or a
`FactRef.previous_cycle` targeting an event claim is invalid at registration time.

### 4.0 `FactIdentityKey`

Persistence needs a stable key for "which real-world fact's current value is this?", and that key is
**not** the full WHAT/WHERE/WHEN/HOW tuple. `when` changes every record by definition, and `how`
contains provenance fields (`correlation_id`, evidence detail, actor/source metadata) that can change
without changing the real-world claim being tracked. Including either in the current-value identity
would make write-on-change and the latest-value index degenerate into "write every cycle under a new
key" for ordinary same-fact updates.

```python
@dataclass(frozen=True)
class FactIdentityKey:
    fact_type: str
    where: Location   # compared by Layer 1's canonical Location equality/serialization rule
```

For a **state** fact, `FactIdentityKey` is therefore exactly **WHAT + WHERE**:
`HouseFact.fact_type` plus the fact's canonical `Location`. `HouseFact.value`, `HouseFact.when`, and
`HouseFact.how` are record content, not identity. This matches the global state-producer uniqueness
invariant above: every `(fact_type, Location)` has one producer after composition, or registration
fails before Persistence ever sees facts for that pair.
If two raw sources can disagree about the same real-world claim, that disagreement is resolved by a
`FusionRule` before storage under the final `FactIdentityKey`; Persistence never keeps separate
"current values" for the same `fact_type`/`Location` just because the provenance differs.

Historical audit remains intact because each durable record still stores its full `Provenance`. A
query can still answer "which source produced this value and why?" by reading the record's `how`; what
`how` cannot do is partition the current-value identity used by write-on-change, reconstruction, and
retention.

**Current value and transition history are separate views of the same accepted state stream.** The
latest-value index answers the common question "what is true now?" in O(1), while the short-term and
durable histories retain every *distinct accepted state transition* for Window queries, audit, and
learning. An unchanged observation is not a transition and is not appended merely because a cycle ran.
Conversely, `on -> off -> on` is three transitions even when all are emitted in one evaluation cycle:
discarding the intermediate records would make a temporal consumer falsely infer continuous `on`.

Persistence assigns every accepted append an internal `AppendOrder(cycle_id, ordinal)`, where `ordinal`
is strictly increasing within the single cycle coordinator. It is storage metadata, never a `HouseFact`
field or a fact identity component. It breaks equal-`when` ties deterministically for the latest-value
index and history reconstruction, preserving the emitting subsystem's declared transition order (for
example, closing an old manual hold before activating its replacement). The public time range remains
ordered by `when`; within one equal instant, records are ordered by `AppendOrder`.

Write-on-change also needs a second, separate shape: the comparable **current state** stored under
that identity. This is deliberately narrower than the whole `HouseFact`, but wider than `value` alone:

```python
@dataclass(frozen=True)
class FactSourceFingerprint:
    kind: FactSourceKind
    source_id: str
    source_type: str | None
    actor_type: FactSourceActorType
    configuration_fingerprint: str | None
    # deliberately excludes correlation_id and evidence

@dataclass(frozen=True)
class FactChangeFingerprint:
    available: bool
    confidence: float | None
    value: EvidenceValue | None   # canonical serialized HouseFact.value; frozen dataclass values are
                                  # normalized to their EvidenceValue-shaped field payload first
    source: FactSourceFingerprint
```

`FactChangeFingerprint` is what Persistence compares for **state** write-on-change (§4.2). It includes
`available` and `confidence` because both are part of the fact's current epistemic state: "sensor is
now unavailable" and "same value, lower confidence" are real current-state changes that must be
durably visible to audit, recovery, and later learning. It includes the stable part of
`FactSource` so a fallback/source handoff with the same value (for example a calendar-derived workday
fact falling back to the raw helper entity) is not silently erased from history.

It excludes `when` because time changes every cycle, excludes `correlation_id` because it is a causal
trace id minted per origin/cycle (§5.2), and excludes `evidence` because evidence can contain
diagnostic detail whose shape or wording changes without changing the fact's current state. A
producer that wants an evidence-only diagnostic change to be visible emits a diagnostic event (§9);
it does not force Persistence to rewrite an otherwise unchanged fact.

When `available=False`, Layer 1 says `HouseFact.value` is undefined and no consumer may read it.
Therefore the fingerprint **canonicalizes `value` to `None` whenever `available=False`**, regardless
of what the producer happened to leave in the field. This prevents repeated unavailability from
writing every cycle merely because an implementation retained a stale prior value or cleared it.

**The state reconstruction algorithm, made explicit — resolved 2026-09-08, found in review not to be as
trivial as the paragraph above implies once write-on-change (§4.2) is factored in.** Write-on-change
means a fact that became true at t0 and never changed since has exactly **one** durable record, dated
t0 — a naive scan for records with a timestamp inside `[t1, t2]` finds nothing whenever `t0 < t1`,
even though the fact was continuously true throughout the whole window. The query is therefore always:
(1) compute the `FactIdentityKey` for the queried `fact_type`/`Location`; (2) find the single most
recent record for that key at-or-before `t1` — the value already in effect when the window opens,
however old that record is; (3) include every record for that key with a timestamp inside `(t1, t2]`
— the changes that happened during the window. Together, these fully reconstruct the value at every
instant in `[t1, t2]`, regardless of how sparse
write-on-change has made the record history. This is one algorithm, stated once here, precisely so
every consumer (a Layer 3 learner, a Layer 7 plugin, an admin diagnostic) gets it right by using the
same query instead of each re-deriving — or mis-deriving — it independently. When records have the
same `when`, the at-or-before record and the changes are ordered by `AppendOrder` above; the final one
at that instant is the reconstructed current value.

### 4.1 Two storage tiers

- **Durable long-term store** — disk-backed, for learning (Layer 3) and audit. Feeds queries over
  days to weeks of history.
- **Short-term in-memory buffer** — no disk I/O, for correlation/follow-up matching
  (`Window`-based, §3.2) within a bounded recent window.

Two tiers because they have genuinely different cost profiles: correlation matching happens on the
hot per-cycle path and can never wait on a disk read; long-term learning needs history that cannot
fit, or be affordably kept, entirely in memory. Every accepted transition touches the in-memory buffer
immediately (no I/O cost) and enters the ordered durable queue through the batching policy below; an
unchanged state candidate only consults the O(1) current index and creates no buffer record.

**Stored-data boundary.** These tiers, the current index, `PreviousCycleSnapshot`, durable retry queue,
Manual Hold journal, recovery-target snapshot, and checkpoint retain only complete `HouseFact`s or
their explicitly declared normalized projections. Every such non-fact projection is a Layer-1
`PersistedProjection`: copied JSON-compatible data, maximum nesting depth 2, finite numbers, and at
most 8 KiB after canonical UTF-8 serialization. They never retain a Home Assistant `State` object,
its full attributes mapping, HA event context, or another mutable HA runtime object. Layer 2 extracts
the small declared input it needs at the HA boundary; Layer 1 validates and copies the resulting
payload before any Layer-0 facility can buffer or persist it. Calendar is the narrow explicit case:
its cache retains only normalized `start`/`end`/`summary`/`source_entity` fields in `CalendarWindow`,
never a provider response or HA state object.

**`previous_cycle` is a third, deliberately tiny in-memory view, not a disk read.** At composition,
consumers declare every state `FactIdentityKey` they will address with `FactRef.previous_cycle=True`.
After each evaluation completes, Persistence seals a `PreviousCycleSnapshot` containing only those
declared keys and their final `HouseFact`s (including an unavailable value where that was the final
result). The next evaluation reads this immutable snapshot in O(1); it never scans the short-term
history buffer and never waits for the durable store. A durable-batch failure does not invalidate this
snapshot while the process remains alive.

```python
@dataclass(frozen=True)
class CycleCommitMarker:
    cycle_id: int
    completed_at: EvidenceInstant

@dataclass(frozen=True)
class CleanShutdownMarker:
    last_completed_cycle_id: int
```

Each successful end-of-cycle durable batch atomically records its `CycleCommitMarker` alongside its
facts. On orderly shutdown, one `CleanShutdownMarker` is written after the last successful batch;
this is one shutdown write, not a per-cycle `fsync`. At a later bootstrap, before the first DAG, a
matching clean marker lets Persistence pre-hydrate the declared previous-cycle keys from the durable
state as of that completed cycle. The marker is **single-use**: bootstrap durably removes it before
exposing any hydrated value, so a subsequent crash cannot reuse the prior run's clean conclusion; if
that removal fails, bootstrap treats the run as unclean and hydrates nothing. This is one startup
write, not a per-cycle `fsync`. An unclean restart, a missing/mismatched marker, or a known
durable-batch failure not followed by a successful batch pre-hydrates no values: every
`previous_cycle` reference is `available=False` for that first cycle. This refuses to pass an older
durable record off as the immediately preceding cycle. Once one new cycle completes, the ordinary
in-memory snapshot resumes.

**The buffer's retention horizon is declared, not fixed — resolved 2026-09-08, reusing §4.3's own
retention-floor pattern rather than inventing a second mechanism.** A dwell check ("has this fact
been true for at least `seconds`, continuously") or a correlation check ("did fact Y occur within
`seconds` after fact X") needs the buffer to actually hold every change within that `Window`'s
`seconds` (or a `LearnedWindow`'s `max_seconds`) — not just the latest value, the full recent history
of changes, to confirm nothing flipped false in between. Nothing previously tied the buffer's own
bounded horizon to how large a `seconds`/`max_seconds` a consumer might configure; a dwell/correlation
check requiring more history than the buffer actually retains can never be satisfied, correctly or
not — a silent, permanent false negative, not a degraded read. Resolved the same way §4.3 resolves
the identical shape of problem for durable retention: whichever subsystem registers a `Window`- or
`LearnedWindow`-based dwell/correlation check **declares** its own `seconds`/`max_seconds` requirement
against Persistence at registration time — a one-directional push, never a live query upward. The
requirement names the input stream it reads: a state stream is its `FactIdentityKey`; an event stream,
which deliberately has no identity key, is its `(fact_type, Location)` pair. Each stream's effective
horizon is the larger of the **15-minute** system-wide default and only the requirements registered
for that stream. A check needing an hour of contiguous history therefore extends its own inputs to an
hour, not every unrelated fact in the house. There is deliberately no absolute maximum horizon yet:
diagnostics expose the largest declared stream horizon and aggregate buffer bytes so a future limit can
be based on actual installations rather than an arbitrary preemptive restriction.

```python
@dataclass(frozen=True)
class StateBufferStream:
    key: FactIdentityKey

@dataclass(frozen=True)
class EventBufferStream:
    fact_type: str
    where: Location

BufferStream = StateBufferStream | EventBufferStream

@dataclass(frozen=True)
class BufferRequirement:
    stream: BufferStream
    horizon: Window                 # `LearnedWindow` declares its validated max_seconds as this Window
```

`register_buffer_requirement(requirement)` is a composition/staging operation, never a hot-path call.
The owner registers one requirement for every state/event stream its dwell or correlation can inspect;
the active buffer stores a precomputed `max(default, requirements)` horizon per stream. Removing or
changing a requirement takes effect only with the next atomic configuration generation; it may evict
now-unneeded older in-memory entries but never reads disk to refill a stream.

### 4.2 Write policy

Writes to the durable tier are **batched at the end of each evaluation cycle** — buffered during the
cycle, flushed once after the domain/reaction pass completes, rather than one disk write per fact.
This keeps the per-fact hot path free of I/O. This batching, not write-on-change below, is what
protects reaction latency: even a policy that wrote every fact every cycle would still be off the
hot path, because every write is already deferred to this one end-of-cycle flush. Write-on-change is
a separate, additional optimization, aimed at write *volume* and disk growth, not per-cycle latency —
worth stating explicitly, since the two are easy to conflate.

**Write-on-change for state facts**: a candidate is compared with the O(1) **in-memory current index**
for its `FactIdentityKey` (§4.0), never only with the last durable record. A changed
`FactChangeFingerprint` is accepted as one ordered transition: it appends immediately to the buffer,
updates that current index, and joins the durable queue. An unchanged fingerprint updates neither
history nor queue. This keeps an ordinary stable reading from consuming buffer or disk space every
cycle, while retaining meaningful changes where `value` stayed the same but
`available`/`confidence`/stable source changed. It also remains correct after a failed durable batch:
the live process still compares against its actual current state, and its ordered queue retries every
uncommitted accepted transition at a later end-of-cycle batch rather than silently collapsing it.

Multiple changed candidates for one `FactIdentityKey` in one cycle are each accepted and appended in
their coordinator order; only the last becomes the index's current value. Persistence must not coalesce
them merely because their key or `when` is shared. Ordinary composed state producers normally emit at
most one candidate per cycle, but explicit lifecycle operations can intentionally emit a sequence.

**The latest-value index — made explicit, resolved 2026-09-08.** Comparing "the candidate value" to
"the current value for this key," every cycle, for every fact, requires Persistence to already
maintain a fast (not scan-based) per-key lookup of each `FactIdentityKey`'s current record. Made
explicit here because two other mechanisms depend on it directly: the reconstruction algorithm above
("find the most recent record at-or-before `t1`") and retention's exemption for the latest record per
key (§4.3). This index is updated incrementally on every accepted state transition — never recomputed
by scanning stored history — so none of these three uses adds a cost beyond what write-on-change already
pays to function at all.

The `CycleCommitMarker` belongs to this same end-of-cycle transaction: a failed durable batch creates
neither a marker nor a partial successful cycle. It does not make the current process unusable because
`PreviousCycleSnapshot` was already sealed in memory; it only removes cross-restart certainty until a
subsequent clean shutdown follows a successful batch.

**Event facts** bypass `FactIdentityKey`, `FactChangeFingerprint`, and the latest-value index. Each
event emission is appended to the in-memory buffer and ordered durable queue, even if its payload
resembles a prior event; this preserves repeated occurrences for audit and Layer 6. The batch remains
the only durable I/O boundary, so append-only event history adds no blocking write to the reaction path.

### 4.3 Retention

Retention is **time-based per `fact_type`, with a hard per-`fact_type` record-count ceiling and a
global pruning watermark** — not one global count-based cap. These three controls serve different
purposes and are applied by background/batch maintenance, never by an evaluation-cycle scan:

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
  target retention window is the larger of the **14-day** system-wide default and every declared requirement,
  so ordinary time-based pruning honors a learner's requested duration without every `fact_type`
  needing an individually hand-tuned setting. It is deliberately a target rather than an unconditional
  guarantee: the hard safety ceiling below takes precedence when the two conflict.
- **Why still a count ceiling, per `fact_type`**: a time-based window alone doesn't protect against
  one pathologically noisy `fact_type` (a flapping sensor writing every few seconds) consuming disk
  space disproportionately. The default ceiling is **50,000 records per `fact_type`**. The ceiling is
  scoped **per `fact_type`**, not global, so one noisy
  `fact_type` evicting its own oldest records early cannot crowd out retention for every other
  `fact_type` sharing a global budget. Hitting the ceiling raises a diagnostic warning (§9), since it
  usually indicates a misbehaving sensor worth investigating, not a config value to silently absorb.
- **Why also a global pruning watermark**: several individually compliant noisy types can still add
  up. The durable fact store therefore has a **512 MiB global watermark**, measured over the store's
  retained record data and indexes. After ordinary time and per-type pruning, maintenance above that
  watermark evicts the globally oldest *evictable* records (superseded state records and event
  records), recording the affected fact types' ceiling/pruning coverage metadata and diagnostics.
  It is a watermark, not an admission quota: it never rejects an observation, blocks a cycle, or
  removes a latest state record. If protected latest state records alone exceed 512 MiB, Persistence
  raises `storage_pressure` and continues to preserve them; an installer can then reduce registry
  cardinality or raise the operational watermark in a later release rather than Heima silently losing
  current house state.

**Retention coverage is explicit.** Persistence durably records, per `fact_type`, the most recent
instant at which count-ceiling or global-watermark pruning discarded history
(`last_retention_pruning_at`). A history read for a declared interval returns its records together
with `retention_coverage`:
`"complete"` only when the requested interval lies wholly within the effective time-retention window
and starts strictly after that `fact_type`'s last ceiling eviction; otherwise `"truncated"`. The
result says whether retention policy may have removed records from that interval, not whether a device
actually emitted observations or whether a learner has sufficient samples — those remain separate
availability and warm-up concerns. The metadata is updated only by the pruning path and read in O(1),
so it adds no scan or I/O to the evaluation cycle.

A consumer that needs a complete declared historical window, including every `PatternLearner`, must
refuse to compute from a `"truncated"` read: it remains warm-up/degraded and emits a diagnostic until
its requested window is covered again. It must never substitute a shorter implicit window or treat
the remaining records as representative. This makes a noisy source reduce only its own learning
availability, while the hard ceiling continues to protect storage and maintenance latency for the
whole installation.

**Neither time-based nor count-based eviction may ever remove the single most recent record for a
given `FactIdentityKey` — resolved 2026-09-08, found in review; sharpened 2026-09-08 by naming the
key explicitly.** This exemption applies only to state facts. Without this exemption,
write-on-change and retention actively work against each other: a fact that became true once and
never changed has exactly one durable record (write-on-change, §4.2); once that record is older than
the `fact_type`'s retention window, time-based eviction would delete it — not just making the
reconstruction algorithm above unable to answer old queries, but making Persistence **forget the
fact's current value entirely**, even though it may still be true right now. Only **superseded**
records — those followed by a newer record for the same key — are eligible for time-based or
count-based eviction; the latest-value index (§4.2) already identifies, at no extra cost, exactly
which record that is for every key, so this exemption costs nothing beyond a lookup the pruning pass
already needs to perform to decide what to evict. Event records have no latest value and are all
eligible for ordinary time/count eviction. This does not weaken the count ceiling's own
purpose (bounding one noisy `fact_type`'s disk footprint): a flapping sensor still produces many
superseded, evictable records for its own key — only its single current record per key is protected,
never its full history.

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
    configuration_fingerprint: str | None = None  # resolved per-producer execution-semantic
                                              # fingerprint, assigned only by its active composed
                                              # generation; never accepted from an untrusted producer
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
    configuration_fingerprint: str | None = None
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
                            # hold, Layer 0 §6; a runtime confirmation response) — two different
                            # boundary checks, one per case, neither reducible to the other; see §5.1
    "timeout",              # recorded because an expected response/confirmation window elapsed with
                            # nothing arriving — assignable only by the in-process timeout controller
    "recovery",             # produced by Recovery/Checkpoint itself (§7) — e.g. an implicit hold
                            # restored after a clean restart (§6.3)
    "system",               # produced by system-owned runtime infrastructure not covered by a more
                            # specific kind above (e.g. a system-owned CronEntry's own bookkeeping)
    "test",                 # produced by test code — never present in production data
    "legacy",               # reserved only for offline/archive tooling examining V2 material; never
                            # admitted to V3 runtime data or produced by new code
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
  runtime confirmation request — this is the boundary for one of the two `resident_response` cases;
- the other case, an **explicit hold** (§6), has a different boundary, stated separately because
  "matches an active request" doesn't apply to it (added 2026-09-08, found in review — the boundary
  for this case was never stated, only the confirmation-response one was): `kind="resident_response"`
  is assignable here only on a false-to-true or true-to-false edge from the dedicated helper/control
  entity, when Home Assistant's event context identifies a non-admin resident. Its `source_id` is that
  helper entity id and `source_type="manual_hold_control"`. The same helper edge attributed to an HA
  admin is legitimate but instead uses the `admin_command` provenance in §6.1; automation, service,
  or unknown-context edges are rejected as explicit-hold actions and raise a diagnostic. It never
  merely asserts that a resident acted because a helper happens to be active;
- a third-party plugin (Layer 7) can produce `kind="third_party_plugin"`, but nothing it returns can
  make the core treat it as `kind="sensor"` or `kind="recovery"`.
- `configuration_fingerprint`, when present, is assigned only by the active composed generation; a
  producer cannot choose or retain one across a generation swap.

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
must do two things explicitly, never rely on the default to "just work" for either: mint a genuinely
new `correlation_id` at each origin point above, and then explicitly propagate that same id,
unchanged, to everything causally downstream of it within the same chain (corrected 2026-09-08 — an
earlier version of this sentence said the opposite of the first half, "pass down an *inherited*
correlation_id at every one of the origin points," when an origin point is, by this section's own
definition, precisely where there is nothing to inherit *from*).

---

## 6. Manual Hold Manager

A manual hold is a resident's override that suppresses some automated behavior in some functional
domain (lighting, heating, security...) at some `Location`. Two kinds, with genuinely different
detection, release, and restart behavior — collapsing them into one undifferentiated shape would
lose real distinctions, not simplify anything:

- **Explicit hold**: the resident turns on a dedicated control (a helper entity, or an equivalent
  admin/panel-declared override) that unambiguously means "hold this." The control itself is a Home
  Assistant entity with state that Home Assistant persists natively, so an explicit hold's **live
  status** is always re-read fresh from that entity's current state every cycle. Heima does retain a
  narrow checkpoint record for the active instance's identity (§6.2); it is never a live-state
  fallback and cannot make a helper that is currently off appear active.
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
    hold_id: str                              # opaque id minted once for this hold instance; a
                                              # replacement always gets a new id
    active: bool
    kind: Literal["explicit", "implicit"]
    held_state: dict[str, EvidenceValue] | None = None   # optional: the specific state/attributes the
                                                 # resident wants respected while the hold suppresses
                                                 # automation here (e.g. a thermostat's target), when
                                                 # the hold pins a value rather than only suppressing.
                                                 # Corrected 2026-09-08, was dict[str, Any]: this is a
                                                 # HouseFact.value (below), which Layer 1 §3 requires
                                                 # to be EvidenceValue-shaped throughout, recursively —
                                                 # Layer 1 §3 cites this exact field as its own
                                                 # compliant example, so the type must actually say so.

@dataclass(frozen=True)
class ManualHoldLifecycleValue:
    hold_id: str
    kind: Literal["explicit", "implicit"]
    event: Literal[
        "activated", "cleared", "expired", "replaced", "restored", "restoration_discarded",
    ]
    reason: Literal[
        "incomplete_evidence", "expired", "not_eligible", "restart_not_clean",
        "state_no_longer_coherent",
    ] | None = None                           # required only for restoration_discarded; forbidden
                                              # for every other event
```

Every ordinary lifecycle transition produces one state/audit `HouseFact` pair with a mechanical,
non-optional contract. Replacement produces two such pairs (one terminal, one activating); a discarded
restoration produces its audit event alone:

- **Current-state fact**: `fact_type="manual_hold.<domain>"`, `value=ManualHoldValue`, and
  `where=Location`. It is written on activation, clearing, expiry, replacement, and restoration.
  `active=True` means this hold instance is now in force; `active=False` closes precisely the
  identified instance. This is the only manual-hold fact a consumer may read as state.
- **Audit event**: `fact_type="manual_hold.<domain>.lifecycle"`,
  `value=ManualHoldLifecycleValue`, and the same `where`. It is written exactly once for every
  transition, including a discarded restoration that has no current-state fact. Lifecycle events are
  never read as state; their purpose is a complete audit/notification trail.

`domain` is the functional behavior being suppressed (lighting, heating, security...), a field
orthogonal to `where`, not folded into it. `hold_id` is opaque, non-empty, and minted at activation;
the paired state fact and lifecycle event use the same id and correlation id. A terminal state fact
and its lifecycle event likewise share a correlation id. `held_state` is carried on an active state
fact only; it is `None` on every inactive one.

The required transition table is:

| Transition | State fact | Lifecycle event | `FactSource` |
| --- | --- | --- | --- |
| explicit activation / clear | `active=True` / `False`, `kind="explicit"` | `activated` / `cleared` | `resident_response`, `source_id=<helper_entity_id>`, `source_type="manual_hold_control"`, `actor_type="resident"`; only the verified resident helper edge in §5.1 |
| implicit activation | `active=True`, `kind="implicit"` | `activated` | `domain`, `source_id=<domain>`, `source_type="implicit_hold_detector"`, `actor_type="heima"`; never `resident_response` |
| explicit admin activation / clear | `active=True` / `False`, `kind="explicit"` | `activated` / `cleared` | `admin_command`, `source_id="manual_hold.activate"` / `"manual_hold.clear"`, `source_type="manual_hold_manager"`, `actor_type="ha_admin"`; the verified admin helper edge in §5.1 |
| implicit admin clear | `active=False` | `cleared` | `admin_command`, `source_id="manual_hold.clear"`, `source_type="manual_hold_manager"`, `actor_type="ha_admin"` |
| implicit expiry | `active=False` | `expired` | `timeout`, `source_id="manual_hold.expiry"`, `source_type="manual_hold_manager"`, `actor_type="scheduler"` |
| replacement | old instance `active=False`, then new instance `active=True` | old `replaced`, then new `activated` | exactly the source values of the successor's activation; all four facts share its one newly minted correlation id |
| successful explicit identity restoration | `active=True`, `kind="explicit"` | `restored` | `recovery`, `source_id="recovery.manual_hold"`, `source_type="manual_hold_restore"`, `actor_type="system"`, with a fresh recovery correlation id |
| explicit recovery activation without an identity record | `active=True`, `kind="explicit"` | `activated` | `recovery`, `source_id="recovery.manual_hold"`, `source_type="manual_hold_restore"`, `actor_type="system"`, with a fresh recovery correlation id |
| explicit recovery clear of a stale identity record | `active=False`, `kind="explicit"` | `cleared` | `recovery`, `source_id="recovery.manual_hold"`, `source_type="manual_hold_restore"`, `actor_type="system"`, with a fresh recovery correlation id |
| successful implicit restoration | `active=True`, `kind="implicit"` | `restored` | `recovery`, `source_id="recovery.manual_hold"`, `source_type="manual_hold_restore"`, `actor_type="system"`, with a fresh recovery correlation id |
| discarded implicit restoration | none | `restoration_discarded` | `recovery`, `source_id="recovery.manual_hold"`, `source_type="manual_hold_restore"`, `actor_type="system"`, with a fresh recovery correlation id |

An explicit hold has no Heima expiry: its helper entity's current state is authoritative. An implicit
hold has one `AtJob`; its expiry emits the `expired` transition above before removing the in-memory
entry. `restoration_discarded.reason` is exactly one of `"incomplete_evidence"`, `"expired"`,
`"not_eligible"`, `"restart_not_clean"`, or `"state_no_longer_coherent"`; its evidence includes the
same frozen restoration fields defined in §6.3. This records every Recovery decision as durable,
queryable data rather than only as a diagnostic message.

An explicit control is therefore not a generic HA boolean: it is a configured, dedicated control
entity with a known domain and `Location`, and its state edge retains the HA event context until the
Manual Hold Manager has authorized or rejected it. A resident edge maps to `resident_response`; an
admin edge maps to `admin_command`, and may therefore activate or clear the explicit hold. An
unattributable or automation/service-originated edge creates neither state nor lifecycle fact and leaves
any existing hold unchanged. It is surfaced as a diagnostic rather than silently reclassified as an
implicit hold, whose distinct divergence evidence is required by §6's own definition.

**Live state never lives in the durable `HouseFact` log.** The Manual Hold Manager keeps the
authoritative "is this active right now" state for **implicit** holds in an **ephemeral in-memory
table**, keyed by `(domain, Location)`, each entry holding its own expiry `AtJob` (§3.1). The
`HouseFact` above is still written for durable audit and learning ("how often does the resident
override X") — but reading that durable log is never how "is this active now" gets answered, for
either kind of hold. For an implicit hold specifically, this matters because it means the in-memory
table, not the durable log, is what determines restart behavior: whatever is in memory when the
process stops is gone, full stop, regardless of what's sitting in durable storage. **Corrected
2026-09-08**: an earlier version of this paragraph said the in-memory table determines restart
behavior "for either kind of hold" — an overgeneralization §6.2 already contradicts: an explicit
hold never has an entry in this table at all, live or otherwise — its status is re-read fresh from
its backing entity every cycle (§6.2), so nothing about this table's restart fate applies to it.

**Concurrency**: starting a new hold on an already-held `(domain, Location)` replaces the existing
in-memory entry and its `AtJob` — last-write-wins, not stacked. It emits the mandatory `replaced`
terminal transition for the old `hold_id`, then the mandatory `activated` transition for the new one.
Both state/lifecycle pairs inherit the one source and one new correlation id of the action that caused
the replacement; replacement itself is not a second causal origin.
Clearing a hold (its `AtJob` firing, an explicit resident action, or an admin action) emits its
mandatory terminal transition before removing the in-memory entry. None of these durable facts is what
a live "is this still active" check consults.

### 6.2 Explicit holds and restart

The backing helper remains the sole authority for whether an explicit hold is live. Its ordinary
Sensor-produced `HouseFact` is read every cycle; neither the audit log nor a checkpoint may override
an observed inactive helper. A separate checkpoint record exists solely to preserve the immutable
identity and optional pinned state of an already-active instance:

```python
@dataclass(frozen=True)
class ExplicitHoldIdentity:
    helper_entity_id: str
    domain: str
    where: Location
    hold_id: str
    held_state: dict[str, EvidenceValue] | None
```

There is at most one active record per `(helper_entity_id, domain, Location)`. Manual Hold journal
compaction (§6.4) writes it after an explicit activation, replacement, or material change, and removes
it after an ordinary clear. It is metadata for identity and audit continuity, not an alternative state
store.

At bootstrap, before the first domain evaluates, the Manual Hold Manager reconciles each configured
explicit helper against its matching checkpoint record exactly once:

1. Helper active and matching record present: recreate the ephemeral runtime association with the
   recorded `hold_id` and `held_state`, then emit an active state fact and `event="restored"` under one
   fresh Recovery correlation id. The helper's current active state, not the record, authorizes this.
2. Helper active and record absent or malformed: mint a new `hold_id`, create and immediately
   journal its record, then emit the active state fact and `event="activated"` under one fresh
   Recovery correlation id. This is an honest new observed instance: Heima cannot claim identity it
   did not durably retain.
3. Helper inactive and matching record present: emit the terminal inactive state fact and
   `event="cleared"` for that record's `hold_id` under one fresh Recovery correlation id; its journal
   compaction removes the record. This closes a transition that may have occurred immediately before
   an unclean stop.
4. Helper inactive and no record: do nothing.

After reconciliation, ordinary edges use the transition table in §6.1. This mechanism adds no
per-cycle I/O or lookup: normal evaluation consults only the fresh helper fact and its in-process
association; checkpoint reads and reconciliation occur once during bootstrap, while writes are only
on explicit-hold transitions.

### 6.3 Implicit holds and restart

**Default: an implicit hold never survives a restart.** If it were silently restored, a suppression
could remain in effect indefinitely with the resident unaware it's still blocking a
potentially safety-relevant behavior — and immediately after a restart, the very signal implicit
holds are detected from (state divergence) is contaminated: Home Assistant may report power-restore
state before real device state is available, and Heima cannot yet tell that apart from a genuine
manual override. Restoring by default would risk manufacturing a false, permanent override out of a
restart artifact.

**Conditional restoration is possible, gated narrowly, opt-in per entity class, never silent.**

**Eligibility is a property of the actuator behind the hold, not of the functional domain.**
Risk varies within a domain far more than across domains — a domain-level "Heating may restore its
holds" toggle would be too coarse (a thermal-safety-relevant actuator and a purely comfort one both
being "heating" doesn't mean they carry the same restart risk). Layer 2's `Actuator` registry entries
carry a classification field for this purpose (corrected 2026-09-06: `Sensor` does not carry this
field — an implicit hold is by definition triggered by a *commanded* entity diverging from its
expected state, so the eligibility lookup is always against the diverging entity's `Actuator`
record, never its `Sensor` record):

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
Provenance.evidence.trigger_state: dict[str, EvidenceValue]   # that entity's relevant state/
                                                     # attributes at the moment the hold was created —
                                                     # corrected 2026-09-07, was dict[str, Any]: Layer
                                                     # 1 §4.3 constrains every `evidence` value to
                                                     # EvidenceValue (JSON primitives, depth <= 2) and
                                                     # cites this exact field as its compliant example
                                                     # ("one level of nested attributes, not deeper");
                                                     # the type annotation must actually say so, not
                                                     # imply a looser shape than Layer 1 permits
Provenance.evidence.expiry: EvidenceInstant         # Layer 1 §4 canonical UTC ISO-8601 text; the
                                                     # raw Python datetime is normalized before it is
                                                     # placed in evidence
                                                     # added 2026-09-07, closing a gap found in
                                                     # review: the restoration algorithm below
                                                     # (steps 1 and 5) needs the hold's original
                                                     # expiry to know whether it already lapsed and to
                                                     # compute the remaining delay — this was
                                                     # referenced as "recorded_expiry" without ever
                                                     # being declared as a stored field anywhere
```

Layer 0's restart logic (below) only ever reads these already-resolved fields — it never queries
Layer 2's registry at restart time, preserving the rule that Layer 0 depends on nothing above it.

**Interaction with `evidence`'s fail-soft policy (Layer 1 §4.3) — resolved 2026-09-07.** A shape or
size violation on `evidence` silently resets it to `{}` for that `HouseFact`, per Layer 1's own rule;
nothing above previously said what the restoration algorithm should do if that happened to an implicit
hold's record. Resolved as an explicit precondition on the algorithm below: if any of
`restore_eligible`/`trigger_entity_id`/`trigger_state` is absent, or `expiry` is absent or not a valid
canonical `EvidenceInstant`, in a checkpointed hold's `evidence` (whether because it was never
populated, malformed, or wiped by the fail-soft policy), discard the candidate — the same conservative
outcome as `restore_eligible=false` (step 3 below), checked earlier as its own step (step 1) since
every later step needs these fields to be readable at all. This keeps
the failure mode conservative (never restoring on incomplete data) and consistent with every other
gate in this algorithm being a "discard unless every check passes" design, rather than leaving an
implementer to guess at undefined behavior for a safety-relevant decision.

**How the data survives the restart at all**: the in-memory table is genuinely gone after a restart,
with nothing recoverable from it — that part doesn't change. What makes conditional restoration
possible is a **second, redundant, durable copy**: the Manual Hold journal (§6.4) durably records the
transition before its facts and checkpoint mutation can diverge, then compacts its checkpoint update
after the facts commit. The checkpointed entry for an implicit hold carries
the complete active-state identity (`hold_id`, domain, `Location`, `kind="implicit"`, and
`held_state`) plus `restore_eligible`/`trigger_entity_id`/`trigger_state`/`expiry` verbatim,
independent of whether `trigger_entity_id` happens to also be on Recovery's own general
critical-entity allowlist (§7.3) — the hold's own record is self-sufficient for the checks below and
for the state/lifecycle facts it may need to emit; it does not rely on that separate allowlist covering
the right entity by coincidence. This checkpoint copy is intentionally redundant with the audit
`HouseFact` written for the same event (§6.1) — the two serve different purposes (restart continuity
vs. long-term audit/learning trend) and are not a duplication to collapse into one. On restart,
Recovery reads the last-written checkpoint — the same file it already reads to answer "did anything
change while Heima was offline" — and that snapshot, not the vanished in-memory table, is what the
restoration algorithm below runs against.

**Restoration algorithm**, run once at startup, before the first domain evaluates, for each implicit
hold found in the last checkpoint:

Every discard in steps 1-5 emits exactly one `manual_hold.<domain>.lifecycle` fact with
`event="restoration_discarded"`, the checkpointed `hold_id`/`kind="implicit"`/`Location`, the fresh
Recovery correlation id, and the matching `reason` named in §6.1. It emits no current-state fact:
the candidate was never active in this runtime. The implementation records the same outcome in the
diagnostic surface, but the lifecycle fact is the durable, authoritative audit record.

1. If `restore_eligible`/`trigger_entity_id`/`trigger_state`/`expiry` is not all present in the hold's
   `evidence`, or if `expiry` cannot be parsed as Layer 1 §4's canonical `EvidenceInstant` — whether
   never populated, malformed, or wiped by Layer 1 §4.3's fail-soft policy — discard it. Same
   conservative outcome as step 3 below (`restore_eligible=false`), checked first since every later
   step needs these fields to even be readable. The lifecycle reason is `"incomplete_evidence"`. Call
   the parsed result `expiry_at`.
2. If `expiry_at` has already passed, discard it — it would have expired anyway. The lifecycle reason
   is `"expired"`.
3. If `Provenance.evidence.restore_eligible` is `false`, discard it. The lifecycle reason is
   `"not_eligible"`. No exceptions past this point —
   this is the per-entity opt-in from above.
4. If Recovery's classification (§7.2) flags ambiguity for `Provenance.evidence.trigger_entity_id`
   (`power_restore_candidate` or `unknown_during_downtime`), or the cycle-level state is not
   `normal`/`startup_recovery`, discard it — this is the restart-cleanliness gate; §7.2 explains
   exactly which states block and why `startup_recovery` alone does not. The lifecycle reason is
   `"restart_not_clean"`.
5. If `trigger_entity_id`'s **current** live state no longer matches
   `Provenance.evidence.trigger_state` (captured when the hold was created), discard it — the
   premise that justified the inference no longer holds, independent of restart cleanliness. The
   lifecycle reason is `"state_no_longer_coherent"`.
6. Otherwise: recreate the in-memory entry and arm a fresh `AtJob(due=expiry_at)` (§3.1 computes
   `expiry_at - now()` once into its monotonic delay, preserving the hold's original real-world
   duration rather than restarting a full-length window), then
   emit both facts required by §6.1: `manual_hold.<domain>` with the original `hold_id`,
   `active=True`, and `kind="implicit"`; then `manual_hold.<domain>.lifecycle` with
   `event="restored"`. Both have `FactSource(kind="recovery", actor_type="system")` and one fresh
   correlation id (§5.2). Layer 0 never calls into Layer 6 directly; it only produces facts, exactly
   as it already does for everything else it records, preserving the rule that Layer 0 depends on
   nothing above it. Layer 6's notification pipeline — already designed to consume this kind of
   event from Reactions and Domain resolution — is what turns the lifecycle event into "an implicit
   hold on `<domain>` at `<Location>` was restored after restart" for the resident. Restoration is
   never silent, regardless of which entity class made it eligible; this is what actually closes the
   "resident unaware" risk that motivated the default in the first place, on top of getting the
   restoration decision right.

This is a deliberate, narrow, explicitly-declared amendment to the default rule above — restoring
requires an admin/installer to have explicitly classified the specific entity as eligible; nothing
is restored by default, and nothing is ever restored quietly.

### 6.4 Manual Hold journal and crash consistency

Every Manual Hold transition — explicit or implicit activation, clear, expiry, replacement,
restoration, and restoration discard — is one `ManualHoldJournalEntry` before it is a durable fact or
checkpoint mutation:

```python
@dataclass(frozen=True)
class ManualHoldCheckpointUpdate:
    action: Literal["upsert", "delete"]
    hold_id: str
    domain: str
    where: Location
    kind: Literal["explicit", "implicit"]
    payload: PersistedProjection | None       # full §6.2/§6.3 checkpoint payload for upsert;
                                               # None only for delete; Layer 1 bounded projection

@dataclass(frozen=True)
class ManualHoldJournalEntry:
    operation_id: str                         # exactly the transition's correlation_id
    facts: tuple[HouseFact, ...]              # state/lifecycle pair, or two pairs for replacement
    fact_roles: tuple[str, ...]               # stable roles within operation; e.g. state, lifecycle,
                                               # old_state, old_lifecycle, new_state, new_lifecycle
    checkpoint_update: ManualHoldCheckpointUpdate
```

`operation_id` is one causal operation, not one fact: a replacement has four roles under its one
correlation id. The journal is a small write-ahead log owned solely by the Manual Hold Manager; it is
not a general event journal and is never used for ordinary sensor facts, evaluation output, or actuator
commands.

The protocol is mandatory:

1. Authorize the transition and construct its complete facts, checkpoint update, and correlation id.
   The upsert payload must first pass Layer 1's `PersistedProjection` validation; a shape, depth, or
   size violation rejects this proposed hold transition before any fact or journal entry exists and
   emits a diagnostic. This is distinct from a later medium write failure, for which the explicit
   degradation rule below applies.
2. Append and `fsync` the journal entry before considering the transition durably complete.
3. Update the live hold state and enqueue the facts for the normal end-of-cycle durable batch. The
   EventStore accepts each fact idempotently by `(operation_id, fact_role)`; a replay cannot append a
   duplicate lifecycle event or a second replacement pair.
4. After that batch acknowledges every role, atomically merge `checkpoint_update` and delete the
   journal entry in one checkpoint-file replacement.

At bootstrap, before §6.2 helper reconciliation or §6.3 implicit restoration, the manager replays
every remaining journal entry: it idempotently commits any missing fact roles, applies its checkpoint
update, and removes the entry atomically. The replay retains the original facts and correlation id;
it completes the interrupted original operation, rather than fabricating a new Recovery event.

**Journal write failure is explicit degradation, never a reason to ignore an override.** If append or
`fsync` fails, the Manager keeps the explicit helper state or inferred implicit suppression live in
memory, emits a diagnostic, and marks the Manager's diagnostic state `durability_pending`. Its fact
pair remains available in the in-memory buffer for current-cycle consumers but is withheld from the
durable batch until the journal is durable; a background retry with backoff performs no disk I/O in
the evaluation path. A process crash while it remains pending can lose identity/audit continuity
because no durable record exists — an unavoidable consequence of the failed medium, stated rather
than hidden. On restart the existing conservative rules apply (explicit helper reconciliation; no
implicit restore absent its durable record). Once the retry succeeds, the original operation is
committed through the same idempotent protocol above.

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
redacted, copied into one `PersistedProjection` per entity, and persisted to disk. A candidate
critical-entity projection that is not representable within that contract is omitted from that one
checkpoint commit and emits a diagnostic; it never causes raw HA data to be retained or invalidates
the rest of the checkpoint. At recovery, an entity without a usable prior projection has no baseline
and is treated conservatively as unknown, never as evidence that nothing changed. The checkpoint is
written:

- **periodically**, by one system-owned `IntervalRecurrence(interval_s=60)` (§3.1), since Recovery
  consumes Timing's execution primitive like everything else that needs periodic work. The callback
  performs a checkpoint replacement only when the checkpoint is `dirty` (a critical-entity projection,
  recovery target, or checkpoint-owned recovery field changed since the completed commit); otherwise
  it performs only an O(1) dirty-flag check and no disk I/O. A failed replacement leaves the flag set
  for retry and emits the ordinary persistence diagnostic;
- **immediately** after specific events that must not be lost to periodic-write staleness: a manual
  confirmation created, approved, dismissed, cancelled, or timed out; a transition back to
  `normal` from any non-normal `RecoveryState`. Manual hold checkpoint mutation instead follows its
  stricter, fact-consistent journal protocol in §6.4.

`RecoveryTargetSnapshot` entries (§7.4) are deliberately different: accepted target changes are
coalesced in memory and written at the next checkpoint commit, at most once per entity in that commit.
They never trigger the immediate-write path; a dirty snapshot is eligible for the next 60-second
checkpoint tick's commit. This bounded loss window is the
explicit performance trade-off for actuator
baseline recovery; manual-hold identity/audit state remains on the stricter journal-`fsync` path in
§6.4.

It answers "did anything change while Heima was offline" cheaply; it is **not** a general restore
mechanism, and — deliberately — it never forces every piece of runtime state through the full
`HouseFact`/`Provenance` shape. The narrowness (only allowlisted attributes, only critical entities)
is a safety/efficiency property, not an oversight: most runtime state genuinely should start clean
after a restart. §6.3's conditional implicit-hold restoration and §7.4's opt-in desired-target
baseline are the two narrow, explicitly-gated exceptions; neither is a precedent for widening this
into a general restore engine.

### 7.4 Power-recovery reconciliation

**Resolved 2026-09-09: recovery restores a baseline, then evaluates the house as it is now.** A
confirmed `power_recovery` must not replay commands that were missed during the outage, nor blindly
reapply the exact observed state from before it. Both would be wrong after a long outage: the sun may
have set, a scheduled period may have ended, or a resident may have changed the context while Heima
was unavailable. Instead, recovery supplies an optional, last-known desired-target **baseline** to
the ordinary current evaluation; the resulting current policy then replaces, narrows, or retains it
before any command is sent. Thus, under unchanged conditions a managed light/fan returns to its prior
desired state, while four hours of elapsed time can legitimately make a light that was previously off
become on.

Layer 0 defines a narrow checkpoint payload and service; it neither reads the live Layer-2 registry
nor issues an actuator command:

```python
@dataclass(frozen=True)
class RecoveryTargetSnapshot:
    entity_id: str
    target: PersistedProjection             # accepted desired target, never a raw HA State
    captured_at: EvidenceInstant
    policy: Literal["reconcile", "require_confirmation"]
    actuator_configuration_fingerprint: str # candidate Actuator execution semantics at target
                                             # acceptance; reload discards a target that no longer matches
```

The owner that accepts an `ApplyStep` records or replaces this snapshot only for an actuator whose
composition-time `power_recovery_policy` (Layer 2 `Actuator`) is `"reconcile"` or
`"require_confirmation"`. The snapshot is **last-write-wins per entity**, queued for the next
checkpoint commit and coalesced to at most one write per entity in that commit. There is no synchronous
flush on a target change, no journal for ordinary facts or commands, and no checkpoint read on the
normal evaluation path. Performance is the deliberate reason for this bounded best-effort guarantee:
a power loss after a target changes but before its batch commits may recover the preceding completed
target, or no target at all, never a fabricated newer one.

Snapshot persistence is not an additional acceptance condition for an `ApplyStep`. If its proposed
target cannot form a valid `PersistedProjection`, the already-authorized command still proceeds, the
owner omits that entity's recovery snapshot and emits a diagnostic. A later restart then has no
baseline for that entity rather than retaining an oversized or malformed target.

At configuration-generation cutover (Layer 2 §2.5), Layer 0 receives resolved Actuator policy and
fingerprint deltas rather than reading a registry. A snapshot whose recorded fingerprint differs from
the active candidate is discarded; `policy="never"` deletes it. A target therefore cannot be applied
under changed capabilities or a newly stricter policy.

Once Recovery has identified a confirmed `power_recovery`, current entity reads are available, and
the system has left `degraded_recovery`/`recovery_settling`, it exposes the last completed snapshots
as a read-only baseline for one full current evaluation. The evaluation order is mandatory:

1. Start from the snapshot target only for an opted-in actuator; an absent snapshot means no
   historical baseline for that entity.
2. Evaluate all current facts, time/calendar state, safety constraints, and manual holds. Their
   present-time result has higher precedence than the baseline.
3. Compute one final desired target per actuator and compare it with the freshly read actual state.
   Only this final delta may become an `ApplyStep`; recovery never first applies the old baseline and
   then applies a second, newly calculated target.

`power_recovery_policy="reconcile"` permits that final delta to be applied automatically.
`"require_confirmation"` turns the final target into a normal runtime-confirmation proposal; it is
never applied before confirmation. `"never"` contributes no snapshot and no automatic recovery
target. The recovery baseline is consumed only by power recovery, not by an ordinary process restart.
If recovery or a command attempt is interrupted, the next cycle repeats the same read/evaluate/compare
operation; actuator recovery is therefore idempotent reconciliation, not impossible physical
exactly-once delivery. This is intentionally separate from the Manual Hold journal, whose purpose is
identity/audit continuity rather than command replay.

### 7.5 Dependency on Timing, and bootstrap order

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
- **A `CronEntry`'s `due` passes while Heima is offline**: no missed occurrence is queued, replayed,
  or inferred from an interrupted countdown. On restart an `IntervalRecurrence` arms its first new
  deadline at `now + interval`; a `WeeklyRecurrence` arms its next matching civil-time occurrence.
  This requires no durable scheduling state beyond the standing rule itself and avoids an unprovable
  catch-up decision. An owner that needs startup work performs it explicitly during bootstrap, where
  that work can be named, reviewed, and tested independently of recurrence timing.
- **Durable-tier write failure** (§4): logged and surfaced as a diagnostic event; the cycle is not
  aborted and the in-memory buffer is unaffected. The durable tier is important for audit and
  learning but is not the source of truth for same-cycle correctness — losing one write is
  recoverable, crashing the engine over it is not an acceptable trade.
- **Checkpoint write failure** (§7): logged and surfaced; Recovery falls back to treating the next
  cycle conservatively (i.e. as if still `degraded_recovery` for classification purposes) rather than
  silently assuming `normal` on stale or missing checkpoint data.
- **Manual Hold journal append/`fsync` failure** (§6.4): the hold remains live for safety but is marked
  `durability_pending`; its durable facts wait for a background retry with backoff. A crash before a
  successful journal write can lose its identity/audit record, which is surfaced as degradation and
  resolved at restart only by the ordinary explicit/implicit conservative rules — never fabricated.

---

## 9. Diagnostics

Layer 0 state must be inspectable, consistent with the project's broader diagnostics culture (a
runtime/plugins/event-store diagnostics surface already exists for other layers):

- **Timing**: every pending `AtJob` and `CronEntry` (id, owner, due, label), queryable at any time.
- **Recovery**: current `RecoveryState`, age of the last checkpoint write, count and identity of
  entities currently carrying `unknown_during_downtime`/`power_restore_candidate`, plus the count,
  age, and entity ids of pending `RecoveryTargetSnapshot`s and the recovery baseline/final-target
  decision for each reconciled actuator.
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

No unresolved Layer-0 runtime parameter remains.

---

## 12. Acceptance criteria (for the eventual implementation phase)

Not part of this design spec's approval gate — recorded so the implementation phase inherits a
concrete checklist rather than re-deriving one:

- One `AtJob`/`CronEntry` execution path, monotonic-safe by construction; no remaining independent
  timer call site anywhere in the codebase.
- `Window`/`LearnedWindow`/`WarmupGate`/`WeeklyRecurrence`/`IntervalRecurrence`/`CalendarWindow` used
  everywhere a bespoke duration/threshold/schedule field exists today — none left on a domain or
  reaction config directly.
- `LearnedWindow` construction rejects a `seed` outside `[min_seconds, max_seconds]`, in a test that
  tries both an under-range and an over-range seed — verified separately from calibration's own
  clamping, since seed is what every dwell check uses before the first calibration completes (§3.2).
- Temporal construction rejects `bool`, zero, negative, `NaN`, and infinite durations for `Window`,
  `IntervalRecurrence`, and `LearnedWindow` bounds; rejects inverted learned ranges; accepts an equal
  positive learned range; rejects invalid weekly weekday/hour/minute fields; and rejects a naive or
  non-UTC `AtJob.due`. Static failures reject startup/reload staging, while a dynamic invalid job is
  diagnosed and never armed (§3.1/§3.2).
- Each short-term input stream has a 15-minute default buffer horizon. A declared `Window`/
  `LearnedWindow` requirement longer than that extends only the addressed state `FactIdentityKey` or
  event `(fact_type, Location)` stream, not unrelated facts; a test registers an hour-long dwell and
  confirms its input history is retained for an hour while an unrelated stream expires at 15 minutes
  (§4.1).
- Every `HouseFact` and every `ApplyStep` carries a non-forgeable, redacted `FactSource`/
  `ApplyStepSource`; a `correlation_id` chain is traceable from a resolved state back to the facts
  that fed it and forward to any resulting `ApplyStep`, per the rules in §5.2. Non-forgeability itself
  is verified per boundary (corrected 2026-09-08 — this criterion previously only checked that fields
  were present, never that a forgery attempt is actually rejected), for every listed case in §5.1:
  a fabricated `kind="admin_command"` from a non-admin connection is rejected/reassigned
  non-authoritative; a fabricated `kind="third_party_plugin"` result is never upgraded to
  `kind="sensor"`/`kind="recovery"`; and `kind="resident_response"` is verified against both of its
  distinct boundary checks separately — an attempted assignment with no matching active confirmation
  request, and, independently, an attempted assignment for an explicit hold with no corresponding
  resident-attributed helper edge — an admin-attributed edge instead emits `admin_command`, while an
  automation, service, or unknown-context edge is rejected with a diagnostic. Passing one check must
  never be treated as satisfying the other.
- An explicit hold's live state is never anything but a fresh per-cycle helper read; across a restart,
  its checkpointed identity is retained only when that helper is still active, otherwise it is
  terminally reconciled or discarded as §6.2 requires. An implicit hold's live
  state never survives a restart unless it passes all five checks in §6.3 (evidence completeness,
  expiry, eligibility, restart-cleanliness, live-state match) — including a test where `evidence` was
  wiped by Layer 1 §4.3's fail-soft policy, verifying discard rather than undefined behavior — and
  every restoration — in every test that exercises one — produces both its active current-state fact
  and its `restored` lifecycle fact, with a fresh Recovery correlation id; every failed restore
  produces exactly one `restoration_discarded` lifecycle fact with its specified reason. Lifecycle
  events reach the resident through Layer 6's notification pipeline, never through a direct Layer 0
  call into Layer 6.
- A confirmed power recovery with an opted-in light/fan preserves the last completed desired-target
  snapshot only as a baseline, evaluates current conditions before issuing any command, and sends one
  final idempotent delta rather than replaying historical commands. A simulated four-hour outage whose
  current time has crossed a lighting boundary verifies that a light previously off is turned on when
  current policy requires it; an unchanged-context case verifies the previous desired target returns.
  A target changed immediately before an intentionally unflushed checkpoint batch verifies that only
  the preceding completed target (or no baseline) is used, never a claimed newer target. `never` sends
  no recovery command and `require_confirmation` creates a proposal rather than an `ApplyStep`.
- Every hold transition emits the exact §6.1 state/lifecycle pair and source: activation, resident or
  admin clear, expiry, replacement, explicit identity reconciliation, restoration, and every
  restoration-discard reason. A replacement
  closes the old `hold_id` before activating the new one; terminal state facts have `active=False` and
  no `held_state`; no lifecycle event is used as a live-state read. Tests verify each required
  `kind`/`source_id`/`source_type`/`actor_type`, including `ha_admin` rather than an untyped "admin",
  and confirm all four replacement facts share exactly one newly minted correlation id.
- Every Manual Hold journal state is exercised: a crash after journal `fsync` but before the facts
  batch, and a crash after its facts batch but before checkpoint compaction, both recover exactly the
  original fact roles and checkpoint update with no duplicate lifecycle event; a replacement recovers
  all four roles under its one operation id. A forced journal-`fsync` failure leaves the hold live and
  `durability_pending`, performs no durable fact write before retry, and after a simulated hard crash
  follows the documented conservative restart outcome rather than inventing an id or audit record.
- Manual-hold `Provenance.evidence.expiry` is written as Layer 1's canonical `EvidenceInstant`, never
  as a raw `datetime`; restart recovery discards a checkpoint whose expiry is absent, malformed, or
  non-UTC, verified independently from the generic evidence-shape fail-soft case.
- A query for "every `HouseFact` true in `Location` X between t1 and t2" correctly reports a fact as
  true throughout the window when its only durable record predates `t1` by a wide margin (§4), via the
  at-or-before-`t1` plus within-window reconstruction — verified for a fact stable for a period longer
  than its `fact_type`'s own retention window.
- Persistence computes the same `FactIdentityKey` for two facts that share `fact_type` and canonical
  `Location` but differ in `when`, `value`, `Provenance.source.correlation_id`, or `evidence`; a test
  verifies that provenance changes alone do not create a second latest-value slot for the same
  real-world fact (§4.0).
- Write-on-change compares `FactChangeFingerprint`, not `value` alone: tests verify that same value
  plus changed `available`, changed `confidence`, or changed stable source fingerprint is persisted;
  same value plus only a changed `correlation_id` or `evidence` is not; and two unavailable facts with
  different raw/stale `value` fields compare equal after unavailable-value canonicalization (§4.0/§4.2).
- A state candidate with an unchanged fingerprint creates neither a new short-term history record nor
  a durable-queue entry, while three changed candidates for the same key in one cycle preserve all
  three records in coordinator `AppendOrder` and leave the latest-value index on the third. A failed
  batch retains that ordered queue for retry; the next in-process candidate still compares against the
  in-memory current index rather than the older durable record (§4.1/§4.2).
- Fact ownership is composed before producers start: dotted glob patterns support whole or partial
  segment matching only (`*` never crosses `.`), match complete fact types only, and are checked for
  overlap during staging. An overlap with differing owner or emission kind — including a Layer-2 state
  claim that reaches Layer 0's reserved manual-hold event namespace — is rejected without an
  evaluation-path lookup; an equivalent-owner/equivalent-kind overlap is accepted. An event fact is
  appended twice when emitted twice with identical payload, has no `FactIdentityKey`/latest-value
  entry, and is rejected when requested as current state or via `FactRef.previous_cycle` (§4).
- A configuration-generation swap assigns a new non-forgeable `configuration_fingerprint` to every
  impacted source, forcing an otherwise unchanged state fact to persist; an Actuator recovery snapshot
  whose fingerprint no longer matches is discarded before recovery can propose or apply it (§5/§7.4).
- Every non-fact durable projection is checked as a copied Layer-1 `PersistedProjection`: a malformed
  manual-hold update is rejected before its journal write; an oversized recovery target leaves its
  already accepted `ApplyStep` intact but creates no baseline; and one invalid critical-entity
  projection is omitted without invalidating other checkpoint entries (§4.1/§6.4/§7.3/§7.4).
- Retention (time-based or count-ceiling) never evicts the single most recent record for a given
  `FactIdentityKey`, verified by a test that ages a stable fact's only record well past its
  `fact_type`'s retention window and confirms it is still present and still returned by the
  reconstruction query above; a superseded (non-latest) record for the same key, aged the same way, is
  confirmed evicted normally (§4.3).
- The 50,000-record count ceiling is a hard per-`fact_type` safety limit even when it conflicts with
  a declared retention target; the 512 MiB global watermark additionally prunes globally oldest
  evictable records when several compliant types accumulate. Neither removes a latest state record or
  rejects an observation. A history interval predating the durable retention-pruning marker reports
  `retention_coverage="truncated"`; a consumer requiring a complete window refuses that input and
  remains degraded rather than learning from the shorter remainder. If protected latest states alone
  exceed the watermark, diagnostics expose `storage_pressure` while current state remains intact
  (§4.3).
- With no declared retention requirement, a fact type keeps its superseded state records and event
  records for the 14-day system-wide baseline; a declared 30-day requirement raises only that fact
  type's target to 30 days, subject to the separate hard count ceiling (§4.3).
- Retention may evict an event record normally once its time/count policy requires it; event history
  has no latest-record exemption (§4.3).
- A `CalendarWindow`'s `summary` field carries the calendar entity's raw event text unmodified — no
  code path inside Layer 0's production of it performs keyword matching or produces a named category,
  verified by constructing one from an entity with no `Sensor`/`CalendarInterpretation` registered at
  all (§3.4) and confirming it's still produced correctly.
- Calendar extraction normalizes timed events to UTC and treats a date-only all-day event as local
  midnight-inclusive through local-midnight-exclusive before UTC conversion, verified across a DST
  transition; `active_now` includes a window exactly at `start` and excludes it exactly at `end`.
  A `ready` empty snapshot, a failed snapshot, and a response with one malformed event plus one valid
  event are tested separately, confirming empty is not failure and a malformed sibling is discarded
  with a diagnostic rather than poisoning valid data (§3.4.1).
- `upcoming_starts_within` returns a future window that starts within a declared seven-day horizon with
  its original `start`/`end`/`summary` intact, excludes an already-active window from that future view,
  and never performs classification. After a simulated restart, Layer 0 obtains a fresh snapshot before
  the first calendar-dependent evaluation, exposes an already-active event without replaying old
  boundaries, and reports failure rather than using a pre-restart cache when that refresh fails.
- A `WeeklyRecurrence` at `02:30` in `Europe/Rome` fires once at `03:00` on the spring-forward date,
  and once at the first `02:30` (`fold=0`) on the fall-back date, never again at the repeated
  `02:30`; both physical fall-back instants still match the same civil-time pattern for bucketing.
  An `IntervalRecurrence` crossing either boundary retains its elapsed monotonic cadence, and a
  configured timezone change re-arms a weekly entry without a catch-up firing (§3.1). After a
  simulated restart, an interval arms at `now + interval` and neither recurrence pattern replays a
  missed occurrence; an owner that needs initialization work is verified to perform it from explicit
  bootstrap logic, not from a scheduler callback.
- An admin-authored HA `schedule.*` helper is read as an ordinary state-bound boolean fact; a change
  to its effective state triggers normal evaluation without a Heima recurrence picker or `CronEntry`.
  An unavailable or unmapped helper state produces `available=False` and cannot activate its Reaction
  (§3.1/Layer 2 §3-4).
- A durable-tier write failure, a checkpoint write failure, or a job callback exception, exercised in
  a test, never crashes the engine and always produces a diagnostic event (§8).
- Recovery's periodic checkpoint is an `IntervalRecurrence` of 60 seconds and writes only while dirty:
  a clean sequence of ticks performs no disk writes; multiple accepted target changes for one entity
  before the next tick produce one last-write-wins snapshot commit; and a failed checkpoint remains
  dirty for retry while the evaluation path continues without disk I/O (§7.3/§7.4).
- A declared `FactRef.previous_cycle` key resolves from the sealed O(1) in-memory snapshot on the
  next in-process cycle even when the preceding durable batch failed. After a simulated clean
  shutdown/restart, the key is pre-hydrated before the first DAG from the matching committed cycle;
  after an unclean restart, missing/mismatched clean marker, or unhealed durable-batch failure it
  instead resolves `available=False` for that first cycle and performs no evaluation-path disk read
  (§4.1).
- Recovery/Checkpoint classification is available, read-only, before the first domain runs in every
  test cycle, including the first cycle after a simulated restart.

---

## Related documents (background only, not required reading)

This spec incorporates and, where needed, revises decisions originally made in v2's
`core/manual_hold_framework_spec.md`, `core/runtime_checkpoint_and_power_recovery_spec.md`, and
`core/runtime_provenance_spec.md`, and in this planning branch's own `v3_architecture_recap.md`
(Layer 0), `v3_backlog.md`, and `v3_house_fact_draft.md` (§WHEN). Where this document and any of
those differ, this document is the current word for Layer 0's v3 design.
