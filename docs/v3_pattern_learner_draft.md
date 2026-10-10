# Heima v3 — `PatternLearner` (draft shapes)

> **Historical draft.** The current V3 learning contract is
> [Layer 3](specs/v3/layer3_learning_spec.md); this file preserves earlier reasoning only.

Status: **historical draft, superseded by Layer 3, not implemented as written.** Promotes Layer 3's central
primitive out of backlog prose (`v3_backlog.md`, LP-1 through LP-6) into a concrete shape, the same
way `HouseFact`/`Provenance`/`Timing` and `Sensor`/`FusionRule`/`Actuator` already have one. Builds
on `v3_house_fact_draft.md` (`HouseFact`, `Window`, `WarmupGate`, `Location`) and
`v3_sensors_actuators_draft.md` (`Interpretation`, for context on what a `HouseFact`'s `value` looks
like).

---

## Why this exists, in one paragraph

Today, every learning family hand-rolls its own bucket-by-key / count / threshold-gate / confidence
logic — `WeekdayStateModule`, `HouseStateInferenceModule`, `HeatingAnalyzer`, `LightingAnalyzer`, and
others, each with its own defaultdict counters, its own `min_support` handling, its own confidence
formula (4 different, incompatible ones were found — `v3_backlog.md` LP-1). `PatternLearner`
replaces all of that with one shared primitive: bucket history by an arbitrary key, gate on support
and warm-up, compute confidence with exactly one of two standardized formulas, fall back through
tiers from most to least specific. Every learning family becomes a `PatternLearnerConfig` instance,
not a bespoke class.

---

## The target being predicted

```python
class TargetShape(Enum):
    CATEGORICAL = "categorical"   # a discrete label: house_state, scene name, activity name
    CONTINUOUS = "continuous"     # a numeric value: a setpoint, a rate of change, a duration

@dataclass(frozen=True)
class ContinuousConfidenceParams:
    floor: float = 0.3     # confidence never reported below this, matches today's analyzers'
                             # own floors (HeatingAnalyzer/LightingAnalyzer/PresenceAnalyzer all
                             # independently picked 0.3 — keeping it as a named default, not
                             # coincidence)
    scale: float = 1.0     # dispersion normalizer; unit matches the target (e.g. degrees C for a
                             # setpoint, minutes for a time-of-day) — always named per learner
                             # config, never a magic number at the call site
```

Confidence is computed by exactly one formula, chosen by `target_shape` — standardized 2026-09-01
(`v3_backlog.md`, LP-1+LP-2), never reinvented per learner:

```python
# CATEGORICAL: confidence = count_of_most_common_outcome / total_observations   (a true match ratio)
# CONTINUOUS:  confidence = max(continuous_params.floor,
#                                1.0 - dispersion / continuous_params.scale)     (inverse dispersion)
```

`min_support` is a separate, boolean pass/fail gate ("not enough data to trust this at all") —
**never** blended into the confidence value itself. That blending was the one formula found actually
wrong in the audit that led here (`min(1.0, support / min_support)`) — a volume proxy mistaken for
confidence.

---

## Bucketing — the tiered fallback ladder

```python
@dataclass(frozen=True)
class BucketKey:
    fact_types: tuple[str, ...]
    # the key value at a given instant is the tuple of these fact_types' values, read from the
    # same Location at (or immediately before) that instant — e.g. ("weekday", "hour_bucket") or
    # ("room_occupancy_pattern",) or ("heating.delta_bucket", "heating.state")
    # Exact join semantics (nearest-prior-value vs. exact-timestamp-match per fact_type) are an
    # implementation detail, not specified here — same latitude already given to LearnedWindow's
    # calibration formula in v3_house_fact_draft.md.

@dataclass(frozen=True)
class PatternTier:
    name: str            # e.g. "rich", "coarse", "minimal" — or a single tier, most learners
                           # won't need more than one
    key: BucketKey
    min_support: int
```

A `PatternLearner` config declares an ordered tuple of tiers, most specific first. At inference
time, the first tier whose matching bucket has `total >= min_support` (and, for a categorical
target, whose winning outcome clears the configured confidence floor) wins; if none do, no pattern
is returned — this generalizes what `HouseStateInferenceModule`'s rich→coarse→minimal ladder already
does today, and what the newly-decided room-occupancy-pattern tier (`v3_backlog.md`, LP-1/LP-2
resolution) needs, as a capability every learner can use, not one learner's private structure. A
learner that only ever needs one bucket shape declares a single-element tier tuple.

---

## The learner itself

