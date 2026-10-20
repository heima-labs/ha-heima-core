# Heima v3 - Layer 7: Extensions

**Status:** Defined V3 extension boundary, approved 2026-10-20 (CA4-129). Not implemented.
**Open corrections:** CA4-131 (Layer-8 surface).

**Layer:** 7 of 8. Builds on Layer 0's claims (§4), composed configuration generation (§4.7),
committed-state observers (§4.8), `FactSource` and non-forgeability (§5, §5.1), Runtime Scheduler
(§3.1) and diagnostics (§10); Layer 2's producer uniqueness (§2.3), report-age expiry (§3.2) and
previous-cycle inputs (§5.6); Layer 3's blueprint/instance contract (§4.1.2), slow-path scheduling and
resource governance (§5.1, §5.3), finding egress (§6.1.1) and proposal path (§6.2); and Layer 5's
evidence source (§4.1). Its decisions are recorded in `docs/v3_backlog.md` (CA4-127, CA4-129).

## Normative precedence

This specification owns the extension registry, the extension blueprint and instance contract,
extension invocation and failure policy, and the conditions for opening Heima to third-party
extensions. It does not restate the Layer 0–6 contracts it uses; where a rule here refers to one,
the owning layer wins. The backlog records decision history, not competing rules.

## 1. Purpose

An extension adds a domain capability to Heima without changing a core semantic registry: it reads
declared facts and published learning results, and produces ordinary facts, diagnostics and
reviewable proposal candidates. It never acts on the house. Layer 7 defines the boundary every
extension uses, so that the core keeps control of when an extension runs, what it sees, what it may
claim, and what happens when it fails.

Initial V3 extensions are **first-party**: they are written and reviewed by the core team and live in
the Heima repository. No external code is discovered or loaded. Third-party extensions are a future
option, reopened only under §11.

## 2. Scope and boundaries

Layer 7 owns:

- the closed, bootstrap-frozen `ExtensionRegistry` and the extension blueprint (§3);
- extension instances, their parameters and input slots, and where they are staged (§4);
- the extension input contract (§5) and output contract (§6);
- invocation, cadence and execution (§7);
- the failure policy and runtime state of an instance (§8);
- add, upgrade, remove and restart behavior (§9);
- the trust statement (§10) and the third-party reopening conditions (§11).

Layer 7 does not own, and an extension cannot extend:

- the core semantic registries: `Interpretation`, `FusionStrategy`, `RegisteredFormula` (Layer 2 §2.1),
  `SemanticResolverRegistry` (Layer 4), learning types and models (Layer 3 §4.1.1),
  `ReactionDescriptorRegistry`, candidate kinds, relation and guard profiles (Layer 5),
  notification kinds (Layer 6), response owners and committed-state subscriptions (Layer 0);
- any action path: an extension never creates an `ApplyStep`, invokes an Actuator, registers a
  candidate kind or descriptor, or stages a custom action path (Layer 5 §2);
- the hot path: no extension code, lock, lookup or dynamic import runs during a Sensor, Fusion,
  resolver or Reaction evaluation (Layer 2 §2.2);
- person classification, actor identity, consent, audiences, and presence or household-context
  claims, other than as an ordinary producer of its own namespace (§5, §6);
- Heima's administration surface, which presents extensions through Layer 8 (CA4-131).

## 3. Extension registry and blueprint

`ExtensionRegistry` is constructed from extension types shipped in the Heima repository and frozen at
bootstrap, before any generation is staged. It is closed to administrators, learners and extensions;
its lookup performs no I/O, dynamic import or extension call. Each entry is an immutable
**blueprint**, following Layer 3 §4.1.2:

