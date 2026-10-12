# Heima v3 — Layer 1: Substrate Primitive

**Status:** Defined V3 contract. Not implemented.
**Layer:** 1 of 8. Builds directly on Layer 0 (`docs/specs/v3/layer0_runtime_spec.md`) — every
`HouseFact` is stored through Layer 0's Persistence facility, timestamped per Layer 0's Timing rules
(UTC, timezone-aware), and carries a Layer 0 `FactSource` inside its `Provenance`. This document
does not restate Layer 0's contract; it assumes the reader has it, since both are the same v3
architecture and Layer 1 does not exist without it.

This document is self-contained with respect to Heima's v2 specs: it defines what Layer 1 is and
does without assuming the reader has read them. Where v2 already solved a piece of this problem,
that solution is restated here in full, not referenced as a prerequisite — v2 documents are listed
at the end, background only.

## Normative precedence

This document defines the current V3 Layer-1 design contract. Open corrections are tracked in
the CA4 backlog; runtime implementation is a separate phase. When implemented, if code and
spec diverge, the divergence must be resolved explicitly — code is a
reference implementation, not the source of truth.

---

## 1. Purpose

Layer 1 defines the one durable assertion shape for Heima's house history: a sensor reading, a
fused derived state, or an operational occurrence such as a hold lifecycle event that must remain auditable. Anything
that asserts something is or happened in the house, somewhere and at a time, is a `HouseFact`; there
is no second, parallel representation for that same persistent assertion. This does **not** make
`HouseFact` a universal envelope for artifacts, transient inter-layer hand-offs, commands, or
configuration/review workflow records. Those objects answer different questions and have their own
typed lifecycle. Five concepts:

1. **`HouseFact`** — the universal persisted WHAT/WHERE/WHEN/HOW assertion record.
2. **`Provenance`** — the HOW envelope: confidence, availability, and the evidence behind them,
   wrapping Layer 0's `FactSource`.
3. **`Location`** — WHERE a fact is about: the whole house, one room, a declared zone, or an ad hoc
   room combination.
4. **`Zone`** — an admin-declared, named group of rooms.
5. **`Topology`** — how rooms physically relate to each other: room enclosure, what lies across
   every opening, passable connections, orientation, floors.

(`Zone` and `Topology` are both part of WHERE, listed separately from `Location` because they answer
different questions — see §6 and §7. A closed set of zone roles, §6.1, names the purpose-specific
groupings the core recognizes.)

## 2. Scope

Layer 1 is responsible for:
- the `HouseFact` shape itself, and the `fact_type` naming convention that identifies what a fact is;
- `Provenance` — the confidence/availability/evidence envelope every `HouseFact` carries, and the
  rules for computing and constraining each of its parts;
- `Location`, `Zone`, and `Topology` — the three complementary pieces of WHERE.

Layer 1 is **not** responsible for:
- `HouseFact` storage mechanics (batching, retention, the two-tier durable/in-memory split) — that is
  Layer 0's Persistence facility (§4 of the Layer 0 spec). Layer 1 defines what gets stored; Layer 0
  defines how.
- the non-forgeable source vocabulary inside `Provenance.source` (`FactSource`, its kinds, its
  non-forgeability rules, `correlation_id` generation) — that is Layer 0 (§5 of the Layer 0 spec).
  Layer 1 only defines the envelope `FactSource` sits inside.
- deciding which entities become facts, or how a raw entity state is interpreted into a `HouseFact`
  value (`Sensor`/`Interpretation`/`FusionRule`) — that is Layer 2.
- learning artifacts/results, typed transient signals, or proposal/review workflow records — Layer 3
  and Layer 5 own their respective contracts. A later authorized `SemanticResolver` may resolve their evidence
  into a declared `HouseFact`, but the hand-off object itself is not one.