```python
@dataclass(frozen=True)
class PatternLearnerConfig:
    learner_id: str                 # e.g. "house_state_inference", "heating_thermal_response",
                                      # "activity_discovery"
    family: str                     # governance family — same string `enabled_plugin_families`
                                      # gates (v3_backlog.md, LP-3); covers this learner whether it
                                      # feeds a live signal, a proposal, or both
    target_fact_type: str           # what's being predicted, e.g. "house_state",
                                      # "heating.thermal_response_rate"
    target_shape: TargetShape
    continuous_params: ContinuousConfidenceParams | None = None   # required iff target_shape is
                                                                     # CONTINUOUS
    tiers: tuple[PatternTier, ...] = ()
    warmup: WarmupGate = ...         # from v3_house_fact_draft.md — per-subject time+sample floor
    history_window: Window | None = None   # bounded rolling lookback (e.g. 7 days for a
                                             # seasonally-sensitive learner); None = the full
                                             # retained history (EventStore's own retention applies)
    where: Location = ...            # scope of both training history and inference — casa, one
                                       # room, a zone; a room-scoped heating learner and the
                                       # whole-house one are two config instances, not one learner
                                       # with a room parameter

@dataclass(frozen=True)
class LearnedPattern:
    tier: str
    key_values: tuple[Any, ...]
    predicted_value: Any
    support: int
    total: int
    confidence: float


class PatternLearner:
    def __init__(self, config: PatternLearnerConfig) -> None: ...

    def analyze(self, history: HouseFactQuery) -> None:
        """Rebuild the model from HouseFact history (v3_backlog.md, LP-4 — queried directly by
        fact_type/Location/time window, never through a bundled snapshot intermediate). For each
        tier, bucket `target_fact_type` observations within `history_window` (or all retained
        history) by that tier's BucketKey; a bucket only becomes usable once the warm-up gate is
        satisfied for its subject. Runs on Layer 3's own slow cycle, not the per-cycle engine loop.
        """

    def infer(self, context: dict[str, Any]) -> LearnedPattern | None:
        """Query the current best match, most-specific tier first. Returns None if no tier has
        enough support. Does NOT check admin-approval state — that's a governance concern layered
        outside this primitive (see 'Two consumption paths' below), not PatternLearner's job."""

    def propose_candidates(self) -> list[LearnedPattern]:
        """Every pattern across every tier that clears min_support, regardless of prior approval —
        feeds the registry-analyzer stage that turns these into ReactionProposals."""
```

---

## Two consumption paths, same primitive, deliberately different governance

Restates the Layer 3 governing rule (`v3_backlog.md`, Phase P4b) in terms of this primitive, so the
split is visible on the type itself, not only in prose:

- **Bounded live signal** (`infer()`): only 3 individually-audited call sites are allowed to trust
  this without going through admin review first — Activity (already-approved patterns only),
  Occupancy (sensorless rooms, confidence floor), HouseState (already-approved contexts only). Each
  of those call sites is responsible for its own approval-gating logic on top of `infer()`'s raw
  result; `PatternLearner` itself has no concept of "approved."
- **Reviewable proposal** (`propose_candidates()`): the registry-analyzer stage reads this, wraps
  each `LearnedPattern` clearing support into a `ReactionProposal` (`HouseFact` + `Provenance` +
  review status, per `v3_house_fact_draft.md`), and nothing reaches operational behavior without
  admin review. This is the *only* path available to a third-party plugin's own `PatternLearner`
  instance (`v3_backlog.md`, LP-6) — `infer()`'s live-signal tier stays closed to external code.

---

## Worked example — the two learners from the Heating thermal-response redesign

Concretely resolves `v3_backlog.md`'s AR-4 part 2B without inventing anything beyond this shape:

```python
PatternLearnerConfig(
    learner_id="heating_thermal_response",
    family="heating",
    target_fact_type="heating.temperature_rate",     # °C/hour, signed
    target_shape=TargetShape.CONTINUOUS,
    continuous_params=ContinuousConfidenceParams(floor=0.3, scale=0.5),  # 0.5 °C/h dispersion scale
    tiers=(
        PatternTier(
            name="delta_and_state",
            key=BucketKey(fact_types=("heating.delta_bucket", "heating.state")),
            min_support=10,
        ),
    ),
    warmup=WarmupGate(min_elapsed=Window(seconds=7 * 86400), min_samples=20),
    history_window=Window(seconds=7 * 86400),   # rolling 7-day window, not all-time history —
                                                   # this is what absorbs seasonal variation
                                                   # (solar gain, day length) without an explicit
                                                   # season bucket dimension, per AR-4's own
                                                   # resolution
    where=Location(scope="casa"),   # or Location(scope="room", room_id=...) for a room with its
                                      # own TRV, per AR-4's per-room addendum — same config shape,
                                      # different `where`
)
```

`propose_candidates()` output here feeds the `AnomalyAnalyzer` comparison (today's observed rate vs.
this baseline) and, separately, a `heating_setback_calibration` `ReactionProposal` once a pattern is
stable enough — both already decided in AR-4, neither needing anything beyond what's drafted above.

---

## Not yet decided

- Exact join semantics for multi-fact_type `BucketKey`s (nearest-prior-value vs. exact-timestamp
  match) — flagged above as an implementation detail, not a blocking design question.
- Whether `PatternLearnerConfig` instances are declared in code only (core-team-authored, matching
  today's built-in learning families) or ever admin-configurable through the panel — no learning
  family is admin-authored today, and nothing in this session's reasoning proposed changing that;
  worth an explicit "no" if this becomes a real spec, not an assumed one.