```python
@dataclass(frozen=True)
class ExtensionInputSlot:
    slot_id: str
    fact_type: str                    # exact core or ext.* fact type; never a pattern
    value_contract: CanonicalJsonObject  # value type, canonical unit or closed vocabulary
    location_kinds: frozenset[str]    # legal Location scope kinds for the instance binding
    history: Window | None            # bounded history read; None reads the current value only

@dataclass(frozen=True)
class ExtensionClaim:
    fact_type: str                    # ext.<extension_id>.<name>, exact
    emission_kind: FactEmissionKind
    value_contract: CanonicalJsonObject
    max_result_age: Window | None     # required for a state claim, None for an event claim;
                                      # >= cadence + CALIBRATION_WINDOW; expiry makes the state
                                      # unavailable (§8)
    max_emissions_per_run: int | None  # required for an event claim, None for a state claim

@dataclass(frozen=True)
class ExtensionProducerRole:
    inputs: tuple[ExtensionInputSlot, ...]
    claims: tuple[ExtensionClaim, ...]
    cadence: Window                   # fixed-delay interval; >= EXTENSION_MIN_INTERVAL (§7.2)
    invoke_on_input_change: bool
    resource_envelope: ResourceEnvelope  # Layer 3 §5.3

@dataclass(frozen=True)
class ExtensionAnalyzerRole:
    learner_inputs: tuple[str, ...]   # registered core learning type/role ids it may read
    candidate_contract: tuple[str, int, str, str]
                                      # exact (candidate_kind, kind version,
                                      #  reaction_descriptor_id, descriptor version)
    cadence: Window
    resource_envelope: ResourceEnvelope

@dataclass(frozen=True)
class ExtensionBlueprint:
    extension_id: str                 # [a-z][a-z0-9_]*; unique; namespace segment
    implementation_version: str
    producer: ExtensionProducerRole | None
    analyzer: ExtensionAnalyzerRole | None   # at least one role is present
    parameter_schema: CanonicalJsonObject    # bounded parameters with Layer-3 impact classes
```

Registration rejects a blueprint whose claims leave `ext.<extension_id>.`, whose state claim lacks a
`max_result_age` or has one shorter than its cadence plus `CALIBRATION_WINDOW` (Layer 3 §5.3.2, so a
forced calibration window never expires a healthy fact), whose event claim declares one or lacks a
positive `max_emissions_per_run`, whose cadence is shorter than §7.2's minimum, whose input slot names a
person-related fact (§5), or whose parameter schema exposes executable code, a raw HA entity or
service selector, an open field, or user-facing text. An analyzer role names an existing core
candidate kind and descriptor exactly; it cannot introduce either.

## 4. Instances and generation placement

An administrator creates only **instances** of a blueprint. An instance has a stable `instance_id`,
the blueprint's `extension_id` and `implementation_version`, an explicit scope, one canonical value
for every exposed parameter, the enabled state, and:

- for a producer role, one exact `(fact_type, Location)` binding per input slot and the exact
  `Location` of each claim;
- for an analyzer role, the exact core learner instances it reads, each of a type its blueprint lists.

Example: the `soil_dryness` blueprint has an input slot "soil moisture, percent, room or zone";
its instance for the balcony binds it to `soil.moisture@balcony` and claims
`ext.soil_dryness.index@balcony`.

**Requirements are derived, not declared.** An input slot binding is a consumer reference. If no
registered producer provides that exact key with a compatible value contract, the instance fails
validation; Layer 8 turns the missing key into a suggestion to create a `Sensor` (CA4-131). The
extension declares what it needs; the administrator creates the registry record (AR-8).

**Placement.** Layer 7 owns the blueprint registry, lifecycle and execution contract, but an instance
is staged by role in the generation of the layer that owns that role. There is no Layer-7
configuration generation:

- the producer role is a third producer kind in the **Layer-2 generation**, beside `Sensor` and
  `FusionRule`. Its claims enter the dependency index as producer claims and its slot bindings as
  consumer references (Layer 0 §4.7). Its input-to-output edge is a previous-cycle edge (Layer 2
  §5.6): it never contributes a same-cycle edge, so an extension that reads a Fusion output which
  in turn consumes the extension's fact creates no evaluation cycle;
- the analyzer role is a learning-analyzer instance in the **Layer-3 generation**, a consumer of the
  learner instances it reads.

An own Layer-7 generation would have to validate either before Layer 2 (losing its Layer-2 inputs)
or after it (so a Layer-2 Fusion could not consume extension facts, Layer 2 §2.1). Removing an
instance with both roles is one composed generation touching Layers 2 and 3. Parameters carry the
Layer-3 impact classes; a parameter change follows the same reload rules.

## 5. Inputs

A producer invocation receives one immutable `ExtensionInputSnapshot`:

- the current committed value of each bound input key, with its `available` flag and provenance;
- for a slot with `history`, the bounded history of that key through the standard Layer-0 query API
  (Layer 0 §4), never a bundled snapshot type;
- the ready calendar timeline snapshot (Layer 0 §3.4.1) when the blueprint declares it;
- the invocation instant and the instance's parameters.

