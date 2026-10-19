# Heima v3 - Layer 3: Learning / pattern recognition

**Status:** Defined V3 core contract; explicitly deferred future components remain unimplemented.
**Open corrections:** none; CA4-12 closed in Layer 5 §7.3.
**Layer:** 3 of 8. Builds on Layer 0 (`Timing`, Persistence, retention coverage), Layer 1
(`HouseFact`, `Location`, `Provenance`), and Layer 2 (the registered facts whose history can be
mined). It does not read Home Assistant runtime objects, entity state, or registry internals.

Layer 3 is the historical-learning boundary. It derives statistical findings and optional learned
models from retained, atomic `HouseFact` history. It is deliberately separate from Layer 2's
`FusionRule`: a fusion combines current facts synchronously in the engine cycle; learning analyzes
history on a slow path. Its only in-cycle step is the bounded emission of an adopted live signal
(§6.3), which serves an artifact but never trains or validates one.

## 1. Purpose

Layer 3 replaces V2's independently implemented learning modules and analyzers with one coherent
architecture. Its job is to answer bounded statistical questions such as:

- which categorical outcome is most consistently associated with a context;
- which continuous value is expected in a context and how dispersed it is;
- whether an observed behavioral pattern is sufficiently supported to be presented for review.
- how a bounded, validated learned model predicts a measurable physical or behavioral outcome.

It does not resolve semantic claims, decide policy, issue an `ApplyStep`, create an active Reaction, or directly
communicate with a resident. It produces evidence and candidates for consumers that own those
decisions.

## 2. Architectural principles

- **Historical, not hot-path computation.** Analysis is scheduled independently of engine
  evaluations. It may read durable history, but never blocks a Sensor, FusionRule, `SemanticResolver`, or
  Reaction cycle.
- **Atomic facts only.** Every input is read through Layer 0's ordinary history API, scoped by
  `fact_type`, `Location`, and time interval. Layer 3 neither consumes nor reintroduces a bundled
  house-snapshot format.
- **Bounded and honest evidence.** A learner declares the history it needs. A
  fixed-window result requiring complete observation is unavailable when Layer 0
  reports truncated retention or typed incomplete `ObservationCoverage`; a
  time-to-event sample is right-censored at the first gap. Neither silently
  trains on an unobserved remainder.
- **A simple baseline, with bounded ML extension.** `PatternLearner` owns shared bucketing, support,
  warm-up, confidence, tier fallback, diagnostics, and failure semantics. A model-learning component
  may use the same historical bindings and governance when the statistical baseline cannot express a
  real, measurable relationship. ML never bypasses those evidence or governance rules.
- **Semantic-claim meaning remains explicit.** The primitive standardizes mechanics, not meaning. A
  learning family declares its target, historical inputs, sample semantics, and allowed consumers.
- **Learning is not authority.** A statistical result is diagnostic by default. Operational use is
  permitted only through an explicitly governed consumption path.
- **Results are not house facts by default.** Artifacts, `ResultEnvelope`, `InferenceSignal`, and
  `LearningProposalCandidate` retain their typed Layer-3 lifecycle; they are never inserted into
  Layer 0 fact history merely because they carry evidence about the house. A later authorized `SemanticResolver`
  may resolve a signal into its own declared `HouseFact`, while Layer 5 may create its own workflow
  record and audit events under its separate contract.
- **No V2 model migration.** V3 learners start without V2 snapshot history, models, approvals, or
  derived state. Their first usable model is built from V3 facts after their warm-up requirements are
  met.

## 3. Scope

Layer 3 owns:

- declaration and staging of learning-family definitions;
- historical input requests and retention requirements;
- sample construction from historical facts;
- model rebuilding, tier selection, warm-up/readiness, standardized confidence computation, and
  optional learned-model training/validation;
- immutable learned findings and diagnostics;
- the controlled hand-off of findings to approved live-signal consumers or proposal analyzers.

Layer 3 does not own:

- fact persistence, retention, or history reconstruction (Layer 0);
- fact interpretation, current-cycle fusion, HA bindings, or Actuator inventory (Layer 2);
- semantic-claim resolution (Layer 4);
- proposal review, conversion into a Reaction, or command generation (Layer 5);
- notification delivery (Layer 6);
- admin-panel presentation and review UI (Layer 8).

## 4. Components

### 4.1 `LearningDefinition` and family governance

A learning family is a named, coherent capability such as approved activity, indirect-room
occupancy, heating calibration, or lighting routines. Its
definition declares the learners and analyzers belonging to that family, their historical inputs,
and their permitted egress paths.

The active generation stages every definition before analysis begins. Staging is responsible for
validating references, registering its retention needs with Layer 0, and rejecting a malformed
definition without altering the active learning generation. A single family-level enabled state
gates both slow analysis and any live-signal publication belonging to that family; disabled means
no analysis, no model refresh, and no output.

### 4.1.1 Core learning-type registry and extension boundary

Each executable learner/model declaration within a `LearningDefinition` names a core-owned `kind_id`
and `version`. At bootstrap, the core builds and freezes an internal learning-type registry before
any generation is staged. Its lookup is O(1) and it performs no I/O, dynamic import, or plugin
resolution during analysis or inference. A learning type registers its configuration schema and pure
validator, permitted binding/target shapes, sample and artifact builders, analysis/inference
implementation, serialization contract, validation metrics, staleness/invalidation policy, and
permitted egress paths. This gives each new core capability one coherent versioned contract rather
than requiring changes to generic engine conditionals.

The active definition and persisted artifact store only `kind_id` and `version`, never a callable or
implementation object. A new core type or version is introduced by reviewed core code and registry
registration. During staging, its validator accepts only compatible definitions; a changed version
revalidates the definitions/artifacts that use that type and invalidates them under the
composed-generation impact rule (Layer 0 §4.7), like other core registries.

The admin can instantiate a registered core type for an explicit scope, enable or disable it, and set
only its explicitly exposed typed parameters. A legal scope is exactly one
Layer-1 `Location` with a `scope` value permitted by that core type: `room`,
`zone`, `rooms`, or `casa`. An explicit set of at least two rooms is
`Location(scope="rooms")`; a singleton is `Location(scope="room")`.
A wildcard or
live query such as "every room with humidity" is never a scope: it could silently change a learner's
population, binding, retention demand, resource cost and evidence meaning when registries change. The
canonical `LocationKey` and resolved ordered membership are included in the
definition fingerprint. A Zone or set membership change
therefore stages a new generation under the composed-generation impact rule (Layer 0 §4.7); it never
adds a room to an active learner implicitly.

The admin cannot register a type, provide code, substitute a binding/model implementation, or create
an egress path. Layer 7 may contribute a separately staged learning analyzer under its plugin
lifecycle, but it receives only immutable findings and the proposal path defined in §6.2. A plugin
cannot register a learner/model type, modify the core registry, or acquire a live-signal path by
registration.

### 4.1.2 Administrative instance contract

A registered core type supplies an immutable **blueprint**: its kind/version, declared input and target
slots, sample binding semantics, tier/fallback design, model/codec implementation, artifact/result
schemas, validation/promotion rules, permitted egress, resource envelope and parameter schema. An
administrator creates only an **instance** of that blueprint. The instance selects an allowed explicit
scope, names an eligible registered binding for each slot the blueprint marks configurable, supplies
every exposed parameter explicitly, and sets the enabled state.

The registry marks each exposed parameter with one core-owned impact class:

```python
ParameterImpact = Literal[
    "analysis_semantics",  # alters sampling/training meaning; invalidates artifact and warm-up
    "serving_semantics",   # alters runtime eligibility/interpretation; invalidates live use
    "scheduling_only",     # changes only a future slow-path admission decision
    "presentation_only",   # changes neither artifact nor runtime semantics
]
```

There are no ambient global defaults for an exposed parameter: the persisted instance contains one
canonical value for each parameter the blueprint exposes. A value fixed by core code is part of the
blueprint implementation, not hidden configuration. The registry may expose only bounded scalar,
duration, enum, or closed structured parameters with a pure validator; it cannot expose executable
code, an open JSON extension field, a raw HA entity/service selector, an arbitrary formula, a model
class, codec, target, egress path, tier algorithm, or resource envelope.

At staging, Layer 3 combines blueprint and instance into one immutable `ResolvedLearningDefinition`.
It resolves scope membership and only the blueprint-declared configurable bindings against the active
Layer-2 generation; validates fact type, unit, `Location` compatibility, history/retention needs and
parameter values; derives separate analysis-definition and serving-generation
fingerprints; and classifies the reload impact from the changed
fields. Any unresolved/ambiguous binding, missing required input, unapproved scope, unknown parameter
or invalid value rejects the new definition without affecting the active generation. A change marked
`analysis_semantics` restarts the normal warm-up/artifact lifecycle; `serving_semantics` immediately
withdraws candidates and live signals bound to the old learner serving
generation, without rewriting a separately approved configured Reaction;
`scheduling_only` takes effect at the next scheduler boundary; and
`presentation_only` changes neither evidence nor scheduling.

A learning definition is also a consumer in the composed configuration generation of Layer 0
§4.7. When a confirmed upstream change makes one of its bindings fail validation (**breaking**),
the commit invalidates that definition: no analysis, refresh, finding, signal or candidate is
produced under it, its artifacts are unavailable for every egress, and its live-signal adoption
chain closes. It stays invalid until an administrator stages a successor definition that
validates. A **semantic_only** upstream change keeps the definition; its source-generation
fingerprint changes, so existing artifacts become unavailable and the ordinary warm-up and
rebuild apply (§4.5).

The artifact's existing `definition_fingerprint` is the
analysis-definition fingerprint of the resolved learner: it covers the
fields enumerated in §4.5 and excludes parameters classified only as
`serving_semantics`, `scheduling_only` or `presentation_only`. The distinct
`serving_generation_fingerprint` covers the active
`definition_fingerprint`, all `serving_semantics` values and the exact
registered operational consumer/contract bindings. A serving-only edit
changes this fingerprint without changing the artifact's analysis revision
or restarting warm-up. It immediately withdraws incompatible live serving
under the old serving generation; renewed signal use requires the ordinary
current generation's administrative adoption/promotion gate. For an
action-bearing candidate it changes the proposed semantic payload and
follows Layer-5 review, while an already approved Reaction keeps its own
immutable configuration until explicitly changed. No serving fingerprint
silently overrides Layer-5 authority.

