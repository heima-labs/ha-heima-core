# Heima v3 — Layer 0: Cross-Cutting Runtime Facilities

**Status:** Defined V3 contract. Not implemented.
**Layer:** 0 of 8 (of the v3 architecture: Substrate, Registries, Learning, Semantic Resolution,
Reactions, Notification, Extensibility, Admin surface build on top of this one).

This document is self-contained: it defines what Layer 0 is and does without assuming the reader
has read Heima's v2 specs. Where v2 already solved a piece of this problem, that solution is
restated here in full, not referenced as a prerequisite — v2 documents are listed at the end,
background only.

## Normative precedence

This document defines the current V3 Layer-0 design contract. Open corrections are tracked in
the CA4 backlog; runtime implementation is a separate phase. When implemented, any code/spec
divergence must be resolved explicitly — code is a reference implementation, not the source of truth.

---

## 1. Purpose

Layer 0 collects the runtime facilities that sit **outside the semantic-resolution DAG** entirely: nothing in
Layers 2-5 (Registries, Learning, Semantic Resolution, Reactions) may depend on a Layer 0 facility
changing mid-cycle, and nothing in Layer 0 depends on a semantic resolver. Six facilities:

1. **Timing** — one execution primitive plus a recurrence policy layer, and non-executing
   comparison types for reasoning about elapsed or absolute time without scheduling anything.
2. **Persistence** — the two-tier `HouseFact` storage (Layer 1), durable observation-continuity metadata, and the unified notification delivery outbox that support their respective contracts.
3. **`FactSource` / `ApplyStepSource`** — one structured-provenance vocabulary spanning facts and
   actions, and the `correlation_id` rules that make "why did the house do this" answerable.
4. **Divergence Hold Manager** — process-local, per-channel suppression after a new
   observation differs from a physically confirmed Heima expectation; its origin is evidence-based.
5. **Recovery / Checkpoint** — pre-DAG classification of runtime health (just started, recovering
   from a power loss, degraded, normal), and the durable checkpoint that backs it.
6. **Runtime health telemetry** — read-only, capability-explicit observations of the engine's own
   latency and effective local resource limits for slow-path admission control; it never decides a
   semantic resolver or action policy.

## 2. Scope

Layer 0 is responsible for:
- the one execution primitive ("at") and the one recurrence policy layer ("cron") every other
  subsystem's time-driven behavior is built from;
- the non-executing comparison types (`Window`, `CalendarWindow`) used to reason about elapsed or
  absolute time; for `CalendarWindow` specifically, the pre-DAG mechanical extraction of raw
  `start`/`end`/summary event data from a `calendar.*` entity (§3.4) — never the classification of
  that raw text into a named category, which is Layer 2's `CalendarInterpretation`;
- `HouseFact` storage mechanics (durable + short-term tiers), durable observation-continuity metadata (§4.4), and the unified notification delivery outbox (§4.5) — not the `HouseFact` type itself, which is Layer 1;
- post-commit notification of declared state keys to core components outside the DAG (§4.8);
- the non-forgeable provenance vocabulary attached to every `HouseFact` and every `ApplyStep`, and
  the rules for how a `correlation_id` is minted and propagated;
- representing an internal channel divergence hold and clearing it on restart or an observation break;
- computing pre-DAG recovery/degradation context and the checkpoint that backs it.
- collecting a read-only runtime-health snapshot outside engine evaluation for slow-path consumers;
  it owns neither learner scheduling nor a resource-allocation policy.

Layer 0 is **not** responsible for:
- semantic resolution, policy logic, signal fusion, or actuator commands (Layers 2-5);
- deciding *what* triggers a re-evaluation cycle. Heima is event-driven: evaluation is triggered by
  meaningful state changes, not by a fixed timer. Timing's periodic fallback (§3.1) is a bounded
  safety net against missed events, not a return to timer-driven evaluation;
- defining the `HouseFact` type, `Location`, `Zone`, or `Topology` (Layer 1) — Layer 0 consumes
  `HouseFact` and references `Location`, it does not own either.
- deciding whether a learner is admissible, assigning worker capacity, or changing a learning profile
  (Layer 3). Layer 0 measures; Layer 3 interprets those measurements under its own contract.

### 2.1 Foundation contract with Layer 1

Layers 0 and 1 form one **foundation slice** with distinct ownership, not a falsely one-directional
stack. Layer 0 owns runtime mechanisms and the `FactSource` vocabulary; Layer 1 owns the immutable
semantic data contracts (`HouseFact`, `Provenance`, `Location`, `Zone`, `Topology`). Persistence and
other Layer-0 mechanisms may accept Layer-1 `HouseFact`/`Location` values, while Layer-1
`Provenance` embeds Layer-0 `FactSource`. This is a bounded reciprocal dependency on immutable
contracts only.

It never permits a behavioral cycle: Layer 0 does not query or invoke Layer-1 registries, topology,
zone resolution, sensor/fusion logic, semantic resolution, or policy logic; Layer 1 does not execute Timing, Persistence,
Recovery, or Divergence Hold Manager behavior while constructing its value objects. Bootstrap composes these
contracts before cycles begin, and the hot path contains no Layer-0 -> Layer-1 -> Layer-0 call chain.
Concrete module layout may use a neutral contracts module or type-only references to avoid a language-
level import cycle, but this does not create a new architectural layer or change either owner's
normative responsibility.

### 2.2 Non-goals

- Prescribing internal class layout beyond the shapes below.
- Configured policies that happen to use a `Window` or a `CronEntry` (e.g. a specific reaction's dwell
  time) — those are Layer 5 concerns configuring a Layer 0 primitive.

---

## 3. Timing

**Time representation**: every declared instant in every V3 contract is
Layer 1's `EvidenceInstant`, including `HouseFact.when`, an `AtJob.due`,
calendar windows, checkpoint entries, learning artifacts and Reaction
records. It is normalized to UTC and validated before entering the contract;
there is no second `datetime` or `Z` wire form. An implementation may parse
the canonical value into a timezone-aware UTC datetime while doing arithmetic,
but must not store, publish, fingerprint or transfer that temporary object.
The one deliberate exception is `WeeklyRecurrence.hour`/`minute`
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
    owner: str          # subsystem name, e.g. "semantic_resolver", "divergence_hold", "engine"
    due: EvidenceInstant  # canonical UTC instant at which this job is due
    label: str
    basis: Literal["elapsed", "wall_clock"]  # declared by the owner; see below
```

`AtJob` is the **one** execution primitive: a scheduled one-shot deadline.

**Scheduling semantics**: at arm (or re-arm) time, Timing parses the canonical `due`, takes the
current reference instant of the job's `basis` (below), computes their difference **once**, and
schedules that duration on a monotonic timer. The owner declares the job's `basis`, which also
selects that reference:

- `elapsed`: the due expresses a duration from an in-process anchor (a fixed-duration hold, a
  `Stability` dwell or grace, a Reaction delay, a confirmation ceiling, an
  `IntervalRecurrence`). Its reference is the current cycle-instant clock of §3.5 (the floored
  history clock), from which the owner derived the due, so the countdown equals the intended
  duration even while the floor is frozen. The monotonic countdown is authoritative and is never
  re-evaluated against wall-clock time while armed; a wall-clock correction cannot shorten, extend
  or repeat it.
- `wall_clock`: the due expresses an instant defined outside the process (a `WeeklyRecurrence`
  occurrence, a calendar boundary, a session or recovery boundary derived from civil or calendar
  time, a Layer-2 `last_reported + max_source_age` expiry). Its reference is the current
  wall-clock reading in UTC, the same unfloored reading §3.5 compares, never the cycle-instant
  clock: while §3.5 holds cycle instants above a regressed wall clock, the civil deadline must not
  fire early. A detected clock discontinuity (§3.5), at a cycle start, at the periodic check or at
  bootstrap, re-arms every pending `wall_clock` job against its unchanged `due` and the wall-clock
  reading taken by that detection. A due at or before that reading fires exactly once,
  immediately; a later due waits. Re-arm uses the ordinary `job_id` replacement,
  so a job never fires twice for one due.

An owner that cannot classify a job's due is invalid at registration. Daylight Saving Time never
changes a UTC `due`; it affects only the civil-time computation of a `WeeklyRecurrence` due
(below). This keeps the robustness property of the historical pre-V3 manual-hold expiry for
elapsed waits, while absolute deadlines follow corrected wall-clock time.

**Re-registration**: `job_id` is a replace key, not a uniqueness constraint to reject on conflict —
registering an `AtJob` with an already-pending `job_id` cancels the old timer and arms the new one.
This lets an owner simply "set the deadline to X" without first checking whether one already exists.
An owner may cancel its pending `(owner, job_id)` idempotently; cancellation leaves no scheduled
callback for that key. A callback already handed to the owner may still race with replacement or
cancellation, so the owner validates its current activation and arm revision before doing work
(Layer 5 §6.0 for programmed Reactions). Timing itself does not decide whether a Reaction step
remains eligible.

```python
@dataclass(frozen=True)
class WeeklyRecurrence:
    weekdays: frozenset[int]   # 0-6, non-empty
    hour: int
    minute: int = 0

@dataclass(frozen=True)
class IntervalRecurrence:
    interval: "Window"  # positive elapsed duration; no separate seconds field

@dataclass(frozen=True)
class CronEntry:
    job_id: str
    owner: str
    pattern: IntervalRecurrence  # Initial V3: elapsed cadence only (see below)
    label: str
```

**Temporal construction validation is mandatory and shared.** One pure validator accepts a duration
only when it is an `int` or `float` but not `bool`, is finite, and is strictly greater than zero; it
normalizes the accepted value to `float`. It is applied to `Window.seconds` and
`IntervalRecurrence.interval.seconds`. `WeeklyRecurrence.weekdays` is non-empty and contains only non-boolean
integers in `0..6`; `hour` and `minute` are non-boolean integers in `0..23` and `0..59` respectively.
`AtJob.due` must be a canonical `EvidenceInstant`. No constructor or scheduler silently clamps, rounds,
or corrects an invalid temporal value; the explicit deadline-construction rule below derives an instant
from a valid duration and changes no duration.

Static configuration shapes are constructed and validated while staging the startup or candidate reload
generation. A dynamic `AtJob` is validated when its owner registers it with Timing, before it reaches
the scheduler; this is not deferred to the callback or repeated in an evaluation cycle. Rejected
configuration leaves the active generation unchanged, while a rejected dynamic job produces a
diagnostic and arms nothing.

**Deadline construction from a duration.** Every contract that derives an instant from an anchor
instant plus a positive duration uses one rule. This covers every `AtJob.due` computed that way (a
`Stability` dwell or grace, a fixed-duration hold, a Reaction delay or step interval, an
`IntervalRecurrence`, a confirmation ceiling, a Layer-6 digest window) and every horizon end such as
`now + horizon` for a calendar read (§3.4.1).

- **Exact value.** The duration's value is the decimal number written by its canonical RFC-8785
  form (§3.2), not the exact binary value of the `float`: `0.1` s is exactly 100 000 µs. The sum
  is computed exactly (for example in integer microseconds from that decimal), never through a
  lossy conversion such as a native duration object built from the `float`.
- **Representation.** The derived instant is the first `EvidenceInstant` at or after the exact
  sum: the sum itself when it is a whole microsecond, otherwise the next whole microsecond. Because
  the anchor is a whole microsecond and the duration is positive, the derived instant is strictly
  later than the anchor. A deadline therefore never fires before its requested duration, and a
  recurrence never re-arms at its own anchor. The difference is below one microsecond and is not a
  change of the `Window`, which keeps its canonical value.
- **Stricter consumers.** A consumer whose own contract is stricter keeps it: the Layer-2
  source-age expiry uses the first instant strictly after its sum (Layer 2 §3.2), and Layer-5
  learned-delay paths require whole milliseconds at staging (Layer 5 §6.0).
- **Overflow.** A derived instant later than the largest canonical `EvidenceInstant`
  (`9999-12-31T23:59:59.999999+00:00`) is unrepresentable. A dynamic registration is then
  rejected with a diagnostic and arms nothing; a static horizon is rejected at staging when its end,
  computed from the staging cycle-instant clock, is unrepresentable. The `Window` itself remains a
  valid duration.
- **Latency is separate.** A monotonic timer that fires after its due is execution lateness, never
  a representation rule; the basis references of this section and §3.5 apply after the due is
  constructed.

`CronEntry` is the recurrence policy layer on top of `AtJob`. In Initial V3 its pattern is only an
`IntervalRecurrence` ("how often, relative to now"): every Heima-owned recurrence is an elapsed
cadence, and admin-authored civil schedules belong to Home Assistant (below). `WeeklyRecurrence`
("which civil moments") is a value type for descriptor time-window parameters and for civil-time
classification; it is not a `CronEntry` pattern. A future weekly `CronEntry` needs its own reviewed
contract, including the identity of an already served occurrence across clock and timezone
changes.

For a `CronEntry`, Timing computes the next `due` relative to now (the cycle-instant clock, the
`elapsed` reference), arms an `AtJob`, and on fire recomputes and re-arms. An `IntervalRecurrence`
job has `basis="elapsed"`; a `WeeklyRecurrence`-derived descriptor boundary has
`basis="wall_clock"`. Calendar cache refresh at a known event boundary
(§3.4.1) is `wall_clock`; a fixed-duration hold deadline (§6.2) is `elapsed`. For `WeeklyRecurrence`, `hour`/`minute` are civil-time values in
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

**Daylight Saving Time execution policy.** This policy applies only while computing a
`WeeklyRecurrence` occurrence; it does not suppress, merge, or alter already-produced `HouseFact`
events or their UTC timestamps. A requested local civil time can be exceptional at a DST boundary:

- When the requested time is **nonexistent** at the spring-forward transition (for example,
  `02:30` in `Europe/Rome` when the clock advances from `01:59:59` directly to `03:00:00`), the
  occurrence starts once at the first valid local instant after the gap (`03:00` in this example).
- When the requested time is **ambiguous** at the autumn fall-back transition (for example,
  `02:30` occurs first in CEST and then again one real hour later in CET), the occurrence starts
  once at the first occurrence (`fold=0`); the second must not start it again.

The next-due calculation must explicitly detect both cases rather than rely on an implementation's
implicit timezone conversion behavior. `pattern.matches(fact.when)` remains a civil-time
classification operation, so either physical occurrence in an ambiguous hour matches the requested
weekday/hour/minute for history and bucketing; only occurrence computation applies the
single-start rule. `IntervalRecurrence` uses elapsed monotonic time and is unaffected by either
case. A change to Home Assistant's configured `time_zone` invalidates a currently armed boundary
derived from a `WeeklyRecurrence` and re-arms it between evaluation cycles using the new zone. The
consumer that derives occurrences defines which occurrence was already served, so that no past
occurrence is replayed merely because the zone or the clock changed (Layer 5 §7.2 for the
Initial-V3 presence-simulation session).

`CronEntry`'s **definition** (owner, pattern, label, job_id) is treated as durable configuration —
a system-owned periodic safety net or another Heima-internal recurrence is a standing rule that
outlives any single pending countdown. This is why `CronEntry` state is expected to survive a
restart (the *rule* is re-read from configuration, a fresh `due` is computed against current time,
and a new `AtJob` is armed — nothing about the interrupted countdown is recovered. For an
`IntervalRecurrence`, that fresh deadline is `now + interval` under the deadline-construction rule
above. Missed occurrences are never replayed implicitly after restart.
An owner that requires an initialization action performs it explicitly during its own bootstrap,
rather than obtaining it indirectly from scheduler catch-up) while a
one-shot `AtJob` that belongs to transient runtime state (see §6, Divergence Hold) does not:
if nothing persists the reason an `AtJob` should exist, there is nothing to re-arm it from after a
restart. This is a design choice about durable configuration, not a limitation of `AtJob` itself.
A divergence-hold deadline is never re-armed from history or a checkpoint (§6.3).

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

The rule governs **standalone** schedules: a recurrence whose own active state is what makes
something happen. It does not govern a **descriptor time-window parameter**: a bounded local-time
window that a versioned Layer-5 descriptor explicitly declares, that never activates anything by
itself, and that only limits when a Reaction already activated by its own start criteria may act.
Such a parameter uses this section's `WeeklyRecurrence` and `Window` types and validation, is
part of the Reaction's immutable configuration, and arms only that Reaction's ordinary next-step
job. `security.presence_simulation`'s session is the Initial-V3 example (Layer 5 §7.2).

### 3.2 Comparison: `Window` and `LearnedWindow`

```python
@dataclass(frozen=True)
class Window:
    seconds: float
```

`Window` is the one V3 elapsed-duration contract. Its canonical JSON form is
`{"seconds": <finite positive RFC-8785 number>}`; the number is seconds,
including fractional seconds when needed. The validated constructor
normalizes a non-boolean `int`/`float` to finite `float` and rejects zero,
negative values, `NaN`, infinity and negative zero. No artifact, Reaction,
job, fact value or other contract stores a parallel integer-millisecond,
`timedelta` or bare-seconds duration form. Algorithms may calculate with
temporary numeric or native duration values, but declared fields and
fingerprint inputs return to `Window` before crossing a contract boundary.

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
    minimum: Window          # lower clamp for the selected duration
    maximum: Window          # upper clamp for the selected duration

Window | LearnedWindow    # anywhere a Window is expected, a LearnedWindow may be substituted
```

`LearnedWindow` lets a dwell or correlation timer calibrate itself from observed history instead of
using a fixed seed forever. Two properties are load-bearing, not optional refinements:

- **`where` is mandatory**, matching Layer 1's rule that a `Location` is always present, never
  absent — without it, "calibrated from occupancy sessions" is ambiguous between the whole house and
  one specific room, and two `LearnedWindow` instances could silently blend unrelated data.
- **`minimum`/`maximum` are mandatory `Window` clamps.** A `LearnedWindow` feeds dwell timers that
  gate physical actuation — an uncalibrated or degenerate value is a real risk, not a theoretical
  one: a calibrated value drifting toward zero causes flicker (rapid on/off), drifting unbounded
  causes a stuck actuator (a light that never turns off). This is a Layer 0 guarantee precisely so
  every call site doesn't have to remember to add its own floor and ceiling. **The clamp is a
  construction-time invariant on `seed` too, not only on values produced later by calibration**
  (corrected 2026-09-08, found in review — previously stated only as a property of the calibrated
  value): `minimum.seconds <= seed.seconds <= maximum.seconds` must hold when a `LearnedWindow` is
  constructed, validated procedurally like `Location`'s own construction rule (§5 of the Layer 1
  spec). Before the first calibration ever completes — precisely the warm-up window where this
  guarantee matters most, since no real data has smoothed anything out yet — every dwell check runs
  against `seed` directly; an out-of-range seed would defeat the guarantee exactly when it's needed,
  not in some later edge case.

The same temporal validator applies to every duration field here: `minimum` and `maximum` are
strictly positive finite `Window`s (never `bool`), `minimum.seconds <= maximum.seconds`, and `seed.seconds`
lies inclusively within that range. Equality is intentionally valid: it configures a fixed bounded
window while retaining one uniform representation. Invalid ranges and values fail construction/staging;
calibration clamps only a valid computed candidate within an already valid range.

No calibration formula (e.g. percentile-of-past-durations) is specified here, and Layer 0 makes no
policy choice. A semantic resolver never calibrates one, because it reads no history (Layer 4 §3);
learned timing is calibrated on the Layer-3 slow path and selected by Layer 5's bounded learned-delay
path (Layer 3 §4.4, Layer 5 §6.0, CA4-13).

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
    start: EvidenceInstant
    end: EvidenceInstant
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
depend on Layer 2. `summary` is the event's raw text, never classified here. The Layer-2
declared-context producer (Layer 2 §2.9, CA4-121) that needs to ask "is this `CalendarWindow` a
vacation" declares the explicit `KeywordClassifier` configuration it uses; it must not infer one
merely from `source_entity`. A Layer-5 plan reads only `FrozenCalendarView` results or the declared
`household.*` facts and never classifies calendar text (§4.1). That same pure classifier may
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
    refreshed_at: EvidenceInstant | None  # None when no successful snapshot exists