Inputs are exact keys. A bound key may be a core fact or another instance's `ext.*` fact; chains
of extensions are allowed, each link adding at least one cycle of latency, and a removed upstream
instance makes its consumers breaking in the impact preview. An extension never reads raw Home
Assistant state, another layer's in-cycle output, engine context of the current cycle, or a fact it
did not declare.

**Person-related facts are excluded.** No slot may bind `presence@casa`, `household.*`, or any fact
about a `Person`, actor, consent or audience (people model invariant 8 and visibility matrix: an
extension is not a resident). Physical evidence such as `occupancy@room` and `occupancy@casa`
is readable.

An analyzer invocation receives the active `DiagnosticFinding` set and the published `ResultPayload`s
of the core learner instances it is bound to, as one immutable snapshot (Layer 3 §6.1.1). It has no
statistics, model or artifact of its own; the statistical work stays in reviewed core learner types.

## 6. Outputs

**Facts.** An extension instance produces only the facts its claims declare. Layer 0 reserves the
`ext.*` namespace for extensions: a non-extension producer may not claim inside it, and an extension
may claim only `ext.<own extension_id>.*`, never a core namespace or another extension's. Each
blueprint contributes `FactTypeClaim`s with `owner_id="layer7.extension.<extension_id>"`, and each
instance its exact `(fact_type, Location, owner_id)` state claims, so two instances cannot produce
the same key (Layer 2 §2.3). The runtime assigns the `FactSource`: `kind="extension"`,
`source_id=instance_id`, `source_type=extension_id`, and the `configuration_fingerprint` of the
active generation, which covers `implementation_version`; `route_fingerprint` is `None`. Nothing an
extension returns sets or changes these fields, and a returned value outside its claims is rejected
(Layer 0 §5.1).

A core consumer uses an extension fact only through an ordinary binding the administrator stages:
a `FusionRule` input, a learner slot, a resolver input or a Reaction binding, each validated and
previewed like any other (Layer 0 §4.7). For example, `ext.vision.person_detected` can become
physical evidence in the `occupancy@room` fusion. `presence@casa` (registered `person.*` sensors
only) and `household.guest_stay` (declared only) remain unreachable by construction.

**Diagnostics.** Operational diagnostics (run outcome, duration, cost, rejected outputs, runtime
state) are Layer-0 diagnostic events (§10). An extension never emits a `DiagnosticFinding`; that
registry is core and frozen.

**Candidates.** An analyzer may submit a `LearningProposalCandidate` only under the exact
candidate contract of its blueprint. It enters the ordinary Layer-5 validation, review and staging
path (Layer 3 §6.2). Its evidence source is `ProposalEvidenceSource(source_kind="extension_analyzer",
source_id=instance_id, ...)`, assigned by the runtime (Layer 5 §4.1); removing or invalidating the
instance makes its pending proposals not approvable.

## 7. Invocation and execution

### 7.1 Off the hot path

An extension never runs in the evaluation cycle. The core decides when it runs: at its fixed-delay
`cadence`, and, when `invoke_on_input_change` is set, after a committed change of a bound input,
observed through a core-declared committed-state subscription derived from the active generation
(Layer 0 §4.8). The run executes on the slow path governed by Layer 3 §5.1 and §5.3: it is admitted
against a `ResourceEnvelope` and runs as cooperative `step(WorkSliceBudget)` work within its
deadline, in the `extension` work class (Layer 3 §5.3.1): due extension slices run before learning
slices, extension runs are serial across the installation, a memory reservation keeps the largest
enabled envelope admissible, and the class is capped at half of the slow-path CPU credit. In
`capacity_unknown` no extension run is admitted and its facts expire (§8). Extensions start only
after the first health baseline at startup (Layer 3 §5.3.2). Results enter staging and are validated at
the next `CycleInputBarrier` like any ingress; an extension fact therefore lags its inputs by at
least one cycle.

Rationale: synchronous in-process Python cannot be preempted. Exception handling catches a raised
error, not a hang or a slow loop; keeping extensions off the hot path protects engine latency and
the Layer 2 §2.2 guarantees independently of non-core code, and lets the core decide when an
extension runs and what it sees. It does not bound CPU or memory (§10). A fact needed in the same
cycle must be produced by the core (Layer 2 §2.1); extensions are unsuitable for fast reactions such
as leak detection.

**Pure computation.** An extension's code receives its input snapshot and returns its result. It
performs no file, network or Home Assistant access, starts no thread or process, and keeps no state
between runs other than what it publishes as facts. Because Initial-V3 extensions are first-party,
this is enforced by code review, not by a sandbox (§10).

### 7.2 Cadence