This keeps an administrative instance a typed declaration rather than a user-programmable ML pipeline.
It follows the separation of component implementation from typed parameters in
[TFX](https://www.tensorflow.org/tfx/guide/understanding_tfx_pipelines) and the explicit
input/output/parameter contract enforced by [MLflow model signatures](https://mlflow.org/docs/latest/ml/model/signatures).

### 4.2 Historical input binding and sample construction

A learner does not receive an untyped global history dump. It declares one immutable,
versioned `SampleBinding`; the common builder reads only the named facts, reconstructs their values
at declared instants using Layer 0's history semantics, and produces immutable samples. A binding is
also the sole declarative feature contract for a runtime-capable learner: history and live inference
must not grow separate feature definitions that can drift apart.

```python
@dataclass(frozen=True)
class FactSlot:
    fact_type: str
    where: Location

@dataclass(frozen=True)
class IntervalAnchor:
    sampling_interval: Window  # >= 5 minutes; slow-path reconstruction only

@dataclass(frozen=True)
class StateTransitionAnchor:
    source: FactSlot              # must resolve to a Layer-0 state claim
    from_values: tuple[EvidenceValue, ...] | None = None  # None: any previous available value
    to_values: tuple[EvidenceValue, ...] | None = None    # None: any new available value

@dataclass(frozen=True)
class EventOccurrenceAnchor:
    source: FactSlot              # must resolve to a Layer-0 event claim
    values: tuple[EvidenceValue, ...] | None = None        # None: every occurrence

SampleAnchor = IntervalAnchor | StateTransitionAnchor | EventOccurrenceAnchor

@dataclass(frozen=True)
class FeatureBase:
    name: str                     # stable, unique within this SampleBinding
    source: FactSlot
    required: bool
    missing_representation_id: str | None
    # required -> None; optional -> explicit core/family-defined representation id.
    # The representation's serialized value and vocabulary are fixed by the staged feature/family contract.

@dataclass(frozen=True)
class AsOfStateFeature(FeatureBase):
    pass  # state age is governed by source validity and historical coverage

@dataclass(frozen=True)
class CausalAggregateFeature(FeatureBase):
    window: Window
    aggregation: Literal["event_count", "true_duration", "mean", "minimum", "maximum"]

@dataclass(frozen=True)
class CausalSequenceFeature(FeatureBase):
    window: Window
    max_items: int                # bounded before analysis and at runtime

FeatureBinding = AsOfStateFeature | CausalAggregateFeature | CausalSequenceFeature

@dataclass(frozen=True)
class PointOutcome:
    source: FactSlot
    horizon: Window | None        # None means the anchor instant; otherwise positive

@dataclass(frozen=True)
class EventWindowOutcome:
    source: FactSlot
    horizon: Window               # > 0; interval is (anchor_at, anchor_at + horizon]
    result: Literal["occurred", "count"]

@dataclass(frozen=True)
class TimeToEventOutcome:
    source: FactSlot
    horizon: Window               # > 0; absence at the end is explicit right-censoring
    values: tuple[EvidenceValue, ...] | None = None

@dataclass(frozen=True)
class FutureStateFractionOutcome:
    source: FactSlot               # one typed state stream, not an event stream
    horizon: Window               # > 0; bounded interval [anchor_at, anchor_at + horizon]
    qualifying_values: tuple[EvidenceValue, ...]  # nonempty closed subset of this state's vocabulary

@dataclass(frozen=True)
class NoOutcome:
    pass

OutcomeBinding = PointOutcome | EventWindowOutcome | TimeToEventOutcome | FutureStateFractionOutcome | NoOutcome

@dataclass(frozen=True)
class SampleBinding:
    binding_id: str
    version: int
    anchor: SampleAnchor
    features: tuple[FeatureBinding, ...]
    outcome: OutcomeBinding
    usage: Literal["analysis_only", "runtime_resolvable"]
```

`anchor_at = T` is the instant at which Heima could have made a prediction. An interval anchor is a
regular historical cadence appropriate to continuous dynamics; it never creates an engine-cycle
timer. A transition anchor is a real Layer-0 state change matching its explicit before/after filters,
while an event anchor is one durable event occurrence matching its optional value filter. This removes
the ambiguous phrase "a transition or event": a state transition cannot accidentally be read as an
event and an event cannot be reconstructed as current state.

**Equal-time concurrency is atomic for learning.** Every accepted record with `when == T` belongs to
one concurrent observation group, even when Layer 0 used its internal `AppendOrder` to reconstruct a
state deterministically. `AppendOrder` is not exposed to Layer 3 and has no causal meaning there.
The sample builder first consolidates the complete equal-time group, then evaluates features against
the resulting state at `T`: `AsOfStateFeature` reconstructs the latest state record at-or-before
`T`, and `CausalAggregateFeature` and `CausalSequenceFeature` follow the canonical window semantics
below. Thus two facts emitted at the same
instant are context observed together, never an implicit cause and outcome merely because one was
appended first. Two separate evaluations never share an instant: Layer 0 §3.5 gives every cycle a
strictly later cycle instant, so a concurrent group always belongs to one cycle and a transition
between consecutive cycles is never merged into one group.
The aggregate is valid only for a source claim and aggregation that its core family validator permits
(for example, `event_count` for events; `mean` only for a finite numeric state). Every declared historical feature/anchor read checks both `retention_coverage` and the
Layer-0 §4.4 `ObservationCoverage` result before sample construction. An incomplete
observation window makes the features that read it missing; an optional feature's ordinary
missing representation cannot turn a process gap into observed context. A required
feature that is unavailable, stale, invalid, or lacks required retention or coverage
excludes the sample, with a diagnostic reason, from exactly the consumers that use it
(requiredness scope below). Optional never means implicit imputation: it requires its declared
`missing_representation_id`. A missing or invalid `PointOutcome` target discards
the sample. An absent event in a complete `EventWindowOutcome` window is a valid
zero/false outcome; an absent `TimeToEventOutcome` event at the end of complete
observation is a right-censored duration. Neither rule applies to an incomplete
observation window. A `FutureStateFractionOutcome` likewise requires complete
observation and retention for its entire interval and a valid state at its anchor;
an incomplete fraction is excluded, never filled from a later matching state.

#### Household-context censoring (CA4-123)

Heima learns the household's behavior, never a guest's, a house sitter's or a cleaner's, while
the physics of the house is learned whoever is inside.

**Behavior or physical, derived per instance.** At staging every learner instance is classified from
its declared inputs, never by an administrator. It is **behavior** learning when any feature, outcome
or learner-specific episode member reads a person-related fact: `occupancy` (room or casa) and its
`occupancy.physical`/`occupancy.evidence.*` inputs, `presence`, `presence.household`,
`occupied_without_residents`, `activity.*`, `actuator.manual_control`, `actuator.correction`,
`reaction.advisory_feedback`, or any `household.*` fact. Otherwise it is **physical** learning. A
slot used only as a sample anchor or as a cohort boundary does not count, so a thermal model that
uses `occupancy.departure`/`occupancy.return` only to delimit empty-house periods stays physical
(§4.8). The person-related list is core-owned; a new person-related fact type joins it in the same
reviewed change.

**Censoring, behavior instances only.** The common builder, and every learner-specific episode
assembler (§4.4.2, §4.4.3), excludes a sample or episode with the reason
`censored_by_household_context` when its observation interval (earliest feature window start to the
end of its outcome or assembly window):

1. intersects a period in which the Layer-4 claim `occupied_without_residents` (Layer 4 §9.2) was
   `True` or unavailable, anywhere in the house; or
2. intersects an active `household.guest_stay` (Layer 2 §2.9) and its subject, or any feature,
   outcome or member slot, is a room in that stay's `guest_room_ids`; while `household.guest_stay` is
   unavailable, its default guest rooms are used. Other rooms keep learning.

A censored sample is never a negative example, a zero outcome or a "no action" observation, and the
builder declares the retention and `ObservationCoverage` of both facts for every behavior binding; a
missing history for either excludes the sample like any other required coverage. Physical instances
are unchanged.

**Live egress.** While the current household context would censor its subject, a behavior instance's
live output (an `InferenceSignal`, a `DiagnosticFinding`, a context-novelty result) abstains with a
diagnostic: a household pattern applied to a guest is wrong, and a stay is novel by definition, so it
never raises a "context regime novel" finding.

#### Causal window semantics

One versioned feature resolver implements these rules for historical construction and live
inference; only the source of records differs. History is write-on-change, so a state value holds
from its record until the next record for the same claim (zero-order hold); nothing is
interpolated.

- **State aggregates** (`mean`, `minimum`, `maximum`, `true_duration`) cover the closed interval
  `[T - window, T]`. The initial value is the as-of state at `T - window`; each later record
  replaces it from its own `when`, and the consolidated equal-time group at `T` is the final value.
  `mean` is time-weighted, the integral of the value over the interval divided by `window`;
  `true_duration` is the number of seconds for which a boolean state is `true`, a finite
  non-negative number no greater than `window`. A record exactly at `T` adds zero duration and zero
  weight, while `minimum` and `maximum` range over every value held during the interval including
  the value at `T`. If the source is unavailable, stale or invalid anywhere in the interval, lacks
  an as-of state at `T - window`, or crosses an incomplete retention or observation interval, the
  feature is missing; it is never computed over the valid part only. A closed global
  overflow gap does not restore an unseeded source key (Layer 0 §4.6): the as-of state
  remains unknown until its acknowledged baseline, and that later seed never fills
  the earlier interval. Recovery of unrelated keys does not affect this feature.
- **Event aggregates** (`event_count`) cover the half-open interval `(T - window, T]`, so adjacent
  windows never count one occurrence twice; the concurrent group at `T` is included. A complete
  interval with no occurrence counts zero; an incomplete one makes the feature missing.
- **Sequences** return the records in `(T - window, T]`: for a state source its records (changes)
  in that interval, for an event source its occurrences. They are ordered by `when`, then, within
  one concurrent group, by the canonical RFC-8785 serialization of `(fact identity, value)`;
  `AppendOrder` is never used. When more than `max_items` qualify, the most recent `max_items` are
  kept. Coverage failure anywhere in the interval makes the feature missing.

A rate is not an aggregation: over a fixed window it is only `event_count` divided by a constant,
and the slope of a numeric state belongs to a Layer-2 formula or an explicit model.

Example: a 30-minute `mean` over a temperature held at 20 C for 25 minutes and 26 C for the last
5 minutes is 21.0 C (not the unweighted 23.0 C); `maximum` is 26 C; a report at 26 C exactly at
`T` changes neither.

#### Requiredness scope

`required` applies to the consumers that read a feature, not unconditionally to the whole sample.
A feature that is the outcome input of every tier, a non-tier model input, or a dimension of every
declared tier is sample-wide: when required and missing, the sample is discarded. A feature used as
a dimension only by some tiers is tier-scoped: when required and missing, including through a gap
in a stream read only by those tiers, the sample is excluded from exactly those tiers and still
enters every tier that does not use it. A missing outcome always discards the whole sample. In
training each tier counts its admitted samples independently, so tier support may differ and is
governed by its own `min_support`; serving applies the same scope through the tier-local
`missing_dimension` and `retention_incomplete` outcomes of §4.3. For example, a sample lacking
`darkness` does not enter a `rich (day_kind, time, occupancy, darkness)` tier but does enter its
`coarse (day_kind, time)` fallback. An optional feature uses its declared missing representation
and is never excluded.

`AsOfStateFeature` and `PointOutcome` address typed state claims. Their
previous `max_age` field is removed: elapsed time since the last *change* is
not elapsed time since a valid source observation. At a requested instant,
the builder first resolves the latest state record, including an unavailable
one, then checks the exact required interval's retention and typed
observation coverage and the source's staged validity rule. A newer
`available=False` state never lets an older available state reappear. A
stable value can therefore remain usable across a long complete interval;
an expired report, unavailable state, process gap or missing boundary cannot.
The same rule applies to current inference through the shared resolver;
source report age is Layer 2 §3.2, not a second Layer-3 historical timer.

Outcomes are intentionally separate and training-only. `PointOutcome` reads a state at `T` when
`horizon=None`, otherwise at `T + horizon`;
`EventWindowOutcome` reads occurrences in `(T, T + horizon]` and cannot treat an
incomplete window as zero or false; `TimeToEventOutcome` measures the first matching
event strictly after `T` and right-censors at Layer 0 §4.4's
`first_incomplete_at` when coverage breaks before an event; a valid target event
strictly before that boundary remains observed even if the rest of the horizon
is incomplete. `FutureStateFractionOutcome` integrates the elapsed time for which
the typed state belongs to its staged `qualifying_values`, using the same
write-on-change state reconstruction as historical `true_duration`, then divides
by its positive horizon. It includes the consolidated state at `T` and treats a
transition exactly at `T + horizon` as zero additional duration. The resulting
finite dimensionless scalar lies in `[0, 1]`; the existing scalar-result and
continuous-confidence contracts apply. It captures both uninterrupted
persistence and later returns to a qualifying state. A source that is
unavailable, stale or invalid anywhere in the interval, a process gap, missing
anchor state or truncated retention excludes the entire sample, even if valid
observations appear on both sides; it is neither a zero fraction nor a
right-censored first-event sample. `NoOutcome` is limited to
unsupervised/anomaly/drift learners. A transition- or
event-occurrence anchor must declare a strictly positive `PointOutcome.horizon`: an anchor-instant target
would still be inside its concurrent observation group. Thus training may read a future outcome only
after it has occurred, while no feature can depend on information newer than `T`. An outcome is never
requested by runtime inference.

The core stages every `SampleBinding` before the generation becomes active. It rejects an empty or
duplicate feature name; unknown fact/location; a duration that violates its field contract (including
an interval below the five-minute floor, and `PointOutcome.horizon=None` for a transition/event
anchor); a source whose
Layer-0 claim has the wrong state/event persistence kind; an invalid aggregate/claim pairing;
an empty, duplicate, unregistered or wrong-type `FutureStateFractionOutcome.qualifying_values`
set, or a fraction outcome whose declared source is not a typed state;
unbounded sequence; a required feature with any missing representation; an optional feature without
one; and a retention or current-buffer requirement that Layer 0 cannot satisfy. It records the
binding/version and canonical parameters in the learner definition fingerprint.

The registered learning type then runs a pure family validator. It may restrict feature names,
requiredness, aggregate choices, value shape, cross-location use, and topology (for example the
room-opening relation of an environmental learner), but may not add an undeclared data read. A type
that publishes a live signal or proposal must additionally require `usage="runtime_resolvable"`.
For that usage, the same versioned feature resolver evaluates the same `SampleBinding` against the
current Layer-0 snapshot and its declared bounded buffer; the only difference from historical
construction is the source of records, not a duplicated transformation. `analysis_only` bindings may
use historical facilities that are intentionally unavailable on the live path.

This is a compact application of point-in-time feature retrieval: an example timestamp bounds all
feature reads and freshness lookback ([Feast point-in-time joins](https://github.com/feast-dev/feast/blob/master/docs/getting-started/concepts/point-in-time-joins.md)). It also follows the production
ML rule that training and serving use the same declared features, while outcomes/labels exist only in
training ([Google Rules of ML](https://developers.google.com/machine-learning/guides/rules-of-ml),
[TFDV schema environments](https://www.tensorflow.org/tfx/guide/tfdv)). The chronological validation
and embargo rules remain §4.7; their use of an explicit temporal gap is consistent with
[`TimeSeriesSplit`](https://scikit-learn.org/1.0/modules/generated/sklearn.model_selection.TimeSeriesSplit.html).

#### Canonical JSON object boundary

`CanonicalJsonObject` is the shared bounded payload type for Layer-3 transform configuration and
typed semantic parameters. It follows Layer 1's V3-wide RFC-8785 rule exactly: object names are sorted
as raw UTF-16 code-unit sequences, primitives use ECMAScript-compatible JSON serialization, and the
canonical output is UTF-8. It does **not** apply NFC, NFD, case folding, trimming, or any other Unicode
normalization: valid strings are preserved as supplied.

```python
CanonicalJsonScalar = None | bool | str | int | float
CanonicalJsonValue = (
    CanonicalJsonScalar
    | tuple["CanonicalJsonValue", ...]
    | Mapping[str, "CanonicalJsonValue"]
)
CanonicalJsonObject = Mapping[str, CanonicalJsonValue]
```

`validate_canonical_json_object(value) -> CanonicalJsonObject` is pure and returns a copied,
recursively immutable canonical representation. It rejects a non-object root; duplicate keys at the
parse boundary; invalid Unicode/lone surrogates; `HouseFact`, Home Assistant objects, dataclasses,
enums, bytes, callables, or arbitrary Python objects; nesting deeper than 8; a canonical RFC-8785 UTF-8
representation over 16 KiB; `NaN`, infinities, negative zero, and integers outside the exact safe
range `[-(2^53 - 1), 2^53 - 1]`. Arrays preserve their declared order, including nested arrays; no
validator reorders them. Field-specific core validators decide whether an empty object, `null`, or a
given array/value shape is meaningful after this common structural validation.

The validator runs before a `ContextTransformRef` enters staging and before a
`ReactionDescriptorCandidate` root or member parameter object is constructed. It is a data/persistence boundary,
not a generic configuration language and not a replacement for the template/transform-specific
validators that constrain semantic meaning.

### 4.3 `PatternLearner`

`PatternLearner` is the shared statistical engine. A concrete learner declares:

- a categorical or continuous target;
- an ordered set of context tiers, from most specific to coarsest;
- a minimum support per tier;
- one learner-wide `min_confidence` for a usable result;
- a `WarmupGate` per learning subject;
- the positive `training_window` and its derived per-source retention requirements;
- the standard Layer-1 confidence mode and its declared parameters where applicable.

Each declared context tier has a stable `tier_id`, an explicit unique `priority`, its own
`min_support`, and an ordered tuple of context dimensions. A dimension references one named feature
binding already declared by the learner; it does not read a `fact_type` directly. It may apply only a
pure, declared, versioned canonicalization or bucketing transform compatible with that feature's
resolved type. The learner's staged definition carries its subject `Location`; a tier therefore
cannot hide a different scope inside an untyped key.

#### Context-transform registry

Layer 3 owns one internal, core-owned `ContextTransformRegistry`, constructed and frozen at bootstrap
with the learning-type registry. It is not an admin configuration surface, a Layer-2 formula registry,
or a plugin extension point: a Layer-2 formula creates a new fact, while a context transform only
canonicalizes/buckets an already declared Layer-3 feature for a tier key.

```python
BucketKind = Literal["boolean", "integer", "string"]

@dataclass(frozen=True)
class BucketValue:
    kind: BucketKind
    value: bool | int | str
```

`BucketValue` is the only value admitted to a context key or coverage cell. `kind="boolean"` accepts
only `bool`; `kind="integer"` accepts only a non-boolean integer in
`[-(2^53 - 1), 2^53 - 1]`; and `kind="string"` accepts only a non-empty valid-Unicode string. `None`,
floats, enums, dataclasses, collections, and HA objects are never bucket values. Its canonical JSON
representation is always `{"kind": ..., "value": ...}` under the shared RFC-8785 rule, so `false`,
`0`, and `"0"` are distinct keys rather than Python-equal accidents. The resolved transform's output
schema further constrains the permitted values; this base type only supplies their unambiguous scalar
representation.

```python
@dataclass(frozen=True)
class ContextTransformRef:
    transform_id: str
    version: int
    canonical_config: CanonicalJsonObject

@dataclass(frozen=True)
class ResolvedContextTransform:
    ref: ContextTransformRef
    input_value_schema_id: str
    output_bucket_schema_id: str
```

For each registered `(transform_id, version)`, the registry owns a pure configuration validator,
input/output schema contract, compiler, and canonicalizer. During staging it resolves every
`ContextTransformRef`, validates `canonical_config` through §4.2's common boundary and then its
feature value shape, compiles the immutable transform once, and records the resolved reference in the
learner definition fingerprint.
The frozen registry retains the compiled pure canonicalizer outside this serializable record. At
analysis and live inference the common feature resolver calls that same canonicalizer: no dynamic
import, I/O, lock, callable deserialization, or admin/plugin code is allowed on the path.

The registry also owns the only valid coarsening relation. For a pair of resolved references it either
rejects the pair or supplies a pure total map from each fine bucket to exactly one coarse bucket. A
declared relation must satisfy, for every valid raw input, `coarse(raw) == coarsen(fine(raw))`; core
tests prove this property for each supported transform/configuration family. Thus a fixed
`time_bucket(15m)` may declare a coarsening to `time_bucket(30m)`, and a one-degree temperature band
to a compatible two-degree band, while an arbitrary category regrouping has no presumed ordering. The
runtime may evaluate each tier directly from its raw declared feature, but staging has already proved
that the two resulting keys preserve the declared refinement relationship.

A core numeric-band transform may accept explicit configured ranges such as 22.5 C through 30.2 C,
but its output is still one discrete `BucketValue`, for example
`BucketValue("string", "22_5_to_30_2_c")`. Its configuration declares one canonical physical unit
and an integer scale; Celsius boundaries therefore use values such as `lower_milli_c=22500` and
`upper_milli_c=30200`, never binary floating-point boundary comparisons. Every range is half-open
`[lower, upper)`, valid ranges have `lower < upper`, and ranges in one transform configuration may
not overlap. A value at an upper boundary belongs to the next range; an uncovered value yields no
bucket and follows the ordinary tier-local `noncanonical_dimension`/fallback path rather than being
rounded or matched to a nearest range.

Changing the semantics of a transform, its configuration validation, canonicalization, output schema,
or coarsening relation requires a new transform version; an existing `(transform_id, version)` is
immutable. A code upgrade that removes or changes a referenced version makes only affected learner
definitions/artifacts unavailable and subject to the composed-generation impact rule (Layer 0
§4.7). Callables never enter persisted generations or artifacts; they retain only `ContextTransformRef`.

The tier identity is the tuple `(learner_id, learner_definition_fingerprint, tier_id)`. The
definition fingerprint includes target semantics, subject Location, ordered feature bindings, and
tier dimension names, order, and transforms. Changing any of those fields changes the identity of
the affected tier rather than presenting an old model as semantically equivalent. `tier_id` is
stable and human-readable, but never inferred from its list position; `priority` alone defines the
fallback order.

`min_support` is deliberately per tier because a narrower context naturally has fewer samples.
`min_confidence` is deliberately learner-wide: every usable result from the learner gives the same
minimum statistical guarantee, regardless of specificity. A tier cannot win merely because it has a
more permissive confidence threshold than a more reliable fallback tier. Findings below
`min_confidence` remain available to diagnostics and proposal analysis where the family permits,
but are not usable inference results.

**Warm-up is learner-wide per subject.** Every `(learner_id, subject Location)` has exactly one
`WarmupGate`, evaluated before any tier is considered. It is neither global to the installation nor
per tier: a coarse tier may reach its smaller `min_support` before a rich tier, but it cannot publish
a result until the learner's common historical-evidence requirement is satisfied. `min_support`
answers the local question "is this context bucket statistically sufficient?"; `WarmupGate` answers
the separate lifecycle question "has this learner, for this subject, accumulated a sufficiently
complete and stable historical basis to begin publishing at all?".

This intentionally favors predictable activation over the earliest possible coarse result. After
bootstrap, a definition change, or a retention interruption, allowing the coarse tier to publish
first and then switching abruptly to richer contexts would make house behavior and diagnostics depend
on transient initialization state rather than only on the staged learning definition. One gate keeps
configuration, audit, and recovery bounded while tier-specific `min_support` continues to handle
ordinary local sparsity after the learner is warmed up.

At an anchor, the sample builder first applies §4.2's typed historical observation-coverage gate and
requiredness scope; a gap-crossing training sample cannot enter any tier as a zero or negative outcome,
and a gap in a stream read only by some tiers excludes the sample from those tiers only. It then resolves the tier's declared dimensions and produces its
concrete `ContextBucketKey`: the tier identity plus the ordered canonical dimension values. For
example, a `rich` semantic-context tier can use `(day_kind=weekday, local_time_bucket=19:15,
occupancy=present, darkness=dark)`, while a `coarse` tier can use only
`(day_kind=weekday, local_time_bucket=19:15)`. These are distinct valid buckets, not a partial key
or failed reconstruction of the rich tier.

Bucket lookup is exact after the declared canonicalization. `PatternLearner` never searches for a
"nearest" value or performs an implicit wildcard match: context dimensions are semantic categories,
not a common metric space. A generic similarity rule would require an explicit distance, limit,
cross-dimension combination rule, and tie semantics for every feature type, and would make a
statistically rich but semantically unrelated context appear valid. Intended generalization belongs
in the staged tier definition itself, for example a 30-minute local-time bucket or a declared
temperature band; continuous relationships belong to a model that explicitly defines them. When an
exact bucket is unavailable, fallback proceeds only through the next explicitly declared coarser
tier. This preserves O(1) lookup, bounded inference, and an audit trail that identifies the actual
context used.

**One usable tier, never an implicit ensemble.** `PatternLearner` selects the first tier in declared
priority order that passes every usability control; it does not average, blend, or compare it with a
later tier. This is a semantic and statistical constraint, not merely a latency optimization. A
coarser tier normally contains the samples of its richer descendants, so an apparently harmless
weighted average double-counts overlapping evidence. There is no universal correct blend weight:
support, confidence, recency, and priority answer different questions. A generic blend would also
create a result whose effective context, confidence, and support cannot be explained or audited.

Likewise, selecting whichever tier appears to have the best confidence would make `priority`
meaningless. A coarser bucket commonly has more support and could routinely beat the more relevant
context even when the latter is already sufficiently evidenced. Cross-tier confidence is not assumed
to be calibrated or comparable merely because each tier meets the learner-wide floor. The explicit
order instead means: use the most informative declared context that is sufficiently founded; only
then generalize to the next declared context. This is a bounded backoff strategy for sparse context,
without importing probability redistribution or smoothing from a different statistical problem
([Katz backoff discussion](https://www.cs.cmu.edu/~roni/papers/scalable-TR-96-139.pdf)).

This restriction applies only to the shared `PatternLearner` tier mechanism. A future core-owned ML
type may implement a mixture, interpolation, or learned expert selector only when that combination
is an explicit versioned part of its model definition, feature contract, artifact, chronological
validation, uncertainty/calibration assessment, and result schema. It is never a generic Layer-3
fallback behavior and cannot be introduced by admin configuration or a plugin. This keeps the
statistical baseline explainable while permitting a separately evidenced model architecture where it
is genuinely justified.

**A fallback chain must actually coarsen.** Staging verifies every adjacent pair in ascending
`priority`: the later tier may drop dimensions, or retain a dimension only with the identical
canonicalization/bucketing transform or with a core-declared coarsening of it. It may not add a
dimension, replace one dimension with another, or use an unrelated transform. Thus
`(day_kind, time, occupancy, darkness) -> (day_kind, time)` is a valid chain, while
`(day_kind, time, occupancy) -> (day_kind, temperature)` is not a fallback chain at all. The latter
requires a separate learner/model definition whose own evidence and priority can be explained. The
core context-transform registry above supplies the pure, versioned coarsening relation used at
staging; no admin-provided callable or informal ordering decides it.

**Deterministic tier-selection algorithm.** Before looking at a tier, `PatternLearner` evaluates its
learner-wide gates: family/learner enabled; `WarmupGate` open; matching current definition and sample
binding fingerprints; successfully decoded, compatible artifact; and artifact within its declared
staleness limit. Any failure yields `global_gate_failed` and no tier is attempted. Artifact decoding,
schema, codec, fingerprint, or result-shape failure is likewise global: it marks the artifact
unavailable rather than concealing an integrity error by falling back to a lower tier.

When the global gates pass, the learner walks tiers in ascending `priority`. For each it resolves only
that tier's declared dimensions, canonicalizes them, performs one exact bucket lookup, and checks
complete declared retention/current-buffer coverage, `min_support`, and the result's type-specific
usability rules. A required unavailable/non-canonicalizable dimension, absent bucket, tier-local
retention/buffer gap, insufficient support, categorical tie, or result below `min_confidence` rejects
only that tier and evaluation continues. An optional feature with its declared missing representation
is a resolvable dimension, not an automatic rejection. The first tier that passes is selected; if
none passes, the result is absent with `no_usable_tier`.

Every evaluation emits a bounded `TierSelectionTrace`: overall status (`selected`,
`no_usable_tier`, or `global_gate_failed`), selected tier where present, and one ordered attempt per
declared tier with exactly one coded outcome: `missing_dimension`, `noncanonical_dimension`,
`bucket_absent`, `retention_incomplete`, `insufficient_support`, `ambiguous_top`,
`below_confidence`, or `selected`. A global failure records its own coded gate reason and no tier
attempts. The trace is diagnostic/audit metadata, not a second result or a path for a consumer to
override the staged priority.

Staging rejects duplicate `tier_id` or `priority`, duplicate dimension names, a reference to an
undeclared feature binding, an incompatible transform, or a non-canonical/non-serializable dimension
value, or a priority chain that is not a declared coarsening. It also requires each declared
dimension to be usable as a context feature under the learner's historical binding contract. No
generic `dict[str, Any]` context is accepted at analysis or inference.

Analysis rebuilds an immutable model from a bounded historical read. A selected inference identifies
both its `tier_id` and complete `ContextBucketKey`; an unselected inference carries the bounded
`TierSelectionTrace`. Neither is represented by a fabricated low-confidence value.

For a categorical target, a bucket is usable by single-value `infer()` only when it has one unique
highest-support outcome and that outcome meets the learner-wide `min_confidence`. Equal
highest-support outcomes produce the explicit diagnostic state `ambiguous_top_outcome`: the full
distribution and support remain inspectable, but no arbitrary categorical value is selected and
fallback proceeds to the next tier. Ordering, insertion time, IDs, and any other incidental runtime
property are forbidden as tie-breakers. A consumer that genuinely needs an outcome distribution
requires a separate typed contract; it cannot reinterpret this diagnostic state as a single
prediction.

For categorical outcomes, confidence uses Layer 1's `categorical_confidence`. For continuous
outcomes, it uses Layer 1's `continuous_confidence`. `min_support` is a readiness gate and never a
factor in either confidence formula.

### 4.4 Target and result contracts

`PatternLearner` deliberately supports only two supervised result shapes: a single categorical
outcome, or a scalar continuous outcome. An event-window target is represented as a categorical
event/non-event outcome; a future-state-fraction target uses the existing
scalar result with dimension `dimensionless`, canonical unit `1` and range
`[0, 1]`. Its `ScalarResult.horizon` equals the staged outcome horizon; a
Layer-5 state-fraction delay consumer requires that horizon to equal its
authorized `LearnedWindow.maximum` (§4.2; Layer 5 §6.0).
This keeps the baseline statistical engine explainable and lets its shared
support, confidence, tier, and fallback rules retain one meaning.

Every published inference result has one bounded, immutable envelope. The envelope is a Heima
artifact/result contract, not an HA state representation and not an operational command; an egress
contract in §6 separately decides whether a valid result may be consumed at all.

```python
@dataclass(frozen=True)
class TimeRange:
    start: EvidenceInstant
    end: EvidenceInstant

@dataclass(frozen=True)
class ArtifactRef:
    definition_fingerprint: str
    analysis_revision: int
    evidence_through: EvidenceInstant

@dataclass(frozen=True)
class ResultEvidence:
    tier_id: str | None
    context_key: tuple[BucketValue, ...] | None  # canonical tier order when tier_id is present
    support: int | None
    confidence: float | None  # Layer-1 confidence semantics; never predictive uncertainty

@dataclass(frozen=True)
class ResultEnvelope:
    result_schema_id: str
    result_schema_version: int
    artifact: ArtifactRef
    sample_binding_id: str
    sample_binding_version: int
    subject: Location
    predicted_at: EvidenceInstant
    evidence: ResultEvidence
    payload: "ResultPayload"
```

`TimeRange` is the closed interval of actual evidence instants described by a
diagnostic or proposal. Both endpoints use Layer-1 `EvidenceInstant` and
`start <= end`; equality permits one observed instant. It does not assert
continuous observation between endpoints: Layer-0 `ObservationCoverage` and
the learner's sample validation remain authoritative for gaps and retention.

`ResultEnvelope` carries no entity id, HA attribute, raw source payload, actuator target, or policy
authority. Its `result_schema_id`/version identifies the core-owned serialization and validator;
the artifact and binding identities make a stale or incompatible result detectable without
deserializing a model implementation. `evidence` preserves the selected tier, canonical context,
support, and Layer-1 confidence when the model has them; a result kind without a tier uses `None`
rather than fabricating a bucket or confidence. Predictive uncertainty remains in the payload and is
never substituted for this confidence. Expiry belongs to the later live-signal/proposal wrapper, not
to the result: the result remains auditable while the referenced artifact's §4.5 staleness policy
decides its inference usability.

The persisted/interprocess representation of an envelope or artifact manifest uses Layer 1's shared
RFC-8785 canonical JSON rule: objects have no duplicate keys, properties have deterministic order, and
numbers are finite IEEE-754 binary64 values. `NaN`, infinities, and negative zero are rejected before
serialization; counts must be non-negative safe integers (`<= 2^53 - 1`). Every contract instant uses the exact
Layer-1 `EvidenceInstant` UTC microsecond `+00:00` form; every positive elapsed duration uses the
Layer-0 `Window` canonical seconds object. The artifact codec rejects a `Z` instant or bare integer
milliseconds as an alternate encoding. Probability mass and the
survival/competing-risk identity use the core constant `PROBABILITY_TOLERANCE = 1e-12`. This supplies
repeatable fingerprints, comparisons, and validation without pretending that arbitrary Python float
rendering is a stable wire format ([RFC 8785](https://www.rfc-editor.org/rfc/rfc8785.html),
[RFC 3339](https://www.rfc-editor.org/info/rfc3339/)).

An artifact consists of this canonical manifest plus a bounded type-specific model payload. The
frozen core learning-type registry owns an `artifact_codec_id` and version for every payload; the
manifest records its SHA-256 digest, result schema, binding/type versions, and full artifact identity.
No artifact is an arbitrary Python pickle, callable, or executable configuration. The codec must
validate decoded structure, version, size, digest, and definition fingerprint before the model is
preloaded. A failed validation leaves the artifact inspectable as rejected but unavailable for
inference; this is equally true of a locally persisted or externally returned artifact.

`SemanticValueId` is a stable ASCII Heima identifier matching
`[a-z][a-z0-9_]*(?:[.][a-z][a-z0-9_]*)*`. It is a member of the active vocabulary owned by the
declaring result schema/family, not an HA entity id, state string, or display label. A value's
presentation label may change without renaming its semantic id; a semantic rename is a vocabulary
change and therefore an artifact-invalidating definition change.

```python
SemanticValueId = str

@dataclass(frozen=True)
class CategoryProbability:
    value_id: SemanticValueId
    probability: float            # finite and in [0, 1]

@dataclass(frozen=True)
class CategoricalResult:
    distribution: tuple[CategoryProbability, ...]  # exactly active vocabulary order
    selected_value_id: SemanticValueId | None
    selection: Literal["unique_top", "ambiguous_top"]

@dataclass(frozen=True)
class PredictionInterval:
    coverage: float               # finite, 0 < coverage < 1
    lower: float
    upper: float                  # finite, lower <= upper

@dataclass(frozen=True)
class ScalarResult:
    point_estimate: float         # finite and within declared physical range
    dimension: str
    unit: str
    horizon: Window | None          # None only for an anchor-instant point outcome
    interval: PredictionInterval | None = None

@dataclass(frozen=True)
class CountBucketProbability:
    lower: int                    # >= 0, contiguous buckets in ascending order
    upper: int | None             # None only for the final unbounded K+ bucket
    probability: float            # finite and in [0, 1]

@dataclass(frozen=True)
class CountResult:
    horizon: Window
    buckets: tuple[CountBucketProbability, ...]
    probability_one_or_more: float
    expected_count: float | None  # finite and >= 0 only when model semantics define it

@dataclass(frozen=True)
class SurvivalPoint:
    horizon: Window               # finite, strictly increasing declared grid
    survival_probability: float   # finite and in [0, 1]

@dataclass(frozen=True)
class CompetingRiskPoint:
    event_id: SemanticValueId
    cumulative_incidence: float   # finite and in [0, 1]

@dataclass(frozen=True)
class SurvivalResult:
    curve: tuple[SurvivalPoint, ...]
    competing_risks: tuple[tuple[CompetingRiskPoint, ...], ...] | None = None
    # outer tuple follows curve horizon order; inner tuple follows declared competing-event order.

@dataclass(frozen=True)
class UnsupervisedResult:
    raw_score: float              # finite; comparable only within baseline/schema version
    abnormal_direction: Literal["lower", "higher"]
    baseline_id: str
    threshold_id: str
    derived_label: SemanticValueId | None = None

ResultPayload = CategoricalResult | ScalarResult | CountResult | SurvivalResult | UnsupervisedResult
```

All probability **distributions** use the result schema's canonical finite numeric encoding and must
total one over their declared exhaustive domain within `PROBABILITY_TOLERANCE`.
`CategoricalResult` contains the complete active vocabulary distribution even when the baseline
`PatternLearner` exposes only one selected outcome. `selected_value_id` is non-null exactly for
`unique_top`; its probability is the unique maximum and it must satisfy the learner's confidence gate.
`ambiguous_top` retains the distribution for audit but has no selected value and cannot be treated as
a single prediction.

`ScalarResult` is self-describing enough to reject a unit/dimension mismatch at the consumer
boundary. Its interval is an uncertainty statement, distinct from the learner's statistical
confidence; a model that supports quantiles may serialize them only through a core-approved later
schema version, never as an unbounded ad-hoc map. `CountResult` has contiguous bounded payload size:
its first bucket begins at zero, the final `K+` bucket expresses its tail,
`probability_one_or_more` must equal `1 - P(0)`, and an expected count is absent unless the model's
declared distribution makes it meaningful. It never serializes a fractional count as an action or a
negative count. This preserves the non-negative distributional nature of counts and avoids applying
ordinary squared-error semantics to sparse zero-heavy windows
([scikit-learn Poisson regression](https://scikit-learn.org/stable/auto_examples/linear_model/plot_poisson_regression_non_normal_loss.html)).

`SurvivalResult` has a finite declared horizon grid. Survival probability is non-increasing over the
grid; with competing risks, each cause has a non-decreasing cumulative-incidence curve and survival
plus all cause incidences equals one at every horizon within `PROBABILITY_TOLERANCE`. It therefore never
collapses competing events into ordinary censoring and never publishes an unqualified expected event
time. `UnsupervisedResult` preserves the raw model-specific score, its direction, and the exact
baseline/threshold that derived any label. Scores from different schemas or baselines are not
comparable, and neither a score nor derived label is a probability, `HouseFact`, or operational
instruction. This also accommodates authoritative implementations whose score convention has an
algorithm-specific direction, rather than inventing a false common scale
([scikit-learn IsolationForest](https://scikit-learn.org/dev/modules/generated/sklearn.ensemble.IsolationForest.html)).

A categorical target declares a canonical representation and one of three vocabulary policies. A
`closed` vocabulary lists every allowed outcome. A `curated_extensible` vocabulary may grow only by a
reviewed proposal and explicit admin approval into a newly staged generation; it is nevertheless
closed for every active generation. A `discovery_only` learner may identify clusters or candidate
labels, but cannot emit a categorical inference result until a later reviewed generation makes that
label active. In no case may a learner synthesize a label or promote a raw HA string, entity name, or
unstructured attribute into an active outcome.

The active vocabulary and policy are part of the `definition_fingerprint`. Adding, removing, or
renaming an active value therefore invalidates the preceding artifact for inference and requires a
rebuild under the new generation. A canonical but inactive observed target value remains a
diagnosable observation or proposal input; it is not silently learned as an untyped operational
result. This lets each independent `activity.<activity_id>` claim evolve through review while keeping
its own vocabulary closed and exhaustive. Scene or actuator choices similarly use a registered Heima
semantic ID owned by their future action/reaction contract, never a raw HA endpoint identifier.

A scalar continuous target declares its physical dimension/unit, valid range, precision, and any
declared horizon. Its result identifies the point estimate and the statistical confidence required by
Layer 1; a model that represents predictive uncertainty additionally publishes an explicit
prediction interval or quantiles. Statistical confidence and a prediction interval are distinct: the
former describes evidence/readiness under the shared contract, while the latter bounds the possible
measured value. Mature forecasting APIs make the same distinction by treating prediction intervals
as a first-class forecast result ([sktime forecasting documentation](https://www.sktime.org/en/stable/api_reference/forecasting.html)).

`time_to_event` is not a scalar-continuous `PatternLearner` target. It requires an optional,
separately validated `SurvivalModel` because an observation that ends before the event says only
that the event time exceeds the observed duration; it is right-censored rather than an ordinary
numeric target. This is the defining distinction of time-to-event analysis
([scikit-survival overview](https://scikit-survival.readthedocs.io/en/v0.25.0/)). A survival
definition must declare the at-risk episode start, target event, reset boundary for recurrent events,
observation-end/censoring reasons, and any competing event that makes the target no longer
applicable. It publishes a survival/risk result or probability at declared horizons, never merely an
unqualified expected duration. Evaluation uses censoring-aware discrimination and calibration
metrics, such as IPCW concordance, time-dependent AUC, and Brier score where applicable
([scikit-survival evaluation guide](https://scikit-survival.readthedocs.io/en/stable/user_guide/evaluating-survival-models.html)).
Competing events are not silently recoded as ordinary right-censoring
([scikit-survival competing-risks guide](https://scikit-survival.readthedocs.io/en/stable/user_guide/competing-risks.html)).
Smart-home research has successfully forecasted the expected time to an activity, which establishes a
real use case but does not remove these semantic requirements
([Minor and Cook, *Forecasting Occurrences of Activities*](https://rex.libraries.wsu.edu/esploro/outputs/journalArticle/Forecasting-Occurrences-of-Activities/99900546937201842)).

The generic `FutureStateFractionOutcome` remains available to a future
registered learning type, subject to §4.2's complete-window and typed-state
rules. Initial V3 registers no solar-exposure-fraction timing profile for
`environment.solar_shading`: its operational hysteresis and dwell are owned
by Layer 2 §5.3 and Layer 5 §7. A future solar forecast requires its own
reviewed definition, evidence gates and descriptor timing path; the mere
presence of this outcome type does not activate one.

#### 4.4.1 `RoomOccupancySurvivalModel`

`RoomOccupancySurvivalModel` is the first concrete `SurvivalModel`. It is one core learner with a
closed, versioned `transition_profile`, not separate lighting, re-entry, or dwell-time engines. The
initial profiles are:

- `stay_duration`: anchor on the subject room's resolved occupancy transition `absent -> present`;
  target event is its later `present -> absent` transition. It describes the duration of the visit.
- `return_delay`: anchor on `present -> absent`; target event is a later `absent -> present`
  transition. It describes the delay before a possible return.

Both profiles use only completed, resolved room-occupancy facts whose own
occupancy labels are eligible physical evidence under Layer 4 §9.1, and named typed context bindings at or
before their anchor. The profile declares its reset boundary, finite horizon grid, censoring reasons,
and a closed competing-event vocabulary. A missing/stale required context at the anchor rejects the sample. After a
valid anchor, a missing/stale occupancy input, `available=False` interval,
process interruption, or the end of the retained complete observation span
right-censors at Layer 0 §4.4's first incomplete instant (or the end of
complete history).
It says only that the event has not been observed by that point. A valid target
transition before the first gap remains an observed event; a transition at or
after that boundary cannot be joined to the pre-gap risk interval. A process gap
is not a competing event and an unchanged post-restart occupancy state cannot
bridge it. For `return_delay`, a declared house transition such as `away`
that makes a room return semantically non-comparable is a competing event, not a censored non-return.
No generic admin event pair can create a profile; adding one requires a reviewed core profile with its
own input, censoring, and competing-event validation.

The initial algorithm is core-owned `DiscreteTimeHazardModel-v1`. For `return_delay`, the
finite declared horizon grid starts at one minute and includes every permitted
`LearnedWindow.maximum` used by its registered action-serving timing path.
The one-minute point needs the same support, calibration and operational-slice
evidence as every other serving horizon; an unvalidated short horizon cannot
serve an action. `stay_duration` retains its separately declared grid. This
time-to-event grid does not change §4.2's five-minute floor for interval-sampled
anchors. For each at-risk interval `j`, a regularized logistic hazard estimates
`h_j = P(event in j | event-free before j, anchor context)`. The artifact derives the monotone survival
curve `S(t_j) = product(k <= j, 1 - h_k)` and, where a profile declares competing events, their bounded
cumulative incidences. It serializes only a canonical feature order, training-partition normalization,
coefficients, finite grid, profile/version identity, and validation metadata; no pickle, callable,
opaque trainer object, or unbounded time series reaches local inference. The profile's elapsed grid
index is an allowed model input; no post-anchor house observation is.

The result uses the existing `SurvivalResult` curve at its declared horizons. `stay_duration` exposes
the probability that the room remains occupied through each horizon; `return_delay` exposes the target
event cumulative incidence, `1 - S(t) - sum(competing incidences at t)`, which reduces to `1 - S(t)`
only when the profile has no competing event. A preloaded result is bounded to a finite dot-product/grid
evaluation. It may be consulted
only on occupancy entry/exit and a policy's already armed timer boundary, never by polling every five
minutes or by blocking an engine cycle.

The mandatory baseline is `EmpiricalDiscreteHazardBaseline-v1`: a profile-specific empirical hazard
curve over the same finite grid and core-declared coarse context partition, with the same complete
episode and censoring rules. It has no learned feature interactions. A learner-wide `WarmupGate` and
independent core-owned floors for complete at-risk episodes, observed target events, and every declared
competing event prevent a sparse room from publishing an apparently precise curve. A missing floor
leaves the artifact unavailable; it cannot replace a competing event with censoring, invent an
expected duration, or collapse an unsupported profile into another.

Validation uses chronological walk-forward partitions with embargo at least equal to feature lookback
plus the profile horizon, then an untouched final holdout. It records censoring and competing-event
rates, IPCW concordance, time-dependent AUC where the profile has sufficient comparable cases, Brier
score/calibration by horizon, operating-envelope coverage, and the same measures for the empirical
baseline. Censoring-aware metrics are required because ordinary duration accuracy would score an
unobserved future as if it were known; survival metrics distinguish discrimination from calibration
([scikit-survival evaluation guide](https://scikit-survival.readthedocs.io/en/stable/user_guide/evaluating-survival-models.html)).
Failure at a required horizon or operational slice leaves the artifact diagnostic/unavailable.

`stay_duration` has diagnostic egress only. `return_delay` may also publish a
validated, reviewable action-serving artifact for the exact registered Layer-5
`routine.actuation_bundle` vacancy-delay path. Its role is timing evidence, not
the primary evidence that selects the bundle or permission to act. The profile,
resolved room subject, anchor, competing-event vocabulary, horizon grid,
result schema, quality gates and serving envelope must match that path exactly.
The existing Layer-3 validation/shadow and CA4-14 adoption lifecycle governs
this artifact; insufficient evidence or failed calibration at the selected
maximum horizon leaves it unavailable. Diagnostics remain available without
adoption. The `SurvivalResult` supplies target-event cumulative incidence at
the declared horizon; it is not a `FutureStateFractionOutcome`, an expected
return time, or an operational command. Layer 5 alone selects a bounded delay
and later checks current state, authority, holds and guards through its common
Reaction path. No room-return model may turn an Actuator on/off by itself,
alter a hold, create an `InferenceSignal`, or authorize a lighting-only path.

An optional `CountModel` predicts a non-negative discrete count in one declared future event window;
it is not a continuous `PatternLearner` result. It publishes a declared discrete distribution or
bounded categories, such as `0`, `1`, and `2+`, together with probability of one-or-more events,
expected count where meaningful, uncertainty, and its event-window horizon. Its validation therefore
tests count/distribution calibration rather than accepting a fractional point estimate as an
operational instruction. A `CountModel` remains diagnostic or proposal-only unless a later
consumer-specific contract explicitly authorizes a bounded use.

The first intended count use case is actuator-correction learning: the number of resident corrections
in a declared analysis interval after an admitted, recorded Heima target decision whose complete
target was observed. The counted corrections come **only** from Layer 5
§6.1's immutable Layer-1 `actuator.correction` event. Denominator and
censoring inputs additionally require the same section's
`actuator.target_lifecycle` event phases and Layer 0 §5.1.1.1's
per-channel state/coverage history; no raw ApplyStep audit is a learner API.
A usable correction record has `classification="manual_override"` with `control_actor`
`resident` or `physical` (a `guest`, `device` or `administrator` correction is never counted), a
non-null unique `anchor_apply_step_id`, matching logical `actuator_id`/`controlled_channel`,
complete-target observation time, correction time, and deduplication identity; service completion
time is optional for `already_satisfied` and failed/timed-out calls. Layer 3 reads these durable
attributed records exactly as historical evidence;
it never calls Layer 5, extends its attribution horizon, relabels an origin, or infers a manual
override from a raw HA state change.

`external_or_unknown_correction`, unanchored correction, duplicate report, malformed provenance, or
ambiguous anchor is excluded from this target and remains diagnostic-only. The learner may select an
analysis window no longer than the Layer-5 core attribution horizon, but that window filters already
attributed evidence; it cannot change the operational meaning of an anchor. This permits an
admin-facing finding such as repeated corrections after a lighting routine without granting the model
authority to alter that routine autonomously.

#### 4.4.2 `CorrectionCountHurdleModel-v1`

`CorrectionCountHurdleModel-v1` is the first concrete core `CountModel`. It is generic over any
registered logical `actuator_id` and `controlled_channel` that can produce Layer-5 correction
evidence; lighting is only its first expected use, not a separate learner engine. One learner instance
has an explicit Actuator/channel and semantic policy scope, one positive `observation_window`, and the
closed target vocabulary `0`, `1`, `2+`. Its target window starts when a recorded, admitted
`ApplyStep` decision has its complete target observed, including an `already_satisfied` decision
or a dispatched step whose calls completed, failed, or timed out, including a valid complete
target reading after the execution confirmation deadline. It never starts at mere command request
or service completion. A decision whose complete target is never observed is censored and cannot
contribute a zero-correction sample. A terminal `unconfirmed` execution outcome remains unchanged
even when a later full-target reading starts a learning window. Repeated evaluations that reuse the same active
target decision and first `anchor_apply_step_id` are one denominator episode, not additional
zero-count samples or restarted observation windows. The live confirmation rule is
Layer 5 §6.0.1. The historical builder resolves exactly one admitted
`decision` phase and its first `complete_observation` phase by
`apply_step_id`, `(actuator_id, controlled_channel)` and frozen
configuration generation; a missing, duplicate, malformed, mismatched or
out-of-order phase excludes the episode. The `decision` phase supplies the
versioned matcher and targeted/expected facets; the observation phase
supplies the first anchor instant. The same-id pair is one denominator
episode even when calls failed or were skipped as `already_satisfied`.
Only a non-null Reaction/generation within the learner's declared semantic
policy scope is eligible; standalone admin/recovery actions remain audit,
not learned automatic-policy corrections. A later `closed` phase or new
admitted decision on that channel bounds/censors the earlier sample under
the already defined supersession and authority rules. Layer 3 cannot
create, repair or relabel any of these phases.

A sample is complete only when the entire observation window is observable and remains attached to its
anchor. Layer 0 §4.4's typed coverage determines the exclusion: an interval whose
reasons include `process_interruption`, `clock_discontinuity`, `queue_overflow` or
`continuity_metadata_unknown` is `censored_by_observation_gap`; the exceptional global
`queue_overflow` epoch of Layer 0 §4.6 censors even a sample whose own stream lost no item.
After its global closure, an unseeded required state key still contributes `queue_overflow`
and censors only dependent samples until its baseline is durably acknowledged; an unrelated
unseeded key does not censor a now-complete window. Otherwise `required_stream_unavailable` for the
addressed channel is `censored_by_unavailability`. Both exclude the sample from
training, validation, and the zero-count class. A restart shorter than the
ordinary freshness bound remains a process gap. `first_incomplete_at` locates
the break; the remainder cannot contribute a zero.
Neither a complete retention read nor matching states on both sides of the gap establish a
zero-correction sample. A process restart does not censor unrelated later windows that begin
after valid observation has resumed; an unreadable individual channel affects only windows
that require that channel. A later admitted, recorded compatible target decision before the
window ends makes the earlier sample `censored_by_superseding_apply`; the new decision opens its own candidate sample. Layer 3 never truncates
either window and calls the partial result a zero count. These censoring reasons, and every excluded
event class from the preceding paragraph, are retained as diagnostics and coverage measures rather
than silently discarded statistics.

The bounded, core-owned algorithm is a regularized two-stage logistic hurdle model:

```text
p_any  = P(count >= 1 | pre-anchor context)
p_many = P(count >= 2 | count >= 1, pre-anchor context)

P(0)  = 1 - p_any
P(1)  = p_any * (1 - p_many)
P(2+) = p_any * p_many
```

It separates the useful sparse-event question, "will this automation be corrected?", from repeated
corrections without pretending that the tail category has the exact numeric value two. The resulting
three-bucket distribution is exhaustive, ordered, finite, and normalized by construction.
`probability_one_or_more` is exactly `p_any`; `expected_count` is `None`, because the unbounded `2+`
tail makes an exact expectation unidentified. This is preferable to a generic Poisson regression: a
Poisson loss is meaningful for exact non-negative counts, while the initial target is deliberately
top-coded and zero-heavy ([scikit-learn Poisson deviance](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.mean_poisson_deviance.html)).

The type's core version fixes regularization, solver, feature encoding, iteration/deadline bounds and
the canonical coefficient codec. There is no per-home hyperparameter search, implicit class balancing,
pickle, callable, or opaque trainer object. The artifact contains only bounded canonical feature
ordering, normalization parameters derived from the training partition, coefficients, intercepts,
algorithm/version identity, and validation metadata. Local inference is a finite dot-product over the
preloaded codec; a future bounded training backend changes neither artifact semantics nor this serving
path.

Features are named, typed, complete `SampleBinding`s resolved no later than the anchor: semantic policy
and action identity, registered Actuator/channel, declared time context, and only those environmental,
presence, or semantic-claim facts that the learner definition explicitly declares relevant. A policy
configuration fingerprint may appear only as the staged semantic behavior identity, never as a raw
configuration object. Post-anchor fact, correction, hold, notification outcome, raw HA state, HA user
identity, entity id, payload, and availability recovery are forbidden features. Missing required input
rejects that sample and serving result rather than invoking implicit imputation.

`PatternLearner` with the same `0`/`1`/`2+` target, subject, feature bindings, observation window, and
chronological partitions is the mandatory baseline. In addition to the common `WarmupGate`, the hurdle
model requires independent core-owned support floors for complete windows, `count >= 1`, and
`count >= 2`. Failure of any floor leaves the artifact diagnostic/unavailable; it must not collapse to
a binary model, merge `2+` into `1`, or report a fabricated low-confidence distribution.

Validation uses the common chronological walk-forward protocol with embargo at least equal to feature
lookback plus `observation_window`, then an untouched final holdout. It records three-class log loss,
Brier score and reliability curve for `p_any`, conditional calibration of `p_many` when positive
support permits, target-window completeness/censoring rates, operating-envelope coverage, and the
same metrics for the `PatternLearner` baseline. Calibration uses predictions from a partition distinct
from the data fitting the classifier; fitting a calibrator on its own training predictions is biased
([scikit-learn calibration guide](https://scikit-learn.org/stable/modules/calibration.html)). An
aggregate score improvement cannot compensate for failed probability calibration, missing positive
support, excessive censoring, or a failed declared operational slice.

The initial egress is diagnostics only: an artifact may report contexts with elevated calibrated
`probability_one_or_more`, observed correction frequency by bucket, and comparative baseline evidence
to the administrator. Its frozen `shadow_requirement` is `not_applicable`: it cannot alter a policy,
threshold, hold, Action, or `InferenceSignal`.

To make this diagnostic operationally visible without granting it authority, the core projects an
eligible result into one `DiagnosticFinding` with the registered schema
`correction_burden.v1`. Its core-owned review gate is evaluated for one semantic policy scope,
registered logical `(actuator_id, controlled_channel)`, and canonical pre-anchor context. Its payload
contains staged semantic policy identity, logical actuator/channel, canonical context key,
complete-window support, censored-window count/reasons, observed correction frequency, calibrated
`0`/`1`/`2+` distribution, `probability_one_or_more`, and baseline comparison. The registry derives
its stable `finding_key` from finding schema, policy scope, logical actuator/channel, context key and
definition fingerprint, so compatible retraining refreshes evidence instead of creating alert churn.

A later descriptor-specific adaptation may propose a reviewable parameter change only under a separate
contract that validates the effect of that change. Correction burden alone demonstrates friction, not
which policy parameter would reduce it; the count model itself never gains that authority. This keeps
override behavior as bounded occupant feedback rather than treating it as an automatic control law,
consistent with [ASHRAE occupant-centric control guidance](https://handbook.ashrae.org/Handbooks/A23/IP/A23_Ch65/a23_ch65_ip.aspx).

#### 4.4.3 `ActuationRoutinePatternModel-v1`

`ActuationRoutinePatternModel-v1` is the first concrete learner for recurring resident-controlled
actuation compositions. It is generic over a bounded `ActuationBundle`, not a lighting engine: turning
on a projector followed by changing three lights is one example, as are any later room-scoped
combinations permitted by a core Layer-5 Reaction descriptor. It discovers an **observed conditional routine**;
it does not infer resident intent, causality, an arbitrary HA script, or a cross-room orchestration.
This keeps the useful part of V2 routine discovery while discarding its raw entity/service payloads
and ad-hoc sequence analyzer. Smart-home research supports temporal episode and frequent-pattern
discovery, but also treats discovered behavior as a pattern requiring later interpretation rather than
an authorized action ([Cook et al., *Improving Home Automation by Discovering Regularly Occurring
Device Interactions*](https://eecs.wsu.edu/~cook/pubs/icdm03.pdf), [Cook et al., *Mining the Home
Environment*](https://pmc.ncbi.nlm.nih.gov/articles/PMC4264109/)).

One declaration fixes exactly one room `subject`, one registered Layer-5 routine Reaction-descriptor id/version and
`relation_profile`, one typed trigger binding, a finite pre-trigger context binding set, and a
core-versioned positive `bundle_assembly_window`. The trigger is a declared Layer-1 fact or completed
Layer-4 output transition, such as `projector.power: off -> on`; it is never an HA event name, entity
id, payload or free expression. All features resolve as-of the trigger's concurrent `when` group.
The trigger may be an ordinary observed physical transition even where its resident provenance is not
known; provenance becomes mandatory only for the learned actuation outcome.

An `ActuationRoutineEpisode` starts at that trigger. It contains the canonical ordered bundle formed
only from subsequent verified Layer-0 `actuator.manual_control` facts whose `ControlActor` (Layer 0
§5) is `resident` or `physical`, joined to their
canonical channel-state edges inside the declared assembly
window. Facts with the same `when` are concurrent members of one observation group, irrespective of
`AppendOrder`; their deterministic canonical member order is the registered descriptor's closed ordering,
not a claim that one caused another. A manual-control fact in the trigger's own concurrent group is
not subsequent and cannot be an outcome member: it may describe the same real-world interaction, but
cannot establish a trigger-to-outcome relation. A complete, observable window with no subsequent
resident control is retained with the closed training-outcome tag
`RoutineTrainingOutcome = Literal["resident_bundle", "no_resident_control"]`, using
`no_resident_control` and no bundle;
it cannot become a positive `ActuationRoutineEpisode` or an actionable candidate. This tag is
eligible for a given candidate only when its required channels were observable and free of
confounding control throughout the window. A positive episode
has `resident_bundle` and a non-empty canonical bundle. It is rejected if that bundle
is over the descriptor's bound, repeats an `(actuator_id, controlled_channel)`, has a missing/invalid
member target, or cannot be mapped to the descriptor's permitted member vocabulary. A member attributed
to Heima, another automation, an external/unknown source, or an unavailable observation never becomes
resident outcome evidence. A manual control by a `guest`, `device` or `administrator` is a
confounding control like an external one: it never becomes a member, and on a channel a candidate
requires it makes that candidate's window ambiguous and excluded, never a negative example. A known
policy action that overlaps the assembly window censors the episode
rather than being relabelled as a resident omission or a negative example. An external/unknown control
on a channel required by a candidate likewise makes that candidate's window ambiguous and excluded;
it is not evidence that the resident chose no action.

**Historical join for routine outcomes.** The registered channel's
`actuator.channel_state.<digest>` history provides its complete canonical
post-edge facet snapshot and exact changed-facet set; the unchanged
three-field `actuator.manual_control` event proves a resident outcome only
when its `ControlActor` is `resident` or `physical`, its `(actuator_id,
controlled_channel, control_edge_id)` joins exactly one available
channel-state transition with the same `when`, and that transition has
`origin="manual"`. A missing, duplicate,
unavailable, initial-after-gap, Heima-linked or mismatched edge cannot
become a resident member. The descriptor's staged channel/intent adapter
projects the observed canonical state and changed facets into the exact
permitted semantic member target; it never copies every observed facet
as an intended command or infers an omitted parameter. If no unique
descriptor-valid target exists, the episode is ambiguous and excluded.
The same channel-state stream reveals external/unknown and Heima-origin
changes that confound a candidate's assembly window; no fabricated
resident event is required for them. A verified physical wall switch
registered as its own channel may be a member for that switch, while an
unavailable bulb is only an observation break. State, resident, target
lifecycle and correction streams all declare retention and
`ObservationCoverage` requirements before training; missing join evidence
or a relevant gap excludes the sample, never supplies a negative outcome.

The candidate bundle is a complete canonical target composition, not a list of observed event deltas:
for each member it records the descriptor-declared final semantic intent and canonical parameters. A
resident may issue several controls during the window; an episode with incompatible or repeated
commands to the same channel is ambiguous and rejected, never reduced by incidental event ordering.
This makes the later Layer-5 policy deterministic while retaining the Layer-2 invariant that every
member becomes one independently owned `ApplyStep`.

The initial algorithm is `ConditionalBundleFrequency-v1`, a bounded statistical estimator. For every
core-declared trigger/context bucket and candidate canonical bundle it retains support in complete
episodes, support across distinct calendar blocks, and the conditional precision
`P(bundle | trigger, context)`. It compares that precision with the same bundle's declared scope
baseline `P(bundle | subject)` and requires a core-owned minimum lift greater than 1 as well as the common
`WarmupGate`, support floor, calendar-diversity floor and confidence floor. A trigger/context sample
with a complete observable assembly window enters the denominator for each eligible candidate bundle:
an exact matching bundle is positive; a different descriptor-valid resident bundle or the typed
`no_resident_control` observation is negative for that candidate. A different valid bundle is also
positive for its own candidate. No-action observations never create a bundle candidate or positive
support. Any unavailable, ambiguous, overlapping-policy or window with incomplete
`ObservationCoverage` (Layer 0 §4.4) is excluded rather than counted as
a negative. This includes process interruptions and unavailable required channels. A single unreadable member channel excludes only candidate observations that require it. The bounded candidate vocabulary comes only from observed descriptor-valid bundles in the
training span; it never enumerates the combinatorial product of actuators and target values.

For this model, `P(bundle | subject)` is a time-exposure probability within
the same room subject and evaluation partition. Let `W` be the positive
`bundle_assembly_window`. Its denominator is the total duration of eligible
start instants `t` for which the full `(t, t + W]` window lies inside that
partition, the declared trigger stream and required candidate channels have
complete `ObservationCoverage`, context bindings resolve as-of `t`, and
resident-control joins and confounder checks are decidable. Its numerator is
the duration of the subset of those start instants whose window contains
exactly the candidate's descriptor-valid resident bundle. Other valid
bundles and a complete window with no resident control contribute only to
the denominator, under the same negative-outcome rule as
`no_resident_control`; a baseline window is not an
`ActuationRoutineEpisode` and never creates a candidate. Ambiguous,
invalid, unavailable or policy-overlapped windows contribute to
neither. Exposure duration counts admissible Layer-1 microsecond start
instants, giving each the same weight; it uses no fixed assembly buckets or
starts selected from observed actions. The `ConditionalBundleFrequency-v1`
contract fixes these window and exposure semantics. An offline interval
sweep over existing event timestamps,
`t_event - W` boundaries and coverage/confounder boundaries computes the
two durations without persisting a reading or iterating at every instant.
Full-window containment and the existing embargo prevent either cohort
from importing a later partition. A bundle spanning any arbitrary clock
boundary remains eligible whenever a complete sliding window contains it.
Overlapping starts are correlated time exposure, not independent training
episodes or support samples. Temporal-block validation recomputes both
probabilities and their lift from complete contiguous blocks; it never uses
the microsecond-start count as a binomial sample size or confidence floor.

`lift = P(bundle | trigger, context) / P(bundle | subject)` when the baseline
is positive. Independence has lift 1; a positive association must exceed
the profile's frozen `RoutineEvidenceGateCalibration.minimum_lift`, above 1. An empty baseline cohort or
zero observed baseline probability makes lift unavailable, not infinite;
the candidate stays diagnostic and cannot pass the lift gate. The same rule
applies to a validation partition or temporal-block resample with zero
baseline: it cannot supply a passing lift interval. The existing
conditional precision, support, calendar-diversity, calibration and temporal
block confidence gates remain separate. This ratio measures association,
not a causal effect or permission to command a member.
The subject frequency here is the lift reference; the no-routine validation
baseline below remains a separate comparator.

Validation is chronological walk-forward with an embargo at least equal to feature lookback plus the
assembly window, followed by an untouched final holdout. It records support, distinct calendar blocks,
conditional precision, baseline frequency, lift, calibration of the binary matching-bundle outcome,
window completeness/censoring, bundle-size distribution, operating-envelope coverage and the same
metrics for the no-routine baseline. A temporal block confidence interval for precision and lift must
exclude the calibration's no-effect thresholds (`no_effect_lift`, `no_effect_precision`) in the
declared direction; aggregate frequency alone cannot
pass an operational slice. A sparse routine, a context slice with poor calibration, or a bundle whose
member composition changes across partitions remains diagnostic/unavailable.

The routine relation profile must register the sole policy-output schema
`routine.bundle_frequency.v1`, with schema-version field `"1"`. Its bounded
artifact contains one `RoutineBundleFrequencyCell` per canonical bundle and
exact context cell, never one result per member:

```python
@dataclass(frozen=True)
class RoutineEstimateInterval:
    lower: float
    upper: float
    nominal_coverage: float

@dataclass(frozen=True)
class RoutineBundleFrequencyCell:
    canonical_bundle_fingerprint: str
    context_cell_key: tuple[BucketValue, ...]
    assembly_window: Window
    complete_trigger_count: int
    matching_trigger_count: int
    distinct_calendar_blocks: int
    conditional_probability: float
    baseline_eligible_exposure: Window | None
    baseline_matching_exposure: Window | None
    baseline_probability: float | None
    precision_interval: RoutineEstimateInterval | None
    lift_interval: RoutineEstimateInterval | None
```

The bundle fingerprint identifies the descriptor-ordered complete target
composition; `context_cell_key` uses the exact `CanonicalEnvelope` axis
order. The artifact rejects duplicate `(canonical_bundle_fingerprint,
context_cell_key)` records. The validator requires positive complete and
matching trigger counts,
`matching_trigger_count <= complete_trigger_count`, positive calendar-block
count, and a conditional probability equal to the count ratio within the
shared probability tolerance. `distinct_calendar_blocks` counts blocks
with matching, complete trigger episodes, not overlapping baseline starts.
The two exposure fields use the sole Layer-0 duration type: `None` means
zero duration, and a present `Window` is positive. Matching exposure cannot
exceed eligible exposure; if eligible exposure is absent, matching exposure
and baseline probability are both `None`. Otherwise baseline probability
is their ratio within the shared probability tolerance, treating absent
matching exposure as zero. Both probabilities are finite in `[0, 1]` when
present. Zero baseline and `None` have no finite lift. Interval bounds and
coverage are finite and ordered; precision bounds lie in `[0, 1]`, lift
bounds are nonnegative, and a lift interval is absent when lift is undefined.
Each interval's nominal coverage must equal the profile-declared value and
its bounds must match the artifact's keyed temporal-block validation report.
Both intervals must be present for proposal eligibility. The point estimates
pass the existing confidence and minimum-lift floors; the temporal-block
intervals exclude the profile's registered no-effect thresholds in the
declared direction, as specified above. An absent interval,
failed calibration, missing calendar diversity, incomplete coverage or
failed chronological validation keeps the cell diagnostic. The same
artifact retains the keyed temporal-block, calibration, holdout and
coverage report from the preceding validation contract; the registered
validator checks that report and its gate results against this cell before
Layer 3 may publish it as policy-consumable. The registered profile is
`RelationProfileRef(profile_id="routine_actuation_bundle", version="1")` (Layer 5 §3.1); its
validator checks each cell against the report and calibration below. Neither the point lift (derived
from the two probabilities) nor any measured field enters the immutable
candidate's semantic fingerprint.

Its gate values are one core-frozen release calibration per profile version, approved by the core
release authority and never by a household administrator, following the thermal calibration
pattern of §4.8:

```python
@dataclass(frozen=True)
class RoutineEvidenceGateCalibration:
    calibration_id: str
    profile_ref: RelationProfileRef
    minimum_complete_triggers_per_cell: int
    minimum_matching_triggers_per_cell: int
    minimum_distinct_calendar_blocks_per_cell: int
    minimum_conditional_precision: float      # the learner-wide min_confidence for this profile
    minimum_lift: float                       # > 1
    no_effect_lift: float                     # >= 1; lift interval lower bound must exceed it
    no_effect_precision: float                # precision interval lower bound must exceed it
    interval_nominal_coverage: float          # in (0, 1)
    bootstrap_replica_count: int
    minimum_valid_bootstrap_replicas: int
    approved_by: str
    calibration_evidence_fingerprint: str

@dataclass(frozen=True)
class RoutineValidationEntry:
    canonical_bundle_fingerprint: str
    context_cell_key: tuple[BucketValue, ...]
    block_duration: Window
    block_count: int
    valid_replica_count: int
    bootstrap_seed: str
    precision_interval: RoutineEstimateInterval | None
    lift_interval: RoutineEstimateInterval | None
    holdout_conditional_probability: float | None
    holdout_lift: float | None
    calibration_error: float | None           # matching-bundle outcome, holdout partition
    coverage_complete: bool
    failed_gates: tuple[str, ...]             # canonical calibration field names; empty iff eligible

@dataclass(frozen=True)
class RoutineValidationReport:
    calibration_id: str
    bootstrap_version: str
    entries: tuple[RoutineValidationEntry, ...]   # unique (bundle fingerprint, context key)
```

Counts are positive integers, `minimum_valid_bootstrap_replicas <= bootstrap_replica_count`, and the
interval coverage equals every cell's `nominal_coverage`. The report reuses §4.8's temporal block
bootstrap protocol and seed rule with `canonical_cell_key` replaced by the bundle fingerprint and
context key; each block is at least the feature lookback plus the assembly window. A cell is eligible
only when its entry exists, `failed_gates` is empty, both intervals are present and match the cell,
`valid_replica_count` meets the minimum, and every count, precision, lift and no-effect gate passes.
A missing entry, a mismatched interval or a non-empty `failed_gates` keeps the cell diagnostic.

Its frozen `shadow_requirement` is `optional_before_proposal`: its only actionable egress after an
explicit administrative transition is a reviewable `ReactionDescriptorCandidate` for the core Layer-5
descriptor `routine.actuation_bundle`, with the observed bundle, declared trigger/context profile
and coverage envelope. Its accompanying typed artifact and proposal evidence carry the evidence
span, measured conditional precision, derivable point lift and its validated
interval; those values are not member or root descriptor parameters. An
administrator may first
run it in shadow to inspect `ShadowProposalPreview` frequency and scope, but cannot bypass any
Layer-5 validation after promotion. It cannot activate the policy, emit an `InferenceSignal`, change a
hold, issue an `ApplyStep`, or send a notification. Once a reviewed policy is configured, ordinary
Layer 5 evaluates its current typed trigger and guards; the learner is not polled on the hot path and
never decides a live action. A compatible retraining refreshes evidence for the same canonical bundle
candidate; a changed member, semantic parameter, trigger/profile or envelope creates a new review
item. Changing the descriptor-owned member order changes the descriptor version and therefore follows
the composed-generation impact rule (Layer 0 §4.7).

This model deliberately does not infer a future calendar schedule from a sequence of resident actions.
Its trigger is already present and its outcome is an immediate bounded bundle. A time-only or
future-sequence pattern, such as a lighting bundle usually set near a particular local time, belongs
only to the future generic `TemporalActuationProfileModel` in §8. That model may propose a registered
temporal-plan descriptor under its independent scheduling and validation contract; it does not turn an
observed clock correlation into an unreviewed recurring action.

An outcome binding of `none` is reserved for an optional `UnsupervisedModel`, such as anomaly,
clustering, or drift analysis. It publishes a typed score, its threshold/baseline version, coverage,
and available explanation or diagnostic evidence; it does not misrepresent a score as a supervised
target prediction. The separation between raw anomaly score, derived label, and confidence follows
established anomaly-detection practice ([PyOD documentation](https://pyod.readthedocs.io/en/latest/)).
An unsupervised result is diagnostic-only or a proposal input; it has no bounded live-signal or direct
operational path.

#### 4.4.4 `ContextRegimeNoveltyModel`

`ContextRegimeNoveltyModel` is the first concrete `UnsupervisedModel`. It detects that a complete,
explicitly scoped room or house-context vector is unlike the operating regimes already observed; it
does not declare a fault, safety violation, resident intent, or a causal explanation. Known security
posture requirements, such as an alarm armed away while casa `occupancy=present`, remain
deterministic future Layer-5 policies. A model that learned an unsafe posture as historically common
must never normalize, suppress, or replace that rule.

The initial core algorithm is `IsolationForest-v1`, using a bounded deterministic forest whose seed is
derived from the canonical definition fingerprint and training span
([scikit-learn IsolationForest](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.IsolationForest.html)). Its named typed bindings are
complete, predeclared Layer-1 facts only: canonical closed categorical values are one-hot encoded and
continuous values use the artifact's bounded deterministic normalization. Raw HA states, entity ids,
resident identities, arbitrary strings, unbounded sequences, and post-sample observations are forbidden.
The artifact serializes a core-owned canonical tree codec, feature vocabulary/order, normalization,
seed, score orientation, threshold identity, operating envelope and validation metadata; it never
serializes a library object, pickle, callable, or executable configuration.

The learner samples at the existing five-minute floor or a slower declared interval. It uses bounded
historical windows and common calendar blocks so temporally adjacent rows do not masquerade as
independent regimes. A learner-wide `WarmupGate`, minimum complete samples, minimum distinct calendar
blocks, and minimum support for each categorical value are mandatory. A new categorical value or a
continuous value outside the recorded finite operating envelope is `outside_operating_envelope`, not an
anomaly score produced by extrapolation. It creates a diagnostic coverage occurrence and schedules the
ordinary bounded evidence inspection.

`UnsupervisedResult.raw_score` is comparable only within the artifact's exact baseline/schema version;
`abnormal_direction="higher"`; and `derived_label`, when the profile threshold is crossed, is the
closed semantic id `context_regime_novel`. The score is not a probability or confidence. The result
contains a bounded explanation consisting only of the most atypical declared feature groups and their
envelope/support status. It never asserts that one feature caused the novelty, invents a resident
behavior label, or searches for a nearest known context to make the input look normal.

Chronological validation records score stability across later blocks, the observed alert rate,
operating-envelope coverage, feature-group availability, artifact-to-artifact score comparability only
where schema/baseline permits, and administrative false-positive/false-negative feedback where supplied.
There is no claim of conventional supervised accuracy without labels. The artifact may become
diagnostic-only or unavailable when score stability, coverage, or alert-rate gates fail. An instance
whose vector includes a person-related feature is behavior learning (§4.2 household-context
censoring): it trains without, and raises no finding during, periods occupied without residents or,
for guest-room features, guest stays; an instance of physical features only (HVAC, temperatures,
power) is unaffected. Its sole egress
is a deduplicated `DiagnosticFinding` with the registered `context_regime_novel.v1` schema or a
bounded request for ordinary evidence inspection/retraining; it cannot create a notification, signal,
fact, policy, hold, action, or security conclusion. Its frozen `shadow_requirement` is
`not_applicable`, because neither egress can acquire operational authority. This separation is
consistent with building fault-detection practice: rule-based and process-history-based diagnostics complement rather than replace each other
([NIST ZandrEA](https://www.nist.gov/publications/using-zandrea-project-research-toward-better-hvac-system-reliability-large-commercial),
[DOE AFDD](https://www.energy.gov/cmei/femp/energy-management-information-system-capabilities)).

#### 4.4.5 `IndirectSemanticAssistModel-v1`

`IndirectSemanticAssistModel-v1` is the single initial core `PatternLearner` family for a learned
assist to one exact Layer-4 semantic claim. It replaces separate occupancy- and activity-assist model
types without weakening their different evidence rules: every learner instance selects one frozen,
core-owned `IndirectAssistanceContract` and one explicit subject. A contract is a typed profile, not an
administrator-authored model, formula, feature expression, or policy.

```python
IndirectReferenceMode = Literal[
    "physical_reference",
    "deterministic_reference",
    "resident_approved_routine",
]
IndirectConfidenceKind = Literal["calibrated_probability", "routine_affinity"]
IndirectValidationMetric = str | int | float | bool
IndirectValidationSummary = Mapping[str, IndirectValidationMetric]

@dataclass(frozen=True)
class IndirectAssistanceContract:
    contract_id: str
    contract_version: int
    target_resolver_kind_id: str
    target_claim_parameter_ids: tuple[tuple[str, SemanticValueId], ...]  # canonical sorted pairs
    legal_scopes: frozenset[ScopeKind]
    positive_assertion: SemanticValueId
    reference_mode: IndirectReferenceMode
    confidence_kind: IndirectConfidenceKind
    feature_schema_id: str
    serving_precondition_ids: tuple[str, ...]  # finite core-declared checks
    validation_gate_id: str
    shadow_requirement: Literal["required_before_live_signal"]
    max_ttl: Window
    policy_posture: Literal["conservative_only", "advisory_only"]
```

The registry is built and frozen with the normal Layer-3 core registry. An instance cannot invent a
contract, target resolver, claim parameter, label, assertion, feature, reference mode, TTL, or policy
posture. It trains only from the contract's complete typed records and serves only its positive
assertion; failed freshness, envelope, drift, validation, shadow, routing, or precondition gates emit
no signal and never a negative assertion.

`physical_reference` is a core-validated direct physical label. The initial
`occupancy.room_present.indirect.v1` contract uses exactly the same-room Layer-2
`FactSlot(fact_type="occupancy.physical", where=subject_room)` with the
registered physical producer and its provenance: individual per-sensor evidence, semantic
occupancy, a learned output, a manually authored assumption, or mixed/unknown provenance are rejected.
Both physical outcomes train and validate the categorical learner, but the contract may emit only
`present`. It uses `calibrated_probability`, with positive predictive value and false-positive/negative
gates on every declared operational slice. Its features contain no direct occupancy/presence reading.
This preserves the former occupancy assist's asymmetry: no learned vacancy can turn lights off.

`deterministic_reference` is a complete non-learned typed fact/semantic reference specified by a later
core contract. `resident_approved_routine` is intentionally different: Layer 3 first discovers only a
diagnostic recurring pattern; it becomes a serving reference only after a resident approves its exact
activity id, scope, canonical feature schema, representative time windows, and pattern version. The
approval is immutable reference metadata, not raw identity data, a live command, or a self-produced
semantic fact. A routine reference may use `routine_affinity`, never claim calibrated probability,
PPV, diagnostic accuracy, or medical validity. Its validation gate instead requires stable recurrence
across chronological holdout blocks, minimum coverage, bounded contradictory observations, stable
feature availability, shadow agreement, and withdrawal on material drift. This allows useful learned
home context without calling an unlabeled cluster ground truth.

All contracts use the common tiered `PatternLearner`, one `WarmupGate` per contract/subject,
chronological validation, final holdout where the reference mode permits it, artifact freshness,
applicability envelope, required shadow, and the common absence-on-failure semantics. Feature bindings
are closed and versioned typed facts at or before the anchor; they cannot contain raw HA payloads,
resident identity, arbitrary event streams, a Layer-3 signal, a prior assisted semantic output, or a
target reference. This prevents feedback and keeps the shared learner rather than multiplying
near-identical model classes.

The initial `activity.sleeping.indirect.v1` contract is room-scoped and uses
`resident_approved_routine`, `routine_affinity`, positive assertion `active`, and
`policy_posture="conservative_only"`. Its serving preconditions require current same-room physical
occupancy support plus the contract's independent routine-evidence families. Heima-authored light or
actuator changes are excluded from those families, so an automation cannot make its own sleep signal
more likely. It may use darkness, device-charging, sustained low activity, and other declared physical
context only as independently correlated groups; no single light state, clock time, charger, or absence
of movement is sufficient. The signal is scoped home-context assistance, never a medical sleep claim
or person identity.

The initial `activity.relax.indirect.v1` contract is likewise room-scoped and uses
`resident_approved_routine`, `routine_affinity`, positive assertion `active`, and
`policy_posture="conservative_only"`. Its serving preconditions require same-room physical occupancy
support and at least two independent declared routine-evidence families. Media playback, seating/sofa
occupancy where available, local activity level, ambient state, and learned time context may contribute
only as those bounded families; no one device state, clock bucket, light level, or lack of movement is
sufficient. An action attributed to Heima, including a previously applied cinema/relax bundle, is
excluded from positive evidence, labels, and serving preconditions. The contract recognizes a
resident-approved leisure context, not a media-session fact or a command to create one.

The initial `activity.working.indirect.v1` contract is room-scoped and uses
`resident_approved_routine`, `routine_affinity`, positive assertion `active`, and
`policy_posture="conservative_only"`. It requires same-room physical occupancy support, at least one
declared workstation-operational evidence family (`computer.interaction_active`, a classified work
application, a bounded communication-session fusion, or an equivalent core-approved workstation
fact), and one further independent context family. The latter may be an explicit normalized work
calendar location, workstation presence, communication context, or the learned day/time routine. A
calendar `work_location=home` supports the contract; `work_location=office` prohibits this **domestic**
working signal; `unknown` is neutral. No weekday, clock bucket, calendar entry, active computer, or
communication session establishes working alone. Heima-authored actions and raw desktop content are
excluded from every feature/reference path. This allows a hybrid schedule to be learned and to drift
without treating an office day as a claim that the resident is not working.

The one egress is the generic `indirect.semantic_assist.v1` signal in §6.3. It cannot decide the
semantic claim, override direct Layer-2 evidence, alter a policy or hold, issue an `ApplyStep`, or
notify a resident by itself. Layer 4 accepts it only through the matching exact contract and resolver
definition. A future vacancy or high-risk assistance contract needs its own core review; it cannot be
introduced by changing an assertion in configuration.

#### 4.4.6 Composite house-state learning is retired

V2's composite `house_state` learner is not a V3 learner. Its values mixed mutually independent
claims: presence (`home`/`away`), activities (`working`/`relax`), quiet or sleep context, planned
absence (`vacation`), and guest context. A categorical model over that mixed vocabulary would create
an arbitrary priority order and cannot represent simultaneous activities in different scopes.

A future learner may assist only one reviewed `SemanticState` or `SemanticEpisode` with one explicit
scope and independent reference contract. It must name that exact Layer-4 `SemanticResolver` as its
sole consumer and may not recreate `house_state.approved_context.v1` under another name. No initial
V3 live signal replaces the retired composite signal.

#### 4.4.7 Context hypotheses outside learned live authority

Some recurring patterns can be useful to bring to an administrator's attention without being safe
enough to become a live semantic claim. The core-owned `ContextHypothesisCandidate` is the diagnostic
egress for such cases. **No `hypothesis_kind` is active in V3 and no V3 learner may emit this
candidate.** A future reviewed core version must introduce a kind together with its producer, evidence,
evaluation, and false-prompt contract. `possible_guest`, for example, additionally requires declared
direct multi-occupant-count evidence; Heima must not derive it from ordinary PIR/motion, binary
presence, room-occupancy overlap, device activity, or an unusual routine. `probable_departure` and
`extended_absence` are not learner hypotheses: any future deterministic use must remain a Layer-5
policy predicate over observed `departure`/`return` episodes and, where explicitly configured, the
declared `household.planned_absence` fact (Layer 2 §2.9). It must not become a Layer-4 semantic claim
merely because a calendar contains an event. A guest stay is likewise declared
(`household.guest_stay`), never a hypothesis: no learner output can set it.
The future candidate shape carries one casa subject, artifact/finding identity, evidence span,
confidence and uncertainty, operating envelope, and expiry. It contains no raw HA payload, resident
identity, command, policy, or state-transition instruction.

`ContextHypothesisCandidate` is not an `InferenceSignal`, `LearningProposalCandidate`, HouseFact, or
notification command. It cannot set `guest`, `away`, or `vacation`, nor can it create a Reaction. A
future administrative-review/notification contract may display an eligible hypothesis and record an
explicit confirmation, rejection, or dismissal under that contract. Until that contract exists, it is
an inspectable diagnostic only. A human decision is a separate, auditable input to the owning future
semantic resolver; it never becomes a retroactive training label unless a later reference contract explicitly
permits it.

This section defines the reusable egress, not an unvalidated guest/absence classifier. No initial
learner is authorized to emit a `ContextHypothesisCandidate` until its core-owned producer declares
the hypothesis semantics, bounded feature/episode contract, reference or unsupervised evaluation
method, calibration where applicable, and false-prompt controls. This prevents an attractive but
unfalsifiable label such as "guests" from being treated as a trained fact merely because it resembles
an unusual occupancy pattern.

The thermal-topology model is a scalar continuous model, but its acceptance remains multi-objective:
forecast error and uncertainty calibration are necessary but not sufficient. Its comparison records
comfort, energy, peak-demand where available, and runtime KPIs against the same baseline and
conditions, following the benchmark-oriented approach of
[BOPTEST](https://www.energy.gov/cmei/buildings/boptest-building-operations-testing-framework).

### 4.5 Model publication and diagnostics

An analyzed model is immutable for readers. A successful analysis atomically replaces the prior model
only after required retention reads, per-sample observation-coverage checks and validations succeed.
A retained span may contain observation gaps: §4.2/§5.2 exclude or censor the affected samples,
and the remaining eligible support must pass the existing gates. A failed read or analysis,
or insufficient support after those exclusions, leaves the last valid model inspectable,
marks its current analysis state degraded, and must not represent that model as refreshed
from the incomplete samples.

Every learner declares a stable `definition_fingerprint` and a mandatory, learner-specific
`max_artifact_staleness`; there is no global default. The fingerprint covers every field that changes
the meaning of a result: target and output semantics, subject Location, feature/outcome bindings,
canonicalization and tier definitions, warm-up/support/confidence gates, and any source-generation
dependency. It excludes serving-only objective, materiality, action and
consumer parameters whose changes leave that statistical result unchanged;
those belong to §4.1.2's `serving_generation_fingerprint`. A published
artifact records that fingerprint, a monotonically increasing
`analysis_revision` within it, and `evidence_through`, the latest historical anchor represented by a
complete successful analysis. Staleness is measured from `evidence_through`, not from the job's
completion time.

With an unchanged `definition_fingerprint`, a complete successful rebuild atomically publishes the
next `analysis_revision`. A failed or incomplete rebuild retains the preceding artifact as
`refresh_degraded` only until `now - evidence_through` exceeds that learner's
`max_artifact_staleness`; it remains auditable throughout, but is unavailable for inference once
stale. A changed fingerprint makes all prior artifacts immediately unavailable for inference,
regardless of age or validation quality, because their learned relationship no longer has the same
meaning. This is an invalidation rule, not a request to synchronously retrain during reload.

Diagnostics expose at least: family/learner identity and enabled state; analysis timestamps and
duration; declared versus covered history; warm-up status; sample counts; usable tiers; rejected
samples grouped by reason; definition fingerprint, analysis revision, evidence-through time,
staleness state; and every degraded/failure reason. Diagnostics never retain raw HA objects or
unbounded payloads.

### 4.6 Optional ML models

Layer 3 may host an ML model when it predicts a concrete, measurable target from explicitly declared
historical features and the simpler `PatternLearner` baseline is insufficient. ML is an additional
learning implementation, not a second authority or a replacement for explainable statistics.

A learned model is trained only from the same validated historical bindings and sample builder used
by the rest of Layer 3. Its immutable published artifact must identify its model family and version,
feature/target schema fingerprint, source-generation fingerprints that affect its meaning, training
interval and retention coverage, validation metrics, uncertainty/calibration information, and the
reason it is unavailable or degraded when applicable. It never retains raw HA objects or an
unbounded training payload.

Training, model selection, validation, and artifact persistence run only on the slow path and under
declared CPU, memory, and wall-clock budgets. A model whose required history is truncated, whose
validation fails, or whose inputs no longer match its staged schema is unavailable; it must not
silently serve a stale or incompatible prediction. A live prediction, where one is later explicitly
allowed, runs only from a preloaded immutable artifact and already-available facts, with bounded pure
computation and no I/O.

Core models are reviewed implementations. A third-party model follows the same Layer-7 boundary as a
third-party analyzer: it may emit diagnostics or a proposal candidate under an exact already-registered
core candidate kind and `ReactionDescriptor`, but cannot create a new live-signal path, `ApplyStep`,
or actuator invocation. The detailed model-definition, artifact, validation, and resource contracts
remain a component decision in §8.

An observational model may predict an outcome under observed conditions, but must not claim that an
action caused that outcome merely from historical correlation. Counterfactual or reinforcement
learning requires a separate causal/experimental contract before it can influence an operational
recommendation.

### 4.7 Validation, shadow evaluation, KPIs, and drift lifecycle

Every learned model is evaluated as a time-series model. Training, tuning, validation, and final
holdout intervals are chronologically ordered; random splitting and shuffled cross-validation are
forbidden. The model definition declares its validation protocol, including the maximum feature
lookback and target horizon. The evaluator applies an embargo between partitions large enough that a
sample in an earlier partition cannot share feature-window or future-outcome observations with a
sample used to score a later partition. A model may not report a validation result whose partitioning
would have leaked future information into a feature or effectively duplicated an overlapping sample.

Acceptance is relative to an explicitly declared baseline, normally the applicable
`PatternLearner` or a deterministic semantic-resolver baseline. A model definition declares its target-specific
quality metrics, minimum calibration requirements where it emits uncertainty, minimum coverage of
the intended operating conditions, and the decision thresholds for unavailable, degraded, and
eligible-for-shadow states. The artifact records the complete evaluation protocol, chronological
intervals, baseline version and scores, model scores, and the observed data-coverage profile; a
single aggregate accuracy score is not sufficient evidence for operational use.

The thermal family additionally evaluates prediction error and uncertainty calibration by forecast
horizon, together with diagnostic operational KPIs: thermal discomfort relative to declared comfort
bands, energy use or a declared proxy where measurements exist, peak demand where available, and
analysis/inference runtime. These KPIs compare a candidate with its baseline during the same
reconstructed conditions. They assess a recommendation or future control strategy only in a separate
simulation or explicitly approved experiment; observational historical data alone cannot establish
an energy or comfort improvement caused by an action.

Passing offline validation makes an artifact eligible only for the next state permitted by its frozen
core `shadow_requirement`; it is not operational by default. The requirement belongs to the reviewed
learning-type/version (or its reviewed relation profile), never to a per-home definition, artifact,
plugin, or learner choice. An administrator may select a stricter path where the type permits it, but
cannot weaken a requirement. The closed values are:

| `shadow_requirement` | Meaning |
| --- | --- |
| `not_applicable` | The type has no operational egress. It remains diagnostic-only; no shadow state exists. |
| `optional_before_proposal` | A review-only proposal type may enter shadow first, or may become `proposal_eligible` through an explicit administrative transition after offline validation. |
| `required_before_proposal` | A proposal-producing type must pass its declared shadow gate before it can become `proposal_eligible`. |
| `required_before_live_signal` | A type whose `InferenceSignal` is consumed automatically must pass its declared shadow gate before it can become `live_signal_eligible`. |
| `shadow_only` | The type may be observed in shadow but has no promotion path in the active core version. |

The artifact lifecycle is therefore `unavailable`, `diagnostic_only`, `eligible_for_shadow`, `shadow`,
and, only where the type authorizes it, `proposal_eligible` or `live_signal_eligible`. These are
generation-scoped administrative authorizations, not quality labels and not an additional model output.
The core type fixes the required shadow observations, coverage slices, outcome-latency allowance,
quality/calibration/drift gates, and maximum shadow age for its promotion gate; a definition may make
them stricter only where that type explicitly allows it. No type may use a missing future outcome as a
passing shadow observation.

In `shadow`, a model receives the normal bounded inputs and publishes timestamped predictions,
uncertainty, coverage, abstentions, drift diagnostics and, for a proposal family, a
`ShadowProposalPreview`. A preview is a registered `DiagnosticFinding` schema, not a second egress
class: it contains the hypothetical semantic candidate and evidence needed for inspection, but is
**not** a `LearningProposalCandidate`, never crosses the Layer-5 proposal facet, cannot open review,
notify a resident, enter a bounded live-signal path, or alter a HouseFact or action. Shadow assessment
compares predictions with subsequently observed outcomes across the declared coverage profile and
evaluates the frequency, scope and guard compatibility that a preview would have had.

Promotion, continued shadowing, rollback and disablement are explicit
administrative generation transitions. Entry to or exit from
`bounded_adaptive` instead appends an authenticated adoption-mode transition
under §4.9 without changing the analysis definition or a configured Reaction
generation. On promotion to `proposal_eligible`, a
still-valid preview may motivate a new `LearningProposalCandidate`, but is never converted in place:
Layer 3 rechecks artifact/fingerprint/evidence/validity and Layer 5 performs its ordinary independent
validation before any `ReactionProposal` exists. On promotion to `live_signal_eligible`, only the
registered signal type may be emitted from the exact adopted artifact for its
consumer (§4.9), and only under its existing current-input/freshness gates. No
model self-promotes; a later compatible artifact may receive bounded adoption without another
per-revision decision only after an explicit core/admin authority defines that policy (§4.9).

Each published model declares the observables it monitors for drift: input-feature distribution and
missingness, target/outcome distribution once available, prediction residuals and calibration, and
schema/topology/configuration fingerprints. A material change is a diagnostic event, never a reason
to mutate the model online. Schema or source-generation incompatibility makes the artifact
immediately unavailable. Statistical input, target, residual, or calibration drift degrades the
artifact, annotates every result accordingly, and schedules bounded re-evaluation or retraining on
the slow path. Until a newly validated artifact is explicitly promoted, the current artifact remains
only at the state authorized before the drift; it cannot gain a new operational permission through
retraining.

### 4.8 Environmental episode learning: first model use cases

The first concrete environmental capability is one graph-constrained core learner,
`EnvironmentalEpisodeLearner`. It is a common episode, sampling, artifact, validation, coverage, and
proposal mechanism; it is not a separate runtime engine for every environmental use case. Its selected
Layer-5 `RelationProfileRef` is read only through the proposal facet. Its evidence facet declares the
legal physical transition, observation slots, outcome shape and horizons, confounder exclusions,
metrics, and shadow requirement; its policy facet declares the permitted Layer-5 descriptors and
policy meaning. Layer 3 never registers, edits, or interprets the policy facet.
`thermal_shading`, `solar_shading`, `thermal_exchange`, `air_quality_exchange`,
`hygrometric_exchange`, `humidity_extraction`, and the
evidence-gated `hvac_thermal_response` are Initial-V3 profiles of that one learner, not distinct
learner kinds. The latter is registered from the start but cannot produce an operational candidate
until its stricter profile evidence and Layer-5 staged-prerequisite gates pass. Each Initial-V3 profile
is registered as `RelationProfileRef(profile_id=<named profile>, version="1")`.
Layer 1 `Topology` is structural prior knowledge: it identifies rooms and their enclosure, exterior
openings (`opening_faces_exterior`, Layer 1 §7), the thermal envelope, facade
exposure, and permitted connections; it is never treated as a measurement of heat or airflow.

Each declaration selects exactly one validated `RelationProfileRef` during staging. The exact ref, its
evidence facet, all resolved bindings, and its permitted outcomes are part of the definition fingerprint;
a generation cannot silently gain or lose capabilities when an optional source later appears or
disappears.

The same selected `RegisteredRelationProfile` fixes the sole policy-output
schema id/version and pure validator (Layer 5 §3.1). The artifact records that
exact schema identity; publication validates its typed output under any required
core-frozen release-gate calibration before a candidate can be formed. The six non-HVAC
Initial-V3 profiles use the common `environmental_response.v1` schema for the
bounded response-artifact cells defined in §4.8.2: exact
profile/transition-class/context/horizon
identity, canonical outcome unit, transition and reference quantiles and support,
response difference, bootstrap interval and provenance, and coverage/eligibility.
The validator checks the profile-declared transition class, outcome shape,
unit, horizons and bounds;
it does not accept an open-ended JSON object or an ineligible cell as a policy
estimate. This artifact output is distinct from the per-inference `ResultEnvelope`
in §4.4, whose closed `ResultPayload` union does not describe a complete response
artifact. `hvac_thermal_response` uses
`hvac_thermal_response.policy_output.v1`, validating its
`ThermalResponseParameter` against the separately core-frozen
`ThermalEvidenceGateCalibration` without changing either type's fields. The
calibration is release metadata, never a learner output. Neither the learner nor the candidate chooses a schema from its
payload shape or creates a new Layer-5 transport path. An incompatible schema
revision makes the prior artifact ineligible for a new candidate under the
ordinary profile-version invalidation rule.

Every active environmental relation profile has frozen
`shadow_requirement="required_before_proposal"`. Its candidate can affect comfort, indoor-air quality,
or the use of openings/covers even though Layer 5 later reviews it, so offline observational validation
alone is insufficient for an eligible proposal. Shadow evaluates bounded predictions and
`ShadowProposalPreview` records against real subsequent outcomes and declared guard availability;
only an explicit administrative promotion can allow the ordinary Layer-5 proposal path.
`hvac_thermal_response` uses the same closed requirements plus its stricter thermal evidence gates;
future profiles must declare one of the same closed requirements when their complete contract is
introduced.

| Relation profile | Required observations | Permitted meaning |
| --- | --- | --- |
| `thermal_shading` | room indoor temperature, outdoor temperature, observed cover position, its associated opening, and a deterministic per-opening solar-incidence proxy | conditional thermal-comfort response of shading |
| `solar_shading` | `thermal_shading` plus measured or explicitly trusted direct/diffuse radiation, resolved as per-opening incident solar exposure | conditional solar-response estimate with higher evidential support |
| `thermal_exchange` | room indoor temperature, outdoor temperature, observed state of an exterior opening, and resolved topology | conditional thermal response of an exchange |
| `air_quality_exchange` | `thermal_exchange` plus room CO2 | conditional CO2 response subject to thermal constraints |
| `hygrometric_exchange` | `thermal_exchange` plus indoor/outdoor temperature and relative humidity, resolved to humidity ratio or dew point | conditional moisture response subject to thermal constraints |
| `humidity_extraction` | room relative humidity and humidity ratio, the extraction fan's observed `level` channel state, and occupancy only where declared | conditional moisture response of fan start and one-level increase |

The following Initial-V3 profile is registered but evidence-gated. Staging accepts it only with its
declared observation bindings; it remains unable to publish a `ThermalResponseParameter` or an
operational candidate until its exact-cell evidence, calibration, and Layer-5 staged prerequisites
pass.

| Evidence-gated relation profile | Required observations | Permitted meaning when eligible |
| --- | --- | --- |
| `hvac_thermal_response` | room and outdoor temperature, observed registered HVAC action and HVAC mode; compatible observed target, solar exposure, and delivered power only where staged | validated passive-drift and recovery reachability evidence for a bounded `ThermalResponseParameter` |

#### Evidence-gated `hvac_thermal_response` contract

This registered profile is operationally dormant until eligible, and its artifact is limited to validated thermal reachability for
one explicit Layer-5 `conditioning_scope` and exactly one declared mode, `heating` or `cooling`. It is
not a whole-home physics model, an occupancy/arrival predictor, a setpoint recommendation, a calendar
schedule, or an actuator command. Heating and cooling use distinct artifacts, cells, envelopes, and
parameters even when one physical endpoint can serve both modes.

The evidence facet separates two complete, profile-declared cohorts: `passive_drift`, during which the
observed HVAC action is inactive for the required stable interval; and `active_response`, during which
the observed mode, action and compatible target remain stable for the declared interval. A manual
setpoint change, mode change, opening/control transition, unavailable required observation, or another
declared confounder excludes the interval from both cohorts. The artifact may use indoor/outdoor
temperature, staged solar exposure, observed target and delivered power only in typed slots declared by
the profile; it does not infer missing observations or borrow an adjacent context cell.

For each supported exact context cell, bounded room-thermal-delta bucket, and bounded recovery
setpoint-step bucket, the sole policy-consumable output is a versioned `ThermalResponseParameter`:

```python
@dataclass(frozen=True)
class ThermalResponseParameter:
    profile_ref: RelationProfileRef
    artifact_ref: str
    conditioning_scope_id: str
    mode: Literal["heating", "cooling"]
    context_cell_fingerprint: str
    thermal_delta_min_c: float
    thermal_delta_max_c: float
    recovery_setpoint_step_min_c: float  # positive absolute magnitude; mode determines direction
    recovery_setpoint_step_max_c: float
    passive_drift_rate_min_c_per_hour: float
    passive_drift_rate_max_c_per_hour: float
    recovery_duration_min: Window
    recovery_duration_max: Window
    conservative_recovery_duration: Window
    conservative_step_settle_duration: Window
    valid_until: EvidenceInstant
```

`conservative_recovery_duration` is a bounded, validated upper recovery estimate for that exact cell and
delta bucket. `recovery_setpoint_step_*` and `conservative_step_settle_duration` describe one observed,
stable HVAC-target move and the conservative time before evaluating the next recovery step; they do not
encode an absolute target or a command sequence. Staging requires finite ordered positive bounds,
`recovery_duration_min.seconds <= conservative_recovery_duration.seconds <= recovery_duration_max.seconds`, and
a positive step-settle duration. The parameter contains no HA entity, service, absolute setpoint,
calendar interval, resident identity, energy-saving claim, or prebuilt command sequence. Layer 5 may
use it only while current inputs match its exact cell and both the requested thermal delta and recovery
setpoint step lie in its declared buckets; otherwise the descriptor abstains. It cannot interpolate,
extrapolate, select a nearby cell, or substitute a fallback parameter.

The profile's shadow compares these passive-drift and recovery-step estimates with later compatible
observed temperature trajectories only. It cannot stage a target, send an `ApplyStep`, or treat an
observed calendar end as an arrival label. Activation requires calibrated trajectory/prediction-interval
and operating-envelope coverage for both cohorts and every published step bucket; an energy benefit is
publishable only with a separately staged measured energy/power outcome.

##### Environmental response evidence-gate calibration

The six non-HVAC `environmental_response.v1` profiles (including `humidity_extraction`) follow the same
release discipline as the thermal profile below: each profile version has exactly one core-frozen
calibration, approved by the core release authority and never by a household administrator, that
fixes its outcome horizons and evidence gates.

```python
@dataclass(frozen=True)
class EnvironmentalResponseGateCalibration:
    calibration_id: str
    profile_ref: RelationProfileRef
    outcome_horizons: tuple[Window, ...]      # non-empty, ascending, unique; the profile's horizons
    minimum_transition_support_per_cell: int
    minimum_reference_support_per_cell: int
    minimum_distinct_calendar_blocks_per_cohort: int
    bootstrap_replica_count: int
    minimum_valid_bootstrap_replicas: int
    response_interval_nominal_coverage: float  # in (0, 1)
    maximum_response_interval_width: float     # in the profile's canonical outcome unit
    minimum_independent_shadow_episodes: int
    approved_by: str
    calibration_evidence_fingerprint: str
```

Counts are positive, `minimum_valid_bootstrap_replicas <= bootstrap_replica_count`, and the width is
finite and positive. Each `environmental_response.v1` cell is eligible only when its horizon is in
`outcome_horizons` and every support, block, replica, width and shadow gate passes; the interval is
§4.8's temporal block bootstrap. The objective and `minimum_practical_delta` test of this section is
applied on top of these gates. A profile without a frozen calibration publishes diagnostics only.

##### Initial thermal evidence-gate calibration

The Initial-V3 numerical gates are not administrator preferences and are not selected from a current
household's early observations. Before `hvac_thermal_response@1` can publish an operational artifact,
core maintainers must freeze one versioned `ThermalEvidenceGateCalibration` after evaluating the
registered baseline against a documented matrix of BOPTEST scenarios and provenance-recorded replay
fixtures, then confirming the result through a documented opt-in field pilot. BOPTEST is used to
compare control outcomes and uncertainty under reproducible building and boundary-condition scenarios;
it does not itself supply product thresholds. The calibration report must make the chosen trade-off
between false late recovery, abstention rate and warm-up duration explicit.

```python
@dataclass(frozen=True)
class ThermalEvidenceGateCalibration:
    calibration_id: str
    profile_ref: RelationProfileRef
    benchmark_protocol_version: str
    replay_fixture_set_fingerprint: str
    field_pilot_protocol_version: str
    field_pilot_evidence_fingerprint: str
    minimum_passive_drift_support_per_cell_delta: int
    minimum_active_response_support_per_cell_delta_step: int
    minimum_distinct_calendar_blocks_per_cohort: int
    bootstrap_replica_count: int
    minimum_valid_bootstrap_replicas: int
    maximum_response_interval_width_c: float
    maximum_trajectory_error_by_horizon_c: CanonicalJsonObject
    prediction_interval_nominal_coverage: float
    minimum_empirical_prediction_interval_coverage: float
    minimum_independent_thermal_shadow_episodes: int
    maximum_conservative_recovery_underprediction_rate: float
    approved_by: str                    # reviewed core-release authority, never household admin
    calibration_evidence_fingerprint: str
```

All support/block/replica/shadow counts are positive integers and
`minimum_valid_bootstrap_replicas <= bootstrap_replica_count`. Every error/interval-width value is
finite and positive; `maximum_trajectory_error_by_horizon_c` contains exactly one finite positive value
for every profile-declared outcome horizon. Both coverage values are in `(0, 1]` with empirical minimum
no greater than nominal coverage, and the allowed underprediction rate is in `[0, 1)`. These invariants
and all fields are frozen with the profile version. The calibration must cover both passive-drift and active-response cohorts; heating and cooling where each is supported;
the declared context, thermal-delta and recovery-step partitions; forecast/sensor uncertainty; and
representative thermal mass and actuator-response regimes. A cell/delta/step artifact is eligible only
when it meets every corresponding frozen gate: passive support applies to its cell/delta cohort,
active support and thermal-shadow evidence apply to its exact cell/delta/step bucket, and no missing
bucket may borrow a threshold result or evidence from a neighbour.

The field pilot validates external validity of the release gate, not a cross-home serving model. Each
participating household explicitly opts in; its local instance remains `notification_only` and produces
no pilot-specific automatic `ApplyStep`. Raw fact history, calendar content, resident identity and
artifact payload stay local. The release process receives only protocol-bounded, redacted aggregate
outcomes sufficient to evaluate warm-up duration, abstention, interval calibration and conservative
recovery underprediction. Withdrawal ends future collection. Pilot evidence never enters another
household's artifact, candidate, envelope, action decision or runtime evaluation.

There is intentionally no Initial-V3 numeric default in this specification. Until a reviewed core
release supplies this complete calibration and its reproducible evidence, the profile remains
diagnostic-only and cannot produce a `LearningProposalCandidate`. Once frozen, a changed numeric gate,
benchmark protocol, fixture set, metric definition, or trade-off is a new profile/calibration version:
it invalidates affected operational artifacts for new candidate production and never silently promotes
or rewrites a pending proposal or configured Reaction.

The core baseline estimator for every active profile, including eligible `hvac_thermal_response`, is
`StratifiedResponseModel`. It compares only complete observed-transition
`EnvironmentalEpisode` records with a profile-declared reference cohort from the same canonical
profile and `transition_class_id` cell. A reference cohort contains `EnvironmentalReferenceWindow` records:
bounded historical windows with the same typed pre-anchor context and post-anchor outcome shape, where
the relevant physical state is observed stable for the profile-declared pre/outcome/exclusion interval.
It is not an `EnvironmentalEpisode` and never pretends that a transition occurred.
Any declared reference or confounder-exclusion span with incomplete
`ObservationCoverage` or truncated retention rejects it: an unobserved interval
cannot become a stable no-action reference. The same freshness, completeness, and
confounder rules apply. For each supported class/context cell and declared outcome
horizon the artifact persists the bounded empirical response distributions, their declared descriptive
quantiles, support of both cohorts, uncertainty interval, and coverage/eligibility status. It never pools
start, modification and termination cohorts or different registered
modification directions/ranges. Its primary
estimate is the difference of the two cohort medians:

```text
response_delta_p50 = median(transition_outcomes) - median(reference_outcomes)
```

`response_delta_p50` has the raw unit and orientation of the declared outcome. It is not a generic
"benefit" score: the relation profile alone defines how an outcome direction relates to a candidate
intent, and Layer 5 still applies its independent current-state guards. The artifact also preserves
the p10/p50/p90 outcome quantiles for both cohorts, so a reviewer can distinguish a typical shift from
a wide or asymmetric response distribution. The estimator never interpolates between cells, searches
for nearest contexts, pools incompatible profiles, or attributes a difference to an action. Its
published conclusion is strictly an **observed conditional response difference**. Insufficient support
in either cohort leaves that cell unavailable rather than borrowing evidence from another cell.
Cell availability is local to its exact profile, transition class, context
and horizon: absence of one class estimate does not invalidate another
eligible class or decide whether a descriptor's separate deterministic step
may run. Layer 5 declares and checks each programmed step's estimate
dependency under §3.2; Layer 3 publishes evidence, never a fallback target.
Observed resident, external and Heima-origin transitions retain their
attribution and enter a profile's cohort only when its declared physical
matcher, coverage and confounder rules admit them. The cohort records the
actual bounded pre/post target, not a developer-assigned improvement for a
particular target. An eligible modification-class response can inform the
descriptor's current decision, but it does not prove that the target is
needed now or that an entire later program will achieve its objective.

The uncertainty interval is a core-owned percentile **temporal block bootstrap** of
`response_delta_p50`, never an iid resampling of individual records. For one profile cell, the
evaluator partitions the chronological transition and reference records into common calendar blocks.
Each block has duration at least the profile's `dependency_window`, defined as the maximum of its
feature lookback, required stable-state hold, confounder exclusion, and outcome horizon. Each bootstrap
replica resamples whole calendar blocks with replacement, then recalculates both cohort medians and
their difference from the retained records. A replica lacking either cohort is invalid; an analysis
with too few valid replicas is unavailable. The artifact records the bootstrap algorithm/version,
the seed obtained from the SHA-256 digest of the RFC-8785-canonical JSON object containing
`definition_fingerprint`, `canonical_cell_key`, `training_span`, and `bootstrap_version`, replication
count, interval coverage, block duration, valid-replica count, and lower/upper bounds. This preserves
local temporal dependence and makes the published artifact reproducible.
The `canonical_cell_key` includes `transition_class_id`, so two physical
transition classes cannot share a bootstrap sample identity or interval.

The profile's frozen calibration is the sole owner of these gate values:
`EnvironmentalResponseGateCalibration` (support per cohort, distinct calendar blocks, bootstrap
replicas, interval coverage and maximum interval width in the outcome's canonical unit) or, for
`hvac_thermal_response`, `ThermalEvidenceGateCalibration`. A cell is usable only when both
cohort-support gates and its temporal-diversity gate pass and its bootstrap interval is no wider than that
calibration's limit. These gates are evidence qualifications, not user-configurable confidence thresholds and not a
claim of causal significance. Bootstrap resampling is used because the uncertainty of a median-derived
statistic generally has no convenient analytic form ([NIST bootstrap guidance](https://www.itl.nist.gov/div898/handbook/eda/section3/eda334.htm)); block resampling rather than iid resampling is required
because the records arise from a temporally dependent house process
([Politis and Romano, stationary bootstrap](https://doi.org/10.1080/01621459.1994.10476870)).

An `EnvironmentalEpisodeLearner` instance also declares one mandatory, core-owned `objective_id` and
one explicit positive `minimum_practical_delta`, represented in the declared outcome's canonical unit.
There is no global objective or materiality default. The selected relation profile's policy facet
validates the closed objective vocabulary, its compatible outcome orientation, permitted action intent,
and the threshold's unit/range. This is deliberately separate from the response estimate: a lower room temperature, for
example, is not intrinsically desirable without an explicit objective. Initial objective/action pairs
include `limit_solar_gain -> increase_shading`, `admit_solar_gain -> decrease_shading`,
`admit_daylight -> decrease_shading` (`solar_shading` only), `cool_with_outdoor_air ->
open_for_exchange`, `warm_with_outdoor_air -> open_for_exchange`, `limit_thermal_exchange ->
close_to_retain`, `reduce_co2 -> open_for_exchange`, `reduce_moisture -> open_for_exchange`,
and `reduce_moisture -> activate_extraction`/`adjust_extraction`
(complete matrices in Layer 5 §7); they are finite
profile-owned semantics, not admin-authored labels or an arbitrary utility function.

A usable cell enters a policy candidate's `CanonicalEnvelope` only when the bootstrap interval proves
the declared practical direction: for a positive desired response its lower bound is at least
`minimum_practical_delta`; for a negative desired response its upper bound is at most the negated
threshold. The profile may apply no weaker rule. This test only establishes that the supported
observational response is directionally material under the selected objective; it does not evaluate
current comfort, safety, weather, security, manual hold, or resident preference.

`objective_id` and `minimum_practical_delta` are `serving_semantics`: changing either never retrains
or invalidates the response artifact, but immediately withdraws an unreviewed candidate selected under
the preceding values and re-evaluates candidate/envelope eligibility from the same compatible artifact.
The artifact's `definition_fingerprint` and `analysis_revision` stay fixed;
the `serving_generation_fingerprint` changes.
They enter the candidate's semantic payload and deduplication fingerprint. A previously approved
configured Layer-5 policy is not silently altered; a changed objective or threshold creates a distinct
ordinary review proposal.

`StratifiedResponseModel` refines the common chronological validation contract of §4.7 with mandatory
walk-forward evaluation. Each fold fits only on an earlier complete training span, applies an embargo
at least as long as `dependency_window`, then evaluates only on later complete transition/reference
records. A record or its feature, stable-state, exclusion, or outcome window may not cross a train,
embargo, validation, or final-holdout boundary. Folds advance only forward in time; random splitting,
shuffling, or reuse of a later record in an earlier fit is forbidden.

The last eligible chronological segment is an untouched final holdout. The artifact considered for
publication is fitted only on evidence preceding that segment and is scored unchanged on it; it is not
refitted with final-holdout evidence after passing. A later ordinary rebuild may incorporate that past
holdout only when it creates a fresh later validation/final-holdout sequence. This trades a small
amount of immediately usable history for an honest publication test.

For every profile cell with complete validation cohorts, the evaluator computes
`holdout_delta_p50 = median(holdout_transition) - median(holdout_reference)`. It records absolute
delta error `abs(response_delta_p50 - holdout_delta_p50)`, directional agreement, and whether the
holdout delta lies within the artifact's training-derived bootstrap interval. The latter is an empirical
stability/coverage observation, not a confidence or causal-probability claim. The required baseline is
`zero_response`, whose error is `abs(holdout_delta_p50)`: a profile must beat that baseline on its
core-declared aggregate error criterion and satisfy its direction, interval-coverage, cell-coverage,
and temporal-slice thresholds. The profile fixes its slices, for example the declared solar-exposure or
indoor/outdoor-delta bands; an aggregate score cannot conceal a failing operational slice.

A cell lacking complete holdout cohorts, failing any profile validation gate, or falling outside the
validated slice coverage remains diagnostic-only and is excluded from `CanonicalEnvelope`. If the
remaining validated cells do not meet the profile's minimum viable envelope, the whole artifact is
`diagnostic_only` and cannot produce a policy candidate. For every initial relation profile, that
predicate is deliberately minimal and exact: at least one validated cell, with every profile-required
axis resolved and with all per-cell support, temporal-diversity, interval, walk-forward, and slice gates
already passed. There is no global percentage of a geometric context space, minimum count of adjacent
cells, continuous-range requirement, nearest-cell expansion, or implicit interpolation.

This choice is intentional. A single cell such as "high southern solar exposure while the room is
already warm" can be a precise and valuable candidate; requiring broad coverage would either suppress
it arbitrarily or reward unsupported extrapolation. Conversely, one broad aggregate score cannot
conceal a weak required slice because each envelope cell is independently validated. The relation
profile may define a stricter core-owned predicate in a future version only when its physical semantics
require it; neither an administrator nor a learner/plugin supplies one. This follows the use of
explicit per-slice value/change thresholds in [TFX Model Analysis](https://www.tensorflow.org/tfx/model_analysis/model_validations)
and scenario-specific rather than universal building-control evaluation in
[BOPTEST](https://ibpsa.github.io/project1-boptest/testcases/).

Expected opportunity is intentionally a separate review diagnostic, not a viability or authority gate.
For each candidate, the slow path reports its observed entries into validated cells as a count and rate
over a profile-declared recent historical observation window, with the window/span and data coverage.
The core may classify that evidence as `recurring`, `occasional`, or `rare` using profile-owned
thresholds, so review can distinguish a daily shading opportunity from an infrequent weather regime.
Opportunity frequency never adds an unsupported cell, suppresses a statistically valid rare candidate,
changes a configured Reaction's execution authority, or alters live Layer-5 evaluation. It is excluded
from the candidate deduplication fingerprint: a changed observed rate refreshes review evidence rather
than creating a different policy proposal.

This adopts the baseline comparison and slice-specific validation discipline used by
[TFX Evaluator](https://tensorflow.github.io/tfx/guide/evaluator/) while keeping environmental control
benefit itself outside observational validation and subject to the separate simulation/experiment
boundary of §4.7.

`StratifiedResponseModel` deliberately reuses the staged bindings, canonical context transforms,
warm-up, complete-interval rules, chronological validation, artifact lifecycle, and operating-envelope
rules already defined for Layer 3. It introduces neither an online optimizer nor a second generic
feature pipeline. A later core-owned ML estimator may replace this estimator only within
`EnvironmentalEpisodeLearner` and only when it preserves the same versioned episode/profile contract,
outcome schema, uncertainty/calibration requirements, envelope semantics, validation protocol, and
Layer-5-only proposal boundary. This follows the separation of observations, actions, constraints, and
benchmark KPIs used by building-control research environments such as
[BOPTEST](https://ibpsa.github.io/project1-boptest/docs-userguide/introduction.html) and
[CityLearn](https://www.citylearn.net/quickstart.html): Heima does not promote an observational
estimator into an online optimizer or reinforcement-learning controller.

Fan/VMC state and speed, occupancy, actual HVAC mode/action and target or delivered power,
per-room temperature, internal-opening state, energy measurements, VOC/PM, and local solar/illuminance
measurements are declared enrichments where available. Their absence never becomes an implicit
substitute. In particular, a model without CO2 may propose only a thermal exchange, never an indoor
air-quality improvement; a solar model without measured or explicitly trusted radiation may only make
the weaker conditional claim supported by its `thermal_shading` profile. Indoor illuminance is required
only for an `admit_daylight` objective; it is not a proxy for glare.

The state of an opening or cover is an observed physical fact, not the last Heima command. An exterior
opening without an actuator remains eligible evidence: its approved policy can use an advice member
(Layer 5 §3.2) that produces a user-facing `reaction.advisory`, never an unavailable command. Layer 3 itself neither chooses a target nor commands
HVAC, openings, shutters, or fans.

No profile may invent a physical coefficient or airflow claim when the data cannot identify it.
Insufficient variation in weather, solar exposure, cover/opening state, HVAC operation, or adjacent
room temperature is missing evidence and causes the affected candidate to remain unavailable or
diagnostic-only.

#### 4.8.1 EnvironmentalEpisode and outcome contract

`EnvironmentalEpisodeLearner` learns only from the common `EnvironmentalEpisode`. Its `anchor_at` is
the timestamp of one profile-declared, observed physical state transition on a staged registered
Sensor state or Actuator channel, never the timestamp of a requested command. A profile fixes the
exact source `FactRef`, canonical state contract, channel/facet identity where applicable, and
versioned transition matcher before training. Existing cover, opening and HVAC-action transitions
use this same rule. The required Initial-V3 extraction profile, and a later
humidifier or dehumidifier profile, declare their own
compatible observed transition and outcome without another learner implementation. For Layer 0
§5.1.1.1 `actuator.channel_state.<digest>` sources, the anchor requires an available valid record
whose `changed_facets` includes a profile-declared facet, a matching registered logical channel and
observable-state contract, and a complete preceding state in the same observation epoch. The first
valid reading after restart or an availability gap has no changed facets and cannot be an anchor.
An unchanged value, service-call completion, `already_satisfied` decision, or unrelated facet change
is not a physical transition. The profile's bounded transition matcher, binding and required
history enter its definition fingerprint; observed origin remains evidence, not a causal claim.
The registered matcher classifies the complete pre/post physical edge into
exactly one `transition_class_id` or excludes it. A class can describe a
program start, bounded target modification or termination; for a quantitative
modification its matcher distinguishes direction and bounded pre/post target
range. The class is profile-owned and reusable across Actuator kinds, never
derived from an HA domain or a Heima command label. The episode and its
comparable stable-pre-state reference windows retain that class id;
`environmental_response.v1` cells carry it explicitly. A single-class
output such as `ThermalResponseParameter` keeps its existing shape: its
exact profile/version resolves the sole registered `primary` class without
adding a field to that parameter. An edge matching two classes is invalid
rather than counted twice.
For a profile of temporary Actuator operation, learning retains the complete
observed entry state, the physical transition sequence and verified origin
per edge. An extraction activation that finds a fan already active is a
no-intervention decision, not a fan-start response episode. An observed
inactive-to-active transition and later speed or stop transitions each form
their own profile-declared class and estimate only with complete pre/post,
matching stable-state reference and confounder coverage. Initial and
resulting speed remain typed context;
active-at-entry observations cannot be silently pooled with
inactive-at-entry activations to estimate the latter's response. The
`humidity_extraction` profile registers three classes on the fan's canonical `level` facet:
`start` (`off -> level k`), `modify_up` (`level k -> level k+1`) and `terminate`
(`level k -> off`); initial and resulting levels remain typed context, and any other edge (a
downward step, a jump of more than one level) is excluded. Its outcome is the room humidity-ratio
change at the calibrated horizons; each class's reference cohort is stable-state windows with the
fan at the class's pre-state level. `terminate` is learned as diagnostic evidence only. Recording or
estimating a level edge does not itself authorize a level policy.
Its named, typed feature bindings describe only the context at or before that transition: the selected
profile's measurements, topology, solar/weather conditions, presence where declared, and all relevant
observed device states. Its named outcome bindings describe measurements strictly after the anchor at
the relation-profile-declared horizons.

An episode is rejected when any required pre-anchor, post-anchor, or confounder-exclusion
read has truncated retention or incomplete `ObservationCoverage`, or when its required
observation is stale, missing, or invalid. It is also rejected when the post-transition
state cannot be observed for the declared minimum window or when a declared
confounder occurs in its exclusion window. At minimum, confounders include a relevant HVAC mode,
action, target, or delivered-power change; another relevant registered Sensor or Actuator-channel
transition, including cover/opening changes where applicable; and any other relation-profile-declared
control change that invalidates attribution. A short-lived transition is consequently
not evidence merely because it appeared in the history.

Each registered relation profile owns a bounded list of outcome horizons; there is no global
environmental response duration. Initial target shapes are: room-temperature change for thermal
shading and thermal exchange; indoor illuminance change only where an indoor illuminance binding is
declared; CO2 reduction or time below a declared threshold for air-quality exchange; and humidity
change for hygrometric exchange; and room humidity-ratio change after the fan's `start` or
`modify_up` transition for `humidity_extraction`. The evidence-gated `hvac_thermal_response` profile uses a
room-temperature trajectory only when it meets the evidence-gated eligibility contract in §4.8 and
the `hvac_thermal_response` requirements in §8 item 6. The horizons, target shape, exclusion
policy, and relation profile all enter the definition fingerprint.

The artifact may compare a transition episode with profile-matched `EnvironmentalReferenceWindow`
records under comparable declared context, but this yields an **observed conditional response
difference**, not proof that the action caused the result. A claim of causal comfort, energy, or
air-quality benefit requires the separate shadow evaluation and, where the relation profile requires
it, a declared simulation or explicitly approved experiment under §4.7.

#### 4.8.2 Environmental input bindings

`EnvironmentalEpisodeLearner` profiles read only complete Layer-1 `HouseFact` records through named,
typed binding slots. A declaration resolves each slot to a `FactRef` during staging; the validator checks the
expected value shape/unit, required `Location`, source availability/freshness policy, and profile
eligibility. It never reads an HA `State`, entity attribute, actuator target, buffer, or payload.
For a quantitative slot, staging checks the producing Layer-2 Sensor's
canonical unit contract against the slot unit; history and current inference
use only the resulting canonical value. A unit-drift `available=False` fact
cannot become an episode sample or a thermal parameter input.
An indoor slot (`room_temperature`, `room_co2`, `indoor_humidity`, `indoor_humidity_ratio`,
`room_illuminance`) binds only a room in the thermal envelope (Layer 1 §6.1/§7); a reading in an
`exterior` room, such as a terrace temperature, may bind only an outdoor slot, explicitly. An
`observed_opening_state` used as exchange evidence requires an opening that faces an exterior side.
The initial core-owned slots are `room_temperature`, `outdoor_temperature`, `room_co2`,
`indoor_humidity`, `outdoor_humidity`, `indoor_humidity_ratio`, `outdoor_humidity_ratio`,
`room_illuminance`, `solar_irradiance`, `incident_solar_exposure`, `outdoor_air_quality`,
`observed_opening_state`, `observed_cover_position`, `actual_hvac_action`, `observed_hvac_mode`,
`observed_hvac_target`, `hvac_delivered_power`, and `observed_actuator_channel_state`. A registered family may require only the slots
its `relation_profile` permits. `observed_hvac_target` and `hvac_delivered_power` are optional
installation capabilities, never values read from an HA attribute by a learner.

`room_*` slots resolve at the subject room, while outdoor/radiation slots resolve at `casa`.
`observed_opening_state` and `observed_cover_position` resolve at the opening owner's room and must
trace to a Layer-2 Sensor with one `related_opening_id`; a derived fact is accepted only when every
physical source traces to that same id. This preserves the distinction between two openings in one
room without adding an opening scope to `Location`. Opening and cover readings use stable logical
Sensor identities in their fact types, for example `environment.opening_state.<sensor_id>` and
`environment.cover_position.<sensor_id>`, never a Home Assistant `entity_id`.
`observed_actuator_channel_state` resolves to exactly one staged
`actuator.channel_state.<digest>` state `FactRef` for the profile's registered
`(actuator_id, controlled_channel)` at its owning room, with the declared
`observable_state_contract_id` and a bounded core matcher over named canonical
facets. Layer 0 §5.1.1.1 supplies its observed changed-facet projection; Layer 3
does not read raw HA attributes, invent an origin, or infer an Actuator's
purpose from its HA domain. A profile selects one physical transition source
per episode so parallel Sensor and channel projections of the same physical
change cannot double-count it. A different channel, mismatched contract,
unavailable reading, incomplete predecessor history or post-restart baseline
cannot be substituted for the declared anchor.
For an extraction fan, the staged canonical `level` facet (`off` or `1..N`) preserves
whether it was already active at a qualifying start and which physical
level transitions followed. No requested level, last Heima command or
assumed ownership replaces those observations. Complete observed level
changes can inform a registered response profile; an active-at-entry
no-command decision remains separate from an observed response to a change.

Solar geometry is also a declared fact input, supplied by the two
core-generated Layer-2 `Sensor` registrations of Layer 2 §3.6 as
`external.solar_elevation` and `external.solar_azimuth` at `casa`; both read
one frozen `sun.sun` state, enforce freshness, and convert degrees to canonical
radians. It is not recomputed ad hoc by a learner from raw HA configuration.
The core `environment.solar_incidence.v1` FormulaStrategy
uses Layer 2 §5.3's closed staged configuration to capture one opening's id and resolved
orientation before combining this geometry with that opening. For a
vertical opening its geometric direct-incidence proxy is zero when
`elevation <= 0`; only above the horizon is it
`max(0, cos(elevation) * cos(solar_azimuth - opening_orientation))`. Without
that horizon gate the cosine expression would falsely report solar exposure
at night. With direct-normal irradiance it
becomes direct incident irradiance, and a measured/trusted diffuse component completes
`environment.incident_solar_exposure.<solar_binding_id>`. The stable `solar_binding_id`, not a raw
`opening_id`, is the fact-type suffix; staging resolves it back to exactly that opening. Without
radiation the proxy remains a dimensionless eligibility/context signal, never a claim of W/m2 solar
gain. Topology supplies the associated opening's resolved exterior connection, and its canonical
fingerprint enters the learner definition. A source or topology generation change therefore invalidates
the affected model through the normal fingerprint path rather than changing the meaning of a sample in
place.

This split follows building-simulation practice, where per-window solar radiation and geometry are
distinct from daylight and glare calculations ([EnergyPlus engineering reference](https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v22.1.0/EngineeringReference.pdf)). It also avoids importing a
universal radiation threshold: observed blind-use studies use probabilistic models conditioned on
radiation, solar altitude, orientation, and occupant/context variables, rather than a transferable
single setpoint ([field study](https://www.sciencedirect.com/science/article/pii/S0360132312000558)).
The learner estimates this home's conditional observed response; it does not claim a general physical
formula, causal effect, or utility optimum is sufficient.

#### 4.8.3 Environmental exchange response and resident preference

The `thermal_exchange`, `air_quality_exchange`, and `hygrometric_exchange` profiles estimate the
observed conditional response after one exterior-opening transition on their declared thermal, CO2, or
moisture outcome. They do not learn
"what residents usually do" as though that behavior were the environmental optimum. Temperature,
CO2, relative humidity, occupancy, time of day, and outdoor conditions are well-established predictors
of manual window behavior, but their importance varies materially by household, room, and season
([one-year residential study](https://pubmed.ncbi.nlm.nih.gov/30468527/),
[multi-season field study](https://www.sciencedirect.com/science/article/pii/S0360132317303888)).

An optional, separate `ResidentPresentationPreferenceModel` may learn a supported non-safety
notification priority, quiet-period, channel, or frequency parameter for one declared
`presentation_scope`. This is a generic presentation scope supplied by a registered Reaction
descriptor, such as its semantic intent plus explicit Location; it is never a raw HA entity, payload,
or a ventilation-specific model. The model uses only explicit resident feedback such as useful/not
useful, postpone, disable, or a declared action response, including the `reaction.advisory_feedback`
answers recorded by Layer 5 (§6.0 of Layer 5). Missing response is censored evidence, not
rejection. Its outcome is a reviewed delivery-parameter candidate only: it cannot change an
environmental effect estimate, message meaning, guard, safety classification, policy eligibility, or
actuator policy. A safety-critical notification is never delayed, ranked below another notification,
suppressed, or otherwise modified by this model. This lets Heima adapt notification presentation
without mistaking environmental behavior or non-response for a comfort, IAQ, or energy preference.

`hvac_thermal_response` is an additional profile of this same learner, not a heating-eco analyzer or
an HVAC control path. Its anchor is one observed transition of the registered `actual_hvac_action`
for the explicit conditioned scope; its complete outcome is the declared room-temperature trajectory
at the profile horizons. A profile-matched no-active-HVAC `EnvironmentalReferenceWindow` may model
passive thermal drift, but it is never an implicit default temperature or a substitute for an observed
HVAC transition. Required context includes `room_temperature`, `outdoor_temperature`,
`actual_hvac_action`, and the explicit `observed_hvac_mode`; solar exposure, the compatible observed
target, and delivered power are used only where staged and available. An unrelated HVAC transition,
manual setpoint change, opening/cover transition, or other profile-declared thermal disturbance in the
exclusion window rejects the episode rather than being averaged into it.

Its Initial-V3 operational use is a bounded thermal-reachability artifact for Layer 5's HVAC descriptor.
It estimates passive drift and recovery-step duration for an exact scope, mode and context bucket;
Layer 5 combines that evidence with administrator-authored absence/return bounds to decide the next
safe step. It cannot select or cap a target, choose an endpoint, schedule recovery, issue an
`InferenceSignal`, or command an Actuator. The same validated artifact may be consumed only by Layer
5's `environment.planned_comfort_trajectory`, under its separate current-absence, calendar,
comfort/energy, guard and shadow-validation contract; that descriptor requires a current stabilized
household `presence=away` claim plus an active matching plan, uses `presence.departure` only for
live-process reevaluation, and treats committed `presence.return` as terminal cancellation. This profile never
creates a recovery schedule itself. Without an
explicitly bound energy measurement, its validation and
proposal may claim only bounded thermal
comfort/safety applicability, never energy savings. This follows the system-specific limits of
residential setback operation documented by the [U.S. Department of Energy](https://www.energy.gov/sites/prod/files/2014/07/f17/ba_case_study_hydronic_setback.pdf) and the need to evaluate comfort and
setback recovery together in [ASHRAE supervisory-control guidance](https://handbook.ashrae.org/Handbooks/A23/IP/A23_Ch43/a23_ch43_ip.aspx).

`thermal_exchange` uses the indoor/outdoor temperature gradient and declared actual HVAC state as
context. `air_quality_exchange` uses room CO2 as the measured outcome; its profile may be learned
without an outdoor-air-quality binding, but automatic opening additionally requires the
`outdoor_air_quality` guard to be fresh and acceptable under the selected guard profile. A pollution
binding may represent PM2.5 or a core-normalized outdoor-air-quality classification with its own
provenance; no universal threshold is embedded in the learner. This follows public-health guidance
that opening windows can worsen conditions when outdoor air quality is poor
([Health Canada guidance](https://www.canada.ca/content/dam/hc-sc/documents/services/publications/healthy-living/guidance-indoor-air-quality-professionals/guidance-indoor-air-quality-professionals.pdf)).

`hygrometric_exchange` compares moisture content, never raw indoor/outdoor relative humidity. A
core FormulaStrategy derives `environment.humidity_ratio.<humidity_binding_id>` from temperature,
relative humidity, and either a bound pressure fact or an explicit installation reference pressure:
`p_v = RH * p_ws(T)` and `w = 0.621945 * p_v / (p - p_v)`. The formula emits kg water/kg dry air and
uses Layer 2 §5.3's closed `environment.humidity_ratio.v1` configuration. It is
unavailable when its declared pressure source/configuration is absent or invalid; it does not fall
back to comparing RH. An optional staged formula may derive moist-air enthalpy
`h = 1.006*T + w*(2501 + 1.86*T)` kJ/kg dry air for a joint thermal/moisture context, but it is a
proxy for the relative desirability of external air, never a measured airflow or energy saving. This
uses the standard psychrometric quantities defined by [ASHRAE](https://handbook.ashrae.org/Handbooks/F21/SI/F21_Ch01/F21_Ch01_si.aspx)
and used by [EnergyPlus psychrometric functions](https://energyplus.net/assets/nrel_custom/pdfs/pdfs_v25.1.0/EngineeringReference.pdf).

Studies also use logistic probabilities and survival models for opening/closing events. Those are
valid future core learner types for resident-behavior timing, but the initial exchange policy uses its
own observed-outcome model and the bounded episode contract; it does not adopt a generic probability
threshold as a command rule ([survival-model study](https://www.sciencedirect.com/science/article/pii/S2210670720302043)).

#### 4.8.4 Environmental safety and comfort envelope

Learning does not enforce live safety or comfort. An environmental `LearningProposalCandidate` may
describe only the exact core `ReactionGuardCapabilityRef`s required by its selected Layer-5
guard contract. It neither embeds a threshold/binding, arbitrary live predicate, nor decides that an
observed historical condition is safe enough now.

Layer 5 may admit an environmental `ReactionProposal` for review only when a core-defined
`ReactionGuardProfile` supplies every required capability. Its numeric limits and the enabled
weather/security/presence checks are explicit administrator configuration, with no hidden global
defaults. An accepted proposal creates only a `notification_only` `ConfiguredReaction`; automatic
actuation belongs exclusively to that reaction's subsequent authenticated promotion and required
household consent. On every proposed execution, Layer 5 evaluates the reaction's current facts and
resolved semantic claims. An unavailable, stale, or invalid required guard fact blocks automatic
actuation. An active manual hold or a higher-precedence safety/security policy always blocks it and is
not overridable by a learner or guard profile.

A candidate without an owned compatible actuator is necessarily `notification_only`. Every newly
approved environmental policy also begins `notification_only`; changing it to automatic actuation is
a separate authenticated administrative transition, requiring a complete compatible guard profile and
a fresh Layer-5 validation. Retraining, a new artifact, high confidence, or shadow promotion cannot
alter that execution mode or expand the policy's authority. A later artifact may revise an already
approved policy only through the general adoption contract in §4.9, and only within that policy's
pre-authorized semantic scope, action endpoints, guard profile, and parameter bounds.

#### 4.8.5 Environmental validation and KPIs

Every `EnvironmentalEpisodeLearner` artifact records profile-specific chronological validation metrics, its declared
baseline, uncertainty calibration, and coverage of the contexts in which it may propose a policy.
`thermal_shading` and `thermal_exchange` require temperature error at every declared horizon and
comfort-range degree-minutes where an administrator-configured comfort range exists.
`solar_shading` with an indoor-illuminance binding additionally requires illuminance error and,
where configured, time in the desired illuminance range. `air_quality_exchange` requires CO2 error,
predicted time below threshold, CO2 ppm-minutes above threshold, and observed recovery time.
`hygrometric_exchange` requires humidity-ratio error; where an administrator also configured a
relative-humidity comfort range, it records time outside that range as an operational comfort metric.
`humidity_extraction` requires humidity-ratio error per transition class and horizon and the
observed time for relative humidity to return to the configured end level.
No profile can become eligible when it lacks the metrics needed to substantiate its own permitted
meaning.

When the evidence-gated `hvac_thermal_response` profile becomes eligible, it requires room-temperature
trajectory error at every declared horizon, comfort-range degree-minutes where the registered HVAC
descriptor declares a range, prediction-interval coverage, and operating-envelope coverage for both
active HVAC and passive-drift cohorts. It records energy error or energy benefit only when a staged
energy/power outcome makes that claim measurable; without it, the profile cannot promote an
energy-benefit assertion.

All environmental profiles also record abstention rate, guard-block rate, manual holds and resident
corrections, notification frequency, and resident response to a notification where available. These
are safety and operational-friction observables, not targets the model may optimize; in particular,
resident acceptance is not evidence that a predicted effect was correct. Energy benefit is reported
only when a declared energy/power binding supplies a suitable measured outcome. Device runtime,
cover position, or a modeled estimate may be recorded as a proxy with its own name, never as kWh
saved.

Shadow evaluation measures predictive quality, calibration, coverage, and hypothetical-policy
feasibility only. It cannot establish benefit from an action it did not perform. Post-approval
observations may compare actual policy episodes with declared comparable baselines as operational
evidence; a causal comfort, air-quality, or energy claim still requires a declared simulation or an
explicitly approved, bounded experiment such as a temporal switchback. Baseline, calibration, and
coverage must all meet the profile's promotion floor before the administrative promotion transition
is available.

#### 4.8.6 `EnvironmentalQuantileResponseModel`

`EnvironmentalQuantileResponseModel` is the first optional ML estimator registered within
`EnvironmentalEpisodeLearner`. It is a versioned replacement for `StratifiedResponseModel`, not a
second environmental learner, policy engine, feature pipeline, or action path. It preserves the same
`relation_profile`, named staged bindings, typed outcome and horizon, complete-interval requirement,
topology validation, objective contract, Layer-5-only candidate boundary, and artifact adoption rules.
It exists only where the exact cells of the statistical baseline are too sparse to represent a real,
measurable non-linear relation among already-declared physical context variables.

The estimator learns an **observed conditional response contrast**, never a causal effect or a
counterfactual action result. For one profile, `transition_class_id` and
outcome it fits two separate cohort predictors over
the identical pre-anchor feature space:

- `transition_model` uses only complete observed-transition `EnvironmentalEpisode` records;
- `reference_model` uses only complete stable-state `EnvironmentalReferenceWindow` records.

It never pools records from another transition class, trains one model with
a synthetic "action happened" feature, requests an unobserved action,
or simulates a command. At serving context `x`, it compares the separately observed conditional
outcomes of these cohorts. This is deliberately the ML analogue of the baseline's two-cohort
comparison, so it retains the statement "conditional observed response difference" rather than
promoting observational home data into a causal claim.

The initial algorithm is core-owned `QuantileGBDT-v1`: bounded gradient-boosted decision-tree
quantile regression. For each cohort it fits independent `q10`, `q50`, and `q90` estimators against
the declared scalar physical outcome. Quantile loss estimates a conditional quantile and can be used
to construct prediction bands ([scikit-learn ensemble guide](https://scikit-learn.org/stable/modules/ensemble.html)).
Tree count, depth, leaf-support rule, iteration limit, feature encoding, and any trainer implementation
are fixed by this versioned core algorithm; they are not per-home admin settings and no generic
hyperparameter search is permitted. The artifact stores a bounded, canonical, core-owned tree codec
and algorithm parameters, never a pickle, callable, opaque library object, or trainer dependency.
A future trainer may run locally or through the bounded execution boundary in §5.3, but local serving
decodes only this verified immutable codec and remains I/O-free.

Every ML feature is a required, named, typed binding already legal for the selected relation profile.
It is read only at or before the anchor, represented in its canonical unit/value vocabulary, and is
complete in both training and serving; a missing value excludes the record or serving evaluation rather
than invoking implicit imputation. Continuous features use the algorithm's versioned deterministic
encoding; closed categorical features use their staged vocabulary. No raw HA object, actuator command,
mutable buffer, payload, post-anchor observation, or free-form category reaches the estimator.

The artifact also publishes an `ApplicabilityEnvelope`, which is a serving gate rather than an
additional learned policy. It contains: the closed categorical values observed in **both** cohorts;
the observed finite lower and upper bound for every continuous feature in both cohorts; and a
profile-declared coarse support partition with minimum support in both cohorts. The partition is a
versioned canonical context transform staged with the profile, not a nearest-neighbor search or a
learned similarity score. A context outside any such bound, vocabulary, or supported partition is
`out_of_operating_envelope` and produces no response estimate or candidate. Inside the envelope,
the estimator may model a continuous non-linear response between observed values; it may never
extrapolate beyond the envelope or silently borrow another relation profile.

For serving context `x`, the result records both predicted cohort bands and derives a conservative
contrast envelope in the physical outcome unit:

```text
transition: q10_t(x), q50_t(x), q90_t(x)
reference:  q10_r(x), q50_r(x), q90_r(x)

conservative_lower = q10_t(x) - q90_r(x)
typical_contrast   = q50_t(x) - q50_r(x)
conservative_upper = q90_t(x) - q10_r(x)
```

This envelope is deliberately not named a confidence interval: subtracting independently estimated
outcome quantiles does not establish a confidence interval for a causal or individual-level effect.
It is a conservative algebraic contrast between calibrated predictive bands. Any quantile crossing
(`q10 > q50` or `q50 > q90`) makes that result unavailable; no sorting, averaging, or silent repair
changes the meaning of a published quantile. The result exposes its cohort values, contrast values,
algorithm/version, binding and profile fingerprints, applicability partition, and coded abstention
reason for audit.

The existing `objective_id` and `minimum_practical_delta` gate a candidate through the conservative
bound in the objective's permitted direction. A desired positive response requires
`conservative_lower >= minimum_practical_delta`; a desired negative response requires
`conservative_upper <= -minimum_practical_delta`. `typical_contrast` alone cannot authorize a
candidate. This is an evidence gate only: Layer 5 still validates semantic action intent, current
guards, scope, endpoints, execution mode, and review workflow.

Validation is the existing chronological walk-forward protocol with embargo at least equal to the
profile `dependency_window`, then an untouched final holdout. It evaluates transition and reference
models separately and the derived contrast only on common eligible profile slices. Each artifact
records, at minimum, per-cohort pinball loss for q10/q50/q90, empirical q10-q90 coverage, median
error, quantile-crossing rate, applicability-envelope coverage, and every declared environmental KPI.
It compares the same chronological slices against `StratifiedResponseModel`; a better aggregate score
cannot compensate for failed band calibration, crossing, inadequate cohort/support coverage, or a
required operational slice. Calibration and predictive accuracy are separate checks: an aggregate
score alone does not establish that an uncertainty-bearing output is reliable
([scikit-learn calibration guide](https://scikit-learn.org/stable/modules/calibration.html)).

An artifact that passes its absolute profile gates and baseline comparison may enter shadow only. Its
hypothetical contrast and candidate remain diagnostics during shadow; they cannot notify, alter an
existing policy, issue a live signal, or produce an action. Promotion is the existing authenticated
artifact-adoption decision of its consumer (Layer 5 §4.1–4.2 for a Reaction, §4.9 for a live
signal), never a configuration-generation change (Layer 0 §4.7). `StratifiedResponseModel` remains the mandatory, independently
available baseline and is never silently replaced merely because a quantile artifact exists. Building
control research similarly evaluates candidate strategies using separate physical, operational, and
computational KPIs rather than forecast error alone
([BOPTEST user guide](https://ibpsa.github.io/project1-boptest/docs-userguide/introduction.html)).

#### 4.8.7 Environmental residual diagnostics

Environmental fault/response diagnostics are not a second unsupervised engine. A core
`EnvironmentalResidualAnalyzer` may compare a complete observed outcome with the compatible
preloaded `StratifiedResponseModel` or `EnvironmentalQuantileResponseModel` expectation for the same
profile/context. Repeated, bounded residual departures can diagnose a response worth investigation,
for example a fan/opening with no observed CO2 or humidity recovery, or a cover transition with no
expected measured illuminance/thermal response where those sensors exist. It reports the observed
outcome, model band/baseline, context/envelope status, repetition count and missing-input reason; it
does not diagnose a root cause, command a device, alter a policy, or reinterpret a missing sensor as a
fault. Its sole diagnostic egress is a `DiagnosticFinding` with the registered
`environmental_residual.v1` schema. Rule-based and process-history-based diagnostics remain complementary in building FDD practice
([NIST ZandrEA](https://www.nist.gov/publications/using-zandrea-project-research-toward-better-hvac-system-reliability-large-commercial)).

### 4.9 Context coverage and continual adaptation

Heima continuously adapts its learned artifacts to new evidence, changing household behavior, and
changing environmental conditions. This is not implemented as a global categorical `Season`: a coarse
calendar label is neither an adequate explanation of weather/solar conditions nor a reliable proxy for
resident behavior. Instead every learner declares one `seasonality_mode` as part of its core-owned
type contract:

- `none` — the learner has no material annual component;
- `environmental_features` — declared contextual facts such as external temperature/humidity,
  radiation, solar geometry, HVAC state, and presence explain the relevant variation;
- `annual_phase` — the preceding features plus a core-owned, numeric cyclic annual-phase fact may model
  a demonstrated residual annual pattern. It is not a free-form calendar string or an implicit global
  input.

An artifact records its `operating_envelope`: the declared feature ranges and supported contextual
combinations for which it has sufficient eligible historical evidence. Validation is chronological and
reports quality, calibration, and coverage by that envelope's regimes rather than only an aggregate
score. Any runtime use of an artifact must abstain when the current context is outside its
`operating_envelope`, regardless of artifact staleness or the validity interval of any later egress
wrapper. A `LearningProposalCandidate` may carry that envelope for Layer-5 review, but it never
evaluates the envelope against live state itself. The suppression owner records the coverage reason and
schedules the normal bounded evidence inspection. A contextual shift is therefore neither silently
extrapolated nor automatically treated as statistical drift.

Operating-envelope coverage, artifact staleness, and egress validity are cumulative, non-interchangeable
gates. `max_artifact_staleness` decides whether the artifact is usable at all; the envelope decides
whether it is applicable to the current context; an `InferenceSignal` expiry decides whether an already
emitted live signal remains fresh; and a `LearningProposalCandidate` validity interval decides whether
Layer 5 may still review that candidate. `ResultEnvelope` has no `valid_until`: it remains an
auditable result, not a live signal or a review item.

Each learner declares the retention needed to support its own history and seasonal comparison through
Layer 0. Fourteen days remains only the default retention: a learner may request months of complete
history, subject to Layer 0's retention and storage governance. It must not impose an arbitrary annual
warm-up or infer a year-round behavior from one short period. New evidence can yield a new validated
artifact continuously, but it never expands a configured Reaction's authority or bypasses its current
guard profile.

Only an operational egress (`InferenceSignal` or an action-bearing Reaction)
requires artifact adoption. A validated `DiagnosticFinding` is a bounded
administrator-only observation: its current publication/withdrawal rules in
§6.1.1 apply without an adoption mode, proposal, or operational permission.
If one model also has an operational egress, non-adoption suppresses that
egress only; it does not suppress an independently eligible diagnostic.

For each operational consumer, the core-owned learner/model type declares
whether the administrator may select `pinned`, `bounded_adaptive`, or both.
`pinned` requires a new authenticated decision for every exact revision:
Layer 3 owns that decision for a registered `InferenceSignal` consumer;
Layer 5 owns a revision-specific reviewable adoption proposal for an
action-bearing Reaction. `bounded_adaptive` is an explicit, pre-authorized
compatibility envelope: the core validator may adopt a later validated
artifact only if the type-specific predicate proves that it remains within
the pre-approved authority. A learner, model, or plugin cannot select the
mode or weaken its predicate.

```python
@dataclass(frozen=True)
class SignalArtifactAdoptionTransition:
    transition_id: str
    transition_kind: Literal["initial", "pinned_revision", "bounded_refresh", "mode_change"]
    operation_id: str                  # stable retry identity for admin or core transition
    learning_instance_id: str
    definition_fingerprint: str
    serving_generation_fingerprint: str
    signal_type: str
    contract_id: str
    subject: Location
    previous_transition_id: str | None
    artifact: ArtifactRef
    adoption_mode: Literal["pinned", "bounded_adaptive"]
    actor_ref: str                     # authenticated administrator or closed system actor
    recorded_when: EvidenceInstant
```

Layer 3 keeps one ordered, durable transition chain for each exact staged
`(learning_instance_id, serving_generation_fingerprint, signal_type, contract_id,
subject)` consumer. Initial `live_signal_eligible` promotion requires the
type's shadow/quality gates and atomically selects an exact artifact and
administrator-selected mode; it cannot infer the latest artifact. A later
`pinned` revision requires an authenticated administrator's exact-artifact
decision through the Layer-3 administrative transition path, with
current-head precondition and idempotent operation identity. The
`adopt_pinned_signal_artifact` request names the same exact consumer,
expected current head, selected immutable `ArtifactRef`, authenticated
actor and stable operation id; it cannot alter the mode or consumer contract.
A `bounded_adaptive` revision may append under the closed system actor only
after the registered signal predicate proves unchanged value vocabulary,
semantics, sole consumer, source/scope, expiry authority, and approved
parameter/envelope bounds. Both paths recheck validation, shadow and
staleness at commit, serialize against the current head, and reveal either
the old or new complete transition after a crash. A definition or contract
change starts a new consumer chain and requires ordinary shadow/promotion;
an edit limited to `serving_semantics` also starts a new chain but may reuse
the still-valid analysis artifact after current serving and approval checks.
Neither path inherits adoption or creates a `ReactionProposal`.

`set_signal_artifact_adoption_mode` names the exact learning instance,
serving-generation fingerprint, signal type, contract, subject, current
adoption head and requested mode, with authenticated actor and stable
operation id. It changes only the mode for that registered consumer. A
`mode_change` transition keeps the same artifact and serving-generation
fingerprint. Entering `bounded_adaptive` requires an authenticated
administrator, a currently eligible artifact, and explicit revalidation of
the current generation's approved compatibility bounds; only later
compatible revisions can advance under the system actor. Returning to
`pinned` fixes the current revision, including when that artifact is
temporarily unavailable, and blocks future automatic adoption. A stale
head, absent adoption, unknown bounds or unsupported mode rejects without
mutation. The command carries an idempotent `operation_id`; concurrent
mode changes and artifact advances serialize on the same head. It neither
reruns training nor extends an emitted signal's expiry.

At emission Layer 3 must match the exact adopted `ArtifactRef` and also pass
the current artifact, context, freshness and contract gates in §6.3. A
withdrawn, stale, disabled or otherwise ineligible adopted artifact emits
no signal; Layer 3 does not silently return to an older revision or serve a
newer unadopted one. Already emitted signals retain only their original
bounded expiry and Layer-4 validation; an adoption transition cannot extend
one. The transition itself is permission history, not an `InferenceSignal`,
`HouseFact`, or notification.

| Egress | `pinned` revision | `bounded_adaptive` revision |
| --- | --- | --- |
| `DiagnosticFinding` | Mode does not apply; validate and publish the current bounded finding. | Mode does not apply; same current-finding path. |
| `InferenceSignal` | Authenticated Layer-3 administrative transition for the exact artifact and registered consumer. | Core-validated compatible Layer-3 transition for that consumer; otherwise no signal from the new revision. |
| Action-bearing Reaction | Revision-specific Layer-5 `ReactionArtifactAdoptionProposal` and `review_proposal`. | Core-validated compatible Layer-5 adoption transition for the same generation and role; otherwise the old serving decision/fallback remains. |

Every operational row still checks the artifact's current eligibility at
use time. Adoption never overrides a stale, withdrawn or incompatible
artifact, and a new semantic definition or consumer contract cannot be
treated as a compatible revision.

For an existing action-bearing Reaction, an eligible first artifact, or an
eligible new revision while the role is in `pinned` mode, yields a
`LearningProposalCandidate` with the closed
`("reaction.artifact_adoption", 1)` kind: exact
Reaction/generation, descriptor-declared artifact role and immutable
`ArtifactRef`. Layer 5 validates that target and persists a
revision-specific `ReactionArtifactAdoptionProposal` (§4.1); its admin review
uses `review_proposal` and can only append the corresponding adoption
transition. The existing semantic configuration proposal remains terminal.
The adoption candidate's deduplication identity includes the artifact
revision, unlike a candidate proposing a new Reaction configuration. This
does not let Layer 3 choose a mode, approve a revision or alter the Reaction.

The common mechanism has different compatibility predicates, not a generalized policy object. For an
`InferenceSignal`, compatibility preserves its registered type, value vocabulary and semantics, sole
authorized consumer, expiry/freshness authority, and source scope; only declared statistical
parameters, confidence, coverage, and fallback thresholds may refine. For an action-bearing policy,
compatibility additionally preserves semantic action kind, Location/opening/Actuator scope, execution
mode, guard profile, and administrator-approved parameter bounds. Any other
change is incompatible: a signal needs a new staged consumer and Layer-3
promotion, while an action-bearing policy needs ordinary Layer-5
configuration review. Thus continuous learning can refine semantic-context and other
signals without silently redefining a state or expanding an action's authority.

### 4.10 Analyzer adapters

An analyzer is family-specific logic that interprets a `PatternLearner` finding in subject-specific terms. For
example, it can compare a current heating rate with a learned thermal baseline, group recurring
lighting observations into a candidate routine, or identify a recurring activity context.

Analyzers may add subject-specific semantics, but must not reimplement generic historical bucketing, support,
warm-up, retention handling, or confidence arithmetic. They consume immutable findings and emit
either diagnostics or a candidate for the proposal path.

## 5. Lifecycle and performance

### 5.1 Evidence-driven refresh scheduling

Every executable learner/model declaration defines a slow-path `inspection_interval` and a
type-validated `min_new_eligible_evidence` gate, expressed in the units meaningful to that type (for
example, eligible anchors, event candidates, or elapsed evidence interval). The interval schedules a
bounded eligibility inspection, not an unconditional rebuild. Its normal recurrence is fixed-delay:
the next inspection is due after the preceding inspection/run finishes, rather than replaying an
elapsed fixed-rate grid. Core-type validation supplies any minimum safe interval and resource budget;
there is no one global learning cadence.

Every learner also declares one positive `training_window`. It is the complete rolling anchor interval
represented by an ordinary rebuild, ending at the training watermark below; it is not an inspection
interval, a cache horizon, or a hint that an implementation may silently shorten. During staging, the
common builder derives and registers the Layer-0 retention requirement separately for each bound
input stream: the anchor interval, the largest causal feature lookback that reads that stream, and a
target horizon only when that stream supplies the outcome. A learner remains warm-up/degraded until
complete derived **retention** coverage exists for every required bound stream;
typed observation gaps within that retained span instead exclude or censor
individual samples under §4.2 and §5.2. This makes a request such as
"thirty days of anchors with a six-hour causal feature" precise without requiring an administrator to
calculate a separate retention value for every input fact. Layer 0 still aggregates the retained
target and hard ceiling per `fact_type`; its coverage result is deliberately stream-scoped, so an
early eviction on another Location with the same type does not falsely degrade this learner.

The inspection calculates a **training watermark**, `eligible_through`: the latest anchor for which
all required features and the declared outcome can be complete. It is bounded by the available source
history, the largest future target horizon, and every declared source-lateness allowance. A targetless
model applies the latter two bounds that are meaningful to its inputs. This prevents samples whose
future outcome has not matured from entering a training span merely because wall-clock time reached a
refresh tick.

An inspection compares `eligible_through` with the published artifact's `evidence_through`. It uses
Layer 0's existing scoped history read only over that incremental interval plus the minimum overlap
required by declared causal feature windows; it does not scan all retained history merely to discover
whether a rebuild is useful. A rebuild is eligible only when the new complete evidence crosses
`min_new_eligible_evidence`, or when a newly activated/changed definition requires its first valid
artifact. Otherwise it records `skipped_no_new_eligible_evidence` and publishes no duplicate
revision.

**Inspection and rebuilding are deliberately different reads.** Once eligible, a rebuild computes its
immutable requested `TrainingSpan` as `(eligible_through - training_window, eligible_through]`. It
contains every candidate anchor in that interval; source reads expand it by the declared causal
lookback and, for an outcome source, the horizon needed to resolve that outcome. The builder records
the effective accepted-anchor range and count after ordinary invalid-sample rejection, then rebuilds
its complete sample set, validation set, tiers, and artifact from that full requested span. The
incremental inspection interval is never passed off as the training dataset. This prevents a scheduled
rebuild from discarding still-relevant support or making a model's meaning depend on the inspection
cadence.

Generic V3 rebuilds are full rolling rebuilds. Incremental fitting is permitted only for a separately
registered core learning type whose artifact/version declares sufficient statistics or update state,
compatibility and merge rules, validation of each update, invalidation, and rollback behavior. No
ordinary learner may call a partial new-evidence slice an incremental update merely because it ran
after a prior artifact.

Every attempted rebuild records an immutable data-span identity: its learner definition fingerprint,
requested `TrainingSpan`, effective accepted-anchor range/count, `eligible_through`, declared
sampling/binding rules, retention coverage, and source-generation fingerprints. The artifact therefore
identifies the data actually sampled, not just the wall-clock time at which a worker happened to
finish. The split between data validation/triggering and the complete training artifact follows
continuous-training practice
([Google Cloud MLOps](https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning)); the explicit data span/version and artifact metadata follow
[TFX spans and versions](https://www.tensorflow.org/tfx/guide/examplegen) and
[TFX ML Metadata](https://www.tensorflow.org/tfx/guide/mlmd).

At most one run for the same learner/model declaration may execute at once. Ordinary scheduled ticks
and data-arrival hints never queue a second run or cancel the first; they coalesce into one recorded
pending refresh reason. Missed periodic ticks are never replayed. After startup or activation of a
new generation, an enabled learner receives one jittered initial inspection, not one run for every
missed interval. A definition change observed while a run is active coalesces into one replacement
inspection after that run finishes; the old run cannot publish (§5.2). These rules adopt the
`max_concurrency` and `no_catchup` discipline used by recurring ML pipelines
([Kubeflow recurring runs](https://www.kubeflow.org/docs/components/pipelines/concepts/run/),
[Kubeflow `no_catchup`](https://github.com/kubeflow/pipelines/blob/master/backend/api/v2beta1/python_http_client/docs/V2beta1RecurringRun.md)).

The runtime also maintains a bounded global analysis queue. Per-learner single-flight is mandatory;
global slots, fair scheduling, and core-owned priority prevent one family from consuming all slow-path
capacity. No user or plugin can raise these limits at runtime. Queue delay, budget rejection,
coalesced requests, skipped inspections, and timeout/failure reasons are diagnostics.

### 5.2 Run lifecycle

1. During startup or candidate reload staging, definitions are validated, each positive
   `training_window` is compiled with its binding lookbacks/target horizons into per-source retention
   requirements, and those requirements are registered with Layer 0. The core registry is already
   frozen.
2. The enabled learner receives its jittered initial inspection or waits for its fixed-delay
   inspection interval. Neither is an engine-cycle timer.
3. The inspection captures the active generation and learner definition fingerprint, calculates its
   training watermark, and requests only its bounded incremental inspection range. A failed read,
   unmet warm-up, or insufficient new eligible evidence produces no rebuild.
4. An eligible rebuild recomputes the complete requested `TrainingSpan` and verifies
   required retention coverage for the whole span and its declared causal lookbacks.
   It reads typed `ObservationCoverage` for each declared anchor, feature and
   outcome interval; the common builder excludes or censors windows intersecting
   an observation gap. The run keeps the full requested span identity and may
   publish only if the remaining eligible samples pass the existing support and
   validation gates. It never shortens the span to hide a gap or counts an
   incomplete window as negative/zero evidence. The sample builder,
   `PatternLearner`, and optional ML training run off the engine hot path. They
   operate only on copied `HouseFact` data and bounded model data.
5. Before publishing, the run verifies that its captured generation and fingerprint still match the
   active definition. A stale run discards its result without delaying reload or replacing an artifact.
6. An ML candidate first completes chronological validation and, when eligible, shadow evaluation;
   it acquires no operational egress path through either state.
7. A valid rebuilt or explicitly promoted model atomically replaces the prior model and exposes
   findings only to the permitted egress paths below.

No analysis run may initiate HA I/O, inspect mutable HA state, write a command, or synchronously
wait for user review. A slow or failed learner must not delay ordinary house evaluation.

### 5.3 Resource governance and future execution backends

Layer 3 protects the house runtime before it optimizes learning throughput. Inference is always a
bounded local read of a preloaded immutable artifact; training and analysis are expendable slow-path
work. This distinction is deliberate: on a domestic installation, a late lighting, HVAC, safety, or
resident interaction response is more harmful than a deferred model refresh.

Each core learning type declares a `ResourceEnvelope` validated before admission: maximum sample
count, feature cardinality, bounded sequence elements, artifact size, declared algorithmic
complexity, wall-clock deadline, declared peak working-set and CPU-cost bounds, and cooperative
checkpoint/cancellation capability. An in-process implementation must additionally expose resumable
work: `step(WorkSliceBudget)` returns either a completed result or a continuation before its monotonic
slice deadline. A type that cannot prove bounded complexity and this cooperative boundary is not
admitted to the in-process V3 runtime. A run whose declared envelope or conservative cost forecast
does not fit the current plan is `rejected_resource_budget`; it is not silently downsampled, changed
into another model, or allowed to compete with the engine. Python cannot offer a portable hard CPU/RSS
kill guarantee, so the contract makes that limitation explicit rather than claiming isolation it does
not provide.

Layer 3 consumes Layer 0's immutable read-only `RuntimeHealthSnapshot` (§9), never a host-wide guess
or a live HA object. It retains an `EngineHealthBaseline` only from an engine-ready interval with no
local learning admitted and all available health signals green. The baseline contains the high-water
Heima RSS and the healthy cycle-latency distribution; it is recalibrated only during a later comparable
no-learning healthy interval, so a learner-induced degradation cannot slowly become the new normal.
`DetectedLearningCapacity` is the resulting diagnostic view of the snapshot, baseline, and their
capabilities. It is an upper bound, never permission to consume the whole machine.

The admin selects one explicit installation profile: `conservative`, `balanced`, or `performance`.
The profile selects core-owned responsiveness coefficients, not fixed slots, CPU values, memory values,
or a bypass around safety gates. For an effective memory limit `M`, effective CPU capacity `C`, healthy
engine RSS baseline `B`, profile reserve coefficient `r`, and measured baseline variation `v`, the
planner derives protected memory headroom `H = r * M + v`, then
`M_learnable = max(0, M - B - H)`. For the same profile's permitted learning CPU share `s`, it derives
`C_learnable = max(0, s * C - C_engine_baseline)`. It also derives the current allowable cycle latency
from the healthy latency percentile and the profile latency multiplier; current latency slack is the
difference between that allowance and the current Layer-0 percentile. These are formulas over current
installation measurements, not constants assigned to a Raspberry, NUC, container, or profile.

For the active profile the core derives a machine-specific `LearningCapacityPlan` with aggregate
memory, CPU-credit, slice-deadline, queue, and admission limits at `lower`, `target`, and `upper`.
`upper` is a hard physical ceiling using declared envelope maxima; `lower` is zero or one only when its
declared envelope fits the protected budget; `target` is the normal fair set whose conservative observed
cost forecasts fit both `M_learnable` and `C_learnable`. Before enough healthy run data exists, a
forecast is the declared envelope; later observations may refine it downward only within that declared
maximum. CPU credit accrues from elapsed monotonic time and actual process CPU time, never raw host CPU
percentages. Each invocation receives `WorkSliceBudget = min(remaining_run_deadline, slice_fraction *
latency_slack)`; non-positive slack admits no next slice. The plan's limits apply in addition to every
type's `ResourceEnvelope`.

A reliable effective memory limit and usable engine-latency measurement are preconditions for local
admission. If either is absent, stale, non-finite, or not enforceable, local in-process learning is
`capacity_unknown` and no job is admitted; external execution remains separately governed below. CPU or
pressure metrics that are absent likewise never permit a scale-up beyond the conservative lower plan.
The core owns coefficients, tolerances, percentile choices, minimum evidence, and stabilization policy;
they are neither administrator, learner, nor plugin settings. This keeps every production allocation
dynamic while retaining a reproducible, testable safety policy.

Plan calibration never runs a stress benchmark during startup. It has four bounded phases:

1. **bootstrap**: obtain a passive Layer-0 snapshot and establish the no-learning healthy baseline;
   derive `lower`/`upper` only when the required capabilities are reliable;
2. **observe**: admit only the `lower` plan and measure real learner duration, retained high-water
   memory, checkpoint behavior, queue delay and effect on engine-cycle latency;
3. **stabilize**: raise by at most one fair admission unit toward `target` only after the core-owned
   count of healthy observations and successful cost samples; on pressure it immediately closes new
   admission and lowers the next boundary, never kills a run already admitted;
4. **periodic rightsizing**: revise `target` slowly from observed cost and unused headroom without
   changing the selected administrative profile. Deferred staleness and queue delay are demand signals:
   with healthy guardrails they may justify a bounded increase, but they never make a pressured host
   eligible for more work.

Health guardrails are cgroup/process memory pressure or OOM-related evidence where available,
high-water memory against dynamically derived protected headroom, Heima cycle-latency degradation from
its frozen healthy baseline, a missed slice/deadline, and timeout/checkpoint failure. Any incident
immediately closes new admission; an admitted continuation is only resumed at its ordinary cooperative
boundary when a later plan permits it. Missing, stale, or unstable metrics block a capacity increase;
they never justify borrowing capacity from the engine. Queue growth, deferment, and staleness are
intentionally excluded from health: they express unsatisfied demand and can influence an increase only
after all health gates are green. Tolerance, asymmetric scale-up/scale-down rate limits, startup
readiness exclusion and a downscale stabilization window prevent plan flapping. This mirrors the
use of lower/target/upper recommendations, historical peaks, variance and OOM events in
[Kubernetes VPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/vertical-pod-autoscale/), and the
tolerance/readiness/stabilization safeguards in
[Kubernetes HPA](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/),
adapted to one local house runtime rather than a cluster.

The admin receives a diagnostic recommendation rather than an automatic profile change. It includes
the detected capacity and active ceiling, per-type recent and high-percentile run cost, queue delay,
timeouts/backoff, resource-pressure deferrals, artifact staleness attributable to capacity, and
observed unused headroom. The recommendation must state its evidence and trade-off, for example
whether the active profile is repeatedly deferring a learner beyond its staleness policy or is
retaining substantial unused capacity without pressure.

Changing the profile is allowed at runtime and does not alter a learner definition, fingerprint,
artifact, or result semantics. It asks the capacity planner to derive a new plan from the same detected
capacity and observed health, then takes effect only at the scheduling boundary. A higher profile admits
pending work gradually under the normal queue rules, while a lower profile prevents new admissions
above its new target. A run already admitted is neither killed abruptly nor reconfigured mid-run; it
completes or stops only at the ordinary cooperative checkpoint/budget boundary. This avoids
resource-policy churn from corrupting otherwise valid slow-path work.

The runtime uses a core-owned bounded global queue with two layers of control:

- **hard bounds**: per-type envelope and installation capacity prevent an inadmissible run from
  starting at all;
- **soft dynamic admission**: when capacity is constrained, the scheduler defers new work and ranks
  eligible learners using only core-owned signals: staleness urgency, sufficient new evidence, drift,
  family impact, declared priority, and observed cost estimates from prior runs. It records
  `deferred_resource_pressure` rather than borrowing capacity from hot-path work.

Measured duration, peak retained working-set estimate, queue delay, timeout, cancellation, and
validation outcome feed those cost estimates. Repeated over-budget or low-benefit attempts receive
backoff and diagnostics. A partial/early-stopped candidate is never published; early stopping is
permitted only for a type that reports contractually valid incremental validation checkpoints. There
is no generic parallel hyperparameter search, concurrent retraining of one declaration, cross-home
model reuse, or policy based on raw host CPU percentages. These exclusions keep resource behavior
predictable on heterogeneous home hardware. The separation of inference from retraining and the use
of measured expected benefit reflect resource-aware continuous learning at the edge
([Ekya](https://arxiv.org/abs/2012.10557)); the restriction of early stopping to models with valid
incremental results follows established ML scheduler practice
([Ray Tune](https://docs.ray.io/en/latest/tune/tutorials/tune-stopping.html)).

V3 initially executes admitted learning locally. It nevertheless defines an execution boundary so a
future core-approved backend can run a job in a local subprocess or on an external server without
changing learner semantics. The local coordinator constructs a bounded, immutable
`LearningExecutionRequest` containing core type/version, definition fingerprint, data-span identity,
redacted/canonical sampled data, resource envelope, deadline, and expected result schema. The backend
returns only a candidate artifact and diagnostics. It never receives HA credentials, direct HA or
fact-store access, permission to inspect live state, or publication authority.

An external job does not consume local worker slots or its remote CPU/RAM envelope, but it is not free
to the house runtime. `LearningCapacityPlan` separately bounds coordinator concurrency, request/result
bytes, serialization work, local data-read budget, deadline and retry/backoff. External dispatch is an
explicit backend choice staged for that learner type; local pressure does not silently fail over a job
to another server, and backend availability never raises local admission capacity. This preserves a
predictable local hot path while leaving process/server isolation available as a future extension.

The local coordinator remains the sole owner of admission, artifact validation, baseline/shadow
evaluation, promotion, persistence, and live inference. An external result is treated exactly as an
untrusted candidate until it passes the same local schema, fingerprint, budget, validation, and
generation checks as a local result. External execution is explicit opt-in and must use an
authenticated, encrypted transport and a core-approved backend capability when implemented. It does
not imply cross-home data sharing, federated learning, or a remote live-inference path. This keeps
the future extension able to obtain stronger process/server resource isolation while preserving the
privacy, authority, and latency boundaries of the local house.

The same boundary may later support external **slow-path scoring**: the coordinator sends a bounded,
redacted request and the backend returns only a finding or `LearningProposalCandidate` for local
validation. This is suitable for costly thermal/topology analysis or optimization because delay or
unavailability merely means that no new diagnostic/proposal is produced.

Remote live inference is explicitly out of scope for the initial V3 runtime. The initial bounded
`InferenceSignal` type (`indirect.semantic_assist.v1`, under its frozen contracts) remains local,
preloaded, and I/O-free. A future core-approved remote **advisory** inference capability would
still be prohibited from the engine evaluation path: the local coordinator would construct a bounded
canonical feature vector with request/schema/artifact identity, input fingerprint, expiry, and
correlation ID; it would validate the matching response locally; and a late, unavailable, expired,
or incompatible response would become absence of signal. It could feed only diagnostics or a proposal
candidate until a separately reviewed architecture decision authorizes any additional bounded use.
The remote service would never gain HA/fact-store access, a command path, or permission to extend the
live-signal exception list.

## 6. Consumption paths and governance

### 6.1 Bounded live signal

Live use of a learned result is an exception, not a default. The only sanctioned family is
`IndirectSemanticAssistModel-v1` under one frozen `IndirectAssistanceContract`. The initial contracts
are `occupancy.room_present.indirect.v1` (positive room-presence evidence only, never vacancy) and
`activity.sleeping.indirect.v1` and `activity.relax.indirect.v1` (positive,
resident-approved room-context assistance only), and `activity.working.indirect.v1` (positive,
resident-approved domestic-working assistance only). Their exact Layer-4 input contracts are specified
with those semantic resolvers; a learner instance cannot self-authorize a new consumer, assertion, or
policy posture.

Every other finding is diagnostic-only until a proposal is reviewed. In particular, heating and
lighting learning, including environmental-exchange and solar-shading models, do not directly alter
  current semantic resolution.

#### 6.1.1 `DiagnosticFinding`

`DiagnosticFinding` is the single core-owned, administrator-only egress for a bounded non-operational
learning diagnostic. It is neither a `ResultPayload` nor a Layer-1 fact, `InferenceSignal`,
`LearningProposalCandidate`, notification command, or action-policy path.

```python
@dataclass(frozen=True)
class DiagnosticFinding:
    finding_schema_id: str           # frozen core registry identity
    finding_schema_version: int
    finding_key: str                 # canonical stable deduplication identity
    subject: Location
    artifact: ArtifactRef
    result_schema_id: str
    result_schema_version: int
    sample_binding_id: str
    sample_binding_version: int
    evidence_span: TimeRange
    definition_fingerprint: str
    payload: CanonicalJsonObject     # validated by the registered finding schema
```

The frozen core `DiagnosticFindingRegistry` owns every schema/version, payload validator, canonical
finding-key derivation, and eligibility/review gate. A payload has only the typed, bounded semantic
fields of its registered schema and never raw HA state/entity/payload, resident identity, command,
target, executable value, notification text, policy authority, or review disposition. Initial schemas
include `correction_burden.v1`, `context_regime_novel.v1`, and `environmental_residual.v1`.
The two initial shadow-preview schemas are listed in §6.1.2.
A compatible retraining refreshes evidence for the same `finding_key`;
a changed schema or definition fingerprint creates a new finding. The administrative diagnostics
surface may render, filter, acknowledge, or dismiss a finding, but those actions are not training
labels and do not alter a configured Reaction. Diagnostic findings never notify residents directly.
Their validation, current-set publication and withdrawal do not wait for an
artifact-adoption decision (§4.9); a concurrent operational signal or policy
from the same model retains its own separate adoption gate.

Each registered schema additionally fixes a positive `max_active_findings_per_subject`, its own
core-defined eligibility/review gate, and a deterministic `selection_key` over only validated payload
and evidence fields. At each refresh, Layer 3 merges compatible records by `finding_key`, retains only
the eligible findings for one `(schema, subject)`, orders them by that schema's `selection_key` and
then `finding_key` as the final tie-break, and exposes at most the declared bound. There is no global
priority or severity comparison across schemas. A valid finding excluded only by this bound remains in
the artifact/diagnostic counters but is not exposed as active; the registry records its
`suppressed_by_capacity` count by schema and subject. This bounds memory and the administrative view
without recasting a diagnostic as a notification, silently discarding its evidence, or letting UI
acknowledgement/dismissal change learning selection.

The active set is a current projection, not an append-only alert log. Each complete successful
publication atomically supplies the full eligible finding snapshot for its
`(finding_schema_id, subject, definition_fingerprint)` partition. A compatible next publication
updates a retained `finding_key` with its new evidence and withdraws a previously active key that is
absent or no longer eligible from that partition; it never leaves an old conclusion active merely
because the new evidence did not repeat it. The withdrawn record and its reason remain in bounded
administrative audit/history, but no longer consume active-finding capacity or appear as a current
diagnostic.

While a compatible artifact is `refresh_degraded` but remains within its learner-specific
`max_artifact_staleness`, its projected findings may remain active only with the same explicit
degraded state and `evidence_through` already required for the artifact. When that window expires,
the learner is disabled, or the artifact becomes incompatible, every finding projected solely from it
is withdrawn from the active set. A definition-fingerprint change instead supersedes its entire prior
partition immediately: its findings are historic evidence for the old meaning, never current
diagnostics while the new generation warms up or rebuilds. Capacity selection is reapplied only to the
atomically published current snapshot, so a finding suppressed by capacity can become active on a
later compatible refresh without retaining any hidden UI or acknowledgement state.

The administrative surface may separately record `acknowledged` or `dismissed` view/audit state for a
stable finding identity, including historic records. Such state can alter only that administrator's
presentation or filtering; it cannot retain, withdraw, revive, rank, select, train from, or otherwise
change the Layer-3 active projection. The registry emits bounded administrator-audit lifecycle reasons
(`activated`, `refreshed`, `withdrawn_not_eligible`, `withdrawn_artifact_unavailable`,
`superseded_definition`, and `suppressed_by_capacity`); these are neither user-facing notifications nor
learning inputs.

#### 6.1.2 `ShadowProposalPreview`

`ShadowProposalPreview` is not a new cross-layer object. It is the named presentation of a
`DiagnosticFinding` with one explicitly registered `ShadowPreviewBinding`; it is never named or
resolved dynamically at runtime. The frozen core binding is:

```python
@dataclass(frozen=True)
class ShadowPreviewBinding:
    producer_type_id: str
    producer_type_version: int
    candidate_kind: str                 # e.g. "reaction.descriptor"
    candidate_kind_version: int         # core proposal-facet semantic contract
    preview_finding_schema_id: str
    preview_finding_schema_version: int
```

The initial frozen registry contains the following concrete bindings. The named preview schemas are
also initial `DiagnosticFindingRegistry` schemas, each with its own positive core-owned active-finding
bound, eligibility gate and selection key under §6.1.1.

| Producer `kind_id` | Producer version | Candidate kind | Candidate version | Preview finding schema |
| --- | ---: | --- | ---: | --- |
| `environmental_episode` | `1` | `reaction.descriptor` | `1` | `shadow_proposal_preview.reaction_descriptor.environmental.v1` |
| `actuation_routine_pattern` | `1` | `reaction.descriptor` | `1` | `shadow_proposal_preview.reaction_descriptor.routine.v1` |

For `environmental_episode`, every initial active `relation_profile` uses the one environmental
binding above. Its relation profile, Reaction-descriptor id/version, subject, objective, canonical bundle,
parameters, required guards and `CanonicalEnvelope` remain validated candidate payload fields; none
can choose a different preview schema. `actuation_routine_pattern` uses its binding whenever the
administrator enables its optional shadow phase. Both preview finding keys derive from that same
candidate semantic identity plus the learning definition fingerprint, so compatible retraining
refreshes the preview while a semantic candidate or definition change creates a new one.

Only the exact reviewed proposal-producing type/version in this binding, while in `shadow`, may emit
its preview finding. During staging, Layer 3 obtains the candidate kind/version and its semantic
validator from the read-only Layer-5 proposal facet, and verifies that the referenced finding schema
is frozen in `DiagnosticFindingRegistry`. The preview schema reuses that exact candidate-kind semantic
validator for bounded hypothetical intent, scope, parameters, envelope and evidence summary; it adds
only shadow-specific bounded fields such as evaluation time, predicted outcome/uncertainty,
coverage/abstention state, and guard-availability summary. It contains no raw HA data, Actuator
endpoint/command, final Reaction, review status, approval, user text, or executable predicate.
The complete binding is part of the resolved learning definition fingerprint.

The preview finding uses the ordinary per-schema/subject capacity bound, current-snapshot replacement,
staleness, supersession, audit and administrator-only rendering rules of §6.1.1. It is never fed into
training and may not be used as a shortcut around Layer 5. An explicit promotion of the linked
artifact to `proposal_eligible` may cause Layer 3 to construct a **new**
`LearningProposalCandidate` only after rechecking the preview's fingerprint, evidence span, expiry and
candidate-kind schema. Layer 5 then validates that new candidate independently. A preview that is
stale, withdrawn, suppressed by capacity, based on a non-promoted artifact, or merely acknowledged/
dismissed has no conversion path.

### 6.2 Reviewable proposal

The ordinary operational path is:

`PatternLearner or ML finding -> family analyzer -> LearningProposalCandidate -> Layer-5 validation -> ReactionProposal -> admin review -> configured Reaction`

An environmental learner is therefore a **policy learner**, never an instantaneous command source.
It may propose a bounded semantic Reaction-descriptor configuration: physical scope, action intent, typed parameters,
guard requirements, and validity for ventilation or solar shading; it cannot say "open this HA entity
now", supply arbitrary live conditions, or evaluate that policy against current state itself. Once an
administrator has approved the resulting configured Reaction, Layer 5 evaluates its declared trigger
and conditions from the current-cycle snapshot supplied after Layer 4's DAG, together with Layer-0
windows. Layer 5 retains authority over proposal validation and actuation; Layer 6 retains notification
delivery. An approved policy may intentionally be notification-only before any separately approved
automatic action is enabled.

`ReactionDescriptor` is the sole generic action-bearing representation of a relationship between
events. A descriptor may expose `admin_direct` for an authenticated typed event-condition-action (ECA)
configuration, or `learner_proposal` for the separate Layer-3 candidate -> review path; both compile
and execute through the same Layer-5 contract. A Layer-4 `SemanticResolver` may publish a derived state
or occurrence that a Reaction consumes, and a calendar or timing entry may be its trigger. Layer 3 may
submit only a candidate for a compatible `learner_proposal` descriptor. This lets a human-authored rule
remain concise when its intended behavior is already known, while preventing a learned artifact from
introducing an arbitrary predicate language or command path. It follows the established ECA
separation of trigger, condition and action in [Home Assistant](https://www.home-assistant.io/docs/automation/basics/)
and [openHAB](https://www.openhab.org/docs/concepts/rules), without importing either platform's
unbounded scripting surface into Heima.

### 6.3 Typed egress contracts

`InferenceSignal` is a transient, typed Layer-3-to-Layer-4 input, never a persistence format or a
generic event bus. Its core-owned signal type declares the value shape; each frozen
`IndirectAssistanceContract` identifies exactly one target resolver kind, claim-parameter tuple and
set of legal scope kinds. Several contracts may share one signal type without sharing authority.
Every instance carries its subject `Location`, learner/model and artifact identity,
definition fingerprint, selected tier or model context where applicable, confidence/uncertainty,
`evidence_through`, and an explicit expiry. It carries neither raw history/HA payload nor command
intent. It is emitted only when its exact artifact is the current adopted
revision for that registered signal consumer under §4.9, active, compatible,
within its staleness limit, and
its current bounded inputs pass the type's freshness rules; otherwise it is absent rather than
fabricated as a low-quality signal.

**Emission timing and expiry wakeup.** Signal emission is a synchronous step of the engine cycle:
it runs after Layer 0 closes the `CycleInputBarrier` with the cycle's Layer-2 facts and before
Layer 4 builds its `SemanticInputSnapshot`. The emitter reads only the adopted artifact and its
declared bounded inputs from that frozen intake and the sealed previous-cycle values; it never
reads a Layer-4 output of the same cycle, which preserves the no-feedback rule below. Its
`emitted_at` is the cycle instant (Layer 0 §3.5). A signal belongs to its emitting cycle only:
it is never carried into a later snapshot, and every cycle re-emits or omits it from fresh inputs.
For each emitted signal, Layer 3 arms one ordinary Layer-0 `AtJob` with `basis="elapsed"`, owner
`learning_signal`, job id derived from `(contract_id, subject)`, and `due=expires_at`. A newer
emission replaces it; a cycle in which that `(contract_id, subject)` emits nothing cancels it, and
a removed, deactivated or invalidated contract or artifact cancels it at its generation swap. At
due, the job requests a fresh evaluation cycle; that cycle re-emits only if the artifact and
inputs still qualify, otherwise the signal is absent and the assisted conclusion is retracted by
the consuming resolver. An assisted conclusion therefore never outlives its signal by more than
ordinary cycle latency, without depending on unrelated external activity. Startup does not
replay a missed expiry callback: no signal survives a restart, and the first cycle emits only
from fresh inputs.

#### `indirect.semantic_assist.v1`

`IndirectSemanticAssistModel-v1` is the sole producer of this one initial core signal type. Its closed
payload is:

```python
@dataclass(frozen=True)
class IndirectSemanticAssistSignal:
    signal_type: Literal["indirect.semantic_assist.v1"]
    contract_id: str                  # one frozen IndirectAssistanceContract id/version
    subject: Location                 # exact contract-compatible scope
    assertion: SemanticValueId        # exactly the contract's positive_assertion
    confidence: float                 # finite [0, 1], interpreted only with confidence_kind
    confidence_kind: IndirectConfidenceKind
    validation_summary: IndirectValidationSummary
    emitted_at: EvidenceInstant
    expires_at: EvidenceInstant
    artifact: ArtifactRef
    definition_fingerprint: str
    tier_id: str
    context_key: ContextBucketKey
```

`validation_summary` has the exact core schema for the contract's reference mode. A
`calibrated_probability` contract includes its slice-appropriate PPV/calibration evidence; a
`routine_affinity` contract includes recurrence, coverage, contradiction, shadow, and drift evidence,
not a fabricated accuracy metric. The signal has no negative assertion, raw proxy/reference input,
resident identity, HA target, command, or policy field. `emitted_at` is its cycle instant and `emitted_at < expires_at`; `expires_at` is no
later than the contract maximum TTL, artifact staleness boundary, or a required input's freshness
deadline.

Layer 4 routes it only when `(contract_id, subject, assertion, confidence_kind)` resolves through the
frozen contract to exactly one staged resolver kind, claim-parameter tuple, and scope. It rejects an
unknown/inactive contract, another producer or consumer, mismatched assertion, payload extension, or
longer TTL. The resolver may inspect the declared confidence, kind, validation summary, and artifact
identity but cannot extend expiry or feed its assisted output back into the contract's reference.

### 6.3.1 Observable automation abstention

An absent `InferenceSignal` or an action suppressed by an approved environmental envelope must not
silently look like a broken user-visible automation. The component that actually evaluates the
failed gate is the **suppression owner**: Layer 3 for a signal it declines to emit, or the later
semantic-resolver/Reaction owner for a configured action it declines to run. It emits one transient typed
`AvailabilitySuppressionOccurrence`; this is not a `HeimaEvent`, `HouseFact`, notification command,
or persistence request. Layer 6 alone owns rendering, delivery and the durable
`automation.availability` audit-event mapping defined by Layer 1 §3.1.

```python
AutomationSuppressionReason = Literal[
    "outside_operating_envelope",
    "artifact_stale",
    "missing_required_input",
    "stale_required_input",
    "artifact_incompatible",
    "manual_hold_active",
    "command_ownership_unavailable",
    "actuator_capability_unavailable",
    "actuator_state_unconfirmed",
    "active_channel_unmanaged_after_restart",
    "cooldown_active",
    "action_guard_active",
]

AutomationAvailabilityTransition = Literal["abstaining", "reason_changed", "restored"]

@dataclass(frozen=True)
class AvailabilitySuppressionOccurrence:
    suppression_scope_id: str      # staged core semantic output/policy identity; never an HA id
    suppression_owner_id: str      # registered Layer-3 signal or later SemanticResolver/Reaction owner
    subject: Location
    transition: AutomationAvailabilityTransition
    reasons: tuple[AutomationSuppressionReason, ...]
                                    # non-empty, distinct, ASCII-lexicographic order; current causes, or the
                                    # ended episode's causes on restore
    artifact: ArtifactRef | None                # required for an artifact-derived abstention
    detected_at: EvidenceInstant
```

`reasons` is an unordered logical set represented by one canonical tuple. The frozen core owns the
pure `canonicalize_suppression_reasons()` helper: it rejects an empty input, duplicate code, or code
outside `AutomationSuppressionReason`, then sorts the distinct codes in ascending ASCII lexical order
before constructing the occurrence. All current codes are ASCII lowercase plus `_`, so this is also
their UTF-8 byte and Unicode-code-point order. An owner and the tracker must use this helper; a
manually supplied occurrence with an out-of-order tuple is invalid rather than normalized differently
at each boundary. The helper performs no I/O, registry lookup, dynamic import, or HA access.

The occurrence carries only its closed reason codes and bounded identity/context required for
correlation; it cannot contain an arbitrary error string, an Actuator id, an HA entity id, or a raw
guard result. The first five codes describe unavailable learning evidence or unsupported context. The
remaining codes describe Layer-5 action admission: an active resident hold, absent command ownership,
missing capability, unconfirmed physical state, an active channel without verified
post-restart management authority, dwell/cooldown, or one or more required
safety/security/weather/privacy/quiet-hours guards. Administrative disablement,
missing or revoked descriptor-required household consent, and invalid authorization
do not create an occurrence: the first two are visible Layer-5 authority states,
while invalid authorization rejects staging rather than becoming a runtime
suppression. None is relabeled `action_guard_active`.

An owner includes every applicable closed cause through that helper; it never chooses an arbitrary
"primary" reason and thereby hides another real block. The canonical tuple is the episode identity for
reason-change purposes. A changed tuple ends the prior reason episode and begins the new one; a
restoration carries the tuple of the episode it ends. This keeps a concurrent hold and safety guard
truthful without exposing internal action details to Layer 6.

The occurrence otherwise carries no raw history, HA payload, actuator command, `automation_scope_id`, or
learner-authored user text. Metrics and diagnostics count every evaluated suppression by owner,
scope, subject, artifact, and individual reason. A non-diagnostic registered suppression owner emits it on the
transition from usable to abstaining, on a material reason-set change during the same episode, and on
return to usable. Repeated evaluations with the same canonical reason set increment metrics but do not create
further occurrences.

At staging, Layer 6 owns the composition and atomic publication of one immutable
`AvailabilityPublicationGeneration`, including its `AvailabilityPublicationIndex`. Layer 3, Layer 4,
and Layer 5 contribute only their own immutable staged declarations: a suppression owner declares its
exact semantic owner/scope/subject key, while Layer 5 declares each configured automation's explicit
binding, enabled state, and resident visibility. Layer 4 declares no policy or automation binding and
never queries ConfiguredReaction state. Layer 6 validates the cross-generation references during this
slow composition phase; no Layer-3/Layer-4/Layer-5 runtime callback or policy query is created.

An exact key
`(suppression_owner_id, suppression_scope_id, exact subject)` resolves to a non-empty, canonical tuple
of explicit `AvailabilityPublicationBinding`s, ordered by `automation_scope_id`. Each binding names
one `automation_scope_id` and its `reaction_descriptor_id`, and declares whether that configured
automation is enabled and user-visible. The same key may intentionally fan out to several distinct automations; staging
rejects a duplicate `automation_scope_id` for one key, because it would create indistinguishable
duplicate delivery/audit work. There is no wildcard, live policy query, or Layer-3-to-Layer-5 callback.

Every suppression owner sends every occurrence to Layer 6's core-owned, transient
`AvailabilityEpisodeTracker`, regardless of whether a current binding is user-visible. This is not
a notification or persistence request: it is the only typed input from an owner to the tracker. Thus
"metrics-only" means that Layer 6 produces neither user-facing delivery nor an
`automation.availability` event, not that it loses the current suppression state needed by a later
configuration reconciliation.

The tracker retains only the current episode for each exact suppression key, its canonical reason set,
and the distinct automation bindings to which it actually delivered an availability notification. It
uses the staged index itself; Layer 3, Layer 4 and Layer 5 never query that index at runtime. On an
`abstaining` or `reason_changed` occurrence, each currently enabled user-visible binding that has
not already received that episode is delivered independently. On `restored`, Layer 6 delivers only to
bindings recorded as notified and still active for the episode. It groups delivery by
`(automation_scope_id, subject, reasons)` and, only there, builds the standard
`automation.availability` event, derives its notification key/severity and persists its
Layer-1 audit fact with its delivery record in Layer 0's unified notification outbox (§4.5). Delivery behavior (families, quiet hours, channels) is fixed by Layer 6 (Layer 6 §6–§7); it may
not turn repeated per-cycle diagnostics into user-facing spam or suppress the first
user-visible failed automation without an explicit higher-level policy decision.
For `active_channel_unmanaged_after_restart`, the user text states that the
actuator is observed active, Heima has no usable current proof to manage it,
and Heima will leave it as observed rather than assume responsibility for a
later automatic stop. It assigns no actor to the observed state. A `restored`
event states only that this specific block ended; it never asserts that
Heima switched the actuator off.
For this reason, "return to usable" means a fresh inactive observation or
validated management proof under current authority. A changed initiating
trigger alone cannot end an already published unmanaged-active episode.
At each process start the Layer-6 tracker uses a fresh, non-reused run identity
in this reason's notification key, together with the exact staged suppression
key. Retries within one run retain the same key; a later restart creates a
new key and may warn again even if the channel, Reaction and reason are
unchanged. This run identity is transient Layer-6 delivery metadata, not a
new HouseFact, channel-state write or Layer-5 authority input.

**Publication-generation reconciliation is a slow, serialized Layer-6 operation.** The tracker
serializes occurrence handling and an atomic publication-generation swap, so every occurrence is
processed wholly under either the old or new index. Immediately after a swap it compares each current
episode against the old and new binding tuples:

- an unchanged enabled user-visible binding keeps its delivery sub-episode and receives no
  duplicate notice;
- a newly enabled/user-visible binding receives the current active abstention immediately, even
  when the owner emitted its transition before that binding existed;
- a removed, disabled, or non-visible binding closes only its delivery sub-episode with the bounded
  Layer-6 administrative audit reason `binding_deactivated`; it receives neither a later restoration
  nor a user-facing configuration message;
- a subsequent `restored` reaches only sub-episodes that were actually notified and remain active.

This resolves a changed configuration without requesting a Layer-3/Layer-5 callback or a live policy
query. A binding's enabled state also changes through Layer-5 authority transitions, which are not
configuration mutations (Layer 0 §4.7). Layer 5 pushes each such change to Layer 6 as a typed
`BindingEnablementChange`, and Layer 6 applies it as a revision of the current publication index
with exactly the reconciliation above (Layer 6 §9.2); the tracker still never queries Layer 5. The tracker is an in-memory delivery coordination cache, not a house-state store and not a new
Layer-0 persistence projection: it is bounded by current registered suppression keys and configured
bindings, performs O(1) episode/index access plus finite binding iteration only on a transition or
generation swap, and performs no I/O in an engine evaluation. It is empty after a process restart.
Owners subsequently publish their first observed active suppression as `abstaining`; Layer 6 does not
replay old delivery episodes merely from audit history.
This separates actionable user impact from internal telemetry, consistent with [Google SRE alerting guidance](https://sre.google/resources/practices-and-processes/incident-management-guide/) and named,
queryable occurrence conventions in [OpenTelemetry](https://opentelemetry.io/docs/specs/semconv/general/events/).

Only the core registry can define an `InferenceSignal` type and authorize its consumer. The closed
initial set contains only `indirect.semantic_assist.v1`, routed through one frozen assistance contract:
`occupancy.room_present.indirect.v1`, `activity.sleeping.indirect.v1`, or
`activity.relax.indirect.v1`, or `activity.working.indirect.v1`. A learner/model or plugin cannot
self-authorize another signal type, contract, consumer semantic resolver, assertion, or longer validity
period.

`LearningProposalCandidate` is the ordinary Layer-3 egress. It is an immutable, typed hand-off to
Layer 5 containing its core `candidate_kind` and `candidate_kind_version`, semantic scope,
evidence/finding identity, model/artifact and data-span identity, deduplication fingerprint,
confidence/uncertainty, validity interval, and only the typed semantic parameters permitted by that
exact candidate contract. It cannot contain an `ApplyStep`, a raw HA entity/service target, a final
Reaction configuration, review status, or approval decision.
When a candidate depends on more than its primary artifact, it also carries
the exact immutable `ArtifactRef` of each supplemental source with a closed,
candidate-version-declared `role_id`. The tuple is canonically ordered with
unique roles and maps to Layer 5 `ProposalSupportingArtifact` evidence (§4.1),
not to semantic descriptor parameters or the deduplication fingerprint.
Layer 3 cannot attach an arbitrary model merely by naming a role: Layer 5
checks each supporting artifact against the staged binding and current
validation/shadow state before admission and again before acceptance.
It is transient: if Layer 5 accepts the candidate under its registered
candidate and Reaction contracts, it persists a `ReactionProposal` for a
new configuration or a `ReactionArtifactAdoptionProposal` for one existing
Reaction role; if it rejects it, the candidate remains only a Layer-3
diagnostic reason.

The second closed Initial-V3 candidate payload is:

```python
@dataclass(frozen=True)
class ArtifactAdoptionCandidate:
    reaction_id: str
    configuration_generation_id: str
    role_id: str
    artifact: ArtifactRef
```

It uses outer `candidate_kind="reaction.artifact_adoption"` and
`candidate_kind_version=1`. The generic `LearningProposalCandidate` carries
its exact validation/shadow evidence, confidence, uncertainty, validity
interval and data span. For this kind, its `finding_id` is the stable identity
of the immutable artifact assessment from that evidence, not a published
`DiagnosticFinding`; Layer 5 resolves it against the same `ArtifactRef` and
rejects an assessment for a different revision. The deduplication
fingerprint covers the outer kind/version and exactly the four payload
fields, including the full artifact revision identity. There are no
descriptor parameters or action members, and the candidate cannot make
itself eligible by choosing a role or assessment identity. Layer 5's current
Reaction/role registry and Layer-3 quality/shadow records remain authoritative.

`ContextHypothesisCandidate` is the separate non-action-bearing diagnostic hand-off described in
§4.4.7. It has no V3 instance; its future closed payload is:

```python
@dataclass(frozen=True)
class ContextHypothesisCandidate:
    hypothesis_kind: SemanticValueId  # active only in a future reviewed core vocabulary
    subject: Location                 # exactly the staged casa scope
    confidence: float                 # finite [0, 1]
    uncertainty: CanonicalJsonObject  # future registered hypothesis schema; no Initial-V3 instance
    evidence_span: TimeRange
    operating_envelope: CanonicalEnvelope
    expires_at: EvidenceInstant
    artifact: ArtifactRef
    definition_fingerprint: str
    finding_id: str
```

It is immutable and deduplicated by the staged hypothesis kind, subject, artifact/finding identity,
and evidence span. `expires_at` is bounded by the model's staleness/freshness rules and is never a
state-expiry instruction. A future core hypothesis schema must validate the
bounded `uncertainty` object before this currently non-instantiable candidate
can be published; `CanonicalEnvelope` already supplies its operating-cell
contract. A future authenticated administrative-review contract may persist a
confirmation, rejection, or dismissal with its own actor/time/audit fields; Layer 3 cannot add those
fields, decide a disposition, or generate user-facing text. This distinct path prevents a
non-actionable question from being accidentally admitted through Layer 5's action-policy workflow.

Layer 3 therefore never constructs a `ReactionProposal` or
`ReactionArtifactAdoptionProposal`, sends a notification, decides approval, or
applies a resulting configuration. Except for the operational availability occurrences in §6.3.1,
Layer 6 may notify an administrator (through Layer 5's `ProposalReviewOccurrence`, Layer 5 §6.0) and Layer 8 may present a review surface only after Layer 5 has
created the reviewable proposal. The future administrative-review surface may additionally render a
`ContextHypothesisCandidate`, but its decision reaches a future semantic resolver only through that separate
audited contract; neither path bypasses Layer-5 action review.

### 6.4 ReactionDescriptorCandidate

`ReactionDescriptorCandidate` is the closed payload for the outer
`(candidate_kind="reaction.descriptor", candidate_kind_version=1)` contract supplied by Layer 5's
read-only proposal facet. The generic `LearningProposalCandidate` carries that outer identity together
with its artifact/evidence/data-span identity, confidence, validity interval, and deduplication
fingerprint. The outer version is the JSON integer `1`; `relation_profile.version` in this payload
is the exact registered JSON string `"1"` for an Initial-V3 profile. Layer 5 §3/§3.1 owns both
wire encodings and rejects numeric/string coercion across them. This payload carries only:

```python
@dataclass(frozen=True)
class NumericOutcomeRequirement:
    minimum_practical_delta: float    # finite > 0, in the registered outcome's canonical unit

@dataclass(frozen=True)
class ActuationMemberCandidate:
    delivery: Literal["command", "advice"]  # Layer 5 §3.2 member delivery
    actuator_id: str | None           # one compatible registered endpoint owned by subject; None only
                                      # for an advice member on an opening without an Actuator
    controlled_channel: str | None    # one registered Layer-2 logical channel of that endpoint
    opening_id: str | None            # required, optional, or forbidden for this member
    action_intent: str                # closed ReactionDescriptor-owned semantic intent
    semantic_parameters: CanonicalJsonObject
    numeric_outcome_requirement: NumericOutcomeRequirement | None

@dataclass(frozen=True)
class ReactionDescriptorCandidate:
    reaction_descriptor_id: str
    reaction_descriptor_version: str
    subject: Location                 # exact scope accepted by the selected descriptor
    relation_profile: RelationProfileRef  # exact Layer-5 shared evidence/policy contract
    objective_id: str                 # closed profile-owned objective; never a resident-authored label
    descriptor_parameters: CanonicalJsonObject
                                     # root-level closed schema selected by this descriptor/version
    actuation_bundle: tuple[ActuationMemberCandidate, ...]
                                      # canonical order; non-empty; command or advice members
    required_guard_capabilities: frozenset[ReactionGuardCapabilityRef]
    operating_envelope: CanonicalEnvelope
```

`actuation_bundle` is one Reaction-level, finite, ordered desired state composition, not a raw HA
service sequence and not a second action protocol. Every member ultimately maps to exactly one
Layer-5 `ApplyStep`; its canonical order is the requested execution order. The core-owned
`ReactionDescriptorRegistry` defines the legal member intents, objective/member-intent pairing, member
count bound, duplicate-channel rule, opening/Actuator relation, numeric-outcome requirement applicability
and bounds, parameter schema/bounds, guard requirements, exact registered
profile-output compatibility, and Layer-5 translation for each
`(reaction_descriptor_id, version)`. Initial intents are `increase_shading`, `decrease_shading`,
`open_for_exchange`, `close_to_retain`, `activate_extraction`, `adjust_extraction`,
`stop_extraction` and `follow_comfort_trajectory`. User-facing text belongs to Layer 6's rendering of
the typed Layer-5 occurrences, never to learner-provided text. A bundle is never empty; a member
without an endpoint is legal only as an advice member under Layer 5 §3.2.

A `delivery="advice"` member is legal only for an intent in the descriptor's `advisory_intents`
(Layer 5 §3.2); it may omit `actuator_id`/`controlled_channel` only when it names an `opening_id`
that faces an exterior side, and it never becomes an `ApplyStep`. Its measured response, where
learned, is the same profile evidence as for a commanded member.

Only a member whose registered profile measures a numeric response to that
member carries `NumericOutcomeRequirement`. Initial environmental-response
members require it; its positive threshold is stable serving semantics and is
checked in the profile outcome's canonical unit. Comfort-trajectory and routine
members require `None`: a setpoint-step bucket is an action bound, not a
minimum measured outcome, and routine frequency describes the whole bundle.
A descriptor/profile pair that requires a numeric outcome rejects `None`;
one that has no per-member numeric outcome rejects a fabricated requirement.

Measured effects are refreshable evidence in the exact typed primary artifact
referenced by `LearningProposalCandidate` and `ProposalEvidenceRevision`, not
immutable member fields. Environmental response uses its registered
numeric-interval output; comfort recovery uses the exact
`ThermalResponseParameter` and its duration bounds; the routine profile
must use the registered `routine.bundle_frequency.v1` whole-bundle/context
output with conditional and baseline probabilities. The exact profile
schema and validator check that output against the candidate and its
review evidence, never a learner-selected member payload.
The routine's separate support, calibration and lift gates remain required
before proposal eligibility.

`descriptor_parameters` and each member's `semantic_parameters` first pass §4.2's
`validate_canonical_json_object`; the registered descriptor then validates each resulting immutable
object against its closed root or member-intent schema and bounds. The registry separately validates
the closed `objective_id`, each permitted member intent, and the presence or absence
of each `numeric_outcome_requirement`; where required, it validates the finite
positive `minimum_practical_delta` in the relation profile's outcome unit. A
bundle may not repeat the same `(actuator_id, controlled_channel)`: distinct channels of one physical
endpoint remain legal, but contradictory commands to one channel are not. Neither path admits a raw
Home Assistant value, executable object, or an untyped extension field.

Every registered descriptor declares a root-parameter schema. A descriptor with no root-level
parameters requires the canonical empty object; it cannot treat a missing field or arbitrary object as
equivalent.
Where a descriptor version permits learned timing, its closed root schema may
carry the canonical data projection of the stable `ReactionTimingModelBinding`
that Layer 5 §4.2 validates.
That binding names the learning definition, sample/result contracts, exact
typed state, qualifying values and authorized window; the condition state
and qualifying values must exactly match the
`FutureStateFractionOutcome` source and set. It never contains an `ArtifactRef`, analysis
revision, predicted `q`, admin approval or live timer. A candidate that needs
a supplemental timing artifact must identify its exact supporting revision
in typed evidence separate from the semantic payload before Layer 5 can
approve it. Layer 5 §4.1 owns that multi-artifact evidence shape, and
§4.2 owns its adoption transition and later-revision path;
an untyped field in `descriptor_parameters` or a redacted snapshot cannot
stand in for it.

The candidate concerns exactly one descriptor-defined scope. The initial environmental and routine
descriptors remain room-scoped, while `environment.planned_comfort_trajectory` accepts only the staged
`ConditioningScope.location` (`room` or `casa`). A member that acts on an opening requires a
Layer-1 Opening for which `opening_faces_exterior` holds (Layer 1 §7), owned by a room subject and an endpoint whose `opening_id` matches it (an advice member may name
only the opening, Layer 5 §3.2). A member that
acts on a room device, such as an extraction fan or light, forbids `opening_id` and requires endpoint
ownership that matches its room subject. The HVAC trajectory member instead requires the one endpoint
declared by its compatible `HvacTrajectoryBinding`; it has no `opening_id` and cannot derive an endpoint
from the scope. It cannot smuggle a raw service, entity selector, nested policy call, unbounded member
list, or arbitrary action graph through `descriptor_parameters` or `semantic_parameters`. Layer 3 validates only the
descriptor/profile and closed payload shape available through its read-only proposal facet. Layer 5
staging alone verifies every bound opening/topology and Actuator relation before creating a reviewable
proposal or activating a configured Reaction.

Its deduplication fingerprint is the canonical combination of Reaction-descriptor id/version, subject,
relation profile, objective id, descriptor parameters, canonical ordered member identities/channels/opening relations/intents,
applicable numeric-outcome requirements, semantic parameters, required guards, and
the operating envelope's `envelope_semantic_projection` (§6.5).
It deliberately excludes measured artifact effects, artifact version, evidence identity,
confidence, and data span: compatible
retraining refreshes evidence for the same review item rather than creating duplicate proposals. Any
change to the included semantic configuration creates a new candidate and requires the ordinary
review/adoption rules.

#### 6.4.1 `environment.planned_comfort_trajectory` candidate translation

Layer 3 translates one eligible exact-cell `ThermalResponseParameter` into exactly one candidate for
one `(conditioning_scope_id, mode)`. It may do so only against the exact staged
`ComfortTrajectoryPrerequisiteGeneration` with the same scope and a declared endpoint for that mode.
The candidate's `subject` is that generation's `ConditioningScope.location`; its profile is exactly
`hvac_thermal_response@1`; its closed objective is `planned_comfort_reachability`; and it has exactly
one `ActuationMemberCandidate` with the bound endpoint, no `opening_id`, and intent
`follow_comfort_trajectory`.

Its root `descriptor_parameters` are exactly:

```json
{
  "prerequisite_generation_id": "<immutable generation id>",
  "prerequisite_definition_fingerprint": "<canonical generation fingerprint>"
}
```

Its member `semantic_parameters` are exactly `{ "mode": "heating" }` or
`{ "mode": "cooling" }`, and its `numeric_outcome_requirement` is `None`.
The selected parameter's `recovery_setpoint_step_min_c` is an artifact-backed
action bound; its recovery-duration fields are artifact-backed reachability
evidence for the exact context, thermal-delta and setpoint-step buckets.
Neither is copied into immutable candidate member semantics. The candidate's
required guards are the exact descriptor-required guards plus the generation's required guard
capabilities, in canonical order; it cannot add, omit, weaken, or rename one. Its
`CanonicalEnvelope` is the parameter's supported exact context cell and declared bucket bounds, never
a calendar interval, a target temperature, or a command schedule.

The generic `LearningProposalCandidate` and its resulting `ProposalEvidenceRevision` retain the
selected parameter's `artifact_ref`, evidence references, validity interval, confidence and uncertainty;
the revision's bounded redacted snapshot additionally records its canonical parameter fingerprint and
scope/mode/cell/bucket identities. These are evidence, not descriptor configuration. Layer 5 requires
them to match the candidate's scope, mode, profile and envelope at admission and review. A new artifact
may refresh one pending proposal only when those semantic fields, including the prerequisite generation
pair, mode, step bucket and envelope, are unchanged; otherwise Layer 3 constructs a new candidate for
ordinary review. No translation may copy a bound, return target, calendar plan, actuator mapping,
adapter constraint, consent state, absolute setpoint, arrival prediction, or `ApplyStep` into the
candidate.

### 6.5 CanonicalEnvelope

`CanonicalEnvelope` is a finite, joint coverage contract, not a collection of independent feature
ranges. Independent ranges could admit an unobserved combination simply because each individual value
was seen elsewhere. The already-selected core-owned Reaction descriptor declares a bounded ordered set of admissible axes and
their versioned partitions; the learner may publish only supported, calibrated cells over those axes.
For an `admin_direct` generation with no relation profile, the descriptor's
versioned validator and compiler select only its exact
`permitted_direct_envelope` axes and permitted joint cells, which may be a
zero-axis subset of the descriptor's wider permitted axes used by a learned
profile. This is the same envelope type and exact-cell runtime lookup;
no Layer-3 artifact or statistical support is implied by direct authoring.

```python
@dataclass(frozen=True)
class EnvelopeAxis:
    slot_id: str
    partition_id: str
    value_kind: Literal["numeric", "categorical"]

@dataclass(frozen=True)
class CoverageCell:
    axis_values: tuple[BucketValue, ...]  # canonical axis order
    support: int | None
    calibrated: bool | None

@dataclass(frozen=True)
class CanonicalEnvelope:
    axes: tuple[EnvelopeAxis, ...]
    supported_cells: frozenset[CoverageCell]
```

`supported_cells` contains at most one cell per exact canonical `axis_values`
tuple, with length and value kinds matching `axes`; every included cell is
admitted by the selected descriptor/profile contract. For a
`learner_proposal` cell, `support` is a positive measured count and
`calibrated=True` is required; unsupported or uncalibrated cells remain
artifact/review evidence outside the policy envelope. For an `admin_direct`
cell, both fields are exactly `None`: admission comes from the immutable
descriptor version and validated administrator configuration, never from
fabricated samples or calibration. A mixed pair is invalid for either origin.
An `admin_direct` envelope with no context axes has exactly one cell with
`axis_values=()`, `support=None`, `calibrated=None`; the empty joint key
matches every valid current context but does not override temporal,
calendar, guard, authority or action-admission checks. The pure
`envelope_semantic_projection` is the canonical ordered `axes` tuple plus
the set of included `axis_values` tuples ordered by their RFC-8785 JSON
UTF-8 bytes, not by Python value comparison. It excludes `support` and
`calibrated` and is the only envelope component used in candidate semantic
deduplication and approved-envelope subset checks. A changed axis/partition
or added/removed cell key changes that projection; a compatible support
refresh for the same cells does not. The runtime plan builds an immutable
index keyed by `axis_values`, so lookup uses the current cell key rather than
constructing a `CoverageCell` with unknown evidence fields.

At Reaction evaluation, Layer 5 discretizes the small declared set of current facts and resolved semantic
outputs from its immutable `DecisionSnapshot`, then checks the exact joint cell: O(d) to construct its
key for d bounded axes, then O(1) membership. It never searches for a nearest value or substitutes a
partial cell. A missing, stale, invalid, unpartitionable, or unsupported input makes the policy abstain
with its diagnostic reason. The descriptor and resource envelope bound both axes and cell count,
preventing a combinatorial coverage table. Layer 4 may provide a typed current semantic claim as one
declared axis input, but it neither reads a Reaction descriptor nor evaluates its envelope.
Each descriptor-version axis names a typed current slot and an exact
core-owned versioned partition whose pure mapping is total for valid values
and has a finite bucket vocabulary. Staging resolves the slot, input
type/unit, partition version, canonical axis order, cell keys and finite
axis/cell limits; an administrator may select only a subset of
descriptor-permitted direct cells when that version explicitly allows it.
The direct registration's axes are fixed by the descriptor version; an
administrator cannot remove a required direct axis. A direct zero-axis
entry has only the empty-key cell and is legal only when the descriptor's
typed trigger, conditions and guard contract already constrain the action.
The learned path retains its exact supported cells and evidence metadata.
An absent, stale or unpartitionable live input still abstains. Changing an
axis or partition's meaning requires a new descriptor version and ordinary
configuration revalidation; it cannot silently widen a current generation.

`environment.solar_shading` permits incident-solar-exposure band, indoor/outdoor-temperature bands,
and observed-cover-state, with radiation, illuminance, HVAC, and presence only where declared by the
profile. `environment.external_exchange` permits indoor/outdoor-temperature-delta band, observed
opening state, and either CO2 or humidity-ratio delta according to purpose, with HVAC and
outdoor-air-quality only where declared. `environment.air_extraction` permits room humidity-rise,
humidity-rate and humidity-level bands, optionally declared current room occupancy, and observed
fan state; no room-kind or bathroom label is an axis. Its trigger input is typed relative humidity;
its learned outcome is the room humidity-ratio change (§4.8.1).
Every registered descriptor permits
only its version-declared axes. For a `learner_proposal`, the selected
`relation_profile` may further restrict them; its validator rejects every
other axis. An `admin_direct` generation has no relation profile and uses
the descriptor declaration alone.

For `bounded_adaptive` adoption, a later envelope must be a subset of the administrator-approved
envelope by cell keys after canonical partition/version equality is verified.
Support and calibration metadata do not enter the subset relation. Removing cells is compatible;
adding a cell authorizes behavior in a new context and therefore creates an incompatible revision for
ordinary review. This applies independently of an artifact's freshness or confidence.

### 6.6 Reaction-descriptor hand-off

`ReactionDescriptorRegistry`, `ReactionEvaluationPlan`, configured-Reaction persistence, evaluation, action
admissibility and `ReactionProposal` translation are Layer-5 contracts, specified only in
`layer5_action_reactions_spec.md`. Layer 3 receives a read-only proposal facet during its own staging:
it validates that the selected `(reaction_descriptor_id, reaction_descriptor_version)`, `relation_profile`,
objective/member-intent pairing, bounded ordered bundle, applicable member numeric-outcome
requirements, scope, parameter shape, required guards, envelope and exact
profile-registered artifact output are legal for a candidate. It
never compiles a plan, evaluates current state, resolves an actuator, or contains a descriptor callable.

This read-only validation is advisory preflight only: it can prevent Layer 3 from emitting a candidate
that is already incompatible with the generation it observed, but it neither reserves that generation
nor authorizes persistence, review, or action. Layer 3 cannot treat a successful preflight result as a
cached authorization. Layer 5 is the sole authority to validate and persist a `ReactionProposal`, and
it repeats authoritative validation when an administrator accepts it. A descriptor, profile, topology,
Actuator, guard, configuration generation, or canonical fingerprint that changes between those moments
is resolved by Layer 5 under its revalidation rules; Layer 3 never reinterprets a candidate to bridge
the mismatch.

`environment.*`, `lighting.*`, `security.*`, `safety.*`, and future namespaces are descriptors of the one Layer-5
Reaction-descriptor mechanism. They do not select a distinct Layer-3 analyzer, policy engine, persistence
path or action protocol. Layer 3 may estimate only values declared by the descriptor, such as a
threshold, window, bounded duration, envelope or expected effect. A deterministic policy can use the
same descriptor without any learner; Layer 3 is useful only where historical evidence must estimate
those declared values.

The candidate deduplication fingerprint is the canonical combination of Reaction-descriptor id/version,
subject, relation profile, objective id, root `descriptor_parameters`, ordered member
identities/channels/opening relations/intents, applicable `numeric_outcome_requirement` values,
member `semantic_parameters`, required guards and the operating envelope's
`envelope_semantic_projection`. It excludes measured artifact effects, artifact version,
evidence identity, confidence and data span so compatible retraining refreshes evidence for one review
item. An incompatible Reaction-descriptor version is handled by the composed-generation impact rule (Layer 0 §4.7), never
reinterpreted by Layer 3.

## 7. V2-derived learning families

The V2 implementation establishes the following candidate families, all to be re-specified against
the contracts above rather than ported mechanically:

- approved activity-context inference;
- indirect-room occupancy assistance;
- thermal-response calibration and a future bounded comfort-setpoint preference candidate;
- environmental exchange (ventilation/air-quality) and solar-shading assistance when their required
  measurements exist;
- recurring lighting routine and scene discovery, generalized in V3 as bounded actuation-bundle
  routine discovery.

V2 retained a clock bucket while discovering lighting scenes but deliberately discarded a time-only
pattern when it lacked an additional contextual explanation. V3 keeps that conservative initial
boundary: `ActuationRoutinePatternModel-v1` covers only a present typed trigger and immediate bundle.
A future reviewed lighting temporal plan, if justified, uses the generic
`TemporalActuationProfileModel` rather than turning a clock correlation into a second lighting learner
or an implicit schedule.

V2 `presence_preheat` is explicitly not ported. It learned a typical whole-house arrival time from
rare `away -> present` transitions and coupled that estimate to arbitrary HA scene/script execution.
This is structurally inapplicable to homes that are often occupied and cannot determine the correct
conditioning lead time from arrival timing alone. Its V3 successor is the unified evidence-gated
Layer-5 `environment.planned_comfort_trajectory` descriptor described in Layer 5 §7.1: it covers both heating
and cooling and combines a current stabilized-away active planned absence, the descriptor's
`departure`/`return` lifecycle handling, and a validated thermal response rather than preserving a
heating-only arrival heuristic.

V2 `heating_preference` is explicitly not ported as an initial V3 learner. It grouped observed
manual setpoints by house state and emitted a second actuator-commanding reaction, so it both treated
an observed adjustment as a durable comfort preference and competed with the heating policy for the
same endpoint. Physical thermal response remains the separate environmental-response concern above.
If later justified, `ComfortSetpointPreferenceModel` is a proposal-only estimator of a bounded
preference parameter for one explicit `conditioning_scope` and one declared conditioning `mode`
(`heating` or `cooling`); it is never an Actuator command, an `InferenceSignal`, or a selector of an
HA entity. The registered Layer-5 HVAC descriptor owns the explicit per-mode endpoint binding, so the
same model contract supports a heat pump using one endpoint for both modes and an installation with
separate heating and cooling endpoints. It also owns auto-mode deadband and every compatibility or
application check. This prevents Layer 3 from silently assuming that a heating setpoint and a cooling
setpoint have the same actuator, scope, safety limit, or operating semantics.

V2 `heating_eco` is explicitly not ported as a separate V3 learner. It inferred an away-time heating
target from Heima-authored events, fell back to a fixed temperature when those events were absent,
and applied that target through an independent reaction. V3 absorbs its potentially useful physical
question into the `hvac_thermal_response` relation profile as bounded reachability evidence, separately
for heating and cooling. Layer 5 alone combines that evidence with staged administrative bounds; it is
never an autonomous reaction, a learned target, or a fixed fallback target.

V2 `composite_room_assist` is explicitly not ported as a V3 learning family. Its historical catalog
mixed unrelated room concerns: humidity/occupancy ventilation, CO2 ventilation, reactive cooling,
occupancy/lux lighting, and vacancy lighting off. V3 decomposes these without a special engine:

- typed environmental Reaction descriptors express declared humidity level, change or rate,
  CO2, temperature and, where required, occupancy conditions with their applicable
  physical/environmental guards; `environment.air_extraction` is room-neutral and
  does not require occupancy unless its configuration declares it;
- `ActuationRoutinePatternModel-v1` may propose only its registered
  `routine.actuation_bundle` descriptor when it observes a repeated typed
  trigger/context followed by a bounded resident-control `ActuationBundle`;
- lighting uses the existing routine and room-occupancy survival contracts; reactive cooling uses the
  environmental response/policy path; planned anticipatory heating/cooling belongs only to evidence-gated
  `environment.planned_comfort_trajectory`.

Historical recurrence never substitutes for current guards. A ventilation/cooling candidate without a required outdoor-air-quality, weather, opening-security
or other descriptor-declared guard binding cannot stage. If a staged guard lacks usable
current evidence, automatic action abstains under the existing policy contract. A current hold
or unconfirmed physical state is instead checked by Layer 5 as a common admission gate on
every affected Actuator channel; neither is a learner-provided guard capability or profile
binding, even when a similar V2 composite pattern was frequently observed. This keeps source control,
outdoor conditions and safety separate from behavioral regularity.

V2 `security_presence_simulation` is not ported as a V3 learning family. Initial V3 instead registers
the administrator-authored `security.presence_simulation` Layer-5 descriptor: a bounded deterrence aid,
never a security guarantee or substitute for locks, alarms or physical protection. Its core-generated
plan uses staged windows and bounded variation, not learned behavior. Its complete calendar, presence,
endpoint, authority, scheduler, privacy and audit contract is owned by Layer 5. Layer 3 neither
produces a candidate nor validates an operational profile for this initial path.

A future `TemporalActuationProfileModel` may personalize that policy only after its independent
contract is defined in §8. It is a generic core temporal-profile model; security-presence simulation is
only its first proposed constrained consumer. For this consumer, its artifacts and generated plans are
security-sensitive administrator data: they remain local, are never sent to an external learning or
inference backend, and cannot become a notification, a HouseFact, or an action without the reviewed
Layer-5 policy.

V2's snapshot model, its independently evolved inference/analyzer pipelines, ad-hoc confidence
formulas, raw entity-target payloads, and learned V2 state/history are explicitly not part of this
layer's V3 contract.

## 8. Decisions to refine component by component

The components whose complete contracts are already specified above are the only ones that an active
generation may stage, subject to their own enabled-state and profile gates. Appearance in this section
does **not** activate a learner, relation profile, hypothesis kind, egress, or consumer. The following
are future component contracts; each remains rejected by staging until its own item explicitly says
otherwise and every cited cross-layer dependency is complete.

1. Concrete definitions for each future core ML estimator beyond the currently specified
   `PatternLearner`, `EnvironmentalEpisodeLearner` estimators (`StratifiedResponseModel` and
   `EnvironmentalQuantileResponseModel`), `RoomOccupancySurvivalModel`, and
   `CorrectionCountHurdleModel-v1`, `ActuationRoutinePatternModel-v1`, and
   `ContextRegimeNoveltyModel`: model/codec algorithm,
   feature-target schema, family metrics and numeric thresholds, explainability, and any explicit
   incremental-fit contract. The common artifact, validation, shadow, drift, invalidation, promotion,
   and resource-governance framework is fixed by §§4-5.

2. `ContextHypothesisCandidate` producers. This is a future diagnostic-only capability, not a V3
   implementation item. Until a reviewed core version registers one closed `hypothesis_kind`, its
   producer and the corresponding schema, staging rejects every instance. That future producer must
   declare the bounded feature/episode contract, independent reference or unsupervised evaluation
   method, calibration where applicable, false-prompt/coverage gates, `shadow_requirement`, expiry,
   administrator presentation/audit rules, and the exact owning future semantic-resolver input contract. It cannot
   create an `InferenceSignal`, `LearningProposalCandidate`, HouseFact, notification, policy, review
   record, or direct transition. `possible_guest` remains an illustrative future kind only; it cannot
   be introduced without direct declared multi-occupant-count evidence and must not be inferred from
   ordinary binary-presence or routine observations.

3. `environment.planned_comfort_trajectory` is an Initial-V3 evidence-gated Layer-5 descriptor, not
   a Layer-3 learner family. Its complete Layer-5 contract is already defined. It remains dormant for
   an individual conditioning scope until a compatible validated `hvac_thermal_response` artifact
   matches the current context and a compatible immutable staged prerequisite generation exists. Consent
   is instead a gate only for later automatic action; proposal, review and notification-only shadow do
   not require it. Heating and cooling share one descriptor contract while their physical response,
   targets and endpoints remain independent. The calendar end supplies an expected return
   boundary, not an inferred arrival forecast or a label for training data. Layer 3 supplies only the
   reviewed bounded response parameter; it never proposes a second preconditioning policy or issues a
   command.

4. `TemporalActuationProfileModel`, a future generic core proposal-only learner for a bounded ordered
   distribution of future profile members and their relative timing/duration under a declared
   day/season/darkness or other staged temporal context. It is distinct from
   `ActuationRoutinePatternModel-v1`: its target is a future temporal plan, not a current typed
   trigger/context-to-immediate-bundle outcome. It reuses resident-control attribution, typed
   bindings, canonical Actuation members/bundles, tier/warm-up, chronological validation, artifact,
   review, scheduler, and execution contracts, but requires its own temporal-sequence estimator and a
   future registered Layer-5 temporal-plan descriptor. It cannot replace or reinterpret an
   administrator-authored HA `schedule.*` helper; that helper remains the sole authority for an
   administrator-created recurrence. No temporal profile may be activated until its future Layer-5
   descriptor and Layer-0-owned execution/scheduling contract are specified, including plan/event/
   jitter bounds, current guard evaluation, manual-control/hold suppression, no-catch-up behavior,
   privacy classification, and plausibility/operational-safety evaluation.

   `security.presence_simulation` is an Initial-V3 administrator-authored constrained consumer, but
   requires no learned profile: Layer 5 owns its core-generated bounded plan over explicitly selected
   interior-light Actuators. A later personalized artifact and generated plans remain
   security-sensitive local administrator data, require the existing
   declared `household.planned_absence`, observed current absence, consent gates and
   endpoint contract, and never claim measured burglary prevention. A future non-security consumer,
   such as a reviewed lighting temporal-plan descriptor,
   must satisfy the same common temporal model contract but declares its own scope, guards and privacy
   class; it is not implicitly enabled by the security use case.

   This is the approved product direction for presence simulation: Initial V3 ships the
   core-generated, unlearned plan, and the learned `TemporalActuationProfileModel` is the intended
   successor for the episode selector. Even then, the administrator's configured session window
   and selected lights remain the hard bounds; a learned profile can never act outside them.

5. `ComfortSetpointPreferenceModel`, a future proposal-only estimator for an administrator-reviewed
   preference parameter of a future Layer-5 HVAC descriptor. Its subject is exactly one explicit
   `conditioning_scope` and one declared `mode` (`heating` or `cooling`), never an implicit
   whole-house default or a raw HA climate entity. It may use only resident-attributed manual setpoint
   adjustments, stable post-adjustment intervals, and declared contemporaneous physical/environmental
   context; a rapid resident correction is counter-evidence, not another sample to average. The
   descriptor resolves the mode to its explicitly compatible Actuator endpoint or endpoints, which may
   be shared by both modes or be distinct. Layer 3 cannot choose that endpoint, issue its command, or
   enforce an auto-mode deadband. Before implementation this item requires the HVAC descriptor's
   comfort/safety envelope, compatible manual-control attribution, context and validation metrics,
   explicit feedback/override treatment, and shadow/review promotion rules. It must not equate a
   setpoint history with universal or individual thermal comfort.

6. `hvac_thermal_response` thermal reachability. It is an Initial-V3 evidence-gated core relation
   profile within `EnvironmentalEpisodeLearner`, not a new learner family. Its §4.8 contract defines
   complete active-response/passive-drift cohorts and produces only the exact-cell
   `ThermalResponseParameter` consumed by the registered HVAC descriptor as a reachability estimate.
   It becomes eligible only with complete calibrated evidence, exact-context coverage and thermal
   shadow validation; the already-defined Layer-5 prerequisite, comfort/safety, shadow/promotion and
   automatic-action consent gates then govern its operational use. Historical
   `occupancy.departure`/`occupancy.return` episodes may delimit an absence cohort (nobody inside,
   whoever lives there; household `presence` episodes never do, CA4-120) but the live descriptor alone may use the declared `household.planned_absence` end (Layer 2 §2.9)
   to schedule against an expected return; that plan never labels calibration data as absence.
   No fixed default target is permitted. A candidate without an explicit energy measurement binding
   must omit energy-savings claims and energy-benefit promotion metrics.

7. `ResidentPresentationPreferenceModel`, a future generic proposal-only model for non-safety
   notification-delivery parameters. Its input vocabulary and one explicit `presentation_scope` must
be declared by the registered Reaction descriptor; it may consume only explicit resident
   feedback, while non-response is right-censored rather than a negative label. Its output can change
   only an administrator-reviewed delivery parameter of that descriptor. It cannot alter the policy's
   semantic content, physical/environmental estimate, live guard, safety classification, action,
   notification existence, or priority of any safety-critical item. The detailed contract must define
   the closed feedback taxonomy, support/recency gates, privacy treatment, delivery parameters,
   presentation KPI, and review/reversal path.

Each item must be resolved in this spec before it is used as an implementation basis.

Layer 3's typed egress contracts are complete in §6. The downstream candidate validation, workflow
persistence/review transition, policy evaluation and translation into a `ReactionProposal` are defined
only by [Layer 5](layer5_action_reactions_spec.md); they are not unresolved Layer-3 decisions.

## 9. Initial acceptance criteria

- An `environmental_response.v1` cell is eligible only under its profile's frozen
  `EnvironmentalResponseGateCalibration`, at a calibrated horizon and with every support, block,
  replica, width and shadow gate passing; a profile without a calibration publishes diagnostics only.
  A `humidity_extraction` edge `level 2 -> level 1` (downward) or `level 1 -> level 3` (jump) is
  excluded rather than classified; `off -> level 2` is a `start` with level 2 as context (§4.8.1).
- A routine cell is proposal-eligible only with a `RoutineValidationReport` entry for its exact
  bundle and context key whose intervals match the cell, whose `failed_gates` is empty and whose
  counts, precision, lift and no-effect bounds pass the frozen `RoutineEvidenceGateCalibration`; a
  missing entry, too few valid bootstrap replicas or a lift interval touching `no_effect_lift`
  keeps it diagnostic. The bootstrap seed reproduces the report (§4.4.3).
- A trace with unequal state durations yields one time-weighted `mean`, `true_duration`,
  `minimum` and `maximum` under zero-order hold over `[T - window, T]`; an event at `T - window`
  is not counted and one at `T` is. A source unavailable anywhere in the window makes the feature
  missing. Equal-time sequence items order by canonical serialization, and overflow keeps the most
  recent `max_items`. Training and serving give the same value for the same records (§4.2).
- A required feature used only by the rich tier and missing in a sample excludes that sample from
  the rich tier only; the coarse tier still counts it, and serving falls back to the coarse tier
  with a `missing_dimension` trace for the rich one (§4.2, §4.3).
- A signal is emitted within its cycle after the Layer-2 barrier and before Layer 4, with
  `emitted_at` equal to the cycle instant; it is never carried into a later cycle. Each emission
  arms or replaces one `elapsed` expiry `AtJob` per `(contract_id, subject)` at `expires_at`; a cycle
  without emission or a generation swap removing the contract/artifact cancels it. With no other
  input, the job's due cycle re-emits only from still-qualifying inputs, otherwise the assisted
  conclusion is retracted; a restart replays no expiry callback (§6.3).
- A `TimeRange` uses two canonical `EvidenceInstant`s in ascending order;
  equal endpoints represent one observed instant but never prove gap-free
  coverage. A diagnostic or candidate whose evidence span is reversed is
  rejected. An indirect occupancy learner binds the exact same-room
  `occupancy.physical` `FactSlot` and physical producer fingerprint, rejecting
  individual evidence and its own semantic output (§4.4/§4.4.5/§6.1.1).
- A `ReactionDescriptorCandidate` carries a positive
  `NumericOutcomeRequirement` exactly where its descriptor/profile declares
  a per-member numeric outcome; comfort and routine members reject it. The
  primary artifact's typed effect matches the registered numeric, duration
  or whole-bundle routine-frequency output schema and conservative evidence gate.
  A thermal duration uses `Window` bounds; a routine evidence revision reports
  measured probabilities without treating them as lift-validation proof.
  `routine.bundle_frequency.v1` rejects a wrong bundle/context key, invalid
  count or exposure ratio, duplicate bundle/context records, non-finite
  probability or interval, a diagnostic zero/absent
  baseline presented as eligible, and member-level frequency copies. Its
  keyed validation report proves support, calibration, temporal-block
  intervals and holdout gates before proposal eligibility (§4.4.3).
  Compatible evidence refresh changes no candidate semantic fingerprint.
  The future `ContextHypothesisCandidate` remains
  unpublishable until a closed uncertainty schema is registered (§6.4).
- One descriptor that permits both authoring origins can register a
  zero-axis direct `CanonicalEnvelope` and nonempty profile-restricted
  learned axes. The direct cell has `support=None, calibrated=None` and
  cannot satisfy a learned candidate's evidence gate; the learned cells
  cannot be copied into a profile-free direct generation. The direct plan
  still needs its staged typed trigger, conditions and guard contract (§6.5;
  Layer 5 §3.2).
- Solar-dependent environmental learners bind only the two current
  casa-scoped radian facts from Layer 2 §3.6 and the staged per-opening
  incidence output; a stale Sun source, changed observer location or geometry
  proxy mislabeled as irradiance cannot enter a sample or proposal (§4.8.2).
- Every registered Initial-V3 relation profile validates a policy-consumable
  artifact output under its exact profile-owned schema id/version. A schema
  mismatch or invalid payload blocks candidate production without a new
  Layer-3-to-Layer-5 path. The thermal parameter additionally requires its
  frozen `ThermalEvidenceGateCalibration`; the six non-HVAC environmental
  profiles use the shared response-artifact schema (§4.8; Layer 5 §3.1),
  separately from the per-inference `ResultEnvelope` of §4.4.
- No Layer-3 implementation reads a V2 snapshot, model, approval store, or history record.
- A confirmed upstream change that removes a learner's bound source invalidates the learning
  definition in the same composed commit: no analysis, finding, signal or candidate, and every
  artifact and adoption chain unavailable until a successor definition validates. A run captured
  against the old generation cannot publish. A semantic-only upstream change keeps the definition
  but makes existing artifacts unavailable through the source-generation fingerprint (§4.1.2;
  Layer 0 §4.7).
- An administrative learner instance names a registered core kind/version, legal explicit scope,
  blueprint-declared binding selections, all exposed canonical parameter values, and enabled state.
  Tests reject wildcard/live-query scopes, unordered or changed scope membership without restaging,
  unknown/unexposed parameters, raw HA entity/service selectors, executable values, invalid bindings
  and any attempted change to target, tier, egress, model/codec or resource envelope. A test changes
  one parameter of each `ParameterImpact` class and proves the declared invalidation, serving,
  scheduling or no-semantic-effect behavior.
- `ResultEnvelope`, artifact manifests, `InferenceSignal`, and `LearningProposalCandidate` cannot be
  submitted to Layer-0 fact persistence. A test proves that only a later authorized `SemanticResolver` can emit a
  distinct declared `HouseFact` from a valid signal, and only Layer 5 can persist a review workflow
  record from a candidate.
- Every learner declares its historical fact types and positive `training_window` before it can run;
  staging derives and registers the corresponding per-source retention requirements.
- A truncated required history interval leaves the learner warm-up/degraded and produces no new usable
  model from that interval.
- A bounded historical read with `ObservationCoverage(status="incomplete")` makes
  every feature reading that window missing, excluding the sample from that feature's consumers
  under §4.2's requiredness scope, even if retention is complete and matching states
  appear on both sides of a short restart. The common `SampleBinding` builder rejects
  an incomplete feature/anchor or point/event-count outcome window; optional missing
  representation cannot turn a process gap into context. A time-to-event outcome
  with a valid target event before `first_incomplete_at` retains that event; without
  such an event it is right-censored exactly at that instant, never a zero or
  competing risk. `PatternLearner` and `ContextRegimeNoveltyModel` receive only
  eligible samples from the same builder (§4.2, §4.4.1).
- A state last changed hours before `T` but remained observable through `T`
  can satisfy an as-of feature or point outcome without a duplicate fact or
  `max_age` calculation. A newer unavailable transition, a report-age expiry
  or an observation gap rejects it; the resolver never skips the unavailable
  record to recover the older value (§4.2; Layer 0 §4.4).
- With complete observation and retention, a missing `PointOutcome` target is
  rejected, no event in an `EventWindowOutcome` is a valid zero/false, and no
  `TimeToEventOutcome` event by the finite horizon is right-censored there.
  The same missing event after an observation gap cannot become zero or a
  horizon-end censor: it is censored at `first_incomplete_at` (§4.2).
- A `FutureStateFractionOutcome` reconstructs a complete typed state interval:
  six qualifying minutes across a ten-minute horizon yield `0.6`, including
  multiple separate qualifying runs. A transition exactly at the horizon end
  adds no duration. Missing state at the anchor, a source or process gap,
  stale/invalid value, or truncated retention excludes the sample instead of
  producing a partial fraction; wrong-kind or unregistered qualifying values
  fail staging. A registered delay using `occupancy=("absent",)` must match
  the exact typed state stream and qualifying set in Layer 5's timing
  binding; a copied boolean vacancy projection is not required. A separate
  boolean condition can exercise the same generic type contract without
  registering an Initial-V3 solar timing model. No post-anchor state is used as a feature
  (§4.2, §4.4; Layer 5 §4.2/§6.0).
- A correction window crossing process interruption is
  `censored_by_observation_gap`; one with only required-channel unavailability is
  `censored_by_unavailability`; either excludes a zero count. A routine assembly
  window crossing either gap is excluded rather than a negative example.
  `EnvironmentalEpisode` and `EnvironmentalReferenceWindow` reject any required
  pre-anchor, post-anchor, reference, or exclusion span crossing a gap; one complete
  unrelated channel remains eligible. A rebuild retains the full declared
  `TrainingSpan` while excluding its gap-crossing samples; it publishes only with
  enough eligible support and never silently shortens the span to the latest
  inspection slice.
  Tests include a valid event before a later gap, a target event after a gap,
  restart shorter than freshness, one channel still unreadable, equal-time gap
  boundary, and independent retention truncation (§4.4.1–4.4.3, §4.8.1, §5.2).
- A count-ceiling or global-watermark eviction on one bound stream makes only reads that include that
  stream report `retention_coverage="truncated"`. A learner bound to a different `Location` of the
  same `fact_type` remains eligible when each of its own required streams is complete; a multi-stream
  learner becomes warm-up/degraded when any one required stream is truncated.
- An eligibility inspection reads only its bounded new-evidence interval and causal overlap. Once it
  admits a rebuild, the rebuilt artifact identifies a complete rolling `TrainingSpan`, not that
  incremental inspection slice. A test with a rare context found only before the latest inspection
  proves that the context remains represented after a successful ordinary rebuild. A partial update is
  rejected unless the registered core learning type supplies its explicit incremental-fit contract.
- Every learner uses one staged, versioned `SampleBinding`. Staging rejects duplicate feature names,
  invalid state/event claim pairings, under-five-minute interval anchors, `PointOutcome.horizon=None`
  on transition/event anchors, unbounded sequences, impossible retention/buffer requirements, and any
  required/optional missingness contradiction.
  Tests cover as-of state, causal aggregate, bounded causal sequence, point-horizon, event-window,
  time-to-event with right-censoring, and context-only samples. A later fact must never alter an
  earlier sample's features; records sharing `when` are consolidated as one concurrent context and
  never become an implicit feature/outcome pair; an unavailable/stale required feature excludes that
  sample from its consumers under §4.2's requiredness scope, and an invalid target discards it, each
  with its declared diagnostic reason.
- `ContextTransformRef.canonical_config` plus `ReactionDescriptorCandidate.descriptor_parameters` and
  member `semantic_parameters` pass the same RFC-8785 `CanonicalJsonObject` validator before their
  type-specific validator. Tests reject duplicate keys,
  lone surrogates, non-finite/negative-zero/out-of-range numbers, depth/size overflow, raw HA objects,
  and callables; they preserve Unicode strings and array order without Unicode normalization.
- Layer 3 stages a `ReactionDescriptorCandidate` only through the read-only Layer-5 proposal facet. It
  rejects an unknown/incompatible Reaction-descriptor or relation-profile version, illegal scope/objective/member
  intent/guard, an empty or over-bound bundle, repeated member channel, a missing, forbidden or invalid
  numeric-outcome requirement, parameter or envelope shape, and a primary
  artifact incompatible with the exact profile-output schema or descriptor/intent
  pairing. The candidate
  contains no callable, dynamic fact expression, current snapshot, HA service target, `ApplyStep`,
  configured Reaction, or arbitrary condition graph. Tests prove that candidate construction cannot invoke
  policy evaluation or actuator resolution, and that the same descriptor is available to a deterministic
  Layer-5 policy without a learner.
- Two valid candidates with the same envelope axes and cell keys, but support
  10 versus 20 in one cell, have the same semantic deduplication identity and
  refresh review evidence. Changing a root `descriptor_parameters` value or
  adding a cell key changes that identity. Duplicate cell keys with different
  evidence are rejected. Runtime exact-cell lookup and `bounded_adaptive`
  subset checks use keys and partition versions, never equality of complete
  `CoverageCell` records.
- A learner proposal rejects a `CoverageCell` with absent support or
  calibration; a profile-free direct Reaction rejects invented non-null
  learner evidence or mixed optional fields. A direct zero-axis envelope has
  exactly one empty-key cell and uses the same runtime exact-cell lookup; a
  future descriptor may stage only its version-declared typed axes, pure
  partitions and bounded joint cells. An unavailable axis input abstains,
  while a changed partition requires a new descriptor version (§6.5).
- Every proposal-producing core type/version has one frozen `ShadowPreviewBinding`. Staging rejects an
  unknown/dynamic preview schema name, a binding whose producer or candidate kind/version does not
  match the active core registry and read-only Layer-5 proposal facet, a preview schema absent from
  `DiagnosticFindingRegistry`, or a mismatch between preview and candidate semantic validators. The
  complete binding enters the definition fingerprint: a changed/removed candidate kind/version,
  preview schema/version, or binding invalidates only the affected artifacts and active previews.
  Tests prove that a preview cannot use a fallback schema/version or payload validator merely because
  its string name resembles a registered candidate kind.
- The initial bindings are exactly `environmental_episode` version `1` to
  `shadow_proposal_preview.reaction_descriptor.environmental.v1` and
  `actuation_routine_pattern` version `1` to
  `shadow_proposal_preview.reaction_descriptor.routine.v1`, both through `reaction.descriptor` candidate
  version `1`. Tests prove that every active environmental relation profile uses only the former,
  cannot reach `proposal_eligible` without a valid preview under its required shadow gate, and cannot
  select a schema by relation profile, descriptor text or payload shape; an optional routine shadow uses
  only the latter. A removed binding/schema selectively withdraws the affected previews and makes only
  its producer artifacts unavailable for the corresponding shadow/promotion path.
- A learner with live egress accepts only `usage="runtime_resolvable"`. Its historical sample and
  live inference use the same versioned `SampleBinding` and feature resolver; a test changes a
  declared binding version and proves that the previous artifact is unavailable until revalidated,
  rather than allowing a second, divergent serving transform.
- A non-diagnostic suppression owner emits one transient `AvailabilitySuppressionOccurrence` when it
  begins abstaining, when its canonical reason set changes, and when it recovers; identical per-cycle
  abstentions produce metrics only. Tests cover unavailable/out-of-envelope learning evidence, manual
  hold, command ownership, actuator capability/state, cooldown and action-guard causes, including a
  canonical multi-cause set. Tests permute the same multi-cause input and prove that the one frozen
  pure helper yields the same ASCII-lexicographic tuple, episode identity, delivery grouping and RFC
  8785 JSON; they reject empty, duplicate, unknown or manually out-of-order tuples, a `HeimaEvent`, `HouseFact`,
  persistence request, user text or `automation_scope_id` in the occurrence; and prove that the
  `AvailabilityEpisodeTracker` is the only Layer-6 input path for an owner occurrence, while its
  immutable exact-subject `AvailabilityPublicationIndex` is the only binding-selection path. A key may
  resolve to a canonical tuple of distinct bindings; staging rejects a duplicate target for the same
  key. Each matched enabled user-visible binding lets Layer 6 correlate restoration with its already notified
  `(automation_scope_id, subject, reasons)` episode and persist one `automation.availability` event;
  an absent/disabled/non-visible binding leaves only metrics. A publication-generation swap retains an
  unchanged notified binding without duplicate delivery, delivers an already active episode to a
  newly visible binding, and closes a removed/disabled/non-visible notified binding with
  `binding_deactivated` audit only; a later restoration reaches only still-active notified bindings.
  Tests prove that owner occurrence handling never queries the publication index and that a process
  restart starts the transient tracker empty rather than replaying delivery history.
- A Layer-5 `active_channel_unmanaged_after_restart` availability occurrence uses that same
  tracker and `automation.availability` fact; it carries no Actuator id, HA
  payload or user text in the occurrence. Every process restart with a
  fresh active channel and no usable management proof starts a new issue,
  even when the action trigger is false; Layer 6's notification key differs
  between process runs and is stable for retries within one run. Repeated cycles
  while the same observed channel remains active produce one visible issue,
  while a later fresh inactive observation produces a `restored` transition
  whose rendering does not claim Heima switched the device off. A trigger
  ceasing to qualify while the device remains active does not falsely restore
  this already opened issue (§6.3.1; Layer 5 §3.2).
- An `interval` anchor declares a sampling interval of at least five minutes. A state-transition or
  event-occurrence anchor remains attached to its actual historical timestamp and is never rounded to
  that cadence.
- Shared support, warm-up, tier fallback, and confidence behavior is implemented once in
  `PatternLearner`, not copied into family analyzers.
- `WarmupGate` is evaluated once per `(learner_id, subject Location)` before tier selection. A test
  proves that a support-sufficient coarse tier produces no result before this common gate opens, then
  becomes eligible after it opens without requiring a separate per-tier warm-up state.
- Every `PatternLearner` tier has a stable identity independent of list position and constructs its
  bucket only from declared, typed, canonicalized feature bindings. Staging rejects an ambiguous,
  untyped, duplicate, or semantically incompatible tier; every finding identifies the selected tier
  and complete context bucket.
- `min_support` is tier-specific, while `min_confidence` is unique to the learner and gates every
  usable inference result regardless of the selected tier.
- A categorical bucket with tied highest-support outcomes is diagnostically retained but unusable by
  single-value inference; no incidental implementation ordering may select an outcome.
- Bucket lookup is exact after declared canonicalization. Context generalization is permitted only
  through an explicitly staged coarser tier or a feature's declared bucketing transform, never
  through nearest-value or wildcard matching at inference time.
- `PatternLearner` selects exactly the first usable tier in declared priority order. A test with
  overlapping rich/coarse samples verifies that it neither averages their distributions nor compares
  their confidence to select a later tier; a richer usable tier wins, while a richer unusable tier
  yields the first usable coarser tier together with its coded fallback trace.
- Staging rejects a nominal fallback sequence that adds/replaces a context dimension or uses an
  unrelated transform. A test accepts a declared transform coarsening and dimension removal, while a
  test with `(day_kind, time, occupancy) -> (day_kind, temperature)` is rejected as not a coarsening.
- The frozen core `ContextTransformRegistry` accepts only versioned references with canonical
  configuration and validates every feature/input-output shape in staging. Tests prove the declared
  `coarse(raw) == coarsen(fine(raw))` property for supported time/numeric bucket pairs, reject an
  unsupported regrouping, and prove that a changed/removed transform version invalidates only learners
  that reference it. No persisted generation or artifact contains a transform callable.
- `BucketValue` preserves the distinction among `false`, `0`, and `"0"` in context and coverage keys.
  A configured numeric interval using scaled integer bounds accepts its lower bound, excludes its upper
  bound, rejects overlap, and produces no nearest-bucket fallback for an uncovered value.
- A global gate failure attempts no tier and returns `global_gate_failed`; each tier-local rejection
  attempts the next tier and records exactly its coded reason. A malformed artifact/result schema is
  tested as a global unavailable-artifact failure, never as a reason to use a lower tier.
- Each learner declares its own `max_artifact_staleness`. A compatible preceding artifact may remain
  usable only through that evidence-based limit after a failed refresh; a changed definition
  fingerprint immediately makes prior artifacts inference-unavailable.
- `PatternLearner` serves only categorical and scalar-continuous targets. Time-to-event, discrete
  count, and targetless analysis use separately typed optional model classes, with
  censoring/competing-risk, distribution/calibration, and score/threshold contracts respectively;
  none obtains operational authority merely by existing.
- Every result uses a core-owned, versioned `ResultEnvelope` with matching artifact and
  `SampleBinding` identities. Its persisted/interprocess manifest is RFC 8785 canonical JSON with
  finite values, canonical Layer-1 `EvidenceInstant` instants and Layer-0 `Window` durations, and no raw HA payload.
  Round-trip fixtures reject alternate `Z` instant and integer-millisecond duration encodings,
  including a result horizon and a thermal response duration (§4.2–§4.4).
  An arbitrary pickle/callable/executable artifact is rejected before preload; its core-owned codec,
  digest, size, and definition fingerprint are all verified.
- Every administrator diagnostic uses the frozen core `DiagnosticFindingRegistry`; tests reject an
  unknown schema/version, noncanonical finding key, invalid bounded payload, raw HA/resident data,
  executable value, policy/action/notification authority, and a compatible evidence refresh that
  creates a second finding instead of updating the same key. Acknowledge/dismiss state remains outside
  the finding and cannot become a learner input without a separately staged explicit-feedback contract.
  Each schema has a positive per-subject active-finding bound and deterministic schema-local selection
  key: a test exceeds the bound with valid distinct keys, retains exactly the selected keys with a
  stable final `finding_key` tie-break, records the remaining entries as `suppressed_by_capacity`, and
  proves that neither another schema nor acknowledgement/dismissal changes that selection.
- A complete compatible diagnostic publication atomically replaces its schema/subject/fingerprint
  active snapshot: a retained key refreshes evidence, while an absent or ineligible prior key is
  withdrawn and preserved only in audit/history. Tests prove that capacity is recalculated from this
  new snapshot; a previously suppressed key may become active later; acknowledgement/dismissal cannot
  retain, revive, withdraw, rank, or train from a finding; degraded findings remain visibly degraded
  only through `max_artifact_staleness`; expiry, disablement, or artifact incompatibility withdraws
  them; and a definition-fingerprint change immediately supersedes every prior active finding rather
  than displaying it through the new generation's warm-up.
- Result validators reject a categorical distribution that differs from the active vocabulary or has
  invalid probability mass; a scalar with an invalid unit/dimension/range/interval; a noncontiguous
  or unbounded-length count distribution; a non-monotone survival/competing-risk curve; and an
  unsupervised score presented as a probability or compared across baseline/schema versions.
- A `CountModel` may learn actuator corrections only from normalized attributable correction events.
  It must never classify an unproven raw HA state change as a resident manual override.
- `RoomOccupancySurvivalModel` derives only `stay_duration` (`absent -> present -> absent`) and
  `return_delay` (`present -> absent -> present`) from complete resolved occupancy episodes. Tests
  prove that an unavailable observation interval and end-of-history are right-censoring; a declared
  competing event is not recoded as censoring; no post-anchor feature is read; every curve is monotone;
  and no survival output directly commands an Actuator, alters a policy/hold, or emits an
  `InferenceSignal`. `stay_duration` stays diagnostic-only. An action-serving
  `return_delay` revision needs a validated one-minute point and the exact
  staged maximum horizon, physical-evidence-eligible room labels, declared
  competing-event calibration, common shadow/adoption gates and matching
  subject/definition/result schema; a failed gate leaves the authorized
  Layer-5 seed in use. No result is recast as a future-state fraction.
- No Initial-V3 solar timing artifact is published merely because the
  generic `FutureStateFractionOutcome` can represent a boolean solar
  condition. A candidate attempting to bind `environment.solar_shading` to
  an unregistered solar-fraction learning definition or timing path fails
  staging; its fixed dwell remains available under Layer 5 §7. Historical
  windows containing source gaps remain incomplete for every future
  fraction-profile registration (§4.2, §4.4; Layer 5 §4.2).
- `ContextRegimeNoveltyModel` scores only complete staged historical context vectors. Tests reject raw
  HA/entity/resident inputs, an unseen categorical value, an out-of-envelope continuous value, an
  unbounded feature sequence, score/probability conflation, and a model result that attempts any
  signal/fact/policy/action/security conclusion. A known security-posture rule remains observable and
  active even when the novelty model scores its context as normal or unavailable.
- `CorrectionCountHurdleModel-v1` uses the complete, uniquely anchored Layer-5 correction evidence
  for one registered Actuator/channel and emits only the `0`/`1`/`2+` distribution. Tests prove that an
  unavailable target window or superseding compatible `ApplyStep` censors, rather than supplies a
  zero-count sample; external/unknown, duplicate, unanchored, and malformed correction records are
  excluded; insufficient `>=1` or `>=2` support leaves the artifact unavailable; and no diagnostic
  count result can alter a policy, hold, action, or `InferenceSignal`. A passing core review gate
  produces only one stable `DiagnosticFinding` with `correction_burden.v1` per semantic
  scope/Actuator/channel/context and definition fingerprint; tests reject raw HA/resident data, a
  target or parameter recommendation, notification/action authority, and treating acknowledgement or
  dismissal as a training label.
- A correction-count sample joins one admitted target decision to its first
  complete-observation phase and the channel's covered history, then counts
  only deduplicated resident correction events within its complete window.
  A complete window without such an event is one zero; a decision with no
  full observation, a later superseding decision, revocation, unavailable
  channel or process gap cannot become zero. A late full observation after
  a terminal call timeout anchors without changing that call outcome
  (§4.4.2; Layer 5 §6.1).
- `ActuationRoutinePatternModel-v1` accepts only declared typed trigger/context bindings and verified
  resident-control outcomes. Tests prove that equal-`when` members remain one concurrent observation
  group, `AppendOrder` cannot create causal order, an unavailable/ambiguous/overlapping-policy window
  is excluded rather than negative, a complete no-control window is a typed negative denominator
  observation without creating a candidate, a different valid bundle is negative for one candidate
  and positive for its own, a repeated member channel or over-bound bundle is rejected, and an
  accepted candidate contains only the registered `routine.actuation_bundle` descriptor and canonical
  member targets. A learner artifact cannot activate, evaluate or execute the resulting policy; before
  its explicit `proposal_eligible` transition it may emit only the registered shadow preview.
- Its versioned subject baseline divides eligible matching-bundle start-time
  exposure by total eligible start-time exposure for the same assembly width,
  independent of trigger occurrences. Tests distinguish a matching bundle,
  another bundle, no resident control, a sequence across an arbitrary clock
  boundary, unavailable/confounded coverage and a process gap. An interval
  sweep agrees with direct classification of small timestamp fixtures and
  does not need periodic device readings. A trigger-only routine still has a
  subject baseline; a zero baseline yields unavailable lift rather than
  infinity or an eligible proposal. For positive baseline, lift is the
  conditional-to-baseline ratio, with 1 as no association. Baseline windows
  create no `ActuationRoutineEpisode`, and overlapping start instants never
  inflate independent support or temporal-block confidence. No future
  partition may enter either denominator (§4.4.3).
- A verified resident brightness change joins exactly one canonical
  channel-state edge by `control_edge_id` and stages only the descriptor's
  permitted target facets. An external/unknown change, an unproven wall
  switch power cut that makes a bulb unavailable, or a missing/double join
  cannot become a resident routine member or a complete no-action negative
  (§4.4.3; Layer 0 §5.1.1).
- Household-context censoring (CA4-123): a routine-learner episode while a house sitter is inside
  with every resident away is `censored_by_household_context`, never `no_resident_control`; during a
  three-day guest stay with residents home, samples whose subject or slots are in the stay's guest
  room are censored and living-room samples are kept; an unavailable `occupied_without_residents`
  censors; an unavailable `household.guest_stay` censors the default guest rooms. A novelty instance
  with an occupancy feature is behavior learning and raises no finding during the stay; one with only
  HVAC and temperature features is physical and unaffected; a thermal instance using occupancy
  episodes only as cohort boundaries stays physical. An occupancy-assist signal for the guest room
  abstains during the stay.
- Manual-control actors (CA4-119): the same brightness change from a resident who is an
  administrator is a member; from a `guest`, a guest-room tablet (`device`) or an installer
  (`administrator`) it is never a member, and on a required channel it makes that candidate's
  window ambiguous and excluded, not a `no_resident_control` negative; from an approved physical
  switch adapter (`physical`) it is a member. A `manual_override` with `control_actor="guest"`
  never enters the correction count.
- `IndirectSemanticAssistModel-v1` accepts only a frozen `IndirectAssistanceContract`. The
  same signal type may serve multiple resolver kinds only through distinct frozen contracts;
  staging rejects one `(signal_type, contract_id/version)` routed to two resolver kinds, a different
  claim-parameter tuple, or a subject outside that contract's legal scopes. The
  `occupancy.room_present.indirect.v1` contract trains/validates only against the same-room
  `FactSlot(fact_type="occupancy.physical", where=subject_room)` with physical producer provenance;
  tests reject individual occupancy evidence, a
  learned/semantic-resolver-derived target, current occupancy/presence feature, raw HA identity/payload,
  `absent` assertion, stale/expired signal, a non-live artifact, non-room subject, or insufficient
  calibrated probability/PPV. The `activity.sleeping.indirect.v1` contract accepts only an immutable
  resident-approved routine reference, its staged independent evidence families, a current physical
  occupancy precondition, and routine-affinity validation; tests reject an unlabeled cluster presented
  as ground truth, an Heima-authored light/actuator output as evidence, a fabricated PPV/accuracy,
  `inactive` assertion, invalid shadow/drift gate, or high-risk policy posture. The
  `activity.relax.indirect.v1` contract additionally requires two independent routine-evidence
  families; tests reject media/light/clock/low-motion as a sole route and a Heima-attributed action as
  positive evidence. The `activity.working.indirect.v1` contract requires one workstation-operational
  family plus one independent context family; tests reject a weekday/time, calendar, computer activity,
  or communication state alone, an `office` calendar plan, raw desktop content, and a Heima-attributed
  action as a positive route. All contracts omit the signal on failure and reject any attempt to persist
  it as a `HouseFact` or use the assisted semantic output as a later reference/feature.
- `ContextHypothesisCandidate` has no active V3 kind or producer: staging rejects every attempted
  instance. A future casa-scoped diagnostic kind must be closed to a staged core vocabulary and tests
  must reject raw HA/resident payload, a command, policy, HouseFact, `InferenceSignal`, action-review
  status, automatic notification, or direct state transition. A confirmation/rejection/dismissal
  belongs only to the later authenticated administrative-review contract and cannot become a training
  label without a separately staged reference rule.
- A categorical vocabulary is closed in every active generation. Values can become active only by
  the declared closed policy or, for `curated_extensible`, by reviewed approval and staging of a new
  generation; discovery never self-promotes a label.
- The core learning-type registry is frozen before staging and admits only reviewed versioned core
  types. Definitions and artifacts persist type identity/version rather than callables; plugins can
  consume findings only through their staged analyzer/proposal boundary.
- Refresh cadence performs evidence eligibility, not unconditional training. Every published artifact
  identifies its complete sampled data span and training watermark; one learner has at most one run,
  missed ticks never catch up, and a stale-generation run cannot publish.
- In-process learning is admitted only within a declared bounded `ResourceEnvelope`; dynamic
  scheduling may defer slow-path work but never borrows hot-path capacity. A future external backend
  receives only a bounded redacted execution request and can return only an untrusted candidate for
  local validation/promotion.
- The selected installation profile derives a machine-specific `LearningCapacityPlan` with
  `lower`/`target`/`upper` aggregate limits rather than fixed host-independent values. Bootstrap is
  passive and admits at most the lower plan; a test proves that capacity increases only after a healthy
  observation window, while memory pressure, cycle-latency degradation, timeout/checkpoint failure or
  other health failure blocks new admission at the next boundary without killing an admitted run. Queue
  delay and staleness are demand signals, never health failures; they can raise capacity only while
  health gates remain green. Missing health metrics cannot increase capacity. External dispatch is bounded separately by local
  coordinator concurrency, bytes, read work, deadline and retry budget, and cannot occur as an
  automatic local-pressure failover.
- The admin may choose an explicit learning-capacity profile and receive an evidence-based diagnostic
  recommendation, but profile changes affect only future scheduling admission and never alter model
  semantics or abruptly reconfigure an admitted run.
- No learner or analyzer blocks an engine evaluation, reads a live HA object, or issues an action.
- An ML model trains only off the hot path from declared historical bindings, publishes an immutable
  versioned artifact with validation/uncertainty metadata, and becomes unavailable rather than serving
  an incompatible or incompletely trained artifact.
- ML validation uses chronological partitions and a declared embargo that prevents overlap through
  either feature lookback or target horizon. It records target-specific quality, calibration,
  operating-condition coverage, and comparison with its declared baseline.
- Every reviewed learning type/version or relation profile declares exactly one closed
  `shadow_requirement`; staging rejects a missing/unknown value and an administrator/definition/plugin
  attempt to weaken it. Tests prove `not_applicable` has no shadow or promotion state;
  `optional_before_proposal` may be promoted only through an explicit administrative transition;
  `required_before_proposal` and `required_before_live_signal` cannot reach their respective eligible
  state before their type-owned shadow gates; and `shadow_only` has no promotion path.
- A shadow artifact may publish ordinary diagnostics and a registered `DiagnosticFinding` preview
  schema only. Tests reject an attempted `LearningProposalCandidate`, Layer-5 proposal-facet call,
  `ReactionProposal`, `InferenceSignal`, notification or HouseFact/action from `shadow`; verify that a
  preview follows normal finding capacity/staleness/supersession rules; and prove that promotion creates
  a new candidate only after fingerprint/evidence/expiry rechecks and independent Layer-5 validation,
  never by converting an acknowledged, dismissed, stale, withdrawn, or capacity-suppressed preview.
- A model publishing both a validated `DiagnosticFinding` and a registered
  `InferenceSignal` exposes the current bounded finding even before an
  artifact is adopted for the signal. Promotion after required shadow
  atomically records the exact signal artifact and administrator-selected
  mode. In `pinned`, a newer revision emits no signal until a current-head
  authenticated Layer-3 adoption transition approves it; in
  `bounded_adaptive`, only a compatible, validated revision advances through
  one idempotent system transition. A changed signal consumer, definition or
  unapproved envelope cannot auto-adopt or borrow a Layer-5 proposal. A
  crash during append reveals the old or new complete head; stale or
  withdrawn adopted evidence emits no signal and never extends an earlier
  signal's expiry (§4.9, §6.1.1, §6.3).
- A signal consumer switches from `pinned` to `bounded_adaptive` through
  `set_signal_artifact_adoption_mode` only after its exact current artifact
  and approved bounds pass validation; the same revision stays adopted.
  Switching back fixes the current revision even when it is temporarily
  unavailable. A stale-head retry or an automatic revision racing with the
  switch cannot create two heads; a restart sees the old or new committed
  transition. Neither switch retrains, extends a prior signal's expiry or
  uses Layer-5 proposal review (§4.9).
- Changing an environmental learner's `objective_id` or
  `minimum_practical_delta` changes its serving-generation fingerprint and
  candidate semantic identity, but leaves the validated response artifact's
  definition fingerprint and analysis revision unchanged. An unreviewed old
  candidate is withdrawn; a previously approved Reaction retains its frozen
  objective until ordinary Layer-5 successor review. A serving-only edit of
  a live-signal instance withdraws its old consumer adoption without
  retraining; the new serving generation needs its own approval before
  emitting (§4.1.2, §4.5, §4.8, §4.9).
- Schema incompatibility immediately makes an artifact unavailable. Statistical input, target,
  residual, or calibration drift produces diagnostics and a bounded slow-path re-evaluation or
  retraining request, never an online parameter mutation or automatic promotion.
- `EnvironmentalEpisodeLearner` has one common episode/artifact/validation/proposal implementation;
  `solar_shading`, exchange, and future environmental use cases are staged relation profiles, never
  separate learner engines. `StratifiedResponseModel` admits a cell only with complete transition and
  `EnvironmentalReferenceWindow` cohorts in that exact canonical cell; it neither interpolates nor
  presents its conditional observed response difference as causal effect.
- A profile-declared observed cover/opening Sensor transition, registered HVAC-action transition,
  or exact registered Actuator-channel facet transition can anchor the same environmental episode
  mechanism. An extraction-fan channel with a changed declared `level` facet and complete
  predecessor/continuation history may qualify; a future humidifier channel needs its own exact
  profile and outcome before it can qualify. A command result, `already_satisfied` decision,
  unchanged or unrelated facet, duplicate Sensor/channel projection, channel mismatch, first
  valid post-gap state, unavailable record or incomplete predecessor never becomes an anchor.
  A relevant competing control transition in the exclusion interval rejects the affected episode
  without excluding an independent room's complete history (§4.8.1–4.8.2; Layer 0 §5.1.1.1).
- An extraction fan already active at qualifying start records its observed
  state and origin but supplies no Heima-start effect sample; no command or
  `already_satisfied` decision is relabeled as a physical transition. When
  an inactive fan is started and later changes level or stops under a
  declared program, each actual edge retains its pre/post `level` and may
  enter only its exact `transition_class_id` cohort with complete coverage.
  `start`, `modify_up` and `terminate` have separate estimates and
  same-class stable-state references; a downward or multi-level edge is
  excluded; a profile with one pooled on/level/off cell or overlapping class
  matchers is rejected. A resident/external level edge retains its origin rather than becoming a
  Heima action; a post-gap baseline is never an edge (§4.8.1–4.8.2).
- A profile with multiple versioned observed-transition classes assigns a
  complete physical edge to exactly one class or excludes it. Its episode,
  matching stable-pre-state reference, output cell and validation use that
  class id; bootstrap identity and optional quantile cohorts do too. Tests
  reject overlapping matchers, mixed start/modification/termination samples,
  speed increases pooled with decreases, missing reference coverage and a
  class whose estimate lacks its own support. A valve or cover profile uses
  the same learner and class-key rule (§4.8–4.8.2).
- An unavailable start, modification or termination estimate affects only
  its exact class/context/horizon cell; no other class or nearby context
  supplies a substitute. An eligible independent cell remains usable, while
  a deterministic step is governed by its Layer-5 descriptor and current
  admission, never by an invented Layer-3 fallback (§4.8.2; Layer 5 §3.2).
- Complete resident or external target changes may inform an exact physical
  transition class only under that profile's matcher and confounder rules;
  their origin remains resident or external. A favorable speed, cover or
  valve modification estimate alone is not a current need or a promise of
  whole-program success (§4.8.1–4.8.2; Layer 5 §3.2).
- The Initial-V3 generation registers `hvac_thermal_response` but keeps it evidence-gated. It accepts
  only an observed registered HVAC-action transition with all required
  pre-anchor facts and a complete post-anchor temperature trajectory. Tests reject a requested command,
  raw HA attribute, absent/mismatched HVAC mode, manual setpoint change or other declared thermal
  confounder in its exclusion window. Its candidate contains only an exact-cell bounded
  `ThermalResponseParameter` for the registered HVAC descriptor; it cannot contain an endpoint, target
  temperature, recovery schedule, signal or action. A test proves an absent energy binding removes
  energy-savings claims and energy-benefit promotion metrics rather than substituting a default.
  Complete observed Layer-4 `occupancy.departure`/`occupancy.return` episodes may delimit historical
  absence cohorts (a house sitter inside is not an absence for physics), but
  a calendar plan cannot label a cohort, become a feature, or substitute for either observed boundary.
- `ResidentPresentationPreferenceModel` accepts only a closed explicit-feedback event for one staged
  non-safety `presentation_scope`; a missing response is censored. Tests reject a raw HA entity or
  payload, manual environmental behavior as a presentation label, an implicit negative label, an
  undeclared delivery parameter, and every attempt to alter policy meaning, effect estimate, guard,
  safety class, action, or a safety-critical notification. Its result is a reviewable delivery
  parameter only.
- `EnvironmentalQuantileResponseModel` is an optional estimator inside that same learner and profile
  contract. A test verifies separate transition/reference quantile cohorts; rejects a raw HA object,
  missing or post-anchor feature, unknown category, out-of-range continuous input, unsupported
  applicability partition, quantile crossing, and any attempt to emit a signal/action. It also proves
  that only the conservative contrast bound in the permitted objective direction can create a shadow
  candidate, while `typical_contrast` alone cannot.
- `StratifiedResponseModel` publishes `median(transition) - median(reference)` together with both
  cohort p10/p50/p90 values and a reproducible temporal-block-bootstrap interval. A test uses adjacent
  correlated records and proves that resampling retains whole common calendar blocks rather than iid
  rows; it also proves that a missing cohort, insufficient distinct blocks, too few valid replicas, or
  an over-wide profile interval makes the cell unavailable.
- `StratifiedResponseModel` validation is walk-forward with an embargo at least equal to
  `dependency_window` and an untouched final holdout. Tests prove that a source window crossing a split
  is excluded, a passed artifact is not refitted on its final holdout, and a cell failing zero-response
  baseline, directional agreement, interval coverage, or a declared operational slice is excluded from
  the envelope; too few remaining cells leave the artifact `diagnostic_only`.
- The initial `minimum viable envelope` is exactly one independently validated cell with every required
  profile axis resolved; a test proves that this permits a rare but fully evidenced condition without
  nearest-cell expansion or a global coverage percentage. Opportunity count/rate/classification is
  review diagnostics only: changes refresh evidence but do not change candidate identity, configured
  policy authority, or Layer-5 live evaluation.
- A thermal-topology model never claims airflow or air-quality prediction without the corresponding
  measured inputs, and reports unidentifiable parameters rather than fabricating coefficients.
- A third-party learner has no live-signal, `ApplyStep`, or actuator-invocation output path; it can
  reach operations only by submitting a candidate for an exact registered core kind and descriptor,
  then through its reviewed proposal.
- A learning result can affect an operational semantic claim only through an explicitly listed bounded live
  exception or after Layer-5 admin review.

## Related documents (background only, not required reading)

This design derives from the historical `v3_pattern_learner_draft.md`,
`v3_architecture_recap.md`, and the learning entries in `v3_backlog.md`. Where those documents
differ from this specification, this document is the current Layer-3 design contract;
remaining corrections are tracked as CA4 items.