active_now(entity_id, now: EvidenceInstant) -> CalendarWindowRead
upcoming_starts_within(entity_id, now: EvidenceInstant, horizon: Window) -> CalendarWindowRead
```

When `status="ready"`, `active_now` returns every window containing `now`.
`upcoming_starts_within` returns every non-active window whose `start` is strictly after `now` and
at-or-before `now + horizon`, that end being derived under §3.1's deadline-construction rule; it preserves each window's original `start`, `end`, `summary`, and
`source_entity`, rather than reducing it to a category.
A predictive consumer that needs seven days therefore declares `horizon=Window(seconds=7 * 24 * 60 *
60)` and can decide today about an event starting tomorrow. Active and upcoming are distinct views, so
an active event is never presented a second time as future work.

Consumers declare their largest upcoming horizon at registration. A Layer-2 Sensor with a
`CalendarWindowReadBinding` (Layer 2 §3.1), which reads only `active_now`, registers its entity with
a zero upcoming horizon: the cache then holds that entity's active windows and refreshes at its
boundaries without prefetching future windows. The cache prefetches through the
maximum declared horizon for that entity, refreshes asynchronously on a `calendar.*` change, before
the next known start/end boundary, and before its prefetched horizon runs out. This lets a scheduled
reaction be armed for an event boundary even when Home Assistant emits no unrelated state change, while
keeping all provider I/O out of the reaction path.

On restart, Layer 0 obtains a fresh snapshot before the first calendar-dependent evaluation, recomputes
the next boundaries, and does not replay past start/end callbacks. An event already active is visible on
that first successful snapshot; a failed initial refresh makes calendar reads `failed` until a later
refresh succeeds. Nothing from a checkpoint is treated as live calendar truth.

Calendar sits in Layer 0, same rank as "at"/"cron" — **not** a semantic resolver (Layer 4), not an
extension (Layer 7). The ready timeline snapshot is read before the core DAG each cycle, same as
Recovery/Checkpoint (§7), and never through an extension registration mechanism; provider refresh remains
asynchronous as §3.4.1 requires. This pre-DAG placement is exactly why classification cannot happen
here: a `Sensor`/`Interpretation` lookup (Layer 2) runs on the ordinary hot-cycle path (Layer 2 §2.2),
not before it.

Layer 0 never resolves a conflict or precedence between calendar sources. It provides only raw
per-entity intervals and containment; the consumer that declares one or more staged requirements owns
any permitted classification and composition under its own contract. Layer 4 transports the opaque
frozen view only and never reads, classifies, resolves, or otherwise interprets it.

### 3.5 Cycle instant and clock discontinuity

Layer 0 alone reads the wall clock for engine evaluation. Every evaluation cycle receives one
**cycle instant**:

```text
cycle_instant = max(wall_clock_reading_utc, previous_cycle_instant + 1 µs)
```

It is the `CycleInputBarrier.when` of that cycle and an `EvidenceInstant` with ordinary
microsecond precision. Distinct cycles therefore never share an instant, and the instant of every
later cycle is strictly greater. Within one cycle, every coordinator-assigned instant — a fact
`when`, a normalized ingress edge instant, an occurrence time — lies in
`(previous_cycle_instant, cycle_instant]`; an ingress source instant at or before the previous
cycle instant is raised to `previous_cycle_instant + 1 µs`, preserving ingress order, and the
original source instant is not retained. At bootstrap `previous_cycle_instant` is the latest
durably committed instant known to Persistence (last `CycleCommitMarker`, continuity watermark
or observation boundary, §4.1/§4.4), so recorded history never moves backward across a restart.
In ordinary operation the wall-clock reading is already later and the rule changes nothing; it
adds one comparison per cycle.

The **cycle-instant clock** applies the same rule at any reading between cycles:
`max(wall_clock_reading_utc, last_cycle_instant + 1 µs)`. The cycle instant is the time assigned
to history; it is not the execution reference for civil deadlines. While the floor holds cycle instants above a regressed wall clock, `wall_clock` jobs
keep counting against the wall-clock reading (§3.1) and `elapsed` jobs against the cycle-instant
clock. A `wall_clock` job that fires in that interval requests an ordinary cycle, whose facts
receive the floored cycle instant; the job's `due` never becomes a history instant.

Equal-`when` facts still occur *within* one cycle and remain one concurrent group (§4.0); they
never span two cycles.

**Clock discontinuity.** At each cycle start and in the system-owned 60-second check of §4.4,
Layer 0 compares the elapsed monotonic time with the elapsed wall-clock time since the previous
comparison. A difference greater than **1 second** in either direction is a clock discontinuity:

- **Forward jump.** The skipped wall-clock interval was not observed. Layer 0 records a
  process-wide observation gap with reason `clock_discontinuity` from the last cycle instant
  before the jump to the first cycle instant after it, and re-arms pending `wall_clock` jobs
  (§3.1).
- **Backward jump.** Layer 0 emits the `clock_regression` diagnostic, re-arms pending
  `wall_clock` jobs and records a process-wide `clock_discontinuity` gap. Its bounds depend on
  whether the corrected wall clock falls behind the cycle floor
  (`previous_cycle_instant + 1 µs`):
  - **Wall clock still ahead of the floor.** Cycle instants follow the corrected wall clock,
    but durations measured across the correction are wrong by its size. The gap uses the
    forward-jump bounds: from the last cycle instant before the detecting comparison to the
    first cycle instant after the detection.
  - **Wall clock behind the floor.** The cycle-instant rule keeps instants strictly increasing,
    so successive cycles advance by one microsecond from the frozen floor until the wall clock
    exceeds it again. Those instants do not measure real elapsed time. The gap runs from the
    first frozen cycle instant until the first cycle whose wall-clock reading exceeds the
    floor.

  A regression of at most 1 second is not a discontinuity and opens no gap. If it puts the
  wall clock behind the floor, the cycle-instant rule absorbs it and Layer 0 emits
  `clock_regression` alone; otherwise nothing is emitted.

**Corrections while the floor holds.** Each discontinuity opens its own gap, whose bounds depend
only on that correction: its direction and, for a backward correction, whether it leaves the wall
clock behind the floor. An earlier gap still waiting for the wall clock to exceed the frozen floor
does not change a later gap's bounds, and a later correction neither closes nor extends it; it
ends under its own rule. A forward correction detected while the wall clock is still behind the
floor therefore takes the forward-jump bounds and ends at the first cycle instant after its
detection, even though that instant is still frozen: the frozen interval is already covered by
the earlier gap, and the skipped interval by the new one. A further backward correction over
1 second while the floor holds takes the frozen-floor bounds, starting at its own first frozen
cycle instant.

At bootstrap a wall-clock reading more than 1 second earlier than the durable floor is a backward
discontinuity under the same rule. A forward difference at bootstrap is indistinguishable from
downtime and is already covered by the ordinary process interruption (§4.4).

**Detection by the periodic check.** A discontinuity found by the 60-second check of §4.4,
between cycles, is handled at detection: `wall_clock` jobs are re-armed, the diagnostic is emitted
and the gap opens immediately. Its bounds are still cycle instants, because only cycles assign
instants to recorded history: it starts at the last cycle instant before the check and ends at the
first cycle instant after it, except a backward correction that leaves the wall clock behind the
floor, which ends under the frozen-floor rule above. The detection point never changes which rule
applies: the same correction found at a cycle start or at the check gets the same end rule. The next cycle compares
against that check, so one correction is detected once. Until the end boundary is durably
acknowledged, a historical read reaching past the start is incomplete (§4.4).
`clock_discontinuity` gap boundaries use the durable observation-continuity metadata path of
§4.4; until a boundary is acknowledged, a historical read spanning it is incomplete. Elapsed
waits, dwell and holds continue on monotonic time and are unaffected (§3.1); they are never
re-evaluated against cycle instants that a discontinuity may have distorted. Historical
durations derived from `when` differences across a `clock_discontinuity` gap are incomplete, never
used as observed elapsed time.

---

## 4. Persistence

`HouseFact` (Layer 1) storage is **always atomic** — one produced fact record at exactly the
granularity the engine computes at internally (per-room, per-signal), never a bundled record. A
"snapshot" (everything true at one instant, or in one place, over one window) is never its own stored
shape — it is a **query reconstructed at read time**: "every `HouseFact` true in `Location` X between
t1 and t2." A generic consumer (including a Layer 7 extension) never needs to learn a bespoke
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
`lighting.*door*` matches `lighting.pippodoor` and `lighting.doorpippo`, but not
`lighting.room.lifecycle`; `lighting.*.lifecycle` matches the latter.

During staging, the engine determines whether two dotted glob patterns have a common valid concrete
fact type. Their overlap is valid when and only when both `owner_id` and `emission_kind` are equal;
otherwise the candidate generation is rejected. This is not about constraining a legitimate partial
match: it guarantees that every concrete fact type has one persistence semantic and one owner. For
example, `lighting.*` as `state` and `lighting.*.lifecycle` as `event` do not overlap because
their segment counts differ; `lighting.*.*` as `state` would conflict with the lifecycle claim.
The glob compilation and overlap check are staging-only; no pattern match or conflict lookup occurs in
the evaluation path.

**Extension namespace (Layer 7 §6).** The `ext.*` namespace is reserved for Layer-7 extensions. A
non-extension producer cannot claim a pattern that overlaps it, and an extension may claim only
`ext.<extension_id>.*` under `owner_id="layer7.extension.<extension_id>"`; a claim overlapping a core
namespace or another extension's namespace rejects the candidate generation.

Every statically-addressable state producer also contributes a global `(fact_type, Location, owner_id)`
claim during the same composition pass. The engine rejects duplicate `(fact_type, Location)` claims,
regardless of layer; a namespace-owning dynamic producer is protected by its
exclusive `FactTypeClaim` instead. Layer 2 `Sensor` and `FusionRule` registrations contribute only `state` claims; a Layer-7 extension producer staged in the Layer-2 generation may contribute state and event claims (Layer 7 §6). Future layers
must make the same declaration before their producers are admitted. This is a startup/configuration
validation table, not a second facts registry or a hot-path abstraction.

The core reserves `FactTypeClaim(fact_type_pattern="manual_hold.lifecycle",
owner_id="layer0.divergence_hold", emission_kind="event")` for hold lifecycle audit (§6).
It also reserves `FactTypeClaim(fact_type_pattern="actuator.manual_control",
owner_id="layer0.manual_control_ingress", emission_kind="event")` for the verified manual-control
edge in §5.1.1. That owner alone constructs its closed three-field canonical value; no Layer-2
Actuator registration or extension may claim the same event type.
The core reserves `FactTypeClaim(fact_type_pattern="actuator.channel_state.*",
owner_id="layer0.channel_observation", emission_kind="state")` for the
per-channel normalized physical-state projection of §5.1.1.1. Each staged
channel also contributes its exact `(fact_type, Location, owner_id)` state
claim. The value is produced from the already frozen Layer-2 observable-state
binding, not from a second HA read or a Layer-5 decision.
The core reserves `FactTypeClaim(fact_type_pattern="actuator.correction",
owner_id="layer5.correction_attribution", emission_kind="event")` for the Layer-5 attribution
event of Layer 5 §6.1. Layer 5 owns its closed `CorrectionAttributionEvent` value contract;
Layer 0 persists the resulting event fact under this exclusive claim.
The core reserves `FactTypeClaim(fact_type_pattern="actuator.target_lifecycle",
owner_id="layer5.target_evidence", emission_kind="event")` for the
admitted-target historical phases of Layer 5 §6.1. It is audit/learning
evidence, not a second command or live target authority.
The core reserves `FactTypeClaim(fact_type_pattern="reaction.decision.*",
owner_id="layer5.reaction_decision", emission_kind="state")` for the per-Reaction Layer-5
decision state (Layer 5 §5.2). Each Reaction-catalog entry contributes its exact
`(fact_type, Location)` claim; ordinary write-on-change persists only changed decisions, and the
default retention applies to superseded values.
The core reserves `FactTypeClaim(fact_type_pattern="reaction.managed_episode.*",
owner_id="layer5.managed_episode", emission_kind="state")` for the
per-channel confirmed-episode projection of §5.1.1.2. Only a staged
descriptor that declares managed-episode resumption may emit it; Layer 0
persists and reads it without inferring ownership from target history.
The core reserves `FactTypeClaim(fact_type_pattern="reaction.follow_up",
owner_id="layer6.reaction_follow_up", emission_kind="event")` for the sole Layer-6
follow-up event adapter (Layer 5 §6.0). Layer 5 supplies only the typed occurrence and
prepares its durable intent through §4.5; it never appends this fact or renders user text.
The core also reserves `FactTypeClaim(fact_type_pattern="automation.availability",
owner_id="layer6.availability", emission_kind="event")` for the one Layer-6 availability-event
adapter. Layer 3, Layer 4 and Layer 5 may emit only their typed transient suppression occurrence;
none may claim or append this event fact directly. This makes the persistent owner, event semantics and
delivery boundary unambiguous before any user-visible availability path is enabled.
The core likewise reserves `FactTypeClaim(fact_type_pattern="reaction.advisory",
owner_id="layer6.reaction_advisory", emission_kind="event")` for the Layer-6 adapter of Layer 5's
typed `ReactionAdvisoryOccurrence` (Layer 5 §6.0); Layer 5 never appends it.
The core reserves `FactTypeClaim(fact_type_pattern="recovery.confirmation_request",
owner_id="layer6.recovery_confirmation", emission_kind="event")` for the Layer-6 adapter of the
typed `RecoveryConfirmationOccurrence` (§7.4.1). It likewise reserves `reaction.action_notice`
(owner `layer6.reaction_action_notice`), `proposal.review_pending` (owner
`layer6.proposal_review`) and `reaction.consent_request` (owner `layer6.consent_request`) as
Layer-6 event claims for the typed Layer-5 occurrences of Layer 5 §6.0; Layer 5 never appends them.
The core reserves `FactTypeClaim(fact_type_pattern="system.health", owner_id="layer6.system_health",
emission_kind="event")` for the Layer-6 adapter of the typed `RuntimeHealthOccurrence` (§10.1); no
other layer appends it.
The core reserves `FactTypeClaim(fact_type_pattern="reaction.advisory_feedback",
owner_id="layer5.advisory_feedback", emission_kind="event")` for the resident feedback that Layer 5
records from an answered advisory (Layer 5 §6.0); it is not a notification.

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
    route_fingerprint: str | None
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
For a Layer-2 fusion, `route_fingerprint` is the stable, canonical digest of
the contributing input route defined in Layer 2 §7. It excludes volatile
correlation ids and free-form evidence, so an unchanged route does not cause
a write on every cycle. A direct producer leaves it `None` unless its own
registered contract declares a stable route identity.

It excludes `when` because time changes every cycle, excludes `correlation_id` because it is a causal
trace id minted per origin/cycle (§5.2), and excludes `evidence` because evidence can contain
diagnostic detail whose shape or wording changes without changing the fact's current state. A
producer that wants an evidence-only diagnostic change to be visible emits a diagnostic event (§10);
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
every consumer (a Layer 3 learner, a Layer 7 extension, an admin diagnostic) gets it right by using the
same query instead of each re-deriving — or mis-deriving — it independently. When records have the
same `when`, the at-or-before record and the changes are ordered by `AppendOrder` above; the final one
at that instant is the reconstructed current value.
If no at-or-before record survives, the state at `t1` is unknown: a later record cannot
seed the earlier portion of the interval. The read reports truncated retention rather
than treating that portion as an unchanged value. A pruned transition may also make a
retained predecessor unreliable (§4.3). A predecessor invalidated by global queue overflow
is instead an observation-coverage limit (§4.4/§4.6), not retention pruning. It cannot
seed a post-gap interval merely because its bytes remain on disk. Until a valid new
baseline for that key is acknowledged, durable reconstruction returns unknown and
`queue_overflow` incomplete coverage for the unseeded interval; a later baseline
never fills an earlier part of the interval retroactively.

### 4.1 Two storage tiers

- **Durable long-term store** — disk-backed, for learning (Layer 3) and audit. Feeds queries over
  days to weeks of history.
- **Short-term in-memory buffer** — no disk I/O, for correlation/follow-up matching
  (`Window`-based, §3.2) within a bounded recent window.

Two tiers because they have genuinely different cost profiles: correlation matching happens on the
hot per-cycle path and can never wait on a disk read; long-term learning needs history that cannot
fit, or be affordably kept, entirely in memory. Every immediately constructible
accepted fact touches the in-memory buffer without disk I/O and enters the
ordered durable queue through the batching policy below; an unchanged state
candidate only consults the O(1) current index and creates no buffer record.
Every accepted `manual_hold.lifecycle` transition is a complete, validated
inline event fact. It enters the short-term buffer and ordinary ordered
durable queue immediately, independent of background disk latency (§6.4).

**Stored-data boundary.** These tiers, the current index, `PreviousCycleSnapshot`, durable retry queue,
notification delivery outbox, recovery-target snapshot, and checkpoint retain only complete `HouseFact`s or
their explicitly declared normalized projections. Every such non-fact payload is a Layer-1
`PersistedProjection`: copied JSON-compatible data, maximum nesting depth 2, numbers within Layer 1's
numeric domain (Layer 1 §3), and at
most 8 KiB after canonical UTF-8 serialization. A record that holds such a payload — an outbox
record, a recovery-target snapshot, a checkpoint entry — is a bounded typed storage envelope owned
by this layer, not itself a `PersistedProjection`: its fields are scalars or closed typed
sub-records, a nested target value is stored as canonical JSON text (Layer 5 §6.0 facet codec), and
its canonical serialization obeys the same 8 KiB bound. The audit queue retains
only complete validated inline event facts, never an oversized non-fact
projection. These facilities never retain a Home Assistant `State` object,
its full attributes mapping, HA event context, or another mutable HA runtime object. Layer 2 extracts
the small declared input it needs at the HA boundary; Layer 1 validates and copies the resulting
payload before any Layer-0 facility can buffer or persist it. Every retained fact and projection is
deeply immutable (Layer 1 §3), so the buffer, current index, snapshots, queue and readers share one
value without defensive copies and no consumer can alter another's view. Calendar is the narrow explicit case:
its cache retains only normalized `start`/`end`/`summary`/`source_entity` fields in `CalendarWindow`,
never a provider response or HA state object.

**`previous_cycle` is a third, deliberately tiny in-memory view, not a disk read.** At composition,
consumers declare every state `FactIdentityKey` they will address with `FactRef.previous_cycle=True`.
After each evaluation completes, Persistence seals a `PreviousCycleSnapshot` containing only those
declared keys and their final `HouseFact`s (including an unavailable value where that was the final
result). The next evaluation reads this immutable snapshot in O(1); it never scans the short-term
history buffer and never waits for the durable store. A durable-batch failure does not invalidate this
snapshot while the process remains alive.
The snapshot starts empty after an unclean restart or a missing/mismatched clean marker;
only the single-use clean-shutdown pre-hydration below seeds it from durable state. A newly
declared or impacted producer key also has no usable predecessor until one complete evaluation
under current execution semantics has sealed it; durable history never seeds such a key, nor
any key outside that clean-shutdown exception.

**`FrozenHistoryView` is the bounded current-cycle history view for policy evaluation, not a second
store.** During Layer-5 staging, every enabled `ReactionEvaluationPlan` declares its finite set of
short-term `HistoryViewRequirement`s (typed state/event stream, `Window`, and slice
shape). At generation staging, a Layer-3 live signal emitter declares, in the same form, the
requirements derived from its `runtime_resolvable` `SampleBinding` features (Layer 3 §4.2, §6.3).
A requirement has the following closed form; its declaring consumer computes its own bounded
aggregate from the returned slice, rather than asking Layer 0 to run a policy expression:

```python
@dataclass(frozen=True)
class HistoryViewRequirement:
    requirement_id: str
    stream: BufferStream  # StateBufferStream or EventBufferStream, §4.1 below
    horizon: Window
    slice_kind: Literal["state_timeline", "event_occurrences"]
```

Staging requires a nonempty unique requirement id within the active union,
one registered stream of the matching state/event persistence kind, a
positive bounded horizon retained for that stream, and the matching
`slice_kind`. An event request cannot be read as a state timeline or vice
versa. The resolved requirement and producer generation enter the plan
fingerprint; Layer 0 validates their union against the active in-memory retention and, at the cycle input
barrier, creates one immutable view over exactly those retained records at or before that barrier.
The view has no general query API: a consumer may read only a requirement id it declared and receives its
canonical `HouseFact` slice or `None` for an incomplete interval. An empty tuple means a
complete interval with no matching event, never incomplete history. A state requirement
without an at-or-before-start record is incomplete; either kind of requirement is
incomplete when its requested start precedes known in-process observation coverage or
required records were evicted, or the declared stream intersects a known
Layer-2 source-age gap (§4.4). This result is frozen for the cycle. It never opens the durable store, scans a mutable live buffer, reaches
Home Assistant, or observes an append accepted after the barrier. Retention is pinned for the short
duration of that cycle's signal emission and policy evaluation, then released.

**`FrozenCalendarView` is the corresponding bounded future-calendar view, not a semantic plan or a
second calendar cache.** A Layer-5 plan or a core Layer-2 declared-context producer (Layer 2 §2.9)
that needs calendar context declares a finite `CalendarViewRequirement` during staging: one permitted `calendar.*` entity and one positive bounded
upcoming horizon. Layer 0 contributes the largest declared horizon to the existing per-entity cache
prefetch (§3.4.1). At the same `CycleInputBarrier`, it freezes that requirement's `active_now` and
`upcoming_starts_within` results using `barrier.when`. A policy may subsequently read only its staged
requirement id; it cannot issue an ad hoc calendar query, widen a horizon, inspect another calendar,
or observe a refresh that arrived after the barrier. The view exposes raw `CalendarWindow` text only
to the staged pure Layer-2 `KeywordClassifier`; neither the classifier result nor a policy outcome may
persist a calendar summary.

```python
@dataclass(frozen=True)
class CycleInputBarrier:
    cycle_id: int
    when: EvidenceInstant
    max_append_ordinal: int

@dataclass(frozen=True)
class FrozenHistoryView:
    barrier: CycleInputBarrier
    requirement_ids: frozenset[str]
    # read(requirement_id) -> tuple[HouseFact, ...] | None; None means incomplete history.

@dataclass(frozen=True)
class CalendarViewRequirement:
    requirement_id: str
    entity_id: str                  # one staged calendar.* entity
    upcoming_horizon: Window        # finite, positive; `now + horizon` must be representable (§3.1)

@dataclass(frozen=True)
class FrozenCalendarView:
    barrier: CycleInputBarrier
    requirement_ids: frozenset[str]
    fingerprint: str                # SHA-256 of the canonical staged read results
    # active(requirement_id) and upcoming(requirement_id) return the frozen CalendarWindowRead.
```

`CycleInputBarrier` is an immutable intake boundary, not a claim that no later Layer-4 or Layer-5
fact may share the same `when`. Such later facts belong to their declared execution phase and cannot
retroactively enter the view. Every later engine cycle receives a different `cycle_id` and a
strictly later cycle instant (§3.5), so a retry of one barrier cannot read newly arrived data and
two cycles never form one equal-time group.

`FrozenCalendarView` is created only from a `ready` cache snapshot obtained after process startup as
required by §3.4.1. A failed read remains `failed` in the frozen view and makes a calendar-dependent
policy abstain; it is never treated as an empty calendar. Its fingerprint covers, for every declared
requirement, the status, refresh instant, active and upcoming normalized windows. This lets a later
calendar refresh, cancellation, or edit create a new cycle and a distinct policy input without placing
provider I/O or mutable cache reads on the decision path.

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
`previous_cycle` reference has no value for that first cycle (absent, never a fabricated
`available=False` fact), which a consumer maps to `previous=None` (Layer 4 §5.1). This refuses to pass an older
durable record off as the immediately preceding cycle. Once one new cycle completes, the ordinary
in-memory snapshot resumes.

**The buffer's retention horizon is declared, not fixed — resolved 2026-09-08, reusing §4.3's own
retention-floor pattern rather than inventing a second mechanism.** A dwell check ("has this fact
been true for at least `seconds`, continuously") or a correlation check ("did fact Y occur within
`seconds` after fact X") needs the buffer to actually hold every change within that `Window`'s
`seconds` (or a `LearnedWindow`'s `maximum.seconds`) — not just the latest value, the full recent history
of changes, to confirm nothing flipped false in between. Nothing previously tied the buffer's own
bounded horizon to how large a `seconds`/`maximum.seconds` a consumer might configure; a dwell/correlation
check requiring more history than the buffer actually retains can never be satisfied, correctly or
not — a silent, permanent false negative, not a degraded read. Resolved the same way §4.3 resolves
the identical shape of problem for durable retention: whichever subsystem registers a `Window`- or
`LearnedWindow`-based dwell/correlation check **declares** its own `seconds`/`maximum.seconds` requirement
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
    horizon: Window                 # `LearnedWindow` declares its validated maximum as this Window
```

`register_buffer_requirement(requirement)` is a composition/staging operation, never a hot-path call.
The owner registers one requirement for every state/event stream its dwell or correlation can inspect;
the active buffer stores a precomputed `max(default, requirements)` horizon per stream. Removing or
changing a requirement takes effect only with the next atomic configuration generation; it may evict
now-unneeded older in-memory entries but never reads disk to refill a stream.

### 4.2 Write policy

Writes to the durable tier are **batched at the end of each evaluation cycle** — buffered during the
cycle, flushed once after the semantic-resolution/policy pass completes, rather than one disk write per fact.
This keeps the ordinary per-fact hot path free of I/O. The explicitly
qualified `reaction.follow_up` intent preparation in §4.5 is the sole synchronous
write before a Reaction boundary advances under healthy storage. This batching,
not write-on-change below, protects ordinary reaction latency: even a policy that wrote every fact every cycle would still be off the
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
Only the bounded overflow policy of §4.6 may discard a queued item, and it always declares the
resulting loss as historical coverage.
The first valid per-channel `actuator.channel_state.*` observation after
process restart is the narrow §5.1.1.1 exception: it force-writes one
new-epoch boundary record even if the old durable state fingerprint
matches, never one record per identical read.
After the global baseline invalidation of §4.6, a fresh producer assertion may also
force one durable baseline record despite an unchanged live fingerprint. This record
uses its actual validation-cycle instant and coordinator-assigned `AppendOrder`;
it joins the same ordered end-of-cycle batch and `CycleCommitMarker` transaction.
It does not append a duplicate transition to the live short-term buffer, change the
live current index or `PreviousCycleSnapshot`, or notify §4.8 subscribers. A genuine
state change still takes the ordinary path exactly once and may supply the new baseline.

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
immediately constructible event fact is appended to the in-memory buffer and ordered durable queue, even if its payload
resembles a prior event; this preserves repeated occurrences for audit and Layer 6. The batch remains
the ordinary event-fact durable I/O boundary. The narrow prepared follow-up-intent
exception at a qualifying Reaction boundary is defined in §4.5; ordinary append-only
event history and hold lifecycle audit add no blocking write to the reaction path.
The Layer-5 `actuator.target_lifecycle` producer supplies its stable
`event_id` as a narrow append-once operation key: queue retry or recovery
with the same id and identical canonical fact reuses the first append;
the same id with a different payload is a producer-contract error and
blocks historical completeness for that stream. Distinct admitted
decisions/phases keep distinct ids. The existing
`actuator.correction.deduplication_key`, Layer-0 resident ingress
`control_edge_id` and the Layer-5 `reaction.advisory_feedback` key
`(advisory_operation_id, action)` likewise deduplicate only their own event family,
never arbitrary event facts. This does not make event payload equality a
general persistence identity or drop repeated real occurrences.
The validated `manual_hold.lifecycle` fact follows this ordinary immediate
buffer and queue rule. A live hold is authorized only by its frozen admission
view, never by the presence or absence of an audit fact (§6.4).

### 4.3 Retention

Retention is **time-based per `fact_type`, with a hard per-`fact_type` record-count ceiling and a
global pruning watermark** — not one global count-based cap. These three controls serve different
purposes and are applied by background/batch maintenance, never by an evaluation-cycle scan:

- **Why time-based, not count-based, as the primary policy**: atomic per-fact storage produces far
  more records for the same information than a bundled snapshot would, and Layer 3 learners reason
  about history in days (a `training_window` of 7 days, a `WarmupGate.min_elapsed` of weeks), not in
  record counts. A pure count cap would be exhausted in hours by the finer granularity, silently
  breaking exactly the learning use cases this model exists to serve. Persistence keeps a small
  `fact_type -> retention_floor` table, but — consistent with Layer 0 depending on nothing above it,
  Persistence never populates that table by reaching upward to query Layer 3's
  registrations. Instead, whichever subsystem registers a learner, or a Layer-7 extension input slot
  with a history window (Layer 7 §5), **declares** its retention need against Persistence at registration time (e.g. "retain at least 30
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
  `fact_type` sharing a global budget. Hitting the ceiling raises a diagnostic warning (§10), since it
  usually indicates a misbehaving sensor worth investigating, not a config value to silently absorb.
- **Why also a global pruning watermark**: several individually compliant noisy types can still add
  up. The durable fact store therefore has a **512 MiB global watermark**, measured over the store's
  retained record data and indexes. After ordinary time and per-type pruning, maintenance above that
  watermark evicts the globally oldest *evictable* records (superseded state records and event
  records), recording the affected history streams' early-pruning coverage metadata and the
  affected fact types' aggregate diagnostics. Complete inline hold-audit facts
  count as ordinary event records under this same watermark (§6.4). It is a watermark, not an admission quota: it never
  rejects an observation, blocks a cycle, or removes a latest state record. If protected latest state records alone exceed 512 MiB, Persistence
  raises `storage_pressure` and continues to preserve them; an installer can then reduce registry
  cardinality or raise the operational watermark in a later release rather than Heima silently losing
  current house state.

**Retention coverage is explicit and stream-scoped.** Retention targets and the 50,000-record
ceiling remain per `fact_type`, but an early count-ceiling or global-watermark eviction is attributed
only to the history stream whose record was actually discarded: a state stream is its
`FactIdentityKey`; an event stream is its `(fact_type, Location)` pair. Persistence durably records
for each affected stream the most recent evicted record's `when` as
`last_early_pruning_at`, never the maintenance time. A history read returns its records
with `retention_coverage`. An event stream is `"complete"` only when the interval lies
wholly within effective time retention and starts strictly after that stream's
early-pruning instant. A state stream additionally needs a retained record at or before
the start, even if that record predates ordinary retention. If an early-pruning instant
is at or after the selected predecessor's `when`, an evicted transition may have
superseded it and the result is `"truncated"`. The single marker may conservatively
truncate an unaffected window, but never certify an unknown initial state as complete.
Missing predecessor, failed time bound or relevant early pruning also returns
`"truncated"`.

The result says whether retention policy may have removed records from that requested stream and
interval, not whether a device actually emitted observations or whether a learner has sufficient
samples — those remain separate availability and warm-up concerns. A multi-stream consumer must
require complete coverage for every stream it binds; one truncated input makes the joint historical
input truncated. Observation continuity is a separate condition (§4.4): complete retention cannot
turn an unobserved period into a complete history window. Aggregate pressure and count-ceiling diagnostics remain per `fact_type`, while
coverage markers are bounded metadata: a marker may be discarded as soon as ordinary time retention
already makes every interval it could affect truncated. The metadata is updated only by the pruning
path and read in O(1), so it adds no scan or I/O to the evaluation cycle.

A consumer that needs a complete declared historical window, including every `PatternLearner`, must
refuse to compute from a `"truncated"` read: it remains warm-up/degraded and emits a diagnostic until
its requested window is covered again. It must never substitute a shorter implicit window or treat
the remaining records as representative. This makes a noisy source reduce only its own learning
availability, while the hard ceiling continues to protect storage and maintenance latency for the
whole installation. In particular, a flapping temperature stream in one room cannot make a complete
history read for the same `fact_type` in another room report `"truncated"` merely because they share
the type-level ceiling.

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

### 4.4 Durable observation continuity

Historical reads distinguish retained records from periods in which Heima could observe.
Persistence owns one durable process-wide observation-continuity timeline, independent of
`retention_coverage` and of any live hold. A bounded declared durable history read returns
one `HistoricalReadResult` for its requested interval and required streams; the hot-path
`FrozenHistoryView` remains the separate frozen in-memory contract of §4.1.

```python
ObservationCoverageStatus = Literal["complete", "incomplete"]
ObservationGapReason = Literal[
    "clock_discontinuity", "continuity_metadata_unknown", "process_interruption",
    "queue_overflow", "required_stream_unavailable",
]

@dataclass(frozen=True)
class ObservationCoverage:
    status: ObservationCoverageStatus
    reasons: tuple[ObservationGapReason, ...]
    first_incomplete_at: EvidenceInstant | None

@dataclass(frozen=True)
class HistoricalReadResult:
    records: tuple[HouseFact, ...]
    retention_coverage: Literal["complete", "truncated"]
    observation_coverage: ObservationCoverage
```

`reasons` is empty and `first_incomplete_at` is None exactly for
`status="complete"`; an incomplete result has a nonempty, distinct, ASCII-sorted
tuple of applicable closed reasons and the first instant *within the requested
interval* at which a required observation is missing. A gap that began before
the request contributes the request start, not its earlier opening instant.
If continuity metadata is unknown, `first_incomplete_at` is
the request start, conservatively. The requested interval's declared endpoint
semantics decide whether a gap exactly on a boundary intersects it. The field
identifies an observation limit, never the occurrence time of a missing event.
`complete` requires that the
requested interval intersects neither a process interruption, a clock discontinuity (§3.5),
a durable-queue overflow loss or unseeded post-overflow baseline of a required stream,
a global overflow epoch (§4.6), nor an unavailable interval
of any required stream, and that continuity metadata is trustworthy. An unknown boundary
reports `continuity_metadata_unknown`, never optimistic completeness. Per-Actuator/channel
`available=False` intervals remain ordinary state history and affect only reads that
require that stream; they do not extend a process-wide interruption. A multi-stream read
is incomplete if any required stream is incomplete. `retention_coverage` independently
reports pruning: complete retention cannot establish that an unobserved window was complete.
No gap becomes zero events, an unchanged state, a resident action, or a hold. State
reconstruction (§4.1) cannot carry an at-or-before value across an incomplete interval
as proof of continuous observation.

For a state stream, the latest record is resolved **before** its availability is
tested. A newer `available=False` record cannot be skipped to reuse an older
available value. `HouseFact.when` dates an accepted transition, not an
identical subsequent read: neither a complete history query nor a current
policy declares a stable available state stale solely because its last change
was long ago. A requested interval can be complete only while Layer 2's
declared source-validity rules and the observation timeline permit it.

An ordinary `available=False` state transition already marks its required
stream unavailable from that fact's `when` until the next available
transition; Layer 0 does not duplicate that interval in another journal.
Separate stream-scoped interruption metadata records only an additional
**known break** not reconstructible from those facts, not every successful
read. If a staged Layer-2 `max_source_age` expires between cycles, Layer 2
supplies the known `last_reported + max_source_age` expiry as the gap start
and the first later valid observation barrier as its end. The unavailable
state fact, if one is emitted, keeps its actual detecting-cycle instant and
is never backdated. If an identical fresh report arrives before the next
cycle, the expiry gap still persists as metadata without creating either
an unavailable or duplicate same-value fact. Layer 2 keeps only the latest
report instant in bounded process memory to detect that case; a process
interruption covers lost memory across restart. Stream-gap boundaries are
keyed by the required `FactIdentityKey`, retained for every declared
historical window that could intersect them, and pruned only when no
supported read can require them; missing necessary boundary metadata makes
that read incomplete. The gap boundary is durable metadata on the ordinary
end-of-cycle path; until its acknowledgement, a historical read spanning
the uncertain boundary returns incomplete. Failed writes and unknown
boundaries use `continuity_metadata_unknown`, never fabricated continuity.
For an active report-age gate, Layer 2's ordinary `AtJob` expiry check (§3.2)
starts an evaluation even if no HA state edge arrives. A historical read
between expiry and durable gap acknowledgement must conservatively report
incomplete from that known expiry, rather than treating a delayed cycle as
positive evidence of continuity.

For a binding without a declared source-age limit, an available HA state
remains the current state until an observable failure or process gap. That is
the registered source's state semantics, not proof that a silent physical
device has reported again. A source that promises periodic reports must
declare a suitable Layer-2 age gate; one that only reports changes cannot be
assigned an invented heartbeat. These rules apply to every staged state
stream, independent of sensor or actuator kind.

A system-owned 60-second recurrence, off the evaluation and HA-command paths, advances one
durable continuity watermark only after all accepted facts **and** independently queued audit
events, including inline hold-audit facts (§6.4), through its chosen observation barrier
have durable acknowledgement. It may piggyback on
the Recovery checkpoint cadence, but must run even when the critical-entity checkpoint is clean.
An empty observation period can therefore advance the watermark without inventing a fact. An
unacknowledged queue item or failed write leaves the watermark where it was; the failure is
diagnostic and cannot certify a complete historical interval. The marker is bounded system
metadata, not a `HouseFact`, hold journal, or per-Actuator checkpoint.
A queue item discarded under §4.6 counts as resolved for this rule only after the
`queue_overflow` gap boundary that declares its loss is durably acknowledged; the watermark
never certifies a discarded item as written. An open global overflow epoch prevents
complete observation coverage through that epoch even if retained items have been written.
Its closure follows the acknowledged intake/accounting boundary of §4.6, not an
all-key re-seed transaction. The watermark may then advance under its ordinary accounting
rule while individual state keys still lack a valid durable baseline: it cannot erase
their `queue_overflow` coverage limits or certify an old value as current. The same
recurrence performs the clock comparison of §3.5.
An attempted hold transition that cannot construct a valid audit fact despite
its staged proof is also a continuity blocker from that known transition instant
(§6.4): the watermark cannot cross it. Reads requiring that audit stream
report `required_stream_unavailable` from that instant rather than infer zero
interventions. Unknown continuity metadata separately uses the request start.

On orderly shutdown, Heima drains and durably acknowledges all accepted facts and audit
events through its final observation barrier, then durably records the observation stop. If
that drain or stop write fails, the next startup uses the hard-crash boundary instead. At startup it durably opens the historical interruption before any historical read can
report complete coverage. With a matching orderly stop, the gap begins at that stop; after a hard
crash or uncertain stop, it begins no later than the last durable continuity watermark. The gap closes at the first post-restart `CycleInputBarrier` built from a newly completed
HA intake snapshot: the source-health result must be valid and every staged binding
must have an explicit current-cycle availability result, including `available=False`
for unreadable individual channels. A barrier made only from startup timers, a prior
cache, or a single entity edge does not close it. The global closure does not wait
for every Actuator to become readable; those still unavailable affect only their
required historical streams. The closure barrier id and UTC instant must be durable
before a historical read may report complete observation beyond that boundary.
Repeated failed startups leave the interruption open.
If the opening or closing metadata cannot be written, historical completeness stays unknown
and learning excludes affected windows until a durable boundary is established; live automation
continues under ordinary current-state admission. This metadata is separate from the single-use
`CleanShutdownMarker` for `previous_cycle` hydration (§4.1): consuming that marker cannot erase
historical coverage.

While HA is unreadable, no fresh current-state action is admitted. Once HA observation resumes,
current policy is evaluated normally, with no missed-command replay. If one Actuator/channel
remains unreadable, only its commands are suppressed as `actuator_state_unconfirmed` and its
dependent historical windows remain incomplete; other readable channels may act. The first
valid returned state starts a new observation epoch and does not itself create a hold (§6.3).

### 4.5 Unified notification delivery outbox

Every notification that Layer 6 delivers to a person — resident or administrator — uses one durable
delivery outbox owned by Layer 0. There is no per-feature delivery store, retry queue or direct
notification call elsewhere. Layer 0 provides only storage mechanics: record uniqueness, atomic
transitions, the atomic write with the notification's audit event fact, retention, and recovery
reads. Layer 6 owns rendering, routing, delivery attempts and every transition decision.

```python
NotificationDeliveryPhase = Literal["prepared", "ready", "delivered", "retired"]

@dataclass(frozen=True)
class NotificationDeliveryRecord:
    notification_kind: str            # the Layer-6-owned event fact type, e.g. "reaction.follow_up"
    operation_id: str                 # stable per notification; unique with notification_kind
    phase: NotificationDeliveryPhase
    intent: PersistedProjection | None    # "prepared" only; producer-owned typed intent
    notification_key: str | None      # delivery deduplication key, from "ready" on
    created_at: EvidenceInstant
    updated_at: EvidenceInstant
```

- **`prepared`** exists only for a kind whose producer must record a boundary before an action
  advances; in Initial V3 only `reaction.follow_up` (below). It holds a bounded producer-owned intent.
- **`ready`** is written in one durable transaction together with the notification's audit
  event fact (Layer 1 §3.1): either both commit or neither. Every delivered notification therefore
  has exactly one audit fact and one ready record, and a crash can never leave an event without its
  delivery record or the reverse.
- **`delivered`** records the acknowledged delivery attempt; **`retired`** ends the record: after
  delivery; for a prepared record, when its boundary needs no notice; or directly from `ready`
  without delivery when Layer 6 decides no notice is due any longer (for example an item closed
  before its deferred or grouped delivery). Retiring an undelivered record never removes its audit
  fact, which was committed with `ready`. One delivery attempt may cover several `ready` records
  (a grouped digest); each then records its own `delivered` transition.

`(notification_kind, operation_id)` is the unique key of the record and also the durable identity
of its audit event fact (`fact_type=notification_kind`), so an event fact needs no separate
reference and is appended at most once per operation. An exact retry of a transition returns the
existing record; a different payload under the same key is rejected. A `ready` record is retained,
whatever ordinary fact retention says, until it is delivered or retired. Delivery is recoverable
at-least-once, not exactly-once display: a crash after the destination accepted a message but before
`delivered` commits may repeat it, and `notification_key` lets an idempotent destination suppress the
repeat. Each record is a bounded typed storage envelope (§4.1 stored-data boundary); only its
`intent` is a `PersistedProjection` (Layer 1 §4). The outbox is separate from the
§4.6 retry queue and from the Recovery checkpoint. A storage failure leaves an affected notification
best effort and is diagnosed; it never blocks an evaluation cycle, an `ApplyStep` or a revocation.

#### 4.5.1 Reaction follow-up preparation

This kind adds the `prepared` phase and its bounded preparation wait to the common outbox
mechanics above. Layer 6 must supply the typed `reaction.follow_up` adapter: it validates
Layer-5 intent and occurrence payloads, builds the event fact, drives the outbox transitions,
and retries delivery. Layer 0 does not implement user-facing rendering or notification delivery.

The Layer-6 `reaction.follow_up` adapter uses the unified outbox (§4.5) with
`notification_kind="reaction.follow_up"`, keyed by the Layer-5 per-boundary,
per-Actuator/channel `operation_id` (Layer 5 §6.0); it is the only kind that uses `prepared`. Its `ReactionFollowUpIntent` schema is owned by Layer 5 §6.0 and validated by Layer 6
before persistence. It is a typed `PersistedProjection`, not a `HouseFact`,
checkpoint, hold journal, or second user-delivery envelope. Before a qualifying Reaction
boundary advances, Layer 6 durably inserts its `prepared` intent with the immutable Reaction,
generation, activation, Actuator/channel, path, possible hold id, target and last observed projection.
Its persisted `subject` is the scalar canonical `LocationKey` JSON text,
decoded back to a validated `Location` on recovery; facet maps contain only
canonical JSON text scalars. These rules keep the entire projection within
Layer 1's depth-two and 8 KiB limits, including a multi-room subject.
Layer 5 awaits acknowledgement only for this preparation and only until its
versioned, positive finite, monotonic core preparation deadline (Layer 5 §6.0).
It neither waits for rendering nor for HA delivery. A repeated id with a different canonical intent is rejected; an exact
retry returns the same acknowledgement. The outbox write occurs at the follow-up boundary,
not on every evaluation, state observation, or hold audit event.
An exit spanning several channels has one independent prepared/ready/retired
record for each channel id, not one activation-wide row or an atomic
all-channel notification. An exact retry of a channel reuses its frozen
first intent; a changed preparation under the same id fails. A failed or
timed-out prepare on one channel does not prevent successful preparations
on other channels. Recovery finalizes each committed prepared row
independently; an unprepared channel has only the existing best-effort
notice guarantee. The per-channel notification key prevents delivery
deduplication from merging different channels.

When Layer 5 supplies the final typed occurrence, Layer 6 validates it against the prepared
intent and builds the Layer-1 `OperationalEventValue` (no stored text, Layer 1 §3.1). One durable transaction appends the
event fact and changes that intent to `ready`; a failed transaction leaves it `prepared`, never
a half-persisted event. The durable key `(fact_type="reaction.follow_up", operation_id)`
allows one identical event on retry and rejects a different canonical payload; ordinary event
facts retain the append-every-occurrence semantics of §4.2. A fully confirmed action atomically retires its prepared intent without an event.
The same no-event retirement applies if fresh admission proves the proposed path no
longer qualifies before a command, including authority revocation. A failed retirement
can leave a conservative interruption notice after a crash; it never permits a stale call.
A prepared intent with no committed outcome or confirmed-success retirement at process
restart is finalized exactly once as `interrupted_before_outcome`; the
adapter never infers whether an HA call was sent or whether its physical target took effect.
A committed event wins over a stale prepared-state view. A follow-up event uses the
Layer-6 `FactSource(kind="system", source_id="layer6.reaction_follow_up")`,
the intent's registered `Location`, and the occurrence's UTC `occurred_at`; a
recovery interruption uses the recovery finalization instant as `when`, while keeping
`prepared_at` in the intent. The resulting notice may use the last
pre-interruption observation only with that timestamp/label; no old value is asserted current.
Recovery of this outbox never replays an Actuator call, restores a hold, or delays ordinary
current-policy automation.

The `ready` record remains available for Layer-6 delivery retry until the delivery attempt is
acknowledged, then may be retired; retention cannot remove an undelivered payload needed for
replay. A crash after HA accepts a delivery but before its acknowledgement can produce a
second visible notification, so the guarantee is recoverable at-least-once delivery, not
exactly-once display. The stable notification key lets an idempotent destination suppress
such a repeat when supported; it is not a fact identity. An unavailable storage
write or an unacknowledged preparation at that deadline exposes
`follow_up_durability_degraded`, even if storage has not declared an outage.
Unlike a hold audit failure (§6.4),
Layer 5 may then advance the scheduled step under ordinary guards and authority, so crash
recovery of that particular notice is not guaranteed. The same operation id is reused if an
uncertain preparation later becomes discoverable. On storage recovery the Layer-6
adapter resolves that id against the outbox before persisting a best-effort queued
event: a found intent is finalized atomically with the fact; an absent intent uses the
ordinary event queue with the same durable unique key. The timed-out prepare may
still commit later. Its insertion and final-event commitment therefore serialize
on the same operation id in one durable transaction domain: preparation checks
for an already committed final fact and cannot recreate `prepared` after it;
finalization checks for a prepared intent and retires it atomically with the fact.
The same per-operation ordering covers a fully confirmed or no-longer-qualifying
boundary with no event: its terminal retirement follows any in-flight prepare,
and a later prepare cannot reopen it. This ordering is background work after
the action boundary; it never extends Layer 5's preparation wait. An exact
late prepare is harmless, while a changed payload is rejected. It cannot
commit a final fact while leaving a found intent prepared. This reconciliation may fail during an ongoing
storage outage, in which case delivery is only best effort until storage returns. Revocation is
never blocked on this outbox.
This narrow synchronous preparation exception does not turn the ordinary event queue or
hold-audit queue into a synchronous write path.

### 4.6 Durable retry-queue budget and overflow

The ordered durable queue (§4.2) holds every accepted state transition, event fact, inline audit
fact and continuity boundary awaiting durable acknowledgement. While storage fails it retains
items for retry, but within a bounded in-memory budget:

```text
queue_budget_bytes = max(32 MiB, 5% × effective_memory_limit)
```

`effective_memory_limit` is the enforceable limit in the latest `RuntimeHealthSnapshot` (§9);
when it is absent or not enforceable the budget is exactly 32 MiB. Queue usage is measured as the
canonical UTF-8 bytes of queued facts and continuity metadata, including pending loss
markers. The fixed-size global marker below has reserved space within the budget; a
single item larger than the available budget is discarded under the same overflow rule. The budget is recomputed only when a new health
snapshot is published, never in the evaluation path; a lower recomputed budget applies to the
next overflow check and never discards an item retroactively merely because the budget changed.
The 32 MiB floor and the 5% coefficient are operational defaults, revisable from evidence in a
later release. The notification delivery outbox (§4.5) is a separate durable store and is not part
of this queue.

When accepting a new item would exceed the budget, Layer 0 frees space in this order and never
blocks admission, a cycle or an HA command:

1. **Collapse superseded state transitions.** For a state `FactIdentityKey` with several queued
   transitions, the oldest queued transitions that are superseded by a later queued transition of
   the same key are discarded. In ordinary overflow the latest queued state of every key
   remains, so durable current state can be restored once storage returns.
2. **Discard the oldest queued event facts**, across event streams, in append order.

In ordinary overflow, continuity and gap boundaries are retained. Every discarded item extends one in-memory
lost interval for its own stream (`FactIdentityKey` or event `(fact_type, Location)`) from the
earliest to the latest discarded `when`; a stream has at most one such merged interval, so this
metadata is bounded by the registered streams. When storage accepts writes again, the
`queue_overflow` boundaries are committed as stream-gap metadata (§4.4) in the same ordered batch
as, or before, the retained items of those streams. A historical read requiring an affected
stream over its lost interval is incomplete with reason `queue_overflow`; it never reports a
discarded transition or event as absent evidence, a zero count or continuous state. A crash
before those boundaries are durable is already covered by the unadvanced continuity watermark
(§4.4).

If the latest states and pending continuity metadata alone cannot fit after those two stages,
Layer 0 enters an exceptional **global overflow epoch**. One bounded global `queue_overflow`
marker replaces the pending per-stream loss markers and starts at the earliest known lost
instant, including an earlier start from a replaced marker. Layer 0 discards the oldest
remaining queued items, including latest states or individual boundaries if required, until
the queue including the global marker fits the budget; an oversized incoming item is discarded
immediately. Later losses extend the same epoch, never create an unbounded list of markers.
Every required stream is incomplete for a historical read intersecting this global epoch,
even if no item from that stream was dropped. The durable latest-value index cannot be used
as a current-state claim across the epoch. The live current index and short-term buffer remain
usable during the running process; the global gap changes historical proof, not HA admission.

**Global invalidation and per-key recovery.** The global opening records a baseline-invalidation boundary
at the coordinator instant and append position of the irreducible overflow, separate
from the earlier first-loss instant used for historical coverage. Every state key
requires a fresh acknowledged assertion after that invalidation boundary; no retained
older baseline is exempt merely because it postdates the first lost historical item. This validity is
Persistence metadata, separate from `HouseFact.how.available`: missing durable proof
does not make the live producer or device unavailable. Pending validity bookkeeping
uses the existing staged state-key/current-index inventory, not a second payload queue
or a growing list of recovery snapshots. A further irreducible loss of protected states
or continuity boundaries during recovery advances the invalidation boundary in the
same bounded global marker; seeds preceding that new boundary cannot validate the new
baseline generation. Invalidation is durable before or atomically with records that
rely on it. Closing a global gap never revives an invalidated older baseline.

**Progressive re-seed.** On storage recovery, the global opening boundary is acknowledged
before or atomically with retained facts, which keep their original order and timestamps.
A new complete HA intake establishes a `CycleInputBarrier` with valid source health
and an explicit current-cycle availability result for every staged binding. This is a
new read of HA's state, not a requirement for every device to report a new measurement:
Layer 2's existing source-validity rules apply. An undefined or expired source produces
`available=False`; the intake does not wait until every source is readable.

Over successive evaluation cycles, each owning producer can supply a fresh valid
current-state assertion for its key, including a genuinely unavailable assertion.
Only assertions that fit the available queue capacity are admitted as recovery baselines;
otherwise recovery of that key waits for a later fresh assertion. The coordinator must
schedule pending eligible keys fairly as capacity becomes available. It never assembles
all keys into another full snapshot or evicts ordinary queued facts just to admit an
unchanged recovery baseline. Changed facts retain ordinary admission/overflow semantics.
A lifecycle state requires its owner's current proof; HA active state alone cannot
recreate a managed episode, and an older stored fact cannot be copied and redated as
proof. Already retained pre-recovery facts remain historical records, not a replacement
for a fresh post-invalidation assertion.

A baseline is a complete producer-validated `HouseFact`, using that validation cycle's
instant and `AppendOrder`. Under §4.2 it may be written despite an unchanged live
fingerprint, through the same bounded queue, serialized writer and atomic per-cycle
transaction. No synchronous write, second queue or whole-re-seed transaction is added.
Queue admission alone does not recover a key: its baseline and validity metadata must
be durably acknowledged together. A failed or discarded baseline leaves the key pending.
A newer state assertion stays after an older seed in append order; a late acknowledgement
cannot roll the key back, and no latest assertion lost under a subsequent invalidation
can be certified by an earlier seed. An acknowledged unavailable baseline restores the
key's durable starting point but its stream remains unavailable under §4.4. A seed never
backdates knowledge across the preceding uncertain interval.

**Global closure.** The global gap may close before all state keys have baselines.
Choose a fresh complete HA intake barrier and the full append boundary of its
completed evaluation cycle, including later DAG facts that share its cycle instant.
Every accepted fact, audit item and continuity boundary through that full boundary
must be durably acknowledged or have its loss durably declared; the intake
`max_append_ordinal` alone cannot certify later same-cycle facts. Let B be the chosen full
append boundary (CA4-117). A failed write of an item at or before B, or the loss of such an item,
before the closure is durably committed leaves the global gap open and requires a new closure
attempt. The closing transaction starts only after every item at or before B is durably
acknowledged or has its loss durably declared, so no item at or before B remains in the queue and
later overflow can only discard items after B. A loss at an append position after B that occurs
before the closure is durably committed does not reopen or extend the closing epoch: it opens a
new global overflow epoch, with its own first-loss instant and baseline-invalidation boundary at
its own append position, even when ordinary per-stream overflow would otherwise suffice. Admission
never waits for the closing COMMIT. The writer persists the new epoch's opening boundary after the
closure record and before, or atomically with, any retained item after that loss position. Under
§4.4 the continuity watermark cannot pass the discarded item until that opening is durable. Persist the
closing boundary and its intake identity/accounting acknowledgement atomically, after
or with the ordered writes they certify. Ordinary cycle batches retain their own
`CycleCommitMarker` atomicity; the final boundary need not contain all recovery baselines.

After closure, event reads can regain complete coverage under §4.4 and state reads can
regain it independently for seeded keys. A state read requiring an unseeded key remains
incomplete with `queue_overflow` from the request's first intersecting uncertain instant
until a valid acknowledged baseline, even outside the now-closed global interval. Other
keys' unrecovered status does not affect it. Ordinary source unavailability still applies
and is not relabeled as storage loss. Durable validity survives restart. A crash before
the opening boundary is durable uses the unadvanced watermark/process-interruption rule.
This includes a crash after the closure COMMIT and before a subsequent epoch's opening is durable:
the database shows the older epoch closed, and the interruption gap starting no later than the
last durable watermark covers the later loss. A durable open gap stays open until a valid closure, and a crash after closure cannot
restore an unseeded key from pre-invalidation history. No recovery action changes the
live current index, short-term history, holds or §4.8 observers solely because storage
validity changed.

The short-term buffer (§4.1) and the live current index are not reduced by this policy, so
hot-path windows and current-state admission are unaffected. Discarding emits the
`durable_queue_overflow` diagnostic with per-stream counts and lost intervals; queue bytes,
budget and its source are always visible in diagnostics (§10). During a global epoch,
diagnostics expose its start, open/closed status and aggregate discarded counts without
requiring an unbounded per-stream list. They also count closures followed by a new epoch opened
before the closure was durable (CA4-117). A discarded hold-audit fact
follows the same rule as any other event: the live hold is unaffected and the audit stream
reports the lost interval.

### 4.7 Composed configuration generation

Every configuration mutation in any layer — a Layer-2 registry change (including the room
inventory attributes, Zones, `ZoneRoleBinding`s and Topology staged with it), a Layer-3 learning
definition, a Layer-4 semantic resolver definition, a Layer-5 Reaction configuration generation,
Reaction-catalog entry, guard-profile or prerequisite generation, and the Layer-6 generation (the availability publication
bindings that follow from them, plus notification recipients, house endpoints and family options) — activates only as part of one **composed configuration generation**. Runtime
authority transitions (promotion, consent, disablement), artifact-adoption and learning lifecycle
transitions, and the Layer-3 learning installation profile (applied at the next scheduling
boundary, Layer 3 §5.3) are not configuration mutations and do not use this path. Accepting a learned Reaction proposal is the one
governance command that creates configuration: it commits its new Reaction through this path as
one composed generation with an empty impact record (Layer 5 §4.1).

```python
@dataclass(frozen=True)
class LayerGenerationRef:
    layer: Literal["layer2", "layer3", "layer4", "layer5", "layer6"]
    generation_id: str
    definition_fingerprint: str

@dataclass(frozen=True)
class ComposedGenerationManifest:
    composed_generation_id: str
    previous_composed_generation_id: str | None
    layers: tuple[LayerGenerationRef, ...]       # exactly one per layer, canonical layer order
    impact_fingerprint: str                       # of the confirmed impact record, below
    invalidated_dependents: tuple[str, ...]       # canonical ids of consumers invalidated by this commit
    actor_ref: str                                # authenticated administrator or closed system actor
    effective_at: EvidenceInstant                 # cycle-clock instant of durable commit (§3.5)
```

**Staging.** A candidate is the active composition plus the edited definitions. Each layer
validates its own part against the candidate lower layers, using only its staged declarations.
Layer 0 builds a staging-only dependency index from those declarations: producer claims
(`FactTypeClaim` and `(fact_type, Location)`), Actuator channels and Layer-3 learning definitions
(identified by id and analysis-definition fingerprint, Layer 3 §4.1.2) on one side; every consumer
reference on the other — Fusion inputs, Layer-3 `FactSlot`/`SampleBinding` sources, Layer-4 input
bindings and upstream claims, Layer-7 extension input-slot bindings and analyzer learner bindings
(Layer 7 §3–§5), Layer-5 trigger, guard, envelope-axis, history, calendar,
timing-model and Actuator-channel bindings, every consumer of a derived Topology or Actuator property
(`opening_faces_exterior`, `weather_exposed`, thermal-envelope membership; Layer 1 §6.1/§7,
Layer 2 §6), and Layer-6 publication keys. Layer-6 recipients, house endpoints and family options have no
dependents: a change to them alone yields an empty impact record and needs no confirmation. A changed room enclosure, opening `other_side`,
`is_external` or zone-role binding therefore classifies every consumer of the derived property. It then classifies every consumer outside
the directly edited objects:

- **breaking** — its binding no longer validates against the candidate: missing producer or
  channel, changed claim kind, value type, unit, vocabulary or legal scope, or, for a timing-model
  binding, a missing learning definition or a changed analysis-definition fingerprint (a
  serving-, scheduling- or presentation-only learner edit leaves it unaffected);
- **semantic_only** — its binding still validates, but an upstream producer's execution semantic
  fingerprint changed;
- **unaffected**.

The canonical impact record lists every breaking and semantic-only consumer with its layer, id
and cause. `impact_fingerprint` is SHA-256 over RFC-8785 canonical JSON of the base composed
generation id, the candidate layer fingerprints and the ordered impact entries. Staging that fails
a layer's own validation is rejected as before and produces no impact record.

**Confirmation.** When the impact record contains any entry, the commit command must carry the
`impact_fingerprint` the administrator reviewed and the base `composed_generation_id`. A
different base generation or fingerprint rejects the commit without mutation; the administrator
receives a fresh preview. An empty impact record needs no confirmation. Rendering the preview and
issuing the confirmation are Layer-8 obligations.

**Commit and activation.** One durable atomic transaction writes the manifest, every new layer
generation record, the dependent invalidations that each owning layer defines (Layer 2 §2.5,
Layer 3 §4.1.2, Layer 4 §8, Layer 5 §4.2) and, for an accepted proposal, its review transition
(Layer 5 §4.1), or writes none of them. That durable write is the
activation: `effective_at` is its cycle-clock instant, and the engine swaps every layer's active
pointer together at the next cycle boundary. No cycle observes a mix of old and new layer
generations. Each produced fact carries its producer's generation fingerprint in `FactSource`, so
historical attribution never depends on `effective_at`. Work admitted under an older generation is
stopped by its own owner's guard: the Layer-5 dispatch fence rejects unsent calls of an
invalidated or superseded Reaction generation, and a Layer-3 run captured against an older
generation cannot publish.

**Configuration history.** Every committed `ComposedGenerationManifest` and every layer generation
record it references are retained indefinitely and remain readable by id. They are configuration
records, not `HouseFact`s, so fact retention (§4.3) never prunes them; their growth is bounded by
the rate of administrator commits. Reading a past generation is a slow-path query for the
administrative history and restore surface (Layer 8); it never affects evaluation, and only the
latest manifest is active.

**Restart and code upgrade.** Bootstrap loads the latest committed manifest and rebuilds every
layer through staging; an uncommitted candidate leaves no trace. If a code upgrade (a changed
formula, learning type, resolver kind, descriptor version or Layer-7 extension
`implementation_version`) makes part of the committed composition invalid, bootstrap applies the same impact classification and invalidations
automatically under the closed system actor, records a new manifest, and reports every
invalidated dependent as a diagnostic; there is no administrator to confirm at bootstrap.
If that manifest cannot be written, the invalid consumers are still excluded from evaluation in
memory, the write is retried, and a persistence diagnostic is raised; no invalid consumer runs.

### 4.8 Committed-state observers

A core component outside the evaluation DAG that must react when a house state changes (for
example Layer 6 waiting for the end of quiet hours) observes it through one generic Layer-0
mechanism instead of polling or a mirrored event fact.

```python
@dataclass(frozen=True)
class CommittedStateSubscription:
    subscriber_id: str                # registered core component, e.g. "layer6.quiet_hours"
    fact_key: FactIdentityKey         # exact state key; never a pattern, an event type or a scope query

@dataclass(frozen=True)
class CommittedStateChange:
    fact_key: FactIdentityKey
    fact: HouseFact | None            # the committed latest state; None if the key has none yet
    cycle_when: EvidenceInstant       # cycle instant of the commit that produced it (§3.5)
```

- **Closed and core-declared.** Only core components register subscriptions; administrators,
  learners and extensions cannot. A subscription names one exact state `FactIdentityKey`, never a
  pattern. A component declares its set at bootstrap, or derives it from the active composed
  generation (§4.7), for example one key per configured room. A derived set is re-declared
  atomically at the same cycle boundary as each generation swap: added keys receive their current
  value once after the first cycle under the new generation, removed keys stop receiving
  deliveries, unchanged keys keep their state. No subscription is added or removed at any other
  time. A key with no registered producer is accepted and simply never changes.
- **After the commit, never inside evaluation.** When a cycle's results become the in-memory
  current index (§4.2), Layer 0 schedules one delivery per subscription whose key changed
  fingerprint in that cycle, including a change of availability. Delivery runs asynchronously
  after the cycle; the cycle never waits for a subscriber, and a subscriber never sees a value
  that is not committed. It is not tied to durable persistence: a value waiting in the §4.6 retry
  queue is already the current state.
- **Coalescing and order.** Per subscription at most one delivery is pending; a newer change
  replaces the pending one, so a subscriber receives the latest committed state in cycle order and
  may miss intermediate values, never receive an older one after a newer one.
- **Initial value.** After the first cycle of a process run each subscriber receives the current
  value of its key once, whether or not it changed, so it never depends on history.
- **Failures.** A subscriber exception is isolated and diagnosed; it does not affect the cycle,
  other subscribers or later deliveries.

This is read-only notification of committed state. It writes no fact, creates no `HouseFact`
event, grants no authority and is not a dependency edge of the semantic DAG (§11).

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
    source_id: str                          # stable id within that kind, e.g. a Sensor or Fusion
                                              # registry id, an analyzer id, a reaction id
    source_type: str | None = None          # optional family, e.g. reaction type
    configuration_fingerprint: str | None = None  # resolved per-producer execution-semantic
                                              # fingerprint, assigned only by its active composed
                                              # generation; never accepted from an untrusted producer
    route_fingerprint: str | None = None   # stable contributing-input route for a trusted derived
                                          # producer; not the producer's configuration identity
    actor_type: FactSourceActorType = "heima"
    user_actor: UserActor | None = None     # required exactly when actor_type == "user"
    correlation_id: str = field(default_factory=lambda: str(uuid4()))  # see §5.2 — this default is
                                              # a safety net only, never relied on in production code
    # no actor identity in operational fact/action provenance; authenticated decisions retain
    # their attributable actor reference in the separate governance ledger

@dataclass(frozen=True)
class ApplyStepSource:
    kind: ApplyStepSourceKind               # a distinct closed action vocabulary; an action is never
                                              # kind="sensor"/"analyzer"/"extension"/
                                              # "semantic_resolver"
    source_id: str
    source_type: str | None = None
    configuration_fingerprint: str | None = None
    actor_type: FactSourceActorType = "heima"
    user_actor: UserActor | None = None     # required exactly when actor_type == "user"
    correlation_id: str = field(default_factory=lambda: str(uuid4()))

FactSourceKind = Literal[
    # fact-only — an action (ApplyStepSource) is never one of these four:
    "sensor",             # a direct read of one raw HA entity, interpreted (Layer 2 Sensor) — one
                            # entity in, one fact out, no combination
    "analyzer",            # derived from combining or analyzing existing data rather than one direct
                            # entity read — a same-cycle deterministic combination (Layer 2 FusionRule)
                            # or a structural match (Layer 5's Reaction-descriptor matcher). The unifying property is
                            # "derived from something other than a single direct entity read", not
                            # "statistical" specifically — FusionRule belongs here, not under "sensor"
    "extension",          # produced by a Layer-7 extension instance from its declared input
                            # slots (Layer 7 §5); fields assigned by the runtime (Layer 7 §6)
    "semantic_resolver",   # produced by a Layer-4 SemanticResolver's own resolution logic, not
                            # sourced from a Layer-2 Sensor/FusionRule directly
    # shared with ApplyStepSource — both a fact and an action can carry these:
    "reaction",            # a fact recorded as a byproduct of a Reaction firing (Layer 5) — distinct
                            # from the ApplyStep(s) the same Reaction issues, which carry
                            # ApplyStepSource with this same kind on the action side
    "admin_command",        # a direct consequence of an admin-panel command, assignable only after
                            # HA confirms the user is an admin (§5.1)
    "user_response",        # a direct consequence of a verified user response to an active
                            # response-ingress request (§5.1.3) or a matched direct Actuator control
                            # edge — two distinct boundary checks; see §5.1. The kind names the
                            # path; who acted is the separate `user_actor`
    "timeout",              # recorded because an expected response/confirmation window elapsed with
                            # nothing arriving — assignable only by the in-process timeout controller
    "recovery",             # produced by Recovery/Checkpoint itself (§7) — e.g. a recovery diagnostic after a restart (§6.3)
    "system",               # produced by system-owned runtime infrastructure not covered by a more
                            # specific kind above (e.g. a system-owned CronEntry's own bookkeeping)
    "test",                 # produced by test code — never present in production data
    "legacy",               # reserved only for offline/archive tooling examining V2 material; never
                            # admitted to V3 runtime data or produced by new code
]

ApplyStepSourceKind = Literal[
    "reaction",            # ordinary automatic policy action, authorized by Layer 5
    "admin_command",       # direct authenticated administrator panel command
    "user_response",       # verified user response/control action; who acted is `user_actor`
    "timeout",             # in-process timeout controller action
    "recovery",            # explicit recovery/reconciliation action
    "system",              # system-owned infrastructure action not covered above
    "test",                # test-only action; never production data
]

FactSourceActorType = Literal[
    "user",        # an authenticated Home Assistant user; who it is in the household is the
                    # separate `UserActor`, never an identity
    "physical",    # a manual control through a core-approved physical-control adapter (for
                    # example a wall switch): manual, but with no authenticated user and no identity
    "heima",       # Heima itself, autonomously — no human in the loop for this specific fact/action;
                    # the default
    "scheduler",   # Timing's own execution (an AtJob/CronEntry firing), not a semantic conclusion
    "service",     # an external HA service call not attributable to a specific user (e.g.
                    # an automation outside Heima calling into a Heima service)
    "system",      # Heima's own startup/runtime infrastructure (Recovery, Persistence), not a semantic resolver
                    # or a human
    "test",        # test code
    "unknown",     # could not be determined — never treated as authoritative for anything requiring
                    # a specific actor
]

HouseholdRole = Literal["resident", "guest", "none"]

@dataclass(frozen=True)
class UserActor:
    household_role: HouseholdRole   # from the user's classified Person (Layer 2 §2.8); "none" for a
                                    # user with no Person (a device account) or an unclassified person
    ha_admin: bool                  # HA's own administrator flag, an independent axis

ControlActor = Literal["resident", "guest", "device", "administrator", "physical"]
```

**Control actor.** Who performed a manual control is recorded as one coarse `ControlActor`, never an
identity, derived deterministically: `household_role="resident"` gives `resident` whatever the
administrator flag; `guest` gives `guest`; `none` with `ha_admin=True` gives `administrator` (a
non-resident administrator, for example an installer); `none` with `ha_admin=False` gives `device`
(an account with no Person, for example a guest-room tablet); a core-approved physical-control
adapter gives `physical`. Only `resident` and `physical` controls can be resident learning evidence
(Layer 3); every class can open a hold when the edge qualifies under §6.2.

**Two independent actor axes.** An authenticated user is described by its household role and by HA's
administrator flag, never by one combined category. Learning evidence and household authority
(consent, request answers, advisory feedback) read the household role; Heima configuration reads the
administrator flag. An administrator is not necessarily a resident (an installer or property manager
in a B2B deployment), and a resident is not necessarily an administrator. At every authenticated
boundary Layer 0 derives `ha_admin` from HA's own permission check and `household_role` from the
active Layer-2 `Person` whose stored `ha_user_id` matches the HA user, never from client data.
Layer 0 does not read the Person registry for this: at each composed-generation cutover Layer 2
pushes a frozen `ha_user_id -> household_role` projection, as it pushes Actuator policy for §7.4,
and the boundary resolves it with one O(1) lookup; an HA user absent from it has
`household_role="none"`.

One provenance taxonomy has two shapes with distinct closed fact/action kinds, never two
independently evolving designs. `ApplyStepSource` carries the action-side kind, source identity,
actor axes and correlation id, but no person/service identity. Authenticated user
authorization is attributable in the separate Layer-5 governance ledger, not copied into an
`ApplyStep`, execution audit or fact payload. A `correlation_id` links bounded operational
projections without becoming an authorization proof or an actor identifier.

### 5.1 Non-forgeability: trust is derived, never stored

There is no persisted or externally-writable "trusted" field. Whether a given `kind` is legitimate
is derived by the code at the boundary that assigns it, never read off the data itself:

- a configured reaction can produce `kind="reaction"`, but cannot declare itself `admin_command`;
- an admin-panel action can produce `kind="admin_command"` only after Home Assistant confirms the
  connection's user is an admin;
- a response can produce a source only after it arrives through the authenticated response
  ingress (§5.1.3), matches an active request of its registered owner and, for a recovery
  confirmation, passes the current-proposal recheck in §7.4.1. Its kind is always
  `kind="user_response"` (one of the two `user_response` boundaries), with `actor_type="user"` and
  the verified `UserActor`; an administrator answering a request is still a response, with
  `ha_admin=True`;
- an extension (Layer 7) can produce `kind="extension"`, but nothing it returns can
  make the core treat it as `kind="sensor"` or `kind="recovery"`.
- `configuration_fingerprint`, when present, is assigned only by the active composed generation; a
  producer cannot choose or retain one across a generation swap.

Source data arriving from persisted config, proposal payloads, imported data, or any
externally-controlled input is **non-authoritative** until a runtime boundary validates or
reassigns it — an untrusted or malformed source is sanitized into a clearly non-authoritative value,
never silently trusted. A Layer-7 extension is the stricter case: a returned source field or a fact
outside its declaration is a contract violation that fails the whole run, so nothing is sanitized
or written (Layer 7 §6, §8). Both `FactSource` and `ApplyStepSource` are redacted before
they reach diagnostics or storage (no secrets, tokens, or raw payloads retained).

### 5.1.1 Trusted manual-control edge

The other `user_response` boundary is a verified direct manual control of a registered logical Actuator channel.
At HA event ingress, before raw context is discarded, Layer 0 may emit the immutable event fact
`actuator.manual_control` only when all of these are true:

1. the edge addresses a Layer-2 registered `actuator_id` and its registered `controlled_channel`;
2. it changes that channel's valid observable physical state, rather than only availability or an
   unrelated entity attribute;
3. the edge is linked to a direct authenticated device command by any user (§5), whatever its
   household role or administrator flag, or to a core-approved physical-control adapter; a propagated HA user context, automation, integration, service, unknown context, or merely an entity state change is insufficient;
4. the edge has a fresh non-forgeable ingress identity and passes the ordinary duplicate filter.

The event is a Layer-1 event fact at the Actuator's registered `Location`, with
`FactSource.kind="user_response"`, `source_id=<actuator_id>`,
`source_type="actuator_control"`, and either `actor_type="user"` with the verified `UserActor` or,
for a core-approved physical-control adapter, `actor_type="physical"` with no `UserActor`. Its canonical value contains only
the internal `actuator_id`, `controlled_channel`, and non-forgeable `control_edge_id`; the
`HouseFact.when` is the observed edge instant. It retains no HA entity id, HA user identity, raw event
context, state payload, or service data. Its `ControlActor` (§5) follows from the provenance. The
event is evidence of someone operating a channel manually, not evidence that the operation corrected
Heima, and only a `resident` or `physical` control is resident evidence (Layer 3). Layer 5 alone compares it to a successful compatible
`ApplyStep` and may create the separately specified `actuator.correction` event (§6.1 of Layer 5).

This shares the Divergence Hold Manager's verified-origin ingress boundary; it introduces no
per-cycle poll, HA I/O, lookup over unregistered entities, or new persistent live-state table. A
physical/integration event without an authenticated user or approved adapter, including a typical dumb wall
switch that merely makes a smart bulb disappear, deliberately emits no manual-control event. A
future core-approved hardware provenance adapter may add a separately verified local-control boundary;
generic state divergence is never treated as that adapter.

### 5.1.1.1 Normalized observation edge and origin proof

The registered Actuator adapter extracts only versioned canonical channel facets from an available
HA state change. At ingress Layer 0 assigns a non-forgeable edge id, a per-channel process-local
observation epoch, and a strictly increasing revision. A transient immutable observation contains
that identity, the validated logical Actuator/channel/facet, canonical observed value and UTC time,
the evidence-based HoldOrigin (§6.1), and the closed origin proof class. All facets from
one HA change share the edge id and revision; duplicate changes do not receive a second revision.
Layer 5 consumes this normalized record for physical confirmation and later divergence (§6.0.1);
Layer 0 never reads Layer 2's registry or evaluates the action matcher itself. The record is not
a HouseFact; its bounded state projection below is. The separate
`actuator.manual_control` event above is emitted only for the verified
manual subset and keeps its exact three-field value.

**Durable channel-state projection.** Each registered channel has one distinct
state `fact_type`, `actuator.channel_state.<digest>`, where `<digest>` is the
full lowercase SHA-256 hex of RFC-8785 canonical JSON over the ordered
`[actuator_id, controlled_channel]` pair. Staging rejects a duplicate digest
or `(fact_type, Location)` claim. The resulting `FactIdentityKey` addresses
one channel even when several Actuators share a room. The core publishes
one available state at the first valid current-cycle observation and then
only on a changed canonical physical state, availability, or stable
observation-source fingerprint under §4.2. An identical HA report emits
neither an edge nor a new state fact. The value is the exact bounded
`ChannelStateValue`:

```python
ChannelStateValue = {
    "actuator_id": str,
    "controlled_channel": str,
    "observable_state_contract_id": str,
    "observed_facets": dict[str, str],  # all valid channel facets as canonical JSON text
    "changed_facets": list[str],  # sorted/unique, nonempty only for a physical change edge
    "control_edge_id": str | None,     # same id as the verified manual-control event, if any
    "origin": Literal["initial", "heima", "manual",
                      "external_automation", "external_integration", "unknown"],
}
```

The first valid observation after startup or an availability gap uses
`changed_facets=[]`, `control_edge_id=None`, `origin="initial"`; it proves
current state, not an intervention during the gap. A later physical edge
uses the exact normalized changed-facet set, non-forgeable edge id and
verified origin class from this ingress. The projected `HouseFact.when` is
the observation edge instant, or the first valid barrier instant for an
initial state. A durable-only re-seed after global queue overflow (§4.6) uses a fresh
validated current observation projected with `changed_facets=[]`, `control_edge_id=None`
and `origin="initial"` at its validation-cycle instant. It does not mint a physical
edge, change the live observation epoch/revision, emit manual-control/correction
or reset a live hold. A real newly observed physical change retains its ordinary
edge projection exactly once and can establish the baseline itself.
On unavailable input it emits `available=False`; its value is
undefined and no edge id or manual-control event is fabricated. If a verified
manual control changes the channel, the state fact and unchanged
three-field `actuator.manual_control` event share the same
`control_edge_id`/`HouseFact.when` and enter the same ordered cycle batch.
The edge id is a join key, never a proof of who acted by itself:
Layer 3 requires the separately claimed manual-control event and its `ControlActor`. An edge linked to
a Heima `ApplyCall` has `origin="heima"` and cannot join a manual-control event.
External/unknown changed edges remain visible as confounders without being
promoted to resident actions.
The first valid observation after a process restart is force-written for
each staged channel even if its old durable fingerprint matches; this
marks the new observation epoch after Layer 0 §4.4's process gap without
inventing an intervening control edge. It is one restart boundary record,
not a per-cycle confirmation.

The Layer-2 staged facet bounds and the Layer-5 lossless canonical JSON-text
codec apply to `observed_facets`. Every possible complete value must fit
Layer 1's depth-two/8 KiB limit; staging rejects an unbounded channel
projection before publication. No raw HA entity id, State object, service
data, user id, personal identity or unregistered attribute is retained.
The projection is a history source and read-only current observation; it
never authorizes an `ApplyStep`, restores a hold or asserts causal origin
from an unavailable transition. Layer 0 persists its state and the paired
manual-control event atomically in the ordinary end-of-cycle fact batch; a failed
batch/uncertain crash follows §4.4's incomplete-history rule.

A `manual` origin requires a matched authenticated device command or a versioned
core-approved physical-control adapter. A propagated HA user id or parent id alone is insufficient.
An automation or integration label requires its own verified execution/link; otherwise use unknown.
An edge linked to a Heima ApplyCall is tagged internally as Heima-originated and excluded from
external hold and manual-control attribution before the public HoldOrigin is assigned. No raw HA
context, personal identity, service payload, or full entity attributes are retained.

### 5.1.1.2 Durable managed-episode projection

A descriptor may opt into resuming an episode it physically started after a
process restart (Layer 5 §3.2). For each eligible `(actuator_id,
controlled_channel)`, Layer 5 emits one bounded `reaction.managed_episode.<digest>`
state fact, using the same channel digest and Location as §5.1.1.1. Its value
has exactly `status="open"|"closed"`, `reaction_id`,
`configuration_generation_id`, `reaction_activation_id`,
`opening_apply_step_id`, and `opening_edge_id`. An opening has all identities;
a closure retains the identities of the episode it closes. The edge id is the
verified physical transition linked to that ApplyStep, not a service-call
success or a target match produced by another actor. No endpoint, raw HA
state, actor identity, timer or target payload is stored. Layer 5 defines
when the state opens and closes; Layer 0 validates the bounded schema and
persists it as an ordinary state fact.

Opening or closure joins the ordinary ordered end-of-cycle fact batch (§4.2),
atomically with other accepted facts in that batch. There is no extra
per-command flush, journal, periodic refresh or write for a speed change.
Write-on-change emits only the opening and closure transitions; the latest
state record per channel is retained under §4.3, even after older event
history is pruned. A failed batch remains queued while Heima runs. A crash
before a committed opening leaves no durable proof; a malformed, absent or globally invalidated
projection likewise supplies no proof. The §4.6 per-key durable validity check
applies even when the global gap has closed; an HA active reading cannot
recreate the stored opening identity or certify an invalidated old marker.
A committed `open` value is only a
candidate for Layer-5 current-policy revalidation after restart, never an
independent command permission, restored activation, timer or hold. The first
fresh physical channel observation is required before that revalidation;
historical intervals crossing the process gap remain incomplete (§4.4).

### 5.1.2 Unavailability is an observation break

For every Actuator channel, `available=False` means the channel was not observable at that instant;
it never means `off`, a control edge, a resident response, a manual override, or a failed Heima
action. A loss of availability may be caused by a non-smart wall switch cutting power, a power outage,
network loss, device fault, or integration restart, and Layer 0 cannot infer which from the unavailable
state alone. A later available state likewise cannot reconstruct the channel's intervening state or
actions.

Layer 0 persists the channel's normal unavailable state transition under the
`actuator.channel_state.*` contract above (independent registered Sensors
retain their own claims), but emits
neither `actuator.manual_control` nor an implicit conclusion from that transition. Consumers that
need complete observation windows must treat an interval containing an unavailable channel as
interrupted rather than as a negative observation. In particular, a later count learner must mark a
post-`ApplyStep` target window with such an interruption as `censored_by_unavailability`, not as zero
resident corrections. Independent registered evidence, such as a power sensor upstream of the device
or a verified physical-control event, may state its own fact; it must never be fabricated from the
unavailable channel.

### 5.1.3 Authenticated response ingress

A person answers an actionable notification (for example "approve" or "dismiss") through one
generic Layer-0 ingress; there is no per-request-type response path. Layer 6 only carries the
answer from its delivery channel to this ingress and never interprets it.

```python
@dataclass(frozen=True)
class ResponseRequestDeclaration:
    request_id: str                   # core-minted, unguessable, unique across process runs
    owner_id: str                     # registered response owner
    allowed_actions: frozenset[str]   # closed per owner, e.g. {"approve", "dismiss"}
    admitted_actors: frozenset[Literal["resident", "admin"]]  # "resident": household_role ==
                                      # "resident"; "admin": ha_admin; either suffices
    expires_at: EvidenceInstant | None  # None: open until the owner withdraws it

@dataclass(frozen=True)
class VerifiedResponse:
    request_id: str
    owner_id: str
    action: str
    actor: UserActor                  # both verified axes (§5)
    actor_ref: str                    # for the owner's governance record only
    ingress_id: str                   # non-forgeable, deduplicated
    received_at: EvidenceInstant
    correlation_id: str
```

The frozen `ResponseOwnerRegistry` is closed to administrators, learners and extensions. Initial V3
registers three owners: `layer0.recovery_confirmation` (§7.4.1), `layer5.household_consent` and
`layer5.advisory_feedback` (Layer 5 §6.0). A later owner, such as proposal review or disabling an
automation from a notification, needs its own reviewed registration. An owner declares each request when it
becomes actionable and withdraws it when it closes; `expires_at=None` declares a request that ends
only by withdrawal (a household consent request, advisory feedback), while a recovery confirmation
declares its 24-hour deadline (§7.4.1). Only a currently declared, unexpired request
accepts a response.

At ingress Layer 0 verifies the Home Assistant user through HA's own authentication, derives its
`UserActor` (§5: `ha_admin` from HA's permission check, `household_role` from the matching Layer-2
`Person`), sets `actor_ref` to that HA user id, assigns a fresh non-forgeable `ingress_id`, mints the
causal `correlation_id` (§5.2), and drops a duplicate report of the same ingress. It then rejects an
unknown, withdrawn or expired `request_id`, an action outside `allowed_actions` and an actor matching
none of `admitted_actors`, all without calling the owner. A guest or a user with no `Person` is
admitted only through `"admin"` when it is an HA administrator. Only a fully verified
`VerifiedResponse` reaches the owner, which alone decides the outcome under its own contract (for a
recovery confirmation, the compare-and-swap and the last-resort rule of §7.4.1). The actor reference
reaches only the owner's governance record; operational facts and `ApplyStep`s carry only the
`UserActor` (§5). A request id, action or response arriving by any other path is never a response.
Rejections are diagnostics.

The two axes are independent: one person may be an administrator and a resident, an administrator may
be a non-resident (B2B), and a resident may not be an administrator. An owner applies any narrower
rule itself (for household consent, membership of `HouseholdConsentAuthority`, Layer 5 §7.1.1; for a
recovery confirmation, the last-resort rule for a non-resident administrator, §7.4.1). The Initial-V3
owners admit: `layer0.recovery_confirmation` `{"resident", "admin"}`; `layer5.household_consent`
`{"resident"}`; `layer5.advisory_feedback` `{"resident"}`.

### 5.2 `correlation_id`: generation and propagation

A `correlation_id` is what makes "why is the house in this state" answerable — following one id from
a resolved state back through the facts that fed it, and forward to any action that resulted. It is
an opaque string minted **once**, at a well-defined origin point, and propagated unchanged to
everything causally downstream of that origin within the same causal chain — never regenerated by
an intermediate step. Origin points:

- **A per-cycle evaluation**: one `correlation_id` is minted at the start of each engine evaluation
  cycle and propagated to every `HouseFact` (Layer-2 sensor/fusion output, Layer-4 semantic claim),
  every `InferenceSignal` emitted in that cycle (Layer 3 §6.3) and every `ApplyStep` (Layer 5)
  produced synchronously within that cycle.
- **A Layer 3 learning analysis run**: `PatternLearner.analyze()` runs on its own slow cycle, mining
  potentially days of history spanning many prior `correlation_id`s — it is a new causal origin, not
  a continuation of any one of them, so it mints its own fresh `correlation_id` for whatever
  artifact, `ResultEnvelope`, `DiagnosticFinding` or `LearningProposalCandidate` it produces (none
  is a `HouseFact`, Layer 3 §2). That output's evidence references the
  `fact_type`/`Location`/time-window query used to mine it, so the chain is still walkable backward
  to the source data, even though the relationship is many-to-one rather than one-to-one.
- **An admin or resident action** (accepting a proposal, directly controlling a device, or
  responding to a runtime confirmation): a new `correlation_id` is minted at the verified ingress
  boundary. A hold transition caused by the observed device edge inherits that causal id; it does
  not become a separately authorized resident action. The recorded origin category remains
  evidence-based (§6.1).
- **A Layer-7 extension run** (Layer 7 §7): it runs off the cycle from earlier committed inputs, so,
  like a Layer-3 analysis run, it mints its own fresh `correlation_id` at run start; every fact it
  returns carries that id in its runtime-assigned `FactSource`, and later cycles that read the fact
  carry their own cycle id.
- **A Recovery-driven event** (§7), including a recovery diagnostic after a restart (§6.3): mints
  its own new `correlation_id` with `kind="recovery"`; no pre-restart hold chain or active
  identity is continued.

The dataclass-level default (a freshly generated id per instance) exists only as a safety net for
objects constructed outside a tracked causal chain (tests, ad hoc tooling). Production code paths
must do two things explicitly, never rely on the default to "just work" for either: mint a genuinely
new `correlation_id` at each origin point above, and then explicitly propagate that same id,
unchanged, to everything causally downstream of it within the same chain (corrected 2026-09-08 — an
earlier version of this sentence said the opposite of the first half, "pass down an *inherited*
correlation_id at every one of the origin points," when an origin point is, by this section's own
definition, precisely where there is nothing to inherit *from*).

---

## 6. Divergence Hold Manager

A hold is internal runtime state for one or more valid differences between confirmed,
current admitted Reaction targets and later observations of the same registered Actuator channel.
The physical value may have been produced by Heima or another actor; its observed origin is
retained independently of the Reaction target. A standalone direct-admin or recovery-only
ApplyStep has no continuing Reaction target and does not create a hold anchor. One observation that
changes several facets creates one hold episode, not one hold per facet. Residents use
the ordinary Home Assistant controls for that device; there is no hold helper, proxy switch,
manual-hold service, or separate resident workflow. A hold does not assert that a resident acted.
The verified origin of the observed change is recorded separately from the fact that a difference
exists. Layer 0 owns hold lifetime and its frozen admission view. Layer 5 owns the command target,
facet normalization, physical-confirmation matcher, and pending-apply reconciliation
(Layer 5 §6.0.1); it submits normalized per-facet expectation and observation transitions to this lower-layer manager.
Layer 0 never reads a Layer-5 registry or a raw Home Assistant state to infer an expected target.

### 6.1 Identity, origin, and lifecycle

The key is `(actuator_id, controlled_channel)` under the committed Actuator generation: at most
one active hold exists per channel. It carries a nonempty canonical set of currently divergent,
confirmed facets, one origin trail, and one release boundary. A later valid differing edge may add
a facet or update an already divergent facet, but never extends the original fixed deadline or
advances the original next-step boundary. A converged or superseded facet leaves
the set; the hold ends when the set becomes empty under the applicable event
reason. The location is the registered Actuator location for audit, not admission.
The earlier domain/location-wide scope and explicit/implicit distinction are superseded.

The administrator may optionally select `changed_facets` scope for a channel only when its core
actuation adapter declares complete, deterministic affected-facet sets for every allowed command;
otherwise the staged scope is `channel`, which is also the default. The administrator does not
configure individual actions, facet lists, or a user-facing hold control. A versioned core
Reaction descriptor selects `fixed_duration` or `next_reaction_step` release for its confirmed
target. `next_reaction_step` is available only when that descriptor provides a stable identity for
future timed or event-selected steps of the same Reaction and a versioned normal-exit contract for
verified cancellation or exhaustion; ordinary re-evaluation and ordered `ApplyStep`s in one
current bundle are not future steps. The release mode and scope are frozen into the hold at
activation. Layer 5 §6 defines admission and step recognition.

```python
HoldOrigin = Literal[
    "manual", "external_automation", "external_integration", "unknown",
]
HoldOriginProof = Literal[
    "direct_authenticated_command", "approved_physical_control",
    "automation_execution", "integration_link", "none",
]

@dataclass(frozen=True)
class HoldAdmissionEntry:
    actuator_id: str
    controlled_channel: str
    hold_id: str
    release_owner_activation_id: str
    divergent_facets: tuple[str, ...]  # canonical nonempty set
    scope: Literal["channel", "changed_facets"]
    expires_at: EvidenceInstant | None  # None for next_reaction_step

@dataclass(frozen=True)
class HoldAdmissionView:
    entries: tuple[HoldAdmissionEntry, ...]  # canonical key order, unique key
    actuator_generation_fingerprint: str
    fingerprint: str

@dataclass(frozen=True)
class HoldLifecycleValue:
    operation_id: str  # unique per admitted transition; stable on queue retry
    hold_id: str
    actuator_id: str
    controlled_channel: str
    divergent_facets: tuple[str, ...]  # state after transition; empty on terminal transition
    event: Literal["activated", "updated", "converged", "expired", "released", "invalidated"]
    release_reason: Literal["next_reaction_step", "reaction_cancelled",
                            "reaction_completed"] | None
    invalidation_reason: Literal["observation_lost", "configuration_changed",
                                 "authority_revoked", "removed_or_rebound",
                                 "expectation_superseded"] | None
    scope: Literal["channel", "changed_facets"]
    release_mode: Literal["fixed_duration", "next_reaction_step"]
    expires_at: EvidenceInstant | None  # original deadline; absent for next_reaction_step
    reaction_id: str  # release owner, fixed when the hold opens
    reaction_generation_id: str  # release-owner generation
    reaction_activation_id: str  # release-owner activation, fixed when the hold opens
    anchor_step_id: str | None  # None for a fixed-duration Reaction
    anchor_target_fingerprint: str
    origin: HoldOrigin
    origin_evidence: HoldOriginProof  # closed proof class; "none" exactly for unknown
    manual_actor: ControlActor | None  # §5; set exactly when origin == "manual"
    observation_context: Literal["normal", "after_observation_break"]
    expected_values: dict[str, str]  # facet -> bounded canonical JSON text
    observed_values: dict[str, str]  # current or last known before break; same facets
    expectation_reaction_ids: dict[str, str]  # facet -> admitted Reaction id
    expectation_generation_ids: dict[str, str]  # facet -> Reaction generation
    expectation_activation_ids: dict[str, str]  # facet -> Reaction activation
    expectation_target_fingerprints: dict[str, str]  # facet -> confirmed target
    expectation_step_ids: dict[str, str]  # facet -> confirmed planned step, if any
    expected_fingerprint: str
    observed_fingerprint: str

```

The origin is assigned at ingress from verified causal evidence, not guessed from the state value,
time, location, or a propagated HA `user_id` alone. `manual` requires a
matched direct authenticated device command or a separately approved physical-control adapter, and
records who acted only as its `ControlActor`: how a change happened (origin) and who made it
(`manual_actor`) are separate fields;
an automation descendant of a user action is not that direct command. `external_automation`
requires a verified automation execution or service-call link; `external_integration` requires a
verified integration link. Heima's own pending or completed command is excluded before origin
classification. If no such proof exists, the origin is `unknown`, and the hold still applies.
The proof class is direct_authenticated_command for a matched authenticated user call,
approved_physical_control for a core-approved physical adapter, automation_execution for a
verified automation link, integration_link for a verified integration link, and none only for
unknown. Neither the live view nor durable audit retains a personal identity, raw HA context,
full HA entity state, or service payload. The two value maps are copied canonical
scalar projections, never raw HA state or arbitrary attributes. Each map value
is the RFC-8785 canonical JSON text of the target contract's normalized facet
value, under the shared codec and facet-key grammar of Layer 5 §6.0. It is a
string in the audit payload even when the physical facet is a number, boolean,
array or object; parsing the text recovers the same normalized value. The
complete dataclass is normalized and validated as an ordinary Layer-1 §3
`HouseFact.value`, including depth two and 8 KiB.
The first four expectation-source maps have exactly the canonical facet keys of
both value maps; `expectation_step_ids` has a subset of those keys and includes a
key only when that confirmed expectation came from a planned step. They identify
the confirmed expectation used for this transition, including its previous source
when a facet is removed after that expectation is superseded. An observation
cannot invent a step id. Every source map is canonically ordered by facet name,
contains only copied scalar ids/fingerprints, and is bounded by the registered
facet set and normalized adapter contracts. At staging, the core computes the
maximum canonical UTF-8 bytes and collection depth of the *complete*
`HoldLifecycleValue` for each permitted channel adapter/scope and the full
staged set of Reactions that may confirm facets on that channel. The
calculation includes mixed-Reaction transitions, every transition kind, the
largest allowed facet set and source maps, optional step ids, longest closed labels,
canonical timestamps, and enforceable maximum RFC-8785 escaped JSON byte
lengths on every variable id,
facet name and facet-value text. Generated ids and fingerprints have fixed
length; registry/configuration ids must declare a finite accepted length.
If any maximum cannot be proved, or a possible value exceeds depth two or
8 KiB, staging rejects that composition atomically. A change to an adapter,
facet contract, identity bound or any contributing Reaction generation repeats the proof before
cutover. No accepted audit is truncated to fit. The runtime validator checks
the actual complete value again; a violated staged bound is an explicit
producer diagnostic, never permission to weaken a live hold (§6.4).
The top-level Reaction and activation fields name the first hold's release
owner, even when a later transition's facet source belongs to another Reaction.
An `updated`
transition caused solely by target supersession retains the last verified
observed-change origin and last known observed values; it does not claim a new
manual edge. On an
observation-break invalidation, the observed values are explicitly the last known values, not a
claim about the newly unavailable device. `invalidation_reason` is required only for
`event="invalidated"`; `release_reason` is required only for `event="released"`; otherwise
those reasons are None. Every transition has its own operation id, including an update that adds
a facet to the same hold. The origin category is evidence about
*how the observation arose*, never a resident authorization or a reason to vary the hold's
blocking effect.

Every admitted lifecycle change submits one complete typed transition and fact
metadata to the ordered asynchronous audit queue, subject to §6.4's write-failure
and invalid-payload diagnostics. The writer produces exactly one event `HouseFact`
with `fact_type="manual_hold.lifecycle"`, `value=HoldLifecycleValue`, and the Actuator's registered
`Location`. Its `FactSource` is the Manager (`kind="analyzer"`, `actor_type="heima"`) for activation,
update, convergence, release, and invalidation, or `kind="system"`, `actor_type="scheduler"` for scheduled expiry. Here `analyzer` identifies
the Manager's derived comparison of a confirmed expectation with a later observation; it
does not classify the actor who changed the device. The stable `manual_hold.lifecycle`
identifier names internal intervention history and makes no claim of resident action;
`origin` and its proof carry that separate attribution.
The event carries a fresh transition operation id distinct from its causal `correlation_id`;
retry of the same operation cannot append it twice. There is no current-state `manual_hold.<domain>` fact:
the generic `FactIdentityKey(fact_type, Location)` cannot identify multiple held channels in one room.
The in-memory association and its frozen `HoldAdmissionView` alone authorize live admission.
Historical event facts are audit/learning evidence, never a way to reconstruct an active hold.

### 6.1.1 Frozen admission view

Before each decision input barrier, the Manager publishes a deeply immutable view. `fingerprint` is
SHA-256 of RFC-8785 canonical JSON over the ordered entries and Actuator-generation fingerprint;
actor identity and origin are excluded because they do not change admission. Layer 4 transports
this view opaquely in `DecisionSnapshot`; Layer 5 uses only that snapshot for a decision and never
reads a newer mutable table. A configuration cutover invalidates entries whose Actuator identity, channel, scope, release
policy, affected-facet contract, or authorized expectation changed. It emits `invalidated` for each in canonical key
order and publishes a new view before another automatic admission. An unresolvable Actuator key
fails admission at the Layer-5 validation boundary rather than being treated as disjoint.

### 6.2 Detection and release

Layer 5 submits all qualifying confirmed-facet changes from one normalized observation as
one atomic channel transition; it never calls the Manager once per facet for that observation.
A divergence qualifies only when the channel/facet is registered and
currently observable; its current admitted Reaction target was physically confirmed during the present
uninterrupted runtime observation epoch; the current valid observation differs under the versioned
core matcher; the observation is a new, deduplicated state edge after that confirmation; and it is
neither a Heima-originated command nor an observation still being reconciled under a pending apply.
Layer 0 checks the submitted Actuator/generation key and release contract before activation;
only `fixed_duration` requires a configured positive `Window`. A command with completed HA service calls but no physical confirmation by its deadline has an
`unconfirmed` execution outcome under Layer 5's pending-apply contract, not a hold or a claimed
resident correction at that deadline. Partial confirmation establishes expectations only for the facets actually
confirmed. After a terminal pending timeout, a fresh valid read matching a facet of the still
authorized recorded target may establish a current expectation for that facet without revising
the terminal execution outcome. Only a later distinct differing edge may activate its hold. A
timeout or unavailable state alone never activates a hold.

The Manager mints one hold id on the first qualifying edge. It copies the
release owner's current `reaction_activation_id` into the live entry and audit;
that id never changes when another facet joins. For `fixed_duration` it arms one
`AtJob` at that instant; for `next_reaction_step` it retains the originating Reaction/generation/activation
and the confirmed target/step identity supplied by Layer 5. One qualifying observation may add
several divergent facets in one `activated` transition. A later distinct valid edge on the same
channel updates the observed fingerprint, verified origin and divergent-facet set in one `updated`
transition; it never extends or replaces the shared boundary. Under selective scope, a later
facet whose confirmed expectation came from a different Reaction still inherits the first hold
anchor if it becomes divergent while that channel hold is active. Layer 5 supplies
the five expectation-source maps for the facets involved in that transition,
including a mixed-facet observation; Layer 0 validates matching keys and retains the first hold's
Reaction/generation/activation, step and release boundary. The observed-change origin and
the source of the expected value remain separate. A later Reaction's step cannot
release the first Reaction's hold. There is no second concurrent hold on the
channel. A duplicate does nothing. This is
intentional: a facet first changed just before expiry receives only the remaining interval.
Convergence removes matching facets in one `updated` transition while some remain; only
complete physical convergence emits `converged` and ends the hold. When a
non-owning Reaction activation's confirmed target for a held facet is no longer current,
Layer 5 reports the committed supersession or loss of that expectation. Layer 0
removes only its affected facets, with one `updated` transition if other divergent
facets remain; it preserves the opening Reaction's release owner and boundary.
If this empties the set without physical convergence, it emits `invalidated` with
`invalidation_reason="expectation_superseded"`. A due candidate step alone, before
Layer 5 establishes that the earlier admitted target is no longer current, does
not remove a facet. A replacement target must pass ordinary admission and
physical confirmation; only a later distinct edge can diverge from it. Fixed expiry emits
`expired` and releases all remaining facets. Release acknowledges the current observation revision:
the unchanged mismatch cannot immediately create a new hold; another qualifying edge is required.
Loss of observation, removal/rebinding, revocation of the release owner's
expectation, or a semantic configuration change emits `invalidated` and releases
the hold; loss of a non-owner expectation follows the facet rule above. A newly authorized target is not treated as a divergence until Heima has recorded the admitted
target decision and confirmed its expected facets from a valid observation; an
`already_satisfied` decision can do so without sending a command. Each transition updates the
live table before the next frozen view;
durable audit completion is never a prerequisite for an in-memory safety decision.

For fixed release, the duration is one explicit positive `Window` in the staged Actuator
configuration, shared by every fixed-duration channel on that Actuator. Each channel hold arms
its own deadline from its activation instant; the shared duration does not merge those deadlines.
It cannot come from an observation source or historical inference. Layer 0 uses Timing's
monotonic `AtJob`, never resumed after restart. For next-step release, Layer 5 reports
the first later timed or fresh-event-selected step of the *same Reaction,
generation and activation on the same channel* whose canonical target differs.
An event-selected step must carry the staged typed current-snapshot boundary
and stable planned-step identity; a past event cannot be replayed to release
a hold. Layer 5 may report it as release-capable only when its descriptor
declares a typed continuation condition for the fresh post-release snapshot;
failure of that condition admits no later command. Layer 0 rejects a step
from an earlier or later activation, even under the same configuration
generation. This releases the entire hold via Layer 5's preliminary non-command result and a fresh
frozen snapshot before ordinary guard/admission checks, even if those checks then prevent
the new command. A normal re-evaluation or another current-bundle
member is not such a step. A programmed change to any target facet on that channel releases the
whole hold, even when the resident changed a different facet: the later full target may restore
that earlier facet. This tradeoff is explicit, not a hidden per-facet exception. A
Layer-5 `ReactionNormalExitResult` proving normal cancellation or natural
completion of the *owning activation* without another step also releases its
hold. Layer 0 checks Reaction, generation and activation against the fixed
release owner and rejects a terminal result from any other activation.
Finishing an individual `ApplyStep` or one-shot bundle is not a normal
exit. A valid, exhausted step stream is completion only when the versioned
descriptor contract verifies no later step and no ongoing target; temporary
source unavailability is not. Both terminal outcomes share the
default exit behavior: no restore command, leave the observed device state, and produce
a typed Layer-5 follow-up occurrence for Layer-6 event production when the last
confirmed target still differs from the observed state or observation is unavailable
(Layer 5 §6.0). A versioned core descriptor may
instead specify a final target. For a normal cancellation request, Layer 5 releases the hold,
obtains a fresh snapshot, and attempts that terminal action under still-current authority,
guards, arbitration and physical verification before closing the activation.
A blocked or unconfirmed final action does not prevent that closure; Layer 5
reports the actual observed state through that same operational event path.
Pending observation after closure cannot cause another call from that activation;
the configured Reaction remains eligible for a later qualifying start.
Administrative disablement and consent revocation of the release owner remain
immediate, invalidate the whole hold, and admit no terminal call after revocation;
loss of a non-owner expectation follows the facet-only rule above. Temporary unavailability
of next-step data is not cancellation or completion and does not invent a release event.
Only Layer 5's validated normal-exit result applies the exit behavior; an
invalid or unreadable program alone does not prove it ended. An indefinitely
constant Reaction cannot offer `next_reaction_step` as its release mode. There
is no implicit timer fallback.

### 6.3 Restart and observation breaks

Every process restart starts with an empty live hold table. A checkpoint, journal, or historical
`HouseFact` never restores a hold. The first valid observation after HA/Heima restart, confirmed
power recovery, or an availability gap establishes a new observation epoch and is not itself a
manual-control edge or hold cause. A difference between that reading and the last pre-restart
expectation may be displayed on Layer 0 §10's existing non-authoritative diagnostic surface,
alongside the current RecoveryState and the known observation break. It is not a
`HoldLifecycleValue`, a hold lifecycle `HouseFact`, or checkpoint state; it creates no new
diagnostic type or persisted event. Its cause remains unknown, is not attributed to a resident,
and does not block normal current-policy evaluation. Heima may issue the newly authorized current
target through the ordinary Layer-5 admission and recovery rules. A power-on default for a bulb
receives the same treatment. There is no claim about what occurred while power or observation was
absent. A hold active before an observation break is invalidated; the first returned value cannot
continue it or create another without a newly confirmed expectation and later edge.

### 6.4 Audit ordering and failures

The live table is process-local. Each lifecycle transition mints a unique opaque
operation id before updating the table, stores it in `HoldLifecycleValue`,
and reuses it on every queue retry. The producer copies the complete typed
transition, its facet-source maps and frozen `where`, `when`, `how` fact
metadata; it validates the normalized value against Layer 1 §3 and retains
canonical bytes at acceptance, without any mutable caller-owned map
reference. The accepted value is the deeply immutable Layer-1 form, shared by
the buffer, queue and readers; no reader can mutate the queued audit fact. A validated transition enters the ordinary
short-term event buffer and ordered asynchronous durable queue at its
original append order and time. Live hold admission updates independently
of durable acknowledgement and never reads audit history.

Staging has already proved that every admitted adapter/scope/Reaction
combination can produce a complete inline `HoldLifecycleValue` within
Layer 1's depth-two and 8 KiB limits (§6.1). The actual runtime value is
checked again. If an implementation violates that bound or supplies an
invalid shape, it reports a producer-contract failure and does not publish
a malformed or truncated fact. The live hold still takes effect; it is not
cleared or bypassed merely because its audit could not be constructed.
The producer records the attempted transition instant as an in-process
continuity blocker: the §4.4 watermark cannot advance past it, and a
historical read requiring lifecycle audit reports
`required_stream_unavailable` from that known instant. If the process crashes,
the last acknowledged watermark conservatively opens the interruption.
The gap is visible in diagnostics and historical continuity, never
interpreted as proof that no hold existed. An invalid value cannot enter
the ordinary retry queue.

The in-memory admission index coalesces an exact repeated operation id
only after comparing the complete canonical fact payload; a mismatch is
rejected immediately without disk I/O. The index covers queued or
in-flight events and drops an entry after durable acknowledgement. The
background writer enforces a durable unique key on
(`fact_type="manual_hold.lifecycle"`, `operation_id`) and compares
complete canonical payloads on a collision: an exact retry retains one
fact, while a changed payload is a diagnostic failure. This durable
check runs outside evaluation. Equal causal `correlation_id` values do
not deduplicate independent transitions; one multi-facet observation
creates one transition and operation id, while two distinct transitions
receive different ids.

A durable write failure leaves the live hold effective and exposes
`durability_pending` until retry; it never turns the failed write into
permission to act. A crash can lose queued but unwritten audit, so history
consumers use the known process/observation break rather than infer
uninterrupted hold state from the last event. The §4.4 continuity
watermark waits for this audit fact's durable acknowledgement; if §4.6
discards it, the watermark may pass its instant only after the
`queue_overflow` boundary declaring its loss is durably acknowledged.
That acknowledgement resolves the lost queue item for watermark
accounting, never certifies the audit fact as written or the affected
history interval as complete. A fact that failed construction above
remains a continuity blocker and has no queued-item overflow branch.
No hold checkpoint update or hold-specific `fsync` is required because
no live hold or identity is restored.

## 7. Recovery / Checkpoint

A lightweight, pre-DAG context computed once per evaluation cycle, before any semantic resolver runs. It
classifies runtime state and makes that classification available, **read-only**, to the consumers
that declare it — Layer 5 through `FrozenRecoveryView` (§7.4) and the hold observation boundary
(§6.3) — so behavior can be conservative and explainable right after a restart or during a partial
outage. Layer-4 semantic resolvers do not receive it (§11).

### 7.1 Cycle-level classification

```python
RecoveryState = Literal[
    "normal",                    # nothing unusual
    "startup_recovery",          # Heima just started; too early to trust anything yet
    "power_recovery",            # evidence of an actual power loss/restore, not just a process
                                   # restart (e.g. a configured UPS/power sensor, or a gap pattern
                                   # across many entities consistent with a power event)
    "degraded_recovery",         # many members of the recovery observation set are unavailable
    "recovery_settling",         # transitioning back toward normal after one of the above
]

@dataclass(frozen=True)
class RecoveryObservationMember:
    member_key: str              # canonical key: a Layer-2 sensor_id, or
                                 # "<actuator_id>/<controlled_channel>"
    kind: Literal["sensor", "actuator_channel", "power_evidence"]

@dataclass(frozen=True)
class RecoveryObservationSet:
    generation_id: str
    members: tuple[RecoveryObservationMember, ...]   # canonical order; at most one power_evidence
    fingerprint: str
```

**Which entities count is declared, not inferred (CA4-151).** Layer 0 does not know what a fact
means, so it never decides which entities are critical. At each composed-generation cutover Layer 2
pushes one frozen `RecoveryObservationSet` (Layer 2 §2.5): every Actuator channel whose
`power_recovery_policy` is not `"never"`, every Sensor declared `recovery_observation="observed"`,
and at most one boolean Sensor declared `"power_evidence"`. Layer 0 never reads the registry for
it. The set replaces a hand-curated allowlist: §7.2 and the §7.3 checkpoint use exactly its members.

**How the state is computed is a core mechanism, blind to meaning.** It uses only each member's
`available` and time. With `S` the current set and `U` its members currently unavailable (a member
without a fresh read since the process started counts as unavailable), the Initial-V3 core rules,
versioned like every core-fixed bound and to be recalibrated after live inventory with a new core
contract version, are:

| State | Entered when | Left when |
|---|---|---|
| `startup_recovery` | every process start | every member of `S` has its first fresh post-start read, or 60 s have elapsed; then the rules below apply |
| `power_recovery` | after startup, the `power_evidence` member reports an off-to-on transition during the downtime, or, without one, at least 50 % of the members that have a checkpoint baseline are unavailable or differ from it at their first read | the episode is confirmed and its id minted (§7.4); then `recovery_settling` |
| `degraded_recovery` | at any time, `|U| >= max(2, ceil(0.5 * |S|))` | the condition no longer holds; then `recovery_settling` |
| `recovery_settling` | on leaving any of the three states above | `normal` after 120 consecutive seconds without the degraded condition and without an availability transition of any member |

An empty `S` never enters `degraded_recovery` or the pattern form of `power_recovery`. A member that
stays unavailable without further transitions does not block the return to `normal`; per-consumer
gates (a fusion's `min_available`, a channel's readability for §7.4) handle its own consumers.
Layer 0 keeps `|U|` and the last member transition instant incrementally at intake, so the
per-cycle classification is O(1). A generation swap re-evaluates the rules against the new set.

### 7.2 Entity-level classification

For each member of the recovery observation set (§7.1) whose state differs from the last checkpoint
after a restart, Recovery attaches one of:

- **`unknown_during_downtime`**: the difference's cause cannot be determined — it may be a
  power-restore artifact, a manual action during downtime, or device behavior. Never treated as
  evidence *for* anything; it exists to be honest about uncertainty, not to resolve it.
- **`power_restore_candidate`**: the difference plausibly matches the entity's known power-on/reset
  behavior (e.g. a light or switch returning to a default state when power is restored).

Both labels, and the cycle-level states `power_recovery`, `degraded_recovery`, and
`recovery_settling`, identify observation ambiguity for consumers; they never establish an offline manual action or restore a hold (§6.3).

### 7.3 Checkpoint mechanics

Backed by a deliberately minimal checkpoint: only the members of the recovery observation set
(§7.1), each as its bounded redacted projection copied into one `PersistedProjection` per member,
and persisted to disk. A candidate
critical-entity projection that is not representable within that contract is omitted from that one
checkpoint commit and emits a diagnostic; it never causes raw HA data to be retained or invalidates
the rest of the checkpoint. At recovery, an entity without a usable prior projection has no baseline
and is treated conservatively as unknown, never as evidence that nothing changed. The checkpoint is
written:

- **periodically**, by one system-owned `IntervalRecurrence(interval=Window(seconds=60))` (§3.1), since Recovery
  consumes Timing's execution primitive like everything else that needs periodic work. The callback
  performs a checkpoint replacement only when the checkpoint is `dirty` (a critical-entity projection,
  recovery target, or checkpoint-owned recovery field changed since the completed commit); otherwise
  it performs only an O(1) dirty-flag check and no disk I/O. A failed replacement leaves the flag set
  for retry and emits the ordinary persistence diagnostic;
- **immediately** after specific events that must not be lost to periodic-write staleness: a manual
  confirmation created, approved, dismissed, invalidated, cancelled, or timed out; a transition back to
  `normal` from any non-normal `RecoveryState`. Hold state is process-local and never mutates
  this checkpoint (§6.3).

`RecoveryTargetSnapshot` entries (§7.4) are deliberately different: accepted target changes are
coalesced in memory. They never trigger the immediate-write path; at most one merged snapshot per
`(actuator_id, controlled_channel)` is eligible for the next 60-second
checkpoint tick's commit. This bounded loss window is the
explicit performance trade-off for actuator baseline recovery. Hold events use the ordinary
ordered audit queue (§6.4).

It answers "did anything change while Heima was offline" cheaply; it is **not** a general restore
mechanism, and — deliberately — it never forces every piece of runtime state through the full
`HouseFact`/`Provenance` shape. The narrowness (only the declared observation-set members)
is a safety/efficiency property, not an oversight: most runtime state genuinely should start clean
after a restart. §7.4's opt-in desired-target baseline is the narrow, explicitly-gated exception; it is not a
precedent for widening this into a general restore engine.

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
class RecoveryFacetBaseline:
    facet: str                               # closed by target_contract_id
    value: str                               # canonical JSON text of the copied target value
                                             # (Layer 5 §6.0 facet codec)
    captured_at: EvidenceInstant
    authority_kind: Literal["reaction", "direct"]
    reaction_id: str | None                   # required exactly for reaction authority
    configuration_generation_id: str | None  # required exactly for reaction authority
    direct_source_kind: Literal["admin_command", "user_response"] | None
                                             # required exactly for direct authority

@dataclass(frozen=True)
class RecoveryTargetSnapshot:
    actuator_id: str
    controlled_channel: str
    entity_id: str
    target_contract_id: str
    facets: tuple[RecoveryFacetBaseline, ...] # non-empty; one entry per canonical facet
    policy: Literal["reconcile", "require_confirmation"]
    actuator_configuration_fingerprint: str # candidate Actuator execution semantics at target
                                             # acceptance; reload discards a target that no longer matches

@dataclass(frozen=True)
class FrozenRecoveryView:
    state: RecoveryState
    recovery_episode_id: str | None       # present for a pending confirmed power-recovery episode
    baselines: tuple[RecoveryTargetSnapshot, ...]  # §7.4-exposed, canonical channel-key order, copied
    fingerprint: str
```

Layer 0 freezes this read-only view at the `CycleInputBarrier`, after the current
recovery classification and checkpoint reads are settled. The episode id is minted
once when a power-recovery episode is confirmed and remains stable through its
settling/reconciliation cycles; ordinary startup has none. `baselines` contains
exactly the snapshots exposed by §7.4 for this cycle, or an explicit empty
tuple when reconciliation is not yet permitted or no baseline exists. Layer 5
uses the same cycle's observed channel availability and current policy to
decide whether an exposed target can act. Its `fingerprint` is SHA-256 over
RFC-8785 canonical JSON of the state, episode id and ordered copied baselines.
A checkpoint commit or
recovery classification change after the barrier affects only the next view.
Layer 4 §5.1 transports it opaquely in `DecisionSnapshot`; Layer 5 combines it
with its separately frozen authority view and never asks Layer 0 for a newer
baseline while evaluating a snapshot.

The key is `(actuator_id, controlled_channel)`, not HA `entity_id`. The owner that accepts an
`ApplyStep` records or updates this snapshot only for an actuator whose
composition-time `power_recovery_policy` (Layer 2 `Actuator`) is `"reconcile"` or
`"require_confirmation"`. For each `ChannelTarget.targeted_facets`, it replaces only that
facet's copied value and trusted authority anchor; untouched facets and other channels
remain. The coalesced snapshot is a storage envelope (§4.1), validated against the channel's
closed target contract and the envelope bound. An invalid update omits the touched channel's recovery
snapshot and emits a diagnostic without cancelling the already-admitted command; it
never leaves a misleading partial merge. Identical updates coalesce. The snapshot is
queued for the next checkpoint commit, at most one write per channel in that commit. There is no synchronous
flush on a target change, no journal for ordinary facts or commands, and no checkpoint read on the
normal evaluation path. Performance is the deliberate reason for this bounded best-effort guarantee:
a power loss after a target changes but before its batch commits may recover the preceding completed
target, or no target at all, never a fabricated newer one.

Layer 5 assigns the authority anchor when it accepts the target. An admitted Reaction
target records its exact `reaction_id` and configuration generation even if the command's
`ApplyStepSource.kind` is `recovery`. A standalone direct admin or verified resident
command records `authority_kind="direct"` and its trusted source kind. A recovery
reconciliation of an older direct target preserves that direct anchor; it cannot relabel
a revoked Reaction target as direct. Unknown or external actions do not create a
checkpointed desired target. A single channel may have facet entries from different
authorized sources; no fictitious whole-channel Reaction owner is inferred.

Snapshot persistence is not an additional acceptance condition for an `ApplyStep`. If its proposed
target cannot be encoded within the §4.1 envelope bound, the already-authorized command still proceeds, the
owner omits that channel's recovery snapshot and emits a diagnostic. A later restart then has no
baseline for that channel rather than retaining an oversized or malformed target.

At configuration-generation cutover (Layer 2 §2.5), Layer 0 receives resolved Actuator policy and
fingerprint deltas rather than reading a registry. A snapshot whose recorded fingerprint or
recovery policy differs from the active candidate, or whose channel is absent from it (a removed
Actuator or channel), is discarded; `policy="never"` deletes it. The Actuator execution semantic
fingerprint includes the HA `entity_id` (Layer 2 §2.5), so rebinding an endpoint discards its
snapshots by the same rule.
A target therefore cannot be applied
under changed capabilities or a newly stricter policy. Layer 5's active generation also
filters every Reaction-anchored facet: a missing, superseded, disabled or non-automatic
Reaction, including a revoked required household consent, removes that facet from the
recovery baseline. A direct-anchored facet does not require a Reaction, but still needs
the current Actuator recovery policy and ordinary channel/safety admission. If no
facets survive, the channel contributes no baseline. This filter is repeated against
current authority before any recovery command or confirmation proposal, not trusted
solely because an earlier checkpoint or cutover accepted it.

Once Recovery has identified a confirmed `power_recovery`, current entity reads are available, and
the system has left `degraded_recovery`/`recovery_settling`, it exposes the last completed snapshots
as a read-only baseline for one full current evaluation. The evaluation order is mandatory:

1. Start from the surviving per-channel facet baselines only for an opted-in actuator;
   an absent or filtered snapshot means no historical baseline for that channel.
2. Evaluate all current facts, time/calendar state, safety constraints, and manual holds. Their
   present-time result has higher precedence than the baseline.
3. Merge surviving facet baselines with current admitted targets, giving each current
   target precedence on the facets it addresses. Validate the resulting channel target
   through its current closed contract and ordinary admission; incompatible mixed
   facets cause abstention on that channel, not a guessed command or cross-channel
   erasure. Compute one final desired target per channel and compare it with the freshly read actual state.
   Only this final delta may become an `ApplyStep`; recovery never first applies the old baseline and
   then applies a second, newly calculated target. A retained baseline by itself is a one-time
reconciliation target, not an ongoing Reaction or a hold anchor. If the current evaluation
admits a Reaction target, its identity is retained separately from the recovery source kind;
after that target is physically confirmed, only a later distinct divergent edge can open a hold.

`power_recovery_policy="reconcile"` permits that final delta to be applied automatically.
`"require_confirmation"` turns the final target into a normal runtime-confirmation proposal; it is
never applied before confirmation. `"never"` contributes no snapshot and no automatic recovery
target. The recovery baseline is consumed only by power recovery, not by an ordinary process restart.
If recovery or a command attempt is interrupted, the next cycle repeats the same read/evaluate/compare
operation; actuator recovery is therefore idempotent reconciliation, not impossible physical
exactly-once delivery. This is intentionally separate from the hold lifecycle event queue, whose purpose is
identity/audit continuity rather than command replay.

### 7.4.1 Runtime confirmation of a recovery target

The confirmation request is a process-local authorization opportunity, not a restored command.
Layer 5 supplies, for each such channel and cycle, one `RecoveryProposalOutcome` (Layer 5 §6.0,
Recovery confirmation proposal): the current admitted proposal from §7.4, `already_satisfied` or
`inadmissible`. Layer 0 owns the request's identity, deadline and lifecycle. This mechanism applies to any opted-in Actuator channel and never
introduces an actuator-kind-specific response path.

```python
@dataclass(frozen=True)
class RecoveryConfirmationRequest:
    request_id: str                 # core-minted, unique within and across process runs
    recovery_episode_id: str        # current confirmed power-recovery episode
    actuator_channel_id: str
    generation_fingerprint: str     # active configuration and authority generation
    proposal_fingerprint: str       # canonical digest of final target, observed channel
                                      # state/epoch, baseline identity and admission inputs
    created_at: EvidenceInstant
    expires_at: EvidenceInstant
    state: Literal["open", "approved", "dismissed", "invalidated", "cancelled", "expired"]
```

Only one `open` request may exist per recovery episode and Actuator channel. An identical
proposal in later cycles reuses it and does not renew its deadline. The Initial-V3 core
confirmation lifetime is 24 hours from creation, measured against the monotonic runtime
deadline and represented by `expires_at` for diagnostics; changing this bound requires a
new core contract version. At `now >= deadline`, Layer 0 records `expired` and rejects
late responses. An expired or dismissed proposal is not generated again merely because
an unchanged evaluation repeats; a materially new proposal or a new recovery episode may
create a new request.

At each fresh relevant cycle Layer 5 recalculates the final target and ordinary admission.
The request stays open only while the same observed state/epoch, target, baseline identity,
configuration/authority generation and guards still make the same command admissible.
An unrelated fact change or repeated identical observation does not invalidate it. A
changed proposal, unreadable channel, failed guard, revoked authority, cancelled recovery
episode or unavailable baseline invalidates it atomically before the next response can be
accepted. If the current complete observation already satisfies the target, it closes as
`cancelled` with reason `already_satisfied`; no command is sent. A newly admissible,
different proposal may create a fresh request after the current-cycle checks.

The request is declared to the authenticated response ingress (§5.1.3) when it becomes `open`,
with actions `approve` and `dismiss` and admitted actors `resident` and `admin`, and withdrawn on every
terminal transition.

**Last resort for a non-resident administrator.** A recovery confirmation is a household decision;
an administrator whose `household_role` is not `resident` (for example an installer, B2B) may answer
only as a last resort. The owner accepts such a response only when, at the response's cycle input
barrier, either the request has been `open` for at least the core-fixed escalation window of
**2 hours** without a resident answer, or the active Layer-6 generation has no recipient whose Person
is a `resident` with at least one endpoint (no resident can receive it). Otherwise the owner rejects
it with the diagnostic `awaiting_resident_answer` and the request stays open. An administrator who is
also a resident is a resident and answers at any time. Changing the window requires a new core
contract version.

Layer 0 hands each request to Layer 6 twice through one typed occurrence: when it opens, so the
resident receives an actionable notification, and when it reaches a terminal state, so Layer 6
can close or replace that notification and no stale button stays usable on a device.

```python
@dataclass(frozen=True)
class RecoveryConfirmationOccurrence:
    operation_id: str                 # sha256 of "recovery.confirmation.operation.v1:" + RFC-8785
                                      # [request_id, phase]
    phase: Literal["opened", "closed"]
    request_id: str
    recovery_episode_id: str
    actuator_id: str
    controlled_channel: str
    subject: Location                 # the Actuator's registered Location, supplied with the proposal
    proposed_facets: dict[str, str]   # facet -> canonical JSON text, Layer 5 §6.0 codec
    allowed_actions: tuple[str, ...]  # ("approve", "dismiss") for "opened"; empty for "closed"
    terminal_state: Literal["approved", "dismissed", "invalidated", "cancelled", "expired"] | None
    expires_at: EvidenceInstant
    occurred_at: EvidenceInstant
```

Layer 5 supplies the subject and the bounded proposed-facet projection in the
`RecoveryConfirmationProposal`; Layer 0 adds no Actuator lookup. `terminal_state` is `None` exactly for `opened`. The occurrence
carries no actor identity, raw HA state or service data. Layer 6 alone appends it as the
`recovery.confirmation_request` event fact with its delivery record in the unified outbox (§4.5);
the operation id appends each phase at most once. A delivery failure does not change the request:
it still expires at `expires_at`, and a response arriving only through the ingress can approve it.
Layer 0 hands the same occurrence, read-only and outside evaluation, to Layer 8's pending-items
projection (Layer 8 §10.3).
After restart the invalidated pre-restart requests (below) produce their `closed` occurrence. A `VerifiedResponse` from that ingress matches `request_id` to the current
`open` request. Approval then takes a fresh cycle input barrier and reruns the same
read/evaluate/compare and dispatch admission under a serialized compare-and-swap on
request state, proposal fingerprint and active generation. If unchanged, it records
`approved` before the ordinary single `ApplyStep` path; a service outcome and physical
confirmation remain separate. If changed, expired or already satisfied, it records the
appropriate terminal state and sends no command. Dismissal records `dismissed` and sends
no command. A second response, a stale request id or a race with invalidation is rejected
without a second command.

Every transition is committed through §7.3's immediate checkpoint path before it is
acknowledged to the resident or exposed as an actionable request. Checkpoint failure
leaves the transition pending and no approval dispatch occurs; retry with the same
request id is idempotent. The checkpoint is an audit trace, not authority to resume an
`open` request. On every process restart, all pre-restart open requests become invalid
for ingress regardless of their persisted state. Recovery records their `invalidated`
terminal transitions through §7.3 before exposing any replacement request; a failed
commit keeps replacement requests non-actionable but never reauthorizes the old id.
Only a fresh complete intake and
current-policy recalculation may create a new request, with a new id, if the delta still
needs confirmation. A response to the old id is always rejected. This rule is separate
from the non-restoration of channel holds (§6.3).

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
  boundary — an exception is caught, logged, surfaced as a diagnostic event (§10), and the job is
  treated as having fired (for a `CronEntry`, the recurrence still re-arms for its next occurrence).
  A single failing job must never take down the engine or silently stop a recurring safety net. A
  Layer-7 extension run uses the same boundary, extended with atomic discard and result expiry
  (Layer 7 §8) — one mechanism, reused, not reinvented. For a divergence-hold expiry (§6), the Manager also checks the monotonic deadline when
  publishing each admission view. A failed `AtJob` callback therefore cannot leave an expired hold
  blocking action indefinitely; the next input barrier releases it and reports the callback fault.
- **Duplicate `job_id` registration**: replace, never error (§3.1) — an owner re-arming the same
  logical deadline is the expected common case, not a conflict to reject.
- **A `CronEntry`'s `due` passes while Heima is offline**: no missed occurrence is queued, replayed,
  or inferred from an interrupted countdown. On restart an `IntervalRecurrence` arms its first new
  deadline at `now + interval`.
  This requires no durable scheduling state beyond the standing rule itself and avoids an unprovable
  catch-up decision. An owner that needs startup work performs it explicitly during bootstrap, where
  that work can be named, reviewed, and tested independently of recurrence timing.
- **Ordinary durable-tier fact-batch write failure** (§4.2): logged and surfaced as a diagnostic event; the cycle is not
  aborted and the in-memory buffer is unaffected. The durable tier is important for audit and
  learning but is not the source of truth for same-cycle correctness — losing one ordinary batch write is
  recoverable, crashing the engine over it is not an acceptable trade. A prolonged failure keeps
  the retry queue within the §4.6 budget and declares any discarded item as `queue_overflow`
  coverage. The separately bounded follow-up preparation and historical-continuity guarantees use
  their own failure rules below.
- **Clock discontinuity** (§3.5): a jump greater than 1 second never moves recorded history
  backward; it re-arms pending `wall_clock` jobs, records a `clock_discontinuity` gap and, for a
  regression, emits `clock_regression`. Elapsed waits continue on monotonic time.
- **Checkpoint write failure** (§7.3): logged and surfaced as a persistence diagnostic; the
  checkpoint remains dirty for retry. The failure does not change the cycle's `RecoveryState`,
  which is classified from current recovery inputs (§7.1). A missing or unusable prior projection
  still supplies no baseline for that entity (§7.3), never evidence that nothing changed.
- **Notification outbox write failure** (§4.5): the affected notification becomes best effort with a
  diagnostic; a `ready` record is never claimed without its committed audit fact, and no cycle,
  command or revocation waits on the outbox.
- **Response ingress rejection** (§5.1.3): an unauthenticated, duplicate, unknown, expired,
  out-of-vocabulary or unauthorized response reaches no owner and is a diagnostic.
- **Follow-up outbox preparation/finalization failure** (§4.5): surface `follow_up_durability_degraded` when preparation fails or misses its finite acknowledgement deadline; do not indefinitely block a scheduled step or immediate revocation. Reconcile an uncertain write under the same operation id, and keep a prepared or ready intent for the prescribed recovery and delivery retry. A failed finalization must not claim that the event fact was committed.
- **Hold-audit validation or durable write failure** (§6.1/§6.4): a violated staged depth/size bound is a producer-contract diagnostic and blocks the continuity watermark, never a truncated fact or permission to bypass the live hold. An already valid fact whose durable write fails remains queued with `durability_pending`, subject to the §4.6 budget and overflow rule. A crash can leave an audit gap bounded by §4.4; restart never restores the hold from audit.
- **Observation-continuity metadata failure** (§4.4): do not acknowledge a historical watermark or report complete coverage across an uncommitted interruption boundary. Surface degraded continuity and use the conservative incomplete/unknown coverage result for affected historical reads; current-cycle action admission still uses fresh inputs.

---

## 9. Runtime health telemetry

Layer 0 owns a read-only `RuntimeHealthSnapshot` for slow-path resource admission. It describes the
runtime that must be protected, not the house: it is not a `HouseFact`, is never stored in the fact
timeline, cannot be read by a semantic resolver/policy as a semantic input, and cannot cause an action. Layer 3
interprets it only at a learning scheduling boundary. The only Layer-0 use is recomputing the
retry-queue budget from its effective memory limit when a new snapshot is published (§4.6).

`RuntimeHealthSnapshot` is immutable and capability-explicit. It contains `captured_monotonic`, the
source/capability set and last successful probe time, effective CPU capacity when known, an effective
enforceable memory limit when known, current Heima process RSS when available, cumulative Heima
process CPU time, cgroup memory-event and
CPU/memory-pressure evidence when available, plus a bounded recent distribution of completed engine
cycle latency and the recent engine CPU usage. A latency sample starts when Layer 0 accepts a meaningful event into a cycle and ends
when that cycle has completed its ordinary engine evaluation and result commit. Over the same span the
coordinator reads the process CPU clock once at each end. It records one O(1) monotonic sample and
one O(1) CPU-time delta into bounded rings; percentile aggregation, the engine CPU usage (the sum of
recent cycle CPU deltas divided by the elapsed monotonic time they cover, in CPU-seconds per second,
the unit of effective CPU capacity) and probe refresh are performed outside the engine evaluation
path. Process CPU time comes from the process's own standard-library accounting, never a host-wide
percentage. Equal-`when` concurrent facts remain one cycle and therefore one
latency sample.

`RuntimeResourceProbe` has no required third-party dependency. On Linux cgroup v2 it reads the
process's effective `cpu.max`/`cpuset.cpus.effective`, `memory.max`/`memory.current`/`memory.events`,
and available PSI files; effective CPU is the lower of quota and affinity capacity. On other platforms
it uses only portable standard-library/process limits that are actually available. An unavailable,
non-finite, or non-enforceable value is represented as absent with its capability unset; it is never
replaced by a guessed machine-wide allocation. This preserves a conservative behavior on an ordinary
host, a container, a NUC, or a Raspberry without making `psutil` or another package part of the
integration's required dependency surface.

The probe is refreshed asynchronously/background outside a cycle and must be bounded, allocation-light,
and failure-contained. Layer 0 exposes its last complete snapshot even if a refresh fails, marking the
staleness/failure capability; it never blocks an event cycle, applies a threshold, schedules a learner,
or changes a learning profile. Each published snapshot, and each change of a degradation
diagnostic of §10 (process interruption, storage or queue-overflow state, follow-up durability,
recovery state, probe staleness), is also handed read-only to Layer 8's health projection (Layer 8
§10.3), outside any cycle. Thus it supplies the measurement contract while Layer 3 owns every
admission, capacity, and degradation decision.

