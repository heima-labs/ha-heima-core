# Heima v3 — Layer 1: Substrate Primitive

**Status:** Draft — pending developer approval. Not implemented.
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

This document defines the intended contract for Layer 1 once approved. Until the developer confirms
it explicitly ("ok, proceed"), it is discussion material, not an implementation target. Once approved
and implemented: if code and spec diverge, the divergence must be resolved explicitly — code is a
reference implementation, not the source of truth.

---

## 1. Purpose

Layer 1 defines the **one shape** everything else in Heima is built from: a sensor reading, a fused
derived state, a learned statistical signal, a reviewable proposal, a manual hold, a notification
trigger. Anything that looks like "a thing that's true, somewhere, at some time, with some
confidence" is a `HouseFact` — there is no second, parallel representation competing with it for the
same kind of information. Five concepts:

1. **`HouseFact`** — the universal WHAT/WHERE/WHEN/HOW record.
2. **`Provenance`** — the HOW envelope: confidence, availability, and the evidence behind them,
   wrapping Layer 0's `FactSource`.
3. **`Location`** — WHERE a fact is about: the whole house, one room, a declared zone, or an ad hoc
   room combination.
4. **`Zone`** — an admin-declared, named group of rooms.
5. **`Topology`** — how rooms physically relate to each other: adjacency, openings, floors.