Invocation follows Layer 3 §5.1's discipline: fixed-delay recurrence after the previous run ends,
at most one run per instance at a time, no queued second run, triggers arriving during a run
coalesced into one later run, no replay of missed ticks, and one jittered initial run after startup
or activation.

In addition, **`EXTENSION_MIN_INTERVAL` = 60 seconds** is the minimum time between the start of two
runs of the same instance, for both triggers. A blueprint cannot declare a shorter cadence, and an
input change sooner than that waits for the interval. It is a core constant, changed only by a new
specification version; neither an administrator nor a blueprint can lower it.

- Why only extensions: core hot-path producers run every cycle by design, and core learner types
  declare reviewed per-type minimum intervals gated by new evidence (Layer 3 §5.1). An
  input-triggered extension would otherwise run as often as a noisy sensor reports.
- Why 60 seconds: an extension already lags by at least one cycle, and anything that must react
  within seconds belongs in the core; the intended uses (soil moisture, weather indices, aggregates)
  change over minutes; with single-flight, the floor bounds one instance to one run per minute,
  independently of its inputs, which the capacity planner can predict.
- What it is not: not a freshness guarantee (§8, `max_result_age`) and not a resource limit
  (envelope and admission).

## 8. Failure policy

A run fails on an exception, a missed deadline, a budget rejection, an envelope breach detected at a
cooperative boundary (Layer 3 §5.3.1), an event claim emitted more than `max_emissions_per_run` times,
or an output that violates its claims or value contracts. A failed run is discarded atomically: no partial fact is written. A result
whose invocation or generation has been superseded is discarded on arrival.

Each state claim has a mandatory `max_result_age`; an event claim has none, because an event has no
current value to expire. Each successful run that publishes a state claim re-arms one ordinary Layer-0 `AtJob` for it (Layer 0 §3.1). If the job comes due without a newer
successful result, the core writes the fact `available=False` at the detecting instant, never
backdated, and passes the gap to Layer 0 §4.4, following Layer 2 §3.2's report-age expiry. A dead
extension is therefore unobservable, never a negative value (as in Layer 0 §5.1.2). Without this
rule, a state fact's last value would stay current indefinitely, because an old `when` never makes a
state stale (Layer 1 §4).

Each instance has a runtime-only state `healthy | backing_off | faulted`. Consecutive failures move
it to `backing_off` with core-constant backoff, and to `faulted` after the core-constant failure
count; it returns to `healthy` after its first successful run. The state is diagnostic, not
configuration: an instance is never disabled automatically, because disablement is a configuration
mutation with impact preview (Layer 0 §4.7).

## 9. Lifecycle

Adding, upgrading or removing an instance is a configuration mutation in one composed generation with
impact preview and confirmation (Layer 0 §4.7). Changing extension code is a Heima release: a new
`implementation_version` changes the instance fingerprints, and bootstrap classifies dependents as
for any code upgrade.

On removal or invalidation, existing rules apply: consumers of its `ext.*` facts are breaking; a
Reaction consuming them becomes `configuration_invalid` (Layer 5 §4.2); history stays attributed by
generation fingerprint; an in-flight run cannot publish; and pending proposals from its analyzer
become not approvable (Layer 5 §4.1). Restart re-derives runtime state from the active generation and,
after the first health baseline, starts with one jittered run per enabled instance; missed runs are
not replayed. Each state claim's expiry job is re-armed from the instant of its last persisted result,
as Layer 2 §3.2 checks report age at its first fresh intake: a claim already older than
`max_result_age` becomes `available=False` at the first cycle, and the others expire on schedule.

## 10. Trust

What Layer 7 guarantees: an extension's output is validated and attributed by the core, it cannot
claim outside its namespace, forge its source, read undeclared or person-related facts, act on the
house, or block the evaluation cycle; a failure is discarded and made visible.

Initial V3 runs extensions in process, with the same protection level as core learners, plus three
measures that bound the damage of a defective extension:

- **Pure computation** (§7.1): no file, network or Home Assistant access and no threads, enforced by
  code review.
- **Disk bounded by construction**: an extension never writes storage itself. Its facts go through
  Layer-0 persistence (write-on-change, retention, retry-queue budget, Layer 0 §4.2–§4.6), state
  claims are fixed keys, and each event claim is bounded by `max_emissions_per_run`.
- **Memory and time checked between slices** (Layer 3 §5.3.1): a run exceeding its envelope stops at
  the next cooperative boundary, so the damage is bounded to one slice.