---

## 10. Diagnostics

Layer 0 state must be inspectable, consistent with the project's broader diagnostics culture (a
runtime/plugins/event-store diagnostics surface already exists for other layers):

- **Timing**: every pending `AtJob` and `CronEntry` (id, owner, due, label), queryable at any time.
- **Committed-state observers**: each subscription, its last delivered `cycle_when`, whether a
  delivery is pending, and subscriber failures (§4.8).
- **Observation continuity**: last durable watermark, any open process interruption, its
  start/end and write failure, plus per-stream availability and incomplete-window reasons.
- **Recovery**: current `RecoveryState` and the rule that produced it, the observation-set
  fingerprint, `|S|`, `|U|` and the last member transition instant, age of the last checkpoint write, count and identity of
  entities currently carrying `unknown_during_downtime`/`power_restore_candidate`, plus the count,
  age, and `(actuator_id, controlled_channel)` keys of pending `RecoveryTargetSnapshot`s,
  with surviving facet counts and the recovery baseline/final-target decision for each
  reconciled channel. Expose checkpoint dirty/retry status and the last
  checkpoint-write failure separately from `RecoveryState`.
- **Divergence Hold Manager**: each active `(actuator_id, controlled_channel)`, hold id,
  divergent facets, configured scope and release mode, time remaining or next Reaction-step identity,
  verified origin category or `unknown`, normalized expected/observed facet values and fingerprints,
  and audit-durability status. The existing diagnostic surface may also display the first
  post-break observation against the last known expectation, with current RecoveryState and
  known break context. This comparison is not a hold event, persisted fact, or claim about an
  offline resident action (§6.3).