- the `Room` registry itself (a room's name, type, floor as an inventory record) — `room_id` here is
  a stable reference into that registry, carried forward from today's existing room-inventory model
  unchanged; Layer 1 consumes `room_id` as an opaque identifier, it does not define what a room is.
  Topology (§7) requires only two attributes of that inventory: `floor` and `enclosure`
  (`interior` | `exterior`, default `interior`; CA4-62).

### 2.1 Non-goals

- Prescribing internal class layout beyond the shapes below.
- A general query language over `HouseFact` history — Layer 0 already establishes the query shape
  ("every `HouseFact` true in `Location` X between t1 and t2"); Layer 1 does not add to it.
- Resolving conflicts between simultaneously-true facts of different provenance (e.g. two `Sensor`s
  disagreeing) — that is a `FusionRule` concern (Layer 2), not something `HouseFact`/`Provenance`
  decide on their own.

### 2.2 Persistent assertions versus application contracts

The following boundary avoids using one generic record for different lifecycle and authority models:

| Shape | Owner and lifetime | `HouseFact`? | Meaning |
|---|---|---:|---|
| Sensor/fused/semantic state or durable operational occurrence | Layer 1 shape, persisted by Layer 0 | Yes | An assertion about the house or an auditable occurrence. |
| `ResultEnvelope` / model artifact | Layer 3 result and artifact lifecycle | No | Versioned analytical output and the evidence that produced it. |
| `InferenceSignal` | Layer 3 -> one authorized Layer 4 consumer, transient | No | Bounded current input for a `SemanticResolver`; it may be absent/expire without changing house history. |
| `LearningProposalCandidate` | Layer 3 -> Layer 5, transient | No | Candidate evidence awaiting Layer-5 validation, not an approved configuration or house assertion. |
| `ReactionProposal` | Layer 5 review workflow, persisted by its own contract | No | Review/configuration state with approval and lifecycle semantics. |
| `HeimaEvent` | Operational delivery envelope | No | Delivery payload; its durable audit representation is the separate event `HouseFact` in §3.1. |

This is not a competing state model. A `SemanticResolver` that accepts a valid `InferenceSignal` may produce its
own declared `HouseFact`; Layer 5 may emit auditable operational events while processing a proposal.
The transient input and workflow record are nevertheless not retroactively facts. This follows the
usual separation between persisted domain events and in-process/application messages: their
implementation and transaction lifecycle differ even when both carry domain-relevant information
([Microsoft domain versus integration events](https://learn.microsoft.com/en-us/dotnet/architecture/microservices/microservice-ddd-cqrs-patterns/domain-events-design-implementation),
[AWS event sourcing](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/event-sourcing-pattern.html)).

---

## 3. `HouseFact`

```python
EvidenceInstant = str  # one canonical UTC instant: YYYY-MM-DDTHH:MM:SS.ffffff+00:00 (§4)

@dataclass(frozen=True)
class HouseFact:
    fact_type: str        # namespaced, dot-separated identifier — see naming convention below
    value: Any             # interpreted payload: a bucket label, an enum member's own primitive
                            # value (its `.value`, e.g. a str/int — never the Enum member object
                            # itself, which isn't EvidenceValue-shaped, see below), a bool, a
                            # structured dict, or a small frozen dataclass (e.g. HoldLifecycleValue,
                            # Layer 0 §6.1) — semantically untyped (one universal shape must
                            # accommodate every kind of fact, and a closed *value* type would just
                            # push the same variability into a wrapper type one level up), but not
                            # unconstrained in shape — see below
    where: Location         # WHERE — §5
    when: EvidenceInstant  # WHEN — the same canonical instant used by every V3 contract (§4)
    how: Provenance         # HOW — §4
```

**`value`'s `Any` annotation is not the whole story — it carries the same storage-safety constraint
as `evidence` (§4.3), for the same reason.** Every `HouseFact`, `value` included, is written through
Layer 0's Persistence facility exactly like `evidence` is, so the same class of accidental leak
applies: a raw Home Assistant `State` object, a binary blob, an arbitrary custom object would break
serialization or dump a raw payload wholesale into durable storage. `value` must be either
`EvidenceValue`-shaped (§4 — JSON primitives or shallow collections of them), **or** a frozen
dataclass instance whose own fields normalize recursively to `EvidenceValue` — the second
form is what lets a producer report a small, named structured value (`HoldLifecycleValue` as defined by Layer 0 §6.1) without collapsing it
into a bare dict and losing its type identity. Python's type system cannot express "any frozen dataclass
with JSON-primitive fields"
as a static union, so this is a **normative construction rule, validated procedurally** — the same
discipline already applied to `Location` (§5) — not something the `Any` annotation itself enforces.
Same nesting-depth and size limits as `evidence` apply, for consistency, not because the two fields
are interchangeable.

For `manual_hold.lifecycle`, the fact value is always the complete
`HoldLifecycleValue` defined by Layer 0 §6.1. Staging must prove that every
permitted transition fits this value contract (Layer 0 §6.1 staging proof and §6.4 runtime validation); construction still
validates the actual value. No detail reference or alternate fact shape exists.

`validate_house_fact_value(value) -> None` is Layer 1's pure, side-effect-free enforcement point for
that complete contract: it accepts an `EvidenceValue` or qualifying frozen dataclass only, recursively
checks finite floats and maximum depth 2, normalizes a permitted dataclass to its field payload for
both depth counting and canonical UTF-8 size measurement, and rejects a result over 8 KiB.
Within a qualifying frozen dataclass, an immutable tuple of permitted values
normalizes to a JSON list before validation; an ordinary `EvidenceValue`
outside that dataclass still does not admit tuples. The normalized list
counts as a collection and meets the same depth and size limits.
The normalized dataclass field object is depth 1; its mapping/list fields are depth 2;
a collection inside one of those fields is depth 3 and invalid. Scalars do not add
collection depth. `HouseFact` construction calls it;
Layer 2 also calls it during staging for every static value that one of its interpretations can emit.
This is one value contract with two entry points, not a second interpretation-specific validator.

**Collection depth is counted one way everywhere.** A scalar has depth 0; every enclosing list,
mapping or normalized frozen-dataclass field object adds 1. `HouseFact.value`, `Provenance.evidence`
and `PersistedProjection` each allow a maximum depth of 2: a top-level mapping or list whose members
are scalars or one further collection of scalars.

**Deep immutability.** Construction freezes `value` and `evidence` once, in the same validation
pass that measures depth and canonical size: every mapping becomes a read-only mapping and every
list becomes a tuple, recursively, and a frozen dataclass value is retained only with frozen
fields. Equality and hashing use the canonical serialization. Canonical JSON still serializes a
frozen sequence as a JSON array, so the wire form is unchanged; the tuple is an in-memory
representation, not an admitted input type outside a qualifying dataclass. The same freeze applies
to a `PersistedProjection` retained by Layer 0. Consumers therefore share one value without
defensive copies, and no consumer can alter a fact or projection held by another component.

**Shared canonical JSON rule.** Every V3 reference to canonical JSON, canonical UTF-8 JSON,
canonical serialization, or a fingerprint/digest derived from JSON means the JSON Canonicalization
Scheme ([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html)): recursive object-key sorting on raw
property names as UTF-16 code-unit sequences, ECMAScript-compatible primitive serialization, and
UTF-8 output. Duplicate property names and lone surrogate code units are invalid; Unicode strings are
otherwise preserved without normalization. A contract may impose a stricter input rule (for example
Layer 3 rejects negative zero), but may not substitute a different JSON ordering or formatter. An
array whose order is semantically defined by this specification is sorted first by that stated rule;
RFC 8785 then preserves that array order. This distinction keeps semantic sets deterministic without
creating a second object-key canonicalizer.

**Home Assistant boundary.** A Home Assistant `State` object, its complete attributes mapping, event
context, or any other HA runtime object is boundary input only: it may be inspected while a binding
extracts its declared raw scalar, but is never retained by reference or serialized into `value`,
`evidence`, `Provenance`, a `HouseFact`, or any Heima-owned payload. A producer that needs selected HA
data creates a copied, normalized, schema-declared `EvidenceValue` projection instead. The resulting
fact is therefore independent of HA's mutable in-memory object graph after construction.

**Numeric scalar rule.** `bool` remains a valid semantic `EvidenceValue`, distinct from a number.
Every `float` anywhere inside an `EvidenceValue` (including nested collections and frozen-dataclass
fields) must be finite: `NaN` and either infinity are invalid because they are not canonical JSON
values. A field declared by a contract as a quantitative number accepts only a non-boolean `int` or
finite `float`; it must never accept Python `True`/`False` as `1`/`0`. This leaves explicitly boolean
fact values and configuration flags valid.

**`value` has no contractual relationship to `available` (§4.1) — considered and rejected.** An
earlier draft required `value=None` whenever `available=False`, mirroring `confidence`'s own
`None`-when-unavailable rule. Dropped: `available: bool` is already the sole, sufficient signal for
"does this fact carry a usable value" — requiring `value` to *also* encode that fact is pure redundancy,
two fields that must be kept in sync for no benefit (unlike `confidence`, see §4.1, where making the
field itself `Optional` buys real protection from a type-checker; `value: Any` cannot buy that
protection under any convention, `Any` accepts everything regardless). `value`'s content is simply
**undefined** when `available=False` — a producer may leave it at `None` out of habit, or at a stale
prior value, or anything else; it carries no meaning either way, and no consumer may read `value`
without checking `available` first, full stop.

**Naming convention for `fact_type`**: dot-separated, namespaced, stable identifiers — `presence`,
`occupancy`, `activity.<activity_id>`, `presence.planned_absence`, `room_signal.bucket`,
`heating.temperature_rate`,
`manual_hold.lifecycle` (Layer 0 §6), `external.<slot>` (`slot` names one externally-sourced context
value — e.g. outdoor temperature or a weather-safety flag from an adapter like OWM or Protezione
Civile, Layer 2's own worked example for `Sensor`). This reuses the same convention Heima's
existing event catalog already establishes for its `type` field (`people.arrive`,
`presence.planned_absence`, `lighting.<detail>` — a stable, hierarchical, human-readable taxonomy),
rather than inventing a second one.
The convention is enforced by usage, not by the type itself — `fact_type` is a plain `str`, not a
closed enum, because new fact types are added routinely (a new `Sensor` registration, a new learned
pattern) and a closed vocabulary here would fight that.

Each concrete identifier has one or more non-empty segments separated by `.`, and may not contain `*`:
the asterisk is reserved exclusively for Layer 0's `FactTypeClaim` glob patterns, never persisted as
part of a fact type. Segment characters otherwise retain their exact Unicode code-point identity;
there is no trim, case-folding, or normalization at this boundary.

A source-level observation may include a stable Heima registry id as its final namespace segment when
several observations of the same semantic kind must coexist at one `Location`; Layer 2 reserves this
shape for room-occupancy evidence as `occupancy.evidence.<kind>.<sensor_id>`. That suffix identifies
the configured logical reading, never a mutable Home Assistant `entity_id`; Layer 2's fused physical
meaning is `occupancy.physical`, while Layer 4 alone resolves the unsuffixed semantic `occupancy`.

**A `HouseFact` is an atomic persistent assertion, not a generic message, command, or state
machine.** Its producing contract (Layer 0 §4) declares whether that assertion is a state that holds
now (for example, `occupancy=true`) or an occurrence that happened at `when` (for example, a channel hold was released). Both use this one immutable shape; neither encodes a multi-step transition
protocol, an intent to act, an ML artifact/result, a transient `InferenceSignal`, or a proposal/review
workflow record. A duration is still read by comparing facts' `when`, or via a `Window` (Layer 0
§3.2). An `ApplyStep` (Layer 5) is the corresponding command shape; a `HouseFact` never is one.

### 3.1 Operational-event mapping

`HeimaEvent` is the operational envelope consumed by the notification pipeline, not a second durable
record model. Its durable audit representation is exactly one `HouseFact` whose producer has declared
`FactEmissionKind="event"` (Layer 0 §4):

```python
EventSeverity = Literal["debug", "info", "warning", "error", "critical"]

@dataclass(frozen=True)
class OperationalEventValue:
    notification_key: str                 # non-empty stable delivery dedup/rate-limit key
    severity: EventSeverity                # delivery/diagnostic priority, never fact identity
    title: str                            # rendered event title retained for audit
    message: str                          # rendered event message retained for audit
    context: dict[str, EvidenceValue]      # event-specific, JSON-compatible payload
```

| `HeimaEvent` field | `HouseFact` representation |
|---|---|
| `type` | `fact_type` in V3's approved stable taxonomy; a V2/legacy type is not admitted to V3 |
| `key` | `value.notification_key` |
| `severity` | `value.severity` |
| `title` / `message` | `value.title` / `value.message` |
| `context` | `value.context` |
| `ts` | `when`, UTC and timezone-aware |
| `event_id` | transient delivery identifier only; neither fact identity nor a separate durable field |
| event location | `where`; mandatory, supplied by the typed producer; `Location(scope="casa")` only when the event is intrinsically house-wide |
| causal context | `how.source.correlation_id`, with ordinary Layer-0 propagation rules |

The event adapter must construct this value at the production boundary and validate the non-empty key,
allowed severity, non-empty title/message, `context` shape, and mandatory `Location`; it must never
guess a room from unstructured context. A V3 `HeimaEvent`, where a delivery/rendering envelope is
still useful, is derived from this event fact and cannot be an independently persisted or audited
channel. Historical V2 events remain outside V3 as archive/rollback material: V3 has no legacy-event
adapter, type map, or runtime fallback, and every V3 producer must emit an approved V3 fact type.

Persistence appends every distinct event occurrence, including otherwise equal payloads. Narrow
producer-owned operation-id protocols are exceptions: `manual_hold.lifecycle` retries are
idempotent under Layer 0 §6.4, every Layer-6 notification kind (including `reaction.follow_up`
and `automation.availability`) is appended once per `(notification_kind, operation_id)` under §4.5,
and `actuator.target_lifecycle`, `actuator.correction` and
`actuator.resident_control` deduplicate by their own stable event/edge ids
under Layer 0 §4.2. None uses
`notification_key` as fact identity. That key is consumed by Layer 6's delivery policy for its
configured deduplication and rate-limiting window. Thus a suppressed repeat delivery remains visible in the audit
trail, while `severity` may affect rendering, route selection, escalation, and diagnostics but never
the fact's identity, ownership, retention semantics, or causal correlation. Event consumers must not
derive a live state from this value; a current claim needs a separate `state` fact by Layer 0 §4.

`actuator.resident_control` and `actuator.correction` are also reserved V3 `event` fact types,
but are audit/learning evidence, not rendered `HeimaEvent`s. Their sole producers and closed
values are Layer 0 §5.1.1 and Layer 5 §6.1 respectively, under Layer 0 §4's exclusive
`FactTypeClaim`s. Neither uses `OperationalEventValue` or creates a resident notification by
itself; both still follow the ordinary `HouseFact` envelope and event-history rules.
`actuator.target_lifecycle` is another non-rendered event fact, owned only
by Layer 5 §6.1 for admitted decision/complete-observation/close history.
`actuator.channel_state.<digest>` is the distinct Layer-0-owned **state**
fact for one registered channel (Layer 0 §5.1.1.1); its bounded facet
projection changes only on physical state/availability changes and the
first valid post-restart observation. Neither record is an operational
notification or a new live command authority.

`reaction.follow_up` is an approved V3 event fact type. Its sole persistent producer is the
Layer-6 adapter: it validates Layer 5's typed `ReactionFollowUpOccurrence`, renders the
resident title/message and maps the occurrence's fixed scalar fields to `context` as defined
by Layer 5 §6.0. Its `expected_facets` and `observed_facets` maps become
`expected.<facet>` and `observed.<facet>` canonical JSON-text scalar entries, not nested
context objects. `subject` becomes `where` and `occurred_at` becomes `when`, never duplicate
context fields. Layer 6 applies Layer 5's closed facet grammar, projection and size bounds,
rejecting unexpected, missing or noncanonical entries before the atomic event/outbox
transaction (Layer 5 §6.0; Layer 0 §4.5). The durable intent is a `PersistedProjection`,
never a second event fact.
`automation.availability` is one approved V3 event fact type. Its sole producer is Layer 6's
core-owned availability-event adapter. Layer 6's transient `AvailabilityEpisodeTracker` receives the
typed suppression occurrence from its owner, reconciles the current episode against the staged
publication generation, and invokes this adapter only for a resident-visible delivery. The adapter
renders the event's title/message and constructs the canonical notification key, severity and bounded
context, then appends the event fact together with its `ready` delivery record in the unified
notification outbox (Layer 0 §4.5); neither Layer 3, Layer 4 nor Layer 5 may pre-render or persist that
event. Layer 0 reserves its exclusive event claim. Every notification Layer 6 delivers follows this
same audit-fact-plus-outbox rule.
`reaction.advisory` is one approved V3 event fact type: a resident-facing suggestion that a
configured Reaction produced instead of a command (Layer 5 §6.0). Its sole producer is the Layer-6
advisory adapter, which validates Layer 5's typed `ReactionAdvisoryOccurrence` and maps its fixed
fields to `context` under the same rule.
`recovery.confirmation_request` is one approved V3 event fact type: the opening or closing of a
power-recovery confirmation request (Layer 0 §7.4.1). Its sole producer is the Layer-6
recovery-confirmation adapter, which renders the actionable notification from Layer 0's typed
`RecoveryConfirmationOccurrence`; the answer returns only through Layer 0's response ingress.

---

## 4. `Provenance`

```python
EvidenceValue = str | int | float | bool | None | dict[str, "EvidenceValue"] | list["EvidenceValue"]
PersistedProjection = dict[str, EvidenceValue]

@dataclass(frozen=True)
class Provenance:
    confidence: float | None                   # 0.0-1.0, or None — see §4.1/§4.2
    source: FactSource                          # Layer 0 §5 — never a free string
    available: bool = True
    evidence: dict[str, EvidenceValue] = field(default_factory=dict)
```

`EvidenceInstant` is a semantic subtype of `str`, not a new runtime object admitted to
`EvidenceValue`. Every V3 contract field declared as an instant, including
`HouseFact.when`, job due times, calendar windows, model artifacts and
Reaction records, uses this one canonical form:
a timezone-aware UTC ISO-8601 value with exactly six fractional-second digits and the literal
`+00:00` offset (for example, `2026-09-08T14:30:00.000000+00:00`). Producers normalize before
constructing the fact; consumers that make a decision from such a field parse and validate that exact
form. A naive `datetime`, a non-UTC offset, or a merely arbitrary string is never a valid
`EvidenceInstant`.

`PersistedProjection` is the deliberately narrow contract for a named structured value retained by a
Layer-0 durable facility without making it a `HouseFact` (for example, one recovery target). Its keys and values are copied and normalized, not retained from an
HA object. It admits no frozen dataclass or arbitrary object: it is a JSON mapping whose values obey
the ordinary `EvidenceValue` rule, have maximum nesting depth 2, contain only finite floats, and have
canonical UTF-8 serialization of at most **8 KiB**. It is a persistence boundary, not a general
configuration type: registry configuration has its own contracts and limits.
The hold-audit queue retains an already validated complete `HouseFact`; it
does not introduce a non-fact projection or an exception to this contract
(Layer 0 §6.4).

### 4.1 `available`

A plain boolean: does this `HouseFact` carry a usable value for the claim it represents at `when`, or
can its producer make no such assertion this cycle? A failed/unreachable source is one cause, but not
the only one: a raw reading can be present yet fail its declared interpretation, and a derived producer
can lack enough usable input to produce its output. `available` deliberately exposes the common result,
not a global taxonomy of those producer-local causes.

`available=True` means consumers may read `value` as the producer's assertion. `available=False` means
consumers must treat `value` as undefined (§3) and `confidence` as `None`; the detailed cause belongs
only in local diagnostics or non-load-bearing `evidence`, never in a new shared `Provenance` enum. This
keeps every consumer on one stable binary contract while allowing each producing layer to state its own
precise failure conditions.

**Staleness is not a `Provenance` field at all — it was
considered and rejected.** An earlier draft of this section had a tri-state `Freshness`
(`FRESH`/`STALE`/`UNAVAILABLE`) computed from elapsed time against a stored maximum-age threshold.
Two problems, found while working through it, not just a naming issue:

- "Is this fact still trustworthy" is a question relative to **whoever is asking, right now** — a
  dwell timer might tolerate a stable state for hours if observation remains continuous; a
  report-driven source might require a new report within seconds. There is no single "freshness"
  value that serves every consumer, so baking one shared answer into `Provenance` would be
  presumptuous regardless of how it's computed.
- Even setting that aside, a *stored* staleness classification cannot stay correct on an immutable,
  write-once `HouseFact` — elapsed time keeps changing after the fact is written, so a `FRESH` fact
  would silently become wrong hours later with nothing rewriting it. This is exactly why `Window`
  (Layer 0 §3.2) is explicitly a **live, read-time** comparison, never a stored value — the same rule
  applies here. Any consumer that cares whether a fact is too old for its purposes computes
  its declared source-validity and observation-coverage gates at read time.
  For a state fact, `when` is the last accepted state-change instant; it is
  **not** the last time an identical value was reported or the end of an
  observation period. An old `when` alone cannot make an otherwise continuously
  observed state stale. Layer 2 §3.2 owns optional source-report age; Layer 0
  §4.4 owns interruption coverage. Occurrence facts retain their own event
  instant and are never extended as current state.

`available`, by contrast, is genuinely different in kind and earns its place as a stored field: it is
not a question of elapsed time at all, and it cannot be derived from absence of a recent fact —
Layer 0's write-on-change policy (§4.2 of the Layer 0 spec) means "no new fact this cycle" is the
**normal, expected** state for anything unchanged, so absence can never be read as "unavailable"
without creating a false positive for every ordinary stable value. Unavailability has to be a
positive signal, recorded at the moment the producer cannot form a usable assertion, which is precisely
the kind of thing that is correctly static and correctly stored once.

**`confidence` is `None` exactly when `available=False`, never a numeric placeholder.** An earlier
draft of this section used `0.0` for this case — rejected: `0.0` is a legitimate, meaningful point
inside the real `0.0`-`1.0` range, so a consumer that forgets to check `available` first would read a
plausible-looking "very low confidence" instead of an unmistakable "not applicable." Unlike a magic
number, `float | None` lets a type-checker flag a producer or consumer that touches `confidence`
without narrowing `available` first — a mistake stays *visible*, not silently plausible. This is a
real, independent benefit specific to `confidence`'s own narrow type, not shared by every field that
happens to correlate with `available` — `value` (§3) correlates with `available` exactly the same
way but gets no such benefit from being made `Optional`, because `value: Any` accepts anything either
way and a type-checker can't narrow `Any` into meaning anything; `value` is deliberately left with no
`None` requirement for that reason, not by oversight. Every producer must set `available=False` and
`confidence=None` together, never `available=False` with a numeric `confidence`, and never
`available=True` with `confidence=None`.

**Construction validation is mandatory.** `Provenance` rejects a boolean or non-finite confidence, or
one outside `[0.0, 1.0]`; it also rejects either inconsistent availability pair above. These are
invalid facts, not degraded observations, so construction fails loudly rather than silently correcting
a value.

### 4.2 `confidence`

**A closed, deliberately small set of standardized forms — never an ad hoc, uncentralized formula
reinvented per producer.** This standardization exists because an audit of the current codebase found
four different, mutually incompatible formulas across modules all called "confidence," not comparable
to each other, one of them (`min(1.0, support / min_support)`) actually wrong — mistaking data volume
for confidence. **The lesson from that audit is discipline, not a hard cap of two**: every confidence
computation goes through a function Layer 1 owns and vets, never one a producer writes itself at its
own call site. The set can grow — deliberately, rarely, the same way `FusionStrategy` (Layer 2) grew a
fifth member instead of staying artificially capped at four — when a genuinely distinct, principled
computation pattern is found, not when a producer wants a shortcut.

```python
from math import isfinite

def categorical_confidence(count_best_outcome: float, total_observations: float) -> float:
    """A true match ratio, P(outcome | pattern). `total_observations` is deliberately general — the
    population being matched against, whether historical pattern occurrences (Layer 3) or same-cycle
    evidence being combined right now (a Layer 2 FusionRule's votes). The formula's meaning (how much
    of the evidence agrees with the reported outcome) is identical either way.

    Preconditions: both arguments are finite; total_observations > 0 (never called with zero — see
    below); 0 <= count_best_outcome <= total_observations. The function validates these conditions and
    raises ValueError on violation, even though its callers validate their own configuration earlier —
    resolved 2026-09-07: found in review that nothing previously stopped a caller error (e.g. double-counting one vote) from
    producing an out-of-range result (count_best_outcome=6, total_observations=5 -> 1.2), silently
    violating Provenance.confidence's own 0.0-1.0 contract (§4) from inside the one function this
    architecture centralizes confidence in specifically to prevent that class of mistake."""
    if (
        isinstance(count_best_outcome, bool)
        or isinstance(total_observations, bool)
        or not isfinite(count_best_outcome)
        or not isfinite(total_observations)
        or total_observations <= 0
        or not 0 <= count_best_outcome <= total_observations
    ):
        raise ValueError("invalid categorical confidence population")
    return count_best_outcome / total_observations

def continuous_confidence(dispersion: float, scale: float, floor: float) -> float:
    """Inverse dispersion. `floor`/`scale` are named parameters supplied by the caller, never ad hoc
    magic numbers at the call site.

    Preconditions: every argument is finite; scale > 0 (a zero or negative scale makes the
    normalization meaningless — the caller chooses a scale appropriate to its own value's units and
    must never pass zero); dispersion >= 0 (a dispersion is a spread, never negative by construction);
    0 <= floor <= 1. The function validates these conditions and raises ValueError on violation —
    resolved 2026-09-07: without these, e.g. continuous_confidence(dispersion=-2.0, scale=1.0,
    floor=0.0) returns 3.0, or a floor passed as 1.5 forces every result above 1.0 regardless of
    dispersion, the same class of contract violation categorical_confidence was found exposed to."""
    if (
        isinstance(dispersion, bool)
        or isinstance(scale, bool)
        or isinstance(floor, bool)
        or not isfinite(dispersion)
        or not isfinite(scale)
        or not isfinite(floor)
        or dispersion < 0
        or scale <= 0
        or not 0 <= floor <= 1
    ):
        raise ValueError("invalid continuous confidence parameters")
    return max(floor, 1.0 - dispersion / scale)

def combined_confidence(confidences: Sequence[float], combinator: Literal["min", "max"]) -> float:
    """For a deterministic logical combination (AND/OR) over several sources' own confidence values
    — not a statistical match-ratio (no "population" here, just already-known inputs). `min` for a
    conjunction: a logical AND is only as trustworthy as its weakest premise. `max` for a disjunction:
    a logical OR is as trustworthy as its strongest confirming premise. Never a mean — averaging would
    let a weak AND premise get diluted by strong ones, or a weak OR confirmation get dragged down by
    irrelevant weak ones, neither of which matches how a boolean combination's own reliability
    actually behaves.

    Typically combines 2+ sources, but a length-1 call is a legitimate degenerate case, not an error —
    e.g. a Layer 2 `UnanimityStrategy` with `min_available=1` (its own default) can validly have exactly
    one available/confirming/dissenting source this cycle; `min`/`max` of a singleton is that source's
    own confidence, unchanged, which is the mathematically correct answer, not a special case this
    function needs to guard against (clarified 2026-09-07 — an earlier draft of this docstring
    overclaimed "not a passthrough (more than one source feeds it)" as if that were an enforced
    precondition rather than the typical case).

    Preconditions: `confidences` is non-empty (same "no meaningful confidence for nothing observed"
    rule as the other two — an empty combination is `available=False`, §4.1, not a call to this
    function), and every confidence is finite and in [0.0, 1.0]. The function validates these
    conditions and raises ValueError on violation."""
    if (
        combinator not in ("min", "max")
        or not confidences
        or any(
            isinstance(confidence, bool)
            or not isfinite(confidence)
            or not 0 <= confidence <= 1
            for confidence in confidences
        )
    ):
        raise ValueError("invalid combined confidence inputs")
    return min(confidences) if combinator == "min" else max(confidences)
```

**Neither `categorical_confidence`/`continuous_confidence` is ever called with a zero/empty
population, and `combined_confidence` is never called with an empty sequence — that case is
`available=False`/`confidence=None` (§4.1), not a degenerate confidence.** This is exactly the kind of edge case
centralizing these formulas exists to handle consistently, so it needs to be stated explicitly, not
left implicit: a `PatternLearner` already guarantees `total_observations > 0` by construction
(`min_support` is checked, and gates on a positive count, before confidence is ever computed). A
`FusionRule` producer must apply the same discipline itself — if every input to a fusion is itself
`available=False` this cycle, the derived `HouseFact` is `available=False` too, and none of these
functions is called at all. There is no meaningful confidence for a value that was never actually
produced.

**Layer 1 owns these three functions as pure, shared, callable implementations — it does not decide
when any of them applies.** That decision requires knowing what's actually being combined or
predicted, which only the producer has: a `PatternLearnerConfig`'s declared `target_shape` (Layer 3),
or which `FusionRule` strategy produced a value and which of its inputs' confidences feed the
combination (Layer 2) — Layer 1 has no visibility into either and should not need any to provide
three correctly-implemented functions. This split matters concretely, not just as a layering nicety:
the standardization exists because an audit found **four incompatible formulas**, all called
"confidence," scattered across modules — if every producer reimplemented the arithmetic itself
instead of calling one shared, tested function, the same drift risk (a subtly different edge-case
handling here, a rounding difference there) would reappear even with the "right" formulas nominally
agreed on. One canonical implementation per pattern, called from wherever it's needed, is what
actually prevents that — not just documenting the formulas and trusting every call site to copy them
faithfully.

**A fourth legitimate option, not a fourth formula: inherit, don't compute.** Some producers select or
pass through one specific upstream fact unchanged rather than combining several (a `FusionRule`'s
direct-passthrough or precedence strategy, Layer 2) — for these, `confidence` is simply the selected
source's own `confidence`, carried forward as-is. This is not a new formula requiring Layer 1 to
define anything further; it is the absence of a new computation. A raw `Sensor`-sourced fact, having
no upstream fact to inherit from and no "target shape" to predict, defaults to `1.0` when
`available=True` under the same principle — a direct reading is either available and fully trusted,
or `available=False`/`confidence=None` (§4.1) expresses its absence, never a numeric value in
between. Reporting anything other than `1.0` for an available raw reading requires a concrete
evidentiary reason (e.g. a sensor known to be noisy), not a guess.

**No consumer ever needs to know which of these applied to a given fact.** This is precisely the
point of standardizing to a small set of comparable, normalized forms: a `confidence` value means the
same thing regardless of which path produced it, so nothing about which formula (or whether
inheritance) was used is ever recorded on the `HouseFact` itself — doing so would reintroduce the kind
of producer-specific interpretation the standardization exists to eliminate. A producer may optionally
note its own method in `evidence` (§4.3) for diagnostic purposes, but this is never load-bearing for
how the number is read downstream.

**`min_support` is not part of `confidence`.** A per-learner minimum-sample threshold is a separate,
boolean pass/fail gate — "is there enough data to trust this signal at all" — evaluated before
`confidence` is computed, never blended into the float itself. This is exactly the formula found
concretely wrong in the audit above, and it stays wrong for the same reason: sample volume and
epistemic confidence are different questions, and conflating them silently reports high confidence
for a pattern that is really just "seen a lot," which is not the same claim.

### 4.3 `evidence`

Supporting detail: a raw sensor state before interpretation, which `FusionRule` strategy produced a
derived fact and from which inputs, why a `PatternLearner` tier matched. A producer may use it
for small, specific diagnostic detail, not as a dumping ground for large payloads. Hold lifecycle transition fields belong in their typed event value
(Layer 0 §6.1), not in an old restoration-evidence map.

**Constrained to a JSON-compatible shape, not `dict[str, Any]`.** `evidence: dict[str, EvidenceValue]`
(§4, `EvidenceValue` defined there) — values are limited to JSON primitives (`str`/`int`/`float`/
`bool`/`None`) or shallow collections of them, **maximum nesting depth 2** under the single
collection-depth rule of §3 (the `evidence` mapping is depth 1; one nested mapping or list of
scalars is depth 2). This is
mechanically enforceable and catches, at construction time, an entire class of accidental leak that a
content-based rule cannot: a raw Home Assistant `State` object, a binary blob, an arbitrary custom
object — none of these fit `EvidenceValue`, so a producer cannot accidentally dump one into `evidence`
the way it could dump one into an unconstrained `Any`-typed field.

**A total serialized-size cap applies on top of the shape constraint**: canonical UTF-8 serialization
of `evidence` is at most **8 KiB**. The same 8 KiB limit applies to `HouseFact.value` after a frozen
dataclass, if present, is normalized to its field payload (§3). This makes "not a dumping ground for
large payloads" an enforced rule rather than an aspiration: even a shape-valid dict cannot retain an
unbounded HA-derived blob. The limit is checked while the payload is already normalized/serialized for
fact construction; it adds no I/O or retained raw HA object to the evaluation path.

**Violation policy: fail soft, not hard — this is a fixed, deliberate choice, not an unspecified
detail left to whoever implements it.** `evidence` is explicitly supporting detail, not essential to
what a `HouseFact` means (§4 intro) — a shape or size violation drops `evidence` back to `{}` for
that specific fact and raises a diagnostic event (Layer 0 §10). A non-finite number anywhere in
`evidence` is such a violation: it discards only `evidence`, never the fact. The `HouseFact` itself is
still created with its `fact_type`/`value`/`where`/`when`/`confidence`/`source`/`available` intact.
Aborting the entire fact over a malformed `evidence` payload would be disproportionate — it would
mean a bug in optional diagnostic detail can silently blind a semantic resolver to a real observation. This is
the opposite policy from `value` (§3): a `value` violation is a hard construction failure, because a
`HouseFact` with no valid payload isn't a degraded fact, it's not a fact at all.

**What the shape constraint does *not* catch, and stays a normative rule instead**: a JSON string can
still legitimately contain a secret, a token, or a precise GPS coordinate — no generic structural
validator can tell "this string is a room name" from "this string is a credential." `evidence` must
never carry secrets, tokens, credentials, or precise geolocation; this is enforced by producer
discipline and review, the same way Layer 0's checkpoint allowlist is curated by hand rather than
inferred — not a contradiction of the mechanical checks above, a different, necessary layer on top of
them. The same restraint that keeps Layer 0's checkpoint minimal applies here for the same reason:
`evidence` explains a fact, it does not duplicate the fact's own history or the raw state behind it
wholesale.

### 4.4 Deliberately not part of `Provenance`

Two things that could plausibly be mistaken for epistemic trust, and are not:

- **`importance`** (`OBSERVE`/`SUGGEST`/`ASSERT`) decorates how a specific consumer *uses* a fact
  (e.g. Layer 3's `InferenceSignal` wrapper), not the fact's own inherent trustworthiness — two
  signals can share the same `confidence` and differ in `importance`. It lives on the consuming
  wrapper, never on `Provenance` itself.
- **Review status** (`pending`/`accepted`/`rejected`, on a `ReactionProposal`, Layer 5) is human
  governance state, not epistemic trust — a proposal's `confidence` doesn't change because an admin
  hasn't reviewed it yet.

---

## 5. `Location`

```python
ScopeKind = Literal["casa", "room", "zone", "rooms"]

@dataclass(frozen=True)
class Location:
    scope: ScopeKind
    room_id: str | None = None               # populated iff scope == "room"
    zone_id: str | None = None               # populated iff scope == "zone"
    room_ids: frozenset[str] | None = None   # populated iff scope == "rooms"; at least 2 entries —
                                               # a single-room set should use scope="room" instead
```

`ScopeKind` is only the closed vocabulary of Layer-1 `Location.scope`; it is
not a second scope object. A registry's `legal_scopes` restricts this
vocabulary, while the actual subject is always one validated `Location`.

**`Location` is always present on a `HouseFact`, never absent.** A whole-house fact belongs to
`casa` by definition — there is no "no location" case.

**Normative construction rule**: exactly one of `room_id`/`zone_id`/`room_ids` is populated, matching
`scope`; `casa` populates none of them; when `scope="rooms"`, `room_ids` has at least 2 entries — a
single-room set is malformed, it must use `scope="room"` instead (corrected 2026-09-08: this
cardinality floor previously lived only in `room_ids`'s own field comment, not stated as part of the
normative rule itself, unlike `Zone.room_ids`'s parallel "at least 1 entry" floor, §6, which the
construction rule there does state explicitly). An implementation must validate all of this at
construction, not leave it to convention — a `Location` with `scope="room"` and a populated `zone_id`
is malformed, and so is `Location(scope="rooms", room_ids=frozenset({"kitchen"}))`.

**Canonical identity and serialization.** Room, zone, and opening identifiers are opaque stable keys:
they are compared as the exact Unicode code-point sequence supplied by their owning registry, with no
trim, case-fold, Unicode normalization, or other implicit rewrite. A `Location` has exactly one
canonical key:

```python
LocationKey = tuple[str, ...]

# casa:  ("casa",)
# room:  ("room", room_id)
# zone:  ("zone", zone_id)
# rooms: ("rooms", *sorted(room_ids, key=unicode_code_point))
```

The `rooms` form is semantically a set, so its input order never matters; its canonical serialized
form is the `room_ids` array sorted by Unicode code point. `Location` equality, hashing, Layer 0's
`FactIdentityKey`, and Layer 2 producer registration all use this key. Its surrounding JSON follows
the shared RFC-8785 rule above; the code-point-sorted array is retained because it is the explicitly
defined semantic ordering of this set. Deserializing then reserializing a valid Location must
reproduce the identical key and JSON value.

Construction validates only shape, cardinality, and non-empty opaque identifiers. Whether an id exists
is resolved at the consuming registry boundary, not in `Location.__init__`: this permits configuration
objects to be loaded before the Room/Zone registries are fully assembled without allowing an unknown
reference to reach a running producer (§6/§7 and Layer 2 §2.3).

Four forms, not three, because one genuine case doesn't fit "a real, standing place":

- **`casa`** — the whole house, the root.
- **`room`** — a single room, by `room_id`.
- **`zone`** — a declared `Zone` (§6), by `zone_id`.
- **`rooms`** — an ad hoc, unnamed set of room ids, for a fact genuinely scoped to a
  dynamically-observed combination of rooms that isn't a standing, admin-declared `Zone` (e.g. a
  learned pattern found to hold across a specific pair of rooms that happened to be occupied
  together, discovered after the fact — not a group anyone declared in advance). The alternative —
  forcing every such fact to match an existing `Zone` or spawning throwaway zones for combinations
  nobody asked for — was considered and rejected: it either loses the ability to express "these
  specific rooms together" when no matching `Zone` exists, or pollutes the `Zone` registry with
  auto-generated groups that were never a real, admin-meaningful concept.

---

## 6. `Zone`

```python
@dataclass(frozen=True)
class Zone:
    zone_id: str
    display_name: str
    room_ids: frozenset[str]   # at least 1 entry — a zone naming zero rooms is meaningless. Unlike
                                # Location's "rooms" scope (§5), a single-room Zone is legitimate: a
                                # Zone is a standing, named, admin-declared concept an admin may
                                # reasonably create around one room today and grow later, not an ad
                                # hoc combination where a single entry would just duplicate scope="room"
```

An admin-declared, named group of rooms — Heima-owned data, not a live reference to Home Assistant's
own label/grouping features. HA's Label registry (and, separately, `Topology`, §7) can **suggest** a
zone at creation time, nothing more — once created, a `Zone` is plain Heima data with no ongoing
dependency on whatever suggested it. This matters concretely: a label renamed or deleted from HA's
own generic UI must never silently break a Heima reaction that depends on a zone.

**Membership is many-to-many, and zones are flat.** A room can belong to several zones at once (e.g.
a kitchen in both a "ground floor" zone and a "living areas" zone) — zones are not an exclusive
partition. A room's zones are found by scanning which `Zone`s reference it; nothing is stored on the
room side. Zones are **not nestable** — a `Zone` groups rooms directly, never other zones. `casa`
(via `Location.scope="casa"`) already serves as the implicit top-level grouping; recursive
zone-of-zones nesting is complexity with no concrete driving use case today.

**Zone identity is not its mutable definition.** `ZoneKey` is exactly `zone_id`; changing
`display_name` or `room_ids` does not change the identity of any `Location(scope="zone")` that points
to it. A Zone's canonical **definition** fingerprint is `(zone_id, display_name,
tuple(sorted(room_ids, key=unicode_code_point)))`, retained by Layer 2 for complete configuration
audit. Its **execution semantic** fingerprint is `(zone_id,
tuple(sorted(room_ids, key=unicode_code_point)))`: display text does not change the meaning of a
zone-scoped fact. Layer 2's reload impact comparison uses the latter, while retaining the former as
historical configuration metadata. `room_ids` serializes as a
Unicode-code-point-sorted array, while in memory it remains a `frozenset`. Zone construction rejects an
empty `zone_id`, empty `display_name`, empty membership, or empty room id; Zone registration resolves
every member against the Room registry and rejects a duplicate `zone_id`.

A changed definition is a new **configuration generation**, even though `ZoneKey` remains the same.
The generation snapshot and both fingerprints are durably retained by Layer 2's atomic reload
protocol, and every re-evaluated fact whose semantics depend on this Zone carries the resolved
execution semantic fingerprint in `FactSource.configuration_fingerprint` (Layer 0 §5). This preserves
historical meaning without
incorrectly changing a `Location(scope="zone")` identity: audit can determine which room membership
was in force for a fact rather than interpreting all records using today’s Zone definition.

### 6.1 Zone roles

A Zone is generic; the core recognizes a purpose only through a closed set of zone roles, each bound
by an administrator to at most one Zone:

```python
ZoneRole = Literal["thermal_envelope", "security_perimeter"]

@dataclass(frozen=True)
class ZoneRoleBinding:
    role: ZoneRole
    zone_id: str
```

A binding is Heima configuration data in the same composed generation as Zones and Topology (Layer 0
§4.7); a duplicate role or unknown zone is rejected, and a `thermal_envelope` Zone containing a room
whose enclosure is `exterior` is rejected. `thermal_envelope` defaults to all `interior`
rooms when unbound; thermal learning and comfort consumers read only that membership, never a room's
functional label. `security_perimeter` has no default and no Initial-V3 consumer; it reserves the
place where a future security perimeter is declared, instead of a stored connection classification.
A role binding adds no field to `Zone` and does not make zones exclusive or nested.

---

## 7. `Topology`

```python
@dataclass(frozen=True)
class Opening:
    opening_id: str
    room_id: str                     # the one room this opening belongs to (its "owner") — a plain
                                       # string key, the same opaque `room_id` convention `HouseFact`
                                       # itself uses (§2), not a `Location` — Topology is structural
                                       # graph data, not fact attribution, and its own `exposure_by_room`/
                                       # `floor_by_room` fields below are keyed by this same plain
                                       # `room_id`, never by `Location`
    type: str                        # e.g. "door", "window", "door_window"
    orientation: str | None = None   # compass orientation, populated for window-bearing openings —
                                       # this is exactly what `exposure_by_room` below is derived from
    entity_id: str | None = None     # an optional HA entity tracking this opening's live state — a
                                       # reference only; `Topology` itself never reads live entity
                                       # state, same non-live-dependency discipline as `Sensor.device_id`
                                       # (Layer 2 §3)
    other_side: str = "outside"      # what lies across this opening: a registered room id or the
                                       # reserved "outside". Declared for every opening, windows
                                       # included (added 2026-10-11, CA4-62); "outside" is the default

@dataclass(frozen=True)
class ResolvedConnection:
    room_a: str
    room_b: str                      # equals the opening's `other_side`; `"outside"` is the reserved
                                       # value for an opening that exits the house, not a real room
    opening_id: str                  # the passable `door`/`door_window` `Opening` it is derived from
    access_type: str = "direct"      # "direct", "stairs", or "elevator" (corrected 2026-09-08, same
                                       # error and same source of truth: was "normal"/"restricted",
                                       # neither a real value; real default is "direct", not "normal")

@dataclass(frozen=True)
class Topology:
    openings: tuple[Opening, ...]
    connections: tuple[ResolvedConnection, ...]
    exposure_by_room: dict[str, tuple[str, ...]]   # room_id -> sorted orientations of its
                                                     # window-bearing openings that face an exterior
                                                     # side (derived from `openings`, not
                                                     # independently authored; CA5)
    enclosure_by_room: dict[str, Literal["interior", "exterior"]]
                                                     # room_id -> enclosure, read from the Room registry's
                                                     # own `enclosure` attribute (default "interior");
                                                     # added 2026-10-11, CA4-62
    floor_by_room: dict[str, int]                   # room_id -> floor, read from the Room registry's
                                                     # own `floor` attribute (added 2026-09-08: this
                                                     # is not derived from `openings`/`connections` the
                                                     # way `exposure_by_room` is — it's a read-only
                                                     # aggregate view over data §2 already says Layer 1
                                                     # doesn't own or define, the same opaque-reference
                                                     # treatment `room_id` itself gets throughout this
                                                     # document; `Topology` here queries that external
                                                     # source, it does not redefine what "floor" means
                                                     # or where it's authoritatively stored
```

**Canonical topology definition and reference validation.** `Topology` is one installation-wide
structural record, not a collection addressed by an arbitrary topology id. Its canonical primary data
is `openings` sorted by `opening_id` and `connections` sorted by `opening_id`, both by Unicode code
point. `Opening.opening_id` values are unique; `ResolvedConnection.opening_id` values are unique; and
every connection's `opening_id` identifies one existing opening whose `room_id` equals that
connection's `room_a`. `room_b` is either a registered room id or the reserved literal `"outside"`.
This ownership rule makes a connection's direction canonical instead of allowing the same physical
relationship to be serialized with its endpoints swapped.

`exposure_by_room`, `enclosure_by_room` and `floor_by_room` are derived views, not independently authored input. On build or
deserialization the registry recomputes them from canonical openings plus the Room registry, orders
each exposure tuple by Unicode code point, serializes map keys under the shared RFC-8785 rule, and
removes duplicate orientations. A
serialized derived view that disagrees with this recomputation is rejected. Topology registration also
resolves every `Opening.room_id`, non-`outside` `Opening.other_side` and `ResolvedConnection.room_b`, and derived-view room key
against the Room registry; unknown ids, duplicate opening/connection ids, or a broken opening-owner
link are errors. A `ResolvedConnection` exists exactly for each passable `door` or `door_window`
opening and its `room_b` equals that opening's `other_side`; a `window` has no connection. Its
canonical fingerprint is the shared RFC-8785 serialization of those canonical
primary data and derived views.

**One physical model, purpose-specific questions (CA4-62, 2026-10-11).** Topology records only
physical facts: each room's `enclosure` (IFC `IfcSpace` internal/external semantics: `interior` is
enclosed by physical boundaries, `exterior` is not, e.g. a terrace or garden), what lies across every
opening (`other_side`), and which openings are passable. It stores no purpose-specific classification.
V2's derived `connection_type` (`indoor`/`outdoor`/`separate`, with an override) was a security
alarm-boundary classification mixed into the topology; it is not carried into V3. A room's functional
label (garage, basement, transit) is descriptive inventory and drives no rule. Every consumer uses
the same pure derived queries, defined once here:

- **exterior side**: a side is exterior when it is `outside` or a room whose enclosure is `exterior`;
- **`opening_faces_exterior(opening)`**: `True` when at least one side of the opening (its owner room
  or `other_side`) is exterior; a window toward a garage (`interior`) is therefore `False`;
- **thermal envelope membership**: the rooms of the `Zone` bound to role `thermal_envelope` (§6.1),
  or all `interior` rooms when that role is unbound.

Purpose-specific groupings that are not physical facts, such as the thermal envelope or a future
security perimeter, are Zones with a core role (§6.1), following IFC's `IfcZone` grouping of spaces.

A third, complementary piece of WHERE — genuinely distinct from both `Location` and `Zone`, not a
variant of either:

- `Location` says *which* place a fact is about.
- `Zone` says *an explicit group someone declared*.
- `Topology` says *how rooms physically relate to each other* — room enclosure, what lies across
  every opening, passable connections, orientation, floor.

**`Opening`/`ResolvedConnection` are restated here in full — corrected 2026-09-08.** An earlier
version of this section said they "carry forward unchanged in shape from Heima's existing
room-topology model... Layer 1 does not redefine them," without ever stating that shape — found in
review to be a real self-containment gap, more serious than the `Room`/`room_id` deferral it was
modeled on: `room_id` is genuinely opaque everywhere it's used (Layer 1 never inspects its internal
structure), but `Topology` uses `Opening`/`ResolvedConnection` as *structured* data with fields whose
meaning (`orientation`, `other_side`, `access_type`) a reader needs to actually understand what
`Topology` answers. The shapes above carry every field a Layer 1 consumer actually reads, matching
Heima's existing room-topology model (`custom_components/heima/room_topology.py`) — flattened only in
packaging, presenting the query-time, already-resolved view a Layer 1 consumer reads (`Topology` is
"queried, not consumed as a stream," below) rather than the admin-authored `Connection` shape that
produces it. One field is deliberately dropped in the flattening, `connection_id` (the real
`Connection`'s own stable identity, used for admin-side edit/delete) — not needed by anything that
only *reads* topology, and explicitly Layer 8's concern, not Layer 1's, consistent with leaving the
rest of `Connection`'s admin-authoring shape there too.

**`Topology` deliberately has no `casa` node — resolved 2026-09-02, not an oversight.** An early
planning note (predating `Topology`'s own separation from `Location`/`Zone`) said the whole-house
concept should become "an explicit node in the topology model." It doesn't, and shouldn't: a graph
node here represents something with a real physical adjacency relationship to other rooms (a room,
or the reserved `outside`) — "casa" isn't adjacent to anything, it **contains** every room, a
different kind of relationship entirely, one this graph isn't built to represent as a peer node.
Every whole-house topological question is answered as an **aggregate query over the existing
room-keyed structures**, never a lookup on a dedicated entry: "does the house have an outdoor
opening" is `any(opening_faces_exterior(o) for o in openings)` (revised 2026-10-11 under CA4-62;
the 2026-09-08 form `any(c.room_b == "outside" for c in connections)` missed windows and exterior
rooms; corrected 2026-09-08 — this example
previously queried `exposure_by_room` for the literal string `"outside"`, but `exposure_by_room`
holds compass *orientations* of window-bearing openings, e.g. `"north"`; it can never contain the
string `"outside"` at all, so the original query could never return `True` for any house, silently
reporting "no outdoor opening" always. `"outside"` is `ResolvedConnection.room_b`'s reserved value,
a different field entirely — found by re-deriving the example by hand against §7's own restated
`ResolvedConnection` shape, not caught when that shape was first written), not
`exposure_by_room["casa"]`; "how many floors" is `len(set(floor_by_room.values()))`, not a `casa`
entry that would have to mean something incoherent (a whole house doesn't have *a* floor). Whole-house
facts and actions already have a home entirely independent of `Topology` — `Location.scope="casa"`
(§5) — so nothing here was actually missing.

**`Topology` is not a fact producer and not a `FusionRule` input by itself.** It is queried, not
consumed as a stream — by `FusionRule`s, by Reactions, and by Reaction-descriptor requirements, when deciding
whether and how to act (e.g. "does this room have an opening for which `opening_faces_exterior` holds", "what's
adjacent to it"). This is why it has no `where`/`when`/`how` of its own: it is not a `HouseFact`, it
is standing structural context `HouseFact`-producing and `HouseFact`-consuming logic can read.

**The shape of a topological precondition (`TopologyRequirement`) is not defined here.** It belongs
to Layer 5's Reaction-descriptor-matching concern, alongside its siblings `SensorRequirement`/
`ActuatorRequirement` — all three are Layer 5 predicates that reference lower-layer types (`Sensor`,
`Actuator`, `Topology`), not lower-layer concepts themselves. An earlier version of this spec defined
`TopologyRequirement` here, inconsistently with how it correctly left `SensorRequirement`/
`ActuatorRequirement` to Layer 5 — corrected 2026-09-02, `v3_backlog.md`. `Topology`'s job ends at
being queryable; what a Reaction descriptor requires of it is Layer 5's to define.

### 7.1 `Zone` suggestions derive from `Topology`

Discovery can propose a `Zone` from topological structure (e.g. "these rooms share a floor, want a
zone for them?") — the same suggestion-only relationship `Zone` already has with HA's Label registry
(§6), not a second live dependency. A `Zone`, once created this way or any other way, is
indistinguishable plain Heima data.

---

## 8. Relationship to Layer 0

Layer 1 is thin on purpose — most of the actual machinery it depends on is Layer 0's:

- **Storage**: every `HouseFact` is written through Layer 0's Persistence (batched, write-on-change,
  retained per the time-based-plus-ceiling policy) — Layer 1 defines the shape being stored, not how.
- **Time**: `HouseFact.when` follows Layer 0's UTC/timezone-aware rule without exception; there is no
  Layer-1-specific time representation.
- **Provenance's source**: `Provenance.source: FactSource` is Layer 0's non-forgeable vocabulary,
  unmodified — Layer 1 does not add a second source concept or relax non-forgeability for facts.
- **Correlation**: a `HouseFact`'s `correlation_id` (inside its `FactSource`) follows Layer 0's
  minting/propagation rules (§5.2 of the Layer 0 spec) exactly — one per evaluation cycle for
  same-cycle facts, one per Layer 3 analysis run for learned facts, and so on. Layer 1 does not
  define a separate correlation mechanism.

Layers 0 and 1 form one **foundation slice** with distinct ownership, not a one-directional stack.
Layer 1 consumes Layer-0 services and the `FactSource` contract; Layer 0 consumes Layer-1 immutable
`HouseFact`/`Location` contracts at its storage and indexing boundary (Layer 0 §2.1). This reciprocal
reference is intentionally limited to data contracts.

It never permits a behavioral cycle: Layer 1 does not execute Timing, Persistence, Recovery, or
Divergence Hold Manager behavior while constructing its value objects, and Layer 0 does not query or invoke Layer-1
registries, topology, zone resolution, sensor/fusion logic, semantic resolution, or policy logic. Bootstrap composes the
two contracts before evaluation; the hot path has no Layer-0 -> Layer-1 -> Layer-0 call chain. An
implementation may use a neutral contracts module or type-only references to avoid a language-level
import cycle without creating a new architectural layer or moving ownership.

---

## 9. Not yet decided

Open cross-layer contracts are tracked in the CA4 backlog. No open CA4 item is currently owned
by this layer; CA4-28 (deep immutability, depth counting and invalid evidence) was closed in §3–4.3.

---

## 10. Acceptance criteria (for the eventual implementation phase)

- Topology has no stored `connection_type`. `opening_faces_exterior` is `True` for a window with
  default `other_side="outside"`, for a door to a room whose enclosure is `exterior` (terrace), and
  for an opening owned by an exterior room; it is `False` for a window or door toward an `interior`
  garage. Only `door`/`door_window` openings produce a `ResolvedConnection`, with `room_b` equal to
  `other_side`. Thermal-envelope membership is the bound Zone's rooms, or every `interior` room when
  `thermal_envelope` is unbound; a duplicate role binding, unknown zone or exterior room in the
  thermal envelope is rejected. `exposure_by_room` omits a window toward an interior garage (§6.1, §7).

- `ScopeKind` accepts exactly the four `Location.scope` values; a registry's
  legal-scope set cannot introduce a fifth spelling or replace a concrete
  `Location` with an unvalidated list of rooms (§5).
- Every existing "a thing that's true, somewhere, at some time, with some confidence" shape in the
  codebase today (`NormalizedObservation`, `DerivedObservation`, room-signal buckets, per-room
  occupancy booleans, independent activity claims and semantic context states) is expressible as a `HouseFact` with no residual
  parallel representation left standing.
- `ResultEnvelope`, model artifacts, `InferenceSignal`, `LearningProposalCandidate`, and
  `ReactionProposal` are rejected at the Layer-0 `HouseFact` persistence boundary. A test proves that
  a valid `InferenceSignal` can lead only to a separate declared semantic-resolver-produced fact, and that a
  `HeimaEvent` has one separate audit-event fact rather than becoming a generic workflow envelope.
- A `HouseFact` can record both a state assertion and an atomic occurrence without becoming a command
  or a state machine; its producer's Layer-0 emission declaration, rather than a field on the fact,
  selects the persistence semantics (§3).
- No `confidence` value anywhere in the codebase is computed by a formula other than the pure
  functions in §4.2 (called, not reimplemented) or the inherit-unchanged case, and no `min_support`-
  style gate is blended into a `confidence` float. **Re-corrected 2026-09-08** — this criterion had
  previously been fixed (2026-09-07) to remove a direct contradiction with §4.2's explicit permission
  to note a confidence method in `evidence` for diagnostics, but the fix did not survive a later edit
  to this document and the original, contradictory wording ("no field anywhere records which
  formula/path produced a given `confidence` value") was back in place — caught on a fresh full
  re-read, not by continuity from the earlier fix. The actual rule, matching §4.2: no *dedicated
  schema field* for this exists on `HouseFact`/`Provenance` outside `evidence`, and nothing downstream
  ever treats such a note as load-bearing — a test that strips a fact's `evidence` entirely must not
  change how any consumer reads its `confidence`.
- None of `categorical_confidence`/`continuous_confidence`/`combined_confidence` is ever called with
  an empty population (`total_observations == 0`, `scale <= 0`, or an empty `confidences` sequence) in
  any test — the zero/empty-population case always produces `available=False`/`confidence=None`
  instead, verified for at least one `FusionRule` strategy with all inputs unavailable.
- Each shared confidence helper rejects its own invalid input domain with `ValueError`, including
  non-finite values and out-of-range counts/confidences, in addition to callers avoiding those inputs
  in normal flow; `Provenance` construction similarly rejects a non-finite or out-of-range confidence
  and either inconsistent `available`/`confidence` pairing.
- `available` and `confidence` are never set inconsistently — `available=False` always pairs with
  `confidence=None` and vice versa, in a test that tries both wrong pairings and rejects them.
- `HouseFact` construction rejects a `value` that isn't `EvidenceValue`-shaped or a qualifying frozen
  dataclass, exceeds the maximum nesting depth, or exceeds the size cap — a hard failure, in a test
  that tries each violation.
- `HouseFact` construction rejects `NaN` and either infinity anywhere in `value`, including nested
  collections and frozen-dataclass fields. The same non-finite number anywhere in `evidence` creates
  the fact with `evidence={}` and a diagnostic (§4.3). Explicit boolean values remain valid
  `EvidenceValue`s but are rejected wherever a quantitative number is required. The three confidence
  helpers and `Provenance` construction reject `bool` for every numeric argument/field rather than
  treating it as `1` or `0`.
- A raw HA `State`, complete attributes mapping, event context, or another HA runtime object cannot
  enter a `HouseFact`, `Provenance`, or a nested payload by reference or serialization. A test extracts
  selected fields into a copied normalized projection, mutates the original HA fixture afterward, and
  confirms the fact is unchanged and remains within its 8 KiB payload cap.
- A constructed fact's `value` and `evidence`, at every nesting level, and a retained
  `PersistedProjection` reject mutation: a consumer that tries to add a key or append to a nested
  list fails, and the buffer, current index, snapshot and other readers continue to observe the
  original canonical value. The frozen sequence serializes as a JSON array with unchanged bytes.
  Depth is counted by the one §3 rule for `value`, `evidence` and `PersistedProjection`: a
  depth-two value is accepted and a third nested collection is rejected (or discarded for evidence).
- A `PersistedProjection` accepts only copied JSON-compatible mappings within depth 2 and 8 KiB,
  rejects raw HA objects, non-finite numbers, excessive depth, and excessive size. Layer 0
  omits an invalid recovery target without cancelling its accepted command and omits only an
  invalid critical-entity checkpoint projection;
  each outcome emits a diagnostic and never retains the original HA object.
- A persisted `ReactionFollowUpIntent` serializes its typed `subject` as one
  scalar canonical `LocationKey` JSON text, including for `rooms`; recovery
  validates and reconstructs the `Location`. Directly nesting `room_ids`
  inside the intent fails the depth-two projection check (Layer 5 §6.0).
- A hold lifecycle event enters the ordinary queue only as a complete
  `HouseFact` whose inline `HoldLifecycleValue` passes the depth-two and
  8 KiB fact-value validator. An arbitrary oversized non-fact projection
  still fails the `PersistedProjection` validator. No raw HA object enters
  either form (§3; Layer 0 §6.4).
- An operational `HeimaEvent` maps to exactly one append-only event fact with its approved V3
  `fact_type`, a mandatory `Location`, and `OperationalEventValue` preserving its non-empty delivery
  key, allowed severity, non-empty title/message, and JSON-compatible context. It rejects a V2/legacy
  event at the V3 boundary rather than translating it. Two distinct equal event occurrences are both retained, while exact operation-id retries of
  `manual_hold.lifecycle` and of any notification kind's `(notification_kind, operation_id)`
  (Layer 0 §4.5) retain one fact and conflicting retries fail.
  A Layer-6 delivery suppression based on a shared `notification_key` never removes an audit
  record (§3.1; Layer 0 §4.5/§6.4).
- A `HoldLifecycleValue` carrying two facet expectation sources is copied and
  validated against its producer-owned full audit schema and the ordinary
  fact-value validator. Composite colour is retained as canonical JSON text
  in a depth-two scalar facet map; a nested source object, raw HA state,
  noncanonical text or partial map is rejected. Its canonical facet tuple
  normalizes to a depth-two JSON list; a raw tuple outside a qualifying frozen
  dataclass remains invalid. Staging rejects any
  adapter/scope/Reaction combination whose worst-case complete inline value
  would exceed depth two or 8 KiB; runtime validation is a backstop and
  never truncates an audit (§3; Layer 0 §6.1–6.4;
  [complete serialized examples](ca4_01_serialization_examples.md)).
- For `reaction.follow_up`, Layer 6 accepts only the closed typed occurrence and
  serializes exactly its declared fixed context keys plus scalar
  `expected.<facet>`/`observed.<facet>` keys; nested facet maps fail the
  depth-two validator. `subject` maps to `where` and
  `occurred_at` to `when`. A fixture rejects an extra key, an invalid path/outcome,
  a mismatched prepared identity or activation id, an oversized facet projection, and resident text
  claiming an interrupted command completed. The resulting fact has a nonempty
  rendered title/message, `warning` severity, and
  `notification_key="reaction.follow_up:" + operation_id` (§3.1; Layer 5 §6.0).
- A shape/size violation on `evidence` never prevents `HouseFact` construction — the fact is still
  created with `evidence={}` and a diagnostic event, verified by a test that triggers each violation
  and checks the fact still exists.
- `HouseFact.when` and every field declared as `EvidenceInstant`, whether in a `HouseFact.value` contract or
  `Provenance.evidence`, is serialized only as canonical UTC ISO-8601 text with six
  fractional-second digits and `+00:00`; a raw `datetime`, a non-UTC timestamp, or a
  malformed string is rejected by producer-side validation. The fixture checks
  `HoldLifecycleValue.expires_at` in `value` (Layer 0 §6.1), not in `evidence`.
- `available=False` is set only when the producer explicitly cannot form a usable assertion (including
  read failure, interpretation failure, or insufficient derived evidence), never inferred from the
  absence of a recent fact for an unchanged value.
- A state unchanged across valid observations retains its original `when` and
  creates no duplicate fact; a historical consumer checks Layer-0 observation
  continuity and any staged source-age gate rather than subtracting that old
  change instant from its query time (§4.1; Layer 0 §4.4).
- `Location` construction rejects any instance where the populated optional field doesn't match
  `scope`, in a test that tries each mismatched combination; a `scope="rooms"` instance with fewer
  than 2 entries in `room_ids` is rejected the same way.
- Two `Location(scope="rooms")` objects built from the same room ids in different input orders have
  identical equality, hash, `FactIdentityKey`, and canonical JSON; a `room` location and a `rooms`
  location that includes that room remain distinct keys.
- Canonical JSON fingerprints produced by Layer 1, Layer 2 configuration staging, and Layer 3 artifact
  serialization agree for an object containing both a BMP key such as `"\uE000"` and the non-BMP
  decoded JSON key `"\uD83D\uDE00"`: object keys follow RFC 8785 UTF-16 ordering, while a declared
  semantic set such as `Location.room_ids` retains its separately specified Unicode-code-point array
  ordering.
- `Zone` construction rejects an empty `room_ids`; changing its display name or membership leaves its
  `ZoneKey` unchanged but changes its definition fingerprint. Empty or unknown room/zone references
  are rejected at their specified construction or registry boundary.
- A room's zone membership is always computed by scanning `Zone.room_ids`, never stored redundantly
  on a room record, verified by a test that adds a room to a second zone without touching the first.
- Permuting a valid Topology's openings/connections produces the same canonical fingerprint; duplicate
  opening ids, duplicate connection opening ids, an unknown room, a connection whose `room_a` is not
  its opening's owner, or a serialized derived view that disagrees with recomputation is rejected.
- `Topology` has no `TopologyRequirement`-shaped type or Reaction-descriptor-matching logic defined anywhere in
  Layer 1's own implementation — that stays entirely Layer 5's, consuming `Topology` only by query.
- A `Topology` instance, including its `openings`/`connections` (`Opening`/`ResolvedConnection`), is
  fully constructible from this document alone — a test builds one directly from the dataclasses in
  §7 with no reference to `custom_components/heima/room_topology.py`'s own internal `Connection` type.

---

## Related documents (background only, not required reading)

This spec incorporates and formalizes decisions originally captured in this planning branch's own
`v3_house_fact_draft.md` (§HouseFact, §HOW, §WHERE), `v3_architecture_recap.md` (Layer 1), and
`v3_backlog.md` ("Foundational model", "`Topology` placed in the architecture", the confidence-formula
and `Provenance.source` corrections under "Full architecture re-review" / "Observability,
re-grounded"). It also draws on v2's `core/event_catalog_spec.md` for the `fact_type` naming
convention. Where this document and any of those differ, this document is the current word for Layer
1's v3 design.