What it does not guarantee: hard isolation. Python cannot interrupt a slice in progress or offer a
portable hard memory/CPU kill (Layer 3 §5.3), and in-process code can technically reach engine
internals. Initial V3 accepts this because every extension is first-party, reviewed code, exactly as
for core learners. The boundary is a contract enforced on the data path, not a sandbox; hard
isolation is a condition for third-party code (§11).

## 11. Reopening conditions for third-party extensions

Loading code not written by the core team requires a new specification version that satisfies every
condition below:

1. Layer 2, 3 and 4 contracts are implemented and stable (V3-2, V3-3, V3-4).
2. A real external consumer exists.
3. A discovery mechanism is chosen (Python entry points or a `hass.data` handshake).
4. An explicit trust model: the loader assigns the origin (`first_party | third_party`), never the
   extension; an administrator grants trust per package with impact preview; and every third-party
   run executes out of process, in a worker with operating-system memory, CPU and time limits that
   can be killed without affecting Heima, through Layer 3 §5.3's execution boundary (bounded
   immutable request in, untrusted result out).
5. A public versioned API: which contracts are public, semantic versioning, a deprecation policy, and
   an explicit amendment of the "no backward compatibility" rule scoped to that surface.
6. A security review of the in-process surface.
7. An explicit decision on the options deferred here: person-related inputs for declared and
   administrator-approved extensions (§5), and analyzers with their own statistics or models (§5).

A third-party extension would still be `kind="extension"`; only its loader-assigned origin differs.

## 12. Guide cases (non-normative)

**Soil dryness.** The `soil_dryness` producer reads soil moisture and the outdoor temperature and
rain facts for a garden sector every 15 minutes and publishes `ext.soil_dryness.index@<sector>` with
`max_result_age` of one hour. An administrator creates a core learner instance whose slot binds that
fact; an analyzer role reads the learner's published results and submits a candidate under an
existing core descriptor, reviewed like any other proposal.

**Watering (counterexample).** A watering extension can publish dryness and advise, but it cannot
open a valve: it has no action path, cannot register a descriptor, and cannot command the valve's
Actuator. Automatic watering would require a core `ReactionDescriptor`, which is a core
specification change, not an extension capability.

## 13. Acceptance criteria (for the eventual implementation phase)

- The registry is frozen before staging; registration rejects a claim outside `ext.<extension_id>.`,
  `max_result_age` below the cadence plus 5 minutes, an event claim without `max_emissions_per_run`, a cadence below 60 seconds, a person-related input slot, an
  unknown candidate contract, and a parameter exposing code, raw entities, open fields or text.
- An instance whose slot key has no compatible producer fails validation and yields one missing-key
  requirement; creating the Sensor makes it validate.
- A non-extension claim inside `ext.*`, an extension claim in a core namespace or another
  extension's namespace, and two instances claiming the same key are rejected at staging.
- A returned fact outside the claims, a returned source field, or a value violating its contract
  rejects the whole run; `FactSource` is always `kind="extension"` with runtime-assigned fields.
- No extension code runs during a cycle; a result is applied at the next `CycleInputBarrier`.
- With a bound input changing every 5 seconds, runs start at most once per 60 seconds, one at a
  time, with intermediate changes coalesced; missed ticks are not replayed after restart.
- An event claim emitted beyond `max_emissions_per_run`, or a run exceeding its envelope at a slice
  boundary, fails the run and writes no fact.
- In `capacity_unknown` no run is admitted and state claims expire; after a restart, a claim older
  than `max_result_age` is unavailable at the first cycle and extensions run only after the first
  baseline.
- An exception, timeout or budget rejection writes no fact; repeated failures reach `faulted`
  without disabling the instance; one success restores `healthy`.
- Without a successful run, each state claim becomes `available=False` at `max_result_age`, not
  backdated, with an observation gap; a downstream Fusion sees an unavailable input.
- A late result from a superseded invocation or generation is discarded.
- Two chained extensions add one cycle of lag each; a read cycle between an extension and a Fusion is
  accepted as a previous-cycle edge.
- Removing an instance whose fact feeds a Fusion and whose analyzer has a pending proposal shows both
  as dependents, makes the Fusion consumer breaking and the proposal not approvable, in one commit.
- An analyzer receives only its bound learners' active findings and published results; it cannot
  submit a candidate outside its contract or emit a `DiagnosticFinding`.
- A watering extension has no way to create an `ApplyStep` or call an Actuator.