- **Notification outbox**: record counts per kind and phase, oldest undelivered `ready` age,
  delivery retries and write failures (§4.5).
- **Response ingress**: declared open requests per owner and rejected responses by reason (§5.1.3).
- **Clock**: last cycle instant, last clock comparison, and every detected discontinuity with
  direction, size, detection point (cycle start or periodic check), whether the wall clock fell
  behind the cycle floor, its own `clock_discontinuity` gap boundaries and end rule (first cycle
  instant after detection, or wall clock exceeding the frozen floor), and re-armed `wall_clock`
  jobs (§3.5). Concurrently open gaps are reported individually.
- **Retry queue**: queued bytes, current budget and its source (floor or memory limit), and, after
  ordinary overflow, per-stream discarded counts and `queue_overflow` lost intervals;
  for exceptional global overflow, the epoch start/status, latest baseline invalidation,
  aggregate discarded counts and pending/acknowledged recovery-key counts (§4.6).
- **Persistence**: durable-tier size and retention pressure per `fact_type` (§4.3) — how close each
  is to its count ceiling, so a misbehaving sensor's volume is visible before it needs to be
  diagnosed reactively; and, per `fact_type`, its effective retention window and which registered
  learner (if any) declared the floor driving it, so an unexpectedly long or short retention window
  is traceable to its source.