(`Zone` and `Topology` are both part of WHERE, listed separately from `Location` because they answer
different questions — see §6 and §7.)

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
- the `Room` registry itself (a room's name, type, floor as an inventory record) — `room_id` here is
  a stable reference into that registry, carried forward from today's existing room-inventory model
  unchanged; Layer 1 consumes `room_id` as an opaque identifier, it does not define what a room is.

### 2.1 Non-goals

- Prescribing internal class layout beyond the shapes below.
- A general query language over `HouseFact` history — Layer 0 already establishes the query shape
  ("every `HouseFact` true in `Location` X between t1 and t2"); Layer 1 does not add to it.
- Resolving conflicts between simultaneously-true facts of different provenance (e.g. two `Sensor`s
  disagreeing) — that is a `FusionRule` concern (Layer 2), not something `HouseFact`/`Provenance`
  decide on their own.

---

## 3. `HouseFact`

```python
@dataclass(frozen=True)
class HouseFact:
    fact_type: str        # namespaced, dot-separated identifier — see naming convention below
    value: Any             # interpreted payload: a bucket label, an enum value, a bool, a
                            # structured dict, or a small frozen dataclass (e.g. ManualHoldValue,
                            # Layer 0 §6.1) — semantically untyped (one universal shape must
                            # accommodate every kind of fact, and a closed *value* type would just
                            # push the same variability into a wrapper type one level up), but not
                            # unconstrained in shape — see below
    where: Location         # WHERE — §5
    when: datetime          # WHEN — a plain, UTC, timezone-aware timestamp (Layer 0 §3); no
                            # wrapper type, matches the existing ISO-timestamp convention used
                            # across the codebase today
    how: Provenance         # HOW — §4
```

**`value`'s `Any` annotation is not the whole story — it carries the same storage-safety constraint
as `evidence` (§4.3), for the same reason.** Every `HouseFact`, `value` included, is written through
Layer 0's Persistence facility exactly like `evidence` is, so the same class of accidental leak
applies: a raw Home Assistant `State` object, a binary blob, an arbitrary custom object would break
serialization or dump a raw payload wholesale into durable storage. `value` must be either
`EvidenceValue`-shaped (§4 — JSON primitives or shallow collections of them), **or** a frozen
dataclass instance whose own fields are themselves, recursively, `EvidenceValue`-shaped — the second
form is what lets a producer report a small, named structured value (`ManualHoldValue`: `active:
bool` + `held_state: dict[str, Any] | None`) without collapsing it into a bare dict and losing its
type identity. Python's type system cannot express "any frozen dataclass with JSON-primitive fields"
as a static union, so this is a **normative construction rule, validated procedurally** — the same
discipline already applied to `Location` (§5) — not something the `Any` annotation itself enforces.
Same nesting-depth and size limits as `evidence` apply, for consistency, not because the two fields
are interchangeable.

**Naming convention for `fact_type`**: dot-separated, namespaced, stable identifiers — `house_state`,
`occupancy`, `room_signal.bucket`, `activity.pattern`, `heating.temperature_rate`,
`manual_hold.<domain>` (Layer 0 §6), `external.<slot>`. This reuses the same convention Heima's
existing event catalog already establishes for its `type` field (`people.arrive`, `house_state.*`,
`lighting.*` — a stable, hierarchical, human-readable taxonomy), rather than inventing a second one.
The convention is enforced by usage, not by the type itself — `fact_type` is a plain `str`, not a
closed enum, because new fact types are added routinely (a new `Sensor` registration, a new learned
pattern) and a closed vocabulary here would fight that.

**A `HouseFact` is a value, not a command and not a state machine.** It describes one thing that was
true, at one place, at one instant, with one epistemic status — it does not represent a transition,
a duration by itself (durations are read by comparing two facts' `when`, or via a `Window`, Layer 0
§3.2), or an intent to act. An `ApplyStep` (Layer 5) is the corresponding command shape; a
`HouseFact` never is one.

---

## 4. `Provenance`

```python
EvidenceValue = str | int | float | bool | None | dict[str, "EvidenceValue"] | list["EvidenceValue"]

@dataclass(frozen=True)
class Provenance:
    confidence: float                          # 0.0-1.0
    source: FactSource                          # Layer 0 §5 — never a free string
    available: bool = True
    evidence: dict[str, EvidenceValue] = field(default_factory=dict)
```

### 4.1 `available`

A plain boolean: does this `HouseFact` represent an actual observed value, or the absence of one
(the source was unreachable/offline at the moment of observation). Nothing more elaborate is needed
or wanted here — see the reasoning below for what was deliberately left out.

**Staleness (`when` too old to trust right now) is not a `Provenance` field at all — it was
considered and rejected.** An earlier draft of this section had a tri-state `Freshness`
(`FRESH`/`STALE`/`UNAVAILABLE`) computed from elapsed time against a stored maximum-age threshold.
Two problems, found while working through it, not just a naming issue:

- "Is this fact still trustworthy" is a question relative to **whoever is asking, right now** — a
  dwell timer might tolerate a `HouseFact` hours old if nothing else has changed since; a
  security-relevant check might want one no more than seconds old. There is no single "freshness"
  value that serves every consumer, so baking one shared answer into `Provenance` would be
  presumptuous regardless of how it's computed.
- Even setting that aside, a *stored* staleness classification cannot stay correct on an immutable,
  write-once `HouseFact` — elapsed time keeps changing after the fact is written, so a `FRESH` fact
  would silently become wrong hours later with nothing rewriting it. This is exactly why `Window`
  (Layer 0 §3.2) is explicitly a **live, read-time** comparison, never a stored value — the same rule
  applies here. Any consumer that cares whether a fact is too old for its purposes computes
  `now() - fact.when` against its own tolerance, the same way every dwell timer already does; no new
  mechanism is needed, `when` alone is sufficient.

`available`, by contrast, is genuinely different in kind and earns its place as a stored field: it is
not a question of elapsed time at all, and it cannot be derived from absence of a recent fact —
Layer 0's write-on-change policy (§4.2 of the Layer 0 spec) means "no new fact this cycle" is the
**normal, expected** state for anything unchanged, so absence can never be read as "unavailable"
without creating a false positive for every ordinary stable value. Unavailability has to be a
positive signal, recorded at the moment the observation fails, which is precisely the kind of thing
that is correctly static and correctly stored once.

### 4.2 `confidence`

**Exactly two standardized forms, chosen by whether the underlying value is categorical or
continuous — never a third, never reinvented per producer.** This standardization exists because an
audit of the current codebase found four different, mutually incompatible formulas across modules
all called "confidence," not comparable to each other, one of them (`min(1.0, support /
min_support)`) actually wrong — mistaking data volume for confidence.

```python
def categorical_confidence(count_best_outcome: float, total_observations: float) -> float:
    """A true match ratio, P(outcome | pattern). `total_observations` is deliberately general — the
    population being matched against, whether historical pattern occurrences (Layer 3) or same-cycle
    evidence being combined right now (a Layer 2 FusionRule's votes). The formula's meaning (how much
    of the evidence agrees with the reported outcome) is identical either way.

    Precondition: total_observations > 0. Never called with zero — see below."""
    return count_best_outcome / total_observations

def continuous_confidence(dispersion: float, scale: float, floor: float) -> float:
    """Inverse dispersion. `floor`/`scale` are named parameters supplied by the caller, never ad hoc
    magic numbers at the call site.

    Precondition: scale > 0. A zero or negative scale makes the normalization meaningless; the
    caller chooses a scale appropriate to its own value's units and must never pass zero."""
    return max(floor, 1.0 - dispersion / scale)
```

**Neither function is ever called with a zero/empty population — that case is `available=False`
(§4.1), not a degenerate confidence.** This is exactly the kind of edge case centralizing these
formulas exists to handle consistently, so it needs to be stated explicitly, not left implicit: a
`PatternLearner` already guarantees `total_observations > 0` by construction (`min_support` is
checked, and gates on a positive count, before confidence is ever computed). A `FusionRule` producer
must apply the same discipline itself — if every input to a weighted-quorum fusion is itself
`available=False` this cycle, the derived `HouseFact` is `available=False` too, and neither
confidence function is called at all. There is no meaningful confidence for a value that was never
actually produced.

**Layer 1 owns these two functions as pure, shared, callable implementations — it does not decide
when either applies.** That decision requires knowing what's actually being combined or predicted,
which only the producer has: a `PatternLearnerConfig`'s declared `target_shape` (Layer 3), or which
`FusionRule` strategy produced a value (Layer 2) — Layer 1 has no visibility into either and should
not need any to provide two correctly-implemented formulas. This split matters concretely, not just
as a layering nicety: the standardization exists because an audit found **four incompatible
formulas**, all called "confidence," scattered across modules — if every producer reimplemented the
arithmetic itself instead of calling one shared, tested function, the same drift risk (a subtly
different edge-case handling here, a rounding difference there) would reappear even with the "right"
two formulas nominally agreed on. One canonical implementation, called from wherever it's needed, is
what actually prevents that — not just documenting the formulas and trusting every call site to copy
them faithfully.

**A third legitimate option, not a third formula: inherit, don't compute.** Some producers select or
pass through one specific upstream fact unchanged rather than combining several (a `FusionRule`'s
direct-passthrough or precedence strategy, Layer 2) — for these, `confidence` is simply the selected
source's own `confidence`, carried forward as-is. This is not a new formula requiring Layer 1 to
define anything further; it is the absence of a new computation. A raw `Sensor`-sourced fact, having
no upstream fact to inherit from and no "target shape" to predict, defaults to `1.0` under the same
principle — a direct reading is either available and fully trusted, or `available=False` (§4.1)
already expresses its absence. Reporting anything other than `1.0` for a raw reading requires a
concrete evidentiary reason (e.g. a sensor known to be noisy), not a guess.

**No consumer ever needs to know which of these applied to a given fact.** This is precisely the
point of standardizing to two comparable, normalized forms: a `confidence` value means the same thing
regardless of which path produced it, so nothing about which formula (or whether inheritance) was
used is ever recorded on the `HouseFact` itself — doing so would reintroduce the kind of
producer-specific interpretation the standardization exists to eliminate. A producer may optionally
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
derived fact and from which inputs, why a `PatternLearner` tier matched. Layer 0's Manual Hold
Manager already uses this field concretely — `restore_eligible`, `trigger_entity_id`, `trigger_state`
(Layer 0 §6.3) — as one example of what belongs here: small, specific, load-bearing detail, not a
dumping ground for large payloads.

**Constrained to a JSON-compatible shape, not `dict[str, Any]`.** `evidence: dict[str, EvidenceValue]`
(§4, `EvidenceValue` defined there) — values are limited to JSON primitives (`str`/`int`/`float`/
`bool`/`None`) or shallow collections of them, **maximum nesting depth 2** (a value, or a dict/list of
values — `trigger_state` above is exactly this: one level of nested attributes, not deeper). This is
mechanically enforceable and catches, at construction time, an entire class of accidental leak that a
content-based rule cannot: a raw Home Assistant `State` object, a binary blob, an arbitrary custom
object — none of these fit `EvidenceValue`, so a producer cannot accidentally dump one into `evidence`
the way it could dump one into an unconstrained `Any`-typed field.

**A total serialized-size cap applies on top of the shape constraint** — a concrete number (a few KB)
to be fixed at implementation time, listed in §9. This is what makes "not a dumping ground for large
payloads" an enforced rule rather than an aspiration: even a shape-valid `evidence` dict can still be
too large if a producer serializes something verbose into it.

**Violation policy: fail soft, not hard — this is a fixed, deliberate choice, not an unspecified
detail left to whoever implements it.** `evidence` is explicitly supporting detail, not essential to
what a `HouseFact` means (§4 intro) — a shape or size violation drops `evidence` back to `{}` for
that specific fact and raises a diagnostic event (Layer 0 §9-style), but the `HouseFact` itself is
still created with its `fact_type`/`value`/`where`/`when`/`confidence`/`source`/`available` intact.
Aborting the entire fact over a malformed `evidence` payload would be disproportionate — it would
mean a bug in optional diagnostic detail can silently blind a domain to a real observation. This is
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
@dataclass(frozen=True)
class Location:
    scope: Literal["casa", "room", "zone", "rooms"]
    room_id: str | None = None               # populated iff scope == "room"
    zone_id: str | None = None               # populated iff scope == "zone"
    room_ids: frozenset[str] | None = None   # populated iff scope == "rooms"; at least 2 entries —
                                               # a single-room set should use scope="room" instead
```

**`Location` is always present on a `HouseFact`, never absent.** A whole-house fact belongs to
`casa` by definition — there is no "no location" case.

**Normative construction rule**: exactly one of `room_id`/`zone_id`/`room_ids` is populated, matching
`scope`; `casa` populates none of them. An implementation must validate this at construction, not
leave it to convention — a `Location` with `scope="room"` and a populated `zone_id` is malformed.

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

---

## 7. `Topology`

```python
@dataclass(frozen=True)
class Topology:
    openings: tuple[Opening, ...]
    connections: tuple[ResolvedConnection, ...]
    exposure_by_room: dict[str, tuple[str, ...]]
    floor_by_room: dict[str, int]
```

A third, complementary piece of WHERE — genuinely distinct from both `Location` and `Zone`, not a
variant of either:

- `Location` says *which* place a fact is about.
- `Zone` says *an explicit group someone declared*.
- `Topology` says *how rooms physically relate to each other* — adjacency, openings between rooms,
  connection type, orientation, floor.

`Opening`/`ResolvedConnection` carry forward unchanged in shape from Heima's existing room-topology
model (adjacency graph, openings, connection type, orientation) — Layer 1 does not redefine them,
only places `Topology` explicitly in the layer model as context other layers query.

**`Topology` deliberately has no `casa` node — resolved 2026-09-02, not an oversight.** An early
planning note (predating `Topology`'s own separation from `Location`/`Zone`) said the whole-house
concept should become "an explicit node in the topology model." It doesn't, and shouldn't: a graph
node here represents something with a real physical adjacency relationship to other rooms (a room,
or the reserved `outside`) — "casa" isn't adjacent to anything, it **contains** every room, a
different kind of relationship entirely, one this graph isn't built to represent as a peer node.
Every whole-house topological question is answered as an **aggregate query over the existing
room-keyed structures**, never a lookup on a dedicated entry: "does the house have an outdoor
opening" is `any(exposure includes "outside" for exposure in exposure_by_room.values())`, not
`exposure_by_room["casa"]`; "how many floors" is `len(set(floor_by_room.values()))`, not a `casa`
entry that would have to mean something incoherent (a whole house doesn't have *a* floor). Whole-house
facts and actions already have a home entirely independent of `Topology` — `Location.scope="casa"`
(§5) — so nothing here was actually missing.

**`Topology` is not a fact producer and not a `FusionRule` input by itself.** It is queried, not
consumed as a stream — by `FusionRule`s, by Reactions, and by template requirements, when deciding
whether and how to act (e.g. "does this room have an operable opening to the outside", "what's
adjacent to it"). This is why it has no `where`/`when`/`how` of its own: it is not a `HouseFact`, it
is standing structural context `HouseFact`-producing and `HouseFact`-consuming logic can read.

**The shape of a topological precondition (`TopologyRequirement`) is not defined here.** It belongs
to Layer 5's template-matching concern, alongside its siblings `SensorRequirement`/
`ActuatorRequirement` — all three are Layer 5 predicates that reference lower-layer types (`Sensor`,
`Actuator`, `Topology`), not lower-layer concepts themselves. An earlier version of this spec defined
`TopologyRequirement` here, inconsistently with how it correctly left `SensorRequirement`/
`ActuatorRequirement` to Layer 5 — corrected 2026-09-02, `v3_backlog.md`. `Topology`'s job ends at
being queryable; what a template requires of it is Layer 5's to define.

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

Layer 1 depends on Layer 0 (this is expected — Layer 0 is the floor everything is built on); nothing
in Layer 0 depends on anything defined here, preserving Layer 0's own invariant.

---

## 9. Not yet decided

- **`HeimaEvent` → `HouseFact` field mapping is incomplete.** The stated intent is that `HeimaEvent`
  (today: `type`/`key`/`severity`/`context`) becomes expressible as a `HouseFact` once `fact_type`
  reuses the same taxonomy `type` already uses. But `type` → `fact_type` and (loosely) `context` →
  `value`/`evidence` are the only two fields with an obvious home — `key` (the dedup/rate-limit key
  the notification pipeline uses) and `severity` (`debug`/`info`/`warning`/`error`/`critical`) have
  no field on `HouseFact` or `Provenance` to live in. This is a real gap, not a detail to gloss over:
  it directly affects Layer 6 (Notification), which is the actual consumer of today's `HeimaEvent`
  shape. Needs a decision — likely when Layer 6 is spec'd — not assumed resolved by this document.
- **Per-`FusionRule`-strategy confidence mapping is mostly resolved, boolean-set is not.** §4.2
  establishes that Layer 2 decides which of {categorical formula, continuous formula,
  inherit-unchanged} applies to a given producer, not Layer 1. Weighted-quorum maps to the categorical
  formula, direct-passthrough/precedence map to inherit-unchanged, and `FormulaStrategy` (Layer 2,
  resolved 2026-09-02 — `v3_backlog.md`, closing AR-4) always maps to the continuous formula by
  construction. Boolean-set (any/all) is the one strategy still without an obvious mapping — "any"
  logic firing on one source out of five isn't meaningfully "low confidence" the way a low categorical
  match-ratio is — left for Layer 2's own spec to resolve, not assumed here.
- `evidence`'s maximum serialized size (§4.3) — a concrete number in KB, not an architectural
  question, to be set when this moves toward implementation.

---

## 10. Acceptance criteria (for the eventual implementation phase)

- Every existing "a thing that's true, somewhere, at some time, with some confidence" shape in the
  codebase today (`NormalizedObservation`, `DerivedObservation`, room-signal buckets, per-room
  occupancy booleans, `Activity`, `HouseState`) is expressible as a `HouseFact` with no residual
  parallel representation left standing.
- No `confidence` value anywhere in the codebase is computed by a formula other than the two pure
  functions in §4.2 (called, not reimplemented) or the inherit-unchanged case, no `min_support`-style
  gate is blended into a `confidence` float, and no field anywhere records which formula/path produced
  a given `confidence` value.
- Neither `categorical_confidence` nor `continuous_confidence` is ever called with
  `total_observations == 0` or `scale <= 0` in any test — the zero/empty-population case always
  produces `available=False` instead, verified for at least one `FusionRule` strategy with all inputs
  unavailable.
- `HouseFact` construction rejects a `value` that isn't `EvidenceValue`-shaped or a qualifying frozen
  dataclass, exceeds the maximum nesting depth, or exceeds the size cap — a hard failure, in a test
  that tries each violation.
- A shape/size violation on `evidence` never prevents `HouseFact` construction — the fact is still
  created with `evidence={}` and a diagnostic event, verified by a test that triggers each violation
  and checks the fact still exists.
- `available=False` is set only on an explicit observation failure, never inferred from the absence of
  a recent fact for an unchanged value.
- `Location` construction rejects any instance where the populated optional field doesn't match
  `scope`, in a test that tries each mismatched combination.
- `Zone` construction rejects an empty `room_ids`.
- A room's zone membership is always computed by scanning `Zone.room_ids`, never stored redundantly
  on a room record, verified by a test that adds a room to a second zone without touching the first.
- `Topology` has no `TopologyRequirement`-shaped type or template-matching logic defined anywhere in
  Layer 1's own implementation — that stays entirely Layer 5's, consuming `Topology` only by query.

---

## Related documents (background only, not required reading)

This spec incorporates and formalizes decisions originally captured in this planning branch's own
`v3_house_fact_draft.md` (§HouseFact, §HOW, §WHERE), `v3_architecture_recap.md` (Layer 1), and
`v3_backlog.md` ("Foundational model", "`Topology` placed in the architecture", the confidence-formula
and `Provenance.source` corrections under "Full architecture re-review" / "Observability,
re-grounded"). It also draws on v2's `core/event_catalog_spec.md` for the `fact_type` naming
convention. Where this document and any of those differ, this document is the current word for Layer
1's v3 design.