- **Runtime health telemetry**: the latest `RuntimeHealthSnapshot`, probe source/capabilities and
  freshness, unavailable/degraded fields and their reasons, effective limits where available, recent
  cycle-latency sample count/distribution, and the last probe failure. These diagnostics expose
  measurement only; they do not claim a Layer-3 admission decision.
- **Producer diagnostics**: the one diagnostic-event path for Layer-1 and Layer-2 producer
  contract violations (an `evidence` shape or size violation, source-shape drift, a non-boolean
  fusion input, a formula-contract violation). Each event is recorded in memory under
  `(producer_id, code)` with a bounded offending reference, a count and the last instant; repeats
  only increment the entry (O(1), no I/O in the cycle). Entries are handed read-only to Layer 8's
  diagnostics; they are never a `HouseFact` and never change a fact's value.

### 10.1 Runtime error condition (CA4-109)

Heima is in **error** while at least one closed cause holds:

```python
RuntimeErrorCause = Literal[
    "no_active_manifest",          # no committed composed configuration is active (§4.7)
    "persistence_write_failing",   # durable writes are failing (§4.1, §4.4, §4.5)
]

@dataclass(frozen=True)
class RuntimeHealthOccurrence:
    operation_id: str     # sha256 of "system.health.operation.v1:" + RFC-8785
                          # [run_id, transition_sequence]
    transition_sequence: int   # 1-based count of transitions emitted in this run
    phase: Literal["error_opened", "causes_changed", "restored"]
    causes: tuple[RuntimeErrorCause, ...]   # non-empty, distinct, ASCII order; the current causes,
                                            # or the ended episode's last causes for "restored"
    detected_at: EvidenceInstant
```

`run_id` is a fresh per-process identity. Each transition has its own identity
`[run_id, transition_sequence]`; `phase` and `causes` are content, not identity (CA4-110). A return to
causes seen earlier in the same episode is a new transition with a new identity, because a real
change happened in between; an exact retry of one transition reuses its whole occurrence.

**Persistence write outcomes (CA4-110).** A *durable write* is a transaction submitted to the common
writer that mutates Heima's durable state. Opening or configuring the connection that a durable write
needs is part of that write. The persistence host reports each durable write's outcome: committed,
failed, or uncertain (treated as failed). Each failure names its write kind (the owning durable path:
accepted facts with their commit marker, a notification `ready` with its audit fact, a composed
generation, continuity metadata, the recovery checkpoint) and whether its owner retains the failed
work for a later attempt. Reads, connection setup with no durable write pending, a transaction that
commits without mutating anything, and a refusal by a writer already closed after a failure are not
outcomes: they neither raise nor clear the cause.

`persistence_write_failing` holds while either:

1. a write kind has retained work whose latest attempt failed; or
2. no durable write has committed since the latest failure.

It begins at the first failure while it does not hold and ends when neither condition holds. A
write kind stops counting under 1 when its latest attempt commits, or when its owner no longer
retains the failed work (for example retry-queue loss under §4.6, which stays a degradation
diagnostic). Failures while the cause holds produce no transition. A backlog may remain when it
ends. No probe, timer, grace interval or queue drain is involved: the cause follows only actual
write outcomes and retained-work state that the owners already have.

Layer 0 evaluates the condition outside any cycle, whenever one of its causes changes, and once after
bootstrap. It hands one occurrence per transition, read-only, to Layer 6 (`system.health`) and to
Layer 8's health projection, so the panel and the notification use the same predicate. The occurrence
is not a `HouseFact` input, cannot be read by a resolver or policy, and causes no action. A condition
still present after a restart opens a new episode of the new run.

---

## 11. Relationship to the core DAG

Layer 4 owns an acyclic same-cycle semantic DAG: a resolver may read only its declared upstream
semantic claims already resolved earlier in the deterministic topological order. A `previous_cycle`
value is instead an explicitly declared Layer-0 snapshot input, never an implicit substitute for an
upstream semantic edge. Layer 0 is outside that DAG by construction: wall-clock time and Recovery's
classification are **engine-computed context**, read-only input available within the current cycle
to the layer that declares it, not another resolver's output. A semantic resolver receives only the
cycle identity and time (Layer 4 §5.1); Recovery's classification reaches only Layer 5, through
`FrozenRecoveryView` (§7.4). Layer-7 extensions run outside the cycle and never
read it (Layer 7 §7). A semantic resolver reads Layer-0
context fresh every cycle, as it reads Layer-2 facts fresh every cycle; neither is produced by an
earlier semantic resolver in the same pass.

---

## 12. Not yet decided

Open cross-layer contracts are tracked in the CA4 backlog. No open CA4 item is currently owned
by this layer; CA4-20, CA4-28 and CA4-38 were closed in §3.1/§3.5, Layer 1 §3–4 and §4.6.

---

## 13. Acceptance criteria (for the eventual implementation phase)

- Runtime error condition (CA4-109): a durable write failure produces one `error_opened` with
  `persistence_write_failing`; a later loss of the active manifest produces `causes_changed` with
  both causes; recovery of both produces one `restored` carrying the last causes. Retries of the same
  transition reuse the `operation_id`; a restart with the condition still present opens a new episode
  with a new `run_id`. No resolver, policy or `ApplyStep` can read the occurrence (§10.1).
- Persistence write outcomes (CA4-110), active manifest present throughout: (1) an accepted-fact
  transaction fails and its facts stay queued: `error_opened`; (2) the connection is reopened with
  nothing written: no change; (3) a transaction commits without mutating: no change; (4) a metadata
  write commits while the failed facts are still queued: no change, condition 1 holds; (5) the fact
  retry commits while other work remains queued: `restored`; (6) a new fact transaction fails:
  `error_opened` of a new episode. A failed composed-generation apply, returned to the caller and not
  retained, opens the cause; the next committed checkpoint ends it. Repeated refusals by the closed
  writer produce nothing.
- Transition identity (CA4-110): in one run and one open episode, causes A, A+B, A, A+B give four
  occurrences with `transition_sequence` 1–4 and four distinct `operation_id`s (transitions 2 and 4
  differ despite equal causes); an exact retry of transition 2 returns the identical occurrence.

Not part of this design spec's approval gate — recorded so the implementation phase inherits a
concrete checklist rather than re-deriving one:

- Every committed manifest and the layer generation records it references stay readable by id
  after any number of later commits and fact-retention runs; reading one changes no active
  generation (§4.7).
- A subscription to `quiet_hours.active@casa` receives its current value once after the first cycle,
  then one delivery per committed change in cycle order; three changes before the subscriber runs
  yield only the latest; an unchanged cycle yields none; a slow or failing subscriber never delays
  a cycle or another subscriber; a pattern key, an event key or a registration outside bootstrap or
  a generation swap is rejected. A generation swap that adds a room delivers that room's key once
  after the first new cycle and stops a removed room's key (§4.8).
- A recovery confirmation produces one `opened` occurrence with `approve`/`dismiss` and one
  `closed` occurrence with its terminal state, each appended once as
  `recovery.confirmation_request`; an identical proposal on a later cycle produces neither again.
  A delivery failure leaves the request and its deadline unchanged, and a restart produces the
  `closed` occurrence for each invalidated pre-restart request (§7.4.1).
- Every delivered notification of any kind has exactly one audit event fact and one outbox record
  written in the same transaction; a crash between them is impossible by construction. A `ready`
  record survives fact retention until delivered or retired; `ready -> retired` without
  delivery keeps the audit fact; an exact transition retry is
  idempotent and a different payload under the same `(notification_kind, operation_id)` is
  rejected. Only `reaction.follow_up` uses `prepared`. A storage failure blocks no cycle (§4.5).
- A response to a recovery confirmation through the ingress reaches the owner only with a valid HA
  user of an allowed category, a declared unexpired request and an allowed action; a forged,
  duplicate, expired or withdrawn request, an actor outside the declared categories, or an action
  outside the vocabulary reaches no owner. An approval yields an `ApplyStep` with
  `kind="user_response"` and the verified `UserActor`, whether the actor is a resident or an
  administrator. The owner's record keeps the actor reference (the HA user id); the resulting
  `ApplyStep` carries only the `UserActor` (§5.1, §5.1.3, §7.4.1). A guest, or a user with no
  `Person` that is not an administrator, is rejected at the ingress. A non-resident administrator's
  approval within 2 hours of opening is rejected by the owner with `awaiting_resident_answer` while a
  resident recipient exists; after 2 hours, or when the Layer-6 generation has no resident recipient
  with an endpoint, it is accepted.

- A `HistoryViewRequirement` stages only for a registered state/event stream
  with its matching slice kind, unique id and retained positive `Window`.
  At one `CycleInputBarrier`, the frozen view returns the same bounded slice
  on retry; a later append is invisible. A complete empty event interval is
  `()`, while a missing state-at-start record, gap or evicted interval is
  `None`, never an empty slice (§4.1). A Layer-3 live signal emitter reads its own staged
  requirements from the same barrier's view and cannot read a Layer-5 requirement id, or the reverse.
- A state that changes once and is then read unchanged for hours creates one
  `HouseFact`, while complete required-stream coverage permits a later
  historical as-of read. A known source-report expiry opens a durable
  stream gap at expiry even when detected on a later cycle; a subsequent
  identical reported value closes it at the first valid observation without
  backdating either fact. A newer unavailable transition is the latest
  state during its interval. If stream-gap metadata cannot be acknowledged,
  the affected read is incomplete (§4.0/§4.2/§4.4).
- Two cycles whose wall-clock readings are the same microsecond receive cycle
  instants `T` and `T + 1 µs`; an ingress edge stamped before the previous
  cycle instant is raised just after it. A `home` then `away` presence
  across those cycles satisfies Layer 4's strict `last_available_when <
  observed_at` and emits one departure (§3.5; Layer 4 §9.3).
- With a fake monotonic clock and fake wall clock: a 0.5 s wall correction
  emits no gap and no diagnostic unless it puts the wall clock behind the cycle
  floor, in which case only `clock_regression` is emitted; a 2 s backward
  correction that puts the wall clock behind the floor keeps instants strictly
  increasing, emits `clock_regression` and records a `clock_discontinuity` gap
  from the first frozen cycle instant until the wall clock exceeds the frozen
  floor. A 2 s backward correction that leaves the wall clock ahead (previous
  cycle at wall 12:00:00 and monotonic 0 s; next reading at wall 12:00:58 and
  monotonic 60 s) emits `clock_regression`, re-arms `wall_clock` jobs and records
  a gap from 12:00:00 to the next cycle instant 12:00:58, with no frozen
  instant. The same correction detected first by the 60-second check opens the
  gap at that check, from the last cycle instant to the first later cycle
  instant, and is not detected again by that cycle; a 10 min forward jump records a gap
  over the skipped interval. A history read spanning either gap is incomplete
  with `clock_discontinuity`. A bootstrap reading earlier than the durable
  floor by more than 1 s behaves as a backward jump (§3.5/§4.4).
- Forward correction while the floor holds (relative seconds): durable floor 100;
  bootstrap at monotonic 0 reads wall 90, cycle instant 100.000001, frozen gap
  open. At monotonic 1 the wall reads 94 (a 3 s forward correction, still below
  the floor). Detected at that cycle start: a new gap 100.000001 → 100.000002,
  ended. Detected first by the periodic check: the new gap starts at 100.000001
  and ends at the next cycle (monotonic 2, wall 95) at 100.000002, without
  waiting for the floor. In both paths the bootstrap gap stays open until a
  cycle whose wall reading exceeds 100, both are reported separately, and each
  end boundary needs durable acknowledgement before a read past it is complete
  (§3.5/§4.4/§10).
- During a wall-clock correction, an armed `elapsed` 30-minute hold expires
  after 30 monotonic minutes. An armed `wall_clock` calendar-boundary job is
  re-armed against its unchanged due: after a forward jump past the due it
  fires once immediately, after a backward jump it waits, and it never fires
  twice. A job registered without `basis` is rejected (§3.1).
- With wall 100, monotonic 0 and cycle 100, a `wall_clock` job due at 110 arms
  10 s. At monotonic 1 the wall reads 98 (a 3 s backward correction); the next
  cycle instant is 100.000001. Re-arming against the wall reading gives 12 s, so
  the job fires at wall 110, never at about wall 108; detection by the periodic
  check or at bootstrap uses the reading of that detection the same way. An
  `elapsed` 30 s hold armed at that cycle has due 130.000001 and a 30 s
  countdown against the cycle-instant clock. The cycle requested by the
  `wall_clock` job receives the floored cycle instant; neither job fires twice
  and replacement and cancellation are unchanged (§3.1, §3.5).
- With storage failing and a fake 32 MiB budget, a flapping state stream keeps
  only its latest queued state plus a `queue_overflow` lost interval; oldest
  queued events are discarded next with per-stream intervals; continuity
  boundaries are never discarded and admission never blocks. After storage
  returns, the boundaries commit with or before the retained items, the
  watermark advances only past declared losses, and reads over a lost
  interval are incomplete with `queue_overflow`, never zero or continuous.
  An unaffected stream remains complete under ordinary overflow. If distinct
  latest states, boundaries or one oversized item cannot fit, the global fallback
  keeps the queue within budget, leaves admission nonblocking and makes every
  intersecting historical read incomplete. After storage recovers, a fresh full
  HA intake and an acknowledged closure boundary are required. Re-seeding proceeds
  through bounded successive cycle batches; total seed volume above the queue budget
  never creates a full snapshot queue or blocks admission. Closure may precede all
  seeds: a post-closure read requiring an unseeded key stays incomplete, while a
  seeded unrelated key or an event stream can regain complete coverage. A discarded
  seed does not recover its key; an unchanged seed creates no duplicate buffer edge
  or §4.8 delivery. Unavailable HA input is acknowledged as unavailable, not replaced
  by an old available value. Another irreducible loss invalidates earlier recovery
  baselines; crashes before/during/after closure preserve conservative per-key validity.
  A closure whose COMMIT is held while admission causes an irreducible loss after B
  commits the older closure without waiting; the loss opens a new epoch persisted after
  the closure and before any later retained item. With a crash injected between the
  closure COMMIT and that opening, the restart shows the older epoch closed and the
  interruption gap from the last durable watermark covering the loss. A failed write of an
  item at or before B aborts the closure (CA4-117).
  With a known 1 GiB memory limit
  the budget is 51.2 MiB; without a known limit it is 32 MiB; a lower recomputed
  budget does not retroactively discard items (§4.4/§4.6).
- One `AtJob`/`CronEntry` execution path, monotonic-safe by construction; no remaining independent
  timer call site anywhere in the codebase.
- Re-registering the same `(owner, job_id)` leaves one pending timer; owner cancellation is
  idempotent. A callback already handed to the owner before replacement/cancellation may arrive,
  but its old arm revision cannot execute a programmed Reaction step or release its hold
  (Layer 5 §6.0).
- `Window`/`LearnedWindow`/`WarmupGate`/`WeeklyRecurrence`/`IntervalRecurrence`/`CalendarWindow` used
  everywhere a bespoke duration/threshold/schedule field exists today — none left on a semantic resolver or
  reaction config directly.
- `LearnedWindow` construction rejects a `seed` outside `[minimum, maximum]`, in a test that
  tries both an under-range and an over-range seed — verified separately from calibration's own
  clamping, since seed is what every dwell check uses before the first calibration completes (§3.2).
- Temporal construction rejects `bool`, zero, negative, `NaN`, and infinite durations for `Window`,
  `IntervalRecurrence`, and `LearnedWindow` bounds; rejects inverted learned ranges; accepts an equal
  positive learned range; rejects invalid weekly weekday/hour/minute fields; and rejects a malformed,
  non-UTC or noncanonical `AtJob.due`. Static failures reject startup/reload staging, while a dynamic invalid job is
  diagnosed and never armed (§3.1/§3.2).
- Deadline construction from anchor `2026-10-14T12:00:00.000000+00:00`: `Window(0.0000001)`
  gives due `…12:00:00.000001` (never equal to the anchor), `Window(0.000001)` gives
  `…12:00:00.000001`, `Window(0.0000015)` gives `…12:00:00.000002`, `Window(0.000002)` gives
  `…12:00:00.000002`, and `Window(0.1)` gives exactly `…12:00:00.100000`, because the canonical
  decimal and not the binary float value is used. An `IntervalRecurrence` of `0.0000001` s re-arms
  1 µs after each fire, never at its own anchor. Each `Window` keeps its canonical value. A dynamic
  job whose sum passes `9999-12-31T23:59:59.999999+00:00` is rejected with a diagnostic and arms
  nothing; a `CalendarViewRequirement` whose horizon end from the staging clock is unrepresentable
  fails staging. A timer firing late is lateness, not a different due (§3.1).
- Canonical round-trip fixtures give the same bytes to equal `EvidenceInstant` values in facts,
  jobs and calendar snapshots, and to equal `Window` values in recurrence, fusion and learning
  contracts. A `Z` alias, a bare millisecond integer or a native `datetime`/`timedelta` at a
  declared contract boundary is rejected (§3; Layer 1 §4).
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
  non-authoritative; a fabricated `kind="extension"` result is never upgraded to
  `kind="sensor"`/`kind="recovery"`; a client-supplied `UserActor` is ignored and re-derived at
  the boundary; and `kind="user_response"` is verified against
  its two distinct boundaries: an active confirmation request, or a matched direct Actuator
  command. Propagated user context, an unregistered channel, or a duplicate ingress identity
  cannot establish manual control.
- An authenticated user action retains the attributable actor only in its
  governance transition; its `ApplyStepSource`, `ApplyStep` and execution audit carry no
  `actor_id` or equivalent personal identity. A correlation id links the records without
  authorizing a command or exposing the actor in the operational projection (§5).
- Bootstrap composes exclusive `event` claims for `actuator.manual_control` (Layer 0)
  and `actuator.correction` (Layer 5). A competing exact or overlapping claim from another
  owner, including an extension, is rejected before producers run. Each accepted fact has its
  owner's closed value and is read as an event, never current state (§4; Layer 5 §6.1).
- A verified manual, automation, or integration edge receives only its proven origin
  (§6.1). An unproven but valid post-confirmation divergence activates a channel hold with
  `origin="unknown"`. A pending Heima action, unconfirmed command timeout, availability change,
  and first observation after restart or an observation break create no hold. A later valid edge
  after a confirmed expectation does. Convergence of all divergent facets, expiry or the
  next planned Reaction step, revocation, rebinding, and observation loss release the channel
  hold as specified in §6. Expiry cannot reactivate from the unchanged observation. Restart
  begins with no holds and current-policy automation resumes normally.
- Given a Heima restart with an old Reaction target and a current HA reading that differs,
  when the first valid post-restart observation arrives, no hold or resident-origin claim is
  produced; the known difference appears only in the existing non-authoritative diagnostic
  surface, and current policy may evaluate. The same holds for two bulbs at power-on defaults
  (§6.3, §10).
- Given a confirmed standalone `admin_command` or `recovery` ApplyStep with no current admitted
  Reaction target, when a later different valid edge arrives, no Reaction hold opens. Given
  a current admitted Reaction target already fully observed, the matching external/admin
  physical state may anchor a later hold without assigning that state to Heima (§6.2).
- One valid observation changing two confirmed facets on a channel creates one hold and one
  activation event. With a 30-minute fixed deadline established at 10:00, a new facet divergence
  at 10:29 joins that hold and is released at 10:30; the update does not grant it another 30
  minutes. Partial convergence removes only the matching facet. Under default scope, any
  automatic command on the channel is blocked until release; under a validated selective scope,
  only a command whose complete affected-facet set intersects the divergent set is blocked.
- Given one Actuator with two fixed-duration channels and one configured 30-minute
  `hold_duration`, a qualifying divergence on channel A at 10:00 and another on channel B
  at 10:10 create separate holds. A expires at 10:30 while B remains active until 10:40;
  updating A or B does not reset either deadline. The shared configuration supplies the
  duration, not a shared expiry instant (§6.2; Layer 2 §6).
- Given two activations A and B of the same configured Reaction generation,
  an A-owned hold retains A's activation id in its frozen admission entry and
  lifecycle audit. A B step or terminal result cannot release it; A's verified
  normal exit can. If A has already ended, a later B-owned hold receives B's
  distinct id. A crash restores neither activation nor hold, and a fresh
  activation after restart cannot claim the old release boundary (§6.1–6.3;
  Layer 5 §3.2/§6.0).
- Given selective scope and Reaction A's confirmed power target held at 10:00, when
  Reaction B confirms a disjoint brightness target and a later valid edge diverges
  on brightness, the same hold is updated without changing A's release owner or
  deadline. Its lifecycle event has source-map entries for the involved facets,
  attributing B's expectation to B rather than A. A mixed-facet edge makes one
  transition whose maps identify both sources. B's future step cannot release the
  hold; A's qualifying step releases the whole hold. A map with missing, extra or
  conflicting facet keys is rejected; staging refuses any channel contract
  whose worst-case complete inline payload exceeds Layer 1 §3's limits.
  Release-owner revocation or observation loss invalidates the shared hold; restart restores
  neither hold nor expectation-source maps.
- Given A's and B's divergent facets share one hold, when B's current target
  is superseded, only B's facet leaves in one `updated` transition and A's
  release boundary stays fixed. When B was the final divergent facet, the
  terminal event is `invalidated` with `expectation_superseded`, never
  `converged`. A merely due or rejected B step changes neither live set nor
  audit; the next B target must be admitted and physically confirmed before
  a later edge can create another divergence (§6.1–6.2).
- For next-step release, a valve moved by the resident from the confirmed 100% target to 50%
  stays held through ordinary Reaction re-evaluations. The same Reaction's later timed step to
  0% releases the hold before attempting closure. A timed step changing only a different target
  facet also releases the whole channel hold; if its complete new target includes 100% opening,
  that opening may be requested again. If guards block the new step, release still occurs but
  no closure is claimed; the unresolved observed state is surfaced. A normal
  cancellation or exhausted step stream proven by the versioned Layer-5
  descriptor contract uses the declared exit policy: absent a final target, the
  observed valve position is left as is and the resident is notified. With a core-declared
  final target, hold release and a fresh snapshot precede one guarded terminal attempt;
  cancellation completes even when that attempt is skipped or remains unconfirmed. Immediate
  authority revocation permits no terminal call. Temporary source unavailability does not
  count as completion.
- A descriptor-declared fresh event step with the same Reaction, generation,
  activation and channel releases a `next_reaction_step` hold when its full
  canonical target differs from the anchor. A replayed old event, unrelated
  Reaction event, ordinary re-evaluation or repeated target cannot release
  it. The event step and a simultaneous due timer resolve to one effective
  target in Layer 5 before Layer 0 sees a release request (§6.2; Layer 5 §6.0).
- A confirmed power recovery with an opted-in light/fan preserves the last completed desired-target
  snapshot only as a baseline, evaluates current conditions before issuing any command, and sends one
  final idempotent delta rather than replaying historical commands. A simulated four-hour outage whose
  current time has crossed a lighting boundary verifies that a light previously off is turned on when
  current policy requires it; an unchanged-context case verifies the previous desired target returns.
  A target changed immediately before an intentionally unflushed checkpoint batch verifies that only
  the preceding completed target (or no baseline) is used, never a claimed newer target. `never` sends
  no recovery command and `require_confirmation` creates a proposal rather than an `ApplyStep`.
- Two logical channels on one HA endpoint keep separate recovery snapshots. Successive
  partial targets on one channel replace only addressed facets, including their
  individual source anchors. A removed or consent-revoked Reaction loses only its
  anchored facets; surviving direct-admin facets still face current policy and safety
  checks. Mixed facets that cannot form a valid current channel target cause abstention,
  not a guessed partial command. Changed endpoint, adapter fingerprint or recovery
  policy discards the affected snapshots. An invalid merged projection omits only its
  channel while the accepted command still proceeds.
- A recovery confirmation for a valve opening, blind position or HVAC target keeps one
  request id across identical fresh evaluations. A relevant changed target, observed
  channel state, guard or authority invalidates it; unrelated facts do not. A target
  already reached closes it without dispatch. Expiry or dismissal does not repeatedly
  reprompt for the same proposal. A response racing invalidation cannot dispatch, and
  two responses cannot dispatch twice. After a crash, a checkpointed open request id
  is rejected; fresh complete intake and recalculation may create a new id. Checkpoint
  failure prevents acknowledging or executing an approval.
- Hold lifecycle audit is one event per admitted transition (§6.1), with a unique operation id
  independent of its causal correlation id. A single multi-facet observation makes one transition; distinct transitions may share a
  correlation id but never an operation id. A reused operation id with different payload is
  rejected. Event-write failure leaves
  the hold live and reports `durability_pending`; after a crash the historical stream may have a
  gap but cannot restore a hold.
- A lifecycle fixture serializes and validates every `HoldLifecycleValue` field
  declared in §6.1, including owner and facet-source identities, four equal
  source-map key sets and the optional step-map subset, target/value
  fingerprints, origin proof, observation context, frozen
  scope/release mode/deadline, and event-specific reasons. It rejects a missing,
  extra or inconsistent field. A light with composite RGB colour remains a
  complete inline value because each facet value is canonical JSON text.
  An illustrative future-descriptor valve position and Initial-V3 HVAC
  mode/setpoint_c fixture pass the same Layer-1 depth-two and 8 KiB
  value-shape validator; the valve follow-up does not claim Initial-V3
  outcome eligibility (complete serialized
  examples: [CA4-01 serialization examples](ca4_01_serialization_examples.md)).
  Staging computes the worst-case complete canonical value for each permitted
  adapter/scope/Reaction combination, including longest allowed identities
  and every source map. A configuration with an unbounded string or a
  8,193-byte worst case is rejected before cutover; an 8,192-byte worst case
  is admitted only if depth also passes. A runtime bound violation is a
  producer-contract diagnostic and leaves the live hold in force without
  publishing a malformed fact. A valid fact enters the short-term buffer
  immediately at its original `when`; a slow durable write does not delay
  that visibility or admission. An exact operation-id retry retains one
  inline fact; a changed payload fails in memory or against the durable key.
  A crash before durable acknowledgement may lose the audit tail under §4.4,
  never a live hold. The continuity watermark waits for the ordinary fact's
  acknowledgement or, if §4.6 discards it, for durable acknowledgement of the
  `queue_overflow` boundary declaring its loss. Before that boundary is
  durable, the watermark cannot pass the loss; afterwards, the affected audit
  interval remains incomplete and the discarded fact is never treated as
  written. A fact rejected before queue admission remains a continuity blocker.
  A separate frozen-view fixture checks every `HoldAdmissionEntry` and
  `HoldAdmissionView` field and fingerprint before Layer 5 consumes the view.
- A declared durable history read returns `HistoricalReadResult` with independent
  retention and typed observation coverage. A clean stop, hard crash after an
  unacknowledged audit event, failed continuity metadata write, repeated failed
  startup, and restart shorter than a freshness bound never report complete
  observation across the process gap. The gap closes only at a durable
  `CycleInputBarrier` from a newly completed HA intake with source health and
  explicit binding availability; a timer-only barrier, cache, or first entity edge
  does not close it. One unavailable valve stream makes only reads requiring it
  incomplete while an unrelated readable light stream may be complete after
  closure. The validator rejects an unknown reason, duplicate/unsorted reasons,
  nonempty reasons/non-None boundary with `complete`, or empty reasons/missing
  boundary with `incomplete`. A gap at an excluded endpoint does not intersect
  the read; a gap already open at the requested start and an unknown-metadata
  read both use that start as the conservative
  boundary (§4.4).
- A `reaction.follow_up` boundary with preparation acknowledged before the finite
  core deadline durably prepares one bounded intent before its step or normal exit
  advances; an exact retry returns the same id, while
  a changed payload under that id fails. An atomic transaction writes the one Layer-6
  event fact and marks the intent ready. A crash before the outcome recovers an
  `interrupted_before_outcome` warning without an Actuator call; a crash after event commit
  cannot append another fact. An undelivered ready payload survives ordinary fact retention
  until delivery acknowledgement; lost acknowledgement permits a repeat delivery. Failed
  preparation or an unacknowledged write at the monotonic deadline reports
  `follow_up_durability_degraded` but never stalls a scheduled guarded step or
  an administrative revocation. A late prepare cannot recreate `prepared` after
  final fact commit or no-event retirement; a crash yields an interruption warning only if preparation
  committed (§4.5; Layer 5 §6.0).
- Given one presence-simulation normal exit for lights A, B and C, core
  derives three distinct channel operation ids from the same activation and
  exit boundary. A and C prepare successfully; B's write remains unacknowledged
  at the finite deadline and reports `follow_up_durability_degraded` only for B.
  A crash before outcomes recovers one `interrupted_before_outcome` fact for
  each committed prepared A/C row and no guaranteed B fact. Exact A/C retries
  retain one fact each; a changed retry fails; the three notification keys
  cannot coalesce. A late B prepare and a B final fact or no-event retirement
  serialize under B's id, without changing A/C. Revocation stops all unsent
  calls and does not erase committed notices (§4.5; Layer 5 §6.0).
- A query for "every `HouseFact` true in `Location` X between t1 and t2" correctly reports a fact as
  true throughout the window when its only durable record predates `t1` by a wide margin (§4), via the
  at-or-before-`t1` plus within-window reconstruction — verified for a fact stable for a period longer
  than its `fact_type`'s own retention window.
- With state A at day 0 and B at day 20, ordinary pruning of A before a days 10–21
  query returns `retention_coverage="truncated"`, even though that interval is inside
  the nominal retention window. Early count/global pruning of an intermediate B
  cannot make an older surviving A look like a complete predecessor. The
  early-pruning marker records the evicted record's `when`, not maintenance time.
  An unaffected event stream may still report complete retention. The short-term
  frozen view returns `None` for an unseeded state interval or an interval crossing
  buffer startup/eviction; it returns an empty tuple only for a complete event
  interval with no occurrence. Layer 5 abstains on `None` (§4.0–4.3; Layer 5 §5.1).
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
  evaluation-path lookup; an equivalent-owner/equivalent-kind overlap is accepted. Two distinct event occurrences with identical payload are appended twice; exact retries
  under the reserved `manual_hold.lifecycle` operation ids and every notification kind's
  `(notification_kind, operation_id)` key (§4.5) append once. Event facts have no `FactIdentityKey`/latest-value entry and are rejected when
  requested as current state or via `FactRef.previous_cycle` (§4).
- A candidate removing a Sensor used by a Fusion input, a Layer-3 binding, a
  Layer-4 resolver and a Layer-5 guard yields one impact record listing all
  four as `breaking`; changing only that Sensor's reliability lists them as
  `semantic_only`. Removing a learning definition, or changing its analysis
  semantics, lists a Layer-5 timing-model binding pinned to it as `breaking`; a
  serving-, scheduling- or presentation-only learner edit leaves it `unaffected`. A commit with a stale base generation or a different
  `impact_fingerprint` mutates nothing; an empty impact needs no
  confirmation. A crash before the manifest write leaves the old composition
  active; after it, bootstrap loads the new manifest. No cycle observes a mix
  of layer generations. A code upgrade invalidating part of the committed
  composition is applied at bootstrap under the system actor with a
  diagnostic for every invalidated dependent (§4.7).
- A configuration-generation swap assigns a new non-forgeable `configuration_fingerprint` to every
  impacted source, forcing an otherwise unchanged state fact to persist; an Actuator recovery snapshot
  whose fingerprint no longer matches is discarded before recovery can propose or apply it (§5/§7.4).
- Every non-fact durable payload is checked as a copied Layer-1 `PersistedProjection`, and every
  outbox record, recovery-target snapshot and checkpoint entry as a typed storage envelope within
  the §4.1 bound whose nested target values are canonical JSON text: an oversized recovery target leaves its
  already accepted `ApplyStep` intact but creates no baseline; and one invalid critical-entity
  projection is omitted without invalidating other checkpoint entries (§4.1/§7.3/§7.4).
- Retention (time-based or count-ceiling) never evicts the single most recent record for a given
  `FactIdentityKey`, verified by a test that ages a stable fact's only record well past its
  `fact_type`'s retention window and confirms it is still present and still returned by the
  reconstruction query above; a superseded (non-latest) record for the same key, aged the same way, is
  confirmed evicted normally (§4.3).
- The 50,000-record count ceiling is a hard per-`fact_type` safety limit even when it conflicts with
  a declared retention target; the 512 MiB global watermark additionally prunes globally oldest
  evictable records when several compliant types accumulate. Neither removes a latest state record or
  rejects an observation. A history interval predating its requested stream's durable
  early-pruning marker reports `retention_coverage="truncated"`; a consumer requiring a complete
  window refuses that input and remains degraded rather than learning from the shorter remainder.
  A test proves that pruning one `(fact_type, Location)` stream does not truncate another Location's
  complete read of the same type, while a joint read is truncated when either required stream was
  affected. If protected latest states alone exceed the watermark, diagnostics expose
  `storage_pressure` while current state remains intact (§4.3).
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
- A staged `CalendarViewRequirement` can read only its one declared entity and finite horizon through
  `FrozenCalendarView`. Tests prove its active/upcoming results and fingerprint are fixed at the same
  `CycleInputBarrier` as `FrozenHistoryView`; a later provider refresh, cancellation or edit cannot
  affect that cycle but changes the next snapshot. A failed source is preserved as `failed`, never
  converted to an empty result; an undeclared requirement, wider horizon or direct provider/cache read
  is rejected. No Layer-0 code classifies a summary or persists it outside the normalized calendar
  cache.
- A `WeeklyRecurrence` occurrence at `02:30` in `Europe/Rome` starts once at `03:00` on the
  spring-forward date, and once at the first `02:30` (`fold=0`) on the fall-back date, never again
  at the repeated `02:30`; both physical fall-back instants still match the same civil-time pattern
  for bucketing. An `IntervalRecurrence` crossing either boundary retains its elapsed monotonic
  cadence, and a configured timezone change re-arms a weekly-derived descriptor boundary without a
  catch-up (§3.1). A `CronEntry` with a `WeeklyRecurrence` pattern is rejected at registration.
  After a simulated restart, an interval arms at `now + interval` and replays no missed occurrence;
  an owner that needs initialization work is verified to perform it from explicit bootstrap logic,
  not from a scheduler callback.
- An admin-authored HA `schedule.*` helper is read as an ordinary state-bound boolean fact; a change
  to its effective state triggers normal evaluation without a Heima recurrence picker or `CronEntry`.
  An unavailable or unmapped helper state produces `available=False` and cannot activate its Reaction
  (§3.1/Layer 2 §3-4).
- A durable-tier write failure, a checkpoint write failure, or a job callback exception, exercised in
  a test, never crashes the engine and always produces a diagnostic event (§8).
- Recovery's periodic checkpoint is an `IntervalRecurrence` of 60 seconds and writes only while dirty:
  a clean sequence of ticks performs no disk writes; multiple accepted target changes for one
  `(actuator_id, controlled_channel)` before the next tick produce one merged snapshot commit with
  per-facet replacement (§7.4); and a failed checkpoint remains
  dirty for retry while the evaluation path continues without disk I/O (§7.3/§7.4). With otherwise
  normal current inputs, that write failure leaves `RecoveryState="normal"` and reports the
  persistence failure separately; genuinely unavailable entities still produce the §7.1
  recovery classification regardless of checkpoint-write status.
- A declared `FactRef.previous_cycle` key resolves from the sealed O(1) in-memory snapshot on the
  next in-process cycle even when the preceding durable batch failed. After a simulated clean
  shutdown/restart, the key is pre-hydrated before the first DAG from the matching committed cycle;
  after an unclean restart, missing/mismatched clean marker, or unhealed durable-batch failure it
  instead has no value for that first cycle (Layer 4 `previous=None`, never a fabricated
  `available=False` fact) and performs no evaluation-path disk read
  (§4.1).
- Recovery/Checkpoint classification is settled before the first semantic resolver runs in every
  test cycle, including the first cycle after a simulated restart, and reaches Layer 5 read-only
  through that cycle's `FrozenRecoveryView`; no Layer-4 resolver input carries it (§11).
- Recovery classification (CA4-151) uses only the pushed `RecoveryObservationSet`: with 10 members,
  5 unavailable enter `degraded_recovery` and 4 do not; with 3 members, 2 enter it and 1 does not;
  with 1 member, its loss never does; an empty set never does. After the condition clears the
  state is `recovery_settling`, and `normal` follows only after 120 s without the condition and
  without a member availability transition; a transition at 119 s restarts the window, and a member
  that stays unavailable without transitions does not block it. A start whose members all read
  fresh in 2 s leaves `startup_recovery` at 2 s; one with a silent member leaves it at 60 s with
  that member counted unavailable. A declared power-evidence member's off-to-on, or 50 % of
  baselined members unavailable or changed at first read, yields `power_recovery`; 49 % does not.
  No Layer-0 rule names a fact type or reads the Layer-2 registry.
- `RuntimeHealthSnapshot` is refreshed outside engine evaluation and one completed cycle contributes
  exactly one bounded, O(1) monotonic latency sample and one O(1) process-CPU-time delta; the engine
  CPU usage is aggregated outside the cycle in CPU-seconds per second. A cgroup-v2 fixture verifies effective
  CPU/memory/pressure parsing; an unavailable or non-enforceable platform value remains absent with its
  capability unset, never a guessed host allocation. Probe failure and percentile aggregation neither
  block a cycle nor produce a `HouseFact`, semantic-resolver input, policy decision, or action (§9).
- A verified manual control edge by any authenticated user or an approved physical-control adapter
  on a registered Actuator channel emits one redacted `actuator.manual_control` event with
  `user_response` provenance and no raw HA identity/context; its `ControlActor` is `resident` for a
  resident (also when an administrator), `guest`, `administrator` for an installer with no Person,
  `device` for a tablet user with no Person, and `physical` for the adapter (CA4-119). Every class
  can open a hold with `origin="manual"` and that `manual_actor` when the edge qualifies under
  §6.2; an edge with no physically confirmed current admitted Reaction target opens none. The same edge from an unavailable
  channel, an unknown/automation/service context, or a duplicate ingress report emits none. A device that becomes unavailable after a dumb wall switch power-cut is
  persisted as an unavailable channel-state transition; it never becomes `off`, a manual-control event, an implicit
  hold, or a zero-correction observation, and recovery of availability cannot synthesize the missing
  intervening history (§5.1.1/§5.1.2).
- A staged channel publishes one bounded `actuator.channel_state.<digest>`
  state fact on first valid observation, physical change, availability change
  and the first post-restart observation, but no fact per identical HA report.
  A verified manual edge joins the unchanged three-field manual-control event
  by its unique edge id in the same durable cycle; an external/unknown or
  Heima-linked edge has no manual-control event. Two Actuators in one room retain
  distinct fact identities, and an oversized/ambiguous facet projection
  fails staging (§4/§5.1.1.1; Layer 2 §6.1).
- An eligible managed-episode opening and closure each append one bounded
  `reaction.managed_episode.<digest>` state transition in the ordinary
  end-of-cycle batch; repeated identical observations and speed changes append
  none. The latest state survives ordinary retention. A crash before opening
  commit, a malformed projection or a closed state yields no restart proof;
  neither a historical `complete_observation` nor a recovery target substitutes
  for it (§4.2–4.3/§5.1.1.2; Layer 5 §3.2).

---

## Related documents (background only, not required reading)

This spec incorporates and, where needed, revises decisions originally made in v2's
`core/manual_hold_framework_spec.md`, `core/runtime_checkpoint_and_power_recovery_spec.md`, and
`core/runtime_provenance_spec.md`, and in this planning branch's own `v3_architecture_recap.md`
(Layer 0), `v3_backlog.md`, and `v3_house_fact_draft.md` (§WHEN). Where this document and any of
those differ, this document is the current word for Layer 0's v3 design.
